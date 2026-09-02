"""TrustLens Phase 3 P3-WP5 — deterministic decision aggregation, risk, confidence & classification.

Consumes the per-rule ``RuleEvaluationResult`` dicts produced by P3-WP4 (``suppression.py``) plus the
immutable ``RuntimeKnowledge`` and folds them into ONE decision-level result across the DET-001 axes that
the earlier work packages deferred (DET-001 §§4,5,9,10,11 / ADR-0006):

  * ``decision_severity``          — max EFFECTIVE severity over eligible MATCHED rules (never additive);
  * ``matched_evidence_strength``  — the governing rule's ADR-0006 composite strength;
  * ``risk_level``                 — fixed ADR-0006 matrix lookup (severity × strength);
  * ``detection_confidence``       — categorical LOW/MEDIUM/HIGH banding (never a probability);
  * ``corroboration``              — over PROVEN-INDEPENDENT governed evidence, never rule count;
  * ``classification``             — the governed final label;
  * the governing rule + reason, and the per-rule ADR-0006 strength.

WP5 is a *consumer* of WP3/WP4 truth. It NEVER re-derives operand truth, structural eligibility, hard-risk
overrides, or suppression (all owned upstream), and it **never inspects polarity/liveness itself**. Evidence
independence is proven ONLY from the authoritative ``live_positive_provenance`` that WP3 emits (the
provenance-output amendment): per matched-positive TRUE indicator, one grouped occurrence per structurally
LIVE contributing observation set. WP5 resolves decisive-indicator ``strength`` read-only through
``RuntimeKnowledge``.

Ratified WP5 policy (design decisions, adversarial-remediation gates):

  * **Proven-independent corroboration.** ONE quantity ``proven_independent_evidence_count`` drives BOTH the
    corroboration band AND the ``>= 3`` path to HIGH confidence. Live occurrence groups that share any
    observation_ref are merged (union-find) into ONE provenance component; the count is the maximum bipartite
    matching between distinct governed evidence classes and distinct provenance components. Missing
    ``live_positive_provenance`` contributes zero independence; a raw class-name count never drives HIGH.
  * **detection_confidence HIGH** ⇔ governing verdict ``SUPPORTED`` ∧ no decisive ``AMBIGUOUS`` ∧ minimum
    decisive extraction ``>= MEDIUM`` ∧ (``proven_independent_evidence_count >= 3`` ∨ active hard-risk
    override). Categorical, never a probability. ``degraded`` caps at MEDIUM; ``PARTIAL``/``HEURISTIC`` never
    reach HIGH; a ``LOW`` decisive extraction never HIGH.
  * ``PARTIAL``/``HEURISTIC`` governing verdict caps corroboration at MEDIUM.
  * **Unresolved harmful candidate** (rule-local) = COMPOSITE, INDETERMINATE, ``required_combination_result``
    UNKNOWN, AND a WP3-produced decisive ``ambiguities`` OR ``unknowns``. A sparse INDETERMINATE is INERT.
    ``matched_positive_indicators`` alone is never decisiveness.
  * **Affirmative benign clear** (STRICT, rule-local, effect-aware) = a COMPOSITE with ``NOT_MATCHED`` +
    ``required_combination_result`` FALSE, OR a COMPOSITE ``SUPPRESSED``. A negative-indicator id / a
    diversity-fail ``NOT_MATCHED``+TRUE / ``CONTEXT_ONLY`` / ``CAP_SEVERITY`` never clears.
  * **Classification precedence:** whole-evaluation ERROR → unsupported/insufficient support → eligible
    harmful MATCHED → degraded → unresolved harmful candidate → affirmative benign clear (only with NO
    unresolved harm) → INSUFFICIENT_EVIDENCE.

Fail-closed: every incoming result is JSON-Schema-validated against ``rule-evaluation-result.schema.json``
and then checked for the full WP5 semantic-invariant matrix (state↔required pairing incl. the legal
``NOT_MATCHED``+TRUE diversity-fail, evaluation_error placement, verdict presence, provenance key membership,
resolution of every governed reference); ``whole_evaluation_errors`` are validated against the promoted
``evaluationError`` contract. Any malformed/impossible input raises ``AggregationError`` (no raw
``KeyError``/``TypeError``/``AttributeError`` escapes, never a silent benign decision). Determinism: all
set-like arrays (incl. nested ``suppression`` and the grouped ``live_positive_provenance``) are canonicalised,
``rule_results`` sorted by ``rule_id``, ``errors`` sorted by a stable key; a permutation of valid inputs
yields a structurally identical result; duplicate whole rule result / duplicate ``rule_id`` fails closed.
WP5 emits NO WP6 field and no numeric score.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .evaluator import DEFAULT_PROFILE, SEVERITY_ORDER, EvaluationProfile

# ---- ordinal scales (single source of truth; SEVERITY_ORDER imported, never re-declared) ----
DECISION_SEVERITY_ORDER = ("NONE",) + SEVERITY_ORDER                 # NONE < LOW < MEDIUM < HIGH < CRITICAL
STRENGTH_ORDER = ("NONE", "WEAK", "MODERATE", "STRONG")
INDICATOR_STRENGTH_ORDER = ("WEAK", "MODERATE", "STRONG")
CONFIDENCE_ORDER = ("LOW", "MEDIUM", "HIGH")
CORROBORATION_BANDS = ("NONE", "LOW", "MEDIUM", "HIGH")

_VERDICT_RANK = {"SUPPORTED": 3, "PARTIAL": 2, "HEURISTIC": 1, "UNSUPPORTED": 0}
_VERDICT_STRENGTH_CAP = {"SUPPORTED": "STRONG", "PARTIAL": "MODERATE", "HEURISTIC": "WEAK", "UNSUPPORTED": "WEAK"}
_VALID_VERDICTS = frozenset(_VERDICT_RANK)

# ADR-0006 risk matrix v1 (risk-matrix-v1): risk = M[decision_severity][matched_evidence_strength]. Ordinal,
# not a probability. Byte-identical to docs/03-detection/validate_det_design.py (drift asserted by the gate).
RISK_MATRIX: Mapping[str, Mapping[str, str]] = {
    "NONE": {"NONE": "NONE"},
    "LOW": {"WEAK": "LOW", "MODERATE": "LOW", "STRONG": "MEDIUM"},
    "MEDIUM": {"WEAK": "LOW", "MODERATE": "MEDIUM", "STRONG": "MEDIUM"},
    "HIGH": {"WEAK": "MEDIUM", "MODERATE": "HIGH", "STRONG": "HIGH"},
    "CRITICAL": {"WEAK": "HIGH", "MODERATE": "HIGH", "STRONG": "CRITICAL"},
}

RISK_MATRIX_ID = "risk-matrix-v1"
CONFIDENCE_POLICY_ID = "confidence-policy-v1"

_SUPPORT_STATES = ("SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "INSUFFICIENT_INFORMATION", "ERROR")
_EVALUABLE_SUPPORT = ("SUPPORTED", "PARTIALLY_SUPPORTED")
_CONFIDENCE_GE = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
_AGG_FAULTS = (KeyError, ValueError, TypeError, IndexError, AttributeError)

# state ↔ required_combination_result pairing (ratified). NOT_MATCHED legally carries TRUE (evidence-class
# diversity gate: require TRUE but < min_evidence_classes → NOT_MATCHED) or FALSE. NOT_APPLICABLE preserves
# the upstream combination truth on degrade, so it is unconstrained but must carry an evaluation_error.
_REQUIRED_FOR_STATE = {
    "MATCHED": ("TRUE",),
    "SUPPRESSED": ("TRUE",),
    "INDETERMINATE": ("UNKNOWN",),
    "NOT_MATCHED": ("TRUE", "FALSE"),
    "NOT_APPLICABLE": ("TRUE", "FALSE", "UNKNOWN"),
}

_ROOT = Path(__file__).resolve().parents[2]
_RULE_EVAL_SCHEMA_PATH = _ROOT / "knowledge" / "schemas" / "detection" / "rule-evaluation-result.schema.json"
_DETECTION_SCHEMA_PATH = _ROOT / "knowledge" / "schemas" / "detection" / "detection-result.schema.json"

_WP5_OWNED_FIELDS = frozenset({"governing", "governing_reason", "rule_evidence_strength", "rule_detection_confidence"})


class AggregationError(Exception):
    """A malformed / impossible decision-aggregation input: a schema-invalid rule result, an invalid or
    missing verdict/severity, an invalid state↔required pairing, an evaluation_error on a normal state, an
    unresolved governed reference (positive/negative/neutralised/override/live provenance), a duplicate
    whole rule result / duplicate ``rule_id``, a pre-populated WP5-owned field, a malformed
    ``whole_evaluation_errors`` entry, an illegal severity×strength matrix cell, or an unknown support
    status. WP5 fails closed on it — never a silent ``NO_SCAM_PATTERN`` or normal low-risk decision."""


@lru_cache(maxsize=1)
def _rule_result_validator() -> Draft202012Validator:
    rev = json.loads(_RULE_EVAL_SCHEMA_PATH.read_text(encoding="utf-8"))
    det = json.loads(_DETECTION_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(rev)
    registry = Registry().with_resources([
        (rev["$id"], Resource.from_contents(rev)),
        (det["$id"], Resource.from_contents(det)),
    ])
    return Draft202012Validator(rev, registry=registry)


@lru_cache(maxsize=1)
def _whole_error_validator() -> Draft202012Validator:
    """Validator for one whole_evaluation_errors entry against the promoted detection-result
    ``$defs/evaluationError`` contract (resolves its internal ``#/$defs/ruleId``)."""
    det = json.loads(_DETECTION_SCHEMA_PATH.read_text(encoding="utf-8"))
    registry = Registry().with_resources([(det["$id"], Resource.from_contents(det))])
    return Draft202012Validator({"$ref": det["$id"] + "#/$defs/evaluationError"}, registry=registry)


# ================================================================ result contract (internal, pre-WP6)


@dataclass(frozen=True)
class DecisionResult:
    """The WP5 decision block. It populates most of ``detection-result.schema.json`` but is NOT a full
    schema-valid document: ``explanation``/``recommended_actions`` (WP6) and ``provenance`` (result
    assembly) are added downstream. All arrays are canonically sorted + duplicate-free (determinism)."""

    input_support_status: str
    classification: str
    decision_severity: str
    matched_evidence_strength: str
    risk_level: str
    detection_confidence: str
    corroboration: Mapping[str, Any]
    governing_rule_id: str | None
    governing_reason: str | None
    matched_rules: tuple[str, ...]
    matched_positive_indicators: tuple[str, ...]
    matched_negative_indicators: tuple[str, ...]
    suppressed_indicators: tuple[str, ...]
    active_overrides: tuple[str, ...]
    ambiguities: tuple[str, ...]
    unknowns: tuple[str, ...]
    degraded: bool
    errors: tuple[Mapping[str, Any], ...]
    rule_results: tuple[Mapping[str, Any], ...]
    evaluation_profile: Mapping[str, str] = field(default_factory=dict)

    def as_decision_dict(self) -> dict:
        out: dict[str, Any] = {
            "input_support_status": self.input_support_status,
            "classification": self.classification,
            "decision_severity": self.decision_severity,
            "matched_evidence_strength": self.matched_evidence_strength,
            "risk_level": self.risk_level,
            "detection_confidence": self.detection_confidence,
            "corroboration_summary": dict(self.corroboration),
            "matched_rules": list(self.matched_rules),
            "matched_positive_indicators": list(self.matched_positive_indicators),
            "matched_negative_indicators": list(self.matched_negative_indicators),
            "suppressed_indicators": list(self.suppressed_indicators),
            "active_overrides": list(self.active_overrides),
            "rule_results": [dict(r) for r in self.rule_results],
            "degraded": self.degraded,
        }
        if self.ambiguities:
            out["ambiguities"] = list(self.ambiguities)
        if self.unknowns:
            out["unknowns"] = list(self.unknowns)
        if self.errors:
            out["errors"] = [dict(e) for e in self.errors]
        return out


# ================================================================ small ordinal / set helpers


def _ord_min(a: str, b: str, order: tuple[str, ...]) -> str:
    return a if order.index(a) <= order.index(b) else b


def _ord_max(a: str, b: str, order: tuple[str, ...]) -> str:
    return a if order.index(a) >= order.index(b) else b


def _sorted_unique(ids: Iterable[str]) -> list[str]:
    return sorted(set(ids))


# ================================================================ eligibility / predicates


def _is_composite(r: Mapping[str, Any]) -> bool:
    return r.get("kind") == "COMPOSITE"


def _is_eligible_matched(r: Mapping[str, Any]) -> bool:
    return (
        _is_composite(r)
        and r.get("evaluation_state") == "MATCHED"
        and r.get("required_combination_result") == "TRUE"
        and r.get("effective_severity") in SEVERITY_ORDER
    )


def _is_unresolved_harmful(r: Mapping[str, Any]) -> bool:
    """Rule-local decision-relevant unresolved harm (DET-001 §4/§15): a COMPOSITE INDETERMINATE with
    ``require`` UNKNOWN AND a WP3-produced decisive ``ambiguities`` OR ``unknowns`` (an observed-but-unresolved
    required operand). Never keyed on ``matched_positive_indicators``; a sparse INDETERMINATE is inert."""
    return (
        _is_composite(r)
        and r.get("evaluation_state") == "INDETERMINATE"
        and r.get("required_combination_result") == "UNKNOWN"
        and bool(r.get("ambiguities") or r.get("unknowns"))
    )


def _has_unresolved_harmful(results: Iterable[Mapping[str, Any]]) -> bool:
    return any(_is_unresolved_harmful(r) for r in results)


def _has_affirmative_benign_clear(results: Iterable[Mapping[str, Any]]) -> bool:
    """STRICT rule-local, effect-aware benign clear (DET-001 §4). ONLY a COMPOSITE whose combination came out
    FALSE, or a COMPOSITE that MATCHED then was SUPPRESSED. A NOT_MATCHED+TRUE diversity-fail is NOT a clear;
    a bare negative id / CONTEXT_ONLY / CAP_SEVERITY never clears."""
    for r in results:
        if not _is_composite(r):
            continue
        state = r.get("evaluation_state")
        if state == "SUPPRESSED":
            return True
        if state == "NOT_MATCHED" and r.get("required_combination_result") == "FALSE":
            return True
    return False


def _has_residual_observed_positive(results: Iterable[Mapping[str, Any]]) -> bool:
    return any(_is_composite(r) and r.get("matched_positive_indicators") for r in results)


# ================================================================ per-rule ADR-0006 strength


def _rule_evidence_strength(r: Mapping[str, Any], rk) -> str:
    verdict = r.get("rule_evidence_verdict")
    cap = _VERDICT_STRENGTH_CAP.get(verdict, "WEAK")
    strengths: list[str] = []
    for iid in r.get("matched_positive_indicators", ()):
        ind = rk.indicator(iid)
        if ind is None:
            raise AggregationError(
                f"rule {r.get('rule_id')}: matched positive {iid!r} does not resolve in RuntimeKnowledge")
        s = ind.get("strength")
        if s not in INDICATOR_STRENGTH_ORDER:
            raise AggregationError(f"rule {r.get('rule_id')}: indicator {iid!r} has invalid governed strength {s!r}")
        strengths.append(s)
    max_indicator = max(strengths, key=INDICATOR_STRENGTH_ORDER.index) if strengths else "WEAK"
    composite = _ord_min(max_indicator, cap, INDICATOR_STRENGTH_ORDER)
    if r.get("active_overrides"):
        composite = _ord_max(composite, "MODERATE", INDICATOR_STRENGTH_ORDER)
    return composite


# ================================================================ governing-rule selection


def _select_governing(eligible: list[Mapping[str, Any]]) -> Mapping[str, Any]:
    return sorted(
        eligible,
        key=lambda r: (
            -SEVERITY_ORDER.index(r["effective_severity"]),
            -_VERDICT_RANK.get(r.get("rule_evidence_verdict"), 0),
            -len(r.get("evidence_classes_spanned", ())),
            r["rule_id"],
        ),
    )[0]


def _governing_reason(gov: Mapping[str, Any], n_eligible: int) -> str:
    parts = [
        f"highest effective severity {gov.get('effective_severity')}",
        f"evidence verdict {gov.get('rule_evidence_verdict')}",
        f"{len(gov.get('evidence_classes_spanned', ()))} independent evidence class(es)",
    ]
    if n_eligible > 1:
        parts.append("selected over ties by severity > verdict (SUPPORTED>PARTIAL) > class breadth > lexical rule id")
    return "; ".join(parts)


# ================================================================ proven-independent corroboration


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)   # deterministic: lexically-smaller root wins


