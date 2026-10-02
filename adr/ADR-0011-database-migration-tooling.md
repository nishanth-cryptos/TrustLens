# ADR-0011 — Database migration tooling

| Field | Value |
|---|---|
| Status | **Accepted** — following independent P6-WP2 review (initial review REQUEST_CHANGES on an unrelated persistence-contract defect, MEDIUM-1, since closed; targeted re-review APPROVE) |
| Date | 2026-10-02 |
| Owner role | Data Architect / Backend Architect |
| Phase | Phase 6 — P6-WP2 PostgreSQL persistence contract |
| Related | [DATA-001](../docs/06-contracts/DATA-001-data-domain-lifecycle-contract.md), [DATA-001-WP2](../docs/06-contracts/DATA-001-WP2-postgresql-persistence-contract.md), [GATE-020](../docs/00-program/GATE-020-phase-6-postgresql-persistence.md), [ADR-0004](ADR-0004-knowledge-storage-architecture.md), [ADR-0008](ADR-0008-python-runtime-service-topology.md), [ADR-0009](ADR-0009-identity-authentication-authorization.md), [ADR-0010](ADR-0010-evidence-storage-tamper-evidence.md), [ADR-0013](ADR-0013-rule-set-publication-version-distribution.md), [ADR-0016](ADR-0016-deployment-resilience-runtime-topology.md), [ARCH-005](../docs/05-architecture/ARCH-005-deployment-resilience-recovery.md) §4.4/§10/§11, RSK-006, ASM-002, ASM-012, OI-05 |
| Reversal cost | **Low–Medium** — migrations are reviewed SQL-first scripts that can be replayed by another runner; the version history table and script headers are the tool-specific parts |

## Context and constraints

ADR-0010 selected PostgreSQL as the structured operational store; DATA-001 defines the logical model and
DATA-001-WP2 the physical persistence contract (`contracts/postgresql/schema-v1.json`). ARCH-005 §4.4 and ADR-0016
require that Phase-6 database migrations stay compatible with controlled replica rollout and rollback, and never
rewrite completed historical results. This ADR decides **how schema changes are authored, reviewed, versioned and
applied**. It does not implement any migration, connection code, repository layer or ORM model, and it does not
claim that PostgreSQL is installed (RSK-006: Docker/PostgreSQL absent from the development machine).

Binding constraints:

- **Python modular monolith** (ADR-0008); Java is not a planned runtime direction.
- **Offline/on-prem viability** (ADR-0004/0013): upgrades must be possible without Internet access.
- **No ORM decision is made by this ADR.** DATA-001 deliberately selected no ORM; the persistence adapter design is
  later work.
- **History integrity** (ADR-0010, `INV-13`): a migration may never alter the bytes or digest of a stored canonical
  artifact (`DetectionResult`, governed input artifact, AI snapshot, report manifest) or rewrite audit history.
- **Mixed-version rollout** (ARCH-005 §4.4): old and new application versions may briefly coexist.
- **Small delivery team** (ASM-012): bespoke infrastructure must be justified.
- **No production-startup schema mutation**: the request path never authors or applies schema changes.

## Decision

Select **Option A — Alembic-managed, versioned, SQL-first PostgreSQL migrations**, under these rules:

1. **Migration tooling only.** Alembic is used as the migration runner and version-history manager. It is not a
   knowledge store, not an authority for governed knowledge (ADR-0004/0013 unchanged), and not the application's
   data-access layer.
2. **No ORM is selected.** Migration scripts express DDL explicitly (Alembic operations and/or reviewed SQL
   statements). They do not depend on ORM model classes, and `autogenerate` is **not** an authority: if it is ever
   used as a drafting aid, its output is reviewed line by line against DATA-001-WP2 like any hand-written change.
   Alembic depends on SQLAlchemy Core as a library; that dependency is accepted for the migration runner only and
   does not select SQLAlchemy ORM (or any ORM) for the application.
3. **Version-controlled, linear history.** Migration scripts live in Git, are reviewed like code, and form a single
   linear revision chain. Branching heads must be merged before release; a release references exactly one head.
4. **Explicit upgrade.** Schema upgrade is a separate, operator-executed release step (`upgrade` to an exact
   revision) using the `tl_schema_migrator` database role. **Application startup never autogenerates or applies
   schema changes**; a replica checks that the database revision is one it supports and fails readiness otherwise.
   Any future automated-apply mechanism requires an explicit later deployment decision.
5. **Offline/on-prem.** Releases ship the migration scripts; reviewed SQL can also be rendered in Alembic offline
   (SQL-generation) mode for environments where a DBA applies scripts. Neither path needs network access.
6. **Reviewed generation.** Any generated migration content is reviewed rather than trusted; CI validates the
   contract and (once implementation exists) the migration chain.

## Alternatives considered

