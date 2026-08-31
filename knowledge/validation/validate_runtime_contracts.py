"""TrustLens Phase 3 P3-WP1 runtime-contract validator.

Validates the RUNTIME detection-result / rule-evaluation-result contracts (knowledge/schemas/detection/)
and their fixtures. It validates STRUCTURE and CROSS-FIELD INVARIANTS only — it contains NO detection
logic and generates no decision (the engine is P3-WP2+). Offline by construction.

Checks:
  1. Both runtime schemas are valid Draft 2020-12.
  2. Enum synchronisation: the schema enums equal the canonical DET-001 / ADR-0006 vocabularies.
  3. Every VALID fixture validates against detection-result (the $ref to rule-evaluation-result resolves),
     carries no probability field (name-scan), and satisfies the cross-field semantic invariants.
  4. Every INVALID fixture is rejected by SOME layer (schema | namescan | semantic) — proving the
     validation is non-vacuous.
  5. Provenance completeness and contract-version syntax are enforced.
  6. Golden-case alignment: each of the 15 DET-001 golden decision cases is REPRESENTABLE in the runtime
     contract (structural compatibility; no engine decision is generated).

Usage:  .venv/bin/python knowledge/validation/validate_runtime_contracts.py [--quiet]
Exit 0 iff every check passes.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "knowledge" / "schemas" / "detection"
DETECTION_RESULT_SCHEMA = SCHEMA_DIR / "detection-result.schema.json"
RULE_EVAL_SCHEMA = SCHEMA_DIR / "rule-evaluation-result.schema.json"
VALID_FIXTURES = SCHEMA_DIR / "fixtures" / "valid-detection-results.json"
INVALID_FIXTURES = SCHEMA_DIR / "fixtures" / "invalid-detection-results.json"
GOLDEN = ROOT / "docs" / "03-detection" / "golden-decision-cases-v1.json"

SEV_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

# ADR-0006 risk matrix v1 (must match validate_det_design.py and ADR-0006).
RISK_MATRIX = {
    "NONE": {"NONE": "NONE"},
    "LOW": {"WEAK": "LOW", "MODERATE": "LOW", "STRONG": "MEDIUM"},
    "MEDIUM": {"WEAK": "LOW", "MODERATE": "MEDIUM", "STRONG": "MEDIUM"},
    "HIGH": {"WEAK": "MEDIUM", "MODERATE": "HIGH", "STRONG": "HIGH"},
    "CRITICAL": {"WEAK": "HIGH", "MODERATE": "HIGH", "STRONG": "CRITICAL"},
}

# Canonical vocabularies frozen by DET-001 / ADR-0005 / ADR-0006 (STEP 5).
CANON = {
    "input_support_status": {"SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "INSUFFICIENT_INFORMATION", "ERROR"},
    "classification": {"NO_SCAM_PATTERN", "INSUFFICIENT_EVIDENCE", "SCAM_PATTERN_SUSPECTED", "SCAM_PATTERN_DETECTED", "UNSUPPORTED", "ERROR"},
    "detection_confidence": {"NOT_APPLICABLE", "LOW", "MEDIUM", "HIGH"},
    "risk_level": {"NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"},
    "decision_severity": {"NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"},
    "matched_evidence_strength": {"NONE", "WEAK", "MODERATE", "STRONG"},
}
CANON_EVAL_STATE = {"MATCHED", "NOT_MATCHED", "INDETERMINATE", "SUPPRESSED", "NOT_APPLICABLE"}
CANON_ACTIONS = {
    "DO_NOT_SHARE_CREDENTIALS", "DO_NOT_ENTER_PIN", "DO_NOT_TRANSFER_MONEY", "DO_NOT_INSTALL_APP",
    "DO_NOT_CONNECT_WALLET", "DO_NOT_DIAL_CODE", "DISCONNECT_REMOTE_ACCESS", "VERIFY_INDEPENDENTLY",
    "CONTACT_BANK", "CONTACT_OFFICIAL_CHANNEL", "REPORT_CYBERCRIME", "PRESERVE_EVIDENCE",
    "PROCEED_WITH_CAUTION", "SEEK_HUMAN_REVIEW", "RESUBMIT_IN_SUPPORTED_LANGUAGE",
}

PROBABILITY_KEY = re.compile(r"probab|likelihood|percent", re.I)


def load(p):
    return json.loads(Path(p).read_text())


def build_validator():
    det = load(DETECTION_RESULT_SCHEMA)
    rev = load(RULE_EVAL_SCHEMA)
    registry = Registry().with_resources([
        (det["$id"], Resource.from_contents(det)),
        (rev["$id"], Resource.from_contents(rev)),
    ])
    return det, rev, Draft202012Validator(det, registry=registry)


def probability_keys(obj, path=""):
    """Recursively find any key that looks like a probability/score (defence in depth)."""
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if PROBABILITY_KEY.search(k) or k.lower() == "score":
                hits.append(f"{path}/{k}")
            hits += probability_keys(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits += probability_keys(v, f"{path}/{i}")
    return hits


def matched_rule_ids(result):
    return sorted(r["rule_id"] for r in result.get("rule_results", [])
                  if r.get("evaluation_state") == "MATCHED" and "rule_id" in r)


def semantic_violations(r):
    """Cross-field invariants not expressible in JSON Schema (DET-001 / ADR-0006)."""
    v = []
    support = r.get("input_support_status")
    cls = r.get("classification")
    sev = r.get("decision_severity")
    strength = r.get("matched_evidence_strength")
    risk = r.get("risk_level")
    conf = r.get("detection_confidence")
    matched = set(r.get("matched_rules", []))
    fired = set(matched_rule_ids(r))

    # matched_rules must equal the MATCHED rule_results
    if matched != fired:
        v.append(f"matched_rules {sorted(matched)} != MATCHED rule_results {sorted(fired)}")

    # risk matrix
    expected_risk = RISK_MATRIX.get(sev, {}).get(strength)
    if expected_risk is None:
        v.append(f"illegal (severity={sev}, strength={strength}) for the risk matrix")
    elif risk != expected_risk:
        v.append(f"risk_level {risk} != RISK_MATRIX[{sev}][{strength}] = {expected_risk}")

    # support/classification consistency; ERROR/UNSUPPORTED must not appear safe
    if support == "UNSUPPORTED" and cls != "UNSUPPORTED":
        v.append("UNSUPPORTED input must have classification UNSUPPORTED (unknown is not safe)")
    if support == "ERROR" and cls != "ERROR":
        v.append("ERROR input must have classification ERROR (a failure must not appear safe)")
    if support == "INSUFFICIENT_INFORMATION" and cls != "INSUFFICIENT_EVIDENCE":
        v.append("INSUFFICIENT_INFORMATION input must classify as INSUFFICIENT_EVIDENCE")

    # fired vs classification/severity/confidence
    if fired:
        if cls not in ("SCAM_PATTERN_DETECTED", "SCAM_PATTERN_SUSPECTED"):
            v.append(f"fired rules present but classification is {cls}")
        if conf == "LOW" and cls != "SCAM_PATTERN_SUSPECTED":
            v.append("LOW detection_confidence with a fired rule must be SCAM_PATTERN_SUSPECTED")
        if conf in ("MEDIUM", "HIGH") and cls != "SCAM_PATTERN_DETECTED":
            v.append(f"{conf} detection_confidence with a fired rule must be SCAM_PATTERN_DETECTED")
        if sev == "NONE":
            v.append("fired rules present but decision_severity is NONE")
    else:
        if cls in ("SCAM_PATTERN_DETECTED", "SCAM_PATTERN_SUSPECTED"):
            v.append(f"no fired rules but classification is {cls}")
        if sev != "NONE" or risk != "NONE" or conf != "NOT_APPLICABLE":
            v.append("no fired rules must yield severity/risk NONE and confidence NOT_APPLICABLE")

    # recommended action vocabulary
    for a in r.get("recommended_actions", []):
        if a.get("action_code") not in CANON_ACTIONS:
            v.append(f"recommended action {a.get('action_code')} not in the controlled vocabulary")
    return v


def golden_case_result(case):
    """Build a minimal, schema-shaped detection-result from a golden case's expected decision."""
    exp = case["expected"]
    prov = {
        "bundle_version": "1.0.0",
        "bundle_content_digest": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "engine_version": "0.1.0-wp1",
        "evaluation_profile": {"profile_id": "mvp-default", "extraction_confidence_gate": "MEDIUM",
                               "risk_matrix_id": "adr-0006-risk-matrix-v1", "confidence_policy_id": "adr-0006-confidence-policy-v1"},
        "component_versions": {"rule_schema": "1.0.0", "indicator_registry": "0.3.0-interim", "indicator_families": "1.0.0",
                               "negative_library": "1.0.0", "taxonomy": "2.0.0", "dimensions": "1.0.0", "extraction_contracts": "1.0.0"},
    }
    rcr = {"MATCHED": "TRUE", "SUPPRESSED": "TRUE", "NOT_MATCHED": "FALSE", "INDETERMINATE": "UNKNOWN", "NOT_APPLICABLE": "UNKNOWN"}
    rule_results = []
    for rid, state in exp.get("rule_states", {}).items():
        rule_result = {"rule_id": rid, "rule_version": "1.0.0", "kind": "COMPOSITE",
                       "evaluation_state": state, "required_combination_result": rcr.get(state, "UNKNOWN")}
        if state == "SUPPRESSED":
            suppressors = sorted({i["id"] for i in case.get("declared_indicators", [])
                                  if i.get("polarity") == "NEGATIVE"})
            if suppressors:
                rule_result["suppression"] = {
                    "effect": "SUPPRESS_RULE",
                    "applied_suppressors": suppressors,
                    "suppressed_by": suppressors[0],
                }
        rule_results.append(rule_result)
    return {
        "result_contract_version": "1.0.0",
        "evaluation_id": f"GDC-ALIGN-{case['id']}",
        "evaluation_timestamp": "2026-08-29T00:00:00Z",
        "input_id": f"IN-{case['id']}",
        "language": case.get("language", ["en"]),
        "script": case.get("script", ["Latn"]),
        "input_support_status": exp["input_support_status"],
        "classification": exp["classification"],
        "decision_severity": exp["severity"],
        "matched_evidence_strength": exp["matched_evidence_strength"],
        "risk_level": exp["risk_level"],
        "detection_confidence": exp["detection_confidence"],
        "provenance": prov,
        "matched_rules": exp.get("fired_rules", []),
        "active_overrides": exp.get("active_overrides", []),
        "rule_results": rule_results,
        "explanation": {"summary": case["title"], "what_was_detected": case["title"], "why": "golden-case alignment",
                        "detection_confidence_reason": "structural representability check only"},
        "recommended_actions": [{"action_code": a} for a in exp.get("recommended_actions", [])],
    }


