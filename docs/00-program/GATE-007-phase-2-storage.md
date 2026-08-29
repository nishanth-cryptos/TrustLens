# GATE-007 — Phase 2 checkpoint: knowledge storage architecture (WP8, ADR-0004)

| Field | Value |
|---|---|
| Document ID | GATE-007 |
| Version | 1.0 |
| Status | **Checkpoint** — assesses WP8 ADR-0004 (knowledge storage); ADR-0014 remains blocked |
| Phase assessed | Phase 2 — Knowledge engineering (WP8) |
| Owner role | Technical Program Director |
| Dependencies | GATE-006, KB-001 (v1.2), KB-002, ADR-0003, ADR-0004, ADR-0014, ADR-0015 |
| Gate result | **`PASS` for ADR-0004; Phase 2 IN PROGRESS — one Sponsor decision (OI-04) outstanding, Phase 3 NOT STARTED** |
| Phase 1 status | **`PARTIAL`** — unchanged ([GATE-001 §7](GATE-001-phase-1-assessment.md)) |
| Last updated | 2026-08-29 |

---

## 1. Scope
WP8 makes the two remaining Phase-2 architecture decisions. **ADR-0004 (knowledge storage) is decided and
Accepted.** **ADR-0014 (language strategy) is authored as Proposed but remains BLOCKED on OI-04.** No
production detection or extraction code was built; no rule/evidence/taxonomy/extraction semantics changed.

## 2. ADR-0004 — the decision
**Option B: Git/JSON as the single authoritative source of truth + a generated, immutable, SHA-256-hashed
published knowledge bundle for runtime.** Full ADR: [ADR-0004](../../adr/ADR-0004-knowledge-storage-architecture.md).

| Question | Answer |
|---|---|
| Authoritative store | **Git repository** (authored JSON + Markdown); review/approval/publish stay git-diff + CI |
| Published artifact | **Immutable, versioned, hash-addressed bundle** (`build_bundle.py` → `bundle-manifest.json`) |
| Runtime store | **In-memory indexes loaded from a bundle** — no DB needed to hold knowledge |
| Database role | **Operational/audit/analytics only**, or a one-way (bundle → DB) read-only materialized cache; never authoritative |
| Graph database | **NOT JUSTIFIED** — relationships are logical IDs, MVP scale is tiny; optional-future only |
| Raw evidence | **Stays in Git now**, referenced by SHA-256; migration-safe to Git LFS / object storage without invalidating any record |
| Version/rollback | Manifest pins every component version + content digest; rollback = activate bundle N-1; no silent mutation of recorded decisions |
| Integrity | SHA-256 per file + content digest; evidence PDFs hashed (ADR-0015); protected `main` + required gate; **signed releases a reserved path** |
| On-prem/offline | Bundle self-contained; runtime needs no network; only `pip install` (build/CI) touches the network |

Rejected: A (no immutable/integrity boundary), C/D (DB authoritative — loses Git diff review + evidence-first
traceability, adds sync/migration burden at trivial scale), E (graph without a query that needs one).

## 3. Proof-of-architecture tooling (STEP 17) — delivered
- **`knowledge/schemas/bundle-manifest.schema.json`** — the manifest contract (Draft 2020-12).
- **`knowledge/publish/build_bundle.py`** — deterministic, offline builder (commit SHA read from
  `GITHUB_SHA`/`.git/HEAD` as files; no subprocess/network). Bundle = 38 files (26 rules + 3 indicator
  files + 2 taxonomy + 5 schemas + 2 evidence-metadata); **excludes** raw PDFs, test corpora, coverage
  matrix and validators.
- **`knowledge/publish/validate_bundle.py`** — integrity validator: manifest schema-valid, every file
  hash re-verified, content digest reproducible, **build deterministic (built twice, identical digest)**,
  all 9 component versions pinned, runtime bundle excludes PDFs/test data.
- **Wired as the 9th check in `run_all.py`** and therefore into GitHub Actions. The built bundle is a
  git-ignored artifact (`build/`), reproducible on demand — not committed.

## 4. ADR-0014 / OI-04 — remains BLOCKED
The **engineering** posture is already language/script-extensible and honest (rule `language_scope` with
`on_unsupported_input: FLAG_UNSUPPORTED`, envelope `language`/`script`, seed case A-006 flags Hinglish as
`UNSUPPORTED`). What is unresolved is the **product scope**: *which* Indian languages MVP detection
supports — [OI-04](PROGRAM-001-program-charter.md#11-open-issues), an explicit **Sponsor** decision, and
additionally gated by [G-08](../01-research/RESEARCH-005-gap-register.md) (**no verified source supplies
non-English cues**, so any added would be `HEURISTIC` and un-publishable without a research pass). The
smallest decision is recorded in [ADR-0014](../../adr/ADR-0014-language-and-script-strategy.md): option
**A** (English only, schemas extensible), **B** (English + Hindi), or **C** (English + selected Indian
languages). This gate does **not** choose.

## 5. Effect on the knowledge base
**None.** No rule scope/status/severity, indicator, taxonomy, negative library or extraction contract
changed. 18 PUBLISHED rules, 55/55 runner cases, extraction contracts and prior gates all unaffected.

## 6. Results (all green)
```
QUALITY GATE: PASS — all 9 checks green (~0.5s)   [8 validators + bundle integrity]
BUNDLE: content_digest 6ab015d1…  38 files  26 rules (18 published)  63 positives  29 negatives
SELF-TEST: PASS — 5 representative defects caught; real repository untouched
```
**LOCAL validated.** Remote GitHub Actions will run on push/PR (path filter already covers `knowledge/**`
and `adr/**`).

## 7. Remaining Phase 2 work
| WP | Status |
|---|---|
| WP2 extraction contracts · WP5 taxonomy · WP6 KB-001 · WP7 CI | ✅ done |
| WP8 ADR-0004 knowledge storage | ✅ **done (this gate)** |
| WP8 ADR-0014 language strategy | ⛔ **Proposed — BLOCKED on OI-04** (Sponsor decision) — the sole remaining Phase-2 item |

## 8. Phase-2 readiness
Every WP2–WP8 engineering item is complete and green. The **only** thing between Phase 2 and COMPLETE is
**one Sponsor decision (OI-04)**. Phase 2 is therefore **IN PROGRESS, gated solely on an owner decision** —
not on any further engineering. Phase 3 (DET-001) must not begin until explicitly approved.

## 9. Change history
| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-08-29 | WP8 assessed. ADR-0004 Accepted (Git source of truth + immutable hashed runtime bundle; DB operational-only; graph not justified; evidence hash-addressed). Manifest schema + builder + integrity validator delivered and wired as the 9th gate check. ADR-0014 authored Proposed/BLOCKED on OI-04. Knowledge base unaffected; Phase 2 IN PROGRESS pending one Sponsor decision. | Technical Program Director |
