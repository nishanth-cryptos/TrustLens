# GATE-024 — Phase 6 operational contract checkpoint

| Field | Value |
|---|---|
| Document ID | GATE-024 |
| Version | 1.0 |
| Status | **P6-WP6 OPERATIONAL CONTRACT APPROVED — REMOTE CI + MERGE PENDING**; P6-WP6 not yet formally closed; not Phase-6 closure |
| Phase assessed | Phase 6 — P6-WP6 operational / replay contracts, additive persistence follow-ups, enrichment API activation |
| Owner role | Backend / Data / Operations Architect |
| Baseline | P6-WP5 merge `8fb963e955c06ded736c81d8f8a076ee599b910d` (PR #30) |
| Primary deliverables | [OPS-001](../06-contracts/OPS-001-operational-replay-persistence-contract.md) v0.1; [`contracts/operations/operational-v1.json`](../../contracts/operations/operational-v1.json); [`operational-contract.schema.json`](../../contracts/operations/operational-contract.schema.json); `contracts/operations/fixtures/negative-mutations.json`; `knowledge/validation/validate_operational_contract.py` |
| Deltas reviewed here | DATA-001 **P6-WP6 ADDITIVE REVISION** (logical objects `ApiIdempotencyRecord` §5.22, `GovernedRemovalTombstone` §5.23; Matrix A rows 29–30; §29); DATA-001-WP2 / `schema-v1.json` **P6-WP6-ADD-001** (contract 0.2.0); API-001 / OAS-001 / `api-v1.json` / `openapi-v1.json` **P6-WP6 ADDITIVE ACTIVATION** and audit-read event; INT-001 machine-contract `api_surface` alignment; `validate_integration_contract.py` IC-46 pin update |
| Independent review | Initial: BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 1 / INFO 3 — REQUEST_CHANGES (§8). Targeted re-review: BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 0 / INFO 0 new — **APPROVE** (§9) |
| Related open items | G-09; OI-05; ASM-002 |
| Last updated | 2026-10-03 |

## 1. Checkpoint purpose

GATE-024 assesses whether P6-WP6 resolves the operational and persistence dependencies deferred by P6-WP2…P6-WP5 at
contract level, additively and without redesigning accepted semantics, and whether the result is mechanically validated
offline. GATE-019…GATE-023 are not modified and did not review these deltas; this gate owns them. The original DATA-001
approval (GATE-019) remains historical; the P6-WP6 additive logical-object delta is reviewed only here. It does not accept
OPS-001, implement anything or close Phase 6.

## 2. Acceptance criteria

| # | Criterion | Evidence | State |
|---|---|---|---|
| 1 | OPS-001 exists (v0.1, Candidate) | OPS-001; OC-01 | MET |
| 2 | Operational machine contract + schema exist | `operational-v1.json`, schema; OC-03 | MET |
| 3 | Durable idempotency persistence defined | `api_idempotency_record`; OPS-001 §4; OC-05…OC-07, OC-09…OC-12 | MET |
| 4 | Idempotency concurrency invariant defined | unique-scope claim, fence, atomic completion; OC-08; SI scenarios (OC-66) | MET |
| 5 | Finite idempotency window, no invented duration | OPS-001 §5; OC-13, OC-14 | MET |
| 6 | ETag mutation revisions persisted for all If-Match aggregates | `mutation_revision` on case_record / review_routing_state / deletion_request; OC-15…OC-20; SE scenarios | MET |
| 7 | External-enrichment additive provenance complete | OPS-001 §7; OC-21, OC-26, OC-27 | MET |
| 8 | `safe_error_category` vocabulary governed | `enrichment_safe_error_category` = INT-001 exactly; OC-23 | MET |
| 9 | Technical outcome vocabulary exact; CLEAN advisory; not consumed | OC-22, OC-24, OC-25 | MET |
| 10 | Enrichment audit events added | `audit_event_type` +7 (+ EGRESS_DENIED reused); OC-28 | MET |
| 11 | Audit-read accountability defined | `AUDIT_LOG_ACCESSED`; listAuditEvents wired; OC-29, OC-30 | MET |
| 12 | DetectionResult immutability preserved | OC-32 | MET |
| 13 | Deletion tombstone defined (content-free) | `governed_removal_tombstone`; OC-31, OC-33 | MET |
| 14 | Cross-store deletion verification defined | OPS-001 §9; OC-34, OC-36; SD scenarios | MET |
| 15 | Partial deletion failures explicit | OC-35 | MET |
| 16 | Restore anti-resurrection defined | OPS-001 §11; OC-37; SX scenarios | MET |
| 17 | Report-after-deletion semantics preserved | OC-38; SP scenarios | MET |
| 18 | Replay-after-deletion semantics preserved | OC-39; SR scenarios | MET |
| 19 | Historical replay: no AI / no provider call / no latest substitution | OC-40…OC-42 | MET |
| 20 | RM-01…RM-14 binding unchanged; enrichment not replay material | OC-43 | MET |
| 21 | Re-analysis remains a new Evaluation | OC-44 | MET |
| 22 | Provider-policy publication / version semantics defined | OPS-001 §10; OC-45…OC-48 | MET |
| 23 | Reserved enrichment endpoint activated consistently | OC-49, OC-50, OC-62 | MET |
| 24 | Enrichment response advisory and content-safe | OC-51 | MET |
| 25 | API/OpenAPI parity preserved; operation count unchanged (53 → 53) | OC-52; `validate_api_contract.py`, `validate_openapi_contract.py` PASS | MET |
| 26 | Required deployment parameters catalogued (24; 22 security/correctness, 2 implementation-profile; retention scoped to automatic expiry) | OPS-001 §16; OC-53, OC-54, OC-58 | MET |
| 27 | No numeric limits invented | OC-14, OC-55 | MET |
| 28 | Additive revision recorded without rewriting history | `additive_revisions`; DATA-001-WP2 §27; DATA-001 §29; OC-61 | MET |
| 28a | Physical tables map to truthful DATA-001 logical objects (`ApiIdempotencyRecord`, `GovernedRemovalTombstone`); no unrelated-object mapping; DC-05 unweakened | DATA-001 §§5.22–5.23, Matrix A; `schema-v1.json`; OC-67; DC-05 PASS unmodified | MET |
| 29 | Earlier validators still pass; only the obsolete IC-46 pin changed | canonical gate 28/28 | MET |
| 30 | G-09 OPEN | §4; OC-57 | MET |
| 31 | OI-05 OPEN | §4; OC-58 | MET |
| 32 | ASM-002 provisional; no tenant field | §4; OC-56 | MET |
| 33 | ENGINE_VERSION 1.0.0 | OC-59 | MET |
| 34 | Validator exists and is wired (28th check) | `run_all.py` | MET |
| 35 | Negative mutations exist (91), each naming its check | fixture; OPS-001 §18 | MET |
| 36 | Self-test proves the validator bites (13th defect) | `ci_selftest.py` 13/13 | MET |
| 37 | No implementation claim; no runtime code | OPS-001 §1; OC-60 | MET |
| 38 | Independent review | Initial REQUEST_CHANGES (§8) → targeted re-review APPROVE (§9) | **MET** |

## 3. Validation evidence

| Check | Result |
|---|---|
| `validate_operational_contract.py` | PASS — 67 checks, 28 offline scenarios, 91 negative mutations rejected |
| `validate_data_contract.py` (unmodified) | PASS — 39 tables, 77 vocabularies, 28 negative mutations rejected |
| `validate_api_contract.py` (unmodified) | PASS — 53 operations |
| `validate_openapi_contract.py` (unmodified) | PASS — 53 operations in parity |
| `validate_integration_contract.py` (IC-46 pin updated) | PASS — 91 negative mutations rejected |
| `run_all.py` / `ci_selftest.py` | PASS 28/28 / PASS 13/13 (builder and reviewer) |
| `ENGINE_VERSION` | `1.0.0` |

Validation is static and offline (no database, server, network or API key).

## 4. Preserved open items

| Item | Status |
|---|---|
| G-09 | **OPEN** — no effectiveness claim |
| OI-05 | **OPEN** — retention durations, residual metadata and backup purge timing NOT YET SPECIFIED |
| ASM-002 | **UNCONFIRMED / PROVISIONAL** |
| Idempotency persistence | CONTRACT-LEVEL CLOSED — runtime pending Phase 9 |
| ETag revision persistence | CONTRACT-LEVEL CLOSED — runtime pending Phase 9 |
| P6-WP5 LOW-2 | CONTRACT-LEVEL CLOSED — runtime pending Phase 9 |
| WP4 INFO collection ETag / `action_code` enum | Informational |

## 5. Known limitations for the reviewer

- **Logical-object mapping (resolved by the MEDIUM-1 correction):** DATA-001 now declares `ApiIdempotencyRecord` and
  `GovernedRemovalTombstone`; the earlier `CrossStoreOperation` / `DeletionAction` mappings are removed.
- **Activation wording:** INT-001 §34 (accepted) said the endpoint would be activated "only when an implementation
  exists (P6-WP6)". P6-WP6 performs a **contract-level** activation as the brief directs; runtime serving still requires
  the Phase-9 implementation. INT-001's machine contract and §34 record the new state.
- **Anti-resurrection source:** the invariant depends on a post-backup deletion record retained outside the restorable
  snapshot; that mechanism is an implementation decision (`REQUIRED_BEFORE_DEPLOYMENT`), and promotion is blocked
  without it.
- **Historical status strings:** original status rows in DATA-001, DATA-001-WP2, API-001, OAS-001 and INT-001 are
  preserved as history; each now carries a separate **Current revision state** row (original work package merged; P6-WP6
  additive delta approved following independent review, remote CI + merge pending).
- Scenario reference models prove contract coherence only; nothing has been executed against a database or server.

## 6. Claim boundary

No database migrated, PostgreSQL running, API implemented, OpenAPI deployed, idempotency/ETag implemented, connector
implemented, backup deletion physically guaranteed, penetration test, production readiness, legal compliance or
admissibility, accuracy, precision, recall or false-positive-rate claim is made. Phase-3, Phase-4, rules/taxonomies,
runtime detection engine, AI runtime and `ENGINE_VERSION` are unchanged.

## 7. Decision

**P6-WP6 OPERATIONAL CONTRACT APPROVED — REMOTE CI + MERGE PENDING.** P6-WP6 is not yet formally closed (remote CI +
merge outstanding); P6-WP7 not started.

## 8. Initial independent review (REQUEST_CHANGES) and corrections — historical record

| Finding | Correction |
|---|---|
| MEDIUM-1 — `api_idempotency_record` falsely mapped to `CrossStoreOperation` only to satisfy DC-05 (tombstone → `DeletionAction` only partly defensible) | Narrow additive DATA-001 revision: new logical objects `ApiIdempotencyRecord` (§5.22: `C2`, `M-OPS`, `OPS`, finite active window, no replay relevance, never authorization) and `GovernedRemovalTombstone` (§5.23: `C2`, `M-IMM`, `OPS`, content-free, one per removed resource, distinct from `DeletionAction`, not a substitute for replay material); Matrix A rows 29–30; `schema-v1.json` mappings and coverage re-pointed; DC-05 unchanged; new OC-67 + 3 targeted mutations |
| LOW-1 — `RETENTION_DURATIONS` declared always-required finite expiry, contradicting `UNRESOLVED_OI05` | Parameter now applies only when OI-05 enables governed automatic expiry (option A); no duration; OI-05 OPEN; OC-58 + mutation |
| INFO-1 — audit-read ordering | Authorize → snapshot → append one `AUDIT_LOG_ACCESSED` → return snapshot; no self-inclusion; append failure withholds the read; OC-30 + 2 mutations |
| INFO-2 — tuning values as security startup blockers | Two classes: `REQUIRED_BEFORE_DEPLOYMENT_SECURITY_OR_CORRECTNESS` vs `CONFIGURATION_REQUIRED_FOR_IMPLEMENTATION_PROFILE` (`INLINE_VS_ECS_THRESHOLD`, `PAGINATION_DEFAULT_LIMIT`); OC-54 + mutation |
| INFO-3 — stale status wording | "Current revision state" rows added to DATA-001, DATA-001-WP2, API-001, OAS-001, INT-001; historical status rows preserved |

All accepted P6-WP6 semantics (idempotency, ETag/CAS, enrichment persistence, audit vocabulary, deletion, restore,
replay, provider policy, API activation, 53-operation parity, IC-46) are unchanged.

All five corrected findings are **CLOSED**: MEDIUM-1, LOW-1, INFO-1, INFO-2, INFO-3.

## 9. Targeted independent re-review — APPROVE

| Item | Result |
|---|---|
| Counts | BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 0 / INFO 0 new — **APPROVE**; carried programme/implementation items remain separately owned and are not new findings |
| Reviewer validation | `run_all` PASS 28/28; `run_all --json` gate=PASS, validators_run=28, validators_failed=0; `ci_selftest` PASS 13/13; operational validator PASS (67 checks, 28 scenarios, 91/91 negative mutations rejected); `ENGINE_VERSION = 1.0.0` |
| MEDIUM-1 | **CLOSED** — `api_idempotency_record` → `ApiIdempotencyRecord`; `governed_removal_tombstone` → `GovernedRemovalTombstone`; DATA-001 declares both (Matrix A rows 29–30; §5.22, §5.23); `CrossStoreOperation` keeps its original meaning; `DeletionAction` (execution of a deletion step) and `GovernedRemovalTombstone` (content-free durable residual fact of a governed removal) remain distinct; DC-05 unchanged; OC-67 protects the mappings |
| LOW-1 | **CLOSED** — `RETENTION_DURATIONS` applies only when `GOVERNED_AUTOMATIC_EXPIRY_ENABLED`; until OI-05 resolves the policy no automatic expiry runs; OI-05 OPEN; deployment is not blocked solely because OI-05 is unresolved; no duration invented |
| INFO-1 | **CLOSED** — `AUDIT_LOG_ACCESSED` ordering: authorize → establish result snapshot → append one access event → return the established snapshot; the new event is never in its own response; append failure → `READ_NOT_RETURNED` |
| INFO-2 | **CLOSED** — `INLINE_VS_ECS_THRESHOLD`, `PAGINATION_DEFAULT_LIMIT` = `CONFIGURATION_REQUIRED_FOR_IMPLEMENTATION_PROFILE`, not security/correctness startup blockers; no numeric defaults |
| INFO-3 | **CLOSED** — historical document statuses preserved; current revision state separated |

Contract-level closures preserved (runtime implementation pending Phase 9; **not** implemented): API idempotency
persistence, ETag revision persistence, external-enrichment persistence (P6-WP5 LOW-2).

Open / separately owned: G-09 OPEN; OI-05 OPEN; ASM-002 UNCONFIRMED / PROVISIONAL; all 24 operational parameter values
NOT YET SPECIFIED (existing owners/classes); provider-policy physical storage → Phase 9; restore deletion-authority
physical storage → Phase 9 / REQUIRED_BEFORE_DEPLOYMENT; SQL / triggers / migrations, API server, workers, connector →
Phase 9.
