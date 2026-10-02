# GATE-019 — Phase 6 data contract foundation checkpoint

| Field | Value |
|---|---|
| Document ID | GATE-019 |
| Version | 1.0 |
| Status | **LOCAL / INDEPENDENT P6-WP1 CONTRACT APPROVED — REMOTE CI + MERGE PENDING**; P6-WP1 not yet closed; not Phase-6 closure |
| Phase assessed | Phase 6 — P6-WP1 canonical data domain & lifecycle contract foundation |
| Owner role | Data Architect / Backend Architect |
| Baseline | Phase-5 closure merge `6c20f448d6df3e36f2a2e9cc97a806aa1deb4f36` (PR #25) |
| Primary deliverable | [DATA-001](../06-contracts/DATA-001-data-domain-lifecycle-contract.md) v0.1 — P6-WP1 contract approved following independent review |
| Independent review | BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 5 / INFO 4 — **FINAL RECOMMENDATION: APPROVE** |
| Governing authority | ARCH-001…007; ADR-0004/0005/0006/0007/0008/0009/0010/0013/0014/0015/0016/0017; DET-001; AI-001 (WP4/WP5); KB-001/KB-002 |
| Related open items | OI-05 (retention/legal basis), G-09 (efficacy), WP4 LOW-3 (SSRF-TOCTOU → ADR-0012), ASM-002 (single tenant, unconfirmed) |
| Last updated | 2026-10-02 |

## 1. Checkpoint purpose

GATE-019 is the checkpoint for the first Phase-6 work package. It assesses whether DATA-001 establishes a canonical
**logical** data contract that later Phase-6 packages (P6-WP2 persistence/schema + ADR-0011, P6-WP3 API, P6-WP4
OpenAPI, P6-WP5 integrations + ADR-0012, P6-WP6 operational contracts) can use without guessing, while preserving
accepted Phase-5 architecture. Following independent review, the P6-WP1 contract is **approved locally**. This
gate does not close P6-WP1 or Phase 6, issue an ADR, or authorize implementation; formal P6-WP1 closure requires
remote CI PASS and merge (§6).

## 2. Acceptance criteria

| # | Criterion | Evidence | State |
|---:|---|---|---|
| 1 | DATA-001 exists with P6-WP1 contract status | DATA-001 metadata, §§26–27 | APPROVED — INDEPENDENT REVIEW |
| 2 | Canonical domain objects defined (identity, case, submission, evidence item, derivative, envelope, governed input artifact, AI provenance, evaluation, result, correction, review routing, adjudication, report, replay, enrichment, knowledge reference/activation, audit, retention/deletion, cross-store operation, feedback) | DATA-001 §5, Matrix A §6 | APPROVED — INDEPENDENT REVIEW |
| 3 | Store authority preserved (`KNOW`/`OPS`/`ECS`/`AUD`/`SEC`/`IDP`/`TEL`/`MEM`) | DATA-001 §§3.3, 4 | APPROVED — INDEPENDENT REVIEW |
| 4 | Knowledge authority remains Git/bundle | DATA-001 §§5.17, 18 | APPROVED — INDEPENDENT REVIEW |
| 5 | PostgreSQL does not become authoritative knowledge store | DATA-001 §§2, 5.17, 18 | APPROVED — INDEPENDENT REVIEW |
| 6 | `EvidenceContentStore` owns raw evidence bytes | DATA-001 §§3.3, 5.4 | APPROVED — INDEPENDENT REVIEW |
| 7 | Identity/authorization resource context represented | DATA-001 §§5.1, 14 | APPROVED — INDEPENDENT REVIEW |
| 8 | Evidence original/derivative distinction explicit | DATA-001 §§5.4–5.6, 8 | APPROVED — INDEPENDENT REVIEW |
| 9 | SHA-256 integrity semantics correct (integrity relative to trusted pin; not truth/authorship/admissibility) | DATA-001 §8.2 | APPROVED — INDEPENDENT REVIEW |
| 10 | Evaluation/result immutability explicit; evaluation ↔ governed input artifact exactly 1 ↔ 1 (LOW-1 fixed) | DATA-001 §§5.7, 5.9, 5.10, 7, 10 | APPROVED — LOW-1 FIXED |
| 11 | Exact replay pins defined | DATA-001 §11.1 (Matrix E) | APPROVED — LOW-2 DEFERRED (non-blocking) |
| 12 | Phase-4 governed artifact replay preserved | DATA-001 §§5.8, 12 | APPROVED — INDEPENDENT REVIEW |
| 13 | No historical AI model recall during replay | DATA-001 §§11.2, 11.3, 12 | APPROVED — INDEPENDENT REVIEW |
| 14 | Analyst adjudication separated from `DetectionResult` | DATA-001 §5.13 | APPROVED — INDEPENDENT REVIEW |
| 15 | Report reproducibility data defined, conditional on retained source artifacts (LOW-3 fixed) | DATA-001 §§5.14, 11.1, 17.2 | APPROVED — LOW-3 FIXED |
| 16 | Audit/telemetry separation preserved | DATA-001 §§15, 16 | APPROVED — INDEPENDENT REVIEW |
| 17 | Data classification defined (`C1`…`C8`) | DATA-001 §3.4, Matrix C §15.1 | APPROVED — INFO-1 CARRIED |
| 18 | Raw evidence excluded from general telemetry/logging | DATA-001 §15.2 | APPROVED — INDEPENDENT REVIEW |
| 19 | Retention/deletion model present | DATA-001 §§5.19, 17 (Matrix F) | APPROVED — INDEPENDENT REVIEW |
| 20 | OI-05 remains OPEN without invented duration/legal basis (ASM-014 placeholder not adopted) | DATA-001 §§5.19.1, 17.1 | APPROVED — INFO-3 |
| 21 | Schema evolution principles defined | DATA-001 §21 | APPROVED — INDEPENDENT REVIEW |
| 22 | No physical SQL schema, API contract, ORM, migration tool or product selection | DATA-001 §§1, 22 | APPROVED — INDEPENDENT REVIEW |
| 23 | ADR-0011 remains Planned | §3 below | CONFIRMED |
| 24 | ADR-0012 remains Planned | §3 below | CONFIRMED |
| 25 | WP4 LOW-3 remains deferred to ADR-0012 | DATA-001 §20 | CONFIRMED |
| 26 | Phase 3/4 frozen; `ENGINE_VERSION = 1.0.0` | Change surface + validation §5 | PASS — LOCAL BUILDER |
| 27 | G-09 remains OPEN | DATA-001 §§1, 26; §4 below | CONFIRMED |
| 28 | No production-readiness or compliance claim | DATA-001 §§1, 17.1, 26 | APPROVED — INDEPENDENT REVIEW |
| 29 | Canonical local validation passes | §5 below | PASS — LOCAL BUILDER |
| 30 | Independent review before acceptance/merge | §7 below | **APPROVE** (independent reviewer) |
| 31 | Single-tenant physical-schema assumption explicitly provisional (LOW-4) | DATA-001 §5.2, §23 item 12 | RECORDED — UNCONFIRMED / PROVISIONAL |

## 3. Decision records

| ADR | Topic | Status after P6-WP1 |
|---|---|---|
| ADR-0011 | Database migration tooling (depends on DATA-001) | **Planned / not issued** — belongs to P6-WP2 |
| ADR-0012 | Threat-intelligence adapter/provider + DNS-rebinding/SSRF-TOCTOU controls | **Planned / not issued** — belongs to the integration WP |

`adr/README.md` is unchanged.

## 4. Programme and claim status

| Item | Status |
|---|---|
| Phase 1 | PARTIAL |
| Phase 2 | PASS |
| Phase 3 | CLOSED at `phase3-wp8-v1.0`; `ENGINE_VERSION = 1.0.0` |
| Phase 4 | FORMALLY CLOSED (GATE-011); optional, default-OFF, non-authoritative |
| Phase 5 | FORMALLY CLOSED (GATE-018; PR #25 merged; remote CI PASS) |
| Phase 6 | **IN PROGRESS** — P6-WP1 contract approved locally/independently; remote CI + merge pending; P6-WP2…WP6 not started |
| Phase 7 / UI | NOT STARTED |
| OI-05 | **OPEN** — retention duration, legal basis and residual metadata NOT YET SPECIFIED (Sponsor + legal/governance) |
| ASM-002 single tenant | **UNCONFIRMED / PROVISIONAL** (Sponsor / Programme) |
| G-09 | **OPEN** |
| WP4 LOW-3 | **OPEN / DEFERRED** → Phase-6 integration WP / ADR-0012 |

No production-readiness, DPDP or other legal-compliance, legal-admissibility, certified-custody, availability, or
detection-efficacy (accuracy/precision/recall/false-positive/negative) claim is made.

## 5. Required local builder validation

| Check | Required result | State |
|---|---|---|
| `.venv/bin/python knowledge/validation/run_all.py` | PASS — 23/23 | PASS — LOCAL BUILDER |
| `.venv/bin/python knowledge/validation/run_all.py --json` | `gate=PASS`, `validators_run=23`, `validators_failed=0` | PASS — LOCAL BUILDER |
| `.venv/bin/python knowledge/validation/ci_selftest.py` | PASS — 7/7 defects caught | PASS — LOCAL BUILDER |
| Phase-3/Phase-4/publish/schema/rule freeze and `ENGINE_VERSION` | zero diff; `1.0.0` | PASS — LOCAL BUILDER |
| `git diff --check` and Markdown whitespace of both P6-WP1 files | clean | PASS — LOCAL BUILDER |

Local builder results do not replace remote CI.

## 6. Finalisation conditions

| # | Condition | State |
|---:|---|---|
| 1 | Independent P6-WP1 review returns APPROVE | **SATISFIED** — APPROVE (BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 5 / INFO 4) |
| 2 | Canonical local validation PASS (23/23) and CI self-test PASS (7/7) | SATISFIED — LOCAL BUILDER |
| 3 | Remote GitHub Actions PASS where triggered | **PENDING** |
| 4 | Approved change merged to `main` | **PENDING** |

Until conditions 3 and 4 are met the correct state is **P6-WP1 CONTRACT APPROVED — REMOTE CI + MERGE PENDING**,
not P6-WP1 CLOSED. Phase 6 is not closed by this gate.

## 7. Independent review outcome and dispositions

Independent P6-WP1 review: **BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 5 / INFO 4 — FINAL RECOMMENDATION: APPROVE.**
The builder did not review its own work.

| Finding | Severity | Disposition | Owner |
|---|---|---|---|
| LOW-1 Evaluation → governed input artifact shown as n → 1, although the artifact embeds `evaluation_id`/`evaluation_timestamp` and re-evaluation creates a new artifact | LOW | **FIXED** — exact 1 ↔ 1 in DATA-001 §5.7, §5.9, Diagram A, Matrix B, §11.3; several evaluations never share one artifact; replay pins the exact artifact. Phase-3/4 semantics unchanged | Closed in P6-WP1 |
| LOW-2 Exact replay / evidence re-verification material set not yet a final physical persistence requirement; replay must still fail if a retained governed artifact is insufficient after evidence deletion | LOW | **NON-BLOCKING for P6-WP1; DEFERRED.** Preserved now: fail closed, no AI recall, no latest/current substitution, no approximate replay success (DATA-001 §11.1, §23 item 14) | P6-WP2 persistence contract; P6-WP6 operational/replay contract |
| LOW-3 Report reproducibility not stated as conditional on retained source artifacts | LOW | **FIXED** — reproduction guaranteed only while all required governed source artifacts are retained; explicit regeneration-unavailable state; no approximate reconstruction, AI recall or substitution; no sensitive retention solely for reproduction unless policy permits; OI-05 OPEN (DATA-001 §5.14, §11.1, §17.2) | Closed in P6-WP1 (format remains Phase 7 / REPORT-001) |
| LOW-4 DATA-001 relies on ASM-002 single tenant, whose sponsor confirmation is outstanding | LOW | **RECORDED** — SINGLE-TENANT PHYSICAL-SCHEMA ASSUMPTION: **UNCONFIRMED / PROVISIONAL**; not claimed resolved; confirmation required before P6-WP2 finalizes physical schema decisions that would be costly to reverse; if multi-tenancy is confirmed instead, P6-WP2 must STOP and reconcile before physical schema acceptance; multi-tenancy not designed (DATA-001 §5.2, §23 item 12) | Sponsor / Programme |
| LOW-5 `docs/06-contracts/**` not directly covered by the workflow path filter | LOW | **RECORDED; workflow unchanged.** This WP triggers CI through `docs/00-program/**`, so P6-WP1 can close. **P6-WP2 acceptance criterion:** before the first validator/schema/contract test depends on `docs/06-contracts/**`, the workflow path filter MUST include the relevant Phase-6 contract paths (DATA-001 §23 item 13) | P6-WP2 / first Phase-6 machine-readable contract-validation work |
| INFO-1 Matrix C lists `C6` as `AUD`-only while `DeletionAction` is `OPS` + `AUD` | INFO | Non-blocking; carried to P6-WP2 wording/schema reconciliation; stores not redesigned | P6-WP2 |
| INFO-2 `RESULT_COMPUTED_PERSISTENCE_PENDING` lacks a terminal path if the in-memory result is lost before persistence | INFO | Non-blocking; carried to P6-WP2. Expected direction: `FAILED_INFRASTRUCTURE`, a new evaluation if retried, and no pretence that the original result was durably completed. Not implemented here | P6-WP2 |
| INFO-3 ASM-014 contains a retention placeholder | INFO | Correctly not adopted; OI-05 remains authoritative and OPEN | Sponsor + legal/governance |
| INFO-4 Stale SRS / ASM wording (Java/Spring backend, database-owned rule entities) | INFO | Historical and already flagged in DATA-001 §2; no modification in P6-WP1 | Programme documentation owner |

## 8. Change boundary

P6-WP1 change surface: **new** `docs/06-contracts/DATA-001-data-domain-lifecycle-contract.md` and **new**
`docs/00-program/GATE-019-phase-6-data-contract-foundation.md`; no other tracked file. The roadmap, SRS, ADR index,
prior ADRs/ARCH documents, CI workflow, Phase-3 runtime, Phase-4 AI code, promoted schemas, rules, taxonomies,
knowledge bundles, publication code and canonical validators are unchanged.

## 9. Recommendation

Proceed to the P6-WP1 commit and PR. After remote CI PASS and merge to `main`, P6-WP1 may be recorded as CLOSED.
Do not issue ADR-0011 or ADR-0012 and do not begin P6-WP2 under this checkpoint.
