"""TrustLens Phase 3 P3-WP3 — deterministic three-valued rule evaluator.

Evaluates ONE governed PUBLISHED rule against one submission's governed observation context and returns a
schema-valid `RuleEvaluationResult` (rule-evaluation-result.schema.json). It is the Kleene interpreter
frozen by ADR-0005 and specified by DET-001 §§6–10. It is a **data interpreter**: no rule-specific code,
no network, no clock, no LLM — pure over *(context, RuntimeKnowledge, evaluation_profile)*.

Input (P3WP3-010 / R3-016). Production evaluation consumes governed observation DATA through the
`*_from_governed` APIs — schema-valid indicator observations **plus** the normalized observations they
reference — and validates it internally via `observations.build_validated_context`, which returns a
deep-frozen internal `EvaluationObservationContext` (no caller-built context is ever accepted). Occurrence
structural semantics have ONE authoritative source — the normalized `observation.schema.json` instance —
reached through `indicator_observation.observation_refs`. The evaluator never reads a structural attribute
off an indicator observation (the governed indicator-observation schema forbids such fields).

Computation order (programme decision 3):

    raw observations
    → STRUCTURAL OCCURRENCE ELIGIBILITY (resolve observation_refs → polarity / attribution / mood)
    → raw LIVE-positive set (structurally-eligible, confidence-gated, combined with three-valued OR)
    → hard-risk override computation (on that raw live set)
    → EXECUTE governed SUPPRESS_INDICATOR at occurrence scope through observation_refs (associated occurrence
      FALSE; explicitly different occurrence unaffected; unresolved association UNKNOWN)
    → override-blockable soft suppression (SUPPRESS_RULE/CAP_SEVERITY/CONTEXT_ONLY) EXPOSED for WP4
    → required-combination evaluation → RuleEvaluationResult → (WP4) suppression/caps/context.

Invariants:
  * **Structural semantics are non-overridable.** A NEGATED / REPORTED / QUOTED / HYPOTHETICAL / purely
    DESCRIPTIVE occurrence is structurally non-live and can NEVER become a live positive via an override.
  * **Sparse observation sets.** An operand with no observation is `UNKNOWN` (missing information is not
    negative evidence), never `FALSE`. Only an explicit `NOT_OBSERVED`/`NOT_APPLICABLE` is `FALSE`.
  * **Multi-occurrence truth is three-valued OR** over per-occurrence live truth (P3WP3-011): any live TRUE
    → TRUE; else any UNKNOWN → UNKNOWN; else FALSE. A structurally non-live FALSE never dominates an
    unresolved possibly-live occurrence, and the result is order-independent.

Deferred downstream (left unset, never a placeholder): final SUPPRESS_RULE/CAP_SEVERITY/CONTEXT_ONLY and
the SUPPRESSED state (WP4); aggregation / risk / classification (WP5); rule_evidence_strength /
rule_detection_confidence (WP4/WP5); explanation prose / actions (WP6).
"""

from __future__ import annotations

import json
from collections.abc import Mapping as ABCMapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator

from . import kleene
from .indexes import category_of, operands
from .kleene import FALSE, TRUE, UNKNOWN
from .observations import (
    LIVE,
    NON_LIVE,
    UNRESOLVED,
    EvaluationObservationContext,
    IndicatorObservation,
    build_validated_context,
    structural_verdict,
)
from .runtime_knowledge import RuntimeKnowledge

_ROOT = Path(__file__).resolve().parents[2]
_RULE_SCHEMA_PATH = _ROOT / "knowledge" / "schemas" / "rule.schema.json"


