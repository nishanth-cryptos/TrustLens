"""TrustLens Phase 3 DET-001 design-gate validator.

Checks the INTERNAL CONSISTENCY of the DET-001 design against the live Phase-2 knowledge base.
It is a DESIGN validator, not a detection engine: it does not evaluate rules over inputs. It proves
that the design contracts and the golden decision cases are coherent, reference only real knowledge,
and obey the ADR-0006 risk model and the classification/severity rules stated in DET-001.

Wired into knowledge/validation/run_all.py as the **10th canonical check** at the Phase-3 closure
(GATE-009): the canonical quality gate now proves the existing 9 checks plus the Phase-3 design
contracts and golden decision cases. It remains independently runnable. It is offline (no network or
subprocess imports), so it passes run_all.py's offline preflight.

Checks:
  1. Both design schemas (detection-result, rule-evaluation-result) are valid Draft 2020-12.
  2. Two synthetic detection-result examples validate against detection-result.schema.json (the $ref to
     rule-evaluation-result resolves) — proves the output contract is usable.
  3. Every golden decision case:
       - fired rule ids resolve to real rule files; severity/verdict/status read from them;
       - declared indicator ids resolve to the positive registry or the negative library;
       - active overrides resolve to the negative library;
       - risk_level == RISK_MATRIX[severity][matched_evidence_strength] (ADR-0006);
       - classification is consistent with input_support_status, fired rules and detection_confidence;
       - decision severity == max effective severity (min(declared, PARTIAL cap)) over fired rules;
       - recommended actions are in the controlled vocabulary;
       - live_publishable == (all fired rules are PUBLISHED) for supported detections.
  Offline by construction. Exit 0 iff every check passes.

Usage:  .venv/bin/python docs/03-detection/validate_det_design.py [--quiet]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2]
DET_DIR = ROOT / "docs" / "03-detection"
CONTRACTS = DET_DIR / "contracts"
DETECTION_RESULT_SCHEMA = CONTRACTS / "detection-result.schema.json"
RULE_EVAL_SCHEMA = CONTRACTS / "rule-evaluation-result.schema.json"
GOLDEN = DET_DIR / "golden-decision-cases-v1.json"

RULES_DIR = ROOT / "knowledge" / "rules"
REGISTRY_PATH = ROOT / "knowledge" / "indicators" / "indicator-registry-v0.json"
NEG_LIBRARY_PATH = ROOT / "knowledge" / "indicators" / "negative-indicator-library-v1.json"

SEV_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

# ADR-0006 risk matrix v1: risk_level = f(severity, matched_evidence_strength). Ordinal, not a probability.
RISK_MATRIX = {
    "NONE": {"NONE": "NONE"},
    "LOW": {"WEAK": "LOW", "MODERATE": "LOW", "STRONG": "MEDIUM"},
    "MEDIUM": {"WEAK": "LOW", "MODERATE": "MEDIUM", "STRONG": "MEDIUM"},
    "HIGH": {"WEAK": "MEDIUM", "MODERATE": "HIGH", "STRONG": "HIGH"},
    "CRITICAL": {"WEAK": "HIGH", "MODERATE": "HIGH", "STRONG": "CRITICAL"},
}

ACTION_VOCAB = {
    "DO_NOT_SHARE_CREDENTIALS", "DO_NOT_ENTER_PIN", "DO_NOT_TRANSFER_MONEY", "DO_NOT_INSTALL_APP",
    "DO_NOT_CONNECT_WALLET", "DO_NOT_DIAL_CODE", "DISCONNECT_REMOTE_ACCESS", "VERIFY_INDEPENDENTLY",
    "CONTACT_BANK", "CONTACT_OFFICIAL_CHANNEL", "REPORT_CYBERCRIME", "PRESERVE_EVIDENCE",
    "PROCEED_WITH_CAUTION", "SEEK_HUMAN_REVIEW", "RESUBMIT_IN_SUPPORTED_LANGUAGE",
}


def load(p):
    return json.loads(Path(p).read_text())


def effective_severity(declared, cap):
    if declared is None:
        return None
    if cap and SEV_ORDER.index(cap) < SEV_ORDER.index(declared):
        return cap
    return declared


def max_severity(sevs):
    live = [s for s in sevs if s]
    if not live:
        return "NONE"
    return max(live, key=SEV_ORDER.index)


# --- synthetic detection-result examples (contract usability proof) ---------
def synthetic_examples():
    base_prov = {
        "bundle_version": "1.0.0",
        "bundle_content_digest": "0" * 64,
        "engine_version": "0.0.0-design",
        "evaluation_profile": {
            "profile_id": "mvp-default",
            "extraction_confidence_gate": "MEDIUM",
            "risk_matrix_id": "adr-0006-risk-matrix-v1",
            "confidence_policy_id": "adr-0006-confidence-policy-v1",
        },
        "component_versions": {"rule_schema": "1.0.0"},
    }
    detected = {
        "result_schema_version": "1.0.0-design",
        "evaluation_id": "EVAL-EXAMPLE-DETECTED",
        "timestamp": "2026-08-29T00:00:00Z",
        "input_id": "IN-EX-1",
        "language": ["en"], "script": ["Latn"],
        "input_support_status": "SUPPORTED",
        "classification": "SCAM_PATTERN_DETECTED",
        "severity": "CRITICAL", "matched_evidence_strength": "STRONG",
        "risk_level": "CRITICAL", "detection_confidence": "HIGH",
        "provenance": base_prov,
        "rule_results": [{
            "rule_id": "TL-PAY-001", "rule_version": "1.0.0", "kind": "COMPOSITE",
            "evaluation_state": "MATCHED", "required_combination_result": "TRUE",
            "matched_positive_indicators": ["RECEIVE_FRAMING", "UPI_PIN_PROMPT"],
            "evidence_classes_spanned": ["PAYMENT_ACTION", "CREDENTIAL_ACTION"],
            "min_evidence_classes_required": 2, "evidence_class_diversity_met": True,
            "active_overrides": ["HR_UPI_PIN_TO_RECEIVE"],
            "rule_evidence_verdict": "SUPPORTED", "rule_severity_declared": "CRITICAL",
            "effective_severity": "CRITICAL", "rule_confidence": "HIGH",
        }],
        "explanation": {
            "what": "PIN entry demanded to receive money.",
            "why": "RECEIVE_FRAMING + UPI_PIN_PROMPT.",
            "detection_confidence_reason": "decisive indicators observed at high confidence; official categorical boundary.",
        },
        "recommended_actions": [{"action": "DO_NOT_ENTER_PIN", "justified_by": "TL-PAY-001"}],
    }
    insufficient = {
        "result_schema_version": "1.0.0-design",
        "evaluation_id": "EVAL-EXAMPLE-INSUFFICIENT",
        "timestamp": "2026-08-29T00:00:00Z",
        "input_id": "IN-EX-2",
        "language": ["en"], "script": ["Latn"],
        "input_support_status": "SUPPORTED",
        "classification": "INSUFFICIENT_EVIDENCE",
        "severity": "NONE", "matched_evidence_strength": "NONE",
        "risk_level": "NONE", "detection_confidence": "NOT_APPLICABLE",
        "provenance": base_prov,
        "rule_results": [{
            "rule_id": "TL-PAY-001", "rule_version": "1.0.0", "kind": "COMPOSITE",
            "evaluation_state": "INDETERMINATE", "required_combination_result": "UNKNOWN",
        }],
        "explanation": {
            "what": "A PIN prompt with unresolved payment direction.",
            "why": "RECEIVE_FRAMING is AMBIGUOUS; the combination is indeterminate.",
            "detection_confidence_reason": "no rule fired; uncertainty preserved.",
        },
        "recommended_actions": [{"action": "SEEK_HUMAN_REVIEW", "justified_by": "TL-PAY-001 INDETERMINATE"}],
        "ambiguities": ["payment_direction unresolved"],
    }
    return {"detected": detected, "insufficient": insufficient}


def main() -> int:
    quiet = "--quiet" in sys.argv
    problems = []

    def log(*a):
        if not quiet:
            print(*a)

    # ---- 1. schemas are valid Draft 2020-12
    det_schema = load(DETECTION_RESULT_SCHEMA)
    rule_schema = load(RULE_EVAL_SCHEMA)
    for name, sch in (("detection-result", det_schema), ("rule-evaluation-result", rule_schema)):
        try:
            Draft202012Validator.check_schema(sch)
        except Exception as e:  # noqa: BLE001
            problems.append(f"schema {name} is not valid Draft 2020-12: {e}")
    log("  ok    both design schemas are valid Draft 2020-12" if not problems else "  FAIL  schema validity")

    # ---- 2. synthetic examples validate against detection-result (with $ref resolved)
    registry = Registry().with_resources([
        (det_schema["$id"], Resource.from_contents(det_schema)),
        (rule_schema["$id"], Resource.from_contents(rule_schema)),
    ])
    dr_validator = Draft202012Validator(det_schema, registry=registry)
    for label, ex in synthetic_examples().items():
        errs = sorted(dr_validator.iter_errors(ex), key=lambda e: e.path)
        for e in errs:
            problems.append(f"synthetic example '{label}' violates detection-result schema: {e.message} at /{'/'.join(map(str, e.path))}")
    log(f"  ok    2 synthetic detection-result examples validate" if not any('synthetic' in p for p in problems) else "  FAIL  synthetic examples")

    # ---- load knowledge
    rules = {p.stem: load(p) for p in RULES_DIR.glob("*.json") if not p.name.startswith("_")}
    positives = {i["id"] for i in load(REGISTRY_PATH)["indicators"]}
    neg_lib = load(NEG_LIBRARY_PATH)
    negatives = {n["negative_indicator_id"] for n in neg_lib["negative_indicators"]}
    overrides = {o["override_id"] for o in neg_lib["overrides"]}
    known_indicators = positives | negatives

    # ---- 3. golden cases
    golden = load(GOLDEN)
    n_cases = len(golden["cases"])
    for c in golden["cases"]:
        cid = c["id"]
        exp = c["expected"]

        def fail(msg):
            problems.append(f"{cid}: {msg}")

        # declared indicators resolve
        for ind in c.get("declared_indicators", []):
            if ind["id"] not in known_indicators:
                fail(f"declared indicator {ind['id']} resolves to neither the positive registry nor the negative library")

        # overrides resolve
        for ov in exp.get("active_overrides", []):
            if ov not in overrides:
                fail(f"active override {ov} not in the negative-indicator library")
        for ov in exp.get("blocked_suppressors", []):
            if ov not in negatives:
                fail(f"blocked suppressor {ov} not in the negative-indicator library")

        # fired rules resolve; compute effective severities
        fired = exp.get("fired_rules", [])
        eff_sevs = []
        for rid in fired:
            if rid not in rules:
                fail(f"fired rule {rid} has no rule file")
                continue
            r = rules[rid]
            cap = r.get("evidence", {}).get("severity_cap")
            eff = effective_severity(r.get("severity"), cap)
            eff_sevs.append(eff)

        # severity == max effective over fired rules
        derived_sev = max_severity(eff_sevs)
        if exp["severity"] != derived_sev:
            fail(f"severity {exp['severity']} != max effective severity of fired rules {derived_sev} ({dict(zip(fired, eff_sevs))})")

        # risk matrix
        sev, strength = exp["severity"], exp["matched_evidence_strength"]
        expected_risk = RISK_MATRIX.get(sev, {}).get(strength)
        if expected_risk is None:
            fail(f"illegal (severity={sev}, strength={strength}) combination for the risk matrix")
        elif exp["risk_level"] != expected_risk:
            fail(f"risk_level {exp['risk_level']} != RISK_MATRIX[{sev}][{strength}] = {expected_risk}")

        # classification consistency
        support, cls, conf = exp["input_support_status"], exp["classification"], exp["detection_confidence"]
        if support == "UNSUPPORTED":
            if cls != "UNSUPPORTED" or fired or sev != "NONE" or conf != "NOT_APPLICABLE":
                fail("UNSUPPORTED input must yield classification UNSUPPORTED, no fired rules, severity NONE, confidence NOT_APPLICABLE")
        elif support == "ERROR":
            if cls != "ERROR":
                fail("ERROR support status must yield classification ERROR")
        elif support in ("SUPPORTED", "PARTIALLY_SUPPORTED"):
            if fired:
                if cls not in ("SCAM_PATTERN_DETECTED", "SCAM_PATTERN_SUSPECTED"):
                    fail(f"fired rules present but classification is {cls}")
                if conf == "LOW" and cls != "SCAM_PATTERN_SUSPECTED":
                    fail("LOW detection_confidence with a fired rule must be SCAM_PATTERN_SUSPECTED")
                if conf in ("MEDIUM", "HIGH") and cls != "SCAM_PATTERN_DETECTED":
                    fail(f"{conf} detection_confidence with a fired rule must be SCAM_PATTERN_DETECTED")
                if sev == "NONE":
                    fail("fired rules present but severity is NONE")
            else:
                if cls not in ("NO_SCAM_PATTERN", "INSUFFICIENT_EVIDENCE"):
                    fail(f"no fired rules but classification is {cls}")
                if sev != "NONE" or exp["risk_level"] != "NONE" or conf != "NOT_APPLICABLE":
                    fail("no fired rules must yield severity/risk NONE and confidence NOT_APPLICABLE")
        elif support == "INSUFFICIENT_INFORMATION":
            if cls != "INSUFFICIENT_EVIDENCE":
                fail("INSUFFICIENT_INFORMATION support must yield classification INSUFFICIENT_EVIDENCE")

        # recommended actions vocabulary
        for a in exp.get("recommended_actions", []):
            if a not in ACTION_VOCAB:
                fail(f"recommended action {a} is not in the controlled vocabulary")

        # live_publishable == all fired rules PUBLISHED (for supported detections)
        if fired:
            statuses = {rid: rules[rid]["lifecycle"]["status"] for rid in fired if rid in rules}
            all_pub = all(s == "PUBLISHED" for s in statuses.values())
            if exp.get("live_publishable") is not None and exp["live_publishable"] != all_pub:
                fail(f"live_publishable={exp.get('live_publishable')} but fired-rule statuses are {statuses}")

    log(f"  ok    {n_cases} golden decision cases internally consistent" if not any(p.split(':')[0].startswith('GDC') for p in problems)
        else f"  FAIL  golden decision cases")

    # ---- report
    print()
    if problems:
        print(f"DET-001 DESIGN GATE: FAIL — {len(problems)} problem(s)")
        for p in problems:
            print("  -", p)
        return 1
    print(f"DET-001 DESIGN GATE: PASS — schemas valid, contract usable, {n_cases} golden cases consistent with the KB and ADR-0006 risk model")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
