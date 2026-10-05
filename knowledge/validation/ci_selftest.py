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


def d_ai_default_on(root: Path):
    p = root / "knowledge" / "ai" / "integration.py"
    orig = p.read_bytes()
    text = orig.decode("utf-8")
    # The Phase-4 safety default is that AI extraction is OFF unless a host explicitly opts in (FR-072,
    # ADR-0007 §9). Flipping the WP5 feature-policy default to ON in the temp copy must trip the P4-WP5
    # integration validator's explicit "feature flag default OFF" assertion -> validate_ai_integration.py.
    mutated = text.replace("    extraction_enabled: bool = False", "    extraction_enabled: bool = True")
    if mutated == text:
        raise RuntimeError("ci_selftest could not flip the AI feature-policy default (declaration text changed?)")
    p.write_bytes(mutated.encode("utf-8"))
    return p, orig


def d_shared_governed_artifact(root: Path):
    p = root / "contracts" / "postgresql" / "schema-v1.json"
    orig = p.read_bytes()
    d = load(p)
    # Dropping the UNIQUE(evaluation_id) constraint on governed_input_artifact would let several evaluations share
    # one governed input artifact, breaking the P6-WP1 LOW-1 1:1 rule. No Phase-2/3/4 validator reads the Phase-6
    # persistence contract, so only the P6-WP2 data-contract gate can bite -> validate_data_contract.py.
    for t in d["tables"]:
        if t["name"] == "governed_input_artifact":
            before = len(t["unique"])
            t["unique"] = [u for u in t["unique"] if u["name"] != "uq_governed_input_artifact_evaluation"]
            if len(t["unique"]) == before:
                raise RuntimeError("ci_selftest could not remove the governed-artifact 1:1 constraint (name changed?)")
    dump(p, d)
    return p, orig


def d_unfenced_result_insert(root: Path):
    p = root / "contracts" / "postgresql" / "schema-v1.json"
    orig = p.read_bytes()
    d = load(p)
    # Removing the BEFORE INSERT result-state guard would let a stale worker insert a DetectionResult under an
    # evaluation already fenced to FAILED_INFRASTRUCTURE (P6-WP2 MEDIUM-1). Only the data-contract gate (DC-25) bites.
    for t in d["tables"]:
        if t["name"] == "detection_result":
            before = len(t.get("constraint_triggers", []))
            t["constraint_triggers"] = [g for g in t.get("constraint_triggers", []) if g["name"] != "tg_detection_result_insert_guard"]
            if len(t["constraint_triggers"]) == before:
                raise RuntimeError("ci_selftest could not remove the result insert guard (name changed?)")
    dump(p, d)
    return p, orig


def d_mutable_detection_result(root: Path):
    p = root / "contracts" / "api" / "api-v1.json"
    orig = p.read_bytes()
    d = load(p)
    # Adding a PATCH operation on the completed DetectionResult would let a client rewrite an authoritative Phase-3
    # decision through the API. No persistence or runtime validator reads the API catalog, so only the P6-WP3
    # API-contract gate (AC-06 immutability) can bite -> validate_api_contract.py.
    template = next((o for o in d["operations"] if o["operation_id"] == "getDetectionResult"), None)
    if template is None:
        raise RuntimeError("ci_selftest could not find getDetectionResult in the API catalog (renamed?)")
    patch = dict(template, operation_id="patchDetectionResult", method="PATCH",
                 request_schema="EvaluationCreateRequest", idempotency="NOT_APPLICABLE")
    d["operations"].append(patch)
    dump(p, d)
    return p, orig


def d_openapi_mutable_result(root: Path):
    p = root / "contracts" / "api" / "openapi-v1.json"
    orig = p.read_bytes()
    d = load(p)
    # Adding a PATCH operation on the DetectionResult path ONLY in the OpenAPI document (the API catalog is untouched)
    # would publish a forbidden mutation through the generated contract surface. Only the P6-WP4 OpenAPI gate reads the
    # OpenAPI file, so only it can bite (OA-20 immutability + OA-03 parity) -> validate_openapi_contract.py.
    item = d["paths"].get("/api/v1/evaluations/{evaluation_id}/result")
    if not item or "get" not in item:
        raise RuntimeError("ci_selftest could not find the DetectionResult path in openapi-v1.json (renamed?)")
    item["patch"] = dict(item["get"], operationId="patchDetectionResult")
    dump(p, d)
    return p, orig


def d_user_controlled_destination(root: Path):
    p = root / "contracts" / "integrations" / "external-enrichment-v1.json"
    orig = p.read_bytes()
    d = load(p)
    # Letting user input populate the destination URL turns indicator lookup into an SSRF primitive. Only the P6-WP5
    # integration gate reads the integration contract, so only it can bite (IC-08) -> validate_integration_contract.py.
    rc = d.get("request_construction", {})
    if "user_input_may_populate" not in rc:
        raise RuntimeError("ci_selftest could not find request_construction.user_input_may_populate (renamed?)")
    rc["user_input_may_populate"].append("destination_url")
    dump(p, d)
    return p, orig


