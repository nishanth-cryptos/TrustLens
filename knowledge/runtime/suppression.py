"""TrustLens Phase 3 P3-WP4 — rule-level suppression / severity orchestration executor.

Consumes a P3-WP3 ``RuleEvaluationResult`` (the per-rule dict produced by ``evaluator.py``) plus the
immutable ``RuntimeKnowledge`` and applies the governed POST-MATCH, rule-level effects that WP3
deliberately deferred (DET-001 §11 items 4–6, ADR-0005 §4):

  * ``SUPPRESS_RULE``  — cancel a MATCHED rule (→ ``SUPPRESSED``) unless blocked by an active hard-risk
    override;
  * ``CAP_SEVERITY``   — lower a MATCHED rule's ``effective_severity`` to the minimum surviving governed
    ceiling (never increases it);
  * ``CONTEXT_ONLY``   — record benign context; never changes state or severity.

WP4 is a *consumer* of WP3 truth, not a re-computation of it. It NEVER re-derives operand truth,
structural occurrence eligibility, hard-risk overrides, or re-executes ``SUPPRESS_INDICATOR`` (all owned
by WP3). It reads WP3's already-computed ``evaluation_state``, ``matched_negative_indicators``,
``active_overrides`` and ``effective_severity`` and resolves each governed effect against
``RuntimeKnowledge`` metadata (``suppression_effect`` / ``category`` / ``blockable_by_overrides`` /
``severity_cap``; override ``blocks_suppression_categories``).

Invariants (programme decision, 2026-08-31):
  * Only ``MATCHED`` (COMPOSITE) → ``SUPPRESSED`` is permitted. ``NOT_MATCHED`` / ``INDETERMINATE`` /
    ``NOT_APPLICABLE`` and ``SUPPRESSION``-kind results are structural and pass through untouched — a
    suppressor can never resurrect a structural FALSE nor manufacture a MATCH.
  * ``CAP_SEVERITY`` never *increases* severity; ``effective_severity = min(WP3 base, surviving ceilings)``
    over the ONE canonical ordering imported from ``evaluator.py``. If every cap is blocked, the WP3 base
    severity is retained.
  * Override authority is governed: an effect is blocked ONLY if ``blockable_by_overrides`` is true AND its
    category is explicitly listed by an active override. The mere presence of an override is never enough.
  * Fail-closed: a malformed / impossible governed effect degrades THAT rule to ``NOT_APPLICABLE`` +
    ``evaluation_error{SUPPRESSION_EXECUTION_ERROR}`` — never a silent ``MATCHED``/``SUPPRESSED``. One bad
    effect degrades one rule; the batch continues.

WP4 emits NO WP5 / decision-level field (classification, risk, decision severity, matched-evidence
strength, detection confidence, corroboration, governing, rule_evidence_strength,
rule_detection_confidence). It produces per-rule results only.
"""

from __future__ import annotations

import copy
from typing import Any, Iterable, Mapping

from .evaluator import DEFAULT_PROFILE, SEVERITY_ORDER, EvaluationProfile, RuleEvaluator
from .runtime_knowledge import RuntimeKnowledge

# Effects WP4 OWNS at the rule level. SUPPRESS_INDICATOR is executed pre-match by WP3 and is recognised
# here as ALREADY_RESOLVED (ignored for state/severity) — never treated as an unknown effect.
_ALREADY_RESOLVED_EFFECT = "SUPPRESS_INDICATOR"
_KNOWN_EFFECTS = frozenset({"SUPPRESS_RULE", "CAP_SEVERITY", "CONTEXT_ONLY", _ALREADY_RESOLVED_EFFECT})

# Set-valued arrays in the public per-rule contract. WP3 already emits these canonically, but the public
# ``apply`` boundary also accepts a schema-shaped WP3 result directly, so it normalises a permuted/duplicated
# caller representation without mutating it. This makes the whole WP4 result canonical, not only its
# ``suppression`` sub-object.
_SET_LIKE_RESULT_ARRAYS = (
    "matched_positive_indicators",
    "matched_negative_indicators",
    "active_overrides",
    "neutralised_indicators",
    "evidence_classes_spanned",
    "observation_refs",
    "indicator_observation_refs",
    "ambiguities",
    "unknowns",
    "evidence_ids",
)
_SUPPRESSION_ID_ARRAYS = (
    "applied_suppressors",
    "applied_severity_caps",
    "blocked_severity_caps",
    "blocked_suppressors",
    "context_only_present",
)
_WP5_OWNED_FIELDS = frozenset({
    "governing",
    "governing_reason",
    "classification",
    "risk_level",
    "decision_severity",
    "matched_evidence_strength",
    "detection_confidence",
    "corroboration",
    "rule_evidence_strength",
    "rule_detection_confidence",
})

