"""TrustLens Phase 3 DET-001 design-gate validator.

Checks the INTERNAL CONSISTENCY of the DET-001 design against the live Phase-2 knowledge base.
It is a DESIGN validator, not a detection engine: it does not evaluate rules over inputs. It proves
that the design contracts and the golden decision cases are coherent, reference only real knowledge,
and obey the ADR-0006 risk model and the classification/severity rules stated in DET-001.

Wired into knowledge/validation/run_all.py as the **10th canonical check** at the Phase-3 closure
(GATE-009): the canonical quality gate now proves the existing 9 checks plus the Phase-3 design
contracts and golden decision cases. It remains independently runnable. It is offline (no network or
subprocess imports), so it passes run_all.py's offline preflight.

Checks — every golden decision case:
   - fired rule ids resolve to real rule files; severity/verdict/status read from them;
   - declared indicator ids resolve to the positive registry or the negative library;
   - active overrides resolve to the negative library;
   - risk_level == RISK_MATRIX[severity][matched_evidence_strength] (ADR-0006);
   - classification is consistent with input_support_status, fired rules and detection_confidence;
   - decision severity == max effective severity (min(declared, PARTIAL cap)) over fired rules;
   - recommended actions are in the controlled vocabulary;
   - live_publishable == (all fired rules are PUBLISHED) for supported detections.
Offline by construction. Exit 0 iff every check passes.

Schema/contract validation (schema validity, fixtures, enum sync, golden-case representability) is owned
by knowledge/validation/validate_runtime_contracts.py (P3-WP1), which validates the PROMOTED, authoritative
runtime contracts under knowledge/schemas/detection/. This validator therefore no longer loads any schema —
it is purely the design-consistency check over the golden cases and the live knowledge base.

Usage:  .venv/bin/python docs/03-detection/validate_det_design.py [--quiet]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DET_DIR = ROOT / "docs" / "03-detection"
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


def binding_topology_problems(exp, rules):
    """Validate the binding rule topology of an expected-decision block (P3-WP7 M1 fail-closed).

    The binding topology is fired_rules UNION every rule id that carries a binding rule_states entry.
    Fail-closed reference resolution: EVERY binding rule id must first resolve against governed rule
    metadata. An unresolved id is an illegal governed reference and FAILS regardless of live_publishable
    — an unknown governed reference is never legal, and lifecycle is never inferred from a rule-id name
    or prefix. Only once every id resolves is the lifecycle biconditional applied (the GDC-08 check,
    unweakened): live_publishable == (every binding rule is PUBLISHED). Returns a list of problem strings
    (empty iff the topology is coherent).
    """
    problems = []
    topology = sorted(set(exp.get("fired_rules", [])) | set(exp.get("rule_states", {})))
    unresolved = [rid for rid in topology if rid not in rules]
    for rid in unresolved:
        problems.append(f"binding rule id {rid} (in fired_rules/rule_states) does not resolve to governed "
                        f"rule metadata — fail closed (an unknown governed reference is never legal)")
    if unresolved:
        return problems  # never infer lifecycle for an unresolved id; the reference failure is authoritative
    if topology:
        statuses = {rid: rules[rid]["lifecycle"]["status"] for rid in topology}
        all_pub = all(s == "PUBLISHED" for s in statuses.values())
        if exp.get("live_publishable") is not None and exp["live_publishable"] != all_pub:
            problems.append(f"live_publishable={exp.get('live_publishable')} but binding rule-topology "
                            f"statuses are {statuses}")
    return problems


def main() -> int:
    quiet = "--quiet" in sys.argv
    problems = []

    def log(*a):
        if not quiet:
            print(*a)

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

        # live_publishable over the COMPLETE binding rule topology (P3-WP7 M1 fail-closed reference resolution).
        # The binding topology is fired_rules UNION every rule id that carries a binding rule_states entry — not
        # only the fired/governing rules. EVERY binding id is first resolved against governed rule metadata: an
        # unresolved id fails closed (an unknown governed reference is never silently omitted from lifecycle
        # validation, never inferred from a rule-id prefix, and is illegal irrespective of live_publishable). For
        # a fully-resolved topology the unweakened lifecycle biconditional holds: live_publishable == (all binding
        # rules PUBLISHED). This still catches a case that expects an unpublished rule to hold a binding state
        # (e.g. a SUPPRESSED design outcome) while claiming live_publishable=true.
        for msg in binding_topology_problems(exp, rules):
            fail(msg)

    # ---- P3-WP7 M1 fail-closed reference-resolution regressions (corpus-independent). These drive the EXACT
    #      production binding-topology check (binding_topology_problems) over synthetic expected-blocks and add a
    #      REGRESSION problem only if it misbehaves. They prove that an unknown governed reference fails closed in
    #      every direction of live_publishable, and that the GDC-08 lifecycle shapes are unchanged. No case-id
    #      special handling — the lifecycle shapes are exercised through the real non-PUBLISHED rule TL-MAL-003.
    def _fails(exp_block):
        return bool(binding_topology_problems(exp_block, rules))

    # CASE A — unknown rule id in rule_states with live_publishable=true MUST fail closed.
    if not _fails({"fired_rules": [], "rule_states": {"UNKNOWN_RULE_ID": "SUPPRESSED"}, "live_publishable": True}):
        problems.append("REGRESSION M1-A: unknown rule_states id + live_publishable=true must FAIL closed but did not")
    # CASE B — unknown rule id in fired_rules with live_publishable=true MUST fail closed.
    if not _fails({"fired_rules": ["UNKNOWN_RULE_ID"], "rule_states": {}, "live_publishable": True}):
        problems.append("REGRESSION M1-B: unknown fired_rules id + live_publishable=true must FAIL closed but did not")
    # CASE C — unknown rule id in rule_states MUST fail closed EVEN WITH live_publishable=false. live_publishable=false
    #          never legalises an unknown governed reference.
    if not _fails({"fired_rules": [], "rule_states": {"UNKNOWN_RULE_ID": "SUPPRESSED"}, "live_publishable": False}):
        problems.append("REGRESSION M1-C: unknown rule_states id must FAIL closed even with live_publishable=false but did not")

    # GDC-08 lifecycle shapes over the real non-PUBLISHED binding rule TL-MAL-003 (biconditional unweakened).
    if "TL-MAL-003" in rules and rules["TL-MAL-003"]["lifecycle"]["status"] != "PUBLISHED":
        # old GDC-08 shape: live_publishable=true + unpublished TL-MAL-003 in binding rule_states MUST fail.
        if not _fails({"fired_rules": [], "rule_states": {"TL-MAL-003": "SUPPRESSED"}, "live_publishable": True}):
            problems.append("REGRESSION GDC-08(old): live_publishable=true + unpublished TL-MAL-003 in binding "
                            "rule_states must FAIL the lifecycle invariant but did not")
        # corrected GDC-08 shape: live_publishable=false + known non-PUBLISHED TL-MAL-003 MUST pass.
        if _fails({"fired_rules": [], "rule_states": {"TL-MAL-003": "SUPPRESSED"}, "live_publishable": False}):
            problems.append("REGRESSION GDC-08(corrected): live_publishable=false + known non-PUBLISHED TL-MAL-003 "
                            "must PASS the lifecycle invariant but did not")

    log(f"  ok    {n_cases} golden decision cases internally consistent" if not any(p.split(':')[0].startswith('GDC') for p in problems)
        else f"  FAIL  golden decision cases")

    # ---- report
    print()
    if problems:
        print(f"DET-001 DESIGN GATE: FAIL — {len(problems)} problem(s)")
        for p in problems:
            print("  -", p)
        return 1
    print(f"DET-001 DESIGN GATE: PASS — {n_cases} golden cases consistent with the KB and the ADR-0006 risk model "
          f"(schema/contract validation owned by validate_runtime_contracts.py)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
