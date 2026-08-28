#!/usr/bin/env python3
import json, hashlib, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANUAL = ROOT / "knowledge" / "sources" / "manual-retrieval"
RAW = ROOT / "knowledge" / "sources" / "raw" / "manual-2026-08-28"

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

errors = []

evidence = json.loads((MANUAL / "evidence-records.json").read_text(encoding="utf-8"))
recon = json.loads((MANUAL / "source-reconciliation.json").read_text(encoding="utf-8"))

records = {r["evidence_id"]: r for r in evidence["records"]}

# ---- durable-truth guard (DEC-006 / ADR-0015): the live manifest must carry the manual layer
# additively, and its automated statuses must still match the frozen historical v1.1 copy.
LIVE_MANIFEST = ROOT / "knowledge" / "sources" / "verification-manifest.json"
HIST_MANIFEST = MANUAL / "verification-manifest-v1.1-original.json"
VALID_CLASSES = {"PRIMARY", "OFFICIAL_ALTERNATE", "OFFICIAL_REPLACEMENT", "INDUSTRY", "SECONDARY", "NONE"}

if not LIVE_MANIFEST.exists():
    errors.append("live verification-manifest.json is missing — restore it before reconciling")
elif not HIST_MANIFEST.exists():
    errors.append("frozen historical manifest (v1.1-original) is missing — cannot prove status preservation")
else:
    live = {s["id"]: s for s in json.loads(LIVE_MANIFEST.read_text())["sources"]}
    hist = {s["id"]: s for s in json.loads(HIST_MANIFEST.read_text())["sources"]}
    for sid, hsrc in hist.items():
        lsrc = live.get(sid)
        if lsrc is None:
            errors.append(f"{sid}: present in historical manifest but missing from live manifest")
            continue
        if lsrc.get("status") != hsrc.get("status"):
            errors.append(
                f"{sid}: automated status changed from {hsrc.get('status')} to {lsrc.get('status')} "
                f"— original automated verification must be preserved"
            )
    # every manual overlay must reference real evidence records and a valid evidence class
    for sid, lsrc in live.items():
        mr = lsrc.get("manual_retrieval")
        if not mr:
            continue
        if mr.get("evidence_class") not in VALID_CLASSES:
            errors.append(f"{sid}: manual_retrieval.evidence_class {mr.get('evidence_class')!r} not in the ADR-0015 hierarchy")
        for eid in mr.get("evidence_ids", []):
            if eid not in records:
                errors.append(f"{sid}: manual overlay cites unknown evidence id {eid}")
        if mr.get("preserves_original_status") not in (None, lsrc.get("status")):
            errors.append(f"{sid}: manual overlay preserves_original_status disagrees with the live status")

for eid, rec in records.items():
    path = RAW / rec["file"]
    if not path.exists():
        errors.append(f"{eid}: missing raw file {rec['file']}")
        continue
    actual = sha256(path)
    if actual != rec["sha256"]:
        errors.append(f"{eid}: sha256 mismatch for {rec['file']}")

for item in recon["items"]:
    for eid in item.get("evidence_ids", []):
        if eid not in records:
            errors.append(f"{item['source_id']}: unknown evidence id {eid}")

# Guardrails against accidental overstatement.
for item in recon["items"]:
    outcome = item["manual_outcome"]
    impact = item["rule_impact"]
    if "PARTIAL" in outcome and "PUBLISHABLE" in impact and "KEEP_DRAFT" not in impact:
        errors.append(f"{item['source_id']}: partial evidence marked publishable without narrowing/review")

if errors:
    print("MANUAL EVIDENCE CHECK: FAIL")
    for e in errors:
        print(" -", e)
    sys.exit(1)

print("MANUAL EVIDENCE CHECK: PASS")
print(f" evidence records: {len(records)}")
print(f" reconciliation items: {len(recon['items'])}")
print(" integrity hashes: OK")
print(" partial-evidence publication guardrail: OK")