# Narrow per-rule data faults degraded to NOT_APPLICABLE (mirrors evaluator._PER_RULE_FAULTS). A WP2
# load-time integrity fault is NOT in this set and is never manufactured here (RuntimeKnowledge is
# already validated); these guard against malformed/for-drift governed suppression metadata.
_PER_RULE_FAULTS = (KeyError, ValueError, TypeError, IndexError)


class SuppressionExecutionError(Exception):
    """A malformed / impossible governed suppression effect: an unresolved matched-negative id, an unknown
    ``suppression_effect``, a ``CAP_SEVERITY`` without a valid ``severity_cap``, an unresolved
    ``active_override`` id, or a WP3-vs-WP4 blocked-set disagreement. Caught by the per-rule isolation
    wrapper and surfaced as ``NOT_APPLICABLE`` + ``evaluation_error{SUPPRESSION_EXECUTION_ERROR}``. Fail
    closed — never a silent MATCHED/SUPPRESSED."""


def _sev_min(a: str | None, b: str | None) -> str | None:
    """Ordinal minimum over the ONE canonical severity ordering (imported, never re-declared). ``None`` is
    the identity so a missing base/ceiling is skipped rather than guessed."""
    if a is None:
        return b
    if b is None:
        return a
    return a if SEVERITY_ORDER.index(a) <= SEVERITY_ORDER.index(b) else b


def _sorted_unique(ids: Iterable[str]) -> list[str]:
    return sorted(set(ids))


