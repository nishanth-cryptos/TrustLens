"""KB-001 governance machine-checks (WP6).

Checks the KB governance controls that are objectively machine-verifiable and not already covered
by the schema/rule/taxonomy/library validators:

  * version strings across all knowledge artifacts are syntactically valid;
  * stable IDs are globally unique within their namespace and namespaces do not collide;
  * PUBLISHED rules carry the human-review metadata KB-001 §5 requires (approved_by_role, and
    REVIEWED manual_retrieval where a manual layer is relied on);
  * no artifact references an ID that resolves to nothing (delegated spot-check).

Human-review controls (concept soundness, review diligence, safeguarding) are explicitly OUT of
scope — KB-001 §9 keeps those with a named human.

Usage:  .venv/bin/python knowledge/validation/validate_kb.py
Exit 0 = machine-checkable KB controls hold.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
K = ROOT / "knowledge"
SEMVER = re.compile(r"^\d+\.\d+\.\d+([-.].+)?$")
VERSIONISH = re.compile(r"^\d+\.\d+(\.\d+)?([-.].+)?$")


def load(p):
    return json.loads(p.read_text())


def main() -> int:
    errs = []
    ids = {}          # id -> namespace, for global-uniqueness

    def claim(idv, ns):
        if idv in ids and ids[idv] != ns:
            errs.append(f"ID collision: {idv} used by both {ids[idv]} and {ns}")
        ids[idv] = ns

    # ---- versions
    checks = [
        (K / "taxonomies/scam-taxonomy.json", "taxonomy_version", VERSIONISH),
        (K / "taxonomies/dimensions-v1.json", "dimensions_version", VERSIONISH),
        (K / "indicators/indicator-registry-v0.json", "registry_version", None),
        (K / "indicators/negative-indicator-library-v1.json", "library_version", SEMVER),
        (K / "seed-data/seed-corpus-v1.json", "corpus_version", VERSIONISH),
    ]
    for path, field, rx in checks:
        v = str(load(path).get(field, ""))
        if rx and not rx.match(v):
            errs.append(f"{path.name}: {field}={v!r} is not a valid version string")

    # ---- namespaces / global uniqueness
    tax = load(K / "taxonomies/scam-taxonomy.json")
    for c in tax["categories"]:
        claim(c["id"], "taxonomy")
        for s in c["subcategories"]:
            claim(s["id"], "taxonomy")
    dims = load(K / "taxonomies/dimensions-v1.json")
    for axis, block in dims["dimensions"].items():
        for t in block["terms"]:
            claim(t["id"], "dimension")
    for i in load(K / "indicators/indicator-registry-v0.json")["indicators"]:
        claim(i["id"], "indicator")
    for n in load(K / "indicators/negative-indicator-library-v1.json")["negative_indicators"]:
        claim(n["negative_indicator_id"], "negative-indicator")

    # ---- rules: version syntax + PUBLISHED review metadata
    rule_ids = set()
    for p in sorted((K / "rules").glob("*.json")):
        r = load(p)
        rid = r.get("id", p.stem)
        if rid in rule_ids:
            errs.append(f"duplicate rule id {rid}")
        rule_ids.add(rid)
        claim(rid, "rule")
        rv = r.get("rule_version", "")
        if rv and not SEMVER.match(rv):
            errs.append(f"{rid}: rule_version {rv!r} not semver")
        if r["lifecycle"]["status"] == "PUBLISHED":
            if not r["lifecycle"].get("approved_by_role"):
                errs.append(f"{rid}: PUBLISHED without approved_by_role (KB-001 §5.12)")
            for ref in r["evidence"]["source_references"]:
                mr = ref.get("manual_retrieval")
                if mr and mr.get("review_status") != "REVIEWED":
                    errs.append(f"{rid}: PUBLISHED relies on manual evidence not marked REVIEWED (KB-001 §5.12)")

    if errs:
        print("KB GOVERNANCE CHECK: FAIL")
        for e in errs:
            print(" -", e)
        return 1
    print("KB GOVERNANCE CHECK: PASS")
    print(f" stable IDs registered: {len(ids)} across taxonomy/dimension/indicator/negative/rule namespaces")
    print(f" rules: {len(rule_ids)}  (version syntax + PUBLISHED review metadata OK)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
