"""TrustLens Phase 3 P3-WP6 — deterministic structured explanation + governed recommended actions.

Consumes the authoritative P3-WP5 ``DecisionResult`` plus the immutable ``RuntimeKnowledge`` and produces an
``ExplanationResult`` that EXPLAINS the decision — it never reconsiders it. WP6 does not change
input_support_status, classification, governing rule, decision severity, matched-evidence strength, risk,
detection confidence, corroboration, rule state, suppression, or override activation. Corroboration remains a
WP5-owned axis and is deliberately not used in WP6 prose: validating it would require forbidden re-aggregation.

TRUST BOUNDARY (independent-review H3). ``build_explanation`` is the PUBLIC, live production surface. A
``DecisionResult`` is a plain dataclass a caller can hand-construct, so being an instance is NOT proof of
trustworthiness. Before rendering ANYTHING, ``_validate_explanation_input`` re-validates the supplied decision
against authoritative ``RuntimeKnowledge`` and the WP5 invariants in ONE place: every ``rule_results`` entry is
re-checked against the promoted ``rule-evaluation-result`` schema and the WP5 semantic-invariant matrix (reusing
the WP5 validators — no divergent semantics), classification is cross-checked against the decision axes,
governing/contributing rules must resolve (and, on the live path, be PUBLISHED), active overrides must resolve
and be backed by a rule result, and echoed ``source_references`` must match the governed rule's authoritative
evidence. Any impossible/forged decision raises ``ExplanationError`` — WP6 never repairs it and never emits a
reassuring explanation for it.

  * ``explanation`` — deterministic templates over governed facts. NO LLM, no generative wording. Official
    factual claims appear ONLY in ``evidence_basis`` as the EXACT stored ``source_references`` quotes taken
    from the GOVERNED rule (never the caller's echo); ``rule.explanation.plain``/``technical`` are never
    re-asserted as official facts. ``supporting_observations`` carry an ``observation_ref`` (+ an optional
    ``span`` from governed offsets) — never a ``redacted_quote`` (no governed redactor exists; ``raw_span`` is
    never copied into result prose).
  * ``recommended_actions`` — resolved ONLY from the governed ``action-policy`` artifact in RuntimeKnowledge
    (never from a rule name or verification-step prose). Action codes are drawn from the promoted vocabulary;
    system-state actions carry no fabricated reason ids (traced by input_support_status/classification + the
    governed policy entry + the pinned action_policy version + bundle_content_digest). No ``priority``.

Design-preview: on-promotion golden cases (``live_publishable:false``, e.g. a governing rule not yet PUBLISHED)
are NOT live-executable. The private ``_build_explanation(..., live=False)`` renders the DESIGNED behaviour for
the golden specification/tests; it is deliberately not exported and there is NO ``allow_unpublished`` production
escape hatch and NO case-id bypass — the public API stays PUBLISHED-only.

Determinism: pure over *(DecisionResult, RuntimeKnowledge, observations)*; inputs never mutated; every list
canonicalised; actions emitted in a fixed action-code order; ``evidence_basis`` totally ordered by full
canonical identity. Fail-closed: required-provenance corruption raises ``ExplanationError``; optional
presentation data (a missing observation offset) is omitted, not fatal.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .aggregation import (
    AggregationError,
    DecisionResult,
    _check_semantic_invariants,
    _is_composite,
    _is_eligible_matched,
    _rule_result_validator,
    _whole_error_validator,
)

# Fixed deterministic emission order (the promoted detection-result action vocabulary order).
_ACTION_ORDER = (
    "DO_NOT_SHARE_CREDENTIALS", "DO_NOT_ENTER_PIN", "DO_NOT_TRANSFER_MONEY", "DO_NOT_INSTALL_APP",
    "DO_NOT_CONNECT_WALLET", "DO_NOT_DIAL_CODE", "DISCONNECT_REMOTE_ACCESS", "VERIFY_INDEPENDENTLY",
    "CONTACT_BANK", "CONTACT_OFFICIAL_CHANNEL", "REPORT_CYBERCRIME", "PRESERVE_EVIDENCE",
    "PROCEED_WITH_CAUTION", "SEEK_HUMAN_REVIEW", "RESUBMIT_IN_SUPPORTED_LANGUAGE",
)
_SCAM_CLASSES = ("SCAM_PATTERN_DETECTED", "SCAM_PATTERN_SUSPECTED")
_EXPL_FAULTS = (KeyError, ValueError, TypeError, IndexError, AttributeError)

# Valid axis vocabularies (mirror detection-result.schema.json). Used by the cross-field validator.
_SUPPORT_VALUES = frozenset({"SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "INSUFFICIENT_INFORMATION", "ERROR"})
_EVALUABLE_SUPPORT = frozenset({"SUPPORTED", "PARTIALLY_SUPPORTED"})
_CLASS_VALUES = frozenset({"NO_SCAM_PATTERN", "INSUFFICIENT_EVIDENCE", "SCAM_PATTERN_SUSPECTED",
                           "SCAM_PATTERN_DETECTED", "UNSUPPORTED", "ERROR"})
_SEVERITY_VALUES = frozenset({"NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"})
_STRENGTH_VALUES = frozenset({"NONE", "WEAK", "MODERATE", "STRONG"})
_RISK_VALUES = frozenset({"NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"})
_CONF_VALUES = frozenset({"NOT_APPLICABLE", "LOW", "MEDIUM", "HIGH"})

# The exact subset the runtime echoes from a governed source_reference (mirrors evaluator._attach_match_provenance).
_ECHO_KEYS = ("source_id", "issuing_body", "authority", "verification_status", "evidence_class", "quote")


class ExplanationError(Exception):
    """Fail-closed WP6 error: required explanation/action provenance is corrupt, impossible, or forged — an
    unresolved/unpublished governing or contributing rule, a scam decision with no governing rule, a
    classification inconsistent with the decision axes, a schema-/semantic-invalid rule result, an unresolved
    or unbacked override, a fabricated source reference, an action reason that cannot resolve, or
    ``ACTION_POLICY_UNAVAILABLE`` (the executed RuntimeKnowledge pins no governed action policy). WP6 never
    emits a generic reassuring explanation instead. ``.code`` is a stable, greppable token."""

    def __init__(self, message: str, *, code: str = "EXPLANATION_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass(frozen=True)
class ExplanationResult:
    """The two WP6-owned blocks + the pinned action-policy version that produced the actions. NOT a full
    detection-result: provenance/timestamps/envelope are WP7/WP8."""

    explanation: Mapping[str, Any]
    recommended_actions: tuple[Mapping[str, Any], ...]
    action_policy_version: str | None = None

    def as_dict(self) -> dict:
        out = {"explanation": dict(self.explanation),
               "recommended_actions": [dict(a) for a in self.recommended_actions]}
        if self.action_policy_version is not None:
            out["action_policy_version"] = self.action_policy_version
        return out


# ================================================================ small helpers

def _canon(item: Mapping[str, Any]) -> str:
    return json.dumps(item, sort_keys=True, separators=(",", ":"))


def _taxonomy_parent_map(rk) -> dict[str, str]:
    """Governed subcategory → parent-category map from RuntimeKnowledge (a category node carries its
    `subcategories`). Ancestry is resolved from the governed structure, never by lexical prefix guessing."""
    parent: dict[str, str] = {}
    for node in rk.index("taxonomy_by_id").values():
        subs = node.get("subcategories")
        if subs:
            cat_id = node.get("id")
            for sub in subs:
                sid = sub.get("id")
                if isinstance(sid, str) and isinstance(cat_id, str):
                    parent[sid] = cat_id
    return parent


def _rule_taxonomy_ids(rule: Mapping[str, Any] | None, parent: Mapping[str, str]) -> set[str]:
    """A rule's trigger-matchable taxonomy ids: its own `taxonomy_refs` plus their GOVERNED parent
    categories (from `parent`) — an unrelated `TAX-*` prefix can never match."""
    refs = set(rule.get("taxonomy_refs", ())) if rule else set()
    return refs | {parent[r] for r in refs if r in parent}


def _eligible_matched(r: Mapping[str, Any]) -> bool:
    return (r.get("kind") == "COMPOSITE" and r.get("evaluation_state") == "MATCHED"
            and r.get("required_combination_result") == "TRUE")


def _decisive_unresolved(r: Mapping[str, Any]) -> bool:
    return (r.get("kind") == "COMPOSITE" and r.get("evaluation_state") == "INDETERMINATE"
            and r.get("required_combination_result") == "UNKNOWN"
            and bool(r.get("ambiguities") or r.get("unknowns")))


def _authoritative_source_refs(rule: Mapping[str, Any] | None) -> list[dict]:
    """The AUTHORITATIVE runtime-facing source references of a GOVERNED rule, mapped byte-identically to
    ``evaluator._attach_match_provenance`` (§11). This — never the caller's echoed ``source_references`` — is
    the sole source of official facts the explanation may assert."""
    out: list[dict] = []
    for ref in (rule or {}).get("evidence", {}).get("source_references", ()):
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
        out.append({k: v for k, v in mapped.items() if v is not None})
    return out


def _contributing_rule_ids(decision) -> set[str]:
    """Rules that contribute a live scam finding/action: the eligible MATCHED set, the governing rule, and —
    only for INSUFFICIENT_EVIDENCE — the decision-relevant unresolved INDETERMINATE rules that can emit a
    verification action. On the live path every one of these must be PUBLISHED (§8)."""
    ids = set(decision.matched_rules)
    if decision.governing_rule_id is not None:
        ids.add(decision.governing_rule_id)
    if decision.classification == "INSUFFICIENT_EVIDENCE":
        ids |= {r["rule_id"] for r in decision.rule_results if _decisive_unresolved(r)}
    return ids


# ================================================================ trust boundary (independent-review H3)

def _fail(msg: str, code: str) -> None:
    raise ExplanationError(msg, code=code)


def _canonical_rollup(value: Any, field: str) -> tuple[str, ...]:
    """Canonical comparison form for a WP5 set-like DecisionResult rollup.

    WP5 emits duplicate-free tuples, while trust-boundary comparison deliberately ignores tuple order so an
    otherwise legitimate caller permutation cannot affect rendering. Duplicate/non-string members cannot have
    been emitted by WP5 and are rejected rather than silently repaired.
    """
    if not isinstance(value, tuple) or not all(isinstance(v, str) for v in value):
        _fail(f"{field} must be a tuple of strings", "INVALID_DECISION")
    if len(value) != len(set(value)):
        _fail(f"{field} contains duplicate members", "ROLLUP_MISMATCH")
    return tuple(sorted(value))


def _validate_wp5_rollups(decision) -> None:
    """Prove that producer-owned WP5 summaries could have been assembled from ``rule_results``.

    This mirrors only aggregation._assemble's rollup definitions. It is not a second aggregation pass: decision
    axes, governing selection, confidence, risk, and corroboration are intentionally not recalculated.
    """
    eligible = [r for r in decision.rule_results if _is_eligible_matched(r)]
    composites = [r for r in decision.rule_results if _is_composite(r)]

    expected: dict[str, tuple[str, ...]] = {
        "matched_rules": tuple(sorted({r["rule_id"] for r in eligible})),
        "matched_positive_indicators": tuple(sorted({iid for r in eligible
                                                       for iid in r.get("matched_positive_indicators", ())})),
        "matched_negative_indicators": tuple(sorted({iid for r in composites
                                                       for iid in r.get("matched_negative_indicators", ())})),
        "suppressed_indicators": tuple(sorted({iid for r in composites
                                                for iid in r.get("neutralised_indicators", ())})),
        "active_overrides": tuple(sorted({oid for r in composites for oid in r.get("active_overrides", ())})),
        "ambiguities": tuple(sorted({item for r in composites for item in r.get("ambiguities", ())})),
        "unknowns": tuple(sorted({item for r in composites for item in r.get("unknowns", ())})),
    }
    for field, wanted in expected.items():
        got = _canonical_rollup(getattr(decision, field), field)
        if got != wanted:
            _fail(f"{field} does not match the WP5 rollup implied by rule_results: got {got}, expected {wanted}",
                  "ROLLUP_MISMATCH")

    expected_degraded = any(r.get("evaluation_state") == "NOT_APPLICABLE" and r.get("evaluation_error")
                            for r in decision.rule_results)
    if not isinstance(decision.degraded, bool) or decision.degraded != expected_degraded:
        _fail(f"degraded does not match rule_results: got {decision.degraded!r}, expected {expected_degraded}",
              "ROLLUP_MISMATCH")

    # Whole-evaluation errors originate outside rule_results and therefore have an independent schema invariant.
    # SINGLE_RULE errors, however, are produced exactly and solely from NOT_APPLICABLE rule results by WP5.
    if not isinstance(decision.errors, tuple):
        _fail("errors must be a tuple", "INVALID_DECISION")
    actual_single: list[str] = []
    for err in decision.errors:
        if not isinstance(err, Mapping):
            _fail(f"errors entry must be a mapping, got {type(err).__name__}", "INVALID_DECISION")
        plain = dict(err)
        verrs = sorted(_whole_error_validator().iter_errors(plain), key=lambda e: list(e.path))
        if verrs:
            _fail(f"malformed decision error: {verrs[0].message}", "INVALID_DECISION")
        if plain.get("scope") == "SINGLE_RULE":
            actual_single.append(_canon(plain))

    expected_single = sorted(_canon({
        "scope": "SINGLE_RULE",
        "stage": "RULE_EVALUATION",
        "code": r["evaluation_error"].get("code", "RULE_EVALUATION_ERROR"),
        "message": r["evaluation_error"].get("message", ""),
        "rule_id": r.get("rule_id"),
    }) for r in decision.rule_results
        if r.get("evaluation_state") == "NOT_APPLICABLE" and r.get("evaluation_error"))
    if sorted(actual_single) != expected_single:
        _fail("SINGLE_RULE errors do not match NOT_APPLICABLE rule_results", "ROLLUP_MISMATCH")


def _validate_classification(decision) -> None:
    """Cross-field consistency: the classification and the WP5 decision axes must be mutually possible. Fails
    closed on any impossible combination (e.g. NO_SCAM_PATTERN with a MATCHED governing rule) — WP6 never
    silently repairs it and never emits reassuring prose for it (§6)."""
    c = decision.classification
    gid = decision.governing_rule_id
    support = decision.input_support_status
    sev, strength, risk, conf = (decision.decision_severity, decision.matched_evidence_strength,
                                 decision.risk_level, decision.detection_confidence)
    eligible = [r for r in decision.rule_results if _is_eligible_matched(r)]
    whole_error = any(e.get("scope") == "WHOLE_EVALUATION" for e in decision.errors)

    if c != "ERROR" and whole_error:
        _fail(f"{c} cannot carry a WHOLE_EVALUATION error (WP5 would classify it ERROR)",
              "CLASSIFICATION_INCONSISTENT")

    def _none_axes(label: str) -> None:
        if sev != "NONE" or strength != "NONE" or risk != "NONE" or conf != "NOT_APPLICABLE":
            _fail(f"{label}: decision axes must be NONE/NOT_APPLICABLE "
                  f"(severity={sev}, strength={strength}, risk={risk}, confidence={conf})",
                  "CLASSIFICATION_INCONSISTENT")

    if c in _SCAM_CLASSES:
        if support not in _EVALUABLE_SUPPORT:
            _fail(f"{c} with non-evaluable input_support_status {support!r}", "CLASSIFICATION_INCONSISTENT")
        if gid is None:
            _fail(f"{c} with no governing rule", "CLASSIFICATION_INCONSISTENT")
        if gid not in decision.matched_rules:
            _fail(f"{c}: governing rule {gid!r} not in matched_rules", "CLASSIFICATION_INCONSISTENT")
        if not eligible:
            _fail(f"{c}: no eligible MATCHED composite rule", "CLASSIFICATION_INCONSISTENT")
        gov = next((r for r in decision.rule_results if r.get("rule_id") == gid), None)
        if gov is None:
            _fail(f"{c}: governing rule {gid!r} absent from rule_results", "CLASSIFICATION_INCONSISTENT")
        if not _is_eligible_matched(gov):
            _fail(f"{c}: governing rule {gid!r} is not an eligible MATCHED composite", "CLASSIFICATION_INCONSISTENT")
        if sev == "NONE" or strength == "NONE" or risk == "NONE":
            _fail(f"{c}: severity/strength/risk must be non-NONE "
                  f"(severity={sev}, strength={strength}, risk={risk})", "CLASSIFICATION_INCONSISTENT")
        if conf == "NOT_APPLICABLE":
            _fail(f"{c}: detection_confidence must be applicable", "CLASSIFICATION_INCONSISTENT")
        if c == "SCAM_PATTERN_DETECTED" and conf == "LOW":
            _fail("SCAM_PATTERN_DETECTED with LOW detection_confidence (would be SUSPECTED)", "CLASSIFICATION_INCONSISTENT")
        if c == "SCAM_PATTERN_SUSPECTED" and conf != "LOW":
            _fail(f"SCAM_PATTERN_SUSPECTED requires LOW detection_confidence, got {conf}", "CLASSIFICATION_INCONSISTENT")
    elif c == "NO_SCAM_PATTERN":
        if support not in _EVALUABLE_SUPPORT:
            _fail(f"NO_SCAM_PATTERN with non-evaluable input_support_status {support!r}", "CLASSIFICATION_INCONSISTENT")
        if gid is not None:
            _fail(f"NO_SCAM_PATTERN with a governing rule {gid!r}", "CLASSIFICATION_INCONSISTENT")
        if eligible:
            _fail("NO_SCAM_PATTERN with an eligible MATCHED harmful rule", "CLASSIFICATION_INCONSISTENT")
        _none_axes("NO_SCAM_PATTERN")
    elif c == "INSUFFICIENT_EVIDENCE":
        if gid is not None:
            _fail(f"INSUFFICIENT_EVIDENCE with a governing rule {gid!r}", "CLASSIFICATION_INCONSISTENT")
        if eligible:
            _fail("INSUFFICIENT_EVIDENCE with an eligible MATCHED harmful rule", "CLASSIFICATION_INCONSISTENT")
        _none_axes("INSUFFICIENT_EVIDENCE")
    elif c == "UNSUPPORTED":
        if support != "UNSUPPORTED":
            _fail(f"UNSUPPORTED classification requires input_support_status UNSUPPORTED, got {support!r}",
                  "CLASSIFICATION_INCONSISTENT")
        if gid is not None or eligible:
            _fail("UNSUPPORTED with a governing/eligible harmful rule", "CLASSIFICATION_INCONSISTENT")
        _none_axes("UNSUPPORTED")
    elif c == "ERROR":
        # WP5 returns ERROR from either an upstream input_support_status=ERROR (errors may be empty) OR a
        # WHOLE_EVALUATION error (which is itself the non-empty error). Requiring one of those is the faithful
        # invariant; requiring errors to be non-empty universally would reject a legitimate WP5 ERROR output.
        if not (support == "ERROR" or whole_error):
            _fail("ERROR classification requires input_support_status ERROR or a WHOLE_EVALUATION error",
                  "CLASSIFICATION_INCONSISTENT")
        if gid is not None or eligible:
            _fail("ERROR with a governing/eligible harmful rule", "CLASSIFICATION_INCONSISTENT")
        _none_axes("ERROR")
    else:
        _fail(f"unknown classification {c!r}", "CLASSIFICATION_INCONSISTENT")


def _validate_explanation_input(decision, rk, *, live: bool) -> None:
    """The single WP6 trust boundary. Validate the supplied WP5 decision against authoritative RuntimeKnowledge
    and the WP5 invariants BEFORE any rendering. Fails closed (typed ``ExplanationError``); reuses the WP5
    rule-result schema + semantic validators rather than inventing divergent semantics (§5–§11)."""
    if not isinstance(decision, DecisionResult):
        _fail(f"decision is not a WP5 DecisionResult (got {type(decision).__name__})", "INVALID_DECISION")

    # WP6 governed actions require the pinned action policy; a historical (1.0.0) bundle fails closed, never
    # silently returns no actions. Every action-bearing result is thus tied to component_versions.action_policy.
    if not rk.has_action_policy():
        _fail("ACTION_POLICY_UNAVAILABLE: the executed RuntimeKnowledge pins no governed action policy "
              "(pre-WP6 / manifest 1.0.0 bundle); WP6 cannot generate recommended actions",
              "ACTION_POLICY_UNAVAILABLE")

    # ---- axis vocabularies ----
    if decision.input_support_status not in _SUPPORT_VALUES:
        _fail(f"invalid input_support_status {decision.input_support_status!r}", "INVALID_DECISION")
    if decision.classification not in _CLASS_VALUES:
        _fail(f"invalid classification {decision.classification!r}", "INVALID_DECISION")
    if decision.decision_severity not in _SEVERITY_VALUES:
        _fail(f"invalid decision_severity {decision.decision_severity!r}", "INVALID_DECISION")
    if decision.matched_evidence_strength not in _STRENGTH_VALUES:
        _fail(f"invalid matched_evidence_strength {decision.matched_evidence_strength!r}", "INVALID_DECISION")
    if decision.risk_level not in _RISK_VALUES:
        _fail(f"invalid risk_level {decision.risk_level!r}", "INVALID_DECISION")
    if decision.detection_confidence not in _CONF_VALUES:
        _fail(f"invalid detection_confidence {decision.detection_confidence!r}", "INVALID_DECISION")

    # ---- every rule result: schema + WP5 semantic invariants + resolves + no duplicates (§7) ----
    validator = _rule_result_validator()
    seen: set[str] = set()
    for r in decision.rule_results:
        if not isinstance(r, Mapping):
            _fail(f"rule_results entry must be a mapping, got {type(r).__name__}", "RULE_RESULT_INVALID")
        errs = sorted(validator.iter_errors(dict(r)), key=lambda e: list(e.path))
        if errs:
            e = errs[0]
            _fail(f"rule_result {r.get('rule_id')!r} fails rule-evaluation-result.schema.json: "
                  f"{e.message} at /{'/'.join(map(str, e.path))}", "RULE_RESULT_INVALID")
        try:
            _check_semantic_invariants(r, rk)
        except AggregationError as ex:
            _fail(f"rule_result semantic invariant: {ex}", "RULE_RESULT_INVALID")
        rid = r.get("rule_id")
        if rk.rule(rid) is None:
            _fail(f"rule_result rule_id {rid!r} does not resolve in RuntimeKnowledge", "REFERENCE_INVALID")
        if rid in seen:
            _fail(f"duplicate rule_id {rid!r} in rule_results", "RULE_RESULT_INVALID")
        seen.add(rid)

    # ---- exact WP5 producer rollups + error-system-state invariants (§7/H3A) ----
    _validate_wp5_rollups(decision)

    # ---- classification cross-field consistency (§6) ----
    _validate_classification(decision)

    rule_of = rk.published_rule if live else rk.rule

    # ---- governing + contributing rules resolve (and, live, are PUBLISHED) (§5/§8) ----
    for rid in sorted(_contributing_rule_ids(decision)):
        if rule_of(rid) is None:
            if live and rk.rule(rid) is not None:
                _fail(f"contributing rule {rid!r} is not PUBLISHED; the live path is PUBLISHED-only", "UNPUBLISHED_RULE")
            _fail(f"contributing rule {rid!r} does not resolve in RuntimeKnowledge", "REFERENCE_INVALID")

    # ---- active overrides resolve; exact rule-result backing was established by rollup reconciliation (§10) ----
    for oid in decision.active_overrides:
        if rk.override(oid) is None:
            _fail(f"active override {oid!r} does not resolve in RuntimeKnowledge", "REFERENCE_INVALID")

    # ---- eligible MATCHED source echoes must be exactly complete against governed authority (§11/M3A) ----
    for r in decision.rule_results:
        if not _is_eligible_matched(r):
            continue
        rid = r["rule_id"]
        authoritative = sorted(_canon(x) for x in _authoritative_source_refs(rule_of(rid)))
        echoed = sorted(_canon({k: item[k] for k in _ECHO_KEYS if item.get(k) is not None})
                        for item in r.get("source_references", ()))
        if echoed != authoritative:
            _fail(f"rule {rid}: source_references are not an exact echo of governed authority",
                  "SOURCE_REFERENCE_MISMATCH")


# ================================================================ recommended actions (governed policy only)

def _recommended_actions(decision, rk, rule_of) -> tuple[dict, ...]:
    classification = decision.classification
    support = decision.input_support_status
    active_overrides = set(decision.active_overrides)
    matched_negatives = set(decision.matched_negative_indicators)
    eligible_rule_ids = list(decision.matched_rules)

    parent = _taxonomy_parent_map(rk)
    rule_tax: dict[str, set[str]] = {rid: _rule_taxonomy_ids(rule_of(rid), parent) for rid in eligible_rule_ids}

    # verification-eligible rules: eligible MATCHED with verification_steps, OR (only when the decision is
    # INSUFFICIENT_EVIDENCE) a decision-relevant unresolved INDETERMINATE rule with verification_steps.
    def has_steps(rid: str) -> bool:
        rule = rule_of(rid)
        return bool(rule and rule.get("explanation", {}).get("verification_steps"))

    verif_rules = {rid for rid in eligible_rule_ids if has_steps(rid)}
    if classification == "INSUFFICIENT_EVIDENCE":
        for r in decision.rule_results:
            if _decisive_unresolved(r) and has_steps(r["rule_id"]):
                verif_rules.add(r["rule_id"])

    acc: dict[str, dict[str, set]] = {}

    def add(code, *, rules=(), inds=(), ovrs=(), evs=()):
        a = acc.setdefault(code, {"reason_rule_ids": set(), "reason_indicator_ids": set(),
                                  "reason_override_ids": set(), "evidence_refs": set()})
        a["reason_rule_ids"].update(rules)
        a["reason_indicator_ids"].update(inds)
        a["reason_override_ids"].update(ovrs)
        a["evidence_refs"].update(evs)

    for e in rk.action_policy_entries():
        t = e["trigger"]
        ttype, tid, code = t["type"], t.get("id"), e["action_code"]
        allowed = (e.get("applies_when") or {}).get("classifications")
        if allowed is not None and classification not in allowed:
            continue
        evs = e.get("evidence_refs", ())
        if ttype == "OVERRIDE":
            if tid in active_overrides:
                add(code, ovrs=[tid], evs=evs)
        elif ttype == "RULE":
            if tid in eligible_rule_ids:
                add(code, rules=[tid], evs=evs)
        elif ttype == "TAXONOMY":
            matched = [rid for rid in eligible_rule_ids if tid in rule_tax.get(rid, ())]
            if matched:
                add(code, rules=matched, evs=evs)
        elif ttype == "NEGATIVE_INDICATOR":
            if tid in matched_negatives:
                add(code, inds=[tid], evs=evs)
        elif ttype == "RULE_VERIFICATION_POLICY":
            if verif_rules:
                add(code, rules=sorted(verif_rules), evs=evs)
        elif ttype == "SYSTEM_CLASSIFICATION":
            if classification == tid:
                add(code, evs=evs)
        elif ttype == "SYSTEM_SUPPORT_STATUS":
            if support == tid:
                add(code, evs=evs)

    out: list[dict] = []
    for code in _ACTION_ORDER:
        if code not in acc:
            continue
        a = acc[code]
        ra: dict[str, Any] = {"action_code": code}
        if a["reason_rule_ids"]:
            ra["reason_rule_ids"] = sorted(a["reason_rule_ids"])
        if a["reason_indicator_ids"]:
            ra["reason_indicator_ids"] = sorted(a["reason_indicator_ids"])
        if a["reason_override_ids"]:
            ra["reason_override_ids"] = sorted(a["reason_override_ids"])
        if a["evidence_refs"]:
            ra["evidence_refs"] = sorted(a["evidence_refs"])
        out.append(ra)
    return tuple(out)


# ================================================================ explanation (deterministic templates)

_WHAT = {
    "NO_SCAM_PATTERN": "No governed scam pattern was established from the evidence evaluated.",
    "INSUFFICIENT_EVIDENCE": "The available evidence does not support a definitive conclusion.",
    "UNSUPPORTED": "This input was not evaluated: its language/script is outside the supported scope (en/Latn).",
    "ERROR": "The evaluation could not be completed.",
}
_SUMMARY = {
    "NO_SCAM_PATTERN": "No governed scam pattern was established from the evidence evaluated.",
    "INSUFFICIENT_EVIDENCE": "Insufficient evidence for a definitive conclusion; routed to human review.",
    "UNSUPPORTED": "Input not evaluated — unsupported language/script; resubmit in a supported language.",
    "ERROR": "Evaluation could not be completed; routed to human review.",
}
_WHY = {
    "NO_SCAM_PATTERN": "No governed composite rule matched, or every matched rule was cancelled by governed benign context.",
    "INSUFFICIENT_EVIDENCE": "No governed rule combination was satisfied, and/or a decisive question remained unresolved.",
    "UNSUPPORTED": "Deterministic detection runs only within the supported language/script scope; this input is out of scope.",
    "ERROR": "A fail-closed integrity or runtime condition prevented a decision.",
}


def _confidence_reason(decision, gov_result) -> str:
    band = decision.detection_confidence
    if band == "NOT_APPLICABLE":
        return f"Detection confidence is not applicable for classification {decision.classification}."
    verdict = (gov_result or {}).get("rule_evidence_verdict")
    override = bool((gov_result or {}).get("active_overrides"))
    parts = [f"Detection confidence is {band}", f"governing evidence verdict {verdict}"]
    if override:
        parts.append("an active governed hard-risk override supports the finding")
    if verdict in ("PARTIAL", "HEURISTIC"):
        parts.append(f"evidence verdict {verdict} caps confidence at MEDIUM")
    if decision.degraded:
        parts.append("a degraded per-rule evaluation caps confidence at MEDIUM")
    return "; ".join(parts) + ". Categorical, not a probability."


def _suppression_considered(decision) -> list[dict]:
    seen: dict[str, str] = {}   # suppressor id -> outcome (first wins deterministically)
    order = {"APPLIED": 0, "BLOCKED_BY_OVERRIDE": 1, "RECORDED_CONTEXT_ONLY": 2}
    for r in sorted(decision.rule_results, key=lambda x: x.get("rule_id", "")):
        supp = r.get("suppression") or {}
        for sid in supp.get("applied_suppressors", ()):
            seen[sid] = "APPLIED"
        for sid in list(supp.get("blocked_suppressors", ())) + list(supp.get("blocked_severity_caps", ())):
            seen.setdefault(sid, "BLOCKED_BY_OVERRIDE")
        for sid in supp.get("context_only_present", ()):
            seen.setdefault(sid, "RECORDED_CONTEXT_ONLY")
    return [{"suppressor": sid, "outcome": seen[sid]}
            for sid in sorted(seen, key=lambda s: (order.get(seen[s], 9), s))]


def _evidence_basis(eligible, rule_of) -> list[dict]:
    """Deterministic official-citation set built from the GOVERNED rule's authoritative source references
    (§11) — never the caller's echo. Canonical-IDENTITY dedup over ALL emitted fields and TOTAL ordering by
    full canonical structure (§12/M1): the SAME governed source can legitimately support different rules with
    distinct stored quotes/provenance — each distinct governed reference survives; only byte-equivalent ones
    collapse; permuted inputs yield an identical evidence_basis. Quote text is never invented or combined."""
    items: dict[str, dict] = {}   # canonical json key -> item
    for r in eligible:
        for item in _authoritative_source_refs(rule_of(r.get("rule_id"))):
            items[_canon(item)] = item
    return [items[k] for k in sorted(items)]


def _supporting_observations(eligible, observations) -> list[dict]:
    obs_by_id = {}
    for o in (observations or ()):
        if isinstance(o, Mapping) and o.get("observation_id"):
            obs_by_id[o["observation_id"]] = o
    refs: set[str] = set()
    for r in eligible:
        for groups in (r.get("live_positive_provenance") or {}).values():
            for group in groups:
                refs.update(group)
    out = []
    for ref in sorted(refs):
        item = {"observation_ref": ref}
        off = (obs_by_id.get(ref) or {}).get("offsets")
        if isinstance(off, Mapping) and isinstance(off.get("start"), int) and isinstance(off.get("end"), int):
            item["span"] = {"start": off["start"], "end": off["end"]}
        out.append(item)
    return out


def _verification_steps(decision, rule_of) -> list[dict]:
    steps: list[str] = []
    ordered = ([decision.governing_rule_id] if decision.governing_rule_id else []) + \
        sorted(rid for rid in decision.matched_rules if rid != decision.governing_rule_id)
    # for INSUFFICIENT_EVIDENCE, add decision-relevant unresolved rules (deterministic)
    if decision.classification == "INSUFFICIENT_EVIDENCE":
        ordered += sorted({r["rule_id"] for r in decision.rule_results if _decisive_unresolved(r)})
    seen = set()
    for rid in ordered:
        rule = rule_of(rid)
        for s in (rule or {}).get("explanation", {}).get("verification_steps", ()):
            if s not in seen:
                seen.add(s)
                steps.append(s)
    return steps


def _limitations(decision, gov_result) -> list[str]:
    out: list[str] = list(decision.ambiguities)
    if decision.degraded:
        out.append("Evaluation was degraded: a per-rule error occurred; the case is routed to review.")
    verdict = (gov_result or {}).get("rule_evidence_verdict")
    if verdict in ("PARTIAL", "HEURISTIC"):
        out.append(f"The governing rule's evidence verdict is {verdict}; severity and confidence are capped accordingly.")
    out.append("Synthetic-only validation; no accuracy/precision/recall claim (G-09).")
    return out


def build_explanation(decision, *, rk, observations: Iterable[Mapping[str, Any]] | None = None) -> ExplanationResult:
    """PUBLIC live production surface. Build the WP6 explanation + governed recommended actions for one WP5
    ``DecisionResult`` (read-only) after fully validating it at the trust boundary. PUBLISHED-only: a live scam
    finding/action may only come from a PUBLISHED rule (§8). A forged/impossible/unpublished decision raises
    ``ExplanationError`` — never a reassuring explanation."""
    return _build_explanation(decision, rk=rk, observations=observations, live=True)


def _build_explanation(decision, *, rk, observations: Iterable[Mapping[str, Any]] | None = None,
                       live: bool = True) -> ExplanationResult:
    """Core builder. ``live=True`` is the PUBLISHED-only production path (via ``build_explanation``).
    ``live=False`` is the PRIVATE design-preview path used ONLY by the golden specification/tests to render the
    designed on-promotion behaviour of ``live_publishable:false`` cases; it is not exported and is not a
    production escape hatch."""
    try:
        _validate_explanation_input(decision, rk, live=live)
        rule_of = rk.published_rule if live else rk.rule
        classification = decision.classification

        gov_rule = rule_of(decision.governing_rule_id) if decision.governing_rule_id is not None else None
        gov_result = None
        if decision.governing_rule_id is not None:
            gov_result = next((r for r in decision.rule_results if r.get("rule_id") == decision.governing_rule_id), None)

        eligible = sorted((r for r in decision.rule_results if _eligible_matched(r)),
                          key=lambda r: r.get("rule_id", ""))

        ex: dict[str, Any] = {}
        if classification in _SCAM_CLASSES:
            name = gov_rule.get("name")
            ex["what_was_detected"] = f"TrustLens identified the governed scam pattern: {name}."
            ex["why"] = "The required indicator combination for this governed pattern matched."
            ex["summary"] = (f"{'Scam pattern detected' if classification == 'SCAM_PATTERN_DETECTED' else 'Scam pattern suspected'}: "
                             f"{name} — risk {decision.risk_level}, confidence {decision.detection_confidence}.")
        else:
            ex["what_was_detected"] = _WHAT[classification]
            ex["why"] = _WHY[classification]
            ex["summary"] = _SUMMARY[classification]
        ex["detection_confidence_reason"] = _confidence_reason(decision, gov_result)

        if decision.matched_positive_indicators:
            ex["matched_indicators"] = sorted(decision.matched_positive_indicators)
        if decision.matched_rules:
            ex["rules_fired"] = sorted(decision.matched_rules)
        if decision.active_overrides:
            ex["overrides_applied"] = [
                {"override_id": oid, **({"blocked_categories": sorted(cats)} if (cats := list((rk.override(oid) or {}).get("blocks_suppression_categories", ()))) else {})}
                for oid in sorted(decision.active_overrides)]
        supp = _suppression_considered(decision)
        if supp:
            ex["suppression_considered"] = supp
        eb = _evidence_basis(eligible, rule_of)
        if eb:
            ex["evidence_basis"] = eb
        so = _supporting_observations(eligible, observations)
        if so:
            ex["supporting_observations"] = so
        vs = _verification_steps(decision, rule_of)
        if vs:
            ex["verification_steps"] = vs
        if decision.unknowns:
            ex["remaining_unknowns"] = list(decision.unknowns)
        lim = _limitations(decision, gov_result)
        if lim:
            ex["limitations"] = lim

        actions = _recommended_actions(decision, rk, rule_of)
        return ExplanationResult(explanation=ex, recommended_actions=actions,
                                 action_policy_version=rk.action_policy_version)
    except ExplanationError:
        raise
    except _EXPL_FAULTS as e:
        raise ExplanationError(f"malformed decision/knowledge for explanation: {type(e).__name__}: {e}") from e
