"""TrustLens bundle-integrity validator — Phase 2 WP8 (ADR-0004).

Proves the published-knowledge-bundle architecture holds, without shipping a committed bundle:

  * the computed manifest is valid against bundle-manifest.schema.json (Draft 2020-12);
  * every file the manifest records exists and its SHA-256 + byte count match the file on disk
    (re-hashed here independently of the builder);
  * the content_digest recomputes from the recorded (path, hash) set;
  * the build is DETERMINISTIC — computed twice, the content digest and per-file hashes are identical;
  * every component version is pinned (present and non-empty);
  * the runtime bundle EXCLUDES raw PDFs and test/dev data (no path leaves the allowed prefixes).

It does not write a bundle (build to a directory with build_bundle.py --out). Offline: no network,
no subprocess. This is the integrity check wired into the CI quality gate (run_all.py) as the 9th step.

Usage:  python knowledge/publish/validate_bundle.py [--quiet] [--bundle DIR]
Exit 0 = the bundle architecture is intact and reproducible.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    sys.exit("jsonschema is required (pip install -r requirements.txt)")

import build_bundle  # same directory; sys.path[0] is knowledge/publish when run as a script

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "knowledge" / "schemas" / "bundle-manifest.schema.json"
ALLOWED_PREFIXES = ("rules/", "indicators/", "taxonomy/", "schemas/", "sources/")


def main() -> int:
    quiet = "--quiet" in sys.argv
    errs = []

    schema = json.loads(SCHEMA_PATH.read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    # 1) compute the manifest and schema-validate it
    m1 = build_bundle.compute_manifest()
    for e in validator.iter_errors(m1):
        errs.append(f"manifest schema: {e.json_path} {e.message}")

    # 2) independently re-hash every recorded file and compare
    members = dict(build_bundle._members())  # bundle_path -> source path
    for entry in m1["integrity"]["files"]:
        bp = entry["path"]
        src = members.get(bp)
        if src is None:
            errs.append(f"manifest lists {bp} but it is not a bundle member")
            continue
        if not src.exists():
            errs.append(f"bundle member missing on disk: {bp}")
            continue
        data = src.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != entry["sha256"]:
            errs.append(f"{bp}: sha256 mismatch (manifest {entry['sha256'][:12]}… vs disk {actual[:12]}…)")
        if len(data) != entry["bytes"]:
            errs.append(f"{bp}: byte count mismatch")

    # 3) recompute content_digest from the recorded set
    recomputed = hashlib.sha256(
        "\n".join(f"{f['path']}={f['sha256']}" for f in sorted(m1["integrity"]["files"], key=lambda x: x["path"])).encode()
    ).hexdigest()
    if recomputed != m1["content_digest"]:
        errs.append(f"content_digest does not recompute (manifest {m1['content_digest'][:12]}… vs {recomputed[:12]}…)")

    # 4) determinism: build the manifest again; digest + per-file hashes must be identical
    m2 = build_bundle.compute_manifest()
    if m1["content_digest"] != m2["content_digest"]:
        errs.append("build is NOT deterministic: content_digest differs between two builds")
    if {f["path"]: f["sha256"] for f in m1["integrity"]["files"]} != \
       {f["path"]: f["sha256"] for f in m2["integrity"]["files"]}:
        errs.append("build is NOT deterministic: per-file hashes differ between two builds")

    # 5) every component version pinned
    for k, v in m1["component_versions"].items():
        if not v:
            errs.append(f"component_versions.{k} is empty — version not pinned")

    # 6) runtime bundle excludes raw PDFs and test/dev data
    for entry in m1["integrity"]["files"]:
        bp = entry["path"]
        if not bp.startswith(ALLOWED_PREFIXES):
            errs.append(f"unexpected bundle path {bp} — outside allowed runtime prefixes")
        if bp.endswith(".pdf"):
            errs.append(f"raw PDF {bp} must not be in the runtime bundle (ADR-0004 §5.2)")
        if any(bad in bp for bad in ("seed-data", "_fixtures", "coverage", "validation", "seed-corpus")):
            errs.append(f"test/dev artefact {bp} must not be in the runtime bundle")

    # 7) optional: verify an on-disk built bundle matches the manifest
    if "--bundle" in sys.argv:
        i = sys.argv.index("--bundle")
        bdir = Path(sys.argv[i + 1])
        if not bdir.is_absolute():
            bdir = ROOT / bdir
        man = bdir / "bundle-manifest.json"
        if not man.exists():
            errs.append(f"--bundle {bdir}: no bundle-manifest.json")
        else:
            disk = json.loads(man.read_text())
            for entry in disk["integrity"]["files"]:
                fp = bdir / entry["path"]
                if not fp.exists():
                    errs.append(f"--bundle: missing {entry['path']}")
                elif hashlib.sha256(fp.read_bytes()).hexdigest() != entry["sha256"]:
                    errs.append(f"--bundle: {entry['path']} hash mismatch")

    if errs:
        print("BUNDLE INTEGRITY CHECK: FAIL")
        for e in errs:
            print(" -", e)
        return 1

    if not quiet:
        c = m1["counts"]
        print("BUNDLE INTEGRITY CHECK: PASS")
        print(f" content_digest {m1['content_digest']}")
        print(f" files {c['files']}  rules {c['rules_total']} ({c['rules_published']} published)  "
              f"positives {c['positive_indicators']}  negatives {c['negative_indicators']}")
        print(f" component versions pinned: {len(m1['component_versions'])}  (deterministic build verified)")
    else:
        print("BUNDLE INTEGRITY CHECK: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