def _max_bipartite_matching(class_to_comp: Mapping[str, set[str]]) -> tuple[int, set[str]]:
    """Deterministic maximum matching between evidence classes (left) and provenance components (right).
    Returns (size, the maximum-cardinality subset of classes actually matched one-to-one to distinct
    components). Classes iterate in sorted order, so the selected subset is stable/reproducible and
    ``len(matched_classes) == size``."""
    match_comp: dict[str, str] = {}

    def augment(cls: str, seen: set[str]) -> bool:
        for comp in sorted(class_to_comp[cls]):
            if comp in seen:
                continue
            seen.add(comp)
            if comp not in match_comp or augment(match_comp[comp], seen):
                match_comp[comp] = cls
                return True
        return False

    for cls in sorted(class_to_comp):
        augment(cls, set())
    matched_classes = set(match_comp.values())
    return len(match_comp), matched_classes


def _proven_independence(eligible: list[Mapping[str, Any]], rk) -> tuple[int, set[str], list[str]]:
    """``proven_independent_evidence_count`` from authoritative WP3 ``live_positive_provenance`` ONLY.

    Live occurrence GROUPS that share any observation_ref merge (union-find) into one provenance COMPONENT;
    the count is the maximum bipartite matching between distinct governed evidence classes and distinct
    components. WP5 never inspects polarity/liveness. Missing provenance → zero independence. Returns
    (count, the maximum-cardinality class subset actually matched to distinct components [so
    ``len == count``], shared refs)."""
    entries: list[tuple[str, tuple[str, ...]]] = []      # (evidence_class, group refs)
    ref_uses: dict[str, int] = {}
    for r in eligible:
        prov = r.get("live_positive_provenance") or {}
        for iid in r.get("matched_positive_indicators", ()):
            ind = rk.indicator(iid)
            if ind is None:
                raise AggregationError(
                    f"rule {r.get('rule_id')}: matched positive {iid!r} does not resolve in RuntimeKnowledge")
            cls = ind.get("evidence_class")
            if not cls:
                continue
            for group in prov.get(iid, []):
                refs = tuple(sorted(set(group)))
                if refs:
                    entries.append((cls, refs))
                    for ref in refs:
                        ref_uses[ref] = ref_uses.get(ref, 0) + 1

    uf = _UnionFind()
    for _, refs in entries:
        for ref in refs:
            uf.find(ref)
        for ref in refs[1:]:
            uf.union(refs[0], ref)

    class_to_comp: dict[str, set[str]] = {}
    for cls, refs in entries:
        class_to_comp.setdefault(cls, set()).add(uf.find(refs[0]))

    count, matched_classes = _max_bipartite_matching(class_to_comp) if class_to_comp else (0, set())
    shared = sorted(ref for ref, n in ref_uses.items() if n > 1)
    return count, matched_classes, shared


