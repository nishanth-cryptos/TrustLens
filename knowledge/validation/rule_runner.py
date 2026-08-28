"""TrustLens rule-runner — Phase 2 work package 8.

Deterministic evaluation of the encoded rule set against the seed corpus and the
reconciliation cases. This is NOT an extraction test: indicator extraction is a
Phase-9 deliverable. The runner takes each case's DECLARED indicator set
(`expected_indicators` + `expected_negative_indicators`) as the ground-truth signal
an extractor would produce, and checks that the rule LOGIC — composite conditions,
own suppressors, and SUPPRESSION rules — behaves as the corpus specifies:

  * malicious cases: every encoded expected rule fires;
  * benign cases: no must_not_match rule fires, and no PUBLISHED rule fires at all
    (the false-positive guard, CONF-002 / RSK-002);
  * ambiguous cases: no PUBLISHED composite rule fires (INSUFFICIENT_EVIDENCE).

It also prints coverage (which live rules are exercised, which corpus-referenced
rules are not yet encoded) and a traceability summary (every published rule resolves
to real evidence). Exit code 0 = every case behaves as specified.

Usage:  .venv/bin/python knowledge/validation/rule_runner.py [--quiet]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES_DIR = ROOT / "knowledge" / "rules"
CORPUS_PATH = ROOT / "knowledge" / "seed-data" / "seed-corpus-v1.json"
RECON_PATH = ROOT / "knowledge" / "seed-data" / "reconciliation-cases-v1.json"
MANIFEST_PATH = ROOT / "knowledge" / "sources" / "verification-manifest.json"
EVIDENCE_RECORDS_PATH = ROOT / "knowledge" / "sources" / "manual-retrieval" / "evidence-records.json"

LIVE_STATUSES = {"PUBLISHED"}          # FR-023: only PUBLISHED is evaluated live
ENCODED_EVALUATED = {"PUBLISHED", "APPROVED", "PEER_REVIEW"}  # exercised in tests


def load(p):
    return json.loads(p.read_text())


# --------------------------------------------------------------- condition eval

def eval_condition(cond, signals):
    if isinstance(cond, str):
        return cond in signals
    if not isinstance(cond, dict):
        return False
    if "all_of" in cond:
        return all(eval_condition(x, signals) for x in cond["all_of"])
    if "any_of" in cond:
        return any(eval_condition(x, signals) for x in cond["any_of"])
    if "n_of" in cond:
        n = cond["n_of"]["n"]
        return sum(1 for x in cond["n_of"]["of"] if eval_condition(x, signals)) >= n
    return False


def composite_matches(rule, signals):
    """Require holds AND no own suppressor is present."""
    logic = rule["logic"]
    if not eval_condition(logic.get("require"), signals):
        return False
    for s in logic.get("suppressed_by", []):
        if s in signals:
            return False
    return True


def suppression_active(rule, signals):
    return eval_condition(rule["logic"].get("require"), signals)


def targets_rule(suppresses, rule):
    for t in suppresses:
        if t == "*" or t == rule["id"]:
            return True
        if t.startswith("TAX-"):
            for tax in rule.get("taxonomy_refs", []):
                if tax == t or tax.startswith(t + "-"):
                    return True
    return False


def lang_applies(rule, case_lang):
    base = case_lang.split("-")[0]
    return base in rule["language_scope"]["languages"]


def evaluate(case, rules):
    """Return (final_findings, matched_before_suppression) for PUBLISHED+APPROVED+PEER_REVIEW rules."""
    signals = set(case.get("expected_indicators", []) or [])
    signals |= set(case.get("expected_negative_indicators", []) or [])
    case_lang = case.get("language", "en")

    applicable = [r for r in rules if lang_applies(r, case_lang)
                  and r["lifecycle"]["status"] in ENCODED_EVALUATED]
    composites = [r for r in applicable if r["kind"] == "COMPOSITE"]
    suppressions = [r for r in rules if r["kind"] == "SUPPRESSION"
                    and lang_applies(r, case_lang)
                    and r["lifecycle"]["status"] in {"APPROVED", "PUBLISHED"}]

    matched = {r["id"]: r for r in composites if composite_matches(r, signals)}
    active_suppr = [r for r in suppressions if suppression_active(r, signals)]

    final = {}
    suppressed_out = {}
    for rid, r in matched.items():
        killed = next((s for s in active_suppr if targets_rule(s["logic"]["suppresses"], r)), None)
        if killed:
            suppressed_out[rid] = killed["id"]
        else:
            final[rid] = r
    return final, matched, suppressed_out


# --------------------------------------------------------------- main

def main() -> int:
    quiet = "--quiet" in sys.argv
    rules = []
    for p in sorted(RULES_DIR.glob("*.json")):
        rules.append(load(p))
    by_id = {r["id"]: r for r in rules}
    live_ids = {r["id"] for r in rules if r["lifecycle"]["status"] in LIVE_STATUSES}

    cases = []
    corpus = load(CORPUS_PATH)
    for bucket in ("benign", "malicious", "ambiguous"):
        for c in corpus.get(bucket, []):
            cases.append({**c, "_bucket": bucket, "_src": "seed-corpus-v1"})
    if RECON_PATH.exists():
        recon = load(RECON_PATH)
        for bucket in ("benign", "malicious", "ambiguous"):
            for c in recon.get(bucket, []):
                cases.append({**c, "_bucket": bucket, "_src": "reconciliation-cases-v1"})

    failures = []
    exercised = set()          # live/approved rules that fired on a malicious case
    not_encoded = set()        # corpus-referenced rules not present as files

    print(f"Rule-runner — {len(rules)} rules ({len(live_ids)} PUBLISHED), {len(cases)} cases\n")

    for case in cases:
        final, matched, suppressed = evaluate(case, rules)
        fired = set(final)
        bucket = case["_bucket"]
        cid = case["id"]
        problems = []

        if bucket == "malicious":
            for rid in case.get("expected_rules", []):
                if rid not in by_id:
                    not_encoded.add(rid)
                    continue
                if rid not in fired:
                    problems.append(f"expected {rid} to fire; fired={sorted(fired)} suppressed={suppressed}")
                else:
                    exercised.add(rid)
        elif bucket == "benign":
            for rid in case.get("must_not_match", []):
                if rid in fired:
                    problems.append(f"{rid} FIRED on benign case (false positive)")
            live_fp = [rid for rid in fired if rid in live_ids]
            if live_fp:
                problems.append(f"PUBLISHED rule(s) fired on benign case: {sorted(live_fp)}")
        else:  # ambiguous
            live_fp = [rid for rid in fired if rid in live_ids]
            if live_fp:
                problems.append(f"PUBLISHED rule(s) fired on ambiguous case (expected INSUFFICIENT_EVIDENCE): {sorted(live_fp)}")

        tag = f"{cid} [{case['_src']}]"
        if problems:
            failures.append((tag, problems))
            print(f"  FAIL  {tag}")
            for p in problems:
                print(f"          {p}")
        elif not quiet:
            detail = f"fired={sorted(fired)}" if fired else "no finding"
            if suppressed:
                detail += f" suppressed={suppressed}"
            print(f"  ok    {tag:<34} {detail}")

    # ---- coverage
    print("\nCoverage")
    live_and_approved = sorted(r["id"] for r in rules
                               if r["lifecycle"]["status"] in {"PUBLISHED", "APPROVED"}
                               and r["kind"] == "COMPOSITE")
    for rid in live_and_approved:
        mark = "exercised" if rid in exercised else "NOT exercised by any malicious case"
        print(f"  {rid:<14} {by_id[rid]['lifecycle']['status']:<11} {mark}")
    if not_encoded:
        print(f"\n  Corpus-referenced rules not yet encoded ({len(not_encoded)}): {sorted(not_encoded)}")

    # ---- traceability: every PUBLISHED rule resolves to real evidence
    print("\nTraceability (PUBLISHED rules resolve to evidence)")
    manifest = {s["id"]: s for s in load(MANIFEST_PATH)["sources"]}
    mr_records = {r["evidence_id"] for r in load(EVIDENCE_RECORDS_PATH)["records"]} \
        if EVIDENCE_RECORDS_PATH.exists() else set()
    trace_fail = []
    for r in rules:
        if r["lifecycle"]["status"] != "PUBLISHED":
            continue
        for ref in r["evidence"]["source_references"]:
            sid = ref["source_id"]
            if sid not in manifest:
                trace_fail.append(f"{r['id']}: source {sid} missing from manifest")
            mr = ref.get("manual_retrieval")
            if mr:
                for eid in mr["evidence_ids"]:
                    if eid not in mr_records:
                        trace_fail.append(f"{r['id']}: manual evidence {eid} missing from records")
    if trace_fail:
        for t in trace_fail:
            print(f"  FAIL  {t}")
        failures.append(("traceability", trace_fail))
    else:
        print(f"  ok    all {len(live_ids)} PUBLISHED rules trace to manifest sources / evidence records")

    # ---- report
    print()
    total = len(cases)
    if failures:
        print(f"{len(failures)} FAILURES across {total} cases + checks")
        return 1
    print(f"{total}/{total} cases behave as specified — "
          f"{len(exercised)} live/approved rules exercised, "
          f"{len(not_encoded)} corpus rules await encoding")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
