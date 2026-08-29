"""TrustLens rule loader and validator — Phase 2 work package 1.

Two layers, deliberately separated (ADR-0003):

  SCHEMA  jsonschema draft 2020-12 against knowledge/schemas/rule.schema.json.
          Catches everything expressible in one document: shape, enums, ordinals,
          conditional requirements, the ban on numeric risk.

  LINT    Everything needing knowledge the rule file does not contain — the
          indicator registry, the source manifest, the taxonomy, the Phase 1
          evidence matrix. This is where the interesting failures live: a rule
          claiming better provenance than Phase 1 established, an indicator that
          nothing extracts, a suppressor used as a trigger.

Implements FR-020 (rules as data), FR-021 (reject at load), FR-025 (graded source
reference required), and the publication constraint from RESEARCH-004 section 7.

Usage:
    .venv/bin/python knowledge/validation/validate_rules.py [--quiet]

Exit code 0 = every rule valid AND every negative fixture correctly rejected.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    sys.exit(
        "jsonschema is required.\n"
        "    python3 -m venv .venv && .venv/bin/pip install jsonschema\n"
        "    .venv/bin/python knowledge/validation/validate_rules.py"
    )

ROOT = Path(__file__).resolve().parents[2]
RULES_DIR = ROOT / "knowledge" / "rules"
SCHEMA_PATH = ROOT / "knowledge" / "schemas" / "rule.schema.json"
REGISTRY_PATH = ROOT / "knowledge" / "indicators" / "indicator-registry-v0.json"
NEG_LIBRARY_PATH = ROOT / "knowledge" / "indicators" / "negative-indicator-library-v1.json"
MANIFEST_PATH = ROOT / "knowledge" / "sources" / "verification-manifest.json"
TAXONOMY_PATH = ROOT / "knowledge" / "taxonomies" / "scam-taxonomy.json"
MATRIX_PATH = ROOT / "docs" / "01-research" / "RESEARCH-004-evidence-matrix.md"
FIXTURES_PATH = RULES_DIR / "_fixtures" / "invalid-rules.json"
EVIDENCE_RECORDS_PATH = ROOT / "knowledge" / "sources" / "manual-retrieval" / "evidence-records.json"

# ADR-0015 evidence hierarchy. Which classes can carry which lone verdict.
SUPPORTED_CAPABLE = {"PRIMARY", "OFFICIAL_REPLACEMENT"}
PUBLISHABLE_CLASSES = {"PRIMARY", "OFFICIAL_ALTERNATE", "OFFICIAL_REPLACEMENT", "INDUSTRY"}
STRONG_CLAIM_MATCH = {"FULL", "FULL_CONCEPT", "FULL_FOR_SCREEN_SHARE_CONCEPT"}

WEAK = "WEAK"


def load(path: Path):
    return json.loads(path.read_text())


# --------------------------------------------------------------- reference data

def load_reference_data():
    registry = load(REGISTRY_PATH)
    indicators = {i["id"]: i for i in registry["indicators"]}

    # WP3 / G-07: negative (SUPPRESSIVE) indicators now live in the formal library.
    # Merge them back into the indicator namespace so L1 (resolution) and L2 (polarity) work.
    library = load(NEG_LIBRARY_PATH)
    for ni in library["negative_indicators"]:
        indicators[ni["negative_indicator_id"]] = {
            "id": ni["negative_indicator_id"],
            "polarity": "NEGATIVE",
            "evidence_class": "SUPPRESSIVE",
            "strength": ni["strength"],
            "_library": ni,
        }

    manifest = load(MANIFEST_PATH)
    sources = {s["id"]: s for s in manifest["sources"]}

    taxonomy = load(TAXONOMY_PATH)
    taxa = set()
    for cat in taxonomy["categories"]:
        taxa.add(cat["id"])
        for sub in cat["subcategories"]:
            taxa.add(sub["id"])

    # Phase 1 verdicts are authoritative: a rule may not re-grade itself upward.
    # The matrix is post-reconciliation (RESEARCH-004 v1.2); manual retrieval upgrades a
    # rule's ceiling only where the evidence matrix records the upgrade.
    matrix = {}
    for rid, verdict in re.findall(
        r"\| `(TL-[A-Z]+-\d+)` \|(?:[^|]*\|){4} \*\*(\w+)\*\* \|", MATRIX_PATH.read_text()
    ):
        matrix[rid] = verdict

    # Manual-retrieval evidence records (DEC-006, ADR-0015).
    mr_records = {}
    if EVIDENCE_RECORDS_PATH.exists():
        mr_records = {r["evidence_id"]: r for r in load(EVIDENCE_RECORDS_PATH)["records"]}

    return indicators, sources, taxa, matrix, mr_records


# --------------------------------------------------------------- condition walk

def operands(condition):
    """Yield every indicator ID referenced anywhere in a condition tree."""
    if isinstance(condition, str):
        yield condition
        return
    if not isinstance(condition, dict):
        return
    for op, val in condition.items():
        if op == "n_of":
            for item in val.get("of", []):
                yield from operands(item)
        else:
            for item in val:
                yield from operands(item)


def satisfying_sets(condition):
    """Every minimal set of indicators that satisfies the condition.

    Needed because evidence-class diversity must hold on every path, not just
    across the union. A rule whose all_of spans three classes but whose any_of
    branch could be satisfied by one weak indicator is still a keyword matcher
    on that branch.
    """
    if isinstance(condition, str):
        return [{condition}]
    if not isinstance(condition, dict):
        return [set()]

    if "all_of" in condition:
        combos = [set()]
        for item in condition["all_of"]:
            combos = [c | s for c in combos for s in satisfying_sets(item)]
        return combos
    if "any_of" in condition:
        return [s for item in condition["any_of"] for s in satisfying_sets(item)]
    if "n_of" in condition:
        n = condition["n_of"]["n"]
        items = condition["n_of"]["of"]
        from itertools import combinations

        out = []
        for chosen in combinations(items, n):
            combos = [set()]
            for item in chosen:
                combos = [c | s for c in combos for s in satisfying_sets(item)]
            out.extend(combos)
        return out
    return [set()]


# --------------------------------------------------------------- lint checks

def lint(rule, indicators, sources, taxa, matrix, mr_records):
    """Return a list of lint failures. Empty means clean."""
    errs = []
    rid = rule.get("id", "<no id>")
    logic = rule.get("logic", {})
    require = logic.get("require")

    # L1 — every referenced indicator exists
    referenced = set(operands(require)) | set(logic.get("suppressed_by", []))
    for ind in sorted(referenced):
        if ind not in indicators:
            errs.append(f"unknown indicator {ind!r} — nothing extracts it, so the rule is dead")

    known = {i for i in referenced if i in indicators}

    # L1b — a rule may not depend on a DEPRECATED negative indicator (WP3 / G-07)
    for ind in sorted(set(logic.get("suppressed_by", [])) & known):
        lib = indicators[ind].get("_library")
        if lib and lib.get("status") == "DEPRECATED":
            errs.append(f"suppressed_by references DEPRECATED negative indicator {ind!r} — migrate it")

    # L2 — polarity discipline
    trigger_ids = set(operands(require))
    for ind in sorted(trigger_ids & known):
        expected = "NEGATIVE" if rule.get("kind") == "SUPPRESSION" else "POSITIVE"
        if indicators[ind]["polarity"] != expected:
            errs.append(
                f"{ind} is {indicators[ind]['polarity']} but is used as a trigger on a "
                f"{rule.get('kind')} rule, which requires {expected}"
            )
    for ind in sorted(set(logic.get("suppressed_by", [])) & known):
        if indicators[ind]["polarity"] != "NEGATIVE":
            errs.append(f"{ind} is POSITIVE but is listed in suppressed_by")

    # L3/L4 — the anti-keyword-matcher checks, on every satisfying path
    if rule.get("kind") == "COMPOSITE" and require is not None:
        need = logic.get("min_evidence_classes", 2)
        for satisfying in satisfying_sets(require):
            resolved = [indicators[i] for i in satisfying if i in indicators]
            if len(resolved) != len(satisfying):
                continue  # already reported as unknown
            classes = {i["evidence_class"] for i in resolved}
            if len(classes) < need:
                errs.append(
                    f"satisfiable by {sorted(satisfying)} spanning {len(classes)} evidence "
                    f"class(es) {sorted(classes)}, below the declared minimum of {need} (CONF-002)"
                )
            if resolved and all(i["strength"] == WEAK for i in resolved):
                errs.append(
                    f"satisfiable by weak indicators alone {sorted(satisfying)} — "
                    f"RP p.13 forbids a finding resting on weak signals"
                )

    # L5 — taxonomy references resolve
    for t in rule.get("taxonomy_refs", []):
        if t not in taxa:
            errs.append(f"unknown taxonomy reference {t!r}")

    # L6 — source references resolve, and grades are not overstated
    for ref in rule.get("evidence", {}).get("source_references", []):
        sid = ref.get("source_id")
        if sid not in sources:
            errs.append(f"source {sid!r} does not exist in the verification manifest")
            continue
        actual = sources[sid]["status"]
        claimed = ref.get("verification_status")
        if claimed != actual:
            errs.append(
                f"{sid} is graded {actual} in the manifest but the rule claims {claimed} "
                f"— a rule may not upgrade its own provenance"
            )
        if sources[sid]["authority"] != ref.get("authority"):
            errs.append(
                f"{sid} authority is {sources[sid]['authority']} in the manifest "
                f"but the rule claims {ref.get('authority')}"
            )
        if actual == "PRIMARY_VERIFIED" and not ref.get("quote"):
            errs.append(f"{sid} is PRIMARY_VERIFIED but the rule cites no locating quotation")

    # L7 — verdict may not exceed the Phase 1 evidence matrix
    order = {"UNSUPPORTED": 0, "HEURISTIC": 0, "PARTIAL": 1, "SUPPORTED": 2}
    if rid in matrix:
        phase1 = matrix[rid]
        claimed = rule.get("evidence", {}).get("verdict")
        if claimed in order and order[claimed] > order.get(phase1, 0):
            errs.append(
                f"evidence verdict {claimed} exceeds the Phase 1 grading {phase1} "
                f"(RESEARCH-004) — verdicts flow from the evidence matrix, not the author"
            )

    # L8 — review scheduling is coherent
    lc = rule.get("lifecycle", {})
    if lc.get("review_due") and lc.get("last_reviewed") and lc["review_due"] <= lc["last_reviewed"]:
        errs.append("review_due must be after last_reviewed")

    # L9 — a suppression rule must name targets that exist or are scoped
    for target in logic.get("suppresses", []):
        if target.startswith("TAX-") and target not in taxa:
            errs.append(f"suppresses unknown taxonomy scope {target!r}")

    refs = rule.get("evidence", {}).get("source_references", [])

    # L10 — manual_retrieval provenance integrity (DEC-006, ADR-0015).
    # The block is additive: verification_status still records the automated grade (L6), and
    # everything the manual layer asserts must resolve to a real evidence record and agree with
    # the manifest's per-source overlay. This is the check that stops manual evidence being invented.
    for ref in refs:
        mr = ref.get("manual_retrieval")
        if not mr:
            continue
        sid = ref.get("source_id")
        src = sources.get(sid, {})
        for eid in mr.get("evidence_ids", []):
            if eid not in mr_records:
                errs.append(f"{sid} manual_retrieval cites unknown evidence id {eid!r}")
            elif not mr_records[eid].get("sha256"):
                errs.append(f"{sid} manual evidence {eid} has no sha256 recorded (ADR-0015 condition 4)")
        overlay = src.get("manual_retrieval")
        if not overlay:
            errs.append(
                f"{sid} carries a rule-level manual_retrieval block but the manifest records no "
                f"manual overlay for it — manual evidence must be recorded at the source first"
            )
        else:
            if mr.get("evidence_class") != overlay.get("evidence_class"):
                errs.append(
                    f"{sid} manual_retrieval evidence_class {mr.get('evidence_class')} disagrees with "
                    f"the manifest overlay {overlay.get('evidence_class')}"
                )
            extra = set(mr.get("evidence_ids", [])) - set(overlay.get("evidence_ids", []))
            if extra:
                errs.append(
                    f"{sid} manual_retrieval cites evidence not recorded in the manifest overlay: "
                    f"{sorted(extra)}"
                )
        # wording may not exceed the source (ADR-0015 condition 6)
        if mr.get("claim_match") in STRONG_CLAIM_MATCH:
            for eid in mr.get("evidence_ids", []):
                rec_cm = mr_records.get(eid, {}).get("claim_match", "")
                if rec_cm.startswith("PARTIAL"):
                    errs.append(
                        f"{sid} manual_retrieval claims {mr.get('claim_match')} but evidence {eid} is "
                        f"graded {rec_cm} — rule wording exceeds the source (ADR-0015 condition 6)"
                    )
        # published/approved rules require recorded human review (ADR-0015 condition 7)
        if rule.get("lifecycle", {}).get("status") in ("APPROVED", "PUBLISHED") \
                and mr.get("review_status") != "REVIEWED":
            errs.append(f"{sid} manual_retrieval is not REVIEWED but the rule is {rule['lifecycle']['status']}")

    # L11 — publication integrity and the ADR-0015 class caps.
    verdict = rule.get("evidence", {}).get("verdict")
    status = rule.get("lifecycle", {}).get("status")

    def effective_class(ref):
        if ref.get("verification_status") == "PRIMARY_VERIFIED":
            return "PRIMARY"
        mr = ref.get("manual_retrieval")
        return mr.get("evidence_class") if mr else None

    if verdict in ("SUPPORTED", "PARTIAL"):
        supporting = [c for c in (effective_class(r) for r in refs) if c in PUBLISHABLE_CLASSES]
        if status in ("APPROVED", "PUBLISHED") and not supporting:
            errs.append(
                f"verdict {verdict} at status {status} but no source_reference provides "
                f"publishable-grade evidence — publication would rest on unverified sources "
                f"with no manual evidence (ADR-0015)"
            )
        if verdict == "SUPPORTED" and supporting and not (set(supporting) & SUPPORTED_CAPABLE):
            errs.append(
                f"verdict SUPPORTED but the only publishable evidence is {sorted(set(supporting))} "
                f"— OFFICIAL_ALTERNATE/INDUSTRY evidence caps a rule at PARTIAL (ADR-0015)"
            )

    return errs


# --------------------------------------------------------------- merge patch

def merge_patch(target, patch):
    """RFC 7386. null removes a key."""
    if not isinstance(patch, dict):
        return patch
    out = dict(target) if isinstance(target, dict) else {}
    for k, v in patch.items():
        if v is None:
            out.pop(k, None)
        else:
            out[k] = merge_patch(out.get(k), v)
    return out


# --------------------------------------------------------------- main

def main() -> int:
    quiet = "--quiet" in sys.argv
    schema = load(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    indicators, sources, taxa, matrix, mr_records = load_reference_data()

    failures = []
    seen_ids = {}

    rule_files = sorted(p for p in RULES_DIR.glob("*.json"))
    print(f"Loading {len(rule_files)} rules against schema {schema['$id']}\n")

    published = 0
    for path in rule_files:
        rule = load(path)
        rid = rule.get("id", path.stem)
        errs = [f"schema: {e.json_path} {e.message}" for e in validator.iter_errors(rule)]
        if not errs:
            errs = [f"lint: {m}" for m in lint(rule, indicators, sources, taxa, matrix, mr_records)]

        if rid in seen_ids:
            errs.append(f"duplicate rule id, also defined in {seen_ids[rid]}")
        seen_ids[rid] = path.name

        if path.stem != rid:
            errs.append(f"filename {path.name} does not match rule id {rid}")

        status = rule.get("lifecycle", {}).get("status", "?")
        verdict = rule.get("evidence", {}).get("verdict", "?")
        if status == "PUBLISHED":
            published += 1

        if errs:
            failures.append((path.name, errs))
            print(f"  FAIL  {rid:<14} {status:<9} {verdict}")
            for e in errs:
                print(f"          {e}")
        elif not quiet:
            print(f"  ok    {rid:<14} {status:<9} {verdict}")

    # ---- negative corpus: every fixture MUST be rejected, by the right layer
    fixtures = load(FIXTURES_PATH)
    base = fixtures["base"]
    print(f"\nNegative corpus — {len(fixtures['fixtures'])} fixtures that must be rejected\n")

    for fx in fixtures["fixtures"]:
        candidate = merge_patch(base, fx["patch"])
        schema_errs = list(validator.iter_errors(candidate))
        lint_errs = lint(candidate, indicators, sources, taxa, matrix, mr_records) if not schema_errs else []

        if schema_errs:
            caught_by = "SCHEMA"
        elif lint_errs:
            caught_by = "LINT"
        else:
            caught_by = None

        expected = fx["expect_rejected_by"]
        if caught_by is None:
            failures.append((fx["name"], [f"NOT REJECTED — expected {expected} to catch it"]))
            print(f"  FAIL  {fx['name']:<45} accepted, but must be rejected")
        elif caught_by != expected:
            failures.append(
                (fx["name"], [f"rejected by {caught_by}, expected {expected} — layer split has drifted"])
            )
            print(f"  FAIL  {fx['name']:<45} caught by {caught_by}, expected {expected}")
        elif not quiet:
            print(f"  ok    {fx['name']:<45} rejected by {caught_by}")

    # ---- report
    total = len(rule_files) + len(fixtures["fixtures"])
    print()
    if failures:
        print(f"{len(failures)} of {total} checks FAILED")
        return 1
    print(f"{total}/{total} checks passed — {len(rule_files)} rules valid, {published} published, "
          f"{len(fixtures['fixtures'])} malformed rules correctly rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