def _corroboration(proven_count: int, classes: set[str], shared_refs: list[str],
                   governing_verdict: str | None) -> dict:
    band = "NONE" if proven_count == 0 else "LOW" if proven_count == 1 else "MEDIUM" if proven_count == 2 else "HIGH"
    if governing_verdict in ("PARTIAL", "HEURISTIC") and CORROBORATION_BANDS.index(band) > CORROBORATION_BANDS.index("MEDIUM"):
        band = "MEDIUM"
    out: dict[str, Any] = {
        "independent_evidence_classes": sorted(classes),
        "evidence_class_count": proven_count,
        "band": band,
    }
    if shared_refs:
        out["shared_observation_refs"] = shared_refs
    return out


def _corroboration_no_fire(results: list[Mapping[str, Any]], classification: str) -> dict:
    if (classification == "INSUFFICIENT_EVIDENCE"
            and not _has_unresolved_harmful(results)
            and _has_residual_observed_positive(results)):
        band = "LOW"
    else:
        band = "NONE"
    return {"independent_evidence_classes": [], "evidence_class_count": 0, "band": band}


# ================================================================ detection confidence


def _detection_confidence(gov: Mapping[str, Any], proven_count: int, profile: EvaluationProfile) -> str:
    verdict = gov.get("rule_evidence_verdict")
    no_ambiguity = not gov.get("ambiguities")
    override = bool(gov.get("active_overrides"))
    conf_inputs = gov.get("extraction_confidence_inputs", {}) or {}
    levels = [conf_inputs.get(iid, "UNKNOWN") for iid in gov.get("matched_positive_indicators", ())]
    min_conf_ge_medium = min((_CONFIDENCE_GE.get(lv, 0) for lv in levels), default=0) >= _CONFIDENCE_GE["MEDIUM"]

    if verdict == "SUPPORTED" and no_ambiguity and min_conf_ge_medium and (proven_count >= 3 or override):
        return "HIGH"
    supp = gov.get("suppression") or {}
    if supp.get("context_only_present") or verdict in ("HEURISTIC", "UNSUPPORTED"):
        return "LOW"
    return "MEDIUM"


