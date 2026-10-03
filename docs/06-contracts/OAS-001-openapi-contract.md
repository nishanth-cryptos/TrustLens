# OAS-001 — OpenAPI contract encoding of API-001

| Field | Value |
|---|---|
| Document ID | OAS-001 |
| Version | 0.1 |
| Status | **P6-WP4 OPENAPI CONTRACT APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING** (§19); not formally closed; no API implemented |
| Phase | Phase 6 — Data, API & Integration Contracts |
| Work package | P6-WP4 — OpenAPI specification + contract consistency validation |
| Owner role | API Architect / Backend Architect |
| Baseline | P6-WP3 merge `4d08c5e570b9a08b87a56a51213f0423ea74166f` (PR #28) |
| OpenAPI artifact | [`contracts/api/openapi-v1.json`](../../contracts/api/openapi-v1.json) — OpenAPI **3.1.0**, JSON |
| Encodes | [API-001](API-001-api-resource-protocol-contract.md) + [`contracts/api/api-v1.json`](../../contracts/api/api-v1.json) (authoritative API semantics) |
| Validator | `knowledge/validation/validate_openapi_contract.py` (36 checks, 44 negative mutations) |
| Checkpoint | [GATE-022](../00-program/GATE-022-phase-6-openapi-contract.md) |
| P6-WP6 delta | **P6-WP6 ADDITIVE ACTIVATION** (§20): `x-trustlens-availability` removed from `listEvaluationEnrichments`; `listAuditEvents` audit event `AUDIT_LOG_ACCESSED`; audit enums refreshed; ETag dependency satisfied — reviewed by [GATE-024](../00-program/GATE-024-phase-6-operational-contract.md), not GATE-022 |
| Current revision state | Original P6-WP4 work package merged (PR #29); the status above is historical. This document also contains a P6-WP6 additive delta (§20): APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING (GATE-024) |
| Last updated | 2026-10-03 |

---

## 1. Purpose, authority and claim boundary

OAS-001 explains how API-001 and its machine catalog are encoded in OpenAPI 3.1, and documents every choice that
standard OpenAPI keywords cannot express. **API-001 and `api-v1.json` remain authoritative for API semantics**;
OpenAPI encodes, constrains and is mechanically checked against them. The encoding exposed **no** ambiguity or
contradiction in API-001, so no accepted artifact was changed.

The OpenAPI document is a contract artifact. It is not an implementation, not generated server code, not deployed, and
**not certified**: validation is **deterministic structural validation plus catalog parity**. No official OpenAPI
conformance validator is pinned in `requirements.txt`, so no claim of full OpenAPI specification compliance is made.
Component schemas are checked against the JSON Schema Draft 2020-12 metaschema, which is the OpenAPI 3.1 schema
dialect. No FastAPI, framework, handler, middleware, gateway, storage SDK or UI exists. G-09 and OI-05 remain OPEN.

## 2. Document-level encoding

| Element | Encoding |
|---|---|
| `openapi` | `3.1.0`; `jsonSchemaDialect` = JSON Schema 2020-12; no OpenAPI-3.0-only `nullable` (nullability uses type unions or `oneOf` with `{"type": "null"}`) |
| `info.version` | `api-v1/contract-0.1.0` — the contract document version. Independent of `ENGINE_VERSION`, `bundle_version`/`content_digest`, `result_contract_version` and database migration revisions (OA-35) |
| `servers` | One relative placeholder `/` — no hostname, localhost or gateway, no topology implied (OA-02) |
| Base path | Public operations under `/api/v1`; `/health/live` and `/health/ready` are internal probes (`security: []`, `x-trustlens-internal: true`) |
| Format | JSON (no YAML parser dependency added; canonical CI stays deterministic and offline) |
| Tenancy | No tenant property, parameter or header anywhere; `x-trustlens-tenancy` mirrors ASM-002 UNCONFIRMED / PROVISIONAL (OA-18) |

## 3. Security scheme

`components.securitySchemes.bearerAuth` is `type: http`, `scheme: bearer`, describing an access token from the
external, pluggable OIDC/OAuth 2.0 identity provider (ADR-0009). No identity provider, password flow, client secret,
refresh token or token format is selected or exposed. Every protected operation declares `security: [{bearerAuth: []}]`.

**OpenAPI security declarations express authentication and coarse operation eligibility only.** Runtime authorization
additionally requires RBAC, resource-level authorization (case ownership/assignment), content permission
(`permits_evidence_content`) and break-glass constraints where applicable. These are carried by the `x-trustlens-*`
extensions (§4). Token claims never grant resource access by themselves.

## 4. TrustLens extensions

Extensions exist only to preserve machine-readable API-001 semantics that standard OpenAPI cannot express. Each maps
one catalog field, and the validator checks it for parity.

| Extension | Where | Meaning (catalog field) |
|---|---|---|
| `x-trustlens-roles` | operation | Roles eligible for the operation type (`roles`) — never sufficient alone |
| `x-trustlens-resource-authorization` | operation | Resource-level authorization category (`resource_authorization`, API-001 §5) |
| `x-trustlens-sensitive-content-permission` | operation | `NONE` / `DERIVED_CONTENT` / `EVIDENCE_CONTENT` (content permission required) |
| `x-trustlens-break-glass-roles` | operation | Roles that may reach content only via an active break-glass grant (ADMINISTRATOR only) |
| `x-trustlens-caller-constraints` | operation | `ASSIGNEE_NOT_CALLER`, `REVIEWER_NOT_GRANTEE` |
| `x-trustlens-grants-case-access` | operation | The operation creates a case-access grant |
| `x-trustlens-idempotency` | operation | `REQUIRED` / `NATURALLY_IDEMPOTENT` / `NOT_APPLICABLE` |
| `x-trustlens-audit` | operation | `{required, event}` governed audit obligation |
| `x-trustlens-sensitivity` | operation | Data class of what the operation can return or accept (`C1`…`C6`) |
| `x-trustlens-mode` | operation | `SYNC` / `ASYNC` |
| `x-trustlens-concurrency` | operation | `NONE` / `IF_MATCH_REQUIRED` |
| `x-trustlens-target-resource` | operation | API resource the operation acts on |
| `x-trustlens-internal` | operation | Internal health probe |
| `x-trustlens-replay-semantics` | operation | `{ai_recall: false, knowledge_selection: PINNED_ONLY, material_substitution: FORBIDDEN, creates_new_evaluation: false}` |
| `x-trustlens-knowledge-control` | operation | Governed knowledge activation/rollback/withdrawal |
| `x-trustlens-creates-new-evaluation` | operation | Creates a new evaluation (never replay) |
| `x-trustlens-availability` | operation | `FUTURE_INT_001` (enrichment, inactive until INT-001/ADR-0012) — removed by the P6-WP6 ADDITIVE ACTIVATION; no operation currently carries it |
| `x-trustlens-tenancy-status` | operation | `PROVISIONAL_BLOCKED_ON_ASM_002` |
| `x-trustlens-sort` | operation | Fixed stable sort order of a list |
| `x-trustlens-binary-body` | request/response | Catalog name of a raw-byte body (evidence/report content) |
| `x-trustlens-error-codes` | error response | Exact API-001 error codes documented under that HTTP status |
| `x-trustlens-trace` | schema property | AC-24 trace to a runtime-emitted Phase-3 node or an API-only category |
| `x-trustlens-visibility` | schema property | `DETAILED_VIEW_ONLY` / `CONTENT_PERMISSION` / `ANALYST_ONLY` (role-dependent representation) |
| `x-trustlens-untrusted`, `x-trustlens-advisory`, `x-trustlens-bounded-length` | schema property | Untrusted client metadata; advisory value; length bounded by configuration (no number invented) |
| `x-trustlens-schema-kind`, `x-trustlens-vocabulary` | schema | Request/response DTO kind; source vocabulary of an `Enum_*` schema |
| `x-trustlens-catalog`, `x-trustlens-etag-strategy`, `x-trustlens-tenancy` | document | Source catalog; ETag decision (§8); tenancy status |

## 5. Matrix A — operation mapping (generated)

| API-001 operationId | OpenAPI method + path | Success | Security | Mode |
|---|---|---|---|---|
| `getMe` | GET `/api/v1/me` | 200 | bearerAuth | SYNC |
| `getLiveness` | GET `/health/live` | 200 | none (internal probe) | SYNC |
| `getReadiness` | GET `/health/ready` | 200 | none (internal probe) | SYNC |
| `getOperationalHealth` | GET `/api/v1/ops/health` | 200 | bearerAuth | SYNC |
| `createCase` | POST `/api/v1/cases` | 201 | bearerAuth | SYNC |
| `listCases` | GET `/api/v1/cases` | 200 | bearerAuth | SYNC |
| `getCase` | GET `/api/v1/cases/{case_id}` | 200 | bearerAuth | SYNC |
| `closeCase` | POST `/api/v1/cases/{case_id}/close` | 200 | bearerAuth | SYNC |
| `reopenCase` | POST `/api/v1/cases/{case_id}/reopen` | 200 | bearerAuth | SYNC |
| `createSubmission` | POST `/api/v1/cases/{case_id}/submissions` | 201 | bearerAuth | SYNC |
| `listSubmissions` | GET `/api/v1/cases/{case_id}/submissions` | 200 | bearerAuth | SYNC |
| `getSubmission` | GET `/api/v1/submissions/{submission_id}` | 200 | bearerAuth | SYNC |
| `createEvidenceUpload` | POST `/api/v1/submissions/{submission_id}/evidence` | 201 | bearerAuth | SYNC |
| `putEvidenceContent` | PUT `/api/v1/evidence/{evidence_id}/content` | 200 | bearerAuth | SYNC |
| `finalizeEvidence` | POST `/api/v1/evidence/{evidence_id}/finalize` | 202 | bearerAuth | ASYNC |
| `listEvidence` | GET `/api/v1/submissions/{submission_id}/evidence` | 200 | bearerAuth | SYNC |
| `getEvidenceMetadata` | GET `/api/v1/evidence/{evidence_id}` | 200 | bearerAuth | SYNC |
| `getEvidenceContent` | GET `/api/v1/evidence/{evidence_id}/content` | 200 | bearerAuth | SYNC |
| `createEvaluations` | POST `/api/v1/submissions/{submission_id}/evaluations` | 202 | bearerAuth | ASYNC |
| `listCaseEvaluations` | GET `/api/v1/cases/{case_id}/evaluations` | 200 | bearerAuth | SYNC |
| `getEvaluation` | GET `/api/v1/evaluations/{evaluation_id}` | 200 | bearerAuth | SYNC |
| `getDetectionResult` | GET `/api/v1/evaluations/{evaluation_id}/result` | 200 | bearerAuth | SYNC |
| `createCorrection` | POST `/api/v1/evaluations/{evaluation_id}/corrections` | 202 | bearerAuth | ASYNC |
| `listEvaluationEnrichments` | GET `/api/v1/evaluations/{evaluation_id}/enrichments` | 200 | bearerAuth | SYNC |
| `createAdjudication` | POST `/api/v1/evaluations/{evaluation_id}/adjudications` | 201 | bearerAuth | SYNC |
| `listAdjudications` | GET `/api/v1/evaluations/{evaluation_id}/adjudications` | 200 | bearerAuth | SYNC |
| `getAdjudication` | GET `/api/v1/adjudications/{adjudication_id}` | 200 | bearerAuth | SYNC |
| `listReviewQueue` | GET `/api/v1/review-queue` | 200 | bearerAuth | SYNC |
| `assignReview` | POST `/api/v1/review-queue/{review_item_id}/assignment` | 200 | bearerAuth | SYNC |
| `listCaseAccessGrants` | GET `/api/v1/cases/{case_id}/access-grants` | 200 | bearerAuth | SYNC |
| `revokeCaseAccessGrant` | POST `/api/v1/access-grants/{grant_id}/revoke` | 200 | bearerAuth | SYNC |
| `createReport` | POST `/api/v1/cases/{case_id}/reports` | 202 | bearerAuth | ASYNC |
| `listReports` | GET `/api/v1/cases/{case_id}/reports` | 200 | bearerAuth | SYNC |
| `getReport` | GET `/api/v1/reports/{report_id}` | 200 | bearerAuth | SYNC |
| `getReportContent` | GET `/api/v1/reports/{report_id}/content` | 200 | bearerAuth | SYNC |
| `createReplay` | POST `/api/v1/evaluations/{evaluation_id}/replays` | 202 | bearerAuth | ASYNC |
| `getReplay` | GET `/api/v1/replays/{replay_id}` | 200 | bearerAuth | SYNC |
| `getActiveKnowledge` | GET `/api/v1/knowledge/active` | 200 | bearerAuth | SYNC |
| `getKnowledgeBundle` | GET `/api/v1/knowledge/bundles/{content_digest}` | 200 | bearerAuth | SYNC |
| `listKnowledgeActivations` | GET `/api/v1/knowledge/activations` | 200 | bearerAuth | SYNC |
| `activateKnowledgeBundle` | POST `/api/v1/knowledge/deployment/activate` | 202 | bearerAuth | ASYNC |
| `rollbackKnowledgeBundle` | POST `/api/v1/knowledge/deployment/rollback` | 202 | bearerAuth | ASYNC |
| `withdrawKnowledgeBundle` | POST `/api/v1/knowledge/bundles/{content_digest}/withdrawal` | 202 | bearerAuth | ASYNC |
| `createDeletionRequest` | POST `/api/v1/deletion-requests` | 201 | bearerAuth | SYNC |
| `listDeletionRequests` | GET `/api/v1/deletion-requests` | 200 | bearerAuth | SYNC |
| `getDeletionRequest` | GET `/api/v1/deletion-requests/{deletion_request_id}` | 200 | bearerAuth | SYNC |
| `authorizeDeletionRequest` | POST `/api/v1/deletion-requests/{deletion_request_id}/authorize` | 202 | bearerAuth | ASYNC |
| `rejectDeletionRequest` | POST `/api/v1/deletion-requests/{deletion_request_id}/reject` | 200 | bearerAuth | SYNC |
| `createBreakGlassGrant` | POST `/api/v1/break-glass-grants` | 201 | bearerAuth | SYNC |
| `getBreakGlassGrant` | GET `/api/v1/break-glass-grants/{break_glass_grant_id}` | 200 | bearerAuth | SYNC |
| `endBreakGlassGrant` | POST `/api/v1/break-glass-grants/{break_glass_grant_id}/end` | 200 | bearerAuth | SYNC |
| `reviewBreakGlassGrant` | POST `/api/v1/break-glass-grants/{break_glass_grant_id}/review` | 200 | bearerAuth | SYNC |
| `listAuditEvents` | GET `/api/v1/audit-events` | 200 | bearerAuth | SYNC |

Exactly the 53 catalog operations appear, each once, with identical `operationId`, method and path. There are no extra
operations (OA-03/OA-04).

## 6. Schemas

- **Request DTOs** (Matrix B) are operation-specific components with `additionalProperties: false`. None carries a
  server-controlled field (owner, creator, actor, audit hash, fence token, decision axes, provenance, digest authority,
  `ENGINE_VERSION`, state, server timestamps, roles), so mass assignment is impossible at the contract level (OA-29,
  OA-31).
- **Response DTOs** (Matrix C) are API views, independent of PostgreSQL rows: no foreign-key columns, trigger state,
  fence tokens, audit-chain internals beyond the content-free audit view API-001 defines, secret references or provider
  credentials. Responses are open (clients tolerate unknown properties) per API-001 §32.
- **Enums** are `Enum_<vocabulary>` components carrying the exact accepted values (persistence- and Phase-3-synchronised
  through the catalog). Nothing is renamed, re-cased or merged (OA-16).
- **Types:** opaque IDs `string` / `format: uuid`; timestamps `string` / `format: date-time` (UTC, RFC 3339,
  server-authoritative); 64-hex digests with `pattern`; bounded text marked `x-trustlens-bounded-length` without inventing
  a number.
- **Field visibility:** role-dependent fields carry `x-trustlens-visibility` instead of being implied universally visible.
  The per-rule decomposition is `DETAILED_VIEW_ONLY`; explanation evidence basis and adjudication rationale are
  `CONTENT_PERMISSION` (assignment alone is insufficient). Operations that can return them are C4 (OA-27).

### 6.1 Matrix B — request schemas (generated)

| API-001 request schema | OpenAPI encoding | Unknown properties |
|---|---|---|
| `EmptyCommandRequest` | `#/components/schemas/EmptyCommandRequest` | rejected (`additionalProperties: false`) |
| `ReasonCommandRequest` | `#/components/schemas/ReasonCommandRequest` | rejected (`additionalProperties: false`) |
| `CaseCreateRequest` | `#/components/schemas/CaseCreateRequest` | rejected (`additionalProperties: false`) |
| `CaseCloseRequest` | `#/components/schemas/CaseCloseRequest` | rejected (`additionalProperties: false`) |
| `SubmissionCreateRequest` | `#/components/schemas/SubmissionCreateRequest` | rejected (`additionalProperties: false`) |
| `EvidenceUploadCreateRequest` | `#/components/schemas/EvidenceUploadCreateRequest` | rejected (`additionalProperties: false`) |
| `EvidenceContentUpload` | binary body `*/*` (`x-trustlens-binary-body`) | n/a (raw bytes) |
| `EvidenceFinalizeRequest` | `#/components/schemas/EvidenceFinalizeRequest` | rejected (`additionalProperties: false`) |
| `EvaluationCreateRequest` | `#/components/schemas/EvaluationCreateRequest` | rejected (`additionalProperties: false`) |
| `UserCorrectionCreateRequest` | `#/components/schemas/UserCorrectionCreateRequest` | rejected (`additionalProperties: false`) |
| `AdjudicationCreateRequest` | `#/components/schemas/AdjudicationCreateRequest` | rejected (`additionalProperties: false`) |
| `ReviewAssignmentRequest` | `#/components/schemas/ReviewAssignmentRequest` | rejected (`additionalProperties: false`) |
| `ReportCreateRequest` | `#/components/schemas/ReportCreateRequest` | rejected (`additionalProperties: false`) |
| `ReplayCreateRequest` | `#/components/schemas/ReplayCreateRequest` | rejected (`additionalProperties: false`) |
| `KnowledgeActivationRequest` | `#/components/schemas/KnowledgeActivationRequest` | rejected (`additionalProperties: false`) |
| `KnowledgeRollbackRequest` | `#/components/schemas/KnowledgeRollbackRequest` | rejected (`additionalProperties: false`) |
| `KnowledgeWithdrawalRequest` | `#/components/schemas/KnowledgeWithdrawalRequest` | rejected (`additionalProperties: false`) |
| `DeletionRequestCreateRequest` | `#/components/schemas/DeletionRequestCreateRequest` | rejected (`additionalProperties: false`) |
| `BreakGlassCreateRequest` | `#/components/schemas/BreakGlassCreateRequest` | rejected (`additionalProperties: false`) |
| `BreakGlassReviewRequest` | `#/components/schemas/BreakGlassReviewRequest` | rejected (`additionalProperties: false`) |

### 6.2 Matrix C — response schemas (generated)

| API-001 response schema | OpenAPI encoding |
|---|---|
| `ApiError` | `#/components/schemas/ApiError` |
| `ApiErrorBody` | `#/components/schemas/ApiErrorBody` |
| `FieldError` | `#/components/schemas/FieldError` |
| `PageInfo` | `#/components/schemas/PageInfo` |
| `MeResponse` | `#/components/schemas/MeResponse` |
| `HealthProbeResponse` | `#/components/schemas/HealthProbeResponse` |
| `OperationalHealthResponse` | `#/components/schemas/OperationalHealthResponse` |
| `CapabilityHealth` | `#/components/schemas/CapabilityHealth` |
| `CaseResponse` | `#/components/schemas/CaseResponse` |
| `CaseViewerAccess` | `#/components/schemas/CaseViewerAccess` |
| `Links` | `#/components/schemas/Links` |
| `CaseListResponse` | `#/components/schemas/CaseListResponse` |
| `SubmissionResponse` | `#/components/schemas/SubmissionResponse` |
| `SubmissionListResponse` | `#/components/schemas/SubmissionListResponse` |
| `EvidenceMetadataResponse` | `#/components/schemas/EvidenceMetadataResponse` |
| `EvidenceListResponse` | `#/components/schemas/EvidenceListResponse` |
| `EvidenceContentDownload` | binary body `*/*` (`x-trustlens-binary-body`) |
| `EvaluationBatchAcceptedResponse` | `#/components/schemas/EvaluationBatchAcceptedResponse` |
| `EvaluationResponse` | `#/components/schemas/EvaluationResponse` |
| `EvaluationFailure` | `#/components/schemas/EvaluationFailure` |
| `AiUsageSummary` | `#/components/schemas/AiUsageSummary` |
| `ProvenanceSummary` | `#/components/schemas/ProvenanceSummary` |
| `EvaluationListResponse` | `#/components/schemas/EvaluationListResponse` |
| `DetectionResultResponse` | `#/components/schemas/DetectionResultResponse` |
| `RuleReference` | `#/components/schemas/RuleReference` |
| `ExplanationView` | `#/components/schemas/ExplanationView` |
| `RecommendedActionView` | `#/components/schemas/RecommendedActionView` |
| `RuleResultView` | `#/components/schemas/RuleResultView` |
| `CorrectionAcceptedResponse` | `#/components/schemas/CorrectionAcceptedResponse` |
| `EnrichmentListResponse` | `#/components/schemas/EnrichmentListResponse` |
| `EnrichmentView` | `#/components/schemas/EnrichmentView` |
| `AdjudicationResponse` | `#/components/schemas/AdjudicationResponse` |
| `AdjudicationListResponse` | `#/components/schemas/AdjudicationListResponse` |
| `ReviewItemResponse` | `#/components/schemas/ReviewItemResponse` |
| `ReviewQueueResponse` | `#/components/schemas/ReviewQueueResponse` |
| `CaseAccessGrantResponse` | `#/components/schemas/CaseAccessGrantResponse` |
| `CaseAccessGrantListResponse` | `#/components/schemas/CaseAccessGrantListResponse` |
| `ReportResponse` | `#/components/schemas/ReportResponse` |
| `ReportListResponse` | `#/components/schemas/ReportListResponse` |
| `ReportContentDownload` | binary body `*/*` (`x-trustlens-binary-body`) |
| `ReplayResponse` | `#/components/schemas/ReplayResponse` |
| `KnowledgeActiveResponse` | `#/components/schemas/KnowledgeActiveResponse` |
| `KnowledgeBundleResponse` | `#/components/schemas/KnowledgeBundleResponse` |
| `KnowledgeActivationListResponse` | `#/components/schemas/KnowledgeActivationListResponse` |
| `KnowledgeActivationResponse` | `#/components/schemas/KnowledgeActivationResponse` |
| `DeletionRequestResponse` | `#/components/schemas/DeletionRequestResponse` |
| `DeletionRequestListResponse` | `#/components/schemas/DeletionRequestListResponse` |
| `BreakGlassGrantResponse` | `#/components/schemas/BreakGlassGrantResponse` |
| `AuditEventListResponse` | `#/components/schemas/AuditEventListResponse` |
| `AuditEventView` | `#/components/schemas/AuditEventView` |

## 7. Parameters, headers and protocol

- **Path parameters:** UUIDv4 strings; `content_digest` is a 64-hex governed knowledge identifier.
- **`Idempotency-Key`** header: present and **required** on every operation the catalog marks `REQUIRED` (all POSTs).
  Same key + equivalent request → original outcome; same key + different request → `409 IDEMPOTENCY_KEY_REUSED`;
  original still running → `409 IDEMPOTENCY_IN_PROGRESS`. The content PUT is naturally idempotent and has no key (OA-10).
- **`If-Match`** header: required on guarded commands (case close/reopen, review assignment, deletion authorize/reject),
  with `412 PRECONDITION_FAILED` and `428 PRECONDITION_REQUIRED` documented. Immutable resources have no precondition
  (OA-14).
- **`ETag`** response header on Case, ReviewItem and DeletionRequest responses (§8).
- **`X-Request-Id`** on every response; `Retry-After` optionally on 429/503.
- **Pagination:** `cursor` + `limit` on every list, plus exactly the catalog's allow-listed filters, typed by vocabulary.
  `limit` has `minimum: 1` and **no default or maximum** (implementation-configured, NOT YET SPECIFIED) (OA-30). Sort
  order is fixed (`x-trustlens-sort`); no generic filter, sort or expression parameter exists.
- **`view`** query parameter on `getDetectionResult` (`STANDARD` | `DETAILED`, API-001 §14).
- **Async:** async operations answer `202` with the resource/status representation API-001 defines; no `Location`
  header, SLA or polling interval is invented (OA-13).
- **Binary content:** evidence upload is a raw-byte request body (`*/*`, `contentMediaType: application/octet-stream`;
  the server validates the declared media type, which is configuration). Evidence and report downloads are raw-byte
  responses with `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff` and `Cache-Control: no-store`.
  Nothing is base64-wrapped in JSON (OA-33). API-001 selects this single application-mediated mechanism, so no
  multipart or pre-authorized-upload variant appears.

## 8. ETag derivation — WP3 LOW-3 decision

**Decision B: a server-authoritative revision source is required; WP2 needs an additive revision before
implementation.**

| Resource | Mutable state (DATA-001-WP2) | ABA risk with a representation-derived ETag | Assessment |
|---|---|---|---|
| Case (`case_record`) | `lifecycle_state`, `closed_at` | **Yes** — OPEN → CLOSED → OPEN can return the same state and a cleared `closed_at` | Needs a monotonic revision |
| Review item (`review_routing_state`) | `queue_state`, assignee, `state_changed_at` | Low — `state_changed_at` changes on each transition, but equal timestamps are possible | Uniform monotonic revision preferred |
| Deletion request (`deletion_request`) | forward-only `state`, `authorized_at`, `completed_at` | No — the lifecycle never returns to an earlier state | Representation-safe today; use the uniform revision once added |
| Knowledge deployment | active `content_digest` | Guarded by `expected_active_content_digest`, not ETag | A→B→A re-matches the same exact identity; acceptable because the guarded value is the identity itself |

**API-side rule (now fixed):** `ETag` is an opaque **strong** validator derived from the resource's
server-authoritative **monotonic revision** (incremented on every committed mutation), never from fields that can
return to a prior value. It encodes nothing about the resource.

**Implementation dependency:** DATA-001-WP2 has no such revision for `case_record` or `review_routing_state`. An
additive WP2 revision (for example a monotonic revision column) is required **before implementation**. OpenAPI invents
no database field. This closes the WP3 **API-design** LOW-3 and records a persistence implementation dependency owned by
the additive DATA-001-WP2 revision + P6-WP6. The decision is machine-readable as `x-trustlens-etag-strategy` (OA-34).

## 9. Matrix D — authentication and authorization (generated)

| operationId | Roles (`x-trustlens-roles`) | Resource authorization | Content permission | Break-glass roles | Caller constraints |
|---|---|---|---|---|---|
| `getMe` | U, A, KE, KA, AD | `SELF` | NONE | — | — |
| `getLiveness` | — | `NONE_INTERNAL_PROBE` | NONE | — | — |
| `getReadiness` | — | `NONE_INTERNAL_PROBE` | NONE | — | — |
| `getOperationalHealth` | AD | `PLATFORM_ADMIN` | NONE | — | — |
| `createCase` | U | `SELF` | NONE | — | — |
| `listCases` | U, A | `CASE_ACCESS` | NONE | — | — |
| `getCase` | U, A | `CASE_ACCESS` | NONE | — | — |
| `closeCase` | U, A | `CASE_ACCESS` | NONE | — | — |
| `reopenCase` | U, A | `CASE_ACCESS` | NONE | — | — |
| `createSubmission` | U | `CASE_OWNER` | NONE | — | — |
| `listSubmissions` | U, A | `CASE_ACCESS` | NONE | — | — |
| `getSubmission` | U, A | `CASE_ACCESS` | NONE | — | — |
| `createEvidenceUpload` | U | `CASE_OWNER` | NONE | — | — |
| `putEvidenceContent` | U | `CASE_OWNER` | EVIDENCE_CONTENT | — | — |
| `finalizeEvidence` | U | `CASE_OWNER` | NONE | — | — |
| `listEvidence` | U, A | `CASE_ACCESS` | NONE | — | — |
| `getEvidenceMetadata` | U, A | `CASE_ACCESS` | NONE | — | — |
| `getEvidenceContent` | U, A | `CASE_EVIDENCE_CONTENT` | EVIDENCE_CONTENT | AD | — |
| `createEvaluations` | U, A | `CASE_ACCESS` | NONE | — | — |
| `listCaseEvaluations` | U, A | `CASE_ACCESS` | NONE | — | — |
| `getEvaluation` | U, A | `CASE_ACCESS` | NONE | — | — |
| `getDetectionResult` | U, A | `CASE_DERIVED_CONTENT` | DERIVED_CONTENT | — | — |
| `createCorrection` | U | `CASE_OWNER` | DERIVED_CONTENT | — | — |
| `listEvaluationEnrichments` | A | `CASE_ACCESS` | NONE | — | — |
| `createAdjudication` | A | `CASE_ASSIGNED_ANALYST` | DERIVED_CONTENT | — | — |
| `listAdjudications` | U, A | `CASE_ACCESS` | NONE | — | — |
| `getAdjudication` | U, A | `CASE_ACCESS` | NONE | — | — |
| `listReviewQueue` | A | `REVIEW_QUEUE` | NONE | — | — |
| `assignReview` | AD | `PLATFORM_ADMIN` | NONE | — | ASSIGNEE_NOT_CALLER |
| `listCaseAccessGrants` | U, AD | `CASE_OWNER_OR_PLATFORM_ADMIN` | NONE | — | — |
| `revokeCaseAccessGrant` | AD | `PLATFORM_ADMIN` | NONE | — | — |
| `createReport` | U, A | `CASE_DERIVED_CONTENT` | DERIVED_CONTENT | — | — |
| `listReports` | U, A | `CASE_ACCESS` | NONE | — | — |
| `getReport` | U, A | `CASE_ACCESS` | NONE | — | — |
| `getReportContent` | U, A | `CASE_DERIVED_CONTENT` | DERIVED_CONTENT | — | — |
| `createReplay` | A, AD | `CASE_ASSIGNED_ANALYST_OR_PLATFORM_ADMIN` | NONE | — | — |
| `getReplay` | A, AD | `CASE_ASSIGNED_ANALYST_OR_PLATFORM_ADMIN` | NONE | — | — |
| `getActiveKnowledge` | A, KE, KA, AD | `KNOWLEDGE_READ` | NONE | — | — |
| `getKnowledgeBundle` | A, KE, KA, AD | `KNOWLEDGE_READ` | NONE | — | — |
| `listKnowledgeActivations` | KE, KA, AD | `KNOWLEDGE_READ` | NONE | — | — |
| `activateKnowledgeBundle` | AD | `KNOWLEDGE_OPERATION` | NONE | — | — |
| `rollbackKnowledgeBundle` | AD | `KNOWLEDGE_OPERATION` | NONE | — | — |
| `withdrawKnowledgeBundle` | KA | `KNOWLEDGE_OPERATION` | NONE | — | — |
| `createDeletionRequest` | U | `DELETION_SCOPE_OWNER` | NONE | — | — |
| `listDeletionRequests` | U, AD | `DELETION_SCOPE_OWNER_OR_PLATFORM_ADMIN` | NONE | — | — |
| `getDeletionRequest` | U, AD | `DELETION_SCOPE_OWNER_OR_PLATFORM_ADMIN` | NONE | — | — |
| `authorizeDeletionRequest` | AD | `PLATFORM_ADMIN` | NONE | — | — |
| `rejectDeletionRequest` | AD | `PLATFORM_ADMIN` | NONE | — | — |
| `createBreakGlassGrant` | AD | `BREAK_GLASS_SELF` | NONE | — | — |
| `getBreakGlassGrant` | AD | `BREAK_GLASS_GRANTEE_OR_PLATFORM_ADMIN` | NONE | — | — |
| `endBreakGlassGrant` | AD | `BREAK_GLASS_GRANTEE` | NONE | — | — |
| `reviewBreakGlassGrant` | AD | `BREAK_GLASS_REVIEWER` | NONE | — | REVIEWER_NOT_GRANTEE |
| `listAuditEvents` | AD | `AUDIT_READ` | NONE | — | — |

No operation lets ADMINISTRATOR reach evidence or derived content by role; break-glass is ADMINISTRATOR-only and its
review must be by a different principal; review assignment forbids self-assignment, including for dual-role principals
(OA-25, OA-26).

## 10. Matrix E — errors and status (generated)

| Error code | HTTP | Retryability |
|---|---:|---|
| `INVALID_REQUEST` | 400 | RETRY_WITH_CHANGES |
| `UNAUTHENTICATED` | 401 | RETRY_WITH_CHANGES |
| `FORBIDDEN` | 403 | NOT_RETRYABLE |
| `NOT_FOUND` | 404 | NOT_RETRYABLE |
| `CONFLICT` | 409 | NOT_RETRYABLE |
| `IDEMPOTENCY_KEY_REUSED` | 409 | RETRY_WITH_CHANGES |
| `IDEMPOTENCY_IN_PROGRESS` | 409 | RETRYABLE |
| `STATE_CONFLICT` | 409 | NOT_RETRYABLE |
| `EVALUATION_NOT_COMPLETED` | 409 | RETRYABLE |
| `PRECONDITION_FAILED` | 412 | RETRY_WITH_CHANGES |
| `PRECONDITION_REQUIRED` | 428 | RETRY_WITH_CHANGES |
| `REMOVED_UNDER_GOVERNANCE` | 410 | NOT_RETRYABLE |
| `PAYLOAD_TOO_LARGE` | 413 | RETRY_WITH_CHANGES |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | RETRY_WITH_CHANGES |
| `RATE_LIMITED` | 429 | RETRYABLE |
| `DEPENDENCY_UNAVAILABLE` | 503 | RETRYABLE |
| `INTEGRITY_FAILURE` | 500 | NOT_RETRYABLE |
| `REPLAY_UNAVAILABLE` | 409 | NOT_RETRYABLE |
| `REPORT_REGENERATION_UNAVAILABLE` | 409 | NOT_RETRYABLE |
| `KNOWLEDGE_NOT_ELIGIBLE` | 409 | NOT_RETRYABLE |
| `INTERNAL_ERROR` | 500 | RETRYABLE |

Each operation documents only its own catalog error codes, grouped by HTTP status, with the exact codes listed in
`x-trustlens-error-codes` and the `ApiError` envelope (`code`, `message`, `request_id`, `retryability`,
`field_errors`). No stack trace, SQL, path, credential, token, evidence or topology field exists (OA-15). Replay
unavailability is an explicit `409 REPLAY_UNAVAILABLE` or a replay record outcome, never a 500. Governed-deletion
tombstones answer `410 REMOVED_UNDER_GOVERNANCE`.

## 11. Matrix F — idempotency and concurrency (generated)

| operationId | Idempotency | `Idempotency-Key` header | If-Match |
|---|---|---|---|
| `getMe` | NOT_APPLICABLE | — | — |
| `getLiveness` | NOT_APPLICABLE | — | — |
| `getReadiness` | NOT_APPLICABLE | — | — |
| `getOperationalHealth` | NOT_APPLICABLE | — | — |
| `createCase` | REQUIRED | required | — |
| `listCases` | NOT_APPLICABLE | — | — |
| `getCase` | NOT_APPLICABLE | — | — |
| `closeCase` | REQUIRED | required | required (412/428) |
| `reopenCase` | REQUIRED | required | required (412/428) |
| `createSubmission` | REQUIRED | required | — |
| `listSubmissions` | NOT_APPLICABLE | — | — |
| `getSubmission` | NOT_APPLICABLE | — | — |
| `createEvidenceUpload` | REQUIRED | required | — |
| `putEvidenceContent` | NATURALLY_IDEMPOTENT | — | — |
| `finalizeEvidence` | REQUIRED | required | — |
| `listEvidence` | NOT_APPLICABLE | — | — |
| `getEvidenceMetadata` | NOT_APPLICABLE | — | — |
| `getEvidenceContent` | NOT_APPLICABLE | — | — |
| `createEvaluations` | REQUIRED | required | — |
| `listCaseEvaluations` | NOT_APPLICABLE | — | — |
| `getEvaluation` | NOT_APPLICABLE | — | — |
| `getDetectionResult` | NOT_APPLICABLE | — | — |
| `createCorrection` | REQUIRED | required | — |
| `listEvaluationEnrichments` | NOT_APPLICABLE | — | — |
| `createAdjudication` | REQUIRED | required | — |
| `listAdjudications` | NOT_APPLICABLE | — | — |
| `getAdjudication` | NOT_APPLICABLE | — | — |
| `listReviewQueue` | NOT_APPLICABLE | — | — |
| `assignReview` | REQUIRED | required | required (412/428) |
| `listCaseAccessGrants` | NOT_APPLICABLE | — | — |
| `revokeCaseAccessGrant` | REQUIRED | required | — |
| `createReport` | REQUIRED | required | — |
| `listReports` | NOT_APPLICABLE | — | — |
| `getReport` | NOT_APPLICABLE | — | — |
| `getReportContent` | NOT_APPLICABLE | — | — |
| `createReplay` | REQUIRED | required | — |
| `getReplay` | NOT_APPLICABLE | — | — |
| `getActiveKnowledge` | NOT_APPLICABLE | — | — |
| `getKnowledgeBundle` | NOT_APPLICABLE | — | — |
| `listKnowledgeActivations` | NOT_APPLICABLE | — | — |
| `activateKnowledgeBundle` | REQUIRED | required | — |
| `rollbackKnowledgeBundle` | REQUIRED | required | — |
| `withdrawKnowledgeBundle` | REQUIRED | required | — |
| `createDeletionRequest` | REQUIRED | required | — |
| `listDeletionRequests` | NOT_APPLICABLE | — | — |
| `getDeletionRequest` | NOT_APPLICABLE | — | — |
| `authorizeDeletionRequest` | REQUIRED | required | required (412/428) |
| `rejectDeletionRequest` | REQUIRED | required | required (412/428) |
| `createBreakGlassGrant` | REQUIRED | required | — |
| `getBreakGlassGrant` | NOT_APPLICABLE | — | — |
| `endBreakGlassGrant` | REQUIRED | required | — |
| `reviewBreakGlassGrant` | REQUIRED | required | — |
| `listAuditEvents` | NOT_APPLICABLE | — | — |

The OpenAPI header does **not** solve durable idempotency: the persistence record remains **OPEN / NON-BLOCKING**,
owned by the additive DATA-001-WP2 revision + P6-WP6. No retention period is invented.

## 12. Matrix G — sensitivity and audit (generated)

| operationId | Sensitivity | Audit required | Audit event |
|---|---|---|---|
| `getMe` | C5 | no | `None` |
| `getLiveness` | C2 | no | `None` |
| `getReadiness` | C2 | no | `None` |
| `getOperationalHealth` | C2 | no | `None` |
| `createCase` | C2 | yes | `CASE_CREATED` |
| `listCases` | C2 | no | `None` |
| `getCase` | C2 | no | `None` |
| `closeCase` | C2 | yes | `CASE_STATE_CHANGED` |
| `reopenCase` | C2 | yes | `CASE_STATE_CHANGED` |
| `createSubmission` | C2 | no | `None` |
| `listSubmissions` | C2 | no | `None` |
| `getSubmission` | C2 | no | `None` |
| `createEvidenceUpload` | C2 | yes | `EVIDENCE_RECEIVED` |
| `putEvidenceContent` | C3 | yes | `EVIDENCE_STORED` |
| `finalizeEvidence` | C2 | yes | `EVIDENCE_STORED` |
| `listEvidence` | C2 | no | `None` |
| `getEvidenceMetadata` | C2 | no | `None` |
| `getEvidenceContent` | C3 | yes | `EVIDENCE_ACCESSED` |
| `createEvaluations` | C2 | yes | `EVALUATION_STARTED` |
| `listCaseEvaluations` | C2 | no | `None` |
| `getEvaluation` | C2 | no | `None` |
| `getDetectionResult` | C4 | yes | `EVIDENCE_ACCESSED` |
| `createCorrection` | C4 | yes | `USER_CORRECTION` |
| `listEvaluationEnrichments` | C2 | no | `None` |
| `createAdjudication` | C4 | yes | `ANALYST_ADJUDICATION` |
| `listAdjudications` | C4 | yes | `EVIDENCE_ACCESSED` |
| `getAdjudication` | C4 | yes | `EVIDENCE_ACCESSED` |
| `listReviewQueue` | C2 | no | `None` |
| `assignReview` | C2 | yes | `CASE_ACCESS_GRANTED` |
| `listCaseAccessGrants` | C5 | no | `None` |
| `revokeCaseAccessGrant` | C5 | yes | `CASE_ACCESS_REVOKED` |
| `createReport` | C4 | yes | `REPORT_GENERATED` |
| `listReports` | C2 | no | `None` |
| `getReport` | C2 | no | `None` |
| `getReportContent` | C4 | yes | `REPORT_EXPORTED` |
| `createReplay` | C2 | yes | `REPLAY_EXECUTED` |
| `getReplay` | C2 | no | `None` |
| `getActiveKnowledge` | C1 | no | `None` |
| `getKnowledgeBundle` | C1 | no | `None` |
| `listKnowledgeActivations` | C2 | no | `None` |
| `activateKnowledgeBundle` | C2 | yes | `KNOWLEDGE_ACTIVATED` |
| `rollbackKnowledgeBundle` | C2 | yes | `KNOWLEDGE_ROLLED_BACK` |
| `withdrawKnowledgeBundle` | C2 | yes | `KNOWLEDGE_WITHDRAWN` |
| `createDeletionRequest` | C2 | yes | `DELETION_REQUESTED` |
| `listDeletionRequests` | C2 | no | `None` |
| `getDeletionRequest` | C2 | no | `None` |
| `authorizeDeletionRequest` | C2 | yes | `RETENTION_ACTION` |
| `rejectDeletionRequest` | C2 | yes | `RETENTION_ACTION` |
| `createBreakGlassGrant` | C5 | yes | `BREAK_GLASS_ACTIVATED` |
| `getBreakGlassGrant` | C5 | no | `None` |
| `endBreakGlassGrant` | C5 | yes | `BREAK_GLASS_EXPIRED` |
| `reviewBreakGlassGrant` | C5 | yes | `BREAK_GLASS_REVIEWED` |
| `listAuditEvents` | C6 | yes | `AUDIT_LOG_ACCESSED` (P6-WP6 additive) |

## 13. Matrix H — API-001 invariant → validator check

| Invariant | Check(s) |
|---|---|
| OpenAPI 3.1, no 3.0 semantics, 2020-12 schemas | OA-01, OA-36 |
| No hostname/topology | OA-02 |
| Exact operation surface (no missing, no extra, no duplicate) | OA-03, OA-04 |
| Success/response/request parity | OA-05, OA-06, OA-07 |
| Auth + role + resource-authorization + content permission parity | OA-08, OA-09 |
| Idempotency, audit, sensitivity, async, If-Match parity | OA-10, OA-11, OA-12, OA-13, OA-14 |
| Error code and status parity | OA-15 |
| Schema parity, request DTOs closed, exact enums | OA-16, OA-29 |
| Local refs only, all resolve | OA-17 |
| No tenancy | OA-18 |
| No invented decision field (priority, probability, score, rank, urgency) | OA-19, OA-21 |
| DetectionResult immutable; no DELETE | OA-20 |
| Knowledge by exact `content_digest`; no bundle_version or latest | OA-22, OA-23 |
| No arbitrary URL fetch | OA-24 |
| Break-glass ADMINISTRATOR-only; reviewer ≠ grantee | OA-25, OA-26 |
| No self-assignment | OA-26 |
| C4 visibility + sensitivity | OA-27 |
| Pinned, no-AI, no-substitution replay | OA-28 |
| Pagination/filters/sort allow-list, no invented limits | OA-30 |
| Server timestamps not client-settable | OA-31 |
| Health exposes no topology | OA-32 |
| Binary bodies, no base64 | OA-33 |
| ETag server-revision decision | OA-34 |
| Version independence; no web framework dependency | OA-35 |

## 14. Matrix I — Phase-3 governed fields (generated)

| OpenAPI property | `x-trustlens-trace` |
|---|---|
| `DetectionResultResponse.evaluation_id` | `phase3:detection-result.schema.json#/properties/evaluation_id` |
| `DetectionResultResponse.result_contract_version` | `phase3:detection-result.schema.json#/properties/result_contract_version` |
| `DetectionResultResponse.result_digest` | `api:PERSISTENCE_PROVENANCE` |
| `DetectionResultResponse.view` | `api:VIEW_SELECTOR` |
| `DetectionResultResponse.input_support_status` | `phase3:detection-result.schema.json#/properties/input_support_status` |
| `DetectionResultResponse.language` | `phase3:detection-result.schema.json#/properties/language` |
| `DetectionResultResponse.script` | `phase3:detection-result.schema.json#/properties/script` |
| `DetectionResultResponse.classification` | `phase3:detection-result.schema.json#/properties/classification` |
| `DetectionResultResponse.decision_severity` | `phase3:detection-result.schema.json#/properties/decision_severity` |
| `DetectionResultResponse.matched_evidence_strength` | `phase3:detection-result.schema.json#/properties/matched_evidence_strength` |
| `DetectionResultResponse.risk_level` | `phase3:detection-result.schema.json#/properties/risk_level` |
| `DetectionResultResponse.detection_confidence` | `phase3:detection-result.schema.json#/properties/detection_confidence` |
| `DetectionResultResponse.degraded` | `phase3:detection-result.schema.json#/properties/degraded` |
| `DetectionResultResponse.governing_rule` | `phase3:rule-evaluation-result.schema.json#/properties/governing` |
| `DetectionResultResponse.matched_rules` | `phase3:detection-result.schema.json#/properties/matched_rules` |
| `DetectionResultResponse.explanation` | `phase3:detection-result.schema.json#/properties/explanation` |
| `DetectionResultResponse.recommended_actions` | `phase3:detection-result.schema.json#/properties/recommended_actions` |
| `DetectionResultResponse.limitations` | `phase3:detection-result.schema.json#/properties/limitations` |
| `DetectionResultResponse.unknowns` | `phase3:detection-result.schema.json#/properties/unknowns` |
| `DetectionResultResponse.ambiguities` | `phase3:detection-result.schema.json#/properties/ambiguities` |
| `DetectionResultResponse.rule_results` | `phase3:detection-result.schema.json#/properties/rule_results` |
| `DetectionResultResponse.provenance` | `phase3:detection-result.schema.json#/properties/provenance` |
| `DetectionResultResponse.not_an_official_determination` | `api:DISCLAIMER` |
| `DetectionResultResponse.absence_of_finding_notice` | `api:INTERPRETATION_NOTICE` |
| `RuleReference.rule_id` | `phase3:rule-evaluation-result.schema.json#/properties/rule_id` |
| `RuleReference.rule_version` | `phase3:rule-evaluation-result.schema.json#/properties/rule_version` |
| `RuleReference.source_references` | `phase3:rule-evaluation-result.schema.json#/properties/source_references` |
| `ExplanationView.summary` | `phase3:detection-result.schema.json#/$defs/explanation/properties/summary` |
| `ExplanationView.evidence_basis` | `phase3:detection-result.schema.json#/$defs/explanation/properties/evidence_basis` |
| `RecommendedActionView.action_code` | `phase3:detection-result.schema.json#/$defs/recommendedAction/properties/action_code` |
| `RuleResultView.rule_id` | `phase3:rule-evaluation-result.schema.json#/properties/rule_id` |
| `RuleResultView.rule_version` | `phase3:rule-evaluation-result.schema.json#/properties/rule_version` |
| `RuleResultView.kind` | `phase3:rule-evaluation-result.schema.json#/properties/kind` |
| `RuleResultView.evaluation_state` | `phase3:rule-evaluation-result.schema.json#/properties/evaluation_state` |
| `RuleResultView.governing` | `phase3:rule-evaluation-result.schema.json#/properties/governing` |
| `RuleResultView.effective_severity` | `phase3:rule-evaluation-result.schema.json#/properties/effective_severity` |
| `RuleResultView.rule_evidence_strength` | `phase3:rule-evaluation-result.schema.json#/properties/rule_evidence_strength` |
| `RuleResultView.rule_detection_confidence` | `phase3:rule-evaluation-result.schema.json#/properties/rule_detection_confidence` |
| `ProvenanceSummary.engine_version` | `phase3:detection-result.schema.json#/properties/provenance/properties/engine_version` |
| `ProvenanceSummary.result_contract_version` | `phase3:detection-result.schema.json#/properties/result_contract_version` |
| `ProvenanceSummary.bundle_content_digest` | `phase3:detection-result.schema.json#/properties/provenance/properties/bundle_content_digest` |
| `ProvenanceSummary.bundle_version` | `phase3:detection-result.schema.json#/properties/provenance/properties/bundle_version` |
| `ProvenanceSummary.evaluation_profile_id` | `phase3:detection-result.schema.json#/properties/provenance/properties/evaluation_profile/properties/profile_id` |
| `ProvenanceSummary.evaluation_timestamp` | `phase3:detection-result.schema.json#/properties/evaluation_timestamp` |

Every governed result property keeps the catalog's AC-24 trace. The reserved but never-emitted Phase-3
`recommendedAction.priority` is not exposed, and any trace to it is rejected (OA-21). `NO_SCAM_PATTERN` is described as
"no governed pattern matched", never as safe; `UNSUPPORTED` is never safe.

## 15. Matrix J — P6-WP3 LOW/INFO carryovers

| Carryover | Disposition in P6-WP4 | Owner |
|---|---|---|
| LOW idempotency persistence | **OPEN / NON-BLOCKING** — header encoded; durable record not solved; no retention invented | Additive DATA-001-WP2 revision + P6-WP6 |
| LOW ETag ABA risk | **API-design part CLOSED** by Decision B (§8); **implementation blocked** on an additive WP2 monotonic revision | Additive DATA-001-WP2 revision + P6-WP6 |
| INFO-1 `artifact_kind OTHER` for user context | Unchanged; encoded as in the catalog | Later WP2 vocabulary revision |
| INFO-2 audit-read event type | Unchanged (`PENDING_TAXONOMY_P6_WP6` carried) | P6-WP6 |
| INFO-3 numeric limits | Unchanged — no `maximum`/`default`/size/rate/duration/retention numbers in OpenAPI | P6-WP4 implementation / P6-WP6 / Sponsor |
| INFO-4 break-glass existence signal | Unchanged; administrator-only operation | — |
| INFO-5 reserved-not-emitted Phase-3 fields | OA-21 rejects traces to the reserved priority; future reserved fields need the same update | Owner of that Phase-3 change |
| User data export / browser CSRF (API-001 §41) | Not resolved here — browser/UX/runtime policy, not OpenAPI representation | P6-WP4 implementation / Phase 7 |

## 16. Open decisions and owners

| # | Decision | Owner |
|---:|---|---|
| 1 | Additive DATA-001-WP2 revision: monotonic resource revision (ETag) + durable API idempotency record | DATA-001-WP2 revision + P6-WP6 |
| 2 | Official OpenAPI conformance validation (would require pinning a validator dependency) | Future CI decision |
| 3 | Numeric limits (page size, upload size, rate thresholds, idempotency retention, break-glass duration) | P6-WP6 / Sponsor |
| 4 | Cookie-session/CSRF variant for the Phase-7 browser client | Phase 7 |
| 5 | User data export operation (FR-065) | Phase 7 / later API revision |
| 6 | Enrichment endpoint activation and SSRF-TOCTOU controls (WP4 LOW-3) | P6-WP5 / ADR-0012 |
| 7 | Confirm single tenancy (ASM-002) before tenancy-sensitive implementation | Sponsor / Programme |

## 17. Builder self-challenge

| Challenge | Answer |
|---|---|
| Are all 53 API-001 operations present exactly once? | Yes (OA-03). |
| Are there any extra OpenAPI operations? | No (OA-03; NEG-OA-02). |
| Can OpenAPI mutate DetectionResult? | No (OA-20; NEG-OA-08; CI self-test). |
| Can EvaluationCreate submit classification? | No (OA-29; NEG-OA-20). |
| Can adjudication submit actor_id? | No (OA-29; NEG-OA-21). |
| Can ANALYST create break-glass? | No (OA-25; NEG-OA-15). |
| Can a dual-role actor bypass `ASSIGNEE_NOT_CALLER`? | No; the constraint is caller-based (OA-26; NEG-OA-16). |
| Can an assigned analyst without content permission see C4 rationale? | No (`CONTENT_PERMISSION`, OA-27; NEG-OA-17). |
| Can an administrator download evidence by role alone? | No (OA-08/OA-09; NEG-OA-06, NEG-OA-07). |
| Can knowledge activate without content_digest, or latest? | No (OA-22/OA-23; NEG-OA-13, NEG-OA-14, NEG-OA-34). |
| Can replay request latest rules or AI re-extraction? | No (OA-28; NEG-OA-18, NEG-OA-19, NEG-OA-44). |
| Can OpenAPI expose priority, scam_probability or a score? | No (OA-19/OA-21; NEG-OA-09, NEG-OA-10). |
| Can tenant_id, a URL-fetch endpoint or an external `$ref` appear? | No (OA-18, OA-24, OA-17; NEG-OA-11, NEG-OA-12, NEG-OA-25). |
| Can a dangling local `$ref` survive? | No (OA-17; NEG-OA-24). |
| Are idempotency-required POSTs missing `Idempotency-Key`? | No (OA-10; NEG-OA-22). |
| Can an If-Match-protected mutation omit If-Match? | No (OA-14; NEG-OA-28). |
| Does the ETag strategy prevent ABA? | Yes by rule (server-authoritative monotonic revision); implementation needs the additive WP2 revision (§8). |
| Is the persistence dependency explicitly recorded? | Yes (`x-trustlens-etag-strategy`, §8, §16). |
| Does any schema expose persistence rows directly? | No; DTOs are API views. |
| Does any request allow mass assignment? | No (`additionalProperties: false`, forbidden fields; OA-29). |
| Does the OpenAPI version equal ENGINE_VERSION? | No (`api-v1/contract-0.1.0`; OA-35; NEG-OA-36). |
| Has FastAPI been implemented? | No; OA-35 rejects a framework dependency. |
| Has ADR-0012 been issued? | No. |

### 17.1 Known weaknesses (not hidden)

- **Structural, not certified:** without a pinned official OpenAPI validator, some OpenAPI-specific rules (for example
  every Parameter Object field combination) are not exhaustively checked. Parity, references and component schemas are.
- **Broad media type for evidence bytes:** the upload body is `*/*` because the accepted media types are configuration;
  enforcement is server-side (`415`).
- **ETag needs persistence:** the rule is fixed, but it cannot be implemented on the current WP2 schema for cases and
  review items.
- **Single bearer scheme:** a cookie-session variant (CSRF) is deferred to Phase 7.

## 18. Acceptance boundary and non-claims

OAS-001 v0.1 and `openapi-v1.json` are the **P6-WP4 OpenAPI contract, APPROVED following independent review**; remote CI
and merge to `main` are pending, so P6-WP4 is not formally closed. No ADR is issued
(ADR-0012 remains **Planned**); API-001, GATE-021, DATA-001, DATA-001-WP2, ADR-0011 and the ADR index are unchanged.
WP4 LOW-3 remains **OPEN / DEFERRED → P6-WP5 / ADR-0012**; ASM-002 remains UNCONFIRMED / PROVISIONAL; G-09 and OI-05
remain OPEN; `ENGINE_VERSION = 1.0.0`. No implementation, deployment, OpenAPI certification, runtime-authorization test,
penetration test, load test, production readiness, legal compliance, legal admissibility or detection-efficacy claim is
made.

## 19. Independent review and acceptance

Independent P6-WP4 review: **BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 2 / INFO 4 — FINAL RECOMMENDATION: APPROVE.**
Reviewer canonical validation: `run_all` PASS 26/26; `run_all --json` `gate=PASS`, `validators_run=26`,
`validators_failed=0`; `ci_selftest` PASS 11/11; `ENGINE_VERSION = 1.0.0`.

| Finding | Severity | Disposition | Owner |
|---|---|---|---|
| Durable idempotency persistence not solved by OpenAPI | LOW | **OPEN / NON-BLOCKING** — DOES_NOT_BLOCK_P6_WP4_CONTRACT. Future record needs idempotency key, scope, request fingerprint, execution state, prior resource/outcome, and retention/deletion treatment; no retention invented | Additive DATA-001-WP2 revision + P6-WP6 |
| ETag persistence | LOW | **API-design ABA question CLOSED** by Decision B (opaque strong validator from a server-authoritative monotonic mutation revision). Current WP2 persistence is insufficient for all mutable resources: DOES_NOT_BLOCK_P6_WP4_CONTRACT_BUT_REQUIRES_PERSISTENCE_REVISION_BEFORE_IMPLEMENTATION; no field created here | Additive DATA-001-WP2 revision + P6-WP6 |
| INFO-1 no official OpenAPI validator pinned | INFO | Assurance is deterministic structural validation + catalog parity; no official certification claimed | Future CI decision |
| INFO-2 `GET /review-queue` returns `ETag`, but a collection ETag source is not defined under the single-resource revision model | INFO | Carried unchanged | Future OAS/API implementation refinement |
| INFO-3 `RecommendedActionView.action_code` is a string, not a Phase-3 enum | INFO | Matches accepted API-001/catalog semantics; unchanged | Future catalog/API revision |
| INFO-4 carried WP3 informational items | INFO | `artifact_kind OTHER`; audit-read event type; break-glass existence signal; reserved-field deny-set maintenance — all carried with their existing owners | As recorded in API-001 §44 / GATE-021 §7b |

Preserved: ADR-0012 Planned / not issued; WP4 LOW-3 OPEN / DEFERRED → P6-WP5 / ADR-0012; ASM-002 UNCONFIRMED /
PROVISIONAL; G-09 OPEN; OI-05 OPEN; `ENGINE_VERSION = 1.0.0`.

## 20. P6-WP6 ADDITIVE ACTIVATION (reviewed by GATE-024)

GATE-022 did not review this delta; [GATE-024](../00-program/GATE-024-phase-6-operational-contract.md) owns it.
`openapi-v1.json` remains in exact parity with `api-v1.json` (53 operations; OA-01…OA-36 PASS unmodified):

- `listEvaluationEnrichments`: `x-trustlens-availability: FUTURE_INT_001` removed; summary/description updated to the
  advisory, provider-assertion wording; method, path, operationId, security, roles and responses unchanged.
- `listAuditEvents`: `x-trustlens-audit.event` = `AUDIT_LOG_ACCESSED`.
- `Enum_audit_event_type` / `Enum_audit_target_kind` regenerated from the revised persistence vocabularies.
- `x-trustlens-etag-strategy`: Decision B unchanged; `implementation_dependency` now records that the P6-WP6 additive
  DATA-001-WP2 revision supplies the monotonic `mutation_revision` (runtime pending Phase 9). This satisfies the §8
  dependency at contract level; the WP3/WP4 ETag and idempotency persistence LOWs are CONTRACT-LEVEL CLOSED (OPS-001).