| Option | Python monolith fit | PostgreSQL support | Deterministic history | Offline/on-prem | Rollback discipline | Reviewability | CI validation | ORM independence | Operational complexity | Lock-in | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **A. Alembic, versioned SQL-first migrations (selected)** | Native Python; same toolchain as the backend | Mature; transactional DDL on PostgreSQL | Revision chain + version table; linear-history rule | Scripts shipped with release; offline SQL rendering | Explicit downgrade functions possible but governed (below) | Scripts are plain Python/SQL in Git | Chain can be checked statically and against a disposable database later | Usable without ORM models; SQLAlchemy Core dependency only | One familiar tool; no extra runtime | Low–Medium: scripts are mostly SQL | ✅ **Selected** |
| B. Plain versioned SQL files + application-owned runner | Python, but bespoke | Any SQL | Only as good as the custom runner (ordering, checksums, version table) | Good | Must be designed from scratch | Excellent (pure SQL) | Must be built | Full | Team must build and maintain locking, checksums, failure handling and tooling | None | ❌ Rejected — re-implements a mature tool's core for a one-engineer team (ASM-012) |
| C. Flyway-style external migration tooling | Separate toolchain; needs a JVM or vendor distribution/container | Mature | Strong (versioned + checksums) | Possible, with an additional runtime artifact | Some capabilities depend on product edition | Excellent (SQL-first) | Good | Full | Adds a non-Python runtime the architecture otherwise avoids (ADR-0008) and Docker is not yet available (RSK-006) | Medium | ❌ Rejected — a second runtime/toolchain without a requirement that Alembic cannot meet |
| D. ORM/schema auto-create or automatic runtime mutation | Convenient | Varies | **None** — schema follows whatever code runs | Poor control | None | Low — changes are implicit | Weak | Requires an ORM | Low at first, high risk later | High | ❌ Rejected — silent production schema mutation; no reviewable history; violates explicit-upgrade and history-integrity constraints |

### Criterion notes

- **Rollback discipline** is about policy as much as tooling; all options except D can support the policy below.
- **Reviewability/CI**: the decisive difference between A and B is who maintains the runner; between A and C, the
  extra runtime. Neither B nor C offers a capability TrustLens needs that A lacks.
- **ORM independence**: A keeps the application persistence-adapter choice open; D forecloses it.

## Migration principles

1. **Versioned, deterministic, reviewable.** One migration = one reviewed change set with a stable revision
   identifier, a description, a reference to the DATA-001-WP2 contract version it implements, and a declared change
   class: `ADDITIVE`, `BACKFILL`, `CONSTRAINT_TIGHTENING`, `DESTRUCTIVE`.
2. **Forward upgrade path.** Every supported database revision has a forward path to the current head. Releases are
   upgraded in order; skipping revisions is not supported.
3. **Contract alignment.** A migration that changes physical structure must be accompanied by the matching change to
   `contracts/postgresql/schema-v*.json` (and pass `validate_data_contract.py`) in the same review.
4. **Expand → migrate → contract** for any change that old and new application versions might observe during a
   rollout: (1) *expand* additively (new nullable columns/tables/indexes) so the old version keeps working;
   (2) deploy application versions that write both or read either; (3) *migrate/backfill* data in bounded batches;
   (4) *contract* (remove/tighten) only in a later release after no running version depends on the old shape.
5. **Rolling-deployment compatibility.** Each migration states which application versions can run against the
   schema before and after it. Not every migration is online-safe; one that is not must be flagged and scheduled
   with an explicit maintenance or rollout plan. **No zero-downtime guarantee is made.**
6. **Backfill ownership.** The authoring Application/Data Engineering role owns backfill logic, its idempotency and
   its verification query; backfills never recompute decisions and never rewrite canonical artifacts or audit
   events.
7. **Locking/concurrency.** Exactly one migration executor runs per database at a time: the release step runs a
   single migrator job, and the migration environment takes a PostgreSQL advisory lock for its duration so an
   accidental second run waits or fails rather than interleaving. Long-running DDL is assessed for lock impact
   before release (e.g. creating indexes concurrently where the change class allows it).
8. **Failure recovery.** Each migration runs in a transaction where PostgreSQL allows it; a failure rolls back that
   migration and leaves the recorded revision unchanged. Non-transactional steps (e.g. concurrent index builds) are
   isolated into their own migration with documented recovery. Recovery is **forward repair** unless the declared
   downgrade is lossless (below).
9. **Backup/restore relationship.** A verified backup point (ARCH-005 §10) precedes every `DESTRUCTIVE` or
   `CONSTRAINT_TIGHTENING` migration. Restore remains the authorised, integrity-verified procedure of ARCH-005 §11;
   a migration is never a substitute for it, and a restored database is re-verified before it receives traffic.