# ================================================================ classification state machine


def _classify(support: str, eligible: list[Mapping[str, Any]], all_results: list[Mapping[str, Any]],
              detection_confidence: str, degraded: bool, whole_error: bool) -> str:
    if whole_error or support == "ERROR":
        return "ERROR"
    if support == "UNSUPPORTED":
        return "UNSUPPORTED"
    if support == "INSUFFICIENT_INFORMATION":
        return "INSUFFICIENT_EVIDENCE"
    if eligible:
        return "SCAM_PATTERN_SUSPECTED" if detection_confidence == "LOW" else "SCAM_PATTERN_DETECTED"
    if degraded:
        return "INSUFFICIENT_EVIDENCE"
    if _has_unresolved_harmful(all_results):
        return "INSUFFICIENT_EVIDENCE"
    if _has_affirmative_benign_clear(all_results):
        return "NO_SCAM_PATTERN"
    return "INSUFFICIENT_EVIDENCE"


# ================================================================ risk


def _risk_level(severity: str, strength: str) -> str:
    if severity == "NONE":
        return "NONE"
    cell = RISK_MATRIX.get(severity, {}).get(strength)
    if cell is None:
        raise AggregationError(
            f"illegal (decision_severity={severity!r}, matched_evidence_strength={strength!r}) for the risk matrix")
    return cell


