# GATE-006 — Phase 2 checkpoint: CI and quality-gate wiring (WP7)

| Field | Value |
|---|---|
| Document ID | GATE-006 |
| Version | 1.0 |
| Status | **Checkpoint** — assesses WP7 (continuous-integration quality-gate wiring) |
| Phase assessed | Phase 2 — Knowledge engineering (WP7) |
| Owner role | Technical Program Director |
| Dependencies | GATE-005, KB-001 (v1.1 §11), the eight knowledge validators |
| Gate result | **`PASS` — WP7 COMPLETE; Phase 2 still IN PROGRESS (only ADR-0004/0014 remain); Phase 3 NOT STARTED** |
| Phase 1 status | **`PARTIAL`** — unchanged ([GATE-001 §7](GATE-001-phase-1-assessment.md)) |
| Last updated | 2026-08-29 |

---

## 1. Scope
WP7 wires the existing knowledge-validation suite into a **deterministic CI quality gate** so that
evidence, taxonomy, indicator, rule, suppression, extraction-contract or governance regressions cannot
be merged. It adds **no** business logic and changes **no** rule/indicator/taxonomy/extraction content;
it is pure enforcement plumbing plus documentation.

## 2. CI architecture
- **One canonical entrypoint** — `knowledge/validation/run_all.py` — runs the complete suite in
  dependency order, as isolated subprocesses of the same interpreter. It does **not** re-implement any
  validator; each stays independently runnable. Non-zero exit if any validator fails; zero only when all
  pass. Flags: `--verbose`, `--json` (machine-readable summary, STEP 9), `--fail-fast`, `--report PATH`.
- **Offline preflight** — before running anything, `run_all.py` statically scans every validator for a
  network-capable (or `subprocess`) import and refuses to run if one is present. The offline guarantee
  is therefore durable, not incidental.
- **Self-test** — `knowledge/validation/ci_selftest.py` proves the gate is non-vacuous by injecting
  representative defects into a **throwaway copy** of the tree and asserting the gate catches each; the
  real repository is never mutated.
- **Workflow** — `.github/workflows/knowledge-validation.yml` (GitHub Actions) runs two jobs: the gate
  (`run_all.py`) and the self-test (`ci_selftest.py`).

## 3. Validators included (execution order)
Dependency-aware: from the most foundational invariant to the most derived.

| # | Validator | Why it runs here |
|---|---|---|
| 1 | `manual_evidence_check.py` | durable-truth: evidence integrity (SHA-256 of the committed PDFs) + automated-status preservation |
| 2 | `phase1_consistency_check.py` | Phase-1 counts consistent across manifest / taxonomy / matrix / corpus |
| 3 | `validate_taxonomy.py` | taxonomy + dimensions integrity; rule `taxonomy_refs` resolve |
| 4 | `validate_kb.py` | KB governance: global ID uniqueness + version syntax + PUBLISHED review metadata |
| 5 | `validate_negative_library.py` | negative-indicator library integrity + overrides |
| 6 | `validate_rules.py` | rule JSON Schema + cross-file linter + negative fixtures |
| 7 | `validate_extraction.py` | extraction contracts: schemas, 28↔63 family partition, fixtures, coverage matrix |
| 8 | `rule_runner.py` | deterministic execution of the encoded rules over corpus + suppression suite |

## 4. Trigger policy
- **push** to `main` and **pull_request**, both filtered to paths that can change a validator's result:
  `knowledge/**`, `docs/00-program/**`, `docs/01-research/**`, `docs/02-knowledge/**`, `adr/**`,
  `requirements.txt`, and the workflow file. Governance/evidence documentation is **inside** the filter,
  so a publishability-affecting doc change cannot bypass CI.
- **workflow_dispatch** for manual runs. `concurrency` cancels superseded runs per ref to keep CI quiet
  without dropping coverage. `permissions: contents: read` (least privilege).

