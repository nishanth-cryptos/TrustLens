# GATE-009 — Phase 3 design gate: DET-001 deterministic detection engine (DESIGN)

| Field | Value |
|---|---|
| Document ID | GATE-009 |
| Version | 1.1 |
| Status | **Gate — Phase 3 DESIGN checkpoint** |
| Phase assessed | Phase 3 — Detection engine design (DET-001), design only |
| Owner role | Detection Architect / Technical Program Director |
| Dependencies | DET-001, ADR-0005, ADR-0006, KB-001, KB-002, RESEARCH-004 §7, CONF-001 |
| Gate result | **DESIGN COMPLETE — implementation NOT started** |
| Phase 2 status | **`PASS`** — unchanged; no Phase-2 semantics modified |
| Phase 1 status | **`PARTIAL`** — unchanged and independent |
| Last updated | 2026-08-29 |

---

## 1. What this gate asserts (and what it does not)

This is a **design** gate. It asserts that Phase 3 has produced a complete, internally consistent,
machine-checked *design* for the deterministic detection engine — the pipeline, execution semantics,
separated risk/severity/confidence model, classification vocabulary, explanation and recommended-action
contracts, determinism guarantees and fail-closed behaviour. It does **not** assert that a production
engine exists (it does not), and it makes **no accuracy claim** (G-09 remains open; RSK-003).

## 2. Deliverables

| Artefact | Path |
|---|---|
| DET-001 design | `docs/03-detection/DET-001-deterministic-detection-engine.md` |
| ADR-0005 execution model | `adr/ADR-0005-rule-execution-model.md` (Accepted) |
| ADR-0006 risk/confidence maths | `adr/ADR-0006-risk-and-confidence-aggregation.md` (Accepted) |
| Detection-result contract | `docs/03-detection/contracts/detection-result.schema.json` |
| Rule-evaluation-result contract | `docs/03-detection/contracts/rule-evaluation-result.schema.json` |
| 15 golden decision cases | `docs/03-detection/golden-decision-cases-v1.json` |
| Phase-3 design validator | `docs/03-detection/validate_det_design.py` |

## 3. Decisions frozen

- **Execution:** three-valued (Kleene) interpreter over the immutable bundle; `UNKNOWN ≠ NOT_OBSERVED`;
  PUBLISHED-only live; rules stay data (ADR-0005).
- **Risk/confidence:** categorical, decomposable, non-probabilistic; decision severity = max effective
  severity; risk = fixed `severity × matched-evidence-strength` matrix; detection confidence a separate
  categorical axis; corroboration counted over independent evidence classes, not rule count; **no fraud
  probability** (ADR-0006, implements CONF-001).
- **Support status decided first;** `UNSUPPORTED`/`INSUFFICIENT_EVIDENCE` never map to benign.
- **Hard-risk overrides** gate suppression only — they never set severity nor bypass `require`.
- **AI boundary** and **fail-closed** behaviour specified (DET-001 §16–17).

## 4. Evidence (all green)

```
Canonical quality gate:   PASS — all 10 checks green (8 knowledge validators + published-bundle
                          integrity + Phase-3 DET-001 design). run_all.py now includes
                          validate_det_design.py as the 10th canonical check.
Phase-3 design check:     PASS — 2 design schemas valid Draft 2020-12; detection-result contract
                          usable (2 synthetic examples validate); 15 golden decision cases consistent
                          with the live KB and the ADR-0006 risk matrix (governed-rule severity).
Gate self-test:           PASS — 5 representative defects caught; the baseline copy runs all 10 checks
                          green, so the 10th check is exercised under CI conditions; repo untouched.
```

## 4a. Closure changes applied at this gate (2026-08-29)

Two — and only two — changes were made after the design was approved:

1. **M-003 / `expected_outcome` reconciliation.** Inspection showed the seed-corpus `expected_outcome`
   field is consumed by **no** severity logic (the rule-runner never reads it; `phase1_consistency_check.py`
   only asserts its presence) and blends finding-class with a coarse band — i.e. it is a **coarse Phase-2
   expectation, not runtime severity**. Per the branch-(b) instruction, values were **preserved** and the
   field was **renamed `expected_outcome → phase2_expected_outcome`** across all three seed files, with a
   `phase2_expected_outcome_semantics` note in each recording why and stating it is NOT DET-001 severity.
   TL-CRED-001 was **not** downgraded — the governed rule (CRITICAL) is authoritative for Phase-3 severity,
   and the golden cases already carry governed-rule severity (enforced by `validate_det_design.py`). The
   sole code consumer (`phase1_consistency_check.py`) was updated to the new key. **No rule meaning changed.**
2. **Phase-3 design validation promoted into CI** as the 10th canonical check: `run_all.py` ORDER,
   `.github/workflows/knowledge-validation.yml` path triggers (+`docs/03-detection/**`), and README/gate
   docs updated. The canonical gate now proves the existing 9 checks **plus** the Phase-3 design contracts
   and golden cases.

## 5. Honesty carried forward

- **No accuracy claim.** G-09 (no labelled corpus) is unclosable; DET-001 defines measurement *hooks*
  only. No precision/recall/false-positive-rate is produced.
- **English/Latn MVP only.** Non-English input is `UNSUPPORTED`, never silently benign (G-08, ADR-0014).
- **Capped evidence stays capped.** `PARTIAL`/`HEURISTIC` rules reach lower risk bands than `SUPPORTED`
  ones (RESEARCH-004 §7); three governed rules remain `DEFERRED` (unobservable).
- **Design ≠ implementation.** Six of the eight Phase-3 work packages (P3-WP1…WP8) are not started.

## 6. Decision

**Phase 3 DESIGN is complete and self-consistent.** Phase 2 remains `PASS` (untouched); Phase 1 remains
`PARTIAL`. The production detection engine (P3-WP1…WP8) **must not begin without explicit approval**.

## 7. Change history

| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-08-29 | Phase-3 design gate recorded: DET-001 + ADR-0005/0006 + design contracts + 15 machine-checked golden cases. Implementation not started. | Detection Architect |
| 1.1 | 2026-08-29 | Design gate **approved**; two closure changes applied (§4a): (1) seed-corpus `expected_outcome → phase2_expected_outcome` rename (coarse Phase-2 expectation, not runtime severity; TL-CRED-001 kept CRITICAL); (2) `validate_det_design.py` promoted to the **10th canonical check** in `run_all.py` + CI path triggers + docs. Full 10-check gate PASS; self-test PASS. Implementation still not started. | Detection Architect |
