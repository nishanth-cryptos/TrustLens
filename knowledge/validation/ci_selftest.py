"""TrustLens quality-gate self-test — Phase 2 WP7 STEP 8.

Proves the canonical gate (run_all.py) is NON-VACUOUS: for each representative knowledge
defect it must fail, and the RIGHT validator must catch it. This is a meta-test of the gate,
not part of the gate itself.

Safety: it never mutates the real repository. It copies the working tree (minus .git/.venv)
to a temporary directory, injects ONE defect at a time into the copy, runs run_all there,
asserts the gate fails with the expected validator, restores the copy, and finally deletes the
temp tree. The real repository is only ever read.

Usage:  python knowledge/validation/ci_selftest.py [--verbose]
Exit 0 = every injected defect was caught by the expected validator (the gate bites).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def dump(p: Path, data):
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---- defect injectors. Each takes the temp repo root, mutates one file, and returns
#      (path, original_bytes) so the harness can restore it afterwards.

def d_unknown_indicator(root: Path):
    p = root / "knowledge" / "rules" / "TL-CRED-001.json"
    orig = p.read_bytes()
    d = load(p)
    # wrap the existing require so it still validates against the schema but references a
    # positive indicator that nothing extracts -> validate_rules L1 (unknown indicator).
    d["logic"]["require"] = {"all_of": [d["logic"]["require"], "BOGUS_INDICATOR"]}
    dump(p, d)
    return p, orig


def d_invalid_taxonomy(root: Path):
    p = root / "knowledge" / "rules" / "TL-CRED-001.json"
    orig = p.read_bytes()
    d = load(p)
    d["taxonomy_refs"] = list(d["taxonomy_refs"]) + ["TAX-91-01"]
    dump(p, d)
    return p, orig


def d_invalid_evidence(root: Path):
    p = root / "knowledge" / "rules" / "TL-CRED-001.json"
    orig = p.read_bytes()
    d = load(p)
    d["evidence"]["source_references"][0]["source_id"] = "SRC-999"
    dump(p, d)
    return p, orig


def d_bad_projection(root: Path):
    p = root / "knowledge" / "extraction" / "extraction-fixtures-v1.json"
    orig = p.read_bytes()
    d = load(p)
    d["fixtures"][0]["expected_projection"]["positive_signals"].append("BOGUS_SIGNAL")
    dump(p, d)
    return p, orig


def d_deprecated_negative(root: Path):
    p = root / "knowledge" / "indicators" / "negative-indicator-library-v1.json"
    orig = p.read_bytes()
    d = load(p)
    # EXPLICIT_NO_FEE is referenced by TL-JOB-001 / TL-JOB-003 suppressed_by; deprecating it
    # must trip validate_rules L1b (a rule may not depend on a DEPRECATED negative indicator).
    for n in d["negative_indicators"]:
        if n["negative_indicator_id"] == "EXPLICIT_NO_FEE":
            n["status"] = "DEPRECATED"
    dump(p, d)
    return p, orig


def d_bad_engine_version(root: Path):
    p = root / "knowledge" / "runtime" / "engine.py"
    orig = p.read_bytes()
    text = orig.decode("utf-8")
    # A malformed runtime-owned engine version is a WP8-EXCLUSIVE defect: no upstream validator reads
    # ENGINE_VERSION, and engine.py deliberately does not raise at import, so only the P3-WP8 result-assembly
    # gate (schema pattern on provenance.engine_version + explicit SemVer check) bites -> validate_wp8_integration.py.
    mutated = text.replace('ENGINE_VERSION = "1.0.0"', 'ENGINE_VERSION = "banana"')
    if mutated == text:
        raise RuntimeError("ci_selftest could not inject a malformed ENGINE_VERSION (constant text changed?)")
    p.write_bytes(mutated.encode("utf-8"))
    return p, orig


DEFECTS = [
    ("unknown indicator reference", d_unknown_indicator, "validate_rules.py"),
    ("invalid taxonomy ID", d_invalid_taxonomy, "validate_rules.py"),
    ("invalid evidence reference", d_invalid_evidence, "validate_rules.py"),
    ("malformed extraction projection", d_bad_projection, "validate_extraction.py"),
    ("deprecated negative-indicator reference", d_deprecated_negative, "validate_rules.py"),
    ("malformed engine version (P3-WP8)", d_bad_engine_version, "validate_wp8_integration.py"),
]


def run_gate(root: Path):
    """Run run_all.py --json inside the temp repo; return the parsed summary."""
    proc = subprocess.run(
        [sys.executable, str(root / "knowledge" / "validation" / "run_all.py"), "--json"],
        capture_output=True, text=True, cwd=str(root), timeout=300,
    )
    try:
        summary = json.loads(proc.stdout)
    except json.JSONDecodeError:
        summary = {"gate": "UNPARSEABLE", "results": [], "_raw": proc.stdout + proc.stderr}
    return proc.returncode, summary


def main() -> int:
    verbose = "--verbose" in sys.argv
    tmp = Path(tempfile.mkdtemp(prefix="trustlens-selftest-"))
    work = tmp / "repo"
    print(f"quality-gate self-test — copying working tree to {work}")
    shutil.copytree(
        ROOT, work,
        ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", "*.pyc", ".pytest_cache"),
    )

    # sanity: the untouched copy must be green, or the test proves nothing
    rc, summary = run_gate(work)
    if rc != 0 or summary.get("gate") != "PASS":
        print("  FAIL  baseline copy is not green — cannot prove the gate bites")
        if verbose:
            print(json.dumps(summary, indent=2))
        shutil.rmtree(tmp, ignore_errors=True)
        return 1
    print(f"  ok    baseline copy green ({summary['validators_run']} validators)\n")

    failures = []
    try:
        for name, inject, expected in DEFECTS:
            path, orig = inject(work)
            rc, summary = run_gate(work)
            path.write_bytes(orig)  # restore immediately

            failed = {r["validator"] for r in summary.get("results", []) if r["status"] == "FAIL"}
            caught = rc != 0 and summary.get("gate") == "FAIL"
            right = expected in failed
            ok = caught and right
            mark = "ok  " if ok else "FAIL"
            print(f"  {mark}  defect: {name}")
            print(f"          gate={'FAIL' if caught else summary.get('gate')}  "
                  f"expected={expected}  caught_by={sorted(failed) or 'NONE'}")
            if not ok:
                failures.append(name)
                if verbose:
                    print(json.dumps(summary, indent=2))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if failures:
        print(f"SELF-TEST: FAIL — {len(failures)} defect(s) not caught as expected: {failures}")
        return 1
    print(f"SELF-TEST: PASS — all {len(DEFECTS)} representative defects caught by the expected validator; "
          f"real repository untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
