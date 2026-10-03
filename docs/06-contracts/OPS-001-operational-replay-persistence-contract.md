# OPS-001 — Operational, replay and persistence-follow-up contract

| Field | Value |
|---|---|
| Document ID | OPS-001 |
| Version | 0.1 |
| Status | **P6-WP6 OPERATIONAL CONTRACT APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING**; P6-WP6 not yet formally closed; not an implementation |
| Phase | Phase 6 — Data, API & Integration Contracts |
| Work package | P6-WP6 |
| Owner role | Backend / Data / Operations Architect |
| Baseline | P6-WP5 merge `8fb963e955c06ded736c81d8f8a076ee599b910d` (PR #30) |
| Machine contract | [`contracts/operations/operational-v1.json`](../../contracts/operations/operational-v1.json) (contract 0.1.0) + [`operational-contract.schema.json`](../../contracts/operations/operational-contract.schema.json) |
| Validator | `knowledge/validation/validate_operational_contract.py` (OC-01…OC-67) + `contracts/operations/fixtures/negative-mutations.json` |
| Additive revisions owned | DATA-001 **P6-WP6 ADDITIVE REVISION** (logical objects `ApiIdempotencyRecord`, `GovernedRemovalTombstone`); DATA-001-WP2 / `schema-v1.json` **P6-WP6-ADD-001** (contract 0.2.0); API-001 / OAS-001 / `api-v1.json` / `openapi-v1.json` **P6-WP6 ADDITIVE ACTIVATION** |
| Gate | [GATE-024](../00-program/GATE-024-phase-6-operational-contract.md) |
| Governing authority | DATA-001; DATA-001-WP2; API-001; OAS-001; INT-001; ADR-0010/0011/0012/0013/0016/0017; ARCH-003/005; DET-001; AI-001-WP4/WP5 |
| Last updated | 2026-10-03 |

## 1. Purpose and claim boundary

OPS-001 resolves, at **contract level**, the operational and persistence dependencies that P6-WP2…P6-WP5 deliberately
deferred to P6-WP6: durable API idempotency, ETag mutation revisions, external-enrichment provenance persistence and
audit vocabulary, audit-read accountability, governed deletion tombstones, restore anti-resurrection, exact-replay
operational semantics, report/replay after deletion, provider-policy publication, activation of the already-reserved
`listEvaluationEnrichments` operation, and a registry of operational parameters that must be bounded but whose values
are not yet governed.

It makes the design implementation-ready. It is **not** an implementation: no database has been migrated, no
PostgreSQL instance runs, no API server, worker, repository, Alembic revision or enrichment connector exists, and no
idempotency/ETag/deletion behaviour has been executed or tested at runtime. Nothing here claims production readiness,
legal compliance or admissibility, penetration testing, or detection effectiveness. G-09 remains **OPEN** — no accuracy,
precision, recall or false-positive-rate claim is made.

## 2. Authority and the additive-revision rule

Accepted contracts remain authoritative for meaning. P6-WP6 makes only the **additive** revisions that earlier work
assigned to it:

| Earlier assignment | Accepted source | P6-WP6 resolution |
|---|---|---|
| Durable API idempotency persistence (LOW) | API-001 §§17, 30; OAS-001; GATE-021/022 carryovers | §§4–5; DATA-001 `ApiIdempotencyRecord`; `api_idempotency_record` |
| ETag monotonic revision persistence (LOW) | OAS-001 §8 Decision B; GATE-022 | §6; `mutation_revision` |
| External-enrichment persistence follow-ups (P6-WP5 LOW-2) | INT-001 §33; `external-enrichment-v1.json` | §7 |
| Enrichment audit events | INT-001 §30 | §8 |
| Audit-read event type (P6-WP3 INFO-2) | API-001 §25 (`PENDING_TAXONOMY_P6_WP6`) | §8 |
| Deletion tombstone (P6-WP2 INFO) | DATA-001 §5.19.3; DATA-001-WP2 | §9; DATA-001 `GovernedRemovalTombstone`; `governed_removal_tombstone` |
| Provider-policy publication | INT-001 §9; ADR-0012 §18 | §10 |
| `listEvaluationEnrichments` activation | API-001 §22; INT-001 §34; ADR-0012 §18 | §14 |
| Unset operational values (P6-WP2 INFO-4 and others) | DATA-001-WP2; API-001; INT-001 | §16 |

Every revised artifact marks its delta (`P6-WP6-ADD-001` / `P6-WP6 ADDITIVE ACTIVATION`). Earlier gate decisions
(GATE-020…GATE-023) are not rewritten and did **not** review these deltas; **GATE-024 owns their acceptance**. No change
contradicts an accepted contract: every revision adds columns, tables, vocabulary values or removes a FUTURE guard that
the accepted contracts themselves scheduled for P6-WP6. No new ADR is required — ADR-0010/0011/0012/0013/0016 already
govern the architecture; OPS-001 adds operational invariants within them.

**Logical model (DATA-001 P6-WP6 ADDITIVE REVISION).** The two new physical structures trace to logical objects that
P6-WP6 adds to DATA-001 (Matrix A rows 29–30), each with its own purpose, authority, store, classification, mutability,
retention and replay relevance:

| Physical structure | DATA-001 logical object | Why it is its own object |
|---|---|---|
| `api_idempotency_record` | `ApiIdempotencyRecord` (§5.22; `C2`, `M-OPS`, `OPS`) | API-boundary request deduplication with its own state machine, active-window retention and API ownership — not multi-store coordinated work (`CrossStoreOperation`) |
| `governed_removal_tombstone` | `GovernedRemovalTombstone` (§5.23; `C2`, `M-IMM`, `OPS`) | The durable residual fact that a resource was removed — distinct from the `DeletionAction` that executed a deletion step, which it references |

No physical table is mapped to an unrelated object to satisfy DC-05; DC-05 is unchanged and now finds both objects
declared in DATA-001. The additive DATA-001 delta is reviewed by GATE-024 (GATE-019 did not review it).

## 3. Persistence additions (P6-WP6-ADD-001, `schema-v1.json` contract 0.2.0)

| Structure | Change | Purpose |
|---|---|---|
| `case_record`, `review_routing_state`, `deletion_request` | `+ mutation_revision bigint NOT NULL` (+ positive check, +1 trigger guard) | Opaque strong ETag source; compare-and-swap writes (§6) |
| `external_enrichment_result` | `+ indicator_type, normalized_indicator_ref, lookup_outcome, provider_response_category, freshness_state, freshness_policy_ref, cache_used, provider_policy_ref, provider_policy_version, provider_policy_digest, parser_schema_version, response_artifact_digest, retained_provider_artifact_ecs_locator`; `safe_error_category` CHECK-bound; 5 new checks | INT-001 provenance/failure/cache/artifact persistence (§7) |
| `api_idempotency_record` (new; DATA-001 `ApiIdempotencyRecord`) | scoped key digest, semantic digest, claim/fence, outcome reference, active window | Durable API idempotency (§§4–5) |
| `governed_removal_tombstone` (new; DATA-001 `GovernedRemovalTombstone`) | content-free removal marker | 410 `REMOVED_UNDER_GOVERNANCE`; restore anti-resurrection (§§9, 11) |
| Vocabularies | `api_idempotency_state`, `enrichment_indicator_type`, `enrichment_lookup_outcome`, `enrichment_freshness_state`, `enrichment_provider_response_category`, `enrichment_safe_error_category`, `governed_removal_resource_kind`, `governed_removal_reason`; `audit_event_type` +8; `audit_target_kind` +3 | Governed CHECK vocabularies |

No SQL, migration or Alembic revision is created. The replay material set (RM-01…RM-14) and the completion protocol
(execution fence) are unchanged.

## 4. Durable API idempotency

**Accepted API semantics are preserved exactly.** `Idempotency-Key` is client-generated, high-entropy and opaque, and
is scoped to authenticated principal + `operation_id` + target resource path. Same key + semantically same request
returns the original outcome without executing again; same key + different semantic request → `409
IDEMPOTENCY_KEY_REUSED`; same key while the original execution is active → `409 IDEMPOTENCY_IN_PROGRESS`.

**Record.** `api_idempotency_record` persists: `principal_reference_id`, `operation_id`, `target_resource_scope`
(canonical concrete path, no query string), `idempotency_key_digest`, `request_fingerprint_version`,
`request_semantic_digest`, `execution_state` (`IN_PROGRESS` / `COMPLETED` / `FAILED_TERMINAL` / `RELEASED`),
`claim_token`, `in_progress_lease_until`, `outcome_http_status`, `outcome_error_code`, `outcome_resource_kind`,
`outcome_resource_id`, `created_at`, `terminal_at`, `active_until`.

**Key storage.** Only a SHA-256 digest of the key bytes is stored; the raw key is never stored, never logged as
authentication material and never grants access. No accepted contract requires raw-key storage. Because the key is
client-generated high-entropy material, its digest is non-reversible in practice; the digest is meaningful only inside
the principal + operation + target scope.

**Authorization order.** Authenticate → authorize (normal role + resource checks) → claim. The key is never an
authorization credential: a replayed outcome is only returned to a caller who is authorized for the operation now, and
different principals have independent scopes (no cross-principal collision or disclosure).

**Semantic request fingerprint** (`TRUSTLENS_IDEMPOTENCY_REQUEST_FINGERPRINT_V1`): SHA-256 over
`TRUSTLENS_CANONICAL_JSON_V1` of {operation_id, target_resource_scope, canonical JSON body — or, for binary uploads, the
uploaded-content SHA-256 — and only semantically relevant headers}. It excludes `X-Request-Id`, `traceparent`,
`tracestate`, the `Idempotency-Key` itself, `Connection`, `Keep-Alive`, `Transfer-Encoding`, `Content-Length`, `Date`
and `User-Agent`. It is a distinct, versioned fingerprint — it does not reuse the Phase-3 result digest.

**Concurrency invariant.** The claim is `INSERT … ON CONFLICT (uq_api_idempotency_scope) DO NOTHING` on the full unique
constraint (principal, operation, target, key digest) — never check-then-insert. Only the inserting request executes.
A conflicting request reads the existing row: different semantic digest → `IDEMPOTENCY_KEY_REUSED`; same digest and
`IN_PROGRESS` with a live lease → `IDEMPOTENCY_IN_PROGRESS`; same digest and terminal → the stored outcome.
**Completion is atomic with the governed effect**: the effect and the `COMPLETED`/`FAILED_TERMINAL` transition commit in
the same transaction, guarded by `WHERE claim_token = $claim_token`, so a stale executor updates zero rows and its
effect rolls back. Transient failures (5xx, 429, `DEPENDENCY_UNAVAILABLE`) end `RELEASED`; an `IN_PROGRESS` claim whose
lease expired may be re-claimed by a request with the same semantic digest via compare-and-swap on `claim_token`
(the effect cannot have committed, because effect and completion are atomic). Asynchronous (202) operations complete
the record when the accepted job/resource reference is durably created.

**Outcome storage.** Only HTTP status, safe machine error code, created/targeted resource kind + opaque identity and
terminal instant are stored. **No response body is cached**; no C4 content is stored, so no undeletable hidden response
cache exists. Records hold opaque references only (not content-bearing) and are purged after the active window by
governed retention action; the outcome reference is a soft reference that never blocks governed deletion.

## 5. Idempotency active window, expiry and closure

`active_until` is server-set at claim time to `created_at` + the governed active window; the claim lease bounds
`IN_PROGRESS`. Both are **finite** and their values are **NOT YET SPECIFIED** (parameters `IDEMPOTENCY_ACTIVE_WINDOW`,
`IDEMPOTENCY_CLAIM_LEASE`; owner Sponsor / P6-WP6 operational configuration / implementation profile;
`REQUIRED_BEFORE_DEPLOYMENT`). No hours or days are invented. **Expiry policy:** after `active_until` the record no
longer governs the key; a later request reusing it is treated as a new request (fresh claim). Clients must not rely on
idempotency beyond the documented window.

**Carryover:** the P6-WP3/P6-WP4 idempotency-persistence LOW is **CONTRACT-LEVEL CLOSED**. Runtime implementation is
pending Phase 9; idempotency is **not** implemented.

## 6. Optimistic concurrency — mutation revision, ETag and If-Match

**Guarded aggregates (derived from `api-v1.json`, `concurrency != NONE`):**

| API resource | Operations with If-Match | Persisted aggregate |
|---|---|---|
| `Case` | `closeCase`, `reopenCase` | `case_record` |
| `ReviewItem` | `assignReview` | `review_routing_state` |
| `DeletionRequest` | `authorizeDeletionRequest`, `rejectDeletionRequest` | `deletion_request` |

No other If-Match aggregate exists. Immutable resources (e.g. `detection_result`, `governed_input_artifact`) gain no
revision.

**Revision invariant.** `mutation_revision` is server-authoritative and monotonic: it starts at 1, a database `BEFORE
UPDATE` guard sets `NEW.mutation_revision = OLD.mutation_revision + 1` on **every** committed mutation, any externally
supplied value is ignored/rejected, and it never decrements or returns to an earlier value. It is not derived from
timestamps or from the current representation, so `OPEN → CLOSED → OPEN` yields three distinct revisions (ABA
prevented). It is never an API field and never client-writable.

**ETag.** Opaque strong validator derived from `mutation_revision` (OAS-001 Decision B, unchanged); the integer is never
exposed directly.

**If-Match write semantics (compare-and-swap):** `UPDATE <table> SET … WHERE <pk> = $id AND mutation_revision =
$expected_revision`. One row updated → mutation committed and revision advanced atomically. Zero rows → no mutation and
`412 PRECONDITION_FAILED`. Missing `If-Match` → `428 PRECONDITION_REQUIRED` before any write.

**Carryover:** the P6-WP4 ETag-revision persistence LOW is **CONTRACT-LEVEL CLOSED**; runtime implementation pending
Phase 9.

## 7. External-enrichment persistence

Cross-checked against INT-001 `provenance.required_fields`, `failure_semantics`, `cache`, `freshness`,
`response_artifact`, `audit` and `persistence_additive_requirements`:

| INT-001 requirement | `external_enrichment_result` column |
|---|---|
| indicator type | `indicator_type` (`URL` / `HOSTNAME` / `REGISTERED_DOMAIN`) |
| normalized indicator identity | `normalized_indicator_ref` (SHA-256; classified `C4` because a digest of a low-entropy indicator is dictionary-reversible, so it follows the deletion graph) |
| technical outcome | `lookup_outcome` (`FOUND` / `NOT_FOUND` / `UNAVAILABLE` / `POLICY_REJECTED` / `INVALID_RESPONSE`; NULL only when not attempted) |
| provider response status/category | `provider_response_category` (`HTTP_2XX` / `HTTP_3XX` / `HTTP_4XX` / `HTTP_429` / `HTTP_5XX` / `NO_RESPONSE`; provider-neutral) |
| freshness state | `freshness_state` (`FRESH` / `STALE` / `UNKNOWN`) + `freshness_policy_ref` |
| cache used | `cache_used` |
| policy reference / version | `provider_policy_ref`, `provider_policy_version` |
| exact policy identity (§10) | `provider_policy_digest` |
| parser/schema version | `parser_schema_version` |
| response artifact digest | `response_artifact_digest` |
| retained raw provider material | `retained_provider_artifact_ecs_locator` (ECS only, only where `raw_provider_content_policy_ref` permits) |
| governed failure vocabulary | `safe_error_category` CHECK-bound to `enrichment_safe_error_category` = exactly the INT-001 failure categories |

New checks enforce INT-001 semantics: outcome ↔ status mapping (`ck_external_enrichment_outcome_status`); `NOT_FOUND` →
reputation `UNKNOWN`, never `CLEAN`/`ALLOWLISTED`/`MATCH` (`ck_external_enrichment_not_found_unknown`); every failure
carries a governed category and successes none (`ck_external_enrichment_error_category`); accepted observations pin
their artifact digest (`ck_external_enrichment_artifact`); retained material is bound to its digest
(`ck_external_enrichment_retained_artifact`).

**Meaning is unchanged.** The technical outcome is persisted independently of TrustLens decision semantics. `NOT_FOUND`
never means safe, legitimate, verified or `NO_SCAM_PATTERN`. Provider `CLEAN` means only that the provider asserted no
adverse reputation. `consumed_in_governed_artifact` stays false; no Phase-3 observation or rule mapping is introduced.

**Immutability.** An accepted enrichment record is historical provenance: provider reputation changes, cache refresh,
provider-policy change or re-analysis insert a **new** row; existing rows are never updated. Raw provider bodies are
never stored inline in PostgreSQL; OPS keeps artifact identity, digest, locator where permitted, classification and
provenance. The digest proves recording integrity, not provider truth or authenticity.

**Carryover:** P6-WP5 LOW-2 (enrichment persistence follow-ups) is **CONTRACT-LEVEL CLOSED**; runtime pending Phase 9.

## 8. Audit additions and audit-read accountability

| Event (`audit_event_type`) | Source | Content |
|---|---|---|
| `ENRICHMENT_REQUESTED` | INT-001 §30 | opaque ids, provider ref, outcome category |
| `PROVIDER_POLICY_SELECTED` | INT-001 §30 | policy ref/version/digest |
| `ENRICHMENT_ACCEPTED` | INT-001 §30 | enrichment id, artifact digest |
| `CREDENTIAL_REFERENCE_FAILURE` | INT-001 §30 | credential **reference** id only |
| `PROVIDER_POLICY_PUBLISHED` / `PROVIDER_POLICY_ACTIVATED` / `PROVIDER_POLICY_WITHDRAWN` | §10 | policy identity |
| `AUDIT_LOG_ACCESSED` | P6-WP3 INFO-2 | see below |
| `EGRESS_DENIED` (existing, reused) | INT-001 §30 | policy / SSRF destination rejection |

`audit_target_kind` gains `EXTERNAL_ENRICHMENT`, `PROVIDER_POLICY`, `AUDIT_LOG`. No audit addition carries a raw
provider body, raw evidence, credential value, `Authorization` header or C4 content.

**Audit-read accountability.** `listAuditEvents` now names `AUDIT_LOG_ACCESSED` (replacing `PENDING_TAXONOMY_P6_WP6` in
`api-v1.json` and OpenAPI). Exactly **one** event is appended per authorized audit-read operation, recording only the
actor, time, request correlation and scope/filter category. It never copies returned audit-event bodies. **Recursion is
avoided** because the read operation — not each returned row — is the audited unit: reading audit events (including
earlier `AUDIT_LOG_ACCESSED` events) emits a single new event for that read and never one per row.

**Deterministic ordering:** (1) authorize the query; (2) establish the result snapshot boundary; (3) append the one
`AUDIT_LOG_ACCESSED` event for the operation; (4) return the previously established result set. The newly appended
access event therefore never appears in the same response. If the accountability event cannot be appended, the read
result is **not** returned (fail closed).

## 9. Governed deletion and tombstones

**DetectionResult stays immutable.** Governed deletion never sets a completed `DetectionResult` to a "deleted" status.
Where governance requires, its retained canonical content (row and/or ECS object) is removed in dependency order and a
separate tombstone records the removal; a subsequent read answers `410 REMOVED_UNDER_GOVERNANCE` (API-001).

**Tombstone** (`governed_removal_tombstone`, `M-IMM`, governed minimization only): `resource_kind`,
`prior_resource_id` (opaque), `deletion_request_id`, `deletion_action_id`, `removal_reason_category`, `removed_at`,
`retention_policy_reference_id`, `created_at`; unique (`resource_kind`, `prior_resource_id`) is the 410 lookup key. It
never holds a `DetectionResult` body, raw evidence, report content, provider body, C4 rationale, secret material, or a
**digest of deleted content** — retaining such digests is not permitted while OI-05 (permitted post-deletion metadata)
is open.

**Crash-safe cross-store workflow** (no distributed PostgreSQL + ECS transaction):

1. authorized request (`deletion_request` → `AUTHORIZED`);
2. enumerate required actions per store (`deletion_action` rows, `PLANNED`);
3. execute the store-specific action (`EXECUTING`);
4. verify absence or minimization in that store;
5. record the action outcome (`VERIFIED_ABSENT` / `RESIDUAL_FOUND` / `FAILED`);
6. create the tombstone — only in the transaction recording the final `VERIFIED_ABSENT` action for the resource;
7. finalize the request only when every required action satisfies the completion policy.

A delete call returning is **not** completion. Request states stay explicit (`COMPLETE`, `PARTIALLY_FAILED`, `FAILED`)
with action-level residual/failure state. A failed ECS deletion is never hidden by deleting only PostgreSQL metadata,
and a failed OPS deletion is never hidden by deleting only ECS bytes. Retry is governed and idempotent (existing
`cross_store_operation` / `deletion_action` attempt tracking; retry limits and backoff are §16 parameters).

## 10. Provider-policy publication and identity

Provider-neutral lifecycle: **validate** an immutable policy document → **publish** it with exact identity → **activate**
that exact identity → it applies to **new** enrichment only → optionally **withdraw/deactivate** → history retained.

- **Identity:** `provider_policy_ref` + `provider_policy_version` + `provider_policy_digest` (SHA-256 over the canonical
  published policy, `TRUSTLENS_CANONICAL_JSON_V1`). Every enrichment pins all three; replay authority is the pinned
  identity. "Latest", "newest" or "current-by-name" is never replay authority.
- **Immutability:** a published version is never mutated in place; existing enrichment provenance is never altered.
- **Authority:** governed operator / configuration authority only — never end users, ANALYST, REVIEWER, AI, provider
  responses or the adapter runtime. No public API is defined (the RBAC role/public workflow is not yet defined, so it
  stays an internal governed configuration workflow; implementation P6-WP6 / Phase-9).
- **Storage:** semantics are storage-independent (immutable version, exact digest, audit, controlled activation,
  reproducibility); storage selection is a Phase-9 implementation decision — Git is not mandated (INT-001).
- **Audit:** `PROVIDER_POLICY_PUBLISHED` / `PROVIDER_POLICY_ACTIVATED` / `PROVIDER_POLICY_WITHDRAWN`.
- **Secrets** remain separate `SEC` references.

## 11. Restore anti-resurrection

ARCH-005 §11.3 already requires restored state to be verified before promotion; OPS-001 adds the governed-deletion
precondition. **Before a restored snapshot is promoted**, restore reconciliation compares it against the authoritative
post-backup governed-deletion record — `CONTENT_DELETED` / `RETENTION_ACTION` audit events and tombstones recorded after
the backup point, obtained from a source that is **not rolled back by the restore itself**. Content known to have been
governed-deleted must remain deleted, or be re-deleted and verified, before promotion. If the post-backup deletion
record cannot be established, promotion is **blocked** (fail closed). The mechanism that retains that record outside
the restorable snapshot is an implementation decision, `REQUIRED_BEFORE_DEPLOYMENT` (owner: P6-WP6 implementation
profile / Phase 9).

**Backup limitation.** Live-system deletion is distinct from physical expiry or purge of historical backup media.
OI-05 remains **OPEN**; OPS-001 does **not** claim backup copies are erased immediately. A restored backup must
nevertheless never make governed-deleted content active again.

## 12. Exact replay and report after deletion

**Replay** is bound to the accepted RM-01…RM-14 material set (DATA-001-WP2); P6-WP6 adds no material kind. It is
verification only — `MATCH`, `MISMATCH` or an explicit failure — never a replacement authoritative `DetectionResult`.
Replay never calls AI (RM-08 restores the sealed snapshot), never calls an enrichment provider, never uses latest or
current knowledge (RM-05 pins the exact `content_digest`), never uses current evidence, never approximates deleted
material and never silently creates a new Evaluation. Missing required material → **`REPLAY_UNAVAILABLE`** (e.g.
governed-deleted evidence bytes, RM-12; unavailable bundle, RM-05; missing AI snapshot when AI was used, RM-08).

**RM-09 is preserved:** no enrichment is consumed by the governed `DetectionResult` (`consumed_in_governed_artifact =
false`), so current Phase-3 replay neither refetches nor requires enrichment — an unavailable provider is irrelevant to
it. Displaying historical enrichment metadata is retrieval from immutable records and their retained artifacts (where
governance permits), not `DetectionResult` replay.

**Report regeneration** requires the retained pinned source material; if any pinned source was governed-deleted the
result is **`REPORT_REGENERATION_UNAVAILABLE`** — no hidden retained copy, no reconstruction from latest/current material.

## 13. Re-analysis

Re-analysis is a **new Evaluation**. It may use current governed knowledge, the current enabled AI policy and the
current external-enrichment policy, and may therefore produce different observations or a different result. It never
overwrites the historical Evaluation, its result or its enrichment records.

## 14. `listEvaluationEnrichments` activation (P6-WP6 ADDITIVE ACTIVATION)

The existing reserved operation is activated by removing only its `FUTURE_INT_001` availability guard in `api-v1.json`
(`availability`) and `openapi-v1.json` (`x-trustlens-availability`). Unchanged: `GET`,
`/api/v1/evaluations/{evaluation_id}/enrichments`, `listEvaluationEnrichments`, role `ANALYST`, `CASE_ACCESS`, `200`,
cursor pagination, `EnrichmentListResponse` / `EnrichmentView`. **Operation count: 53 before, 53 after** (verified); no
new endpoint; base stays `/api/v1`; no `ENGINE_VERSION` change; no new decision semantics.

The response remains advisory metadata: `EnrichmentView` keeps exactly `enrichment_id`, `provider_category`, `status`,
`reputation_result`, `observed_at`, `advisory`, and exposes no raw provider bytes, ECS locator, credential reference,
`Authorization` header, network target or raw evidence. Its description now states that `CLEAN` is a provider assertion,
never TrustLens safe (`advisory = true`). Activation is **contract-level**: runtime serving requires the Phase-9
implementation. INT-001's machine contract records the new state (`api_surface.availability = ACTIVE_CONTRACT`).

## 15. Async work safety

Background work may be retried, but durable terminal effects must remain idempotent and fenced against stale workers
wherever concurrent execution can occur. The evaluation execution fence (`execution_fence_token`, DATA-001-WP2
completion protocol) remains authoritative and unchanged; cross-store and deletion work keep their existing idempotency
keys and attempt tracking; API commands use the §4 claim fence. No generic worker table is introduced.

## 16. Required runtime-parameter registry

Every parameter below must be finite/bounded and **no value is chosen** (value **NOT YET SPECIFIED**). Two requirement
classes are distinguished:

- **`REQUIRED_BEFORE_DEPLOYMENT_SECURITY_OR_CORRECTNESS`** — safety- or correctness-relevant; a missing value makes
  deployment (or enablement of the named feature) **fail closed** — never infinite, unbounded, security-disabled or a
  silent library default.
- **`CONFIGURATION_REQUIRED_FOR_IMPLEMENTATION_PROFILE`** — ordinary performance/UX tuning (`INLINE_VS_ECS_THRESHOLD`,
  `PAGINATION_DEFAULT_LIMIT`); the implementation profile must choose an explicit finite value, but a missing value is a
  profile-completeness defect, **not** a security startup gate.

Feature-scoped parameters apply only when the named feature or policy is enabled. **`RETENTION_DURATIONS` applies only
when the eventual OI-05 retention policy enables governed automatic expiry**; until then no automatic expiry runs
(persistence `retention_policy_status = UNRESOLVED_OI05`). OI-05 may decide on no automatic expiry; no duration is
assumed and deployment is not blocked on OI-05 by this contract.

| Parameter | Meaning | Unit | Applies when | Requirement class | Owner |
|---|---|---|---|---|---|
| IDEMPOTENCY_ACTIVE_WINDOW | Server-set idempotency active window (active_until). | DURATION | ALWAYS | SECURITY_OR_CORRECTNESS | Sponsor / P6-WP6 operational configuration / implementation profile |
| IDEMPOTENCY_CLAIM_LEASE | In-progress idempotency claim lease. | DURATION | ALWAYS | SECURITY_OR_CORRECTNESS | Sponsor / P6-WP6 operational configuration / implementation profile |
| EVALUATION_EXECUTION_LEASE | Evaluation worker execution lease (DATA-001-WP2 fencing). | DURATION | ALWAYS | SECURITY_OR_CORRECTNESS | Sponsor / P6-WP6 operational configuration / implementation profile |
| OPERATIONAL_WORKER_RETRY_MAX_ATTEMPTS | Maximum attempts for retryable operational work (cross-store, deletion, reconciliation). | COUNT | ALWAYS | SECURITY_OR_CORRECTNESS | Sponsor / P6-WP6 operational configuration / implementation profile |
| OPERATIONAL_WORKER_BACKOFF_BOUNDS | Minimum/maximum backoff (jitter-capable) for operational workers. | DURATION_RANGE | ALWAYS | SECURITY_OR_CORRECTNESS | Sponsor / P6-WP6 operational configuration / implementation profile |
| INLINE_VS_ECS_THRESHOLD | Size threshold above which canonical artifacts are externalized to ECS (storage_mode). | BYTES | ALWAYS | IMPLEMENTATION_PROFILE | Sponsor / P6-WP6 operational configuration / implementation profile |
| PAGINATION_DEFAULT_LIMIT | Default page size for cursor pagination. | COUNT | ALWAYS | IMPLEMENTATION_PROFILE | Sponsor / P6-WP6 operational configuration / implementation profile |
| PAGINATION_MAX_LIMIT | Maximum page size for cursor pagination. | COUNT | ALWAYS | SECURITY_OR_CORRECTNESS | Sponsor / P6-WP6 operational configuration / implementation profile |
| REQUEST_AND_UPLOAD_MAX_SIZE | Maximum request body / evidence upload size (PAYLOAD_TOO_LARGE). | BYTES | ALWAYS | SECURITY_OR_CORRECTNESS | Sponsor / implementation security profile |
| RATE_LIMIT_THRESHOLDS | Admission-control thresholds (RATE_LIMITED). | RATE | ALWAYS | SECURITY_OR_CORRECTNESS | Sponsor / implementation security profile |
| BREAK_GLASS_MAX_DURATION | Maximum break-glass grant duration. | DURATION | ALWAYS | SECURITY_OR_CORRECTNESS | Security Operations / Sponsor |
| RETENTION_DURATIONS | Retention durations per retention class (only if OI-05 enables governed automatic expiry). | DURATION | GOVERNED_AUTOMATIC_EXPIRY_ENABLED (OI-05) | SECURITY_OR_CORRECTNESS | Sponsor + legal/governance (OI-05) |
| PROVIDER_CONNECT_TIMEOUT | Provider connect timeout. | DURATION | EXTERNAL_ENRICHMENT_ENABLED | SECURITY_OR_CORRECTNESS | P6-WP6 operational configuration / implementation security profile (INT-001) |
| PROVIDER_READ_TIMEOUT | Provider read timeout. | DURATION | EXTERNAL_ENRICHMENT_ENABLED | SECURITY_OR_CORRECTNESS | P6-WP6 operational configuration / implementation security profile (INT-001) |
| PROVIDER_OVERALL_DEADLINE | Provider overall deadline. | DURATION | EXTERNAL_ENRICHMENT_ENABLED | SECURITY_OR_CORRECTNESS | P6-WP6 operational configuration / implementation security profile (INT-001) |
| PROVIDER_RETRY_MAX_ATTEMPTS | Provider retry maximum attempts. | COUNT | EXTERNAL_ENRICHMENT_ENABLED | SECURITY_OR_CORRECTNESS | P6-WP6 operational configuration / implementation security profile (INT-001) |
| PROVIDER_BACKOFF_BOUNDS | Provider backoff bounds. | DURATION_RANGE | EXTERNAL_ENRICHMENT_ENABLED | SECURITY_OR_CORRECTNESS | P6-WP6 operational configuration / implementation security profile (INT-001) |
| PROVIDER_REDIRECT_MAX_HOPS | Provider redirect maximum (finite implementation-configured maximum). | COUNT | EXTERNAL_ENRICHMENT_ENABLED | SECURITY_OR_CORRECTNESS | P6-WP6 operational configuration / implementation security profile (INT-001) |
| PROVIDER_WIRE_RESPONSE_MAX_BYTES | Provider response maximum wire bytes. | BYTES | EXTERNAL_ENRICHMENT_ENABLED | SECURITY_OR_CORRECTNESS | P6-WP6 operational configuration / implementation security profile (INT-001) |
| PROVIDER_DECODED_RESPONSE_MAX_BYTES | Provider response maximum decoded bytes. | BYTES | EXTERNAL_ENRICHMENT_ENABLED | SECURITY_OR_CORRECTNESS | P6-WP6 operational configuration / implementation security profile (INT-001) |
| PROVIDER_CACHE_TTL_AND_FRESHNESS_PERIODS | Cache TTL and freshness periods per provider policy. | DURATION | ENRICHMENT_CACHE_ENABLED | SECURITY_OR_CORRECTNESS | Governed provider policy / P6-WP6 operational configuration |
| PROVIDER_CIRCUIT_BREAKER_THRESHOLDS | Provider circuit-breaker thresholds and windows. | THRESHOLD_SET | EXTERNAL_ENRICHMENT_ENABLED | SECURITY_OR_CORRECTNESS | P6-WP6 operational configuration / implementation security profile (INT-001) |
| PROVIDER_RATE_QUOTA | Provider-side rate quota respected by the adapter. | RATE | EXTERNAL_ENRICHMENT_ENABLED | SECURITY_OR_CORRECTNESS | P6-WP6 operational configuration / implementation security profile (INT-001) |
| PROVIDER_CREDENTIAL_ROTATION_PERIOD | Provider credential rotation period (SEC). | DURATION | EXTERNAL_ENRICHMENT_ENABLED | SECURITY_OR_CORRECTNESS | Sponsor / implementation security profile |

Provider parameters are linked to the corresponding INT-001 machine-contract fields, which remain NOT YET SPECIFIED.

## 17. Offline scenarios

`operational-v1.json` carries 28 static scenarios evaluated by contract-driven reference models in the validator
(OC-66). They are contract tests, **not** runtime claims.

| Area | Scenarios |
|---|---|
| Idempotency | SI-01 same key + same request while running → `IDEMPOTENCY_IN_PROGRESS`; SI-02 after completion → original outcome, no execution; SI-03 different request → `IDEMPOTENCY_KEY_REUSED`; SI-04 different principal → independent execution; SI-05/06 different operation/target → independent; SI-07 after released transient failure → re-claim |
| ETag | SE-01 `OPEN → CLOSED → OPEN` → distinct ETags; SE-02 stale If-Match → 412; SE-03 missing If-Match → 428; SE-04 matching If-Match → commit + revision advance |
| Deletion | SD-01 OPS ok + ECS residual → `PARTIALLY_FAILED`, no tombstone; SD-02 ECS ok + OPS failed → `PARTIALLY_FAILED`; SD-03 all verified → `COMPLETE` + tombstone; SD-04 calls returned, nothing verified → `FAILED` |
| Restore | SX-01 snapshot with deleted material + record → re-delete and verify before promotion; SX-02 no record → promotion blocked; SX-03 clean snapshot → promotion after verification |
| Replay | SR-01 all present → capable; SR-02 evidence deleted → unavailable; SR-03 bundle unavailable → unavailable; SR-04 AI snapshot missing when AI used → unavailable; SR-05 AI not used → capable; SR-06 enrichment provider unavailable → capable (irrelevant); SR-07 lineage derivative deleted → unavailable |
| Report | SP-01 pinned source deleted → `REPORT_REGENERATION_UNAVAILABLE`; SP-02 retained → permitted |
| Enrichment | SN-01 historical record returned without any provider call |

## 18. Validation

`validate_operational_contract.py` runs 67 checks (OC-01…OC-67) across the operational contract, the revised
persistence contract, API catalog, OpenAPI document, INT-001 machine contract, DATA-001 and these documents, then applies 91
negative mutations (targeting the operational, persistence, API, OpenAPI or integration contract) and requires each
named check to fail. It is wired as the 28th canonical validator; the CI self-test gains a 13th defect (monotonic
revision removed from `case_record`) that only this validator catches.

Existing validators are unchanged except one documented, genuinely obsolete pin: **IC-46** in
`validate_integration_contract.py` required `listEvaluationEnrichments` to stay `FUTURE_INT_001`; it now requires the
reserved surface to be unchanged and its availability to match the INT-001 `api_surface` record (`FUTURE_INT_001` before
activation, `ACTIVE_CONTRACT` after) in both the catalog and OpenAPI. The data-contract, API and OpenAPI validators pass
unmodified against the additive revisions.

## 19. Carryovers and open items

| Item | Status |
|---|---|
| G-09 | **OPEN** — no labelled real-world corpus; no effectiveness claim |
| OI-05 | **OPEN** — retention durations, permitted residual metadata and backup purge timing NOT YET SPECIFIED |
| ASM-002 | **UNCONFIRMED / PROVISIONAL** — no `tenant_id`, `X-Tenant` or tenant-specific provider routing |
| Idempotency persistence (P6-WP3/WP4 LOW) | CONTRACT-LEVEL CLOSED — runtime pending Phase 9 |
| ETag revision persistence (P6-WP4 LOW) | CONTRACT-LEVEL CLOSED — runtime pending Phase 9 |
| P6-WP5 LOW-2 enrichment persistence | CONTRACT-LEVEL CLOSED — runtime pending Phase 9 |
| P6-WP3 INFO-2 audit-read event type | Resolved — `AUDIT_LOG_ACCESSED` |
| P6-WP2 tombstone follow-up | Resolved — `governed_removal_tombstone` |
| WP4 INFO collection ETag / `action_code` enum | Informational (unchanged) |
| P6-WP5 INFO-D (CLEAN presentation at activation) | Resolved — `EnrichmentView` description |

## 20. Traceability

| Brief requirement | Artifact | Check |
|---|---|---|
| Durable idempotency record and scope | `api_idempotency_record`, `uq_api_idempotency_scope`; §4 | OC-05, OC-06 |
| Semantic request digest | `request_semantic_digest`; §4 | OC-07 |
| Concurrency / no double execution | claim + fence + atomic completion; §4 | OC-08, OC-66 (SI) |
| Outcome semantics (original / reused / in-progress) | §4 | OC-09…OC-11 |
| No hidden response cache; finite window; no invented duration | §§4–5 | OC-12…OC-14 |
| If-Match aggregates and monotonic revision | §6 | OC-15…OC-20, OC-66 (SE) |
| Enrichment persistence | §7 | OC-21…OC-27 |
| Audit additions and audit-read | §8 | OC-28…OC-30 |
| Tombstone, immutability, cross-store deletion | §9 | OC-31…OC-36, OC-66 (SD) |
| Restore anti-resurrection | §11 | OC-37, OC-66 (SX) |
| Report / replay after deletion; replay boundaries | §12 | OC-38…OC-43, OC-66 (SR, SP) |
| Re-analysis | §13 | OC-44 |
| Provider policy | §10 | OC-45…OC-48 |
| API activation | §14 | OC-49…OC-52, OC-62 |
| Runtime parameters | §16 | OC-53…OC-55 |
| Carryovers / freeze / no implementation | §§1, 19 | OC-56…OC-61, OC-63…OC-65 |
| Truthful logical-object mapping (DATA-001 additive objects) | §2 | OC-67 |

## 21. Unresolved implementation values and owners

| Item | Owner |
|---|---|
| All §16 parameter values | As listed in §16 (Sponsor / operational configuration / implementation security profile) |
| Retention durations, residual tombstone metadata, backup purge timing | OI-05 (Sponsor + legal/governance) |
| Mechanism retaining the post-backup deletion record outside the restorable snapshot | P6-WP6 implementation profile / Phase 9 (`REQUIRED_BEFORE_DEPLOYMENT`) |
| Provider-policy storage and operator workflow/RBAC | Phase 9 |
| Physical SQL, Alembic revisions, triggers, repositories, API server, workers, connector | Phase 9 (ADR-0011 tooling) |
| ASM-002 tenancy confirmation | Sponsor / Programme (blocks the first schema-creating migration) |

## 22. Builder self-challenge (summary)

The same key cannot execute twice concurrently (unique-scope claim + fence + atomic completion); a different body with
the same key is rejected; different principals cannot collide; the key never authorizes; no C4 response content is
cached; no duration is invented; `OPEN → CLOSED → OPEN` cannot reuse an ETag; clients cannot set `mutation_revision`;
every If-Match aggregate has revision support; a `DetectionResult` is never mutated for deletion; deletion cannot report
`COMPLETE` while ECS content remains; restore cannot promote resurrected governed-deleted content; tombstones hold no
C4 content; replay calls neither AI nor a provider and never uses latest knowledge; current Phase-3 replay does not
require enrichment; provider `CLEAN` never means TrustLens safe; provider policies cannot be mutated in place or changed
by AI and replay never uses a "latest" policy; `listEvaluationEnrichments` is no longer FUTURE with method/path/operationId
unchanged and no raw provider response; API/OpenAPI counts (53/53) and parity are exact; OI-05 and G-09 stay OPEN; no
`tenant_id`; `ENGINE_VERSION` unchanged; no runtime code. Weaknesses are listed in GATE-024 §5.

## 23. Change log

| Version | Date | Change |
|---|---|---|
| 0.1 (approved) | 2026-10-03 | Acceptance bookkeeping: targeted independent re-review APPROVE (BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 0 / INFO 0 new); status APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING; review history in GATE-024 §§8–9 |
| 0.1 (review correction) | 2026-10-03 | Independent-review corrections: MEDIUM-1 — DATA-001 additive logical objects `ApiIdempotencyRecord` / `GovernedRemovalTombstone` replace the `CrossStoreOperation` / `DeletionAction` mappings (OC-67); LOW-1 — `RETENTION_DURATIONS` scoped to governed automatic expiry (OI-05); INFO-1 — audit-read ordering; INFO-2 — security/correctness vs implementation-profile parameter classes; INFO-3 — current-revision notes |
| 0.1 | 2026-10-03 | P6-WP6: initial operational contract candidate; additive DATA-001-WP2 revision P6-WP6-ADD-001; P6-WP6 additive activation of `listEvaluationEnrichments`; audit-read event; runtime-parameter registry; validator, scenarios, negative mutations |
