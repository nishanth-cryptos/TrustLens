"""TrustLens Phase 3 P3-WP5 validator — decision aggregation, risk, confidence & classification.

Proves `knowledge/runtime/aggregation.py` (`aggregate_decision`) against DET-001 §§4,5,9,10,11 / ADR-0006
and the ratified + adversarial-remediation WP5 policy, over:

  * REAL GOVERNED BUNDLE tests — the full production WP3 → WP4 → WP5 path replayed over all 15 DET-001
    golden decision cases (`golden-decision-cases-v1.json`, cases_version 1.2.0). Published rules run through
    the live production API; a golden whose governing rule is not PUBLISHED (GDC-07 TL-MAL-003, GDC-10
    TL-JOB-003) is replayed through the explicit ON-PROMOTION API. Evidence independence is proven ONLY from
    the WP3-emitted `live_positive_provenance` that rides on each rule result. The golden `expected` axes are
    the binding oracle; never changed to fit the code.
  * SYNTHETIC ENGINE-CAPABILITY tests — `aggregate_decision` over hand-built, schema-valid WP4-shaped result
    dicts (carrying `live_positive_provenance` groups) and a TEST-ONLY synthetic `RuntimeKnowledge`. These
    prove ENGINE SEMANTICS only; they assert nothing about published knowledge.

Adversarial-remediation policy under test:
  * ONE `proven_independent_evidence_count` — union-find over shared observation_refs into provenance
    COMPONENTS, then max bipartite matching (evidence class × component) — drives BOTH the corroboration band
    AND the >=3 path to HIGH confidence. Shared/merged occurrences and missing provenance never reach >=3.
  * degraded caps confidence at MEDIUM. whole-evaluation error / support ERROR → classification ERROR.
  * unresolved-harmful candidate = COMPOSITE INDETERMINATE + require UNKNOWN + WP3 ambiguities|unknowns (never
    matched positives alone). Benign clear is STRICT rule-local (NOT_MATCHED+FALSE or SUPPRESSED); a bare
    negative id / CONTEXT_ONLY / CAP_SEVERITY / diversity-fail NOT_MATCHED+TRUE never clears.
  * every result JSON-Schema-validated + the full semantic matrix (state↔required pairing incl. legal
    NOT_MATCHED+TRUE, evaluation_error placement, verdict presence, provenance key membership, reference
    resolution); whole_evaluation_errors validated against the promoted evaluationError contract. Malformed
    input → typed AggregationError, never a normal decision. Determinism: permutation → identical.

Usage:
  .venv/bin/python knowledge/validation/validate_wp5_aggregation.py [--quiet]
Exit 0 iff every assertion passes.
"""

from __future__ import annotations

import importlib.util
import json
import random
import sys
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "knowledge" / "publish"))     # build_bundle (publishing tool, not a package)

import build_bundle  # noqa: E402

from knowledge.runtime import (  # noqa: E402
    EvaluationProfile,
    RuleEvaluator,
    RuleSuppressionExecutor,
    aggregate_decision,
    load_bundle,
)
from knowledge.runtime.aggregation import RISK_MATRIX, AggregationError  # noqa: E402
from knowledge.runtime.indexes import INDEX_NAMES  # noqa: E402
from knowledge.runtime.runtime_knowledge import RuntimeKnowledge  # noqa: E402

GOLDEN = ROOT / "docs" / "03-detection" / "golden-decision-cases-v1.json"
RESULT_SCHEMA = ROOT / "knowledge" / "schemas" / "detection" / "detection-result.schema.json"
RULE_EVAL_SCHEMA = ROOT / "knowledge" / "schemas" / "detection" / "rule-evaluation-result.schema.json"
DESIGN_VALIDATOR = ROOT / "docs" / "03-detection" / "validate_det_design.py"

FORBIDDEN_KEYS = frozenset({
    "explanation", "recommended_actions", "recommended_action", "evidence_basis",
    "verification_steps", "summary", "what_was_detected",
})
FORBIDDEN_KEY_FRAGMENTS = ("prob", "score", "percent", "likelihood", "0_100", "0to100")

_PROV = {"extractor_id": "wp5-tests", "extractor_type": "LLM", "extractor_version": "1.0.0"}


class Check:
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

    def raises(self, fn, msg: str) -> None:
        self.count += 1
        try:
            fn()
            self.failures.append(msg + " (did not raise)")
        except AggregationError:
            pass
        except Exception as e:  # noqa: BLE001
            self.failures.append(msg + f" (raised {type(e).__name__}, not AggregationError)")