class RuleSuppressionExecutor:
    """Stateless-over-inputs executor bound to one immutable ``RuntimeKnowledge``. Pure over
    *(wp3_result, RuntimeKnowledge)* — no clock, no network, no LLM, no mutation of the inputs."""

    def __init__(self, rk: RuntimeKnowledge) -> None:
        self.rk = rk

    # ================================================================ public API

    def apply(self, result: Mapping[str, Any]) -> dict:
        """Apply WP4 rule-level suppression/caps to ONE WP3 per-rule result and return a NEW result dict.
        Per-rule fail-closed: a malformed governed effect degrades that rule to
        ``NOT_APPLICABLE{SUPPRESSION_EXECUTION_ERROR}`` (never a silent MATCHED/SUPPRESSED)."""
        rid, rver, kind = "TL-XXX-000", "0.0.0", "COMPOSITE"
        try:
            if not isinstance(result, Mapping):
                raise SuppressionExecutionError(
                    f"WP4 input must be a WP3 result mapping, got {type(result).__name__}")
            rid = result.get("rule_id", rid)
            rver = result.get("rule_version", rver)
            kind = result.get("kind", kind)
            return self._apply(result)
        except (SuppressionExecutionError, *_PER_RULE_FAULTS) as e:
            message = str(e) if isinstance(e, SuppressionExecutionError) else f"{type(e).__name__}: {e}"
            required = result.get("required_combination_result", "UNKNOWN") if isinstance(result, Mapping) else "UNKNOWN"
            return {
                "rule_id": rid,
                "rule_version": rver,
                "kind": kind if kind in ("COMPOSITE", "SUPPRESSION") else "COMPOSITE",
                "evaluation_state": "NOT_APPLICABLE",
                # preserve the WP3 combination truth for later degraded routing; do NOT invent one
                "required_combination_result": required if required in ("TRUE", "FALSE", "UNKNOWN") else "UNKNOWN",
                "evaluation_error": {"code": "SUPPRESSION_EXECUTION_ERROR", "message": message},
            }

    def apply_all(self, results: Iterable[Mapping[str, Any]]) -> tuple[dict, ...]:
        """Apply WP4 to a batch of WP3 results, isolating each rule (one malformed effect never poisons the
        batch). Order is preserved (WP3 already emits lexical rule-id order)."""
        return tuple(self.apply(r) for r in results)

    # ================================================================ core (over a single WP3 result)

    def _apply(self, result: Mapping[str, Any]) -> dict:
        out = copy.deepcopy(dict(result))
        self._canonicalize_result(out)

        # WP5-owned data cannot cross any public WP4 entry point, even on a structural/non-MATCHED result.
        # Silently stripping it would conceal a stage-boundary violation; degrade this member explicitly.
        leaked_wp5 = sorted(_WP5_OWNED_FIELDS & set(out))
        if leaked_wp5:
            raise SuppressionExecutionError(
                f"rule {out.get('rule_id')}: WP3 result contains pre-populated WP5 fields {leaked_wp5}")

        state = out.get("evaluation_state")
        kind = out.get("kind")

        # WP4 acts ONLY on a MATCHED COMPOSITE rule. Structural states are non-overridable and a
        # SUPPRESSION-kind rule is infrastructure that never becomes SUPPRESSED — pass through unchanged.
        if kind != "COMPOSITE" or state != "MATCHED":
            return out

        self._validate_matched_input(out)

        matched_negative = out.get("matched_negative_indicators", [])
        active_overrides = out.get("active_overrides", [])
        if not isinstance(matched_negative, list) or not all(isinstance(nid, str) for nid in matched_negative):
            raise SuppressionExecutionError(
                f"rule {out.get('rule_id')}: matched_negative_indicators must be an array of ids")
        if not isinstance(active_overrides, list) or not all(isinstance(oid, str) for oid in active_overrides):
            raise SuppressionExecutionError(
                f"rule {out.get('rule_id')}: active_overrides must be an array of ids")
        blocked_categories = self._blocked_categories(active_overrides)

        applied_suppressors: list[str] = []
        blocked_suppressors: list[str] = []
        applied_caps: list[str] = []
        blocked_caps: list[str] = []
        context_only: list[str] = []
        surviving_ceilings: list[str] = []

        for nid in matched_negative:
            neg = self.rk.negative_indicator(nid)
            if neg is None:
                # An impossible governed reference: a TRUE matched negative that WP3 read from the SAME
                # RuntimeKnowledge must resolve. Fail closed rather than emit a clean MATCHED.
                raise SuppressionExecutionError(
                    f"rule {out.get('rule_id')}: matched negative {nid!r} does not resolve in RuntimeKnowledge")
            if not isinstance(neg, Mapping):
                raise SuppressionExecutionError(
                    f"rule {out.get('rule_id')}: matched negative {nid!r} has malformed governed metadata")
            effect = neg.get("suppression_effect")
            if effect not in _KNOWN_EFFECTS:
                raise SuppressionExecutionError(
                    f"rule {out.get('rule_id')}: negative {nid!r} has unknown suppression_effect {effect!r}")
            if not isinstance(neg.get("blockable_by_overrides"), bool):
                raise SuppressionExecutionError(
                    f"rule {out.get('rule_id')}: negative {nid!r} has invalid blockable_by_overrides")
            if not isinstance(neg.get("category"), str) or not neg.get("category"):
                raise SuppressionExecutionError(
                    f"rule {out.get('rule_id')}: negative {nid!r} has invalid suppression category")
            if effect == _ALREADY_RESOLVED_EFFECT:
                continue  # WP3 executed it pre-match at occurrence scope; recognised, not re-applied

            blocked = self._is_blocked(neg, blocked_categories)
            if effect == "SUPPRESS_RULE":
                (blocked_suppressors if blocked else applied_suppressors).append(nid)
            elif effect == "CAP_SEVERITY":
                ceiling = neg.get("severity_cap")
                if ceiling not in ("LOW", "MEDIUM", "HIGH"):
                    raise SuppressionExecutionError(
                        f"rule {out.get('rule_id')}: CAP_SEVERITY {nid!r} has invalid severity_cap {ceiling!r}")
                if blocked:
                    blocked_caps.append(nid)
                else:
                    applied_caps.append(nid)
                    surviving_ceilings.append(ceiling)
            elif effect == "CONTEXT_ONLY":
                context_only.append(nid)

        # Governed resolution must agree with WP3's informational blocked_suppressors when WP3 provided it
        # (both are computed over the same governed knowledge in production). Fail closed on divergence.
        self._cross_check_blocked(out, blocked_suppressors, blocked_caps)

        # ---- CAP_SEVERITY: effective_severity = min(WP3 base, surviving ceilings); never increases ----
        base = out.get("effective_severity")
        effective = base
        for ceiling in surviving_ceilings:
            effective = _sev_min(effective, ceiling)
        if effective is not None:
            out["effective_severity"] = effective

        # ---- SUPPRESS_RULE: ONLY MATCHED -> SUPPRESSED. required_combination_result stays TRUE ----
        if applied_suppressors:
            out["evaluation_state"] = "SUPPRESSED"

        self._attach_suppression(out, applied_suppressors, blocked_suppressors,
                                 applied_caps, blocked_caps, surviving_ceilings, context_only)
        return out

    # ================================================================ helpers

    @staticmethod
    def _canonicalize_result(result: dict[str, Any]) -> None:
        """Canonicalise set-like public result arrays in-place on the private deep copy only."""
        for field in _SET_LIKE_RESULT_ARRAYS:
            value = result.get(field)
            if isinstance(value, list) and all(isinstance(item, str) for item in value):
                result[field] = _sorted_unique(value)

        suppression = result.get("suppression")
        if not isinstance(suppression, dict):
            return
        for field in _SUPPRESSION_ID_ARRAYS:
            value = suppression.get(field)
            if isinstance(value, list) and all(isinstance(item, str) for item in value):
                suppression[field] = _sorted_unique(value)
        ceilings = suppression.get("severity_caps_applied")
        if isinstance(ceilings, list) and all(item in ("LOW", "MEDIUM", "HIGH") for item in ceilings):
            suppression["severity_caps_applied"] = sorted(set(ceilings), key=SEVERITY_ORDER.index)

    @staticmethod
    def _validate_matched_input(result: Mapping[str, Any]) -> None:
        """Validate the WP3→WP4 boundary fields that are authoritative for a MATCHED composite.

        WP3 always supplies TRUE combination truth and a canonical base effective severity. Applied WP4
        metadata cannot already be present on a WP3 result; accepting it would let stale/caller-authored
        suppression survive as a normal result instead of failing closed.
        """
        rid = result.get("rule_id")
        if result.get("required_combination_result") != "TRUE":
            raise SuppressionExecutionError(
                f"rule {rid}: MATCHED WP3 result must have required_combination_result='TRUE'")
        if result.get("effective_severity") not in SEVERITY_ORDER:
            raise SuppressionExecutionError(
                f"rule {rid}: MATCHED WP3 result has invalid/missing base effective_severity "
                f"{result.get('effective_severity')!r}")
        supp = result.get("suppression")
        if supp is not None and not isinstance(supp, Mapping):
            raise SuppressionExecutionError(f"rule {rid}: suppression metadata must be an object")
        if supp:
            wp4_owned = {
                "suppressed_by", "effect", "applied_suppressors", "severity_caps_applied",
                "applied_severity_caps", "blocked_severity_caps",
            }
            unexpected = sorted(wp4_owned & set(supp))
            if unexpected:
                raise SuppressionExecutionError(
                    f"rule {rid}: WP3 result contains pre-applied WP4 metadata {unexpected}")

    def _blocked_categories(self, active_overrides: Iterable[str]) -> frozenset[str]:
        """Governed blocked-suppression categories from the ACTIVE overrides (WP3-computed ids resolved
        through RuntimeKnowledge). An unresolved override id fails closed."""
        cats: set[str] = set()
        for oid in active_overrides:
            ov = self.rk.override(oid)
            if ov is None:
                raise SuppressionExecutionError(
                    f"active override {oid!r} does not resolve in RuntimeKnowledge")
            if not isinstance(ov, Mapping):
                raise SuppressionExecutionError(
                    f"active override {oid!r} has malformed governed metadata")
            blocked = ov.get("blocks_suppression_categories")
            if not isinstance(blocked, (list, tuple)) or not all(
                    isinstance(category, str) and category for category in blocked):
                raise SuppressionExecutionError(
                    f"active override {oid!r} has invalid blocks_suppression_categories")
            cats.update(blocked)
        return frozenset(cats)

    @staticmethod
    def _is_blocked(neg: Mapping[str, Any], blocked_categories: frozenset[str]) -> bool:
        """An effect is blocked ONLY when it is EXPLICITLY override-blockable AND its category is one an
        active override blocks. Presence of an override alone is never sufficient (programme directive §5)."""
        return bool(neg.get("blockable_by_overrides")) and neg.get("category") in blocked_categories

    def _cross_check_blocked(self, result: Mapping[str, Any],
                             blocked_suppressors: list[str], blocked_caps: list[str]) -> None:
        """WP4's governed blocked-soft set must equal WP3's informational ``suppression.blocked_suppressors``
        when WP3 emitted it. WP3 exposes blocked SOFT suppressors (SUPPRESS_RULE ∪ CAP_SEVERITY); WP4 splits
        them into ``blocked_suppressors`` (SUPPRESS_RULE) and ``blocked_severity_caps`` (CAP_SEVERITY), so
        their union must match. A divergence is fail-closed, never silently reconciled (directive §5)."""
        suppression = result.get("suppression")
        if suppression is None:
            return
        if not isinstance(suppression, Mapping):
            raise SuppressionExecutionError(
                f"rule {result.get('rule_id')}: suppression metadata must be an object")
        wp3_blocked = suppression.get("blocked_suppressors")
        if wp3_blocked is None:
            return
        if not isinstance(wp3_blocked, list) or not all(isinstance(nid, str) for nid in wp3_blocked):
            raise SuppressionExecutionError(
                f"rule {result.get('rule_id')}: WP3 blocked_suppressors must be an array of ids")
        governed = set(blocked_suppressors) | set(blocked_caps)
        if set(wp3_blocked) != governed:
            raise SuppressionExecutionError(
                f"rule {result.get('rule_id')}: WP3 informational blocked_suppressors "
                f"{sorted(wp3_blocked)} disagree with WP4 governed resolution {sorted(governed)}")

    @staticmethod
    def _attach_suppression(out: dict, applied_suppressors: list[str], blocked_suppressors: list[str],
                            applied_caps: list[str], blocked_caps: list[str],
                            surviving_ceilings: list[str], context_only: list[str]) -> None:
        """Assemble the deterministic ``suppression`` sub-object (all id arrays sorted + duplicate-free)."""
        # WP3's suppression object is informational only (blocked/context candidates). Rebuild the WP4-owned
        # object from governed resolution so no stale applied/blocked/context field can survive accidentally.
        supp: dict[str, Any] = {}

        applied_suppressors = _sorted_unique(applied_suppressors)
        blocked_suppressors = _sorted_unique(blocked_suppressors)
        applied_caps = _sorted_unique(applied_caps)
        blocked_caps = _sorted_unique(blocked_caps)
        context_only = _sorted_unique(context_only)
        # ceilings recorded as ordinal levels (schema enum LOW/MEDIUM/HIGH), deduped, ordinal-sorted
        ceilings = sorted({c for c in surviving_ceilings if c in ("LOW", "MEDIUM", "HIGH")},
                          key=SEVERITY_ORDER.index)

        if applied_suppressors:
            supp["applied_suppressors"] = applied_suppressors
            supp["suppressed_by"] = applied_suppressors[0]   # lexical first — NOT arrival/eval order
        if blocked_suppressors:
            supp["blocked_suppressors"] = blocked_suppressors
        if applied_caps:
            supp["applied_severity_caps"] = applied_caps
            if ceilings:
                supp["severity_caps_applied"] = ceilings
        if blocked_caps:
            supp["blocked_severity_caps"] = blocked_caps
        if context_only:
            supp["context_only_present"] = context_only

        # primary effect (precedence SUPPRESS_RULE > CAP_SEVERITY > CONTEXT_ONLY > NONE)
        if applied_suppressors:
            supp["effect"] = "SUPPRESS_RULE"
        elif applied_caps:
            supp["effect"] = "CAP_SEVERITY"
        elif context_only:
            supp["effect"] = "CONTEXT_ONLY"
        else:
            supp["effect"] = "NONE"

        if supp:
            out["suppression"] = supp


