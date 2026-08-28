"""Phase 1 gate evidence — cross-artifact consistency check.

Verifies that the three machine-readable knowledge files agree with each other
and with the counts asserted in RESEARCH-001..005. Run from anywhere:

    python3 knowledge/validation/phase1_consistency_check.py

Exit code 0 = all checks pass. Cited as evidence by GATE-001.

This is a *consistency* checker, not a schema validator. The rule JSON Schema
and its validator are Phase 2 deliverables (ADR-0003, DEC-004); this file is the
interim mechanism that keeps the Phase 1 artifacts honest until then.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

results = []


def check(name, ok, detail=""):
    results.append((ok, name, detail))


manifest = json.loads((ROOT / "knowledge/sources/verification-manifest.json").read_text())
taxonomy = json.loads((ROOT / "knowledge/taxonomies/scam-taxonomy.json").read_text())
corpus = json.loads((ROOT / "knowledge/seed-data/seed-corpus-v1.json").read_text())

r001 = (ROOT / "docs/01-research/RESEARCH-001-source-inventory.md").read_text()
r002 = (ROOT / "docs/01-research/RESEARCH-002-scam-taxonomy.md").read_text()
r004 = (ROOT / "docs/01-research/RESEARCH-004-evidence-matrix.md").read_text()

# ---------------------------------------------------------------- manifest
src_ids = [s["id"] for s in manifest["sources"]]
check("manifest: source IDs unique", len(src_ids) == len(set(src_ids)),
      f"{len(src_ids)} sources")
check("manifest: total matches summary",
      len(src_ids) == manifest["summary"]["total_sources"],
      f'{len(src_ids)} vs {manifest["summary"]["total_sources"]}')

grades = {}
for s in manifest["sources"]:
    grades[s["status"]] = grades.get(s["status"], 0) + 1
summary = manifest["summary"]
for key, grade in [("primary_verified", "PRIMARY_VERIFIED"),
                   ("primary_cited_unverified", "PRIMARY_CITED_UNVERIFIED"),
                   ("index_only", "INDEX_ONLY"),
                   ("retrieval_failed", "RETRIEVAL_FAILED")]:
    check(f"manifest: {grade} count matches summary",
          grades.get(grade, 0) == summary[key],
          f'actual {grades.get(grade, 0)} vs stated {summary[key]}')

check("manifest: PRIMARY_VERIFIED fraction is stated as verified-only",
      summary["primary_verified_fraction"].startswith(
          f'{summary["primary_verified"]}/{summary["total_sources"]}'),
      summary["primary_verified_fraction"])

check("manifest: every grade is in the glossary vocabulary",
      set(grades) <= {"PRIMARY_VERIFIED", "PRIMARY_CITED_UNVERIFIED",
                      "INDEX_ONLY", "RETRIEVAL_FAILED", "SECONDARY"},
      str(sorted(grades)))

check("manifest: every PRIMARY_VERIFIED source carries located quotations",
      all(s.get("verified_quotes") for s in manifest["sources"]
          if s["status"] == "PRIMARY_VERIFIED"),
      str([s["id"] for s in manifest["sources"]
           if s["status"] == "PRIMARY_VERIFIED" and not s.get("verified_quotes")]))

check("manifest: every unverified source records what was being tested",
      all(s.get("claim_under_test") or s.get("note") for s in manifest["sources"]
          if s["status"] != "PRIMARY_VERIFIED"),
      str([s["id"] for s in manifest["sources"] if s["status"] != "PRIMARY_VERIFIED"
           and not (s.get("claim_under_test") or s.get("note"))]))

# RESEARCH-001 headline table
r001_counts = dict(re.findall(r"\| `(\w+)` \| (\d+) \|", r001))
for grade, key in [("PRIMARY_VERIFIED", "primary_verified"),
                   ("PRIMARY_CITED_UNVERIFIED", "primary_cited_unverified"),
                   ("INDEX_ONLY", "index_only"),
                   ("RETRIEVAL_FAILED", "retrieval_failed")]:
    if grade in r001_counts:
        check(f"RESEARCH-001 §2 {grade} matches manifest",
              int(r001_counts[grade]) == grades.get(grade, 0),
              f'doc {r001_counts[grade]} vs manifest {grades.get(grade, 0)}')

# ---------------------------------------------------------------- taxonomy
cats = taxonomy["categories"]
subs = [sub for c in cats for sub in c["subcategories"]]
cat_ids = [c["id"] for c in cats]
sub_ids = [s["id"] for s in subs]

check("taxonomy: category IDs unique", len(cat_ids) == len(set(cat_ids)))
check("taxonomy: subcategory IDs unique", len(sub_ids) == len(set(sub_ids)))
check("taxonomy: top-level count matches coverage",
      len(cats) == taxonomy["coverage"]["top_level"]["total"],
      f'{len(cats)} vs {taxonomy["coverage"]["top_level"]["total"]}')
check("taxonomy: subcategory count matches coverage",
      len(subs) == taxonomy["coverage"]["subcategories"]["total"],
      f'{len(subs)} vs {taxonomy["coverage"]["subcategories"]["total"]}')
check("taxonomy: subcategory IDs nest under their parent",
      all(s["id"].startswith(c["id"] + "-") for c in cats for s in c["subcategories"]))

ev_top = {}
for c in cats:
    ev_top[c["evidence"]] = ev_top.get(c["evidence"], 0) + 1
ev_sub = {}
for s in subs:
    ev_sub[s["evidence"]] = ev_sub.get(s["evidence"], 0) + 1
check("taxonomy: top-level evidence tally matches coverage",
      ev_top.get("VERIFIED", 0) == taxonomy["coverage"]["top_level"]["verified"]
      and ev_top.get("PARTIAL", 0) == taxonomy["coverage"]["top_level"]["partial"],
      f'{ev_top} vs {taxonomy["coverage"]["top_level"]}')
check("taxonomy: subcategory evidence tally matches coverage",
      ev_sub.get("VERIFIED", 0) == taxonomy["coverage"]["subcategories"]["verified"]
      and ev_sub.get("PARTIAL", 0) == taxonomy["coverage"]["subcategories"]["partial"]
      and ev_sub.get("UNVERIFIED", 0) == taxonomy["coverage"]["subcategories"]["unverified"],
      f'{ev_sub} vs {taxonomy["coverage"]["subcategories"]}')

# every source cited by the taxonomy must exist in the manifest
tax_srcs = {s for c in cats for s in c.get("sources", [])}
tax_srcs |= {s for sub in subs for s in sub.get("sources", [])}
tax_srcs = {s for s in tax_srcs if s.startswith("SRC-")}
check("taxonomy: every cited SRC-* resolves in the manifest",
      tax_srcs <= set(src_ids), f"dangling: {sorted(tax_srcs - set(src_ids))}")

# RESEARCH-002 asserted counts
m = re.search(r"\| \*\*Total\*\* \| \*\*(\d+)\*\* \|", r002)
if m:
    check("RESEARCH-002 §4 subcategory total matches taxonomy",
          int(m.group(1)) == len(subs), f"doc {m.group(1)} vs json {len(subs)}")

# ---------------------------------------------------------------- rules
rule_rows = re.findall(
    r"\| `(TL-[A-Z]+-\d+)` \| ([^|]+?) \|[^|]*\|[^|]*\|[^|]*\| \*\*(\w+)\*\* \| ([^|]+?) \|", r004)
rules = {rid: {"legacy": legacy.strip(), "verdict": verdict, "impl": impl.strip()}
         for rid, legacy, verdict, impl in rule_rows}
check("RESEARCH-004: 30 starter rules parsed", len(rules) == 30, f"{len(rules)} parsed")

verdicts = {}
for r in rules.values():
    verdicts[r["verdict"]] = verdicts.get(r["verdict"], 0) + 1
check("RESEARCH-004: verdict tally is 17/9/4 as stated in §3 (v1.2, post-RESEARCH-006)",
      verdicts.get("SUPPORTED") == 17 and verdicts.get("PARTIAL") == 9
      and verdicts.get("UNSUPPORTED") == 4, str(verdicts))

publishable = {rid for rid, r in rules.items() if r["verdict"] != "UNSUPPORTED"}
implementable = {rid for rid, r in rules.items() if r["impl"].startswith("YES")}
check("RESEARCH-004: 22 rules both evidenced and implementable (v1.2, post-RESEARCH-006)",
      len(publishable & implementable) == 22,
      f"{len(publishable & implementable)}")

# ---------------------------------------------------------------- corpus
items = corpus["benign"] + corpus["malicious"] + corpus["ambiguous"]
ids = [i["id"] for i in items]
check("corpus: case IDs unique", len(ids) == len(set(ids)), f"{len(ids)} cases")
check("corpus: composition matches contents",
      corpus["composition"]["benign"] == len(corpus["benign"])
      and corpus["composition"]["malicious"] == len(corpus["malicious"])
      and corpus["composition"]["ambiguous"] == len(corpus["ambiguous"])
      and corpus["composition"]["total"] == len(items),
      json.dumps(corpus["composition"]))
check("corpus: provenance is SYNTHETIC (CON-005)",
      corpus["provenance"] == "SYNTHETIC")
check("corpus: benign authored first (CONF-002) — benign IDs lead",
      all(i["id"].startswith("B-") for i in corpus["benign"]))
check("corpus: every benign case declares must_not_match",
      all(i.get("must_not_match") for i in corpus["benign"]))
check("corpus: every case declares an expected_outcome",
      all(i.get("expected_outcome") for i in items))

ref_rules = {r for i in items for r in i.get("expected_rules", []) + i.get("must_not_match", [])}
check("corpus: every referenced rule ID exists in RESEARCH-004",
      ref_rules <= set(rules), f"dangling: {sorted(ref_rules - set(rules))}")

unsup_refs = {r for i in corpus["malicious"] for r in i.get("expected_rules", [])
              if rules.get(r, {}).get("verdict") == "UNSUPPORTED"}
check("corpus: no malicious case expects an UNSUPPORTED rule to fire",
      not unsup_refs, f"offenders: {sorted(unsup_refs)}")

deferred_refs = {r for i in corpus["malicious"] for r in i.get("expected_rules", [])
                 if rules.get(r, {}).get("impl", "").startswith(("⚠️", "🟡"))}
check("corpus: no malicious case expects a DEFERRED rule to fire",
      not deferred_refs, f"offenders: {sorted(deferred_refs)}")

# ---------------------------------------------------------------- report
fails = [r for r in results if not r[0]]
for ok, name, detail in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"   [{detail}]" if detail and not ok else ""))
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
sys.exit(1 if fails else 0)
