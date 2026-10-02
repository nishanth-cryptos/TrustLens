# GATE-020 — Phase 6 PostgreSQL persistence contract checkpoint

| Field | Value |
|---|---|
| Document ID | GATE-020 |
| Version | 1.0 |
| Status | **LOCAL / INDEPENDENT P6-WP2 PERSISTENCE CONTRACT APPROVED — REMOTE CI + MERGE PENDING**; P6-WP2 not yet formally closed; not Phase-6 closure |
| Phase assessed | Phase 6 — P6-WP2 PostgreSQL persistence contract + ADR-0011 |
| Owner role | Data Architect / Backend Architect |
| Baseline | P6-WP1 merge `0ac84cd89be1f15895e7f8c3a8cd39126cfaa874` (PR #26) |
| Primary deliverables | [DATA-001-WP2](../06-contracts/DATA-001-WP2-postgresql-persistence-contract.md) v0.1; [`contracts/postgresql/schema-v1.json`](../../contracts/postgresql/schema-v1.json) (contract 0.1.0) + JSON Schema + negative fixtures; [ADR-0011](../../adr/ADR-0011-database-migration-tooling.md) (**Accepted**); `knowledge/validation/validate_data_contract.py` |
| Governing authority | DATA-001 v0.1; ARCH-003…007; ADR-0004/0008/0009/0010/0013/0016/0017; DET-001; AI-001 WP4/WP5 |
| Independent review | Initial: BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 4 / INFO 4 — REQUEST_CHANGES. Targeted re-review: BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 2 / INFO 3 — **APPROVE** (§7a, §7b) |
| Related open items | ASM-002 (single tenancy, unconfirmed — blocks the first schema-creating migration, not this contract), OI-05, G-09, WP4 LOW-3 (→ ADR-0012), RSK-006 (no PostgreSQL available) |
| Last updated | 2026-10-02 |

## 1. Checkpoint purpose

GATE-020 assesses whether P6-WP2 turns DATA-001 into an implementation-ready PostgreSQL persistence contract with a
migration-tooling decision (ADR-0011), machine-checkable structure and CI coverage, while preserving Phase-5 authority
and DATA-001 meaning. Following independent review the contract is approved locally and ADR-0011 is Accepted; formal
P6-WP2 closure still requires remote CI PASS and merge (§6). It does not implement a database or close Phase 6.

## 2. Acceptance criteria

| # | Criterion | Evidence | State |
|---:|---|---|---|
| 1 | Persistence contract exists, supplementing (not replacing) DATA-001 | DATA-001-WP2 metadata, §§1–2 | AUTHORED |
| 2 | Every DATA-001 canonical object mapped (Feedback explicitly deferred Post-MVP) | WP2 §6; contract `logical_object_coverage`; DC-05 | AUTHORED — VALIDATED |
| 3 | Git/bundle remains knowledge authority; no rule/indicator/taxonomy tables | WP2 §§2, 14; DC-06 | AUTHORED — VALIDATED |
| 4 | Raw evidence bytes and full submitted content never in PostgreSQL | WP2 §5.5; DC-07 | AUTHORED — VALIDATED |
| 5 | Secrets/keys never in OPS | WP2 §16; DC-10 | AUTHORED — VALIDATED |
| 6 | Evaluation ↔ governed input artifact physically 1:1 | WP2 §7; DC-09; CI self-test defect | AUTHORED — VALIDATED |
| 7 | Completed `DetectionResult` immutable with all provenance pins; adjudication separate | WP2 §§7–8; DC-08 | AUTHORED — VALIDATED |
| 7a | Fenced, commit-coherent completion: no result under a failed/fenced evaluation; stale worker cannot complete; consumers pin only COMPLETED results (review MEDIUM-1) | WP2 §12.1; `completion_protocol`; DC-25; NEG-22…NEG-28; CI self-test defect 9 | **CLOSED** — validated; approved at targeted re-review |
| 8 | Replay material set enumerated; explicit unavailable states; re-verification sequence (closes WP1 LOW-2) | WP2 §9; DC-18 | AUTHORED — VALIDATED |
| 9 | Report regeneration conditional on retained inputs (WP1 LOW-3 carried) | WP2 §10 | AUTHORED |
| 10 | Cross-store states, idempotency, reconciliation ownership/queues; no DB transaction claimed over ECS | WP2 §§11, 19; DC-22 | AUTHORED — VALIDATED |
| 11 | Lost in-memory result → `FAILED_INFRASTRUCTURE`; retry is a new evaluation (closes WP1 INFO-2) | WP2 §12; DC-22 | AUTHORED — VALIDATED |
| 12 | DeletionAction OPS workflow separated from AUD accountability (closes WP1 INFO-1) | WP2 §13; DATA-001 §5.19.3/§28 | AUTHORED |
| 13 | Authorization/resource schema support; administrator grants no evidence access | WP2 §16; DC-20 | AUTHORED — VALIDATED |
| 14 | Retention represented without duration or legal basis; OI-05 OPEN | WP2 §13; DC-17 | AUTHORED — VALIDATED |
| 15 | Tenancy-sensitive structures PROVISIONAL / BLOCKED ON ASM-002; no tenant column; ASM-002 does not block this contract but blocks the first schema-creating migration and tenancy-sensitive implementation | WP2 §3; DC-14 | AUTHORED — VALIDATED; **ASM-002 OPEN** |
| 16 | Identifier strategies compared; UUIDv4 selected; no PII/meaning | WP2 §5.2 | AUTHORED |
| 17 | Types, vocabularies (synced with promoted contracts), JSONB rules defined; no score/probability column | WP2 §§5.3–5.6; DC-12/13 | AUTHORED — VALIDATED |
| 18 | No `ON DELETE CASCADE`; audit never cascades or FK-links into OPS | WP2 §17; DC-04/DC-15 | AUTHORED — VALIDATED |
| 19 | Indexes justified; FK indexes for deletable parents; no scale claims | WP2 §18; DC-24 | AUTHORED — VALIDATED |
| 20 | Append-only hash-chained audit storage; not tamper-proof | WP2 §15; DC-15 | AUTHORED — VALIDATED |
| 21 | ADR-0011 issued after comparing Alembic / plain SQL runner / Flyway-style / ORM auto-create | ADR-0011 | **ACCEPTED** following independent review |
| 22 | Migration principles: versioning, expand/migrate/contract, locking, failure recovery, backup relationship, downgrade policy, destructive-change governance, ownership | ADR-0011 | AUTHORED |
| 23 | No ORM selected; no startup schema mutation; no zero-downtime claim | ADR-0011 Decision 2/4, principle 5 | AUTHORED |
| 24 | Machine-readable contract + JSON Schema + static validator + negative fixtures | `contracts/postgresql/**`, `validate_data_contract.py` | PASS — LOCAL BUILDER |
| 25 | Validator wired into canonical gate; CI self-test proves it bites | `run_all.py` (24 checks), `ci_selftest.py` (9 defects) | PASS — LOCAL BUILDER |
| 26 | CI path filter covers `docs/06-contracts/**` and `contracts/**` (closes WP1 LOW-5) | `.github/workflows/knowledge-validation.yml` | AUTHORED |
| 27 | ADR-0012 remains Planned; WP4 LOW-3 deferred to ADR-0012 | `adr/README.md`; WP2 §23 | CONFIRMED |
| 28 | Phase-3/Phase-4/runtime/publish frozen; `ENGINE_VERSION = 1.0.0` | Change surface + validation §5 | PASS — LOCAL BUILDER |
| 29 | No database, migration, repository, API or UI implemented; no production/compliance/efficacy claim | WP2 §§1, 25 | AUTHORED |
| 30 | Independent review before acceptance | §§6, 7a, 7b | INITIAL REQUEST_CHANGES → MEDIUM-1 CLOSED → TARGETED RE-REVIEW **APPROVE** |

`AUTHORED` records builder completion; `VALIDATED` means the static validator enforces it. Neither is independent
approval.

## 3. Decision records

| ADR | Status after P6-WP2 |
|---|---|
| ADR-0011 Database migration tooling | **Accepted** following independent P6-WP2 review — Alembic-managed, versioned, SQL-first; no ORM selected |
| ADR-0012 Threat-intelligence adapter/provider + SSRF-TOCTOU | **Planned** — not issued |

## 4. Programme and claim status

| Item | Status |
|---|---|
| Phase 5 | FORMALLY CLOSED |
| Phase 6 | **IN PROGRESS** — P6-WP1 merged (PR #26); P6-WP2 approved locally/independently, remote CI + merge pending; P6-WP3…WP6 not started |
| ASM-002 single tenancy | **UNCONFIRMED** — does not block acceptance of this versioned contract; MUST be resolved by Sponsor/Programme before the first schema-creating migration is accepted/executed and before tenancy-sensitive implementation |
| OI-05 | **OPEN** |
| G-09 | **OPEN** |
| WP4 LOW-3 | **OPEN / DEFERRED** → ADR-0012 |
| RSK-006 | PostgreSQL/Docker still unavailable — contract is static only |

No database implemented, migration executed, PostgreSQL installation, production readiness, zero-downtime
migration, RPO/RTO, legal compliance, or detection-efficacy claim is made.

## 5. Required local builder validation

| Check | Required result | State |
|---|---|---|
| `.venv/bin/python knowledge/validation/run_all.py` | PASS — 24/24 (23 + `validate_data_contract.py`) | PASS — LOCAL BUILDER |
| `.venv/bin/python knowledge/validation/run_all.py --json` | `gate=PASS`, `validators_run=24`, `validators_failed=0` | PASS — LOCAL BUILDER |
| `.venv/bin/python knowledge/validation/ci_selftest.py` | PASS — 9/9 defects caught | PASS — LOCAL BUILDER |
| `validate_data_contract.py` negative mutations | 28/28 rejected by the expected check (incl. DC-25 for MEDIUM-1) | PASS — LOCAL BUILDER |
| Phase-3/Phase-4/runtime/publish freeze; `ENGINE_VERSION` | zero diff; `1.0.0` | PASS — LOCAL BUILDER |
| `git diff --check` + whitespace of all P6-WP2 files | clean | PASS — LOCAL BUILDER |

## 6. Finalisation conditions

| # | Condition | State |
|---:|---|---|
| 1 | Independent review APPROVE (builder did not self-review or self-accept ADR-0011) | **SATISFIED** — targeted re-review APPROVE |
| 2 | Canonical local validation PASS (24/24) and CI self-test PASS (9/9) | SATISFIED — LOCAL BUILDER |
| 3 | Remote GitHub Actions PASS (triggered by `docs/06-contracts/**` and `contracts/**` as well) | **PENDING** |
| 4 | Merge to `main` | **PENDING** |

Until conditions 3 and 4 are met the correct state is **P6-WP2 PERSISTENCE CONTRACT APPROVED — REMOTE CI + MERGE
PENDING**, not P6-WP2 CLOSED.

ASM-002 is **not** a finalisation condition for this contract. It MUST be resolved by the Sponsor/Programme before
the first schema-creating migration is accepted or executed and before tenancy-sensitive implementation; a
multi-tenant confirmation requires this contract to be revised and re-reviewed first.

## 7. Change boundary

New: `adr/ADR-0011-database-migration-tooling.md`; `docs/06-contracts/DATA-001-WP2-postgresql-persistence-contract.md`;
`docs/00-program/GATE-020-phase-6-postgresql-persistence.md`; `contracts/postgresql/schema-v1.json`;
`contracts/postgresql/schema-contract.schema.json`; `contracts/postgresql/fixtures/negative-mutations.json`;
`knowledge/validation/validate_data_contract.py`.
Modified: `adr/README.md` (ADR-0011 Planned → Accepted); `.github/workflows/knowledge-validation.yml` (path filter);
`knowledge/validation/run_all.py` (24th check); `knowledge/validation/ci_selftest.py` (8th and 9th defects);
`docs/06-contracts/DATA-001-data-domain-lifecycle-contract.md` (narrow: supplement reference, INFO-1 clarification,
§28 carryover record, review INFO-3 Submission `C3` alignment). Phase-3/Phase-4 runtime, schemas, rules, taxonomies, bundles, publication code, ARCH documents
and other ADRs are unchanged.

## 7a. Independent review outcome and corrections

Initial independent P6-WP2 review: **BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 4 / INFO 4 — REQUEST_CHANGES.** The
reviewer classified ASM-002 as LOW (does not block the P6-WP2 contract; blocks tenancy-sensitive implementation).

| Finding | Severity | Disposition |
|---|---|---|
| MEDIUM-1 `detection_result` could commit under an evaluation already fenced to `FAILED_INFRASTRUCTURE` after lease expiry | MEDIUM | **CLOSED (approved at targeted re-review).** Fence token on `evaluation` (held while executing, cleared in every `FAILED_*` state); NOT NULL token on `detection_result` bound by FK `(evaluation_id, execution_fence_token)`; BEFORE INSERT state/token guard; deferred two-way commit invariants (result ⇔ `COMPLETED`); guarded completion compare-and-set that rolls back on zero rows; consumer safety (adjudication/report via result FK, replay requires `COMPLETED`). Encoded as `completion_protocol`; DC-25; NEG-22…NEG-28; CI self-test defect 9 (WP2 §12.1) |
| LOW-1 deletion order vs `RESTRICT` FKs | LOW | **ADDRESSED** — content phase then children-first row phase derived from the declared FK graph (WP2 §13); `RESTRICT` unchanged |
| LOW-2 artifact presence vs `REQUESTED → FAILED_PRECONDITION` | LOW | **ADDRESSED** — an evaluation may not enter `RUNNING` without its exact artifact (`tg_evaluation_running_requires_artifact`) |
| LOW-3 ASM-002 wording | LOW | **WORDING ALIGNED** across GATE-020, WP2 §3, DATA-001 §28, `schema-v1.json` tenancy note, ADR-0011 |
| LOW-4 static-only PostgreSQL limitation | LOW | **RETAINED** as a disclosed limitation; owner implementation / ADR-0011 validation plan |
| INFO-1 audit role wording | INFO | **ADDRESSED** — narrow column-level `audit_chain_head` UPDATE for append; no UPDATE/DELETE on historical audit rows |
| INFO-2 scratch generator | INFO | **ADDRESSED** — `schema-v1.json` is the maintained source; hand edits must pass all checks |
| INFO-3 DATA-001 Submission `C3` placement | INFO | **NARROWLY ALIGNED** — DATA-001 §5.3 and Matrix A row 7 |
| INFO-4 unset operational values | INFO | **DEFERRED to P6-WP6** — inline-vs-ECS threshold, lease length, retry backoff remain NOT YET SPECIFIED |

## 7b. Targeted re-review and acceptance

Targeted independent re-review: **BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 2 / INFO 3 — FINAL RECOMMENDATION: APPROVE.**

| Item | Disposition | Owner |
|---|---|---|
| MEDIUM-1 | **CLOSED** — opaque execution fence token; result insertion-state guard; fence-token binding between `evaluation` and `detection_result`; compare-and-set completion on the current fence; failed states clear the fence; deferred commit-time invariant (result exists ⇔ `COMPLETED`); retry = new evaluation; DC-25; NEG-22…NEG-28; CI self-test coverage | — |
| LOW — ASM-002 single tenancy | **OPEN / EXTERNAL DEPENDENCY; NON-BLOCKING** for contract acceptance. Blocks the first schema-creating migration and tenancy-sensitive implementation; five structures stay PROVISIONAL; no `tenant_id` | Sponsor / Programme |
| LOW — static PostgreSQL validation | **NON-BLOCKING / FUTURE VALIDATION** — CHECK expressions, constraint triggers, roles/grants, DDL semantics and the migration chain not yet executed against a disposable PostgreSQL instance; no runtime verification claimed | Implementation phase / ADR-0011 validation plan |
| INFO-A DATA-001 §5.2 tenancy wording | **ALIGNED** | — |
| INFO-B deletion vs `COMPLETED` tombstone | **CARRIED** — after governed deletion of a `DetectionResult`, a `COMPLETED` tombstone no longer implies a result exists; replay fails closed at the required-artifact check. Future work must distinguish the normal durable-completion invariant (unchanged) from post-deletion tombstone semantics; no tombstone rule invented | P6-WP6 (operational/replay contract); OI-05 |
| INFO-4 operational values | **DEFERRED** — inline-vs-ECS threshold, lease length, retry backoff NOT YET SPECIFIED | P6-WP6 |

P6-WP1 carryovers remain **CLOSED**: LOW-2, INFO-1, INFO-2 (through MEDIUM-1), LOW-5. ADR-0012 remains Planned;
WP4 LOW-3 remains OPEN / DEFERRED → P6-WP5 / ADR-0012. G-09 and OI-05 remain OPEN.

## 8. Builder findings carried to review

| Severity | Finding | Owner |
|---|---|---|
| LOW (reclassified by review) | ASM-002 single tenancy unconfirmed; five tenancy-sensitive structures are PROVISIONAL and machine-checked; does not block this contract; blocks the first schema-creating migration and tenancy-sensitive implementation | Sponsor / Programme |
| LOW | Contract is static: CHECK expressions, triggers and roles are unverified until a disposable PostgreSQL is available (RSK-006) | Implementation phase |
| LOW | Strict replay requires retained original evidence bytes; governed deletion ends exact replay (intentional; duration is OI-05) | Sponsor + legal/governance |
| INFO | Inline-vs-ECS threshold, execution lease length and retry backoff NOT YET SPECIFIED | P6-WP6 |

## 9. Recommendation

Proceed to the P6-WP2 commit and PR. After remote CI PASS and merge to `main`, P6-WP2 may be recorded as CLOSED. Do not
issue ADR-0012 and do not begin P6-WP3 under this checkpoint.
