"""TrustLens published-knowledge-bundle builder — Phase 2 WP8 (ADR-0004).

Assembles the RUNTIME-NECESSARY knowledge into an immutable, versioned, hash-addressed bundle:
rules, indicator registry/families, negative-indicator library, taxonomy + dimensions, the rule and
extraction schemas, and evidence METADATA (verification manifest + evidence records). It deliberately
EXCLUDES raw PDFs, the test corpora, the extraction-coverage matrix and the validators — the runtime
engine needs evidence references, not whole documents or test data.

The build is DETERMINISTIC: the content_digest is a SHA-256 over the sorted set of
'<bundle_path>=<sha256>' lines, independent of build time or machine. commit_sha and created_at are
recorded as provenance but are excluded from the digest, so the same commit always yields the same
digest. Fully offline — no network, no subprocess (commit SHA is read from GITHUB_SHA or .git/HEAD as
plain files).

Usage:
  python knowledge/publish/build_bundle.py                 # print the manifest (dry run), no files written
  python knowledge/publish/build_bundle.py --out build/bundle   # also copy files + write bundle-manifest.json
  python knowledge/publish/build_bundle.py --gate PASS --out DIR # record that the publication gate passed

This is a knowledge-PUBLISHING tool (Phase 2), not a Phase-3 runtime service.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
K = ROOT / "knowledge"

MANIFEST_SCHEMA_VERSION = "1.0.0"
BUNDLE_VERSION = "1.0.0"

# The extraction contract schemas (WP2). They carry no per-file version field; the bundle pins them to
# the WP2 contract version, sourced from the envelope schema's envelope_version const.
EXTRACTION_SCHEMA_FILES = [
    "input-envelope.schema.json",
    "observation.schema.json",
    "url-observation.schema.json",
    "indicator-observation.schema.json",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_commit_sha() -> str:
    """Commit SHA from the CI env or .git/HEAD, read as plain files (no subprocess, no network)."""
    env = os.environ.get("GITHUB_SHA")
    if env:
        return env.strip().lower()
    head = ROOT / ".git" / "HEAD"
    if not head.exists():
        return "unknown"
    ref = head.read_text().strip()
    if ref.startswith("ref:"):
        ref_path = ROOT / ".git" / ref.split(" ", 1)[1].strip()
        if ref_path.exists():
            return ref_path.read_text().strip().lower()
        # packed refs fallback
        packed = ROOT / ".git" / "packed-refs"
        if packed.exists():
            want = ref.split(" ", 1)[1].strip()
            for line in packed.read_text().splitlines():
                if line and not line.startswith(("#", "^")) and line.endswith(want):
                    return line.split(" ", 1)[0].strip().lower()
        return "unknown"
    return ref.lower()  # detached HEAD: raw sha


def _members():
    """Yield (bundle_path, source_abs_path) for every file that belongs in the runtime bundle.

    Order of discovery does not matter — the manifest sorts by bundle_path.
    """
    # rules: every encoded rule (the engine filters to lifecycle.status == PUBLISHED at load time)
    for p in sorted((K / "rules").glob("*.json")):
        yield f"rules/{p.name}", p
    # indicators
    for name in ("indicator-registry-v0.json", "indicator-families-v1.json",
                 "negative-indicator-library-v1.json"):
        yield f"indicators/{name}", K / "indicators" / name
    # taxonomy
    yield "taxonomy/scam-taxonomy.json", K / "taxonomies" / "scam-taxonomy.json"
    yield "taxonomy/dimensions-v1.json", K / "taxonomies" / "dimensions-v1.json"
    # schemas: rule schema + extraction contracts (load-time validation)
    yield "schemas/rule.schema.json", K / "schemas" / "rule.schema.json"
    for name in EXTRACTION_SCHEMA_FILES:
        yield f"schemas/{name}", K / "schemas" / name
    # evidence METADATA references only (never the PDFs)
    yield "sources/verification-manifest.json", K / "sources" / "verification-manifest.json"
    yield "sources/evidence-records.json", K / "sources" / "manual-retrieval" / "evidence-records.json"


def _component_versions() -> dict:
    def v(path, *keys, const_path=None):
        d = json.loads((path).read_text())
        if const_path:
            node = d
            for k in const_path:
                node = node[k]
            return str(node)
        for k in keys:
            if k in d:
                return str(d[k])
        return ""
    return {
        "rule_schema": v(K / "schemas" / "rule.schema.json",
                         const_path=("properties", "schema_version", "const")),
        "taxonomy": v(K / "taxonomies" / "scam-taxonomy.json", "taxonomy_version"),
        "dimensions": v(K / "taxonomies" / "dimensions-v1.json", "dimensions_version"),
        "indicator_registry": v(K / "indicators" / "indicator-registry-v0.json", "registry_version"),
        "indicator_families": v(K / "indicators" / "indicator-families-v1.json", "families_version"),
        "negative_library": v(K / "indicators" / "negative-indicator-library-v1.json", "library_version"),
        "evidence_manifest": v(K / "sources" / "verification-manifest.json", "manifest_version", "version"),
        "evidence_records": v(K / "sources" / "manual-retrieval" / "evidence-records.json", "version"),
        "extraction_schemas": v(K / "schemas" / "input-envelope.schema.json",
                                const_path=("properties", "envelope_version", "const")),
    }


def _counts(files) -> dict:
    rules = [json.loads((K / "rules" / Path(f["path"]).name).read_text())
             for f in files if f["path"].startswith("rules/")]
    reg = json.loads((K / "indicators" / "indicator-registry-v0.json").read_text())
    neg = json.loads((K / "indicators" / "negative-indicator-library-v1.json").read_text())
    tax = json.loads((K / "taxonomies" / "scam-taxonomy.json").read_text())
    dims = json.loads((K / "taxonomies" / "dimensions-v1.json").read_text())
    return {
        "files": len(files),
        "rules_total": len(rules),
        "rules_published": sum(1 for r in rules if r["lifecycle"]["status"] == "PUBLISHED"),
        "positive_indicators": len(reg["indicators"]),
        "negative_indicators": len(neg["negative_indicators"]),
        "taxonomy_categories": len(tax["categories"]),
        "taxonomy_subcategories": sum(len(c["subcategories"]) for c in tax["categories"]),
        "dimension_terms": sum(len(b["terms"]) for b in dims["dimensions"].values()),
    }


def compute_manifest(gate: str = "NOT_RECORDED") -> dict:
    """Compute the bundle manifest WITHOUT writing any files. Deterministic apart from
    created_at/commit_sha, which are excluded from content_digest."""
    from datetime import datetime, timezone
    files = []
    for bundle_path, src in _members():
        if not src.exists():
            raise FileNotFoundError(f"bundle member missing: {src}")
        data = src.read_bytes()
        files.append({"path": bundle_path, "sha256": sha256_bytes(data), "bytes": len(data)})
    files.sort(key=lambda f: f["path"])
    digest_input = "\n".join(f"{f['path']}={f['sha256']}" for f in files)
    content_digest = sha256_bytes(digest_input.encode("utf-8"))
    return {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "bundle_version": BUNDLE_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "commit_sha": _read_commit_sha(),
        "gate": gate,
        "content_digest": content_digest,
        "component_versions": _component_versions(),
        "integrity": {"algorithm": "sha256", "files": files},
        "counts": _counts(files),
        "notes": "Runtime bundle: rules + indicators + negatives + taxonomy/dimensions + schemas + "
                 "evidence metadata. Excludes raw PDFs, test corpora, coverage matrix, validators (ADR-0004 §5.2).",
    }


def build(out_dir: Path, gate: str = "NOT_RECORDED") -> dict:
    """Materialise the bundle into out_dir and write bundle-manifest.json. Returns the manifest."""
    manifest = compute_manifest(gate)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    for bundle_path, src in _members():
        dst = out_dir / bundle_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    (out_dir / "bundle-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main() -> int:
    out_dir = None
    gate = "NOT_RECORDED"
    if "--out" in sys.argv:
        i = sys.argv.index("--out")
        out_dir = Path(sys.argv[i + 1]) if i + 1 < len(sys.argv) else None
    if "--gate" in sys.argv:
        i = sys.argv.index("--gate")
        gate = sys.argv[i + 1] if i + 1 < len(sys.argv) else gate
    if out_dir is not None:
        if not out_dir.is_absolute():
            out_dir = ROOT / out_dir
        manifest = build(out_dir, gate)
        print(f"bundle built -> {out_dir}")
        print(f" content_digest {manifest['content_digest']}")
        print(f" files {manifest['counts']['files']}  rules {manifest['counts']['rules_total']} "
              f"({manifest['counts']['rules_published']} published)  commit {manifest['commit_sha']}")
    else:
        print(json.dumps(compute_manifest(gate), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
