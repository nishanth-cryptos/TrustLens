"""TrustLens rule-runner — Phase 2 WP8, upgraded for the WP3/G-07 negative-indicator library.

Deterministic evaluation of the encoded rule set against the seed corpus, the reconciliation
cases and the suppression tests. NOT an extraction test: extraction is Phase 9. Each case's
DECLARED indicator set (`expected_indicators` + `expected_negative_indicators`) is treated as the
signal an extractor would produce, and the runner checks that the rule LOGIC plus the formal
suppression semantics behave as specified.

Suppression semantics (from knowledge/indicators/negative-indicator-library-v1.json):

  1. Hard-risk OVERRIDES are computed on the RAW signal set, per applicable rule.
  2. If an override is active for a rule, directional neutralisation is skipped (the live pattern is
     trusted) and soft suppressor categories are BLOCKED.
  3. Otherwise, SUPPRESS_INDICATOR (directional negation) neutralises its target positives; the
     rule's `require` is evaluated on the reduced set.
  4. If the rule still matches, SUPPRESS_RULE cancels it and CAP_SEVERITY caps its severity —
     unless the suppressor's category is blocked by an active override.
  5. CONTEXT_ONLY indicators are recorded as benign evidence and never change the finding.
  6. Numeric score-reduction magnitudes are deliberately absent (deferred to DET-001, CONF-001).

Every suppression decision is explainable (`--explain`).

Usage:  .venv/bin/python knowledge/validation/rule_runner.py [--quiet] [--explain]
Exit 0 = every case behaves as specified AND traceability holds.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES_DIR = ROOT / "knowledge" / "rules"
NEG_LIBRARY_PATH = ROOT / "knowledge" / "indicators" / "negative-indicator-library-v1.json"
MANIFEST_PATH = ROOT / "knowledge" / "sources" / "verification-manifest.json"
EVIDENCE_RECORDS_PATH = ROOT / "knowledge" / "sources" / "manual-retrieval" / "evidence-records.json"
CASE_FILES = [
    ("seed-corpus-v1", ROOT / "knowledge" / "seed-data" / "seed-corpus-v1.json"),
    ("reconciliation-cases-v1", ROOT / "knowledge" / "seed-data" / "reconciliation-cases-v1.json"),
    ("suppression-tests-v1", ROOT / "knowledge" / "seed-data" / "suppression-tests-v1.json"),
]

LIVE_STATUSES = {"PUBLISHED"}
ENCODED_EVALUATED = {"PUBLISHED", "APPROVED", "PEER_REVIEW"}
SEVERITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


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
        return sum(1 for x in cond["n_of"]["of"] if eval_condition(x, signals)) >= cond["n_of"]["n"]
    return False


def family_match(families, rule):
    if "*" in families:
        return True
    for f in families:
        for t in rule.get("taxonomy_refs", []):
            if t == f or t.startswith(f + "-") or f.startswith(t + "-"):
                return True
    return False


def override_applicable(ov, rule):
    if rule["id"] in ov.get("applies_to_rules", []):
        return True
    return family_match(ov.get("applies_to_families", []), rule)


def lang_applies(rule, case_lang):
    return case_lang.split("-")[0] in rule["language_scope"]["languages"]


# --------------------------------------------------------------- evaluation core

def evaluate(case, rules, neg, overrides):
    """Return (final, explain) where final maps rid -> effective severity, explain maps rid -> dict."""
    raw = set(case.get("expected_indicators", []) or [])
    raw |= set(case.get("expected_negative_indicators", []) or [])
    lang = case.get("language", "en")

    present_neg = {n: neg[n] for n in raw if n in neg}
    positives = {s for s in raw if s not in neg}

    composites = [r for r in rules if r["kind"] == "COMPOSITE"
                  and lang_applies(r, lang) and r["lifecycle"]["status"] in ENCODED_EVALUATED]
    suppression_rules = [r for r in rules if r["kind"] == "SUPPRESSION"
                         and lang_applies(r, lang) and r["lifecycle"]["status"] in {"APPROVED", "PUBLISHED"}]

    final, explain = {}, {}
    for r in composites:
        active_ovs = [ov for ov in overrides if override_applicable(ov, r) and eval_condition(ov["condition"], raw)]
        blocked_cats = set()
        for ov in active_ovs:
            blocked_cats |= set(ov["blocks_suppression_categories"])

        # directional neutralisation (skipped when a hard-risk override is active)
        neutralised = set()
        if not active_ovs:
            for nid, ni in present_neg.items():
                if ni["suppression_effect"] == "SUPPRESS_INDICATOR":
                    neutralised |= set(ni.get("suppresses_indicators", []))
        eff = (positives - neutralised) | set(present_neg)

        if not eval_condition(r["logic"].get("require"), eff):
            continue  # rule does not match

        matched_pos = sorted(p for p in positives - neutralised)
        # gather suppressors that apply to this rule
        cancelled_by = None
        caps = []
        blocked = []
        for nid, ni in present_neg.items():
            eff_kind = ni["suppression_effect"]
            if eff_kind not in ("SUPPRESS_RULE", "CAP_SEVERITY"):
                continue
            applies = nid in set(r["logic"].get("suppressed_by", [])) or family_match(ni["applicable_rule_families"], r)
            if not applies:
                continue
            if ni["category"] in blocked_cats:
                blocked.append(nid)
                continue
            if eff_kind == "SUPPRESS_RULE":
                cancelled_by = nid
                break
            caps.append(ni.get("severity_cap"))

        # legacy SUPPRESSION-kind rules (also override-aware)
        if cancelled_by is None:
            for s in suppression_rules:
                if eval_condition(s["logic"].get("require"), raw) and _targets(s["logic"].get("suppresses", []), r):
                    if active_ovs:
                        blocked.append(s["id"])
                    else:
                        cancelled_by = s["id"]
                        break

        exp = {
            "matched_positives": matched_pos,
            "negatives_present": sorted(present_neg),
            "neutralised": sorted(neutralised),
            "overrides_active": [ov["override_id"] for ov in active_ovs],
            "blocked_suppressors": blocked,
            "cancelled_by": cancelled_by,
            "severity_caps": [c for c in caps if c],
        }
        if cancelled_by:
            explain[r["id"]] = {**exp, "outcome": "suppressed"}
            continue
        sev = r.get("severity", "LOW")
        for cap in caps:
            if cap and SEVERITY_ORDER.index(cap) < SEVERITY_ORDER.index(sev):
                sev = cap
        final[r["id"]] = sev
        explain[r["id"]] = {**exp, "outcome": "fired", "severity": sev}
    return final, explain


def _targets(suppresses, rule):
    for t in suppresses:
        if t == "*" or t == rule["id"]:
            return True
        if t.startswith("TAX-"):
            for tax in rule.get("taxonomy_refs", []):
                if tax == t or tax.startswith(t + "-"):
                    return True
    return False


# --------------------------------------------------------------- main

def main() -> int:
    quiet = "--quiet" in sys.argv
    do_explain = "--explain" in sys.argv
    rules = [load(p) for p in sorted(RULES_DIR.glob("*.json"))]
    by_id = {r["id"]: r for r in rules}
    live_ids = {r["id"] for r in rules if r["lifecycle"]["status"] in LIVE_STATUSES}

    library = load(NEG_LIBRARY_PATH)
    neg = {n["negative_indicator_id"]: n for n in library["negative_indicators"]}
    overrides = library["overrides"]

    cases = []
    for label, path in CASE_FILES:
        if not path.exists():
            continue
        data = load(path)
        for bucket in ("benign", "malicious", "ambiguous"):
            for c in data.get(bucket, []):
                cases.append({**c, "_bucket": bucket, "_src": label})

    failures = []
    exercised = set()
    not_encoded = set()
    override_hits = set()

    print(f"Rule-runner — {len(rules)} rules ({len(live_ids)} PUBLISHED), "
          f"{len(neg)} negative indicators, {len(overrides)} overrides, {len(cases)} cases\n")

    for case in cases:
        final, explain = evaluate(case, rules, neg, overrides)
        fired = set(final)
        for e in explain.values():
            override_hits.update(e["overrides_active"])
        bucket, cid = case["_bucket"], case["id"]
        problems = []

        if bucket == "malicious":
            for rid in case.get("expected_rules", []):
                if rid not in by_id:
                    not_encoded.add(rid)
                elif rid not in fired:
                    e = explain.get(rid, {})
                    problems.append(f"expected {rid} to fire; got {e.get('outcome','no-match')} {e}")
                else:
                    exercised.add(rid)
        elif bucket == "benign":
            for rid in case.get("must_not_match", []):
                if rid in fired:
                    problems.append(f"{rid} FIRED on benign case — {explain[rid]}")
            live_fp = sorted(rid for rid in fired if rid in live_ids)
            if live_fp:
                problems.append(f"PUBLISHED rule(s) fired on benign case: {live_fp}")
        else:  # ambiguous
            live_fp = sorted(rid for rid in fired if rid in live_ids)
            if live_fp:
                problems.append(f"PUBLISHED rule(s) fired on ambiguous case: {live_fp}")

        tag = f"{cid} [{case['_src']}]"
        if problems:
            failures.append((tag, problems))
            print(f"  FAIL  {tag}")
            for p in problems:
                print(f"          {p}")
        elif not quiet:
            detail = f"fired={sorted(fired)}" if fired else "no finding"
            supp = {rid: e["cancelled_by"] for rid, e in explain.items() if e["outcome"] == "suppressed"}
            if supp:
                detail += f" suppressed={supp}"
            print(f"  ok    {tag:<36} {detail}")
            if do_explain:
                for rid, e in explain.items():
                    print(f"           · {rid}: {e}")

    # ---- coverage
    print("\nCoverage (COMPOSITE rules, PUBLISHED/APPROVED)")
    for rid in sorted(r["id"] for r in rules
                      if r["kind"] == "COMPOSITE" and r["lifecycle"]["status"] in {"PUBLISHED", "APPROVED"}):
        mark = "exercised" if rid in exercised else "NOT exercised by any malicious case"
        print(f"  {rid:<14} {by_id[rid]['lifecycle']['status']:<10} {mark}")
    print(f"\n  Hard-risk overrides exercised: {sorted(override_hits) or 'NONE'}")
    if not_encoded:
        print(f"  Corpus-referenced rules not yet encoded ({len(not_encoded)}): {sorted(not_encoded)}")

    # ---- traceability
    print("\nTraceability (PUBLISHED rules resolve to evidence)")
    manifest = {s["id"] for s in load(MANIFEST_PATH)["sources"]}
    mr_records = {r["evidence_id"] for r in load(EVIDENCE_RECORDS_PATH)["records"]} \
        if EVIDENCE_RECORDS_PATH.exists() else set()
    trace_fail = []
    for r in rules:
        if r["lifecycle"]["status"] != "PUBLISHED":
            continue
        for ref in r["evidence"]["source_references"]:
            if ref["source_id"] not in manifest:
                trace_fail.append(f"{r['id']}: source {ref['source_id']} missing from manifest")
            for eid in ref.get("manual_retrieval", {}).get("evidence_ids", []):
                if eid not in mr_records:
                    trace_fail.append(f"{r['id']}: manual evidence {eid} missing")
    if trace_fail:
        for t in trace_fail:
            print(f"  FAIL  {t}")
        failures.append(("traceability", trace_fail))
    else:
        print(f"  ok    all {len(live_ids)} PUBLISHED rules trace to manifest/evidence")

    print()
    if failures:
        print(f"{len(failures)} FAILURES across {len(cases)} cases + checks")
        return 1
    print(f"{len(cases)}/{len(cases)} cases behave as specified — {len(exercised)} rules exercised, "
          f"{len(override_hits)} overrides exercised, {len(not_encoded)} rules await encoding")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