def main() -> int:
    quiet = "--quiet" in sys.argv
    problems = []

    def log(msg):
        if not quiet:
            print(msg)

    det, rev, validator = build_validator()

    # 1. schemas valid
    for name, sch in (("detection-result", det), ("rule-evaluation-result", rev)):
        try:
            Draft202012Validator.check_schema(sch)
        except Exception as e:  # noqa: BLE001
            problems.append(f"schema {name} invalid Draft 2020-12: {e}")
    log("  ok    both runtime schemas valid Draft 2020-12" if not problems else "  FAIL  schema validity")

    # 2. enum synchronisation with DET-001 / ADR-0006
    for field, expected in CANON.items():
        got = set(det["properties"][field]["enum"])
        if got != expected:
            problems.append(f"enum drift: detection-result.{field} {sorted(got)} != canonical {sorted(expected)}")
    got_states = set(rev["properties"]["evaluation_state"]["enum"])
    if got_states != CANON_EVAL_STATE:
        problems.append(f"enum drift: evaluation_state {sorted(got_states)} != {sorted(CANON_EVAL_STATE)}")
    got_actions = set(det["$defs"]["recommendedAction"]["properties"]["action_code"]["enum"])
    if got_actions != CANON_ACTIONS:
        problems.append(f"enum drift: action_code {sorted(got_actions)} != canonical {sorted(CANON_ACTIONS)}")
    if det["properties"]["result_contract_version"]["const"] != "1.0.0":
        problems.append("result_contract_version const must be 1.0.0")
    log("  ok    enums synchronised with DET-001 / ADR-0006" if not any('enum drift' in p or 'contract_version' in p for p in problems) else "  FAIL  enum sync")

    # 3. valid fixtures
    valid = load(VALID_FIXTURES)["fixtures"]
    for fx in valid:
        fid = fx.get("evaluation_id", "?")
        errs = sorted(validator.iter_errors(fx), key=lambda e: list(e.path))
        for e in errs:
            problems.append(f"valid fixture {fid} fails schema: {e.message} at /{'/'.join(map(str, e.path))}")
        for hit in probability_keys(fx):
            problems.append(f"valid fixture {fid} contains a probability-like field: {hit}")
        for v in semantic_violations(fx):
            problems.append(f"valid fixture {fid} semantic violation: {v}")
    log(f"  ok    {len(valid)} valid fixtures pass schema + name-scan + semantics"
        if not any('valid fixture' in p for p in problems) else "  FAIL  valid fixtures")

    # 4. invalid fixtures — each must be rejected by SOME layer (non-vacuity)
    invalid = load(INVALID_FIXTURES)["invalid_fixtures"]
    for inv in invalid:
        res = inv["result"]
        schema_bad = bool(list(validator.iter_errors(res)))
        namescan_bad = bool(probability_keys(res))
        semantic_bad = bool(semantic_violations(res)) if not schema_bad else False
        if not (schema_bad or namescan_bad or semantic_bad):
            problems.append(f"invalid fixture NOT rejected (vacuous): {inv['reason']}")
    log(f"  ok    {len(invalid)} invalid fixtures each rejected (non-vacuous)"
        if not any('vacuous' in p for p in problems) else "  FAIL  invalid fixtures")

    # 6. golden-case alignment — representability of all 15 golden decision cases
    if GOLDEN.exists():
        cases = load(GOLDEN)["cases"]
        for c in cases:
            built = golden_case_result(c)
            errs = sorted(validator.iter_errors(built), key=lambda e: list(e.path))
            for e in errs:
                problems.append(f"golden case {c['id']} not representable: {e.message} at /{'/'.join(map(str, e.path))}")
        log(f"  ok    {len(cases)} golden decision cases representable in the runtime contract"
            if not any('not representable' in p for p in problems) else "  FAIL  golden-case alignment")
    else:
        problems.append("golden-decision-cases-v1.json not found for alignment check")

    print()
    if problems:
        print(f"RUNTIME CONTRACTS: FAIL — {len(problems)} problem(s)")
        for p in problems:
            print("  -", p)
        return 1
    print(f"RUNTIME CONTRACTS: PASS — schemas valid, enums synced, {len(valid)} valid + {len(invalid)} invalid "
          f"fixtures, all 15 golden cases representable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
