# GATE-033 — P9-S2-ADD-001 persistence revision and Phase-6 snapshot revision P6-SNAPSHOT-REV-001

| Field | Value |
|---|---|
| Document ID | GATE-033 |
| Version | 1.0 |
| Status | **P9-S2-ADD-001 AND P6-SNAPSHOT-REV-001 APPROVED FOLLOWING INDEPENDENT REVIEW — FORWARD ACTIVATION RECORDED — REMOTE CI + MERGE PENDING**. Not S2 closure. Migration 0004 is not applied to the sponsor's database |
| Phase assessed | Phase 9, S2 (secure evidence intake): a governed forward revision of the Phase-6 persistence contract |
| Owner role | Backend / Data Architect |
| Baseline | `35fc587` (branch `phase9-s2-evidence-intake`; the revision is uncommitted until the sponsor's PR) |
| Primary deliverables | [DATA-001-WP2-ADD-P9-S2-001](../06-contracts/DATA-001-WP2-ADD-P9-S2-001-evidence-upload-intent.md); [`schema-v1-addendum-p9-s2-add-001.json`](../../contracts/postgresql/schema-v1-addendum-p9-s2-add-001.json) with [`schema-addendum.schema.json`](../../contracts/postgresql/schema-addendum.schema.json); [`phase6-snapshot-revision-p9-s2-add-001.json`](../../contracts/phase6/phase6-snapshot-revision-p9-s2-add-001.json) with its schema and negative fixtures; [`validate_phase6_snapshot_revision.py`](../../knowledge/validation/validate_phase6_snapshot_revision.py); migration `apps/backend/migrations/versions/0004_evidence_intake.py` |
| Sponsor decision | P9-S2-ADD-001 approved in principle by the sponsor on 2026-10-14. The user (programme sponsor) asked for this activation record on 2026-10-14. No further sponsor sign-off is recorded here: the sponsor's own Git review and merge are the remaining integration step |
| Independent review | Four rounds (§3). Final: **APPROVE**, 0 remaining material findings |
| Related open items | P6-WP7-LOW-1 (resolved forward, §5); ADDITIVE-REVISION-ID-PATTERN (open, non-blocking); OI-05 (open); G-09 (open) |
| Last updated | 2026-10-14 |

## 1. Checkpoint purpose

GATE-033 records the independent review and approval of persistence addendum P9-S2-ADD-001, and the forward activation
of Phase-6 snapshot revision P6-SNAPSHOT-REV-001 that carries it. GATE-019…GATE-032 are not modified. The Phase-6
closure manifest and its 19-artifact snapshot stay byte-for-byte unchanged: the revision carries those pins and adds
new ones. This gate approves a contract revision and its offline validation. It does not migrate any persistent
database, merge any change or close S2.

## 2. What the review approved

| Item | Approved scope |
|---|---|
| Effective persistence contract | **0.3.0** = `schema-v1.json` 0.2.0 + the machine addendum, composed deterministically. It passes DC-01…DC-25 against the actual structural schema and keeps every historical data-contract negative mutation |
| Additive changes | Table `evidence_upload_intent` (its identifier is the API `evidence_id`; no digest before PUT); vocabularies `evidence_upload_intent_state` and `evidence_put_rejection_category`; `api_idempotency_record.superseded_at` (write-once); fencing guard on `cross_store_operation.attempt_count` |
| Constraint relaxation | **P9-S2-ADD-001-REL-01** — `uq_api_idempotency_scope` becomes partial (`WHERE superseded_at IS NULL`). A **governed constraint relaxation**, not an additive change, explicitly approved with its preserved invariants and migration compatibility |
| Snapshot revision | **P6-SNAPSHOT-REV-001**: 19 Phase-6 pins carried unchanged; the four P6-WP7-LOW-1 structural-schema pins; the P9-S2-ADD-001 artifacts, migration 0004, the revision's schema, fixtures and validator; this gate record |
| Validator | The corrected snapshot validator: composition, governed CHECK predicates, migration catalog, transition, fencing and privilege guards |
| Implementation safety | Symlink-safe disposable credential guards for the test and loader paths |
| API / OAS | Unchanged (`v1`, `api-v1/contract-0.1.0`); `client_declared_sha256` stays optional |

The reviewer's readiness statements: **READY_FOR_GOVERNED_ACTIVATION: YES**; **READY_FOR_LOCAL_MIGRATION_AFTER_ACTIVATION: YES**.

## 3. Independent review history

| Round | Verdict | Counts | Findings and resolution |
|---|---|---|---|
| 1 | REQUEST_CHANGES | BLOCKER 0 / HIGH 0 / MEDIUM 6 / LOW 1 | (1) machine addendum invalid against the structural table schema; (2) concurrent evidence PUT race; (3) short filesystem writes; (4) forwarded-header admission bypass; (5) unbounded streamed JSON; (6) disposable-test database isolation; (7) misleading upload failure copy. All seven corrected with regression tests |
| 2 | REQUEST_CHANGES | Two findings; the severity breakdown is not recorded here | (1) permanent credential loaders not guarded in disposable mode; (2) the snapshot validator checked CHECK constraint names, not predicates. Both corrected; `CHECK (true)` is rejected even when the migration pin is updated |
| 3 | REQUEST_CHANGES | Exactly 1 MEDIUM | The credential-path guard normalised `..` before resolving symlinks. Corrected: the original path is resolved, compared by path components, and the resolved destination is what the loader reads |
| 4 | **APPROVE** | 0 remaining material findings | Explicit approvals: REL-01; effective contract 0.3.0; the corrected snapshot validator; symlink-safe disposable credential guards; READY_FOR_GOVERNED_ACTIVATION YES; READY_FOR_LOCAL_MIGRATION_AFTER_ACTIVATION YES |

## 4. Validation evidence (builder-run on this branch, 2026-10-14)

| Check | Result |
|---|---|
| `validate_phase6_snapshot_revision.py` | PASS: ACCEPTED; 19 historical + 4 structural + 8 added pins; effective 0.3.0 (40 tables) passes DC-01…DC-25 and 28 historical negative mutations; 17 checks; all fixture negative mutations rejected |
| `run_all.py` | PASS, 37/37 validators |
| Backend tests (disposable PostgreSQL) | 183/183 before activation; the activation changes no implementation file |
| Phase-6 closure / data contract validators | PASS unchanged (19 pins, 39 tables) |

These are the builder's results. The reviewer's own runs are not reproduced here.

## 5. Activation boundary

- **Accepted in this branch:** P6-SNAPSHOT-REV-001 is ACCEPTED (approved and activated) and P9-S2-ADD-001 is ACTIVATED.
  They become repository authority when the sponsor merges this branch. Its integration state is
  REMOTE CI + MERGE PENDING (no PR number or merge commit exists yet).
- **P6-WP7-LOW-1** is resolved forward: the accepted revision pins the four structural schemas. The frozen Phase-6
  closure manifest keeps its historical OPEN record.
- **Unchanged by activation:** implementation, migration 0004 (its reviewed bytes, including its pre-activation
  docstring) and encrypted evidence behaviour.
- **Sponsor steps after merge:** create the evidence key with the documented noclobber command, review
  `make migration-sql`, then run `make migrate` as `tl_schema_migrator`. Until then the sponsor's database stays at
  0003 and evidence intake answers 503.

## 6. Claim boundary

This gate does **not** claim: a merge or remote CI result, a migrated sponsor database, production readiness, a
production KMS, complete T09, full S2 completion or accessibility conformance. G-09, OI-05 and the
additive-revision-id limitation remain open with their owners.

## 7. Decision

**APPROVED FOLLOWING INDEPENDENT REVIEW — FORWARD ACTIVATION RECORDED — REMOTE CI + MERGE PENDING.** The governed
record is ready for the sponsor's manual Git/PR process.
