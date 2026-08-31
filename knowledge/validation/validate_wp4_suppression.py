"""TrustLens Phase 3 P3-WP4 validator — the rule-level suppression / severity orchestration executor.

Proves `knowledge/runtime/suppression.py` (`RuleSuppressionExecutor`) against the programme decision of
2026-08-31 and DET-001 §11 / ADR-0005 §4 / ADR-0006, over the REAL published knowledge bundle (built
deterministically by `build_bundle.py`, loaded by the P3-WP2 loader) AND — for governed effects that have
no live library example — over EXPLICIT, TEST-ONLY synthetic RuntimeKnowledge. The two are labelled
distinctly and never conflated:

  * REAL GOVERNED BUNDLE TEST  — production WP3→WP4 path over the real bundle (`*_with_suppression_*`).
  * SYNTHETIC ENGINE-CAPABILITY TEST — WP4 executor over a hand-built synthetic RuntimeKnowledge carrying
    TEST-ONLY negative indicators / overrides. These prove ENGINE SEMANTICS only; they are NOT evidence
    that the corresponding negative indicator exists in published TrustLens knowledge, and make NO
    accuracy/effectiveness claim.

The current governed negative library has 13 SUPPRESS_RULE, 8 SUPPRESS_INDICATOR, 8 CONTEXT_ONLY and ZERO
CAP_SEVERITY entries, and every SUPPRESS_RULE is `blockable_by_overrides`. So CAP_SEVERITY and
    non-blockable SUPPRESS_RULE (test-matrix rows 3–7, 19–20 where applicable) are engine-capability tests;
    rows 1,2,8–18 use real governed entries where the matrix permits.

The 20-row test matrix (programme brief):
  1  MATCHED + active SUPPRESS_RULE            -> SUPPRESSED                       (REAL)
  2  MATCHED + SUPPRESS_RULE blocked by override -> MATCHED                        (REAL)
  3  non-blockable SUPPRESS_RULE + override     -> SUPPRESSED                      (SYNTHETIC)
  4  MATCHED CRITICAL + CAP HIGH                -> effective HIGH                  (SYNTHETIC)
  5  caps HIGH + MEDIUM                         -> effective MEDIUM                (SYNTHETIC)
  6  cap blocked by override                    -> declared/base severity retained (SYNTHETIC)
  7  one cap blocked, one survives              -> surviving cap applies           (SYNTHETIC)
  8  CONTEXT_ONLY                               -> no state/severity change        (REAL)
  9  NOT_MATCHED + suppressor                   -> remains NOT_MATCHED             (REAL)
 10  INDETERMINATE + suppressor                 -> remains INDETERMINATE           (REAL)
 11  NOT_APPLICABLE + suppressor                -> remains NOT_APPLICABLE          (REAL)
 12  deterministic effect ordering                                                (REAL+SYNTH)
 13  malformed governed effect                  -> fail closed / typed error       (SYNTHETIC)
 14  WP3 occurrence-associated SUPPRESS_INDICATOR unchanged                        (REAL, GDC-15)
 15  structural negation cannot be resurrected                                    (REAL)
 16  no WP5 / decision fields emitted                                             (REAL+SYNTH)
 17  multiple SUPPRESS_RULE effects              -> lexical primary suppressor     (REAL)
 18  CONTEXT_ONLY + SUPPRESS_RULE                 -> deterministic suppression      (REAL)
 19  malformed member in batch                    -> isolated typed error           (SYNTHETIC)
 20  WP3 base below WP4 cap                       -> severity never increases       (SYNTHETIC)

Minor-remediation regressions additionally prove whole-result canonicalisation under duplicate/permuted
schema-valid set arrays, the full valid monotonicity ladder, malformed CRITICAL-cap rejection, rejection
of every WP5-owned field at the public boundary, and batch isolation of a WP5-contaminated member.

Usage:
  .venv/bin/python knowledge/validation/validate_wp4_suppression.py [--quiet]
Exit 0 iff every assertion passes.
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "knowledge" / "publish"))     # build_bundle (publishing tool, not a package)

import build_bundle  # noqa: E402

from knowledge.runtime import (  # noqa: E402
    EvaluationProfile,
    RuleEvaluator,
    RuleSuppressionExecutor,
    SuppressionExecutionError,
    evaluate_rule_with_suppression_from_governed,
    evaluate_rules_with_suppression_from_governed,
    load_bundle,
)
from knowledge.runtime.indexes import INDEX_NAMES  # noqa: E402
from knowledge.runtime.runtime_knowledge import RuntimeKnowledge  # noqa: E402
from knowledge.runtime.suppression import SEVERITY_ORDER  # noqa: E402

RESULT_SCHEMA = ROOT / "knowledge" / "schemas" / "detection" / "rule-evaluation-result.schema.json"
GOLDEN = ROOT / "docs" / "03-detection" / "golden-decision-cases-v1.json"

# Decision-level / aggregation-derived keys WP4 must NEVER emit (owned by WP5/WP6). Same forbidden set the
# WP3 validator uses — makes the boundary check non-vacuous.
FORBIDDEN_RESULT_KEYS = frozenset({
    "classification", "risk_level", "decision_severity", "matched_evidence_strength",
    "detection_confidence", "corroboration",
    "rule_evidence_strength", "rule_detection_confidence",
    "governing", "governing_reason",
})

_PROV = {"extractor_id": "wp4-tests", "extractor_type": "LLM", "extractor_version": "1.0.0"}
_INPUT = "IN-WP4"


class Check:
    """Named assertion bucket; collects failures without aborting so the whole suite reports at once."""

    def __init__(self) -> None:
        self.failures: list[str] = []
        self.count = 0

    def ok(self, cond: bool, msg: str) -> None:
        self.count += 1
        if not cond:
            self.failures.append(msg)

    def eq(self, got, want, msg: str) -> None:
        self.count += 1
        if got != want:
            self.failures.append(f"{msg}: got {got!r}, want {want!r}")


# ================================================================ REAL governed-data builders

def _ob(oid, *, status="OBSERVED", polarity="AFFIRMED", attribution="FIRST_PARTY", mood="DIRECTIVE",
        otype="CLAIM"):
    return {"observation_id": oid, "observation_type": otype, "source_input_id": _INPUT, "status": status,
            "polarity": polarity, "attribution": attribution, "mood": mood, "provenance": _PROV}


def _io(iid, refs, *, matched="OBSERVED", confidence="HIGH", polarity="POSITIVE"):
    d = {"indicator_id": iid, "polarity": polarity, "matched": matched, "input_id": _INPUT,
         "provenance": _PROV, "observation_refs": list(refs)}
    if confidence is not None:
        d["confidence"] = {"level": confidence}
    return d


def _pos(iid, ref, *, matched="OBSERVED", confidence="HIGH", **obs):
    return _io(iid, [ref], matched=matched, confidence=confidence, polarity="POSITIVE"), _ob(ref, status=_STATUS[matched], **obs)


def _neg(iid, ref, *, matched="OBSERVED", confidence="HIGH"):
    return _io(iid, [ref], matched=matched, confidence=confidence, polarity="NEGATIVE"), _ob(ref, status=_STATUS[matched])


_STATUS = {"OBSERVED": "OBSERVED", "NOT_OBSERVED": "NOT_OBSERVED", "AMBIGUOUS": "AMBIGUOUS",
           "UNKNOWN": "UNKNOWN", "NOT_APPLICABLE": "NOT_APPLICABLE"}


def _governed(*pairs):
    """Split (indicator, observation) pairs into the two governed dict lists a `*_from_governed` API takes."""
    ind = [p[0] for p in pairs]
    obs = [p[1] for p in pairs]
    return ind, obs


# ================================================================ SYNTHETIC TEST-ONLY RuntimeKnowledge

def _synthetic_rk(negatives: dict[str, dict], overrides: dict[str, dict]) -> RuntimeKnowledge:
    """Build an EXPLICIT, TEST-ONLY RuntimeKnowledge carrying only the two indexes WP4 reads
    (`negative_indicators_by_id`, `overrides_by_id`). This is TEST INFRASTRUCTURE — it never touches the
    real immutable bundle and asserts nothing about published knowledge (SYNTHETIC ENGINE-CAPABILITY only)."""
    indexes = {name: {} for name in INDEX_NAMES}
    indexes["negative_indicators_by_id"] = dict(negatives)
    indexes["overrides_by_id"] = dict(overrides)
    return RuntimeKnowledge.build({}, indexes)


def _syn_neg(nid, effect, *, category="TEST_CATEGORY", blockable=False, severity_cap=None):
    n = {"negative_indicator_id": nid, "suppression_effect": effect, "category": category,
         "blockable_by_overrides": blockable}
    if severity_cap is not None:
        n["severity_cap"] = severity_cap
    return n


def _syn_override(oid, blocked_categories):
    return {"override_id": oid, "blocks_suppression_categories": list(blocked_categories)}


def _matched_result(*, rule_id="TL-SYN-001", severity="CRITICAL", effective=None,
                    matched_negative=(), active_overrides=(), suppression=None):
    """A hand-built WP3-shaped MATCHED COMPOSITE result for SYNTHETIC engine-capability tests. Mirrors the
    fields WP4 consumes; nothing here is claimed to be a real published finding."""
    r = {
        "rule_id": rule_id, "rule_version": "1.0.0", "kind": "COMPOSITE",
        "evaluation_state": "MATCHED", "required_combination_result": "TRUE",
        "matched_positive_indicators": ["SYN_POS_A", "SYN_POS_B"],
        "evidence_classes_spanned": ["PRETEXT", "PAYMENT_ACTION"],
        "min_evidence_classes_required": 2, "evidence_class_diversity_met": True,
        "rule_evidence_verdict": "SUPPORTED", "rule_severity_declared": severity,
        "effective_severity": effective if effective is not None else severity,
    }
    if matched_negative:
        r["matched_negative_indicators"] = list(matched_negative)
    if active_overrides:
        r["active_overrides"] = list(active_overrides)
    if suppression is not None:
        r["suppression"] = suppression
    return r


# ================================================================ 1–2, 8–11, 14–15, 17–18 REAL bundle tests

def check_real_suppress_rule(c: Check, rk) -> list[dict]:
    """Rows 1, 2, 8, 9, 10, 11, 15, 17, 18 — REAL GOVERNED BUNDLE."""
    produced: list[dict] = []

    def run_rule(rid, *pairs, language="en"):
        ind, obs = _governed(*pairs)
        r = evaluate_rule_with_suppression_from_governed(rk, rid, ind, obs, language=language)
        produced.append(r)
        return r

    # Row 1 — MATCHED + active SUPPRESS_RULE -> SUPPRESSED (TL-JOB-001 TAX-06, no override) + EDUCATIONAL_CONTENT
    r1 = run_rule("TL-JOB-001",
                  _pos("UPFRONT_FEE_DEMAND", "o1"), _pos("JOB_CONTEXT", "o2"),
                  _neg("EDUCATIONAL_CONTENT", "o3"))
    c.eq(r1["evaluation_state"], "SUPPRESSED", "row1: TL-JOB-001 + EDUCATIONAL_CONTENT is SUPPRESSED")
    c.eq(r1["required_combination_result"], "TRUE", "row1: SUPPRESSED keeps required_combination_result TRUE")
    c.ok("EDUCATIONAL_CONTENT" in r1.get("suppression", {}).get("applied_suppressors", []),
         "row1: EDUCATIONAL_CONTENT recorded in applied_suppressors")
    c.eq(r1.get("suppression", {}).get("suppressed_by"), "EDUCATIONAL_CONTENT",
         "row1: suppressed_by is the lexical-first applied suppressor")

    # Row 2 — SUPPRESS_RULE blocked by override -> MATCHED (TL-CRED-001 + EDUCATIONAL_CONTENT + HR_OTP_DISCLOSURE_REQUEST)
    r2 = run_rule("TL-CRED-001",
                  _pos("CREDENTIAL_REQUEST_OTP", "o1"), _pos("ACCOUNT_BLOCK_THREAT", "o2"),
                  _neg("EDUCATIONAL_CONTENT", "o3"))
    c.eq(r2["evaluation_state"], "MATCHED", "row2: override blocks SUPPRESS_RULE, rule stays MATCHED")
    c.ok("HR_OTP_DISCLOSURE_REQUEST" in r2.get("active_overrides", []), "row2: override active")
    c.ok("EDUCATIONAL_CONTENT" in r2.get("suppression", {}).get("blocked_suppressors", []),
         "row2: blocked suppressor recorded (FR-042)")
    c.ok("applied_suppressors" not in r2.get("suppression", {}),
         "row2: no suppressor applied while blocked")

    # Row 8 — CONTEXT_ONLY -> no state/severity change (TL-JOB-001 MATCHED + LOW_AMOUNT)
    r8 = run_rule("TL-JOB-001",
                  _pos("UPFRONT_FEE_DEMAND", "o1"), _pos("JOB_CONTEXT", "o2"),
                  _neg("LOW_AMOUNT", "o3"))
    c.eq(r8["evaluation_state"], "MATCHED", "row8: CONTEXT_ONLY does not change state")
    c.eq(r8.get("effective_severity"), "HIGH", "row8: CONTEXT_ONLY does not change severity (declared HIGH)")
    c.ok("LOW_AMOUNT" in r8.get("suppression", {}).get("context_only_present", []),
         "row8: CONTEXT_ONLY recorded as context")
    c.ok("applied_suppressors" not in r8.get("suppression", {}), "row8: CONTEXT_ONLY never suppresses")

    # Row 9 — NOT_MATCHED + suppressor -> remains NOT_MATCHED (missing decisive operand via NOT_OBSERVED)
    r9 = run_rule("TL-JOB-001",
                  _pos("UPFRONT_FEE_DEMAND", "o1", matched="NOT_OBSERVED"), _pos("JOB_CONTEXT", "o2"),
                  _neg("EDUCATIONAL_CONTENT", "o3"))
    c.eq(r9["evaluation_state"], "NOT_MATCHED", "row9: NOT_MATCHED + suppressor stays NOT_MATCHED")
    c.ok("applied_suppressors" not in r9.get("suppression", {}), "row9: no suppression applied to NOT_MATCHED")

    # Row 10 — INDETERMINATE + suppressor -> remains INDETERMINATE (AMBIGUOUS decisive operand)
    r10 = run_rule("TL-JOB-001",
                   _pos("UPFRONT_FEE_DEMAND", "o1", matched="AMBIGUOUS"), _pos("JOB_CONTEXT", "o2"),
                   _neg("EDUCATIONAL_CONTENT", "o3"))
    c.eq(r10["evaluation_state"], "INDETERMINATE", "row10: INDETERMINATE + suppressor stays INDETERMINATE")

    # Row 11 — NOT_APPLICABLE + suppressor -> remains NOT_APPLICABLE (out-of-scope language)
    r11 = run_rule("TL-JOB-001",
                   _pos("UPFRONT_FEE_DEMAND", "o1"), _pos("JOB_CONTEXT", "o2"),
                   _neg("EDUCATIONAL_CONTENT", "o3"), language="hi")
    c.eq(r11["evaluation_state"], "NOT_APPLICABLE", "row11: NOT_APPLICABLE + suppressor stays NOT_APPLICABLE")

    # Row 15 — structural negation cannot be resurrected: a NEGATED-only positive -> NOT_MATCHED, never SUPPRESSED/MATCHED
    pos_neg = _io("UPFRONT_FEE_DEMAND", ["o1"], polarity="POSITIVE")
    ob_neg = _ob("o1", polarity="NEGATED")   # structurally non-live
    r15 = evaluate_rule_with_suppression_from_governed(
        rk, "TL-JOB-001",
        [pos_neg, _io("JOB_CONTEXT", ["o2"]), _io("EDUCATIONAL_CONTENT", ["o3"], polarity="NEGATIVE")],
        [ob_neg, _ob("o2"), _ob("o3")])
    produced.append(r15)
    c.eq(r15["evaluation_state"], "NOT_MATCHED",
         "row15: structural NEGATED positive remains non-live and yields NOT_MATCHED")
    c.ok("active_overrides" not in r15,
         "row15: a structurally non-live positive cannot activate a hard-risk override")

    # Row 17 — multiple surviving SUPPRESS_RULE effects: full sorted set + lexical primary.
    r17 = run_rule("TL-JOB-001",
                   _pos("UPFRONT_FEE_DEMAND", "o1"), _pos("JOB_CONTEXT", "o2"),
                   _neg("SUPPORT_NEVER_ASKS", "o3"), _neg("EDUCATIONAL_CONTENT", "o4"))
    c.eq(r17["evaluation_state"], "SUPPRESSED", "row17: multiple surviving suppressors suppress once")
    c.eq(r17.get("suppression", {}).get("applied_suppressors"),
         ["EDUCATIONAL_CONTENT", "SUPPORT_NEVER_ASKS"],
         "row17: all applied suppressors are lexical and duplicate-free")
    c.eq(r17.get("suppression", {}).get("suppressed_by"), "EDUCATIONAL_CONTENT",
         "row17: suppressed_by is lexical first, independent of input order")

    # Row 18 — CONTEXT_ONLY is recorded alongside SUPPRESS_RULE but cannot alter effect precedence/severity.
    r18 = run_rule("TL-JOB-001",
                   _pos("UPFRONT_FEE_DEMAND", "o1"), _pos("JOB_CONTEXT", "o2"),
                   _neg("LOW_AMOUNT", "o3"), _neg("EDUCATIONAL_CONTENT", "o4"))
    c.eq(r18["evaluation_state"], "SUPPRESSED", "row18: SUPPRESS_RULE wins with CONTEXT_ONLY present")
    c.eq(r18.get("effective_severity"), "HIGH", "row18: CONTEXT_ONLY does not alter severity")
    c.eq(r18.get("suppression", {}).get("effect"), "SUPPRESS_RULE",
         "row18: deterministic primary-effect precedence")
    c.eq(r18.get("suppression", {}).get("context_only_present"), ["LOW_AMOUNT"],
         "row18: context remains recorded alongside suppression")

    return produced


def check_real_suppress_indicator_unchanged(c: Check, rk) -> dict:
    """Row 14 — WP3 occurrence-associated SUPPRESS_INDICATOR is owned by WP3; WP4 leaves it untouched.
    Uses the GDC-15 governed_input (live OTP request disjoint from a negated disclaimer)."""
    golden = json.loads(GOLDEN.read_text())
    cases = golden if isinstance(golden, list) else golden.get("cases") or golden.get("golden_cases")
    gdc15 = next(c2 for c2 in cases if c2["id"] == "GDC-15")
    gi = gdc15["governed_input"]
    ind = gi["indicator_observations"]
    obs = gi["normalized_observations"]

    ev = RuleEvaluator(rk, EvaluationProfile())
    wp3 = ev.evaluate_rule_from_governed("TL-CRED-001", ind, obs)
    wp4 = RuleSuppressionExecutor(rk).apply(wp3)

    c.eq(wp4["evaluation_state"], wp3["evaluation_state"],
         "row14: WP4 does not change the state WP3 set for a SUPPRESS_INDICATOR scenario")
    c.eq(wp4["evaluation_state"], "MATCHED",
         "row14: GDC-15 live OTP request survives (disjoint from the negated disclaimer)")
    c.eq(wp4.get("neutralised_indicators"), wp3.get("neutralised_indicators"),
         "row14: WP4 preserves WP3 neutralised_indicators (SUPPRESS_INDICATOR already executed)")
    return wp4


# ================================================================ 3–7, 13 SYNTHETIC engine-capability tests

def check_synthetic_nonblockable_and_caps(c: Check) -> list[dict]:
    """Rows 3–7 and 13 — SYNTHETIC ENGINE-CAPABILITY (no live governed example exists). These prove engine
    semantics ONLY; they do not assert that any such negative indicator exists in published knowledge."""
    produced: list[dict] = []

    # Row 3 — non-blockable SUPPRESS_RULE + override -> SUPPRESSED (override cannot block a non-blockable effect)
    rk3 = _synthetic_rk(
        {"SYN_NONBLOCK_SR": _syn_neg("SYN_NONBLOCK_SR", "SUPPRESS_RULE", category="SYN_CAT", blockable=False)},
        {"HR_SYN_TEST": _syn_override("HR_SYN_TEST", ["SYN_CAT"])})
    res3 = RuleSuppressionExecutor(rk3).apply(
        _matched_result(matched_negative=["SYN_NONBLOCK_SR"], active_overrides=["HR_SYN_TEST"]))
    produced.append(res3)
    c.eq(res3["evaluation_state"], "SUPPRESSED",
         "row3: a non-blockable SUPPRESS_RULE still suppresses even with an active override")
    c.eq(res3.get("suppression", {}).get("applied_suppressors"), ["SYN_NONBLOCK_SR"],
         "row3: non-blockable suppressor recorded as applied")

    # Row 4 — MATCHED CRITICAL + CAP HIGH -> effective HIGH
    rk4 = _synthetic_rk({"SYN_CAP_HIGH": _syn_neg("SYN_CAP_HIGH", "CAP_SEVERITY", severity_cap="HIGH")}, {})
    res4 = RuleSuppressionExecutor(rk4).apply(
        _matched_result(severity="CRITICAL", matched_negative=["SYN_CAP_HIGH"]))
    produced.append(res4)
    c.eq(res4["evaluation_state"], "MATCHED", "row4: CAP_SEVERITY does not suppress (rule stays MATCHED)")
    c.eq(res4.get("effective_severity"), "HIGH", "row4: CRITICAL capped to HIGH")
    c.eq(res4.get("suppression", {}).get("applied_severity_caps"), ["SYN_CAP_HIGH"],
         "row4: applied cap id recorded")
    c.eq(res4.get("suppression", {}).get("severity_caps_applied"), ["HIGH"], "row4: ceiling HIGH recorded")

    # Row 5 — caps HIGH + MEDIUM -> effective MEDIUM (minimum surviving ceiling)
    rk5 = _synthetic_rk({"SYN_CAP_HIGH": _syn_neg("SYN_CAP_HIGH", "CAP_SEVERITY", severity_cap="HIGH"),
                         "SYN_CAP_MED": _syn_neg("SYN_CAP_MED", "CAP_SEVERITY", severity_cap="MEDIUM")}, {})
    res5 = RuleSuppressionExecutor(rk5).apply(
        _matched_result(severity="CRITICAL", matched_negative=["SYN_CAP_HIGH", "SYN_CAP_MED"]))
    produced.append(res5)
    c.eq(res5.get("effective_severity"), "MEDIUM", "row5: min(CRITICAL, HIGH, MEDIUM) = MEDIUM")
    c.eq(res5.get("suppression", {}).get("applied_severity_caps"), ["SYN_CAP_HIGH", "SYN_CAP_MED"],
         "row5: both surviving caps recorded (sorted)")
    c.eq(res5.get("suppression", {}).get("severity_caps_applied"), ["MEDIUM", "HIGH"],
         "row5: ceilings recorded ordinal-sorted")

    # Row 6 — cap blocked by override -> declared/base severity retained
    rk6 = _synthetic_rk(
        {"SYN_CAP_BLOCKABLE": _syn_neg("SYN_CAP_BLOCKABLE", "CAP_SEVERITY", category="SYN_CAT",
                                       blockable=True, severity_cap="MEDIUM")},
        {"HR_SYN_TEST": _syn_override("HR_SYN_TEST", ["SYN_CAT"])})
    res6 = RuleSuppressionExecutor(rk6).apply(
        _matched_result(severity="CRITICAL", matched_negative=["SYN_CAP_BLOCKABLE"],
                        active_overrides=["HR_SYN_TEST"]))
    produced.append(res6)
    c.eq(res6.get("effective_severity"), "CRITICAL", "row6: blocked cap does not lower severity (CRITICAL kept)")
    c.eq(res6.get("suppression", {}).get("blocked_severity_caps"), ["SYN_CAP_BLOCKABLE"],
         "row6: blocked cap recorded")
    c.ok("applied_severity_caps" not in res6.get("suppression", {}), "row6: no cap applied while blocked")

    # Row 7 — one cap blocked, one survives -> surviving cap applies
    rk7 = _synthetic_rk(
        {"SYN_CAP_BLOCKABLE": _syn_neg("SYN_CAP_BLOCKABLE", "CAP_SEVERITY", category="SYN_CAT",
                                       blockable=True, severity_cap="MEDIUM"),
         "SYN_CAP_SURVIVE": _syn_neg("SYN_CAP_SURVIVE", "CAP_SEVERITY", category="OTHER_CAT",
                                     blockable=True, severity_cap="HIGH")},
        {"HR_SYN_TEST": _syn_override("HR_SYN_TEST", ["SYN_CAT"])})  # blocks SYN_CAT only
    res7 = RuleSuppressionExecutor(rk7).apply(
        _matched_result(severity="CRITICAL", matched_negative=["SYN_CAP_BLOCKABLE", "SYN_CAP_SURVIVE"],
                        active_overrides=["HR_SYN_TEST"]))
    produced.append(res7)
    c.eq(res7.get("effective_severity"), "HIGH", "row7: only the surviving cap (HIGH) applies")
    c.eq(res7.get("suppression", {}).get("applied_severity_caps"), ["SYN_CAP_SURVIVE"], "row7: surviving cap recorded")
    c.eq(res7.get("suppression", {}).get("blocked_severity_caps"), ["SYN_CAP_BLOCKABLE"], "row7: blocked cap recorded")

    # Row 13 — malformed governed effect -> fail closed / typed error (NOT a clean MATCHED/SUPPRESSED)
    # (a) unresolved matched-negative id
    rk_empty = _synthetic_rk({}, {})
    bad_a = RuleSuppressionExecutor(rk_empty).apply(_matched_result(matched_negative=["SYN_MISSING"]))
    produced.append(bad_a)
    c.eq(bad_a["evaluation_state"], "NOT_APPLICABLE", "row13a: unresolved negative id fails closed")
    c.eq(bad_a.get("evaluation_error", {}).get("code"), "SUPPRESSION_EXECUTION_ERROR",
         "row13a: typed SUPPRESSION_EXECUTION_ERROR")
    # (b) unknown suppression_effect
    rk_bad = _synthetic_rk({"SYN_BAD": _syn_neg("SYN_BAD", "TELEPORT_RULE")}, {})
    bad_b = RuleSuppressionExecutor(rk_bad).apply(_matched_result(matched_negative=["SYN_BAD"]))
    produced.append(bad_b)
    c.eq(bad_b["evaluation_state"], "NOT_APPLICABLE", "row13b: unknown effect fails closed")
    # (c) CAP_SEVERITY without a valid severity_cap
    rk_nocap = _synthetic_rk({"SYN_CAP_BAD": _syn_neg("SYN_CAP_BAD", "CAP_SEVERITY", severity_cap="NONE")}, {})
    bad_c = RuleSuppressionExecutor(rk_nocap).apply(_matched_result(matched_negative=["SYN_CAP_BAD"]))
    produced.append(bad_c)
    c.eq(bad_c["evaluation_state"], "NOT_APPLICABLE", "row13c: invalid severity_cap fails closed")
    # fail-closed must NEVER manufacture a safer benign result
    for b in (bad_a, bad_b, bad_c):
        c.ok(b["evaluation_state"] not in ("MATCHED", "SUPPRESSED"),
             "row13: malformed effect never yields a clean MATCHED/SUPPRESSED")

    # cross-check divergence also fails closed (WP3 informational blocked_suppressors disagrees with WP4)
    rk_x = _synthetic_rk(
        {"SYN_SR": _syn_neg("SYN_SR", "SUPPRESS_RULE", category="SYN_CAT", blockable=True)},
        {"HR_SYN_TEST": _syn_override("HR_SYN_TEST", ["SYN_CAT"])})
    diverging = _matched_result(matched_negative=["SYN_SR"], active_overrides=["HR_SYN_TEST"],
                                suppression={"blocked_suppressors": ["SOMETHING_ELSE"]})
    xr = RuleSuppressionExecutor(rk_x).apply(diverging)
    produced.append(xr)
    c.eq(xr["evaluation_state"], "NOT_APPLICABLE", "row13d: WP3/WP4 blocked-set divergence fails closed")
    c.eq(xr.get("evaluation_error", {}).get("code"), "SUPPRESSION_EXECUTION_ERROR",
         "row13d: divergence uses the typed WP4 error")

    return produced


def check_synthetic_batch_and_no_increase(c: Check) -> list[dict]:
    """Rows 19–20 — TEST-ONLY engine-capability checks for isolation and monotone severity."""
    rk = _synthetic_rk({
        "SYN_SR": _syn_neg("SYN_SR", "SUPPRESS_RULE"),
        "SYN_CAP_HIGH": _syn_neg("SYN_CAP_HIGH", "CAP_SEVERITY", severity_cap="HIGH"),
    }, {})

    # Row 19 — one unresolved governed negative degrades only its own result; order/length are preserved.
    batch = RuleSuppressionExecutor(rk).apply_all([
        _matched_result(rule_id="TL-SYN-001", matched_negative=["SYN_SR"]),
        _matched_result(rule_id="TL-SYN-002", matched_negative=["SYN_MISSING"]),
    ])
    c.eq(len(batch), 2, "row19: malformed batch member does not abort or truncate the batch")
    c.eq(batch[0]["evaluation_state"], "SUPPRESSED", "row19: valid sibling completes normally")
    c.eq(batch[1]["evaluation_state"], "NOT_APPLICABLE", "row19: malformed member alone fails closed")
    c.eq(batch[1].get("evaluation_error", {}).get("code"), "SUPPRESSION_EXECUTION_ERROR",
         "row19: malformed member carries typed WP4 error")

    # Row 20 — a higher ceiling participates but cannot raise an already-lower WP3 effective severity.
    lower_base = RuleSuppressionExecutor(rk).apply(
        _matched_result(severity="CRITICAL", effective="MEDIUM", matched_negative=["SYN_CAP_HIGH"]))
    c.eq(lower_base["evaluation_state"], "MATCHED", "row20: cap-only result stays MATCHED")
    c.eq(lower_base.get("effective_severity"), "MEDIUM", "row20: HIGH cap cannot increase MEDIUM WP3 base")
    c.eq(lower_base.get("suppression", {}).get("applied_severity_caps"), ["SYN_CAP_HIGH"],
         "row20: participating cap id remains auditable")
    c.eq(lower_base.get("suppression", {}).get("severity_caps_applied"), ["HIGH"],
         "row20: participating ceiling remains auditable")

    # Programme-approved monotonicity ladder uses only governed cap values LOW/MEDIUM/HIGH.
    monotonic: list[dict] = []
    for base, expected in (("HIGH", "HIGH"), ("MEDIUM", "MEDIUM"), ("LOW", "LOW")):
        result = RuleSuppressionExecutor(rk).apply(
            _matched_result(severity="CRITICAL", effective=base, matched_negative=["SYN_CAP_HIGH"]))
        monotonic.append(result)
        c.eq(result.get("effective_severity"), expected,
             f"remediation cap monotonicity: {base} base + HIGH cap -> {expected}")

    # CRITICAL is deliberately NOT a governed CAP_SEVERITY ceiling; it fails closed rather than acting as a no-op.
    rk_critical = _synthetic_rk({
        "SYN_CAP_CRITICAL": _syn_neg("SYN_CAP_CRITICAL", "CAP_SEVERITY", severity_cap="CRITICAL")
    }, {})
    malformed_critical = RuleSuppressionExecutor(rk_critical).apply(
        _matched_result(severity="HIGH", matched_negative=["SYN_CAP_CRITICAL"]))
    c.eq(malformed_critical["evaluation_state"], "NOT_APPLICABLE",
         "remediation cap governance: CRITICAL severity_cap fails closed")
    c.eq(malformed_critical.get("evaluation_error", {}).get("code"), "SUPPRESSION_EXECUTION_ERROR",
         "remediation cap governance: CRITICAL severity_cap carries typed WP4 error")
    return [*batch, lower_base, *monotonic, malformed_critical]


def check_public_canonicalization(c: Check) -> list[dict]:
    """Minor remediation: duplicate/permuted schema-valid set arrays produce one identical whole result."""
    rk = _synthetic_rk({
        "AAA_SUPPRESS": _syn_neg("AAA_SUPPRESS", "SUPPRESS_RULE"),
        "ZZZ_SUPPRESS": _syn_neg("ZZZ_SUPPRESS", "SUPPRESS_RULE"),
        "SYN_CAP_HIGH": _syn_neg("SYN_CAP_HIGH", "CAP_SEVERITY", severity_cap="HIGH"),
        "SYN_CAP_MED": _syn_neg("SYN_CAP_MED", "CAP_SEVERITY", severity_cap="MEDIUM"),
        "SYN_CONTEXT": _syn_neg("SYN_CONTEXT", "CONTEXT_ONLY"),
    }, {
        "HR_NOOP_A": _syn_override("HR_NOOP_A", ["UNRELATED_A"]),
        "HR_NOOP_B": _syn_override("HR_NOOP_B", ["UNRELATED_B"]),
    })

    def shaped(permuted: bool) -> dict:
        if permuted:
            result = _matched_result(
                matched_negative=["ZZZ_SUPPRESS", "SYN_CONTEXT", "SYN_CAP_MED", "AAA_SUPPRESS",
                                  "SYN_CAP_HIGH", "AAA_SUPPRESS"],
                active_overrides=["HR_NOOP_B", "HR_NOOP_A", "HR_NOOP_B"])
            result.update({
                "matched_positive_indicators": ["SYN_POS_B", "SYN_POS_A", "SYN_POS_B"],
                "neutralised_indicators": ["SYN_POS_B", "SYN_POS_A", "SYN_POS_B"],
                "evidence_classes_spanned": ["PAYMENT_ACTION", "PRETEXT", "PAYMENT_ACTION"],
                "observation_refs": ["obs-b", "obs-a", "obs-b"],
                "indicator_observation_refs": ["io-b", "io-a", "io-b"],
                "ambiguities": ["SYN_POS_B", "SYN_POS_A", "SYN_POS_B"],
                "unknowns": ["SYN_POS_B", "SYN_POS_A", "SYN_POS_B"],
                "evidence_ids": ["MR-EVID-002", "MR-EVID-001", "MR-EVID-002"],
            })
        else:
            result = _matched_result(
                matched_negative=["AAA_SUPPRESS", "SYN_CAP_HIGH", "SYN_CAP_MED", "SYN_CONTEXT",
                                  "ZZZ_SUPPRESS"],
                active_overrides=["HR_NOOP_A", "HR_NOOP_B"])
            result.update({
                "matched_positive_indicators": ["SYN_POS_A", "SYN_POS_B"],
                "neutralised_indicators": ["SYN_POS_A", "SYN_POS_B"],
                "evidence_classes_spanned": ["PAYMENT_ACTION", "PRETEXT"],
                "observation_refs": ["obs-a", "obs-b"],
                "indicator_observation_refs": ["io-a", "io-b"],
                "ambiguities": ["SYN_POS_A", "SYN_POS_B"],
                "unknowns": ["SYN_POS_A", "SYN_POS_B"],
                "evidence_ids": ["MR-EVID-001", "MR-EVID-002"],
            })
        return result

    permuted = shaped(True)
    canonical = shaped(False)
    untouched = copy.deepcopy(permuted)
    out_a = RuleSuppressionExecutor(rk).apply(permuted)
    out_b = RuleSuppressionExecutor(rk).apply(canonical)
    c.eq(permuted, untouched, "remediation canonicalisation: caller input is not mutated")
    c.eq(out_a, out_b, "remediation canonicalisation: duplicate/permuted inputs yield identical whole result")
    for field in ("matched_positive_indicators", "matched_negative_indicators", "active_overrides",
                  "neutralised_indicators", "evidence_classes_spanned", "observation_refs",
                  "indicator_observation_refs", "ambiguities", "unknowns", "evidence_ids"):
        c.ok(out_a[field] == sorted(set(out_a[field])),
             f"remediation canonicalisation: {field} sorted + duplicate-free")
    for field in ("applied_suppressors", "applied_severity_caps", "context_only_present"):
        values = out_a["suppression"][field]
        c.ok(values == sorted(set(values)),
             f"remediation canonicalisation: suppression.{field} sorted + duplicate-free")
    c.eq(out_a["suppression"]["severity_caps_applied"], ["MEDIUM", "HIGH"],
         "remediation canonicalisation: cap values unique + ordinal-sorted")
    return [out_a, out_b]


def check_wp5_boundary(c: Check) -> list[dict]:
    """Minor remediation: every WP5-owned field is rejected at every public WP4 apply boundary."""
    rk = _synthetic_rk({"SYN_SR": _syn_neg("SYN_SR", "SUPPRESS_RULE")}, {})
    produced: list[dict] = []
    sample_values = {
        "governing": True,
        "governing_reason": "pre-populated",
        "classification": "SCAM_PATTERN_DETECTED",
        "risk_level": "HIGH",
        "decision_severity": "HIGH",
        "matched_evidence_strength": "STRONG",
        "detection_confidence": "HIGH",
        "corroboration": "MULTI_RULE",
        "rule_evidence_strength": "STRONG",
        "rule_detection_confidence": "HIGH",
    }
    for field, value in sorted(sample_values.items()):
        contaminated = _matched_result(matched_negative=["SYN_SR"])
        contaminated[field] = value
        result = RuleSuppressionExecutor(rk).apply(contaminated)
        produced.append(result)
        c.eq(result["evaluation_state"], "NOT_APPLICABLE",
             f"remediation WP5 boundary: pre-populated {field} fails closed")
        c.eq(result.get("evaluation_error", {}).get("code"), "SUPPRESSION_EXECUTION_ERROR",
             f"remediation WP5 boundary: {field} carries typed WP4 error")
        c.ok(field not in result, f"remediation WP5 boundary: {field} is not silently propagated")

    # Boundary rejection precedes the structural-state pass-through path.
    nonmatched = _matched_result()
    nonmatched.update({"evaluation_state": "NOT_MATCHED", "required_combination_result": "FALSE",
                       "governing": False})
    nonmatched_result = RuleSuppressionExecutor(rk).apply(nonmatched)
    produced.append(nonmatched_result)
    c.eq(nonmatched_result["evaluation_state"], "NOT_APPLICABLE",
         "remediation WP5 boundary: non-MATCHED input with WP5 field also fails closed")

    # One contaminated member must not poison a valid sibling in apply_all.
    contaminated = _matched_result(rule_id="TL-SYN-002", matched_negative=["SYN_SR"])
    contaminated["classification"] = "SCAM_PATTERN_DETECTED"
    batch = RuleSuppressionExecutor(rk).apply_all([
        _matched_result(rule_id="TL-SYN-001", matched_negative=["SYN_SR"]), contaminated,
    ])
    produced.extend(batch)
    c.eq(len(batch), 2, "remediation WP5 boundary: contaminated batch member does not truncate batch")
    c.eq(batch[0]["evaluation_state"], "SUPPRESSED",
         "remediation WP5 boundary: valid batch sibling completes")
    c.eq(batch[1]["evaluation_state"], "NOT_APPLICABLE",
         "remediation WP5 boundary: contaminated member alone fails closed")
    c.eq(batch[1].get("evaluation_error", {}).get("code"), "SUPPRESSION_EXECUTION_ERROR",
         "remediation WP5 boundary: contaminated batch member has typed WP4 error")
    return produced


# ================================================================ 12 determinism + 16 boundary + schema

def check_determinism(c: Check, rk) -> None:
    """Row 12 — deterministic effect ordering: identical inputs -> byte-identical results; all id arrays sorted."""
    ind, obs = _governed(_pos("UPFRONT_FEE_DEMAND", "o1"), _pos("JOB_CONTEXT", "o2"),
                         _neg("EDUCATIONAL_CONTENT", "o3"), _neg("LOW_AMOUNT", "o4"))
    a = evaluate_rules_with_suppression_from_governed(rk, ind, obs)
    b = evaluate_rules_with_suppression_from_governed(rk, ind, obs)
    c.ok(json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True),
         "row12: batch WP3->WP4 is byte-identical across runs")
    for r in a:
        supp = r.get("suppression", {})
        for key in ("applied_suppressors", "blocked_suppressors", "applied_severity_caps",
                    "blocked_severity_caps", "context_only_present"):
            if key in supp:
                c.ok(list(supp[key]) == sorted(supp[key]) == sorted(set(supp[key])),
                     f"row12: suppression.{key} sorted + duplicate-free")


def check_schema_and_boundary(c: Check, produced: list[dict], validator: Draft202012Validator) -> None:
    """Row 16 — every WP4 result is schema-valid and emits NO WP5/decision field (non-vacuous)."""
    for r in produced:
        errs = sorted(validator.iter_errors(r), key=lambda e: list(e.path))
        c.ok(not errs, f"schema: {r.get('rule_id')} {r.get('evaluation_state')} -> "
                       f"{errs[0].message if errs else ''}")
        leaked = FORBIDDEN_RESULT_KEYS & set(r)
        c.ok(not leaked, f"boundary: {r.get('rule_id')} leaked decision/aggregation keys {sorted(leaked)}")
    suppressed = [r for r in produced if r["evaluation_state"] == "SUPPRESSED"]
    c.ok(bool(suppressed), "row16: at least one SUPPRESSED result produced (non-vacuous)")
    capped = [r for r in produced
              if r.get("suppression", {}).get("applied_severity_caps")]
    c.ok(bool(capped), "row16: at least one CAP_SEVERITY result produced (non-vacuous)")


# ================================================================ main

def main() -> int:
    quiet = "--quiet" in sys.argv

    def log(*a):
        if not quiet:
            print(*a)

    schema = json.loads(RESULT_SCHEMA.read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    tmp = Path(tempfile.mkdtemp(prefix="wp4-supp-"))
    bundle = tmp / "bundle"
    build_bundle.build(bundle)
    rk = load_bundle(bundle)

    log(f"P3-WP4 suppression/severity-orchestration validation — bundle {rk.bundle_version} "
        f"({len(rk.published_rule_ids())} PUBLISHED rules)")
    log("  REAL GOVERNED BUNDLE tests: rows 1,2,8,9,10,11,14,15,17,18")
    log("  SYNTHETIC ENGINE-CAPABILITY tests (no live governed example): rows 3,4,5,6,7,13,19,20")

    c = Check()
    real = check_real_suppress_rule(c, rk)
    real.append(check_real_suppress_indicator_unchanged(c, rk))
    synth = check_synthetic_nonblockable_and_caps(c)
    synth.extend(check_synthetic_batch_and_no_increase(c))
    synth.extend(check_public_canonicalization(c))
    synth.extend(check_wp5_boundary(c))
    check_determinism(c, rk)
    check_schema_and_boundary(c, real + synth, validator)

    print(f"\n{c.count - len(c.failures)}/{c.count} assertions passed.")
    if c.failures:
        print(f"P3-WP4 SUPPRESSION: FAIL — {len(c.failures)} assertion(s) failed:")
        for f in c.failures:
            print(f"  - {f}")
        return 1
    print("P3-WP4 SUPPRESSION: PASS — SUPPRESS_RULE (MATCHED->SUPPRESSED), override-aware blocking, "
          "CAP_SEVERITY min-ceiling, CONTEXT_ONLY inertness, structural non-resurrection, SUPPRESS_INDICATOR "
          "left to WP3, deterministic ordering, fail-closed typed errors, schema validity, and NO WP5 fields.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