# ================================================================ validation / canonicalisation

_SET_LIKE_RESULT_ARRAYS = (
    "matched_positive_indicators", "matched_negative_indicators", "active_overrides",
    "neutralised_indicators", "evidence_classes_spanned", "observation_refs",
    "indicator_observation_refs", "ambiguities", "unknowns", "evidence_ids",
)
_SET_LIKE_SUPPRESSION_ARRAYS = (
    "applied_suppressors", "blocked_suppressors", "applied_severity_caps",
    "blocked_severity_caps", "context_only_present", "severity_caps_applied",
)


def _validate_and_canonical_copy(result: Any) -> dict:
    """Schema-validate ONE WP4 result, reject pre-populated WP5 fields, then return a deterministic deep copy
    (every set-like array — flat, nested ``suppression``, and grouped ``live_positive_provenance`` — sorted +
    duplicate-free). Fails closed."""
    if not isinstance(result, Mapping):
        raise AggregationError(f"WP4 rule result must be a mapping, got {type(result).__name__}")
    plain = copy.deepcopy(dict(result))
    errs = sorted(_rule_result_validator().iter_errors(plain), key=lambda e: list(e.path))
    if errs:
        e = errs[0]
        raise AggregationError(
            f"rule {plain.get('rule_id')}: WP4 result fails rule-evaluation-result.schema.json: "
            f"{e.message} at /{'/'.join(map(str, e.path))}")
    leaked = sorted(_WP5_OWNED_FIELDS & set(plain))
    if leaked:
        raise AggregationError(f"rule {plain.get('rule_id')}: WP4 result contains pre-populated WP5 fields {leaked}")

    for f in _SET_LIKE_RESULT_ARRAYS:
        v = plain.get(f)
        if isinstance(v, list) and all(isinstance(x, str) for x in v):
            plain[f] = _sorted_unique(v)
    supp = plain.get("suppression")
    if isinstance(supp, dict):
        for f in _SET_LIKE_SUPPRESSION_ARRAYS:
            v = supp.get(f)
            if isinstance(v, list) and all(isinstance(x, str) for x in v):
                supp[f] = (sorted(set(v), key=SEVERITY_ORDER.index) if f == "severity_caps_applied"
                           else _sorted_unique(v))
    prov = plain.get("live_positive_provenance")
    if isinstance(prov, dict):
        canon: dict[str, list] = {}
        for key in sorted(prov):
            groups = prov[key]
            if isinstance(groups, list):
                norm = sorted({tuple(sorted(set(g))) for g in groups if isinstance(g, list)})
                canon[key] = [list(g) for g in norm]
        plain["live_positive_provenance"] = canon
    return plain


