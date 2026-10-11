# UX-004 — Evidence review and security UX

| Field | Value |
| --- | --- |
| Document ID | UX-004 |
| Version | 0.1 |
| Status | P7-WP4 EVIDENCE REVIEW AND SECURITY UX APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING |
| Phase / work package | Phase 7 — UX, Evidence & Reporting Design / P7-WP4 |
| Owner role | Product / Security UX |
| Branch | phase7-wp4-evidence-review |
| Baseline | e58dac6bff63a8cb79512338919af6d15db958c1 (P7-WP3 closure merge, PR #38) |
| Machine contract | [`ux-review-v1.json`](../../contracts/ux/ux-review-v1.json) with [`ux-review-contract.schema.json`](../../contracts/ux/ux-review-contract.schema.json) |
| Validation | `knowledge/validation/validate_ux_review.py`; `contracts/ux/fixtures/review-negative-mutations.json` |
| Gate | [GATE-029](../00-program/GATE-029-phase-7-evidence-review-security.md) |
| Foundation | [UX-001](UX-001-experience-foundation-information-architecture.md) / GATE-026; consumes [UX-002](UX-002-submission-evidence-intake.md) / GATE-027 and [UX-003](UX-003-result-presentation.md) / GATE-028 (closed, not modified) |
| Last updated | 2026-10-11 |

## 1. Authority and scope

UX-004 is the P7-WP4 UX design and contract for evidence review and security, approved following independent review. It designs how people see
evidence content, how content permission is shown and withdrawn, how analysts work the review queue, how administrators
assign reviews and use break-glass, how human adjudication is recorded and shown beside the immutable `DetectionResult`,
how the C4 adjudication rationale is protected, and what audit shows. It is a design and contract package only: there is
no frontend, API or runtime implementation, and nothing here is a production-readiness, usability-testing,
accessibility-conformance or security-testing claim.

Scope equals the UX-001 P7-WP4 handoff: Evidence review, Content permission, Review queue, Assignment, Break-glass,
Adjudication, C4 rationale and Audit access. The machine contract is authoritative; the tables below are exact
projections checked by `validate_ux_review.py`.

Authority is not redefined here. The backend decides every access through role, resource authorization and the separate
content permission (API-001 §3–§4, §15–§16, §23, §25). The UX may hide or show controls only from authorized metadata the
backend already returned; a hidden control is never a security control and no client-side check replaces the backend.
No new API operation, persisted field, permission grant, role or retention rule is introduced.

## 2. Surfaces and operations

Seven UX-001 surfaces carry the work package. Every operation below equals the accepted API catalog exactly (method,
path, roles, resource authorization, content permission, break-glass roles, sensitivity, audit, concurrency and caller
constraints). `getCase`, `getDetectionResult` and `getMe` are consumed, not owned: `getCase` supplies
`viewer_access.relationship` and `viewer_access.can_view_evidence_content`, `getDetectionResult` supplies the
`result_digest` of the exact result being adjudicated, and `getMe` supplies roles for navigation only.

<!-- UXV:operations:BEGIN -->
| Operation | Surface | Method | Path | Roles | Resource authorization | Content permission | Break-glass roles | Sensitivity | Audit event | Concurrency | Caller constraints |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| getEvidenceContent | UX-EVIDENCE-CONTENT | GET | /api/v1/evidence/{evidence_id}/content | USER, ANALYST | CASE_EVIDENCE_CONTENT | EVIDENCE_CONTENT | ADMINISTRATOR | C3 | EVIDENCE_ACCESSED | NONE | — |
| listCaseAccessGrants | UX-ACCESS-GRANTS | GET | /api/v1/cases/{case_id}/access-grants | USER, ADMINISTRATOR | CASE_OWNER_OR_PLATFORM_ADMIN | NONE | — | C5 | — | NONE | — |
| revokeCaseAccessGrant | UX-ACCESS-GRANTS | POST | /api/v1/access-grants/{grant_id}/revoke | ADMINISTRATOR | PLATFORM_ADMIN | NONE | — | C5 | CASE_ACCESS_REVOKED | NONE | — |
| listReviewQueue | UX-REVIEW-QUEUE | GET | /api/v1/review-queue | ANALYST | REVIEW_QUEUE | NONE | — | C2 | — | NONE | — |
| assignReview | UX-ASSIGNMENT | POST | /api/v1/review-queue/{review_item_id}/assignment | ADMINISTRATOR | PLATFORM_ADMIN | NONE | — | C2 | CASE_ACCESS_GRANTED | IF_MATCH_REQUIRED | ASSIGNEE_NOT_CALLER |
| createBreakGlassGrant | UX-BREAK-GLASS | POST | /api/v1/break-glass-grants | ADMINISTRATOR | BREAK_GLASS_SELF | NONE | — | C5 | BREAK_GLASS_ACTIVATED | NONE | — |
| getBreakGlassGrant | UX-BREAK-GLASS | GET | /api/v1/break-glass-grants/{break_glass_grant_id} | ADMINISTRATOR | BREAK_GLASS_GRANTEE_OR_PLATFORM_ADMIN | NONE | — | C5 | — | NONE | — |
| endBreakGlassGrant | UX-BREAK-GLASS | POST | /api/v1/break-glass-grants/{break_glass_grant_id}/end | ADMINISTRATOR | BREAK_GLASS_GRANTEE | NONE | — | C5 | BREAK_GLASS_EXPIRED | NONE | — |
| reviewBreakGlassGrant | UX-BREAK-GLASS | POST | /api/v1/break-glass-grants/{break_glass_grant_id}/review | ADMINISTRATOR | BREAK_GLASS_REVIEWER | NONE | — | C5 | BREAK_GLASS_REVIEWED | NONE | REVIEWER_NOT_GRANTEE |
| listAdjudications | UX-ADJUDICATION | GET | /api/v1/evaluations/{evaluation_id}/adjudications | USER, ANALYST | CASE_ACCESS | NONE | — | C4 | EVIDENCE_ACCESSED | NONE | — |
| getAdjudication | UX-ADJUDICATION | GET | /api/v1/adjudications/{adjudication_id} | USER, ANALYST | CASE_ACCESS | NONE | — | C4 | EVIDENCE_ACCESSED | NONE | — |
| createAdjudication | UX-ADJUDICATION | POST | /api/v1/evaluations/{evaluation_id}/adjudications | ANALYST | CASE_ASSIGNED_ANALYST | DERIVED_CONTENT | — | C4 | ANALYST_ADJUDICATION | NONE | — |
| listAuditEvents | UX-AUDIT | GET | /api/v1/audit-events | ADMINISTRATOR | AUDIT_READ | NONE | — | C6 | AUDIT_LOG_ACCESSED | NONE | — |
<!-- UXV:operations:END -->

## 3. Presentation states and recovery

Each accepted error maps to a UX-001 presentation state that already lists that error, with recovery consistent with
the API's retryability. A refused content download is shown as CONTENT_PERMISSION_REQUIRED only when `getCase` has already
shown a visible case without content permission; otherwise it is ACCESS_DENIED. `EVALUATION_NOT_COMPLETED` on adjudication
is resolved from the authoritative Evaluation state exactly as UX-001 defines, never inferred from the code alone. No
error state shows content or implies anything about the material.

<!-- UXV:errors:BEGIN -->
| API error | HTTP | Retryability | Presentation state | Recovery | Alternate state |
| --- | --- | --- | --- | --- | --- |
| CONFLICT | 409 | NOT_RETRYABLE | CONFLICT | STOP_NO_RETRY | — |
| DEPENDENCY_UNAVAILABLE | 503 | RETRYABLE | TEMPORARILY_UNAVAILABLE | WAIT_THEN_RETRY_SAME_REQUEST | — |
| EVALUATION_NOT_COMPLETED | 409 | RETRYABLE | CONDITIONAL_ON_EVALUATION_STATE | REFRESH_EVALUATION_STATUS | — |
| FORBIDDEN | 403 | NOT_RETRYABLE | ACCESS_DENIED | STOP_NO_RETRY | CONTENT_PERMISSION_REQUIRED |
| IDEMPOTENCY_IN_PROGRESS | 409 | RETRYABLE | ACTION_PENDING | WAIT_FOR_PENDING_COMMAND | — |
| IDEMPOTENCY_KEY_REUSED | 409 | RETRY_WITH_CHANGES | CONFLICT | REVIEW_THEN_NEW_COMMAND | — |
| INTEGRITY_FAILURE | 500 | NOT_RETRYABLE | INTEGRITY_ERROR | STOP_NO_RETRY | — |
| INTERNAL_ERROR | 500 | RETRYABLE | SERVER_ERROR | RETRY_SAME_REQUEST | — |
| INVALID_REQUEST | 400 | RETRY_WITH_CHANGES | ACTION_FAILED | CORRECT_REQUEST | — |
| NOT_FOUND | 404 | NOT_RETRYABLE | NOT_FOUND_OR_NOT_VISIBLE | STOP_NO_RETRY | — |
| PRECONDITION_FAILED | 412 | RETRY_WITH_CHANGES | STALE_STATE | REFRESH_THEN_DECIDE | — |
| PRECONDITION_REQUIRED | 428 | RETRY_WITH_CHANGES | PRECONDITION_REQUIRED | REFRESH_THEN_DECIDE | — |
| RATE_LIMITED | 429 | RETRYABLE | RATE_LIMITED | WAIT_THEN_RETRY_SAME_REQUEST | — |
| REMOVED_UNDER_GOVERNANCE | 410 | NOT_RETRYABLE | REMOVED_UNDER_GOVERNANCE | STOP_NO_RETRY | — |
| STATE_CONFLICT | 409 | NOT_RETRYABLE | CONFLICT | STOP_NO_RETRY | — |
| UNAUTHENTICATED | 401 | RETRY_WITH_CHANGES | AUTHENTICATION_REQUIRED | REAUTHENTICATE_THEN_RETRY | — |
<!-- UXV:errors:END -->

## 4. Evidence content and content permission

Case metadata never implies content. Before any content control, the surface reads `getCase` and uses only
`viewer_access` to decide what to offer: the owner and an assigned analyst whose grant permits evidence content see an
explicit download control; an assigned analyst without content permission sees CONTENT_PERMISSION_REQUIRED and no request
is made; a person without case visibility is not told whether the case exists. Knowledge roles have no evidence surface.
Administrators never reach content by role: only the caller's own active, scoped break-glass grant covering the item
opens the same download path, and the backend decides coverage. Another administrator never inherits a grant.

Content is delivered only as the accepted attachment download (`EvidenceContentDownload`: server-generated filename,
server-verified media type, `Cache-Control: no-store`). There is no inline viewer, preview, thumbnail or client cache, and
content never appears in notifications. Before the download the surface states that downloading the original evidence is
recorded in the audit log (`EVIDENCE_ACCESSED`).

<!-- UXV:content_matrix:BEGIN -->
| Role | Case relationship | Content permission | Evidence content |
| --- | --- | --- | --- |
| USER | OWNER | yes | DOWNLOAD_OFFERED |
| USER | NONE | no | NOT_VISIBLE |
| ANALYST | ASSIGNED_ANALYST | yes | DOWNLOAD_OFFERED |
| ANALYST | ASSIGNED_ANALYST | no | CONTENT_PERMISSION_REQUIRED |
| ANALYST | NONE | no | NOT_VISIBLE |
| KNOWLEDGE_EDITOR | NONE | no | NOT_OFFERED |
| KNOWLEDGE_APPROVER | NONE | no | NOT_OFFERED |
| ADMINISTRATOR | NONE | no | BREAK_GLASS_ONLY |
| ADMINISTRATOR | BREAK_GLASS | yes | DOWNLOAD_OFFERED |
<!-- UXV:content_matrix:END -->

## 5. Case access grants

The owner can list who can access the case and an administrator can revoke a grant with a reason
(`listCaseAccessGrants`, `revokeCaseAccessGrant`). The list is content-free metadata: grant kind, whether case metadata and
evidence content are permitted, effective and revocation times. Principals appear as opaque identifiers because no
display-name capability exists. Seeing a grant entry never grants access to the parent case.

## 6. Review queue

The queue (`listReviewQueue`) is ANALYST-only and content-free: review item, evaluation and case identifiers, state,
routing basis, assignee and queued time, with the API's filters, sort and cursor pagination. The ETag is used for
assignment preconditions but not displayed. A queue entry grants nothing: opening it goes through `getCase` and normal
authorization. The queue shows no evidence content, rationale, result axes or aggregate counters, and its deployment-wide
scope stays provisional under ASM-002.

<!-- UXV:labels:BEGIN -->
| Vocabulary | Value | Label | Meaning |
| --- | --- | --- | --- |
| api_review_state | NOT_ROUTED | Not routed | Not in human review. |
| api_review_state | QUEUED | Waiting for review | Routed for human review and not yet in review. |
| api_review_state | IN_REVIEW | In review | An assigned analyst is reviewing this evaluation. |
| api_review_state | ADJUDICATED | Adjudicated | A human adjudication has been recorded; the system result is unchanged. |
| api_review_state | WITHDRAWN | Withdrawn | No longer in human review. |
| review_routing_basis | INSUFFICIENT_EVIDENCE | Not enough evidence | The result had insufficient basis for a governed pattern. |
| review_routing_basis | UNSUPPORTED | Not supported | The input could not be evaluated. |
| review_routing_basis | ERROR | Evaluation error | The evaluation reported an error. |
| review_routing_basis | DEGRADED | Degraded evaluation | The evaluation ran with reduced capability. |
| review_routing_basis | INDETERMINATE_RULE | Indeterminate rule | At least one governed rule could not be decided. |
| review_routing_basis | SEEK_HUMAN_REVIEW_ACTION | Human review recommended | The governed action policy recommends human review. |
| adjudication_outcome | AGREES_WITH_RESULT | Analyst agrees with the system result | A human reviewer agreed with this exact result. The result itself is unchanged. |
| adjudication_outcome | DISAGREES_WITH_RESULT | Analyst disagrees with the system result | A human reviewer disagreed with this exact result. The result itself is unchanged. |
| adjudication_outcome | UNABLE_TO_ADJUDICATE | Analyst could not adjudicate | A human reviewer could not reach a view on this exact result. |
<!-- UXV:labels:END -->

## 7. Assignment

`assignReview` is an ADMINISTRATOR command. The assignee must differ from the caller (`ASSIGNEE_NOT_CALLER`), including a
principal holding both ADMINISTRATOR and ANALYST, and analysts have no assignment command. The administrator must make an
explicit content-permission choice with no pre-selected default and sees its consequence; a reason code is required. The
command sends `If-Match` with the review item's ETag; a stale ETag shows STALE_STATE and the current state, and nothing is
overwritten silently. Retries reuse the same idempotency key without exposing it. The administrator gains no content.

No accepted API lets an administrator read the queue or search principals, so the design cannot discover an assignment
target, its ETag or the analyst identifier. The command acts only on values supplied through an accepted channel; this
gap is an owned deferred decision carried from UX-001 (§14).

## 8. Break-glass

Break-glass is a separate, explicit administrator entry, never a toggle or flag on another request, and an analyst cannot
create it. The administrator chooses the scope (`CASE_EVIDENCE` or one `EVIDENCE_ITEM`, which requires the evidence
identifier) and enters a reason that must not contain evidence content. Before activation the surface states the scope,
that the reason is recorded, that the access is temporary, audited and signalled, and that a different administrator
must review it afterwards.

A grant is caller-bound. Content is reachable only when the caller is the grantee, the grant is active, the case is in
scope and, for an `EVIDENCE_ITEM` grant, the exact item is in scope; a different administrator, a dual-role principal
without its own grant, an ended or expired grant, another case or another item gives no content and no request.

The duration is set by the server and is NOT YET SPECIFIED; the surface shows only the server's `expires_at` and invents
no countdown. While a grant is active a persistent indicator shows its scope, start and expiry with an action to end it
early (`endBreakGlassGrant`, grantee only). Break-glass gives no standing privilege, no silent elevation, and no access to
adjudication rationale or result detail. Review (`reviewBreakGlassGrant`) is by a different administrator
(`REVIEWER_NOT_GRANTEE`), records an outcome, and any note must not contain evidence content. With no grant-listing
operation, reviewers find grants from `BREAK_GLASS_ACTIVATED` audit events and then read the grant.

## 9. Human adjudication

An adjudication is a separate, append-only human record about one exact result. It never edits, replaces or merges with
the `DetectionResult` and never changes its classification. It is shown beside the result with its own provenance
(HUMAN_ADJUDICATION), and supersession is shown as a relationship, never an edit. An assigned analyst records it with the
`result_digest` of the exact result being viewed, an outcome and a rationale; actor and time come from the server. A digest
mismatch is shown as CONFLICT and the person re-reads the result before deciding again.

## 10. C4 rationale

The rationale may quote evidence, so it is C4. It is shown only to an assigned analyst whose grant permits evidence
content; assignment alone is not enough. The owner sees outcome and time only. Administrators and knowledge roles never
see it by role, and break-glass does not reveal it. For everyone else the surface shows the same restricted text, so the
absence of a rationale is never presented as an empty one. Reads that include it are audited (`EVIDENCE_ACCESSED`), and
it never appears in the queue, audit views or notifications. When writing one, the analyst is told that it may quote
evidence and who can read it.

<!-- UXV:rationale_matrix:BEGIN -->
| Role | Case relationship | Content permission | Outcome visible | C4 rationale visible |
| --- | --- | --- | --- | --- |
| USER | OWNER | yes | yes | no |
| ANALYST | ASSIGNED_ANALYST | yes | yes | yes |
| ANALYST | ASSIGNED_ANALYST | no | yes | no |
| ANALYST | NONE | no | no | no |
| KNOWLEDGE_EDITOR | NONE | no | no | no |
| KNOWLEDGE_APPROVER | NONE | no | no | no |
| ADMINISTRATOR | NONE | no | no | no |
| ADMINISTRATOR | BREAK_GLASS | yes | no | no |
<!-- UXV:rationale_matrix:END -->

## 11. Audit visibility and access consequences

Audit (`listAuditEvents`) is ADMINISTRATOR-only and content-free: the accepted `AuditEventView` metadata with the API's
filters and chain ordering. Reading the audit log is itself audited (`AUDIT_LOG_ACCESSED`) and the surface says so first.
Audit is not an activity feed, users and analysts have no audit view, and integrity fields are metadata, not a verdict.
Every action whose operation requires audit tells the person beforehand that it is recorded; operations without an audit
requirement make no such statement.

<!-- UXV:consequences:BEGIN -->
| Operation | Audit | Audit event | Audit notice shown |
| --- | --- | --- | --- |
| getEvidenceContent | REQUIRED | EVIDENCE_ACCESSED | yes |
| listCaseAccessGrants | NOT_REQUIRED | — | no |
| revokeCaseAccessGrant | REQUIRED | CASE_ACCESS_REVOKED | yes |
| listReviewQueue | NOT_REQUIRED | — | no |
| assignReview | REQUIRED | CASE_ACCESS_GRANTED | yes |
| createBreakGlassGrant | REQUIRED | BREAK_GLASS_ACTIVATED | yes |
| getBreakGlassGrant | NOT_REQUIRED | — | no |
| endBreakGlassGrant | REQUIRED | BREAK_GLASS_EXPIRED | yes |
| reviewBreakGlassGrant | REQUIRED | BREAK_GLASS_REVIEWED | yes |
| listAdjudications | REQUIRED | EVIDENCE_ACCESSED | yes |
| getAdjudication | REQUIRED | EVIDENCE_ACCESSED | yes |
| createAdjudication | REQUIRED | ANALYST_ADJUDICATION | yes |
| listAuditEvents | REQUIRED | AUDIT_LOG_ACCESSED | yes |
<!-- UXV:consequences:END -->

## 12. Security scenarios

The scenarios pin what the UX offers and presents for each action and context. `validate_ux_review.py` re-derives every
row with an independent decision procedure built from the API's roles, break-glass roles, resource authorization, caller
constraints, audit and field visibility, and checks them against the matrices above.

<!-- UXV:scenarios:BEGIN -->
| Scenario | Situation | Action | Role / relationship / content | Control offered | Request | Presented as | Content | Rationale | Audit notice |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RV-01 | Owner downloads own evidence | DOWNLOAD_EVIDENCE | USER / OWNER / yes | yes | yes | READY | ATTACHMENT | no | yes |
| RV-02 | Assigned analyst with content permission downloads evidence | DOWNLOAD_EVIDENCE | ANALYST / ASSIGNED_ANALYST / yes | yes | yes | READY | ATTACHMENT | no | yes |
| RV-03 | Assigned analyst without content permission | DOWNLOAD_EVIDENCE | ANALYST / ASSIGNED_ANALYST / no | no | no | CONTENT_PERMISSION_REQUIRED | NONE | no | no |
| RV-04 | Analyst without case visibility | DOWNLOAD_EVIDENCE | ANALYST / NONE / no | no | no | NOT_FOUND_OR_NOT_VISIBLE | NONE | no | no |
| RV-05 | Administrator without break-glass | DOWNLOAD_EVIDENCE | ADMINISTRATOR / NONE / no | no | no | ACCESS_DENIED | NONE | no | no |
| RV-06 | Administrator with an active break-glass grant covering the item | DOWNLOAD_EVIDENCE | ADMINISTRATOR / BREAK_GLASS / yes | yes | yes | READY | ATTACHMENT | no | yes |
| RV-07 | Grantee's evidence-item grant covers a different evidence item | DOWNLOAD_EVIDENCE | ADMINISTRATOR / BREAK_GLASS / yes | no | no | ACCESS_DENIED | NONE | no | no |
| RV-08 | Knowledge editor | DOWNLOAD_EVIDENCE | KNOWLEDGE_EDITOR / NONE / no | no | no | ACCESS_DENIED | NONE | no | no |
| RV-09 | Owner reads adjudications: outcome only | READ_ADJUDICATION | USER / OWNER / yes | yes | yes | READY | NONE | no | yes |
| RV-10 | Assigned analyst with content permission reads the rationale | READ_ADJUDICATION | ANALYST / ASSIGNED_ANALYST / yes | yes | yes | READY | NONE | yes | yes |
| RV-11 | Assigned analyst without content permission: outcome only | READ_ADJUDICATION | ANALYST / ASSIGNED_ANALYST / no | yes | yes | READY | NONE | no | yes |
| RV-12 | Administrator with break-glass cannot read adjudications | READ_ADJUDICATION | ADMINISTRATOR / BREAK_GLASS / yes | no | no | ACCESS_DENIED | NONE | no | no |
| RV-13 | Assigned analyst records an adjudication | CREATE_ADJUDICATION | ANALYST / ASSIGNED_ANALYST / no | yes | yes | READY | NONE | no | yes |
| RV-14 | Owner cannot adjudicate | CREATE_ADJUDICATION | USER / OWNER / yes | no | no | ACCESS_DENIED | NONE | no | no |
| RV-15 | Analyst opens the review queue | VIEW_QUEUE | ANALYST / NONE / no | yes | yes | READY | NONE | no | no |
| RV-16 | Administrator has no queue read | VIEW_QUEUE | ADMINISTRATOR / NONE / no | no | no | ACCESS_DENIED | NONE | no | no |
| RV-17 | Administrator assigns another analyst | ASSIGN_REVIEW | ADMINISTRATOR / NONE / no | yes | yes | READY | NONE | no | yes |
| RV-18 | Administrator holding ANALYST cannot assign self | ASSIGN_REVIEW | ADMINISTRATOR / NONE / no | no | no | ACCESS_DENIED | NONE | no | no |
| RV-19 | Analyst has no assignment command | ASSIGN_REVIEW | ANALYST / NONE / no | no | no | ACCESS_DENIED | NONE | no | no |
| RV-20 | Administrator activates break-glass | CREATE_BREAK_GLASS | ADMINISTRATOR / NONE / no | yes | yes | READY | NONE | no | yes |
| RV-21 | Analyst cannot create break-glass | CREATE_BREAK_GLASS | ANALYST / ASSIGNED_ANALYST / no | no | no | ACCESS_DENIED | NONE | no | no |
| RV-22 | Grantee ends break-glass early | END_BREAK_GLASS | ADMINISTRATOR / BREAK_GLASS / yes | yes | yes | READY | NONE | no | yes |
| RV-23 | Different administrator cannot end another grantee's grant | END_BREAK_GLASS | ADMINISTRATOR / NONE / no | no | no | ACCESS_DENIED | NONE | no | no |
| RV-24 | Different administrator reviews the grant | REVIEW_BREAK_GLASS | ADMINISTRATOR / NONE / no | yes | yes | READY | NONE | no | yes |
| RV-25 | Grantee cannot review own grant | REVIEW_BREAK_GLASS | ADMINISTRATOR / BREAK_GLASS / yes | no | no | ACCESS_DENIED | NONE | no | no |
| RV-26 | Administrator reads the audit log | VIEW_AUDIT | ADMINISTRATOR / NONE / no | yes | yes | READY | NONE | no | yes |
| RV-27 | Analyst has no audit view | VIEW_AUDIT | ANALYST / ASSIGNED_ANALYST / yes | no | no | ACCESS_DENIED | NONE | no | no |
| RV-28 | Owner lists who can access the case | LIST_GRANTS | USER / OWNER / yes | yes | yes | READY | NONE | no | no |
| RV-29 | Analyst cannot list grants | LIST_GRANTS | ANALYST / ASSIGNED_ANALYST / yes | no | no | ACCESS_DENIED | NONE | no | no |
| RV-30 | Administrator revokes a grant | REVOKE_GRANT | ADMINISTRATOR / NONE / no | yes | yes | READY | NONE | no | yes |
| RV-31 | Owner cannot revoke | REVOKE_GRANT | USER / OWNER / yes | no | no | ACCESS_DENIED | NONE | no | no |
| RV-32 | Owner without case visibility cannot read adjudications | READ_ADJUDICATION | USER / NONE / no | no | no | NOT_FOUND_OR_NOT_VISIBLE | NONE | no | no |
| RV-33 | Another administrator cannot use the grantee's active grant | DOWNLOAD_EVIDENCE | ADMINISTRATOR / NONE / no | no | no | ACCESS_DENIED | NONE | no | no |
| RV-34 | Grantee with an evidence-item grant for this item | DOWNLOAD_EVIDENCE | ADMINISTRATOR / BREAK_GLASS / yes | yes | yes | READY | ATTACHMENT | no | yes |
| RV-35 | Grantee whose grant has ended or expired | DOWNLOAD_EVIDENCE | ADMINISTRATOR / NONE / no | no | no | ACCESS_DENIED | NONE | no | no |
| RV-36 | Grantee whose grant covers a different case | DOWNLOAD_EVIDENCE | ADMINISTRATOR / NONE / no | no | no | ACCESS_DENIED | NONE | no | no |
| RV-37 | Dual-role administrator and analyst without assignment or an own grant | DOWNLOAD_EVIDENCE | ADMINISTRATOR / NONE / no | no | no | ACCESS_DENIED | NONE | no | no |
<!-- UXV:scenarios:END -->

## 13. Guardrails, exposure and protected copy

Protected display copy is a closed set of governed messages: the content-permission explanations, the audit notices, the
restricted-rationale text, the adjudication outcome labels and the accessible announcements below. Masked states never
disclose whether something exists; locked and restricted texts carry no identifiers, quoted text or content-derived
facts; adjudication wording never says the result, classification, severity, risk or matched rules changed.
Notifications never carry evidence content, rationale, break-glass reasons or review notes.

<!-- UXV:protected_text:BEGIN -->
| Protected display field | Governed text |
| --- | --- |
| content_permission.content_actions.DOWNLOAD_OFFERED | An explicit download control is offered after the audit notice; the backend still decides. |
| content_permission.content_actions.CONTENT_PERMISSION_REQUIRED | The case is visible but content permission was not granted; no download control and no request. |
| content_permission.content_actions.NOT_VISIBLE | The case is not visible to this person; existence is not disclosed. |
| content_permission.content_actions.NOT_OFFERED | This role has no evidence surface. |
| content_permission.content_actions.BREAK_GLASS_ONLY | No content by role; content is reachable only through the caller's own active, scoped break-glass grant covering the item. |
| content_permission.pre_access_notice.text | Downloading the original evidence is recorded in the audit log. |
| c4_rationale.restricted_text | The rationale is restricted to an assigned analyst with content permission. |
| c4_rationale.author_notice | This rationale may quote evidence. Only an assigned analyst with content permission can read it. |
| audit.pre_read_notice | Reading the audit log is itself recorded in the audit log. |
| adjudication.outcome_labels.AGREES_WITH_RESULT.label | Analyst agrees with the system result |
| adjudication.outcome_labels.AGREES_WITH_RESULT.meaning | A human reviewer agreed with this exact result. The result itself is unchanged. |
| adjudication.outcome_labels.DISAGREES_WITH_RESULT.label | Analyst disagrees with the system result |
| adjudication.outcome_labels.DISAGREES_WITH_RESULT.meaning | A human reviewer disagreed with this exact result. The result itself is unchanged. |
| adjudication.outcome_labels.UNABLE_TO_ADJUDICATE.label | Analyst could not adjudicate |
| adjudication.outcome_labels.UNABLE_TO_ADJUDICATE.meaning | A human reviewer could not reach a view on this exact result. |
| announcements.CONTENT_PERMISSION_REQUIRED.text | You do not have permission to view this evidence content. |
| announcements.NOT_FOUND_OR_NOT_VISIBLE.text | Nothing is available here. |
| announcements.ACCESS_DENIED.text | This action is not available to you. |
| announcements.RATIONALE_RESTRICTED.text | The rationale is restricted. |
| announcements.BREAK_GLASS_ACTIVE.text | Break-glass access is active and recorded until the time shown. |
<!-- UXV:protected_text:END -->

Each presentation state may announce only what it may show, and only from the authorized read behind it. A masked
(not found or not visible), denied or content-restricted state shows and announces no resource metadata at all, so an
inaccessible resource never reveals its existence, adjudication outcome or time. A restricted rationale keeps only the
outcome and time that case access already shows, and an active grant shows only the grantee's own grant fields.

<!-- UXV:announcements:BEGIN -->
| Presentation state | Source read | Visible fields | Announced fields |
| --- | --- | --- | --- |
| CONTENT_PERMISSION_REQUIRED | — | — | — |
| NOT_FOUND_OR_NOT_VISIBLE | — | — | — |
| ACCESS_DENIED | — | — | — |
| RATIONALE_RESTRICTED | getAdjudication | outcome, adjudicated_at | outcome, adjudicated_at |
| BREAK_GLASS_ACTIVE | getBreakGlassGrant | scope_kind, case_id, evidence_id, started_at, expires_at | scope_kind, expires_at |
<!-- UXV:announcements:END -->


No administrator content by role, no analyst self-elevation, no self-assignment or dual-role exemption, no hidden-control
or client-side authorization, no silent or standing break-glass, no adjudication edit of the result, no rationale without
permission, no inline evidence rendering, no content in the queue, and no invented operation, persisted field,
permission grant or retention rule. Raw provider bodies, secrets, connector topology, internal hosts, evidence-store
locators, fence tokens and idempotency-key material are never exposed, and audit is never presented as activity.

## 14. Open decisions

<!-- UXV:decisions:BEGIN -->
| Unresolved decision | Owner | Status |
| --- | --- | --- |
| Administrator assignment target and If-Match acquisition: no administrator queue-read or principal-directory capability exists, so the assignment command can only act on a review item reference, ETag and analyst identifier supplied through an accepted channel | API owner (governed API revision), carried from UX-001 | DEFERRED |
| A CASE_EVIDENCE break-glass grant has no accepted evidence-listing operation for administrators (listEvidence and getCase are USER/ANALYST only); evidence identifiers are reachable only from content-free audit metadata | API owner with Security Architect | DEFERRED |
| No operation lists break-glass grants awaiting review; reviewers find grants through listAuditEvents (BREAK_GLASS_ACTIVATED) and then getBreakGlassGrant | API owner with Security Architect | DEFERRED |
| reason_code on assignment and access-grant revocation has no governed vocabulary | API owner (governed vocabulary) | DEFERRED |
| Principals appear as opaque identifiers; no principal display-name capability exists for queues, grants or audit | API owner with Product / Security UX | DEFERRED |
| An assigned analyst without permits_evidence_content may author a C4 rationale that the same analyst cannot read back; confirm the intended authoring rule | API owner with Security Architect | DEFERRED |
| Break-glass duration is server-set and NOT YET SPECIFIED; the UX shows only the server's expires_at | Security Architect / P5-WP5 implementation | DEFERRED |
| Final user-facing copy, translation and plain-language review of review and security labels | Product / Security UX with Phase 9 | DEFERRED |
| Detailed accessible and responsive layout of review and security surfaces | P7-WP6 / Accessibility UX | DEFERRED |
<!-- UXV:decisions:END -->

## 15. Carryovers and claims

<!-- UXV:carryovers:BEGIN -->
| Item | Status | Owner |
| --- | --- | --- |
| G-09 | OPEN | Phase 10 (testing/evaluation; QA Lead) with Sponsor for any corpus access |
| OI-05 | OPEN | Sponsor + legal/governance |
| ASM-002 | UNCONFIRMED / PROVISIONAL | Sponsor / Programme |
| P6-WP7-LOW-1 | OPEN / NON-BLOCKING | Next governed Phase-6 snapshot revision / Programme governance |
<!-- UXV:carryovers:END -->

No tenant field or organization switcher is introduced and no numeric retention or break-glass duration is invented.
Reports, replay, re-analysis, correction and deletion workflows belong to P7-WP5, and detailed accessible and responsive
layout to P7-WP6. `ENGINE_VERSION = 1.0.0` remains unchanged.

## 16. Lifecycle and independent review

The structured lifecycle in the machine contract is authoritative and fails closed. A review round, an approval or merge
evidence counts only when it equals the record pinned in `validate_ux_review.py` by a governed bookkeeping step, so no
prose here can establish approval. Round 1 (initial independent review) returned REQUEST_CHANGES (BLOCKER 0 / HIGH 1 /
MEDIUM 3 / LOW 0 / INFO 0). Round 2 (targeted re-review) closed HIGH-1 and MEDIUM-3 and returned REQUEST_CHANGES
(BLOCKER 0 / HIGH 0 / MEDIUM 2 / LOW 0 / INFO 0). Round 3 closed MEDIUM-1 and returned REQUEST_CHANGES (BLOCKER 0 /
HIGH 0 / MEDIUM 1 / LOW 0 / INFO 0) on the security-table check. Round 4 (targeted re-review) returned APPROVE
(BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 0 / INFO 0) and closed every remaining finding. The lifecycle is APPROVED following
independent review, with remote CI and merge pending; CLOSED needs merge and remote-CI evidence pinned by the governed
post-merge step. GATE-029 §7 holds the review record.
