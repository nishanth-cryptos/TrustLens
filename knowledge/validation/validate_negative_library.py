"""Static integrity validator for the negative-indicator & suppression library (WP3, G-07).

Checks the library file itself and its cross-references, independently of the rule linter:

  * ids unique; required fields present; effect / category / strength in the controlled vocabulary;
  * SUPPRESS_INDICATOR effects name real POSITIVE indicators to neutralise;
  * CAP_SEVERITY effects carry a severity_cap; other effects do not;
  * hard-risk overrides are explicit: unique ids, a condition referencing only known POSITIVE
    indicators, and an applicability (rule ids or families);
  * applicable_rule_families / override applies_to_families are '*' or a valid TAX **category** id
    (TAX-NN). Suppression/override scope is CATEGORY-level: a rule's category membership is derived by
    rollup from its taxonomy_refs, and the runtime loader (P3-WP2) matches negative/override scope at
    category granularity, so a subcategory-scoped negative/override could never be acted on consistently.
    Both authoring and runtime therefore agree on category-only family scope (DET-001-WP2 §Taxonomy);
  * language/script present;
  * every negative id referenced by any rule's suppressed_by resolves and is not DEPRECATED;
  * no PUBLISHED rule depends on an unresolved suppression reference.

Usage:  .venv/bin/python knowledge/validation/validate_negative_library.py
Exit 0 = library is internally consistent and every rule reference resolves.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB_PATH = ROOT / "knowledge" / "indicators" / "negative-indicator-library-v1.json"
REGISTRY_PATH = ROOT / "knowledge" / "indicators" / "indicator-registry-v0.json"
TAXONOMY_PATH = ROOT / "knowledge" / "taxonomies" / "scam-taxonomy.json"
RULES_DIR = ROOT / "knowledge" / "rules"

EFFECTS = {"SUPPRESS_RULE", "SUPPRESS_INDICATOR", "CAP_SEVERITY", "CONTEXT_ONLY"}
STRENGTHS = {"WEAK", "MODERATE", "STRONG"}
SEVERITIES = {"LOW", "MEDIUM", "HIGH"}
REQUIRED = ["negative_indicator_id", "version", "status", "name", "description", "category",
            "suppression_effect", "strength", "applicable_rule_families", "language", "script",
            "false_negative_risk", "change_history"]


def load(p):
    return json.loads(p.read_text())


def leaves(cond):
    if isinstance(cond, str):
        yield cond
        return
    for _, v in cond.items():
        for x in v:
            yield from leaves(x)


def main() -> int:
    errs = []
    lib = load(LIB_PATH)
    registry = load(REGISTRY_PATH)
    positives = {i["id"] for i in registry["indicators"] if i["polarity"] == "POSITIVE"}
    taxonomy = load(TAXONOMY_PATH)
    # Suppression/override family scope is CATEGORY-level only (TAX-NN); subcategories are NOT valid
    # scope targets (runtime matches at category granularity — DET-001-WP2). Kept in sync with the
    # runtime loader's validate_references (knowledge/runtime/indexes.py).
    family_scope = {c["id"] for c in taxonomy["categories"]}

    categories = set(lib["categories"])
    ni = lib["negative_indicators"]
    ids = [n["negative_indicator_id"] for n in ni]
    if len(ids) != len(set(ids)):
        errs.append("duplicate negative_indicator_id")

    by_id = {n["negative_indicator_id"]: n for n in ni}
    for n in ni:
        nid = n["negative_indicator_id"]
        for f in REQUIRED:
            if f not in n:
                errs.append(f"{nid}: missing required field {f}")
        if n.get("suppression_effect") not in EFFECTS:
            errs.append(f"{nid}: bad effect {n.get('suppression_effect')}")
        if n.get("category") not in categories:
            errs.append(f"{nid}: category {n.get('category')} not in library vocabulary")
        if n.get("strength") not in STRENGTHS:
            errs.append(f"{nid}: bad strength {n.get('strength')}")
        if n.get("status") not in ("ACTIVE", "DEPRECATED"):
            errs.append(f"{nid}: bad status {n.get('status')}")
        eff = n.get("suppression_effect")
        if eff == "SUPPRESS_INDICATOR":
            tgts = n.get("suppresses_indicators", [])
            if not tgts:
                errs.append(f"{nid}: SUPPRESS_INDICATOR must name suppresses_indicators")
            for t in tgts:
                if t not in positives:
                    errs.append(f"{nid}: neutralises unknown positive indicator {t}")
        if eff == "CAP_SEVERITY" and n.get("severity_cap") not in SEVERITIES:
            errs.append(f"{nid}: CAP_SEVERITY needs a valid severity_cap")
        if eff != "CAP_SEVERITY" and "severity_cap" in n:
            errs.append(f"{nid}: severity_cap only valid on CAP_SEVERITY")
        for fam in n.get("applicable_rule_families", []):
            if fam != "*" and fam not in family_scope:
                errs.append(f"{nid}: applicable_rule_family {fam} is not a TAX category id (category-level scope only)")
        if not n.get("language") or not n.get("script"):
            errs.append(f"{nid}: language/script required")
        if n.get("false_negative_risk") not in ("LOW", "MEDIUM", "HIGH"):
            errs.append(f"{nid}: false_negative_risk must be LOW/MEDIUM/HIGH")

    # overrides
    ov_ids = [o["override_id"] for o in lib["overrides"]]
    if len(ov_ids) != len(set(ov_ids)):
        errs.append("duplicate override_id")
    for o in lib["overrides"]:
        oid = o["override_id"]
        for lf in leaves(o["condition"]):
            if lf not in positives:
                errs.append(f"{oid}: override condition references unknown positive {lf}")
        if not o.get("applies_to_rules") and not o.get("applies_to_families"):
            errs.append(f"{oid}: override must declare applies_to_rules or applies_to_families")
        for fam in o.get("applies_to_families", []):
            if fam not in family_scope:
                errs.append(f"{oid}: applies_to_family {fam} not a TAX category id (category-level scope only)")
        for cat in o.get("blocks_suppression_categories", []):
            if cat not in categories:
                errs.append(f"{oid}: blocks unknown category {cat}")

    # cross-check: every negative referenced by a rule resolves and is ACTIVE
    referenced = set()
    published_bad = []
    for p in sorted(RULES_DIR.glob("*.json")):
        r = load(p)
        for s in r.get("logic", {}).get("suppressed_by", []):
            referenced.add(s)
            if s not in by_id:
                errs.append(f"{r['id']}: suppressed_by references unknown negative {s}")
                if r["lifecycle"]["status"] == "PUBLISHED":
                    published_bad.append((r["id"], s))
            elif by_id[s]["status"] == "DEPRECATED":
                errs.append(f"{r['id']}: suppressed_by references DEPRECATED negative {s}")
    if published_bad:
        errs.append(f"PUBLISHED rules depend on unresolved suppression refs: {published_bad}")

    # report
    if errs:
        print("NEGATIVE-LIBRARY CHECK: FAIL")
        for e in errs:
            print(" -", e)
        return 1
    from collections import Counter
    print("NEGATIVE-LIBRARY CHECK: PASS")
    print(f" negative indicators: {len(ni)}  overrides: {len(lib['overrides'])}")
    print(f" effects: {dict(Counter(n['suppression_effect'] for n in ni))}")
    print(f" referenced by rules: {sorted(referenced)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