## 5. Runtime and dependencies
- **Python 3.12** in CI (code is compatible with 3.11–3.14; local dev runs 3.14).
- **`requirements.txt`** is the single dependency mechanism: `jsonschema` + `referencing` (pinned), used
  by only two validators; the other six are pure standard library. CI installs from it — never from a
  developer's `.venv`. `pip install` is the **only** network step; validation itself is offline.

## 6. Offline / durable-truth guarantee
No validator imports a network module (statically enforced by the preflight). `manual_evidence_check.py`
SHA-256-hashes the **committed** evidence PDFs (`knowledge/sources/raw/…`, all git-tracked) against the
frozen manifest, so the repository's evidence bundle is the durable source of truth. CI performs no
external advisory retrieval.

## 7. Negative CI tests (proof the gate bites)
`ci_selftest.py`, run on a disposable copy, injects and catches:

| Injected defect | Caught by (expected) |
|---|---|
| unknown indicator reference | `validate_rules.py` |
| invalid taxonomy ID | `validate_rules.py` |
| invalid evidence reference | `validate_rules.py` |
| malformed extraction projection | `validate_extraction.py` |
| deprecated negative-indicator reference | `validate_rules.py` |

All five caught by the expected validator; the real repository is untouched and returns to green.

## 8. Local developer command == CI command
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # one-time
.venv/bin/python knowledge/validation/run_all.py                     # before every commit
```
CI runs the identical `run_all.py`. Documented in [README](../../README.md) and [KB-001 §11](../02-knowledge/KB-001-knowledge-governance.md).

## 9. Governance integration
[KB-001 §11](../02-knowledge/KB-001-knowledge-governance.md) (v1.1) records that a change **cannot become
merge-eligible while the mandatory machine-enforced suite fails**, and that **CI does not replace** the
§9 human controls (evidence interpretation, official-channel identity, safeguarding, semantic rule
review, high-risk-override weakening, publication approval). A green gate is **necessary but not
sufficient** for merge/publication.

## 10. Results
```
# local canonical gate
QUALITY GATE: PASS — all 8 validators green in ~0.5s

# gate self-test (non-vacuity)
SELF-TEST: PASS — all 5 representative defects caught by the expected validator; real repository untouched

# workflow YAML — parsed and structurally validated locally (triggers, jobs, anchors, python 3.12)
```
**LOCAL CI-CONTRACT VALIDATED.** **REMOTE CI RUN NOT CONFIRMED** — the branch has not been pushed, so
GitHub Actions has not executed. Remote confirmation is pending a push/PR.

## 11. Effect on the knowledge base
**None.** No rule scope/status/severity, no indicator, taxonomy, negative library or extraction contract
changed. 18 PUBLISHED rules, 55/55 runner cases, and the extraction contracts are all unaffected — WP7 is
enforcement and documentation only.

## 12. Remaining Phase 2 work

| WP | Status |
|---|---|
| WP2 extraction contracts | ✅ done (GATE-005) |
| WP5 taxonomy · WP6 KB-001 | ✅ done (GATE-004) |
| WP7 CI quality-gate wiring | ✅ **done (this gate)** |
| WP8 ADR-0004 (storage) · ADR-0014 (language) | **open** — the only remaining Phase-2 items; ADR-0014 blocked on OI-04 |

## 13. Decision
**Stop here, as instructed.** WP7 passes: a single canonical, offline, reproducible gate now enforces the
machine-checkable knowledge controls on every relevant change, proven non-vacuous by the self-test, with
governance recording that a red gate blocks merge without replacing human review. **Phase 2 remains IN
PROGRESS** (WP8 ADR-0004/0014 remain). Phase 3 (DET-001) and any production extractor must not begin until
explicitly approved.

## 14. Change history
| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-08-29 | WP7 assessed: canonical `run_all.py` gate (8 validators, dependency order, offline preflight), `ci_selftest.py` non-vacuity proof, GitHub Actions workflow (path-filtered PR + main, self-test job), `requirements.txt`, README + KB-001 §11 governance. Local gate + self-test green; remote CI not yet run. Knowledge base unaffected. Phase 2 remains IN PROGRESS (WP8 remains). | Technical Program Director |