@lru_cache(maxsize=1)
def _rule_validator() -> Draft202012Validator:
    """The governed rule JSON Schema validator (engine-side, offline, cached) — used only to validate
    caller-supplied CANDIDATE rule mappings on the non-production path."""
    schema = json.loads(_RULE_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _to_plain_json(obj: Any) -> Any:
    """Normalize ANY mapping/sequence (dict, MappingProxyType, custom Mapping, tuple, …) to plain
    JSON-compatible types so a caller-supplied candidate is schema-validated regardless of its concrete
    container type (P3WP3-R3-018 — concrete type is never provenance)."""
    if isinstance(obj, ABCMapping):
        return {str(k): _to_plain_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [_to_plain_json(v) for v in obj]
    return obj

SEVERITY_ORDER = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
_CONF_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
_GATE_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}

_SOFT_SUPPRESS_EFFECTS = ("SUPPRESS_RULE", "CAP_SEVERITY")

# Per-rule data faults that degrade ONE rule to NOT_APPLICABLE + evaluation_error (DET-001 §16). A
# deliberately NARROW set of malformed-rule/observation errors. It does NOT include WP2 load-time integrity
# faults (BundleLoadError/IntegrityError): those must fail the whole bundle closed (P3WP3-005).
_PER_RULE_FAULTS = (KeyError, ValueError, TypeError, IndexError)


class EvaluatorError(Exception):
    """A malformed rule encountered mid-evaluation (e.g. an unknown condition operator, or malformed
    candidate lifecycle/language_scope/logic). Caught by the per-rule isolation wrapper and surfaced as
    NOT_APPLICABLE + evaluation_error so a single bad rule degrades that rule only (DET-001 §16). Distinct
    from a RuntimeKnowledge integrity failure, which is a WP2 load-time fault that refuses the bundle."""


@dataclass(frozen=True)
class EvaluationProfile:
    """The pinned, governed knobs of one evaluation (DET-001 §16 reproducibility). WP3 consumes only the
    extraction-confidence gate; the matrix/policy ids are carried for provenance/replay parity."""

    extraction_confidence_gate: str = "MEDIUM"
    risk_matrix_id: str = "risk-matrix-v1"
    confidence_policy_id: str = "confidence-policy-v1"

    @property
    def gate_rank(self) -> int:
        return _GATE_RANK[self.extraction_confidence_gate]


DEFAULT_PROFILE = EvaluationProfile()


def _sev_min(a: str, b: str | None) -> str:
    if b is None:
        return a
    return a if SEVERITY_ORDER.index(a) <= SEVERITY_ORDER.index(b) else b


class RuleEvaluator:
    """Stateless-over-inputs interpreter bound to one immutable RuntimeKnowledge + evaluation profile."""

    def __init__(self, rk: RuntimeKnowledge, profile: EvaluationProfile | None = None) -> None:
        self.rk = rk
        self.profile = profile or DEFAULT_PROFILE
        self._positive_ids = frozenset(rk.index("indicators_by_id"))
        self._negative_ids = frozenset(rk.index("negative_indicators_by_id"))

    # ================================================================ public API (PRODUCTION)
    # The production evaluator OWNS the governed validation boundary (P3WP3-R3-016): callers pass governed
    # DATA (indicator-observation + normalized-observation dicts); the evaluator validates ONCE and builds a
    # private, deep-frozen context internally. No pre-built/validated context is ever accepted from a caller.

    def evaluate_rules_from_governed(self, indicator_observations: Iterable[Mapping[str, Any]],
                                     observations: Iterable[Mapping[str, Any]], *,
                                     language: str = "en", script: str = "Latn") -> tuple[dict, ...]:
        """Validate the governed observation data ONCE, then evaluate every executable PUBLISHED rule in
        lexical id order, isolating per-rule failures. Per-rule only — no aggregation (P3-WP5). Raises
        ValueError if the governed data is malformed (fail closed)."""
        ctx = build_validated_context(indicator_observations, observations, language=language, script=script)
        return tuple(self._evaluate_validated(rid, ctx) for rid in self.rk.published_rule_ids())

    def evaluate_rule_from_governed(self, rule_id: str, indicator_observations: Iterable[Mapping[str, Any]],
                                    observations: Iterable[Mapping[str, Any]], *,
                                    language: str = "en", script: str = "Latn") -> dict:
        """Validate the governed observation data, then evaluate ONE governed PUBLISHED rule resolved BY ID
        from RuntimeKnowledge (P3WP3-004). A non-`str` rule_id raises `TypeError`; an unknown id →
        NOT_APPLICABLE{RULE_NOT_FOUND}; a non-PUBLISHED rule → NOT_APPLICABLE{RULE_NOT_PUBLISHED}. Raises
        ValueError if the governed data is malformed (fail closed)."""
        if not isinstance(rule_id, str):
            raise TypeError("evaluate_rule_from_governed requires a governed rule id (str)")
        ctx = build_validated_context(indicator_observations, observations, language=language, script=script)
        return self._evaluate_validated(rule_id, ctx)

    # ================================================================ design / validation APIs (non-production)

    def evaluate_on_promotion_from_governed(self, rule_id: str,
                                            indicator_observations: Iterable[Mapping[str, Any]],
                                            observations: Iterable[Mapping[str, Any]], *,
                                            language: str = "en", script: str = "Latn") -> dict:
        """DESIGN/VALIDATION ONLY — evaluate a rule resolved BY ID from RuntimeKnowledge REGARDLESS of
        lifecycle status (documents on-promotion behaviour of a not-yet-PUBLISHED governed rule). The rule is
        trusted governed knowledge (already validated at WP2 load); the observation data is validated here."""
        if not isinstance(rule_id, str):
            raise TypeError("evaluate_on_promotion_from_governed requires a governed rule id (str)")
        ctx = build_validated_context(indicator_observations, observations, language=language, script=script)
        rule = self.rk.rule(rule_id)
        if rule is None:
            return self._not_applicable(rule_id, "0.0.0", "COMPOSITE",
                                        "RULE_NOT_FOUND", f"no rule {rule_id!r} in RuntimeKnowledge")
        rid = rule["id"]
        rver = str(rule.get("rule_version") or rule.get("schema_version") or "0.0.0")
        return self._run_isolated(rule, rid, rver, rule.get("kind", "COMPOSITE"), ctx, candidate=True)

    def evaluate_candidate_rule_from_governed(self, rule_mapping: Mapping[str, Any],
                                              indicator_observations: Iterable[Mapping[str, Any]],
                                              observations: Iterable[Mapping[str, Any]], *,
                                              language: str = "en", script: str = "Latn") -> dict:
        """DESIGN/VALIDATION ONLY — evaluate a caller-supplied CANDIDATE rule mapping. The candidate is
        normalized to plain JSON REGARDLESS of concrete container type (dict / MappingProxyType / custom
        Mapping — concrete type is never provenance; P3WP3-R3-018) and validated against the governed
        rule.schema.json inside isolation, so a schema-invalid candidate degrades to NOT_APPLICABLE +
        evaluation_error rather than matching. The observation data is validated by build_validated_context."""
        ctx = build_validated_context(indicator_observations, observations, language=language, script=script)
        return self._evaluate_candidate_validated(rule_mapping, ctx)

    # ================================================================ internal evaluation (over a built ctx)

    def _evaluate_validated(self, rule_id: str, ctx: EvaluationObservationContext) -> dict:
        """PUBLISHED-only evaluation of one rule against an already-validated context (internal)."""
        rule = self.rk.rule(rule_id)
        if rule is None:
            return self._not_applicable(rule_id, "0.0.0", "COMPOSITE",
                                        "RULE_NOT_FOUND", f"no rule {rule_id!r} in RuntimeKnowledge")
        status = rule.get("lifecycle", {}).get("status")
        if status != "PUBLISHED":
            rver = str(rule.get("rule_version") or rule.get("schema_version") or "0.0.0")
            return self._not_applicable(rule_id, rver, rule.get("kind", "COMPOSITE"),
                                        "RULE_NOT_PUBLISHED",
                                        f"rule {rule_id} status {status!r} is not PUBLISHED (not executable live)")
        rid = rule["id"]
        rver = str(rule.get("rule_version") or rule.get("schema_version") or "0.0.0")
        return self._run_isolated(rule, rid, rver, rule.get("kind", "COMPOSITE"), ctx, candidate=False)

    def _evaluate_candidate_validated(self, rule_mapping: Mapping[str, Any],
                                      ctx: EvaluationObservationContext) -> dict:
        try:
            if not isinstance(rule_mapping, ABCMapping):
                raise EvaluatorError(f"candidate rule must be a mapping, got {type(rule_mapping).__name__}")
            plain = _to_plain_json(rule_mapping)   # normalize dict/mappingproxy/custom Mapping → JSON
            errs = sorted(_rule_validator().iter_errors(plain), key=lambda e: list(e.path))
            if errs:
                e = errs[0]
                raise EvaluatorError(f"candidate rule fails rule.schema.json: {e.message} "
                                     f"at /{'/'.join(map(str, e.path))}")
            rid = plain.get("id", "TL-XXX-000")
            rver = str(plain.get("rule_version") or plain.get("schema_version") or "0.0.0")
            kind = plain.get("kind", "COMPOSITE")
        except (EvaluatorError, *_PER_RULE_FAULTS) as e:
            return self._not_applicable("TL-XXX-000", "0.0.0", "COMPOSITE",
                                        "RULE_EVALUATION_ERROR", f"malformed candidate metadata: {e}")
        return self._run_isolated(plain, rid, rver, kind, ctx, candidate=True)

    # ---- shared isolation + dispatch ----
    def _run_isolated(self, rule: Mapping[str, Any], rid: str, rver: str, kind: str,
                      ctx: EvaluationObservationContext, *, candidate: bool) -> dict:
        try:
            scope = rule.get("language_scope", {})
            if not isinstance(scope, ABCMapping):
                raise EvaluatorError(f"rule {rid}: 'language_scope' must be an object")
            if not self._language_in_scope(scope, ctx):
                return self._not_applicable(rid, rver, kind, "LANGUAGE_OUT_OF_SCOPE",
                                            f"input {ctx.language}/{ctx.script} outside rule language_scope")
            if kind == "SUPPRESSION":
                return self._evaluate_suppression(rule, rid, rver, ctx)
            return self._evaluate_composite(rule, rid, rver, ctx)
        except EvaluatorError as e:
            return self._not_applicable(rid, rver, kind, "RULE_EVALUATION_ERROR", str(e))
        except _PER_RULE_FAULTS as e:
            return self._not_applicable(rid, rver, kind, "RULE_EVALUATION_ERROR", f"{type(e).__name__}: {e}")

    # ================================================================ COMPOSITE path

    def _evaluate_composite(self, rule: Mapping[str, Any], rid: str, rver: str,
                            ctx: EvaluationObservationContext) -> dict:
        logic = rule.get("logic", {})
        if not isinstance(logic, ABCMapping):
            raise EvaluatorError(f"rule {rid}: 'logic' must be an object, got {type(logic).__name__}")
        require = logic.get("require")
        min_classes = int(logic.get("min_evidence_classes", 2))
        rule_categories = self._rule_categories(rule)

        # 1) structurally-eligible LIVE-positive truth. Structural occurrence semantics are OCCURRENCE-SCOPED
        #    (P3WP3-R3-017): a NEGATED/REPORTED/QUOTED occurrence is non-live via its OWN backing observation
        #    (observation_refs), so it never yields a live positive and a *separate* live occurrence is
        #    unaffected. This is distinct from the governed SUPPRESS_INDICATOR library effect (executed in
        #    step 3). Multiple occurrences combine by three-valued OR.
        pos_truth, neutralised = self._positive_truth_map(ctx)
        neutralised = set(neutralised)

        def truth(indicator_id: str) -> str:
            entry = pos_truth.get(indicator_id)
            if entry is not None:
                return entry[0]
            return UNKNOWN  # SPARSE: an absent operand is UNKNOWN, never FALSE

        # 2) hard-risk overrides on the raw structurally-eligible live-positive set (DET-001 §10), computed
        #    BEFORE governed suppression is executed (resolution order: overrides FROM the raw live set).
        active_overrides, blocked_categories = self._active_overrides(rule, rid, rule_categories, truth)

        # 3) EXECUTE governed SUPPRESS_INDICATOR pre-match (DET-001 §11 / ADR-0005 §2) at OCCURRENCE scope.
        #    An active suppressor can neutralise only target-positive occurrences associated through governed
        #    observation_refs. Explicitly disjoint occurrences are unaffected; an unresolved association makes
        #    the otherwise-live target occurrence UNKNOWN. Structural non-live remains FALSE and authoritative.
        neg_active = self._active_negatives(ctx)
        matched_negative = sorted(n for n in neg_active if self._negative_applies(n, rule_categories))
        suppressors_by_target = self._active_suppressor_occurrences(
            ctx, matched_negative, active_overrides, blocked_categories
        )
        for tgt, suppressors in sorted(suppressors_by_target.items()):
            if tgt not in pos_truth:
                continue
            val, reason, occurrence_neutralised = self._combine_positive(ctx, tgt, suppressors)
            pos_truth[tgt] = (val, reason)
            if val == FALSE and occurrence_neutralised:
                neutralised.add(tgt)
            elif val != FALSE:
                neutralised.discard(tgt)

        # 4) Kleene evaluation of the required combination (post structural eligibility + executed suppression).
        required = self._eval_condition(require, truth)

        # 5) decisive operands + evidence-class diversity (over the TRUE positive operands).
        operand_ids = sorted(self._operand_ids(require))
        pos_operands = [o for o in operand_ids if o in self._positive_ids]
        matched_positive = sorted(o for o in pos_operands if truth(o) == TRUE)
        evidence_classes = sorted({
            ec for o in matched_positive
            if (ec := (self.rk.indicator(o) or {}).get("evidence_class"))
        })
        diversity_met = len(evidence_classes) >= min_classes

        # 6) evaluation state (STEP 5).
        if required == TRUE:
            state = "MATCHED" if diversity_met else "NOT_MATCHED"
        elif required == FALSE:
            state = "NOT_MATCHED"
        else:
            state = "INDETERMINATE"

        # 7) uncertainty ledger over decisive operands that resolved UNKNOWN.
        ambiguities, unknowns = self._uncertainty(pos_operands, pos_truth)

        # 8) soft suppression candidates exposed for WP4 (override-blockable SUPPRESS_RULE/CAP_SEVERITY +
        #    CONTEXT_ONLY). Governed SUPPRESS_INDICATOR was already EXECUTED pre-match (step 3).
        suppression = self._suppression_candidates(matched_negative, blocked_categories, bool(active_overrides))

        # ---- assemble ----
        result: dict[str, Any] = {
            "rule_id": rid,
            "rule_version": rver,
            "kind": "COMPOSITE",
            "evaluation_state": state,
            "required_combination_result": required,
            "matched_positive_indicators": matched_positive,
            "evidence_classes_spanned": evidence_classes,
            "min_evidence_classes_required": min_classes,
            "evidence_class_diversity_met": diversity_met,
            "rule_evidence_verdict": rule.get("evidence", {}).get("verdict"),
            "rule_severity_declared": rule.get("severity"),
        }
        declared_sev = rule.get("severity")
        if declared_sev:
            result["effective_severity"] = _sev_min(declared_sev, rule.get("evidence", {}).get("severity_cap"))

        if matched_negative:
            result["matched_negative_indicators"] = matched_negative
        if neutralised:
            result["neutralised_indicators"] = sorted(neutralised)
        if active_overrides:
            result["active_overrides"] = active_overrides
        if suppression:
            result["suppression"] = suppression

        conf_inputs = self._extraction_confidence_inputs(pos_operands, ctx)
        if conf_inputs:
            result["extraction_confidence_inputs"] = conf_inputs

        obs_refs = self._collect_refs(pos_operands, matched_negative, ctx)
        if obs_refs:
            result["observation_refs"] = obs_refs
        if ambiguities:
            result["ambiguities"] = ambiguities
        if unknowns:
            result["unknowns"] = unknowns

        if state == "MATCHED":
            self._attach_match_provenance(result, rule)
        return result

    # ================================================================ SUPPRESSION path (kept distinct)

    def _evaluate_suppression(self, rule: Mapping[str, Any], rid: str, rver: str,
                              ctx: EvaluationObservationContext) -> dict:
        logic = rule.get("logic", {})
        if not isinstance(logic, ABCMapping):
            raise EvaluatorError(f"rule {rid}: 'logic' must be an object, got {type(logic).__name__}")
        require = logic.get("require")
        neg_truth = self._negative_truth_map(ctx)

        def truth(indicator_id: str) -> str:
            entry = neg_truth.get(indicator_id)
            return entry[0] if entry is not None else UNKNOWN  # sparse: absent negative -> UNKNOWN

        required = self._eval_condition(require, truth)
        state = {TRUE: "MATCHED", FALSE: "NOT_MATCHED", UNKNOWN: "INDETERMINATE"}[required]

        operand_ids = sorted(self._operand_ids(require))
        matched_negative = sorted(o for o in operand_ids if truth(o) == TRUE)

        result: dict[str, Any] = {
            "rule_id": rid,
            "rule_version": rver,
            "kind": "SUPPRESSION",
            "evaluation_state": state,
            "required_combination_result": required,
            "rule_evidence_verdict": rule.get("evidence", {}).get("verdict"),
        }
        if matched_negative:
            result["matched_negative_indicators"] = matched_negative
        obs_refs = self._collect_refs([], matched_negative, ctx)
        if obs_refs:
            result["observation_refs"] = obs_refs
        if state == "MATCHED":
            self._attach_match_provenance(result, rule)
        return result

    # ================================================================ positive truth (structural + OR)

    def _positive_truth_map(self, ctx: EvaluationObservationContext) -> tuple[dict[str, tuple[str, str]], frozenset[str]]:
        out: dict[str, tuple[str, str]] = {}
        neutralised: set[str] = set()
        for iid in ctx.present_indicator_ids():
            if iid not in self._positive_ids:
                continue  # negatives handled separately; unknown ids ignored
            val, reason, structurally_neutralised = self._combine_positive(ctx, iid)
            out[iid] = (val, reason)
            if val == FALSE and structurally_neutralised:
                neutralised.add(iid)
        return out, frozenset(neutralised)

    def _combine_positive(self, ctx: EvaluationObservationContext, iid: str,
                          suppressors: Iterable[IndicatorObservation] = ()) -> tuple[str, str, bool]:
        """Combine a positive indicator's occurrences into one Kleene value + reason via three-valued OR
        over per-occurrence live truth (P3WP3-011). Each occurrence's live truth is its confidence-gated
        truth GATED BY structural eligibility (resolved from observation_refs): NON_LIVE → FALSE; LIVE →
        gate truth; UNRESOLVED → FALSE only if the gate is an explicit absence, else UNKNOWN (never guessed
        live). Active SUPPRESS_INDICATOR occurrences are then applied only to positive occurrences sharing an
        observation_ref. Explicitly disjoint refs do not interact; a missing ref on either side makes the
        association unresolved and turns an otherwise-live/uncertain occurrence UNKNOWN. Order-independent.
        The third return flag records occurrence neutralisation (structural or associated suppression), not an
        affirmative NOT_OBSERVED absence."""
        suppressors = tuple(suppressors)
        occ: list[tuple[str, str]] = []          # (kleene, reason) per occurrence
        occurrence_neutralised = False
        for io in ctx.observations_for(iid):
            if io.polarity is not None and io.polarity != "POSITIVE":
                occ.append((UNKNOWN, "polarity_mismatch"))
                continue
            g, gr = self._gate_single(io.matched, io.confidence)
            s = structural_verdict(ctx.observations_by_id, io)   # module free function (no subclass polymorphism)
            if s == NON_LIVE:
                if g != FALSE:  # a would-be-live/uncertain occurrence forced FALSE by structure (not mere absence)
                    occurrence_neutralised = True
                value, reason = FALSE, "structural_nonlive"
            elif s == LIVE:
                value, reason = g, gr
            else:  # UNRESOLVED — cannot establish the structural association
                value, reason = (FALSE, gr) if g == FALSE else (UNKNOWN, "unresolved_structure")

            # Structure and explicit absence are authoritative FALSE. Suppression can only neutralise an
            # otherwise-live/uncertain occurrence, never resurrect or weaken a structural FALSE.
            if value != FALSE and suppressors:
                associated, unresolved = self._suppression_association(io, suppressors)
                if associated:
                    occurrence_neutralised = True
                    value, reason = FALSE, "associated_suppression"
                elif unresolved:
                    value, reason = UNKNOWN, "unresolved_suppression_association"
            occ.append((value, reason))

        if any(t == TRUE for t, _ in occ):
            return (TRUE, "observed_live", occurrence_neutralised)
        unknown_reasons = [r for t, r in occ if t == UNKNOWN]
        if unknown_reasons:
            for pref in ("unresolved_suppression_association", "ambiguous", "unresolved_structure", "polarity_mismatch",
                         "low_confidence", "confidence_absent", "unknown_extraction"):
                if pref in unknown_reasons:
                    return (UNKNOWN, pref, occurrence_neutralised)
            return (UNKNOWN, "unknown_extraction", occurrence_neutralised)
        return (FALSE, "neutralised" if occurrence_neutralised else "not_observed", occurrence_neutralised)

    @staticmethod
    def _suppression_association(positive: IndicatorObservation,
                                 suppressors: Iterable[IndicatorObservation]) -> tuple[bool, bool]:
        """Return (associated, unresolved) for one positive occurrence.

        Any shared governed observation_ref is an explicit association. Two non-empty disjoint ref sets are
        explicitly different occurrences. If either side has no refs, the association cannot be resolved.
        An explicit association wins over an additional unresolved suppressor because this occurrence is known
        to be neutralised.
        """
        positive_refs = frozenset(positive.observation_refs)
        unresolved = False
        for suppressor in suppressors:
            suppressor_refs = frozenset(suppressor.observation_refs)
            if not positive_refs or not suppressor_refs:
                unresolved = True
            elif positive_refs & suppressor_refs:
                return True, unresolved
        return False, unresolved

    # ================================================================ negative truth

    def _negative_truth_map(self, ctx: EvaluationObservationContext) -> dict[str, tuple[str, str]]:
        out: dict[str, tuple[str, str]] = {}
        for iid in ctx.present_indicator_ids():
            if iid not in self._negative_ids:
                continue
            out[iid] = self._combine_negative(ctx.observations_for(iid), iid)
        return out

    def _active_negatives(self, ctx: EvaluationObservationContext) -> frozenset[str]:
        return frozenset(nid for nid, (val, _) in self._negative_truth_map(ctx).items() if val == TRUE)

    def _combine_negative(self, occs: Iterable[IndicatorObservation], iid: str) -> tuple[str, str]:
        """Confidence-gated three-valued OR over a NEGATIVE indicator's occurrences (structural eligibility
        does not apply — a negative indicator IS the structural/suppressive fact)."""
        gated: list[tuple[str, str]] = []
        for io in occs:
            if io.polarity is not None and io.polarity != "NEGATIVE":
                gated.append((UNKNOWN, "polarity_mismatch"))
                continue
            gated.append(self._gate_single(io.matched, io.confidence))
        vals = {g for g, _ in gated}
        if TRUE in vals:
            return (TRUE, "observed")
        if UNKNOWN in vals:
            reasons = [r for g, r in gated if g == UNKNOWN]
            for pref in ("ambiguous", "polarity_mismatch", "low_confidence",
                         "confidence_absent", "unknown_extraction"):
                if pref in reasons:
                    return (UNKNOWN, pref)
            return (UNKNOWN, "unknown_extraction")
        return (FALSE, "not_observed")

    def _gate_single(self, matched: str, confidence: str | None) -> tuple[str, str]:
        """DET-001 §8 extraction-confidence gate for ONE occurrence. LOW → UNKNOWN (never FALSE);
        UNKNOWN/AMBIGUOUS → UNKNOWN; OBSERVED with NO declared confidence → UNKNOWN (never silently HIGH)."""
        if matched == "OBSERVED":
            if confidence is None:
                return (UNKNOWN, "confidence_absent")
            if _CONF_RANK[confidence] >= self.profile.gate_rank:
                return (TRUE, "observed")
            return (UNKNOWN, "low_confidence")
        if matched in ("NOT_OBSERVED", "NOT_APPLICABLE"):
            return (FALSE, "not_observed")
        if matched == "AMBIGUOUS":
            return (UNKNOWN, "ambiguous")
        return (UNKNOWN, "unknown_extraction")

    # ================================================================ overrides

    def _active_overrides(self, rule: Mapping[str, Any], rid: str, rule_categories: frozenset[str],
                          truth) -> tuple[list[str], frozenset[str]]:
        """Hard-risk overrides active for this rule, computed on the RAW STRUCTURALLY-ELIGIBLE live-positive
        set (DET-001 §10). Because `truth` already reflects structural eligibility, an override can NEVER be
        activated by, nor resurrect, a structurally non-live occurrence."""
        active: list[str] = []
        blocked: set[str] = set()
        overrides_by_id = self.rk.index("overrides_by_id")
        for oid in sorted(overrides_by_id):
            ov = overrides_by_id[oid]
            if not self._override_applies(ov, rid, rule_categories):
                continue
            if self._eval_condition(ov.get("condition"), truth) == TRUE:
                active.append(oid)
                blocked.update(ov.get("blocks_suppression_categories", ()))
        return active, frozenset(blocked)

    def _override_applies(self, ov: Mapping[str, Any], rid: str, rule_categories: frozenset[str]) -> bool:
        if rid in ov.get("applies_to_rules", ()):
            return True
        return bool(rule_categories & set(ov.get("applies_to_families", ())))

    def _negative_applies(self, nid: str, rule_categories: frozenset[str]) -> bool:
        fams = (self.rk.negative_indicator(nid) or {}).get("applicable_rule_families", ())
        return "*" in fams or bool(set(fams) & rule_categories)

    def _suppression_candidates(self, matched_negative: list[str], blocked_categories: frozenset[str],
                                override_active: bool) -> dict[str, Any]:
        """Expose (never resolve) the suppression picture for WP4: which override-blockable SOFT suppressors
        an active override would BLOCK (FR-042), and which CONTEXT_ONLY benign markers are present. Directional
        SUPPRESS_INDICATOR negatives are structural and never appear as 'blocked'."""
        blocked: list[str] = []
        context_only: list[str] = []
        for nid in matched_negative:
            neg = self.rk.negative_indicator(nid) or {}
            effect = neg.get("suppression_effect")
            cat = neg.get("category")
            if effect == "CONTEXT_ONLY":
                context_only.append(nid)
            elif override_active and effect in _SOFT_SUPPRESS_EFFECTS and cat in blocked_categories:
                blocked.append(nid)
        out: dict[str, Any] = {}
        if blocked:
            out["blocked_suppressors"] = sorted(blocked)
        if context_only:
            out["context_only_present"] = sorted(context_only)
        return out

    def _active_suppressor_occurrences(self, ctx: EvaluationObservationContext, matched_negative: list[str],
                                       active_overrides: list[str], blocked_categories: frozenset[str],
                                       ) -> dict[str, tuple[IndicatorObservation, ...]]:
        """Return active governed suppressor occurrences grouped by target positive indicator.

        Association is deliberately not inferred here: `_combine_positive` resolves it only from the two
        occurrences' governed observation_refs. A suppressor is skipped only when explicitly override-blockable
        and blocked by an active override; no current directional suppressor is blockable.
        """
        targets: dict[str, list[IndicatorObservation]] = {}
        for nid in matched_negative:
            neg = self.rk.negative_indicator(nid) or {}
            if neg.get("suppression_effect") != "SUPPRESS_INDICATOR":
                continue
            if self._suppressor_blocked(neg, active_overrides, blocked_categories):
                continue
            active_occurrences = [
                io for io in ctx.observations_for(nid)
                if (io.polarity is None or io.polarity == "NEGATIVE")
                and self._gate_single(io.matched, io.confidence)[0] == TRUE
            ]
            for target in neg.get("suppresses_indicators", ()):
                targets.setdefault(target, []).extend(active_occurrences)
        return {target: tuple(occurrences) for target, occurrences in targets.items()}

    def _suppressor_blocked(self, neg: Mapping[str, Any], active_overrides, blocked_categories) -> bool:
        """A governed suppressor is blocked ONLY when it is EXPLICITLY override-blockable AND an active
        override blocks its category (FR-042). A non-override-blockable suppressor (every directional
        SUPPRESS_INDICATOR in the library) is NEVER blocked by an override."""
        return (bool(active_overrides)
                and bool(neg.get("blockable_by_overrides"))
                and neg.get("category") in blocked_categories)

    # ================================================================ condition evaluation

    def _eval_condition(self, cond: Any, truth) -> str:
        if isinstance(cond, str):
            return truth(cond)
        if not isinstance(cond, ABCMapping):
            raise EvaluatorError(f"condition node is neither an indicator id nor an operator object: {cond!r}")
        if "all_of" in cond:
            return kleene.all_of(self._eval_condition(x, truth) for x in cond["all_of"])
        if "any_of" in cond:
            return kleene.any_of(self._eval_condition(x, truth) for x in cond["any_of"])
        if "n_of" in cond:
            node = cond["n_of"]
            return kleene.n_of(int(node["n"]), [self._eval_condition(x, truth) for x in node.get("of", ())])
        raise EvaluatorError(f"unknown condition operator(s): {sorted(cond)} (expected all_of/any_of/n_of)")

    def _operand_ids(self, cond: Any) -> set[str]:
        """Every leaf indicator id in a condition tree — delegates to the single canonical, mappingproxy-safe
        walker `indexes.operands` so authoring and runtime can never drift."""
        return set(operands(cond))

    # ================================================================ small helpers

    def _rule_categories(self, rule: Mapping[str, Any]) -> frozenset[str]:
        return frozenset(c for t in rule.get("taxonomy_refs", ()) if (c := category_of(t)))

    def _language_in_scope(self, scope: Mapping[str, Any], ctx: EvaluationObservationContext) -> bool:
        langs = scope.get("languages")
        scripts = scope.get("scripts")
        if not langs and not scripts:
            return True
        base_lang = ctx.language.split("-")[0]
        lang_ok = (not langs) or (base_lang in langs)
        script_ok = (not scripts) or (ctx.script in scripts)
        return lang_ok and script_ok

    def _uncertainty(self, pos_operands: list[str],
                     pos_truth: Mapping[str, tuple[str, str]]) -> tuple[list[str], list[str]]:
        ambiguities: list[str] = []
        unknowns: list[str] = []
        for o in pos_operands:
            entry = pos_truth.get(o)
            if entry is None or entry[0] != UNKNOWN:
                continue
            reason = entry[1]
            if reason == "ambiguous":
                ambiguities.append(f"{o}: decisive operand AMBIGUOUS")
            elif reason == "unresolved_structure":
                ambiguities.append(f"{o}: decisive operand occurrence association unresolved "
                                   f"(live vs negated/reported cannot be established)")
            elif reason == "unresolved_suppression_association":
                ambiguities.append(f"{o}: decisive suppression occurrence association unresolved")
            elif reason == "polarity_mismatch":
                ambiguities.append(f"{o}: decisive operand polarity mismatch vs registry")
            else:
                unknowns.append(f"{o}: decisive operand UNKNOWN ({reason})")
        return sorted(ambiguities), sorted(unknowns)

    def _extraction_confidence_inputs(self, pos_operands: list[str],
                                      ctx: EvaluationObservationContext) -> dict[str, str]:
        out: dict[str, str] = {}
        for o in pos_operands:
            occs = ctx.observations_for(o)
            if not occs:
                continue
            out[o] = self._representative_confidence(occs)
        return dict(sorted(out.items()))

    def _representative_confidence(self, occs) -> str:
        """Highest declared level among OBSERVED reads; UNKNOWN when nothing was affirmatively observed or an
        OBSERVED read carried no declared level (never silently reported as HIGH)."""
        levels = [o.confidence for o in occs if o.matched == "OBSERVED" and o.confidence]
        if levels:
            return max(levels, key=lambda l: _CONF_RANK[l])
        return "UNKNOWN"

    def _collect_refs(self, pos_operands: list[str], matched_negative: list[str],
                      ctx: EvaluationObservationContext) -> list[str]:
        obs_refs: set[str] = set()
        for iid in list(pos_operands) + list(matched_negative):
            for io in ctx.observations_for(iid):
                obs_refs.update(io.observation_refs)
        return sorted(obs_refs)

    def _attach_match_provenance(self, result: dict, rule: Mapping[str, Any]) -> None:
        src_refs: list[dict] = []
        evidence_ids: set[str] = set()
        for ref in rule.get("evidence", {}).get("source_references", ()):
            mapped: dict[str, Any] = {
                "source_id": ref.get("source_id"),
                "issuing_body": ref.get("issuing_body"),
                "verification_status": ref.get("verification_status"),
            }
            if ref.get("authority"):
                mapped["authority"] = ref["authority"]
            mr = ref.get("manual_retrieval") or {}
            if mr.get("evidence_class"):
                mapped["evidence_class"] = mr["evidence_class"]
            if ref.get("quote"):
                mapped["quote"] = ref["quote"]
            src_refs.append(mapped)
            evidence_ids.update(mr.get("evidence_ids", ()))
        if src_refs:
            result["source_references"] = src_refs
        if evidence_ids:
            result["evidence_ids"] = sorted(evidence_ids)
        expl = rule.get("explanation", {})
        frag = {k: expl[k] for k in ("plain", "technical", "why_confidence_limited") if expl.get(k)}
        if frag:
            result["explanation_fragment"] = frag

    def _not_applicable(self, rid: str, rver: str, kind: str, code: str, message: str) -> dict:
        return {
            "rule_id": rid,
            "rule_version": rver,
            "kind": kind if kind in ("COMPOSITE", "SUPPRESSION") else "COMPOSITE",
            "evaluation_state": "NOT_APPLICABLE",
            "required_combination_result": UNKNOWN,
            "evaluation_error": {"code": code, "message": message},
        }


# ---- module-level convenience wrappers (production = governed DATA in, validated internally) ----

def evaluate_rule_from_governed(rk: RuntimeKnowledge, rule_id: str,
                                indicator_observations: Iterable[Mapping[str, Any]],
                                observations: Iterable[Mapping[str, Any]],
                                *, profile: EvaluationProfile | None = None,
                                language: str = "en", script: str = "Latn") -> dict:
    """Production convenience: validate governed observation data and evaluate one PUBLISHED rule by id."""
    return RuleEvaluator(rk, profile).evaluate_rule_from_governed(
        rule_id, indicator_observations, observations, language=language, script=script)


def evaluate_rules_from_governed(rk: RuntimeKnowledge,
                                 indicator_observations: Iterable[Mapping[str, Any]],
                                 observations: Iterable[Mapping[str, Any]],
                                 *, profile: EvaluationProfile | None = None,
                                 language: str = "en", script: str = "Latn") -> tuple[dict, ...]:
    """Production convenience: validate governed observation data once and evaluate all PUBLISHED rules."""
    return RuleEvaluator(rk, profile).evaluate_rules_from_governed(
        indicator_observations, observations, language=language, script=script)