def _check_semantic_invariants(r: Mapping[str, Any], rk) -> None:
    """The full WP5 semantic-invariant matrix (not expressible in JSON Schema). Fails closed on any
    impossible combination, and resolves every governed reference WP5 relies on."""
    rid = r.get("rule_id")
    state = r.get("evaluation_state")
    req = r.get("required_combination_result")

    allowed = _REQUIRED_FOR_STATE.get(state)
    if allowed is None:
        raise AggregationError(f"rule {rid}: unknown evaluation_state {state!r}")
    if req not in allowed:
        raise AggregationError(f"rule {rid}: state {state} with required_combination_result {req!r} (allowed {allowed})")

    has_err = "evaluation_error" in r
    if state == "NOT_APPLICABLE":
        err = r.get("evaluation_error")
        if not isinstance(err, Mapping) or not err.get("code") or not isinstance(err.get("message"), str):
            raise AggregationError(f"rule {rid}: NOT_APPLICABLE needs a well-formed evaluation_error, got {err!r}")
    elif has_err:
        raise AggregationError(f"rule {rid}: evaluation_error present on a normal {state} result")

    if _is_composite(r) and state != "NOT_APPLICABLE":
        if r.get("rule_evidence_verdict") not in _VALID_VERDICTS:
            raise AggregationError(f"rule {rid}: COMPOSITE result has missing/invalid rule_evidence_verdict "
                                   f"{r.get('rule_evidence_verdict')!r}")
    if _is_composite(r) and state == "MATCHED" and r.get("effective_severity") not in SEVERITY_ORDER:
        raise AggregationError(f"rule {rid}: MATCHED composite has invalid effective_severity {r.get('effective_severity')!r}")

    # resolve every governed reference WP5 relies on
    for iid in r.get("matched_positive_indicators", ()):
        if rk.indicator(iid) is None:
            raise AggregationError(f"rule {rid}: matched positive indicator {iid!r} does not resolve")
    for iid in r.get("neutralised_indicators", ()):
        if rk.indicator(iid) is None:
            raise AggregationError(f"rule {rid}: neutralised indicator {iid!r} does not resolve")
    for nid in r.get("matched_negative_indicators", ()):
        if rk.negative_indicator(nid) is None:
            raise AggregationError(f"rule {rid}: matched negative indicator {nid!r} does not resolve")
    for oid in r.get("active_overrides", ()):
        if rk.override(oid) is None:
            raise AggregationError(f"rule {rid}: active override {oid!r} does not resolve")

    prov = r.get("live_positive_provenance") or {}
    matched_pos = set(r.get("matched_positive_indicators", ()))
    for key in prov:
        if key not in matched_pos:
            raise AggregationError(f"rule {rid}: live_positive_provenance key {key!r} not in matched_positive_indicators")