10. **History integrity.** No migration may modify stored canonical JSON text, any digest, or `audit_event` rows.
    Database-level immutability triggers stay in force during migrations; a migration needing to touch protected
    history is out of policy and requires a new ADR.
11. **Retention neutrality.** Migrations neither shorten nor extend data retention implicitly; moving or copying
    sensitive data requires the destructive-change governance below (OI-05 remains open).

### Destructive migration governance

`DESTRUCTIVE` (column/table removal, type narrowing, data transformation, sensitive-data movement) and
`CONSTRAINT_TIGHTENING` changes require, before merge:

- a compatibility analysis covering every application version that may run during rollout;
- confirmation of a verified backup point and the recovery procedure;
- a data-retention/privacy assessment (what data is removed, copied or moved; OI-05 implications);
- a rollback or forward-repair plan stating what is lost if the step is undone;
- independent review in addition to the author; and
- an explicit release note. Irreversible destruction is never automated as a side effect of another change.

### Downgrade and rollback policy

- **Application rollback ≠ schema downgrade.** Rolling back an application release re-deploys older code; it does
  not imply running schema downgrades. Expand-first migrations are designed so the previous application version
  still works against the newer schema.
- **Downgrades are not promised.** A migration may provide a downgrade only if it is lossless and tested. Where
  reversing a migration would destroy or lose information (dropped columns, transformed data, appended history),
  **no destructive downgrade is provided; recovery is forward repair**, or restore from a verified backup under the
  ARCH-005 §11 procedure.
- No downgrade may delete governed audit events or alter stored canonical artifacts.

### Migration ownership (roles, not people)

| Activity | Role |
|---|---|
| Author migrations, backfills and the matching contract change | Application / Data Engineering |
| Review (two-party for `DESTRUCTIVE`/`CONSTRAINT_TIGHTENING`) | Independent reviewer + Data Architect |
| Execute in a controlled release step with `tl_schema_migrator` | Deployment operator (Platform Operations) |
| Verify post-migration health, contract and integrity checks | Platform Operations + Data/Storage Operations |
| Request path | **Never** authors or applies schema changes |

## Justification

Alembic meets every constraint with the least new machinery: it is Python-native (ADR-0008), supports PostgreSQL
transactional DDL, keeps a reviewable linear history in Git, works offline, and does not force an ORM. Option B
would make a single engineer own a migration runner's hardest parts (ordering, version table, locking, failure
handling). Option C adds a non-Python runtime that the architecture otherwise avoids. Option D cannot provide
explicit, reviewable, history-safe upgrades. The decision was **Accepted** following independent P6-WP2 review;
the migration decision itself was unchanged by that review. No efficacy or production-readiness claim is made (G-09 OPEN).

## Consequences

**Positive** — explicit, reviewable schema evolution; offline releases; no silent production mutation; the
application persistence-adapter choice stays open; migrations stay largely portable SQL.

**Costs** — SQLAlchemy Core becomes a dependency of the migration runner; expand/migrate/contract releases take more
steps; downgrades are deliberately limited, so forward repair and backups carry recovery.

## Risks

| Risk | Mitigation |
|---|---|
| `autogenerate` output trusted blindly | Not an authority; mandatory line-by-line review against DATA-001-WP2 and the contract validator |
| Migration rewrites history or canonical artifacts | Principle 10; immutability triggers; out-of-policy changes need a new ADR |
| Mixed-version rollout breaks on schema change | Expand → migrate → contract; per-migration compatibility statement |
| Concurrent migration runs | Single migrator job + advisory lock |
| Destructive change loses data | Destructive-change governance, verified backup point, forward-repair plan |
| Tool coupled to an ORM later by convenience | Decision 2; any ORM adoption is a separate decision |
| Tenancy decided implicitly in the first migration | DATA-001-WP2 marks tenancy-sensitive structure PROVISIONAL; ASM-002 does not block the contract, but the first schema-creating migration must not be accepted or executed until ASM-002 is resolved |

## Reversal cost

**Low–Medium.** Migration bodies are largely SQL; moving to a plain-SQL runner or another tool means porting the
revision chain and version-table bookkeeping, not rewriting the schema. Reversing the **principles** (explicit
upgrade, no startup mutation, history integrity) would be high-cost and require a superseding ADR.

## Validation plan

1. Independent P6-WP2 review of this ADR together with DATA-001-WP2 and GATE-020.
2. Canonical gate passes with the new static data-contract validator (`validate_data_contract.py`), and the CI
   self-test proves it bites.
3. Once PostgreSQL is available (RSK-006/OI-02): a disposable-database check that the migration chain upgrades from
   empty to head, that the resulting catalog matches `contracts/postgresql/schema-v1.json`, that immutability
   triggers reject updates, and that the fenced completion protocol (DATA-001-WP2 §12.1) rejects a stale worker's
   result — planned for the implementation phase, not claimed here.
4. Remote CI PASS and merge; acceptance only after independent review.
