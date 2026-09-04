"""TrustLens knowledge quality gate — Phase 2 WP7.

The single canonical entrypoint that runs the COMPLETE knowledge-validation suite in
dependency order and fails as a whole if any validator fails. It is the command CI runs
and the command a developer runs before committing — the two execute identical logic.

Design guarantees:
  * It does NOT re-implement any validator. Each existing validator stays independently
    runnable; run_all invokes each as an isolated subprocess (same interpreter), preserving
    that validator's own output and exit code.
  * Non-zero exit if ANY required validator fails; zero only when the whole suite passes.
  * Exceptions are never swallowed — a crashing validator surfaces as a non-zero return with
    its traceback shown.
  * OFFLINE by construction. A preflight refuses to run if any validator imports a
    network-capable module, so validation can never silently depend on live retrieval. The
    committed evidence bundle is the durable source of truth (manual_evidence_check hashes it).
  * It never modifies repository data — it only reads and executes.

Order (dependency-aware, see ORDER below):
  manual evidence integrity → Phase-1 consistency → taxonomy → KB governance →
  negative-indicator library → rule schema/lint → extraction contracts → rule runner →
  published-bundle integrity (ADR-0004) → Phase-3 DET-001 design (golden cases) →
  Phase-3 runtime contracts (P3-WP1: schemas + fixtures) →
  Phase-3 runtime loader (P3-WP2: bundle load + integrity + indexes) →
  Phase-3 rule evaluator (P3-WP3: Kleene three-valued evaluation + evidence-class diversity) →
  Phase-3 suppression executor (P3-WP4: rule suppression + severity caps) →
  Phase-3 decision aggregator (P3-WP5: governing rule + risk/severity/confidence + classification) →
  Phase-3 explanation + governed actions (P3-WP6: deterministic explanation + action-policy artifact) →
  Phase-3 golden end-to-end replay (P3-WP7: public live + governed design-preview lanes) →
  Phase-3 engine integration + result assembly (P3-WP8: final DetectionResult contract + provenance pinning + CI closure)

Usage:
  python knowledge/validation/run_all.py             # human-readable; runs all; non-zero on any failure
  python knowledge/validation/run_all.py --verbose   # also print each validator's full output
  python knowledge/validation/run_all.py --fail-fast # stop at the first failing validator
  python knowledge/validation/run_all.py --json       # machine-readable summary (JSON) to stdout
  python knowledge/validation/run_all.py --report P    # also write the JSON summary to path P
Exit 0 only when every validator passes.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Dependency-aware execution order. Each entry: (repo-relative path, why-it-runs-here).
# Rationale — the suite flows from the most foundational invariant to the most derived, ending
# with the publish-integrity check (ADR-0004) and the Phase-3 DET-001 design gate:
#   1 evidence must be intact and its automated grades preserved before anything trusts it;
#   2 Phase-1 counts/consistency across manifest/taxonomy/matrix/corpus must hold;
#   3 the taxonomy + dimensions must be internally valid (rules reference taxa);
#   4 KB governance checks global ID uniqueness/versioning across those namespaces;
#   5 the negative-indicator library must be valid (rules + extraction consume it);
#   6 rules validate against schema + the linter, which reads indicators/taxonomy/manifest/library;
#   7 extraction contracts build on rules + families + library + taxonomy/dimensions;
#   8 the rule runner executes the whole encoded set over the corpus + suppression suite;
#   9 the published knowledge bundle builds deterministically and its hashes verify (ADR-0004 WP8);
#  10 the Phase-3 DET-001 design golden decision cases are consistent with the governed KB and the
#     ADR-0006 risk model (Phase-3 closure, GATE-009);
#  11 the Phase-3 runtime detection contracts (P3-WP1) are valid, their fixtures pass/fail as intended,
#     the enums are synchronised with DET-001/ADR-0006, and all 15 golden cases are representable;
#  12 the Phase-3 runtime loader (P3-WP2) loads the published bundle fail-closed — manifest schema,
#     per-file SHA-256 + content digest, exact-token version compatibility, cross-reference integrity,
#     the PUBLISHED-only executable boundary and immutable indexes — with typed errors on every defect;
#  13 the Phase-3 rule evaluator (P3-WP3) interprets each PUBLISHED rule against indicator observations
#     in Kleene three-valued logic (UNKNOWN != NOT_OBSERVED), gates evidence-class diversity, and emits
#     schema-valid per-rule results with NO final risk/classification — over the real published bundle.
#  14 the Phase-3 suppression executor (P3-WP4) consumes WP3 per-rule results and applies governed,
#     override-aware SUPPRESS_RULE / CAP_SEVERITY / CONTEXT_ONLY effects with per-rule fail-closed isolation.
#  15 the Phase-3 decision aggregator (P3-WP5) folds the governed per-rule results into ONE decision — max
#     effective severity, ADR-0006 composite matched-evidence strength, the fixed severity x strength risk
#     matrix, categorical detection confidence, corroboration over independent evidence classes, and the
#     final classification — deterministic and fail-closed, verified against all 15 golden decision cases.
#  16 the Phase-3 explanation/action builder (P3-WP6) renders the already-decided result and resolves actions
#     only from the governed action-policy artifact, with a PUBLISHED-only public trust boundary;
#  17 the Phase-3 golden runner (P3-WP7) composes WP3→WP6 over all 15 cases, including separate public-live and
#     lifecycle-eligible design-preview lanes, then compares every binding golden axis and action in order.
#  18 the Phase-3 engine integration gate (P3-WP8) assembles the final promoted DetectionResult through the public
#     evaluate_detection_from_governed, pins full bundle/engine/profile provenance, enforces the detection-result
#     JSON Schema + reusable semantic invariants + assembler reconciliation, and proves support-first
#     orchestration, PUBLISHED-only preview exclusion, privacy, determinism and fail-closed forgery rejection.
ORDER = [
    ("knowledge/validation/manual_evidence_check.py", "durable-truth: evidence integrity + automated-status preservation"),
    ("knowledge/validation/phase1_consistency_check.py", "Phase-1 counts consistent across manifest / taxonomy / matrix / corpus"),
    ("knowledge/validation/validate_taxonomy.py", "taxonomy + dimensions integrity; rule taxonomy_refs resolve"),
    ("knowledge/validation/validate_kb.py", "KB governance: global ID uniqueness + version syntax + PUBLISHED review metadata"),
    ("knowledge/validation/validate_negative_library.py", "negative-indicator library integrity + overrides"),
    ("knowledge/validation/validate_rules.py", "rule JSON Schema + cross-file linter + negative fixtures"),
    ("knowledge/validation/validate_extraction.py", "extraction contracts: schemas, families partition, fixtures, coverage matrix"),
    ("knowledge/validation/rule_runner.py", "deterministic execution of the encoded rules over corpus + suppression suite"),
    ("knowledge/publish/validate_bundle.py", "published knowledge bundle: deterministic build + SHA-256 integrity (ADR-0004)"),
    ("docs/03-detection/validate_det_design.py", "Phase-3 DET-001 design: golden decision cases consistent with the governed KB and the ADR-0006 risk model"),
    ("knowledge/validation/validate_runtime_contracts.py", "Phase-3 P3-WP1 runtime contracts: detection-result / rule-evaluation-result schemas + fixtures + enum sync + golden-case representability"),
    ("knowledge/validation/validate_runtime_loader.py", "Phase-3 P3-WP2 runtime loader: fail-closed bundle load, integrity, exact-token compatibility, reference integrity, immutable indexes"),
    ("knowledge/validation/validate_rule_evaluator.py", "Phase-3 P3-WP3 rule evaluator: Kleene three-valued evaluation, confidence gate, evidence-class diversity, PUBLISHED-only, determinism, schema validity, no final risk/classification"),
    ("knowledge/validation/validate_wp4_suppression.py", "Phase-3 P3-WP4 suppression executor: override-aware SUPPRESS_RULE, ordinal CAP_SEVERITY, inert CONTEXT_ONLY, deterministic metadata, per-rule fail-closed isolation, no WP5 fields"),
    ("knowledge/validation/validate_wp5_aggregation.py", "Phase-3 P3-WP5 decision aggregation: governing-rule selection, max effective severity, ADR-0006 composite strength + risk matrix, categorical confidence, corroboration over independent evidence classes, classification state machine, determinism + fail-closed, 15 golden decision cases"),
    ("knowledge/validation/validate_wp6_explanation.py", "Phase-3 P3-WP6 explanation + governed actions: deterministic templated explanation (evidence_basis exact stored quotes, no PII/redacted_quote, no numeric), recommended actions from the governed action-policy artifact (no free-form code, no priority), WP5 decision immutable, determinism + fail-closed, 15 golden decision cases"),
    ("knowledge/validation/validate_wp7_golden_runner.py", "Phase-3 P3-WP7 golden end-to-end runner: fixture adaptation + independently-derived support, public PUBLISHED live replay, lifecycle-eligible design preview, exact golden-axis/action comparison, determinism and fail-closed reporting"),
    ("knowledge/validation/validate_wp8_integration.py", "Phase-3 P3-WP8 engine integration + result assembly: production evaluate_detection_from_governed builds a schema+semantically valid, fully-provenance-pinned, immutable DetectionResult from WP3→WP6; support-first (no rules for non-evaluable), PUBLISHED-only preview exclusion, faithful WP5/WP6 serialization, privacy-minimised, deterministic with identity/time invariance, fail-closed on forgery/corruption"),
]

# Network-capable modules a validator must never import — the offline guarantee (WP7 STEP 7).
NETWORK_IMPORT = re.compile(
    r"^\s*(?:import|from)\s+(socket|ssl|http|httplib|urllib|requests|httpx|aiohttp|"
    r"ftplib|telnetlib|smtplib|poplib|imaplib)\b",
    re.MULTILINE,
)
# subprocess is allowed only in this runner, never in a validator (it could shell out to the net).
SUBPROCESS_IMPORT = re.compile(r"^\s*(?:import|from)\s+subprocess\b", re.MULTILINE)

PASS_TIMEOUT_S = 300


def preflight_offline():
    """Static guard: no validator may import a network-capable (or subprocess) module.

    This is what makes the offline guarantee durable rather than incidental — a future
    validator that quietly adds `import requests` fails the gate before it can run.
    """
    problems = []
    for relpath, _ in ORDER:
        module = Path(relpath).name
        path = ROOT / relpath
        if not path.exists():
            problems.append(f"{module}: validator file is missing")
            continue
        src = path.read_text(encoding="utf-8")
        for m in NETWORK_IMPORT.finditer(src):
            problems.append(f"{module}: imports network-capable module {m.group(1)!r} — validators must be offline (WP7 STEP 7)")
        for _ in SUBPROCESS_IMPORT.finditer(src):
            problems.append(f"{module}: imports subprocess — a validator must not shell out (offline guarantee)")
    return problems


def run_one(relpath: str):
    """Run a single validator as an isolated subprocess; return a result dict."""
    module = Path(relpath).name
    path = ROOT / relpath
    start = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, str(path), "--quiet"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=PASS_TIMEOUT_S,
    )
    dur = time.perf_counter() - start
    output = (proc.stdout or "") + (proc.stderr or "")
    # a concise failure reason: last non-empty output line, else the return code
    reason = ""
    if proc.returncode != 0:
        lines = [ln for ln in output.splitlines() if ln.strip()]
        reason = lines[-1].strip() if lines else f"exit {proc.returncode}"
    return {
        "validator": module,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "returncode": proc.returncode,
        "duration_s": round(dur, 3),
        "output": output.rstrip(),
        "reason": reason,
    }


def main() -> int:
    verbose = "--verbose" in sys.argv
    as_json = "--json" in sys.argv
    fail_fast = "--fail-fast" in sys.argv
    report_path = None
    if "--report" in sys.argv:
        i = sys.argv.index("--report")
        if i + 1 < len(sys.argv):
            report_path = Path(sys.argv[i + 1])

    def log(*a):
        if not as_json:
            print(*a)

    # ---- offline preflight
    problems = preflight_offline()
    if problems:
        if as_json:
            print(json.dumps({"gate": "FAIL", "stage": "offline-preflight", "problems": problems}, indent=2))
        else:
            print("QUALITY GATE: FAIL (offline preflight)")
            for p in problems:
                print("  -", p)
        return 2

    log(f"TrustLens knowledge quality gate — {len(ORDER)} checks (8 validators + bundle integrity + Phase-3 design + runtime contracts + runtime loader + runtime evaluator + suppression executor + decision aggregator + explanation/actions + golden end-to-end replay + engine integration), dependency order, offline")
    log(f"interpreter: {sys.executable}")
    log(f"repo root  : {ROOT}\n")

    results = []
    for relpath, why in ORDER:
        res = run_one(relpath)
        res["rationale"] = why
        results.append(res)
        if not as_json:
            mark = "ok  " if res["status"] == "PASS" else "FAIL"
            print(f"  {mark}  {res['validator']:<30} {res['duration_s']:>6.2f}s  {why}")
            if res["status"] == "FAIL":
                print(f"        └─ {res['reason']}")
            if verbose or res["status"] == "FAIL":
                for line in res["output"].splitlines():
                    print(f"        │ {line}")
        if fail_fast and res["status"] == "FAIL":
            break

    failed = [r for r in results if r["status"] == "FAIL"]
    total_s = round(sum(r["duration_s"] for r in results), 3)

    if as_json:
        summary = {
            "gate": "FAIL" if failed else "PASS",
            "validators_run": len(results),
            "validators_failed": len(failed),
            "total_duration_s": total_s,
            "results": [{k: r[k] for k in ("validator", "status", "returncode", "duration_s", "reason")} for r in results],
        }
        print(json.dumps(summary, indent=2))
    else:
        print()
        if failed:
            print(f"QUALITY GATE: FAIL — {len(failed)}/{len(results)} validator(s) failed in {total_s:.2f}s: "
                  f"{[r['validator'] for r in failed]}")
        else:
            print(f"QUALITY GATE: PASS — all {len(results)} checks green in {total_s:.2f}s")

    if report_path is not None:
        report_path.write_text(json.dumps({
            "gate": "FAIL" if failed else "PASS",
            "total_duration_s": total_s,
            "results": [{k: r[k] for k in ("validator", "status", "returncode", "duration_s", "reason")} for r in results],
        }, indent=2), encoding="utf-8")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