# ================================================================ public API


def aggregate_decision(
    rule_results: Iterable[Mapping[str, Any]],
    *,
    input_support_status: str,
    rk,
    profile: EvaluationProfile | None = None,
    language: str = "en",
    script: str = "Latn",
    whole_evaluation_errors: Iterable[Mapping[str, Any]] = (),
) -> DecisionResult:
    """Fold WP4 per-rule results into one deterministic ``DecisionResult`` (pure over
    *(rule_results, RuntimeKnowledge, evaluation_profile, input_support_status)*). Evidence independence is
    proven only from the WP3-emitted ``live_positive_provenance`` on each result."""
    profile = profile or DEFAULT_PROFILE
    if input_support_status not in _SUPPORT_STATES:
        raise AggregationError(f"unknown input_support_status {input_support_status!r}")

    # ---- validate whole-evaluation errors inside the typed boundary ----
    whole_errors: list[dict] = []
    try:
        for e in whole_evaluation_errors:
            if not isinstance(e, Mapping):
                raise AggregationError(f"whole_evaluation_errors entry must be a mapping, got {type(e).__name__}")
            plain = dict(e)
            verrs = sorted(_whole_error_validator().iter_errors(plain), key=lambda x: list(x.path))
            if verrs:
                raise AggregationError(f"malformed whole_evaluation_errors entry: {verrs[0].message}")
            whole_errors.append(plain)
    except AggregationError:
        raise
    except _AGG_FAULTS as e:
        raise AggregationError(f"malformed whole_evaluation_errors: {type(e).__name__}: {e}") from e

    # ---- validate + canonicalise each rule result, then enforce semantic invariants ----
    try:
        materialised = [_validate_and_canonical_copy(r) for r in rule_results]
        for r in materialised:
            _check_semantic_invariants(r, rk)
    except AggregationError:
        raise
    except _AGG_FAULTS as e:
        raise AggregationError(f"malformed WP4 rule-result input: {type(e).__name__}: {e}") from e

    seen: set[str] = set()
    for r in materialised:
        rid = r.get("rule_id")
        if not isinstance(rid, str):
            raise AggregationError(f"WP4 rule-result missing a string rule_id: {r!r}")
        if rid in seen:
            raise AggregationError(f"duplicate rule_id {rid!r} in the WP4 result set (invalid upstream corruption)")
        seen.add(rid)

    prof_ids = {
        "profile_id": getattr(profile, "profile_id", "profile-v1"),
        "extraction_confidence_gate": profile.extraction_confidence_gate,
        "risk_matrix_id": profile.risk_matrix_id,
        "confidence_policy_id": profile.confidence_policy_id,
    }

    degraded = any(r.get("evaluation_state") == "NOT_APPLICABLE" and r.get("evaluation_error") for r in materialised)
    errors = list(whole_errors)
    for r in materialised:
        if r.get("evaluation_state") == "NOT_APPLICABLE" and r.get("evaluation_error"):
            err = r["evaluation_error"]
            errors.append({"scope": "SINGLE_RULE", "stage": "RULE_EVALUATION",
                           "code": err.get("code", "RULE_EVALUATION_ERROR"),
                           "message": err.get("message", ""), "rule_id": r.get("rule_id")})
    whole_error = bool(whole_errors)

    if whole_error or input_support_status not in _EVALUABLE_SUPPORT:
        classification = _classify(input_support_status, [], materialised, "NOT_APPLICABLE", degraded, whole_error)
        return _assemble(
            input_support_status, classification, "NONE", "NONE", "NONE", "NOT_APPLICABLE",
            {"independent_evidence_classes": [], "evidence_class_count": 0, "band": "NONE"},
            None, None, [], materialised, degraded, errors, prof_ids,
        )

    eligible = [r for r in materialised if _is_eligible_matched(r)]

    if not eligible:
        classification = _classify(input_support_status, [], materialised, "NOT_APPLICABLE", degraded, whole_error)
        corroboration = _corroboration_no_fire(materialised, classification)
        return _assemble(
            input_support_status, classification, "NONE", "NONE", "NONE", "NOT_APPLICABLE",
            corroboration, None, None, [], materialised, degraded, errors, prof_ids,
        )

    for r in eligible:
        r["rule_evidence_strength"] = _rule_evidence_strength(r, rk)

    governing = _select_governing(eligible)
    governing_id = governing["rule_id"]
    governing_verdict = governing.get("rule_evidence_verdict")

    decision_severity = max((r["effective_severity"] for r in eligible), key=SEVERITY_ORDER.index)
    matched_evidence_strength = governing["rule_evidence_strength"]

    proven_count, proven_classes, shared_refs = _proven_independence(eligible, rk)
    corroboration = _corroboration(proven_count, proven_classes, shared_refs, governing_verdict)
    detection_confidence = _detection_confidence(governing, proven_count, profile)
    if degraded and CONFIDENCE_ORDER.index(detection_confidence) > CONFIDENCE_ORDER.index("MEDIUM"):
        detection_confidence = "MEDIUM"                       # degraded caps confidence at MEDIUM (Decision 2)

    risk_level = _risk_level(decision_severity, matched_evidence_strength)
    classification = _classify(input_support_status, eligible, materialised, detection_confidence, degraded, whole_error)

    reason = _governing_reason(governing, len(eligible))
    for r in materialised:
        if r["rule_id"] == governing_id and _is_eligible_matched(r):
            r["governing"] = True
            r["governing_reason"] = reason
    governing["rule_detection_confidence"] = detection_confidence

    return _assemble(
        input_support_status, classification, decision_severity, matched_evidence_strength, risk_level,
        detection_confidence, corroboration, governing_id, reason, eligible, materialised, degraded, errors,
        prof_ids,
    )


