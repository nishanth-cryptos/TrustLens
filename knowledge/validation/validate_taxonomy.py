"""Taxonomy + dimension integrity validator (WP5) and rule↔taxonomy reconciliation.

Static checks the phase-1 consistency checker does not cover:

  * dimension registries: ids unique, prefix-correct, required fields, valid status;
  * every subcategory dimension tag resolves to a real dimension id;
  * every subcategory carries evidence_maturity from the controlled vocabulary + status/version;
  * TAX-11 (and any DEFERRED category) carries no executable rule;
  * every rule taxonomy_ref resolves and is not DEPRECATED;
  * a PUBLISHED, non-HEURISTIC rule may not sit on a subcategory whose evidence_maturity is
    NO_PRIMARY_SOURCE / UNVERIFIED (RESEARCH-002 §5.1);
  * no duplicate taxonomy ids.

Usage:  .venv/bin/python knowledge/validation/validate_taxonomy.py
Exit 0 = taxonomy internally consistent and every rule reconciles.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TAX_PATH = ROOT / "knowledge" / "taxonomies" / "scam-taxonomy.json"
DIM_PATH = ROOT / "knowledge" / "taxonomies" / "dimensions-v1.json"
RULES_DIR = ROOT / "knowledge" / "rules"

MATURITY = {"PRIMARY", "PRIMARY_MANUAL", "PRIMARY_PARTIAL", "OFFICIAL_ALTERNATE",
            "OFFICIAL_REPLACEMENT", "INDUSTRY", "PARTIAL", "NO_PRIMARY_SOURCE", "UNVERIFIED"}
PUBLISHABLE_MATURITY = {"PRIMARY", "PRIMARY_MANUAL", "PRIMARY_PARTIAL",
                        "OFFICIAL_ALTERNATE", "OFFICIAL_REPLACEMENT", "INDUSTRY", "PARTIAL"}
DIM_KEYS = ["fraud_objective", "technical_mechanism", "typical_channels",
            "social_engineering_tactics", "requested_user_actions", "potential_harm"]
KEY_TO_AXIS = {"fraud_objective": "fraud_objective", "technical_mechanism": "technical_mechanism",
               "typical_channels": "channel", "social_engineering_tactics": "social_engineering_tactic",
               "requested_user_actions": "requested_user_action", "potential_harm": "potential_harm"}


def load(p):
    return json.loads(p.read_text())


def main() -> int:
    errs = []
    tax = load(TAX_PATH)
    dims = load(DIM_PATH)

    # dimension registries
    dim_ids = {}
    for axis, block in dims["dimensions"].items():
        prefix = block["id_prefix"]
        ids = set()
        for t in block["terms"]:
            tid = t["id"]
            if tid in ids:
                errs.append(f"dimension {axis}: duplicate id {tid}")
            ids.add(tid)
            if not tid.startswith(prefix + "-"):
                errs.append(f"dimension {tid}: wrong prefix for axis {axis} (expect {prefix}-)")
            for f in ("name", "definition", "status", "version", "evidence_maturity", "change_history"):
                if f not in t:
                    errs.append(f"dimension {tid}: missing {f}")
            if t.get("status") not in ("ACTIVE", "DEPRECATED"):
                errs.append(f"dimension {tid}: bad status")
        dim_ids[axis] = ids

    # taxonomy
    cat_ids, sub_ids = set(), set()
    sub_by_id = {}
    deferred_subs = set()
    for c in tax["categories"]:
        if c["id"] in cat_ids:
            errs.append(f"duplicate category id {c['id']}")
        cat_ids.add(c["id"])
        for s in c["subcategories"]:
            sid = s["id"]
            if sid in sub_ids:
                errs.append(f"duplicate subcategory id {sid}")
            sub_ids.add(sid)
            sub_by_id[sid] = s
            if s.get("evidence_maturity") not in MATURITY:
                errs.append(f"{sid}: evidence_maturity {s.get('evidence_maturity')} not in vocabulary")
            for f in ("status", "version"):
                if f not in s:
                    errs.append(f"{sid}: missing {f}")
            if s.get("detection_status") == "DEFERRED_SAFEGUARDING" or c.get("detection_status") == "DEFERRED_SAFEGUARDING":
                deferred_subs.add(sid)
            for key, tags in s.get("dimensions", {}).items():
                if key not in DIM_KEYS:
                    errs.append(f"{sid}: unknown dimension key {key}")
                    continue
                for tag in tags:
                    if tag not in dim_ids[KEY_TO_AXIS[key]]:
                        errs.append(f"{sid}: dimension tag {tag} not in {KEY_TO_AXIS[key]} registry")

    # rule reconciliation
    published_bad = []
    for p in sorted(RULES_DIR.glob("*.json")):
        r = load(p)
        status = r["lifecycle"]["status"]
        verdict = r["evidence"]["verdict"]
        for ref in r.get("taxonomy_refs", []):
            if ref not in cat_ids and ref not in sub_ids:
                errs.append(f"{r['id']}: taxonomy_ref {ref} resolves to nothing")
                continue
            s = sub_by_id.get(ref)
            if s and s.get("status") == "DEPRECATED":
                errs.append(f"{r['id']}: taxonomy_ref {ref} is DEPRECATED")
            # detection-deferred categories must carry no executable rule
            if ref in deferred_subs:
                errs.append(f"{r['id']}: references detection-DEFERRED taxonomy {ref} — no rule may be authored there")
            # publication gate on maturity (RESEARCH-002 §5.1)
            if s and status == "PUBLISHED" and verdict in ("SUPPORTED", "PARTIAL"):
                if s["evidence_maturity"] not in PUBLISHABLE_MATURITY:
                    published_bad.append(f"{r['id']} on {ref} (maturity {s['evidence_maturity']})")

    if published_bad:
        errs.append("PUBLISHED non-heuristic rules on non-publishable-maturity subcategories: "
                    + "; ".join(published_bad))

    if errs:
        print("TAXONOMY CHECK: FAIL")
        for e in errs:
            print(" -", e)
        return 1
    total_terms = sum(len(v) for v in dim_ids.values())
    print("TAXONOMY CHECK: PASS")
    print(f" categories: {len(cat_ids)}  subcategories: {len(sub_ids)}  dimension terms: {total_terms}")
    print(f" detection-deferred: {sorted(deferred_subs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