def _scan_no_forbidden(c: Check, obj, where: str) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            lk = str(k).lower()
            c.ok(k not in FORBIDDEN_KEYS, f"{where}: forbidden WP6 field {k!r} present")
            c.ok(not any(fr in lk for fr in FORBIDDEN_KEY_FRAGMENTS), f"{where}: probability/score-named key {k!r}")
            _scan_no_forbidden(c, v, f"{where}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _scan_no_forbidden(c, v, f"{where}[{i}]")
    else:
        c.ok(not isinstance(obj, float), f"{where}: float value {obj!r} (no numeric probability allowed)")


# ================================================================ REAL golden replay

def _compact_to_governed(rows):
    status_for = {"OBSERVED": "OBSERVED", "NOT_OBSERVED": "NOT_OBSERVED", "AMBIGUOUS": "AMBIGUOUS",
                  "UNKNOWN": "UNKNOWN", "NOT_APPLICABLE": "NOT_APPLICABLE"}
    ind, obs, seen = [], [], set()
    for i, r in enumerate(rows):
        iid = r.get("id") or r.get("indicator_id")
        matched = r["matched"]
        reg_pol = r["polarity"] if r.get("polarity") in ("POSITIVE", "NEGATIVE") else "POSITIVE"
        struct_pol = r.get("structural_polarity") or (r["polarity"] if r.get("polarity") in ("AFFIRMED", "NEGATED") else "AFFIRMED")
        refs = list(r["observation_refs"]) if r.get("observation_refs") else [f"obs-{i:02d}"]
        for ref in refs:
            if ref in seen:
                continue
            seen.add(ref)
            obs.append({"observation_id": ref, "observation_type": "CLAIM", "source_input_id": "IN-WP5",
                        "status": status_for[matched], "polarity": struct_pol,
                        "attribution": r.get("attribution") or "FIRST_PARTY", "mood": r.get("mood") or "DIRECTIVE",
                        "provenance": _PROV})
        io = {"indicator_id": iid, "polarity": reg_pol, "matched": matched, "input_id": "IN-WP5",
              "provenance": _PROV, "observation_refs": refs}
        if r.get("confidence"):
            io["confidence"] = {"level": r["confidence"]}
        ind.append(io)
    return ind, obs


def _wp4_results_for_case(rk, case):
    lang = case["language"][0] if case.get("language") else "en"
    script = case["script"][0] if case.get("script") else "Latn"
    gi = case.get("governed_input")
    ind, obs = (gi["indicator_observations"], gi["normalized_observations"]) if gi else _compact_to_governed(case["declared_indicators"])
    ev = RuleEvaluator(rk, EvaluationProfile())
    ex = RuleSuppressionExecutor(rk)
    results = {}
    for wp3 in ev.evaluate_rules_from_governed(ind, obs, language=lang, script=script):
        results[wp3["rule_id"]] = ex.apply(wp3)
    for rid in case["expected"].get("rule_states", {}):
        if rid not in results:
            wp3 = ev.evaluate_on_promotion_from_governed(rid, ind, obs, language=lang, script=script)
            results[rid] = ex.apply(wp3)
    return list(results.values())


def check_golden(c: Check, rk) -> list[tuple]:
    golden = json.loads(GOLDEN.read_text())
    matrix: list[tuple] = []
    for case in golden["cases"]:
        cid = case["id"]
        exp = case["expected"]
        support = exp["input_support_status"]

        if support in ("SUPPORTED", "PARTIALLY_SUPPORTED"):
            results = _wp4_results_for_case(rk, case)
            d = aggregate_decision(results, input_support_status=support, rk=rk)
            shuffled = results[:]
            random.Random(1234).shuffle(shuffled)
            d2 = aggregate_decision(shuffled, input_support_status=support, rk=rk)
            c.ok(d.as_decision_dict() == d2.as_decision_dict(), f"{cid}: shuffled result order -> identical decision")
        else:
            d = aggregate_decision([], input_support_status=support, rk=rk)

        c.eq(d.classification, exp["classification"], f"{cid}: classification")
        c.eq(d.decision_severity, exp["severity"], f"{cid}: decision_severity")
        c.eq(d.matched_evidence_strength, exp["matched_evidence_strength"], f"{cid}: matched_evidence_strength")
        c.eq(d.risk_level, exp["risk_level"], f"{cid}: risk_level")
        c.eq(d.detection_confidence, exp["detection_confidence"], f"{cid}: detection_confidence")
        c.eq(d.corroboration["band"], exp["corroboration_band"], f"{cid}: corroboration_band")
        # independent_evidence_classes is the matched subset -> length is exactly the proven count
        c.eq(len(d.corroboration["independent_evidence_classes"]), d.corroboration["evidence_class_count"],
             f"{cid}: len(independent_evidence_classes) == evidence_class_count")
        if cid == "GDC-10":
            c.eq(d.corroboration["evidence_class_count"], 3, "GDC-10: three proven independent classes")
            c.eq(len(d.corroboration["independent_evidence_classes"]), 3, "GDC-10: all three classes listed")
        if cid == "GDC-15":
            c.eq(d.corroboration["independent_evidence_classes"], ["CREDENTIAL_ACTION", "PRESSURE"],
                 "GDC-15: exactly the two proven independent classes")

        fired = exp.get("fired_rules", [])
        if fired:
            c.ok(d.governing_rule_id in fired, f"{cid}: governing rule {d.governing_rule_id} in fired {fired}")
            gov = next(r for r in d.rule_results if r["rule_id"] == d.governing_rule_id)
            c.ok(gov.get("governing") is True, f"{cid}: governing rule flagged")
        else:
            c.ok(d.governing_rule_id is None, f"{cid}: no governing rule when nothing fires")

        _scan_no_forbidden(c, d.as_decision_dict(), f"{cid}")
        matrix.append((cid, support, exp["classification"], d.risk_level, d.detection_confidence, exp.get("live_publishable", True)))
    return matrix


# ================================================================ SYNTHETIC engine-capability infrastructure

_TEST_INDICATORS = {
    "SYN_STRONG_A": {"id": "SYN_STRONG_A", "polarity": "POSITIVE", "evidence_class": "PRETEXT", "strength": "STRONG"},
    "SYN_STRONG_B": {"id": "SYN_STRONG_B", "polarity": "POSITIVE", "evidence_class": "PAYMENT_ACTION", "strength": "STRONG"},
    "SYN_STRONG_C": {"id": "SYN_STRONG_C", "polarity": "POSITIVE", "evidence_class": "PRESSURE", "strength": "STRONG"},
    "SYN_MOD_A": {"id": "SYN_MOD_A", "polarity": "POSITIVE", "evidence_class": "IDENTITY_CLAIM", "strength": "MODERATE"},
    "SYN_WEAK_A": {"id": "SYN_WEAK_A", "polarity": "POSITIVE", "evidence_class": "CHANNEL_ARTIFACT", "strength": "WEAK"},
}
_TEST_NEGATIVES = {
    nid: {"negative_indicator_id": nid, "suppression_effect": "SUPPRESS_RULE", "category": "TEST", "blockable_by_overrides": False}
    for nid in ("SOME_NEG", "SUPPORT_NEVER_ASKS", "SYN_SUPPRESSOR")
}
_TEST_OVERRIDES = {"HR_X": {"override_id": "HR_X", "blocks_suppression_categories": []}}


def _synthetic_rk() -> RuntimeKnowledge:
    indexes = {name: {} for name in INDEX_NAMES}
    indexes["indicators_by_id"] = dict(_TEST_INDICATORS)
    indexes["negative_indicators_by_id"] = dict(_TEST_NEGATIVES)
    indexes["overrides_by_id"] = dict(_TEST_OVERRIDES)
    return RuntimeKnowledge.build({}, indexes)


def _res(rule_id, *, state="MATCHED", severity="CRITICAL", verdict="SUPPORTED",
         positives=("SYN_STRONG_A", "SYN_STRONG_B"), classes=None, overrides=(),
         extraction=None, context_only=(), required=None, ambiguities=(), unknowns=(),
         provenance=None, extra=None):
    """A schema-valid WP4-shaped per-rule result dict carrying WP3 `live_positive_provenance` groups."""
    positives = list(positives)
    classes = list(classes) if classes is not None else sorted({_TEST_INDICATORS[p]["evidence_class"] for p in positives})
    extraction = extraction or {p: "HIGH" for p in positives}
    r = {
        "rule_id": rule_id, "rule_version": "1.0.0", "kind": "COMPOSITE",
        "evaluation_state": state,
        "required_combination_result": required or ("TRUE" if state in ("MATCHED", "SUPPRESSED") else ("FALSE" if state == "NOT_MATCHED" else "UNKNOWN")),
        "rule_evidence_verdict": verdict,
        "rule_severity_declared": severity,
    }
    if state in ("MATCHED", "SUPPRESSED", "NOT_MATCHED"):
        r["effective_severity"] = severity
    if positives and state != "NOT_APPLICABLE":
        r["matched_positive_indicators"] = positives
        r["evidence_classes_spanned"] = classes
        r["extraction_confidence_inputs"] = extraction
        prov = provenance if provenance is not None else {p: [[f"{rule_id}-{p}"]] for p in positives}
        prov = {k: v for k, v in prov.items() if k in positives}
        if prov:
            r["live_positive_provenance"] = prov
    if overrides:
        r["active_overrides"] = list(overrides)
    if context_only:
        r["suppression"] = {"effect": "CONTEXT_ONLY", "context_only_present": list(context_only)}
    if state == "SUPPRESSED":
        r["suppression"] = {"effect": "SUPPRESS_RULE", "applied_suppressors": ["SYN_SUPPRESSOR"], "suppressed_by": "SYN_SUPPRESSOR"}
    if ambiguities:
        r["ambiguities"] = list(ambiguities)
    if unknowns:
        r["unknowns"] = list(unknowns)
    if extra:
        r.update(extra)
    return r


def _decide(results, *, support="SUPPORTED", rk=None, whole_errors=()):
    return aggregate_decision(results, input_support_status=support, rk=rk or _synthetic_rk(),
                              whole_evaluation_errors=whole_errors)


# ================================================================ SYNTHETIC tests

def check_governing_and_severity(c: Check) -> None:
    rk = _synthetic_rk()
    d = _decide([_res("TL-AAA-001", severity="HIGH"), _res("TL-BBB-002", severity="CRITICAL"),
                 _res("TL-CCC-003", severity="MEDIUM")], rk=rk)
    c.eq(d.governing_rule_id, "TL-BBB-002", "governing: highest effective severity governs")
    c.eq(d.decision_severity, "CRITICAL", "severity: max, never a sum")

    d = _decide([_res("TL-ZZZ-009", severity="CRITICAL", verdict="PARTIAL"),
                 _res("TL-AAA-001", severity="CRITICAL", verdict="SUPPORTED")], rk=rk)
    c.eq(d.governing_rule_id, "TL-AAA-001", "governing: SUPPORTED beats PARTIAL at equal severity")

    d = _decide([_res("TL-BBB-002", severity="CRITICAL", positives=("SYN_STRONG_A", "SYN_STRONG_B")),
                 _res("TL-AAA-001", severity="CRITICAL", positives=("SYN_STRONG_A", "SYN_STRONG_B", "SYN_STRONG_C"))], rk=rk)
    c.eq(d.governing_rule_id, "TL-AAA-001", "governing: more evidence classes wins the verdict tie")

    d = _decide([_res("TL-BBB-002", severity="CRITICAL"), _res("TL-AAA-001", severity="CRITICAL")], rk=rk)
    c.eq(d.governing_rule_id, "TL-AAA-001", "governing: lexical rule id final tie-break")

    d = _decide([_res("TL-SUP-001", state="SUPPRESSED", severity="CRITICAL"),
                 _res("TL-MAT-002", state="MATCHED", severity="HIGH")], rk=rk)
    c.eq(d.governing_rule_id, "TL-MAT-002", "governing: SUPPRESSED CRITICAL never governs")
    c.eq(d.decision_severity, "HIGH", "severity: from the surviving MATCHED rule")


def check_strength_and_risk(c: Check) -> None:
    rk = _synthetic_rk()
    d = _decide([_res("TL-AAA-001", severity="HIGH", verdict="PARTIAL", positives=("SYN_STRONG_A", "SYN_STRONG_B"))], rk=rk)
    c.eq(d.matched_evidence_strength, "MODERATE", "strength: PARTIAL caps STRONG to MODERATE")
    d = _decide([_res("TL-AAA-001", severity="HIGH", verdict="SUPPORTED", positives=("SYN_WEAK_A", "SYN_MOD_A"))], rk=rk)
    c.eq(d.matched_evidence_strength, "MODERATE", "strength: SUPPORTED but max decisive MODERATE -> MODERATE")
    d = _decide([_res("TL-AAA-001", severity="HIGH", verdict="PARTIAL", positives=("SYN_WEAK_A", "SYN_MOD_A"), overrides=("HR_X",))], rk=rk)
    c.eq(d.matched_evidence_strength, "MODERATE", "strength: override raises the MODERATE floor")

    strength_positives = {"WEAK": ("SYN_WEAK_A", "SYN_WEAK_A"), "MODERATE": ("SYN_MOD_A", "SYN_WEAK_A"), "STRONG": ("SYN_STRONG_A", "SYN_STRONG_B")}
    verdict_for = {"WEAK": "HEURISTIC", "MODERATE": "PARTIAL", "STRONG": "SUPPORTED"}
    for sev in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        for strength in ("WEAK", "MODERATE", "STRONG"):
            d = _decide([_res("TL-AAA-001", severity=sev, verdict=verdict_for[strength],
                              positives=strength_positives[strength], classes=["PRETEXT", "PAYMENT_ACTION"])], rk=rk)
            c.eq(d.matched_evidence_strength, strength, f"row-matrix: strength for verdict {verdict_for[strength]}")
            c.eq(d.risk_level, RISK_MATRIX[sev][strength], f"row-matrix: risk cell M[{sev}][{strength}]")

    spec = importlib.util.spec_from_file_location("_det_design", DESIGN_VALIDATOR)
    det = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(det)
    c.eq(RISK_MATRIX, det.RISK_MATRIX, "drift: runtime RISK_MATRIX identical to the DET-001 design-gate matrix")


def _p3():
    return {"SYN_STRONG_A": [["oa"]], "SYN_STRONG_B": [["ob"]], "SYN_STRONG_C": [["oc"]]}


def check_confidence_boundaries(c: Check) -> None:
    rk = _synthetic_rk()
    pos3 = ("SYN_STRONG_A", "SYN_STRONG_B", "SYN_STRONG_C")

    d = _decide([_res("TL-AAA-001", severity="CRITICAL", verdict="SUPPORTED", positives=pos3, provenance=_p3())], rk=rk)
    c.eq(d.detection_confidence, "HIGH", "conf: SUPPORTED + 3 proven-independent + decisive HIGH -> HIGH")

    d = _decide([_res("TL-AAA-001", severity="CRITICAL", verdict="SUPPORTED",
                      positives=("SYN_STRONG_A", "SYN_STRONG_B"), overrides=("HR_X",))], rk=rk)
    c.eq(d.detection_confidence, "HIGH", "conf: SUPPORTED + override + decisive HIGH -> HIGH (2 classes)")

    d = _decide([_res("TL-AAA-001", severity="CRITICAL", verdict="SUPPORTED", positives=("SYN_STRONG_A", "SYN_STRONG_B"))], rk=rk)
    c.eq(d.detection_confidence, "MEDIUM", "conf: SUPPORTED + only 2 proven + no override -> MEDIUM")

    d = _decide([_res("TL-AAA-001", severity="CRITICAL", verdict="SUPPORTED", positives=pos3, provenance=_p3(),
                      extraction={"SYN_STRONG_A": "LOW", "SYN_STRONG_B": "HIGH", "SYN_STRONG_C": "HIGH"})], rk=rk)
    c.eq(d.detection_confidence, "MEDIUM", "conf: a decisive LOW extraction blocks HIGH -> MEDIUM")

    d = _decide([_res("TL-AAA-001", severity="HIGH", verdict="SUPPORTED", positives=pos3, provenance=_p3(),
                      extraction={"SYN_STRONG_A": "MEDIUM", "SYN_STRONG_B": "HIGH", "SYN_STRONG_C": "HIGH"})], rk=rk)
    c.eq(d.detection_confidence, "HIGH", "conf: min MEDIUM extraction + 3 proven + SUPPORTED -> HIGH (GDC-10 path)")

    d = _decide([_res("TL-AAA-001", severity="HIGH", verdict="PARTIAL", positives=pos3, provenance=_p3())], rk=rk)
    c.eq(d.detection_confidence, "MEDIUM", "conf: PARTIAL caps confidence at MEDIUM")

    d = _decide([_res("TL-AAA-001", severity="HIGH", verdict="HEURISTIC", positives=pos3, provenance=_p3())], rk=rk)
    c.eq(d.detection_confidence, "LOW", "conf: HEURISTIC -> LOW")
    c.eq(d.classification, "SCAM_PATTERN_SUSPECTED", "class: LOW confidence with a fired rule -> SUSPECTED")

    d = _decide([_res("TL-AAA-001", severity="CRITICAL", verdict="SUPPORTED",
                      positives=("SYN_STRONG_A", "SYN_STRONG_B"), context_only=("BENIGN_CTX",))], rk=rk)
    c.eq(d.detection_confidence, "LOW", "conf: active benign CONTEXT_ONLY nudges a non-HIGH decision to LOW")


def check_proven_independence(c: Check) -> None:
    """Union-find components; the SAME quantity drives band and the >=3 confidence path."""
    rk = _synthetic_rk()
    pos3 = ("SYN_STRONG_A", "SYN_STRONG_B", "SYN_STRONG_C")

    def consistent(dec, want_count, where):
        corr = dec.corroboration
        c.eq(corr["evidence_class_count"], want_count, f"{where}: count")
        c.eq(len(corr["independent_evidence_classes"]), want_count, f"{where}: len(independent_evidence_classes) == count")

    # 14. 3 classes / same single live occurrence -> count 1 ; list length 1
    one = {p: [["one"]] for p in pos3}
    d = _decide([_res("TL-AAA-001", severity="CRITICAL", verdict="SUPPORTED", positives=pos3, provenance=one)], rk=rk)
    consistent(d, 1, "prov: 3 classes / one component")
    c.eq(d.detection_confidence, "MEDIUM", "prov: 3 classes / one occurrence -> not HIGH")

    # 15. 3 classes / same MULTI-ref live occurrence -> count 1 (grouped occurrence)
    multi = {p: [["ra", "rb"]] for p in pos3}
    d = _decide([_res("TL-AAA-001", severity="CRITICAL", verdict="SUPPORTED", positives=pos3, provenance=multi)], rk=rk)
    c.eq(d.corroboration["evidence_class_count"], 1, "prov: 3 classes / one shared multi-ref occurrence -> count 1")

    # 16. overlapping groups [A,B] and [B,C] -> one component
    overlap = {"SYN_STRONG_A": [["ra", "rb"]], "SYN_STRONG_B": [["rb", "rc"]]}
    d = _decide([_res("TL-AAA-001", severity="CRITICAL", verdict="SUPPORTED",
                      positives=("SYN_STRONG_A", "SYN_STRONG_B"), provenance=overlap)], rk=rk)
    c.eq(d.corroboration["evidence_class_count"], 1, "prov: overlapping groups [A,B],[B,C] -> one component")

    # 17. 3 classes / 2 components -> count 2, list length 2, not HIGH
    two = {"SYN_STRONG_A": [["o1"]], "SYN_STRONG_B": [["o1"]], "SYN_STRONG_C": [["o2"]]}
    d = _decide([_res("TL-AAA-001", severity="CRITICAL", verdict="SUPPORTED", positives=pos3, provenance=two)], rk=rk)
    consistent(d, 2, "prov: 3 classes / 2 components")
    c.eq(d.detection_confidence, "MEDIUM", "prov: 2 components -> not HIGH")

    # 18. 3 classes / 3 separate live components -> count 3, list length 3
    d = _decide([_res("TL-AAA-001", severity="CRITICAL", verdict="SUPPORTED", positives=pos3, provenance=_p3())], rk=rk)
    consistent(d, 3, "prov: 3 separate components")
    c.eq(d.corroboration["band"], "HIGH", "prov: 3 components -> band HIGH")

    # shuffled class/component ordering -> identical selected class list (deterministic)
    shuffle_two = {"SYN_STRONG_C": [["o2"]], "SYN_STRONG_A": [["o1"]], "SYN_STRONG_B": [["o1"]]}
    d_a = _decide([_res("TL-AAA-001", severity="CRITICAL", verdict="SUPPORTED",
                        positives=("SYN_STRONG_A", "SYN_STRONG_B", "SYN_STRONG_C"), provenance=two)], rk=rk)
    d_b = _decide([_res("TL-AAA-001", severity="CRITICAL", verdict="SUPPORTED",
                        positives=("SYN_STRONG_C", "SYN_STRONG_B", "SYN_STRONG_A"), provenance=shuffle_two)], rk=rk)
    c.eq(d_a.corroboration["independent_evidence_classes"], d_b.corroboration["independent_evidence_classes"],
         "prov: shuffled class/component ordering -> identical selected class list")

    # 20. missing provenance -> zero independence
    d = _decide([_res("TL-AAA-001", severity="CRITICAL", verdict="SUPPORTED", positives=pos3, provenance={})], rk=rk)
    c.eq(d.corroboration["evidence_class_count"], 0, "prov: missing provenance -> zero independence")
    c.eq(d.detection_confidence, "MEDIUM", "prov: missing provenance -> not HIGH")

    # 21. duplicate occurrence groups / duplicate refs are schema-PROHIBITED (uniqueItems) -> cannot inflate
    c.raises(lambda: _decide([_res("TL-AAA-001", severity="CRITICAL", verdict="SUPPORTED",
                                   positives=("SYN_STRONG_A", "SYN_STRONG_B"),
                                   provenance={"SYN_STRONG_A": [["oa"], ["oa"]], "SYN_STRONG_B": [["ob"]]})], rk=rk),
             "prov: duplicate occurrence groups are schema-rejected (cannot inflate)")
    c.raises(lambda: _decide([_res("TL-AAA-001", severity="CRITICAL", verdict="SUPPORTED",
                                   positives=("SYN_STRONG_A", "SYN_STRONG_B"),
                                   provenance={"SYN_STRONG_A": [["oa", "oa"]], "SYN_STRONG_B": [["ob"]]})], rk=rk),
             "prov: duplicate refs within a group are schema-rejected")

    # replay the previous failing scenario: 3 TRUE from ONE shared live occurrence (WP3 already excluded the
    # unique reported occurrences), so proven == 1, not HIGH via corroboration.
    shared_live = {p: [["shared-live"]] for p in pos3}
    d = _decide([_res("TL-AAA-001", severity="CRITICAL", verdict="SUPPORTED", positives=pos3, provenance=shared_live)], rk=rk)
    c.eq(d.corroboration["evidence_class_count"], 1, "prov: 3 TRUE from one shared live occurrence -> count 1")
    c.eq(d.detection_confidence, "MEDIUM", "prov: shared-live 3-class -> not HIGH via corroboration")


def check_unresolved_harm_and_benign(c: Check) -> None:
    rk = _synthetic_rk()
    harm = _res("TL-IND-001", state="INDETERMINATE", severity="CRITICAL", positives=("SYN_STRONG_A",),
                ambiguities=["payment_direction unresolved"])
    benign = _res("TL-NEG-002", state="NOT_MATCHED", severity="HIGH", positives=(),
                  extra={"matched_negative_indicators": ["SOME_NEG"]})
    c.eq(_decide([harm, benign], rk=rk).classification, "INSUFFICIENT_EVIDENCE",
         "harm>benign: unrelated benign negative cannot clear unresolved harm")

    harm_unk = _res("TL-IND-001", state="INDETERMINATE", severity="CRITICAL", positives=("SYN_STRONG_A",),
                    unknowns=["OPERAND: decisive operand UNKNOWN (low_confidence)"])
    c.eq(_decide([harm_unk], rk=rk).classification, "INSUFFICIENT_EVIDENCE",
         "unresolved: relevant unknown without ambiguity blocks benign")

    sparse = _res("TL-IND-003", state="INDETERMINATE", severity="CRITICAL", positives=("SYN_STRONG_A",))
    clear = _res("TL-CLR-004", state="NOT_MATCHED", severity="HIGH", positives=())
    c.eq(_decide([sparse, clear], rk=rk).classification, "NO_SCAM_PATTERN",
         "inert: sparse INDETERMINATE with a matched positive does not block a benign clear")

    # diversity-fail NOT_MATCHED+TRUE is NOT a benign clear
    divfail = _res("TL-NMT-005", state="NOT_MATCHED", severity="HIGH", positives=("SYN_STRONG_A",), required="TRUE")
    c.eq(_decide([divfail], rk=rk).classification, "INSUFFICIENT_EVIDENCE",
         "benign: a diversity-fail NOT_MATCHED+TRUE does not clear")

    c.eq(_decide([_res("TL-CLR-006", state="NOT_MATCHED", severity="HIGH", positives=())], rk=rk).classification,
         "NO_SCAM_PATTERN", "benign: NOT_MATCHED+FALSE clears")
    c.eq(_decide([_res("TL-SUP-007", state="SUPPRESSED", severity="CRITICAL")], rk=rk).classification,
         "NO_SCAM_PATTERN", "benign: SUPPRESSED clears")

    ctx = _res("TL-IND-008", state="INDETERMINATE", severity="HIGH", positives=("SYN_STRONG_A",), context_only=("LOW_AMOUNT",))
    c.ok(_decide([ctx], rk=rk).classification != "NO_SCAM_PATTERN", "benign: CONTEXT_ONLY alone never clears")

    bare = _res("TL-IND-009", state="INDETERMINATE", severity="HIGH", positives=(),
                extra={"matched_negative_indicators": ["SUPPORT_NEVER_ASKS"]})
    c.eq(_decide([bare], rk=rk).classification, "INSUFFICIENT_EVIDENCE",
         "benign: a bare negative id without FALSE/SUPPRESSED does not clear")


def check_states_support_and_degraded(c: Check) -> None:
    rk = _synthetic_rk()
    d = _decide([_res("TL-MAT-001", state="MATCHED", severity="CRITICAL"),
                 _res("TL-IND-002", state="INDETERMINATE", severity="HIGH", positives=("SYN_STRONG_A",))], rk=rk)
    c.eq(d.governing_rule_id, "TL-MAT-001", "states: MATCHED governs over a co-present INDETERMINATE")
    c.eq(d.classification, "SCAM_PATTERN_DETECTED", "states: MATCHED + INDETERMINATE is a detection")

    for support, want in (("UNSUPPORTED", "UNSUPPORTED"), ("ERROR", "ERROR"), ("INSUFFICIENT_INFORMATION", "INSUFFICIENT_EVIDENCE")):
        d = _decide([], support=support, rk=rk)
        c.eq(d.classification, want, f"support {support} -> {want}")
        c.eq(d.decision_severity, "NONE", f"support {support} -> severity NONE")

    d = _decide([_res("TL-MAT-001", state="MATCHED", severity="CRITICAL", overrides=("HR_X",))], rk=rk,
                whole_errors=[{"scope": "WHOLE_EVALUATION", "stage": "BUNDLE_INTEGRITY", "code": "DIGEST_MISMATCH", "message": "bad"}])
    c.eq(d.classification, "ERROR", "whole-error: forces classification ERROR")
    c.eq(d.decision_severity, "NONE", "whole-error: no decision severity")
    c.eq(d.detection_confidence, "NOT_APPLICABLE", "whole-error: no confidence")

    degraded = {"rule_id": "TL-ERR-009", "rule_version": "1.0.0", "kind": "COMPOSITE", "evaluation_state": "NOT_APPLICABLE",
                "required_combination_result": "UNKNOWN", "evaluation_error": {"code": "RULE_EVALUATION_ERROR", "message": "boom"}}
    d = _decide([_res("TL-MAT-001", state="MATCHED", severity="CRITICAL", verdict="SUPPORTED", overrides=("HR_X",)), degraded], rk=rk)
    c.ok(d.degraded is True, "degraded: flag set on a per-rule error")
    c.eq(d.detection_confidence, "MEDIUM", "degraded: a would-be-HIGH MATCHED is capped to MEDIUM")
    c.eq(d.classification, "SCAM_PATTERN_DETECTED", "degraded: MATCHED remains a detection")


def check_fail_closed(c: Check) -> None:
    rk = _synthetic_rk()
    c.raises(lambda: _decide([_res("TL-AAA-001"), _res("TL-AAA-001")], rk=rk), "fail-closed: duplicate rule_id")
    c.raises(lambda: _decide([{"rule_id": "TL-AAA-001", "rule_version": "1.0.0", "kind": "COMPOSITE",
                               "evaluation_state": "MATCHED", "required_combination_result": "UNKNOWN"}], rk=rk),
             "fail-closed: MATCHED without required=TRUE")
    c.raises(lambda: _decide([_res("TL-AAA-001", state="INDETERMINATE", required="FALSE")], rk=rk),
             "fail-closed: INDETERMINATE without UNKNOWN")
    c.raises(lambda: _decide([_res("TL-AAA-001", extra={"effective_severity": "BOGUS"})], rk=rk),
             "fail-closed: invalid effective_severity (schema)")
    c.raises(lambda: _decide([_res("TL-AAA-001", verdict="BOGUS")], rk=rk), "fail-closed: invalid verdict (schema)")
    # MATCHED + evaluation_error -> AggregationError
    c.raises(lambda: _decide([_res("TL-AAA-001", extra={"evaluation_error": {"code": "X", "message": "y"}})], rk=rk),
             "fail-closed: evaluation_error on a MATCHED result")
    c.raises(lambda: _decide([{"rule_id": "TL-AAA-001", "rule_version": "1.0.0", "kind": "COMPOSITE",
                               "evaluation_state": "NOT_APPLICABLE", "required_combination_result": "UNKNOWN",
                               "evaluation_error": {"code": "X"}}], rk=rk),
             "fail-closed: malformed evaluation_error (missing message, schema)")
    c.raises(lambda: _decide([{"not": "a valid result"}], rk=rk), "fail-closed: schema-invalid WP4 result")
    c.raises(lambda: aggregate_decision([], input_support_status="NONSENSE", rk=rk), "fail-closed: unknown support status")
    c.raises(lambda: _decide([_res("TL-AAA-001", positives=("NOT_IN_RK", "SYN_STRONG_B"), classes=["PRETEXT", "PAYMENT_ACTION"],
                                   provenance={"SYN_STRONG_B": [["rr"]]})], rk=rk),
             "fail-closed: unresolved positive indicator")
    c.raises(lambda: _decide([_res("TL-AAA-001", extra={"matched_negative_indicators": ["NOT_A_NEG"]})], rk=rk),
             "fail-closed: unresolved negative indicator")
    c.raises(lambda: _decide([_res("TL-AAA-001", overrides=("HR_UNRESOLVED",))], rk=rk),
             "fail-closed: unresolved active override")
    c.raises(lambda: _decide([_res("TL-AAA-001", extra={"live_positive_provenance": {"SYN_STRONG_C": [["rr"]]}})], rk=rk),
             "fail-closed: provenance key not in matched_positive_indicators")
    c.raises(lambda: _decide([_res("TL-AAA-001", provenance={"SYN_STRONG_A": [[]], "SYN_STRONG_B": [["r"]]})], rk=rk),
             "fail-closed: empty provenance group (schema)")
    c.raises(lambda: _decide([_res("TL-AAA-001", extra={"governing": True})], rk=rk),
             "fail-closed: pre-populated WP5 field rejected")
    c.raises(lambda: aggregate_decision([], input_support_status="SUPPORTED", rk=rk,
                                        whole_evaluation_errors=[{"scope": "WHOLE_EVALUATION"}]),
             "fail-closed: malformed whole_evaluation_errors (missing code/message)")

    # diversity-fail NOT_MATCHED+TRUE is ACCEPTED (not an error)
    try:
        _decide([_res("TL-DIV-010", state="NOT_MATCHED", severity="HIGH", positives=("SYN_STRONG_A",), required="TRUE")], rk=rk)
        accepted = True
    except AggregationError:
        accepted = False
    c.ok(accepted, "accepted: NOT_MATCHED + required=TRUE (diversity gate) is a legal WP3 result")

    # a malformed MATCHED must never serialise as NO_SCAM_PATTERN
    try:
        _decide([_res("TL-AAA-001", verdict="BOGUS")], rk=rk)
        emitted = "NO_SCAM_PATTERN"
    except AggregationError:
        emitted = None
    c.ok(emitted is None, "fail-closed: a malformed MATCHED never serialises as NO_SCAM_PATTERN")


def check_determinism(c: Check) -> None:
    rk = _synthetic_rk()
    e1 = {"rule_id": "TL-ERR-001", "rule_version": "1.0.0", "kind": "COMPOSITE", "evaluation_state": "NOT_APPLICABLE",
          "required_combination_result": "UNKNOWN", "evaluation_error": {"code": "A_ERR", "message": "a"}}
    e2 = {"rule_id": "TL-ERR-002", "rule_version": "1.0.0", "kind": "COMPOSITE", "evaluation_state": "NOT_APPLICABLE",
          "required_combination_result": "UNKNOWN", "evaluation_error": {"code": "B_ERR", "message": "b"}}
    c.eq(_decide([e1, e2], rk=rk).as_decision_dict(), _decide([e2, e1], rk=rk).as_decision_dict(),
         "determinism: error-array permutation -> identical")

    s1 = _res("TL-SUP-001", state="SUPPRESSED", severity="CRITICAL")
    s1["suppression"] = {"effect": "SUPPRESS_RULE", "applied_suppressors": ["A_SUP", "B_SUP"], "suppressed_by": "A_SUP"}
    s2 = _res("TL-SUP-001", state="SUPPRESSED", severity="CRITICAL")
    s2["suppression"] = {"effect": "SUPPRESS_RULE", "applied_suppressors": ["B_SUP", "A_SUP"], "suppressed_by": "A_SUP"}
    c.eq(_decide([s1], rk=rk).as_decision_dict(), _decide([s2], rk=rk).as_decision_dict(),
         "determinism: nested suppression permutation -> identical")

    # grouped-provenance permutation -> identical
    g1 = _res("TL-AAA-001", severity="CRITICAL", positives=("SYN_STRONG_A", "SYN_STRONG_B"),
              provenance={"SYN_STRONG_A": [["ry", "rx"]], "SYN_STRONG_B": [["ob"]]})
    g2 = _res("TL-AAA-001", severity="CRITICAL", positives=("SYN_STRONG_A", "SYN_STRONG_B"),
              provenance={"SYN_STRONG_B": [["ob"]], "SYN_STRONG_A": [["rx", "ry"]]})
    c.eq(_decide([g1], rk=rk).as_decision_dict(), _decide([g2], rk=rk).as_decision_dict(),
         "determinism: grouped-provenance permutation -> identical")


def check_schema_conformance(c: Check, rk) -> None:
    schema = json.loads(RESULT_SCHEMA.read_text())
    rev = json.loads(RULE_EVAL_SCHEMA.read_text())
    Draft202012Validator.check_schema(schema)
    registry = Registry().with_resources([(schema["$id"], Resource.from_contents(schema)), (rev["$id"], Resource.from_contents(rev))])
    validator = Draft202012Validator(schema, registry=registry)

    golden = json.loads(GOLDEN.read_text())
    case = next(x for x in golden["cases"] if x["id"] == "GDC-01")
    d = aggregate_decision(_wp4_results_for_case(rk, case), input_support_status="SUPPORTED", rk=rk)
    dd = d.as_decision_dict()

    doc = {
        "result_contract_version": "1.1.0", "evaluation_id": "eval-wp5-test",
        "evaluation_timestamp": "2026-09-02T00:00:00Z", "input_id": "IN-WP5",
        "language": ["en"], "script": ["Latn"],
        "input_support_status": dd["input_support_status"], "classification": dd["classification"],
        "risk_level": dd["risk_level"], "decision_severity": dd["decision_severity"],
        "matched_evidence_strength": dd["matched_evidence_strength"], "detection_confidence": dd["detection_confidence"],
        "corroboration_summary": dd["corroboration_summary"], "matched_rules": dd["matched_rules"],
        "matched_positive_indicators": dd["matched_positive_indicators"],
        "matched_negative_indicators": dd["matched_negative_indicators"],
        "suppressed_indicators": dd["suppressed_indicators"], "active_overrides": dd["active_overrides"],
        "rule_results": dd["rule_results"], "degraded": dd["degraded"],
        "provenance": {
            "bundle_version": rk.bundle_version, "bundle_content_digest": rk.content_digest, "engine_version": "0.5.0",
            "evaluation_profile": {"profile_id": "profile-v1", "extraction_confidence_gate": "MEDIUM",
                                   "risk_matrix_id": "risk-matrix-v1", "confidence_policy_id": "confidence-policy-v1"},
            "component_versions": {"rule_schema": "1.0.0", "indicator_registry": "0.3.0-interim",
                                   "indicator_families": "1.0.0", "negative_library": "2.0.0",
                                   "taxonomy": "1.0.0", "dimensions": "1.0.0", "extraction_contracts": "1.0.0"},
        },
        "explanation": {"summary": "", "what_was_detected": "", "why": "", "detection_confidence_reason": ""},
        "recommended_actions": [],
    }
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    c.ok(not errors, "schema: assembled WP5 decision validates against detection-result.schema.json"
         + ("" if not errors else f" — first: {errors[0].message} at /{'/'.join(map(str, errors[0].path))}"))
    _scan_no_forbidden(c, dd, "schema-doc")


def main() -> int:
    quiet = "--quiet" in sys.argv

    def log(*a):
        if not quiet:
            print(*a)

    tmp = Path(tempfile.mkdtemp(prefix="wp5-agg-"))
    bundle = tmp / "bundle"
    build_bundle.build(bundle)
    rk = load_bundle(bundle)

    log(f"P3-WP5 decision-aggregation validation — bundle {rk.bundle_version} ({len(rk.published_rule_ids())} PUBLISHED rules)")
    log("  REAL GOVERNED BUNDLE: 15 golden decision cases replayed WP3->WP4->WP5 (WP3 live_positive_provenance)")
    log("  SYNTHETIC ENGINE-CAPABILITY: governing/severity, strength, risk cells, proven-independence "
        "(union-find components), confidence, unresolved-harm/benign, states/degraded/whole-error, fail-closed, determinism")

    c = Check()
    matrix = check_golden(c, rk)
    check_governing_and_severity(c)
    check_strength_and_risk(c)
    check_confidence_boundaries(c)
    check_proven_independence(c)
    check_unresolved_harm_and_benign(c)
    check_states_support_and_degraded(c)
    check_fail_closed(c)
    check_determinism(c)
    check_schema_conformance(c, rk)

    if not quiet:
        print("\n  golden decision matrix (cid | support | classification | risk | confidence | live_publishable):")
        for cid, support, cls, risk, conf, live in matrix:
            print(f"    {cid:<7} {support:<22} {cls:<22} {risk:<9} {conf:<15} live={live}")

    print(f"\n{c.count - len(c.failures)}/{c.count} assertions passed.")
    if c.failures:
        print(f"P3-WP5 AGGREGATION: FAIL — {len(c.failures)} assertion(s) failed:")
        for f in c.failures:
            print(f"  - {f}")
        return 1
    print("P3-WP5 AGGREGATION: PASS — proven-independent corroboration from authoritative WP3 live provenance "
          "(union-find components), ADR-0006 risk/strength, categorical confidence (degraded-capped), rule-local "
          "unresolved-harm + strict benign clear, full semantic-validation fail-closed input and determinism, "
          "all consistent with DET-001 + the 15 golden cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