# ---- module-level convenience wrappers (production = governed DATA in, WP3 then WP4) ----

def apply_rule_suppression(rk: RuntimeKnowledge, result: Mapping[str, Any]) -> dict:
    """Apply WP4 rule-level suppression/caps to one WP3 per-rule result."""
    return RuleSuppressionExecutor(rk).apply(result)


def evaluate_rules_with_suppression_from_governed(
        rk: RuntimeKnowledge,
        indicator_observations: Iterable[Mapping[str, Any]],
        observations: Iterable[Mapping[str, Any]],
        *, profile: EvaluationProfile | None = None,
        language: str = "en", script: str = "Latn") -> tuple[dict, ...]:
    """Production convenience: run WP3 over ALL PUBLISHED rules, then apply WP4 suppression/caps per rule."""
    ev = RuleEvaluator(rk, profile or DEFAULT_PROFILE)
    wp3 = ev.evaluate_rules_from_governed(indicator_observations, observations,
                                          language=language, script=script)
    return RuleSuppressionExecutor(rk).apply_all(wp3)


def evaluate_rule_with_suppression_from_governed(
        rk: RuntimeKnowledge, rule_id: str,
        indicator_observations: Iterable[Mapping[str, Any]],
        observations: Iterable[Mapping[str, Any]],
        *, profile: EvaluationProfile | None = None,
        language: str = "en", script: str = "Latn") -> dict:
    """Production convenience: run WP3 for ONE PUBLISHED rule by id, then apply WP4 suppression/caps."""
    ev = RuleEvaluator(rk, profile or DEFAULT_PROFILE)
    wp3 = ev.evaluate_rule_from_governed(rule_id, indicator_observations, observations,
                                         language=language, script=script)
    return RuleSuppressionExecutor(rk).apply(wp3)