def _assemble(support, classification, severity, strength, risk, confidence, corroboration,
              governing_id, governing_reason, eligible, all_results, degraded, errors, prof_ids) -> DecisionResult:
    matched_rules = _sorted_unique(r["rule_id"] for r in eligible)
    matched_pos: set[str] = set()
    for r in eligible:
        matched_pos.update(r.get("matched_positive_indicators", ()))
    matched_neg: set[str] = set()
    suppressed: set[str] = set()
    overrides: set[str] = set()
    ambiguities: set[str] = set()
    unknowns: set[str] = set()
    for r in all_results:
        if not _is_composite(r):
            continue
        matched_neg.update(r.get("matched_negative_indicators", ()))
        suppressed.update(r.get("neutralised_indicators", ()))
        overrides.update(r.get("active_overrides", ()))
        ambiguities.update(r.get("ambiguities", ()))
        unknowns.update(r.get("unknowns", ()))

    errors_sorted = sorted(
        errors, key=lambda e: (e.get("scope", ""), e.get("stage", ""), e.get("code", ""),
                               e.get("rule_id", "") or "", e.get("message", "")))

    return DecisionResult(
        input_support_status=support,
        classification=classification,
        decision_severity=severity,
        matched_evidence_strength=strength,
        risk_level=risk,
        detection_confidence=confidence,
        corroboration=corroboration,
        governing_rule_id=governing_id,
        governing_reason=governing_reason,
        matched_rules=tuple(matched_rules),
        matched_positive_indicators=tuple(_sorted_unique(matched_pos)),
        matched_negative_indicators=tuple(_sorted_unique(matched_neg)),
        suppressed_indicators=tuple(_sorted_unique(suppressed)),
        active_overrides=tuple(_sorted_unique(overrides)),
        ambiguities=tuple(sorted(ambiguities)),
        unknowns=tuple(sorted(unknowns)),
        degraded=degraded,
        errors=tuple(errors_sorted),
        rule_results=tuple(sorted(all_results, key=lambda r: r.get("rule_id", ""))),
        evaluation_profile=prof_ids,
    )


# ---- module-level convenience wrapper (production = governed DATA in, WP3 -> WP4 -> WP5) ----

def evaluate_decision_from_governed(
    rk,
    indicator_observations: Iterable[Mapping[str, Any]],
    observations: Iterable[Mapping[str, Any]],
    *,
    input_support_status: str = "SUPPORTED",
    profile: EvaluationProfile | None = None,
    language: str = "en",
    script: str = "Latn",
    whole_evaluation_errors: Iterable[Mapping[str, Any]] = (),
) -> DecisionResult:
    """Production convenience: run WP3 over all PUBLISHED rules, apply WP4 suppression/caps, then aggregate to
    one decision. The proven-independence provenance rides on each rule result's WP3 ``live_positive_provenance``
    — WP5 builds no provenance of its own. ``input_support_status`` is decided upstream and passed in."""
    from .suppression import evaluate_rules_with_suppression_from_governed

    wp4 = evaluate_rules_with_suppression_from_governed(
        rk, indicator_observations, observations, profile=profile, language=language, script=script)
    return aggregate_decision(
        wp4, input_support_status=input_support_status, rk=rk, profile=profile,
        language=language, script=script, whole_evaluation_errors=whole_evaluation_errors)