def d_case_revision_removed(root: Path):
    p = root / "contracts" / "postgresql" / "schema-v1.json"
    orig = p.read_bytes()
    d = load(p)
    # Removing the monotonic mutation_revision from case_record (column, mutable entry, check and +1 guard) re-opens
    # the ETag ABA hole (OPEN -> CLOSED -> OPEN reusing a validator). The persistence contract stays internally
    # consistent, so only the P6-WP6 operational gate (OC-16/OC-18/OC-20) bites -> validate_operational_contract.py.
    t = next((x for x in d.get("tables", []) if x.get("name") == "case_record"), None)
    if not t or not any(c["name"] == "mutation_revision" for c in t["columns"]):
        raise RuntimeError("ci_selftest could not find case_record.mutation_revision in schema-v1.json (renamed?)")
    t["columns"] = [c for c in t["columns"] if c["name"] != "mutation_revision"]
    t["mutable_columns"] = [c for c in t["mutable_columns"] if c != "mutation_revision"]
    t["checks"] = [c for c in t["checks"] if "mutation_revision" not in c["rule"]]
    t["transition_guards"] = [g for g in t["transition_guards"] if "mutation_revision" not in g]
    dump(p, d)
    return p, orig


def d_closure_digest_corrupted(root: Path):
    p = root / "contracts" / "phase6" / "phase6-closure-v1.json"
    orig = p.read_bytes()
    d = load(p)
    # Corrupting ONE pinned SHA-256 in the Phase-6 closure snapshot (the pinned artifact itself is untouched) must be detected
    # as drift between pinned digest and actual bytes. Only the P6-WP7 closure gate reads the closure manifest, so only it
    # can bite (P6C-11) -> validate_phase6_closure.py.
    art = next((a for a in d.get("snapshot", {}).get("artifacts", []) if a.get("path") == "contracts/api/api-v1.json"), None)
    if art is None:
        raise RuntimeError("ci_selftest could not find the pinned api-v1.json digest in phase6-closure-v1.json (renamed?)")
    art["sha256"] = ("0" if art["sha256"][0] != "0" else "1") + art["sha256"][1:]
    dump(p, d)
    return p, orig


def d_ux_role_only_evidence_content(root: Path):
    p = root / "contracts" / "ux" / "ux-foundation-v1.json"
    orig = p.read_bytes()
    d = load(p)
    surface = next((s for s in d["surfaces"] if s["surface_id"] == "UX-EVIDENCE-CONTENT"), None)
    if surface is None or surface["content_permission_required"] != "CONTENT_PERMISSION_REQUIRED":
        raise RuntimeError("ci_selftest could not find the governed evidence-content UX permission")
    # P7-WP1-only defect: the UX surface bypasses the separate evidence-content permission.
    # Accepted API / data / Phase-6 artifacts stay untouched; UXF-20 must catch it.
    surface["content_permission_required"] = "ROLE_ONLY"
    dump(p, d)
    return p, orig


DEFECTS = [
    ("unknown indicator reference", d_unknown_indicator, "validate_rules.py"),
    ("invalid taxonomy ID", d_invalid_taxonomy, "validate_rules.py"),
    ("invalid evidence reference", d_invalid_evidence, "validate_rules.py"),
    ("malformed extraction projection", d_bad_projection, "validate_extraction.py"),
    ("deprecated negative-indicator reference", d_deprecated_negative, "validate_rules.py"),
    ("malformed engine version (P3-WP8)", d_bad_engine_version, "validate_wp8_integration.py"),
    ("AI feature flag defaults ON (P4-WP5)", d_ai_default_on, "validate_ai_integration.py"),
    ("shared governed input artifact breaks evaluation 1:1 (P6-WP2)", d_shared_governed_artifact, "validate_data_contract.py"),
    ("result insertable under a fenced/failed evaluation (P6-WP2 MEDIUM-1)", d_unfenced_result_insert, "validate_data_contract.py"),
    ("completed DetectionResult made mutable through the API (P6-WP3)", d_mutable_detection_result, "validate_api_contract.py"),
    ("DetectionResult PATCH published only in OpenAPI (P6-WP4)", d_openapi_mutable_result, "validate_openapi_contract.py"),
    ("user input controls the enrichment destination URL (P6-WP5)", d_user_controlled_destination, "validate_integration_contract.py"),
    ("case_record monotonic mutation revision removed (P6-WP6)", d_case_revision_removed, "validate_operational_contract.py"),
    ("pinned Phase-6 closure artifact digest corrupted (P6-WP7)", d_closure_digest_corrupted, "validate_phase6_closure.py"),
    ("evidence-content UX uses role-only access (P7-WP1)", d_ux_role_only_evidence_content, "validate_ux_foundation.py"),
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
