# UX-005 — Reporting and historical workflows

| Field | Value |
| --- | --- |
| Document ID | UX-005 |
| Version | 0.1 |
| Status | P7-WP5 REPORTING AND HISTORICAL WORKFLOWS UX CLOSED |
| Phase / work package | Phase 7 — UX, Evidence & Reporting Design / P7-WP5 |
| Owner role | Product / Reporting UX |
| Branch | phase7-wp5-reporting-workflows |
| Baseline | b5a663a6dd6343b17b7cf8dfa927c0aae4f8ebd9 (P7-WP4 closure merge, PR #40) |
| Machine contract | [`ux-reporting-v1.json`](../../contracts/ux/ux-reporting-v1.json) with [`ux-reporting-contract.schema.json`](../../contracts/ux/ux-reporting-contract.schema.json) |
| Validation | `knowledge/validation/validate_ux_reporting.py`; `contracts/ux/fixtures/reporting-negative-mutations.json` |
| Gate | [GATE-030](../00-program/GATE-030-phase-7-reporting-historical-workflows.md) |
| Foundation | [UX-001](UX-001-experience-foundation-information-architecture.md) / GATE-026; consumes UX-002, UX-003 and [UX-004](UX-004-evidence-review-security.md) (closed, not modified) |
| Last updated | 2026-10-11 |

## 1. Authority and scope

UX-005 is the P7-WP5 UX design and contract for reporting and historical workflows, approved following independent review
and CLOSED after merge (PR #41; GATE-030 §8): case-scoped reports and
their content, historical replay, re-analysis and user correction as new evaluations, governed deletion, governed
removal (410) versus not found or not visible (404), report regeneration that cannot happen, and honest history. It is a
design and contract package only: there is no frontend, API or runtime implementation, and nothing here is a
production-readiness, usability-testing, accessibility-conformance or security-testing claim.

Scope equals the UX-001 P7-WP5 handoff: Reports, Replay, Re-analysis, Governed deletion, 410 removed, Replay unavailable,
Report regeneration unavailable and Historical comparison. The machine contract is authoritative; the tables below are
exact projections checked by `validate_ux_reporting.py`. Authority is not redefined: the backend decides every access
through role, resource authorization and the separate content permission (API-001 §3, §13, §17–§20), and no API
operation, persisted field, permission grant, report format or retention rule is introduced.

History is never rewritten. A `DetectionResult` is immutable, adjudications are append-only, and every replay, report,
re-analysis, correction and deletion leaves earlier records as they were.

## 2. Surfaces and operations

Five UX-001 surfaces carry the work package, and every owned operation equals the accepted API exactly. User correction
(`createCorrection`) is an accepted operation that UX-001 placed on no surface; UX-003 deferred it here, so its placement
in the evaluation context is recorded in this contract and UX-001 is unchanged. Re-analysis reuses `createEvaluations`
(owned by UX-002 for the first evaluation) only with a predecessor evaluation and a reason. `getCase`, `getEvaluation`
and `listCaseEvaluations` are consumed, not owned.

<!-- UXP:operations:BEGIN -->
| Operation | Surface | On UX-001 surface | Method | Path | Roles | Resource authorization | Content permission | Mode | Audit event | Concurrency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| createReport | UX-REPORT-CONTENT | yes | POST | /api/v1/cases/{case_id}/reports | USER, ANALYST | CASE_DERIVED_CONTENT | DERIVED_CONTENT | ASYNC | REPORT_GENERATED | NONE |
| listReports | UX-REPORTS | yes | GET | /api/v1/cases/{case_id}/reports | USER, ANALYST | CASE_ACCESS | NONE | SYNC | — | NONE |
| getReport | UX-REPORTS | yes | GET | /api/v1/reports/{report_id} | USER, ANALYST | CASE_ACCESS | NONE | SYNC | — | NONE |
| getReportContent | UX-REPORT-CONTENT | yes | GET | /api/v1/reports/{report_id}/content | USER, ANALYST | CASE_DERIVED_CONTENT | DERIVED_CONTENT | SYNC | REPORT_EXPORTED | NONE |
| createReplay | UX-REPLAY | yes | POST | /api/v1/evaluations/{evaluation_id}/replays | ANALYST, ADMINISTRATOR | CASE_ASSIGNED_ANALYST_OR_PLATFORM_ADMIN | NONE | ASYNC | REPLAY_EXECUTED | NONE |
| getReplay | UX-REPLAY | yes | GET | /api/v1/replays/{replay_id} | ANALYST, ADMINISTRATOR | CASE_ASSIGNED_ANALYST_OR_PLATFORM_ADMIN | NONE | SYNC | — | NONE |
| createEvaluations | UX-EVALUATION | yes | POST | /api/v1/submissions/{submission_id}/evaluations | USER, ANALYST | CASE_ACCESS | NONE | ASYNC | EVALUATION_STARTED | NONE |
| createCorrection | UX-EVALUATION | no | POST | /api/v1/evaluations/{evaluation_id}/corrections | USER | CASE_OWNER | DERIVED_CONTENT | ASYNC | USER_CORRECTION | NONE |
| createDeletionRequest | UX-DELETION | yes | POST | /api/v1/deletion-requests | USER | DELETION_SCOPE_OWNER | NONE | SYNC | DELETION_REQUESTED | NONE |
| listDeletionRequests | UX-DELETION | yes | GET | /api/v1/deletion-requests | USER, ADMINISTRATOR | DELETION_SCOPE_OWNER_OR_PLATFORM_ADMIN | NONE | SYNC | — | NONE |
| getDeletionRequest | UX-DELETION | yes | GET | /api/v1/deletion-requests/{deletion_request_id} | USER, ADMINISTRATOR | DELETION_SCOPE_OWNER_OR_PLATFORM_ADMIN | NONE | SYNC | — | NONE |
| authorizeDeletionRequest | UX-DELETION | yes | POST | /api/v1/deletion-requests/{deletion_request_id}/authorize | ADMINISTRATOR | PLATFORM_ADMIN | NONE | ASYNC | RETENTION_ACTION | IF_MATCH_REQUIRED |
| rejectDeletionRequest | UX-DELETION | yes | POST | /api/v1/deletion-requests/{deletion_request_id}/reject | ADMINISTRATOR | PLATFORM_ADMIN | NONE | SYNC | RETENTION_ACTION | IF_MATCH_REQUIRED |
<!-- UXP:operations:END -->

## 3. Presentation states and recovery

Each accepted error maps to a UX-001 presentation state that already lists it, with recovery consistent with the API's
retryability. `EVALUATION_NOT_COMPLETED` is resolved from the authoritative Evaluation state, never from the code alone.
A refused report-content request is CONTENT_PERMISSION_REQUIRED only when `getCase` has already shown a visible case
without content permission.

<!-- UXP:errors:BEGIN -->
| API error | HTTP | Retryability | Presentation state | Recovery | Alternate state |
| --- | --- | --- | --- | --- | --- |
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
| REPLAY_UNAVAILABLE | 409 | NOT_RETRYABLE | REPLAY_UNAVAILABLE | STOP_NO_RETRY | — |
| REPORT_REGENERATION_UNAVAILABLE | 409 | NOT_RETRYABLE | REPORT_REGENERATION_UNAVAILABLE | STOP_NO_RETRY | — |
| STATE_CONFLICT | 409 | NOT_RETRYABLE | CONFLICT | STOP_NO_RETRY | — |
| UNAUTHENTICATED | 401 | RETRY_WITH_CHANGES | AUTHENTICATION_REQUIRED | REAUTHENTICATE_THEN_RETRY | — |
<!-- UXP:errors:END -->

## 4. Governed removal (410) and not found (404)

A resource removed through governed deletion answers `410 REMOVED_UNDER_GOVERNANCE` and is shown as REMOVED_UNDER_GOVERNANCE:
a governed-unavailability state that is never recreated and never worded as missing or unknown. An ordinary `404` stays
NOT_FOUND_OR_NOT_VISIBLE and never reveals whether a hidden resource exists. A completed evaluation can survive as a
historical tombstone (`result_availability = REMOVED_UNDER_GOVERNANCE`): result, evidence-content and report-content
requests answer 410, replay answers `409 REPLAY_UNAVAILABLE` and report regeneration ends REGENERATION_UNAVAILABLE. What
a tombstone retains is not yet specified (OI-05).

## 5. Reports

Reports are case-scoped; there is no global report listing. Creating a report makes a new revision pinned to the case,
the evaluations, their result and evidence digests, the knowledge-bundle digest, the engine version and the report
contract version; reproducing a report means reproducing exactly from those pins, never from the latest material.
Report metadata shows revision, state, contract version, digest, reproduction link, generation time and a category-only
unavailable reason; the content link itself is not displayed.

Report content needs case access and evidence-content permission (derived content). It is an attachment download only,
uncached and in a format not yet specified (REPORT-001), and the surface says first that downloading it is recorded in
the audit log. Reports are never transmitted anywhere automatically. Administrators never receive report content, and
break-glass does not apply to reports.

<!-- UXP:report_content:BEGIN -->
| Role | Case relationship | Content permission | Report content |
| --- | --- | --- | --- |
| USER | OWNER | yes | OFFERED |
| USER | NONE | no | NOT_VISIBLE |
| ANALYST | ASSIGNED_ANALYST | yes | OFFERED |
| ANALYST | ASSIGNED_ANALYST | no | CONTENT_PERMISSION_REQUIRED |
| ANALYST | NONE | no | NOT_VISIBLE |
| KNOWLEDGE_EDITOR | NONE | no | NOT_OFFERED |
| KNOWLEDGE_APPROVER | NONE | no | NOT_OFFERED |
| ADMINISTRATOR | NONE | no | NOT_OFFERED |
| ADMINISTRATOR | BREAK_GLASS | yes | NOT_OFFERED |
<!-- UXP:report_content:END -->

When a pinned source has been removed, the report state is REGENERATION_UNAVAILABLE and content retrieval answers
`409 REPORT_REGENERATION_UNAVAILABLE`. The surface says the report cannot be reproduced; nothing is approximated,
substituted from latest material, produced by AI or reconstructed from removed content.

## 6. Replay

Replay is exact historical verification of the pinned material: no AI call, no latest knowledge, no new evaluation and
no new result. An assigned analyst, or an administrator entering through an authorized reference without access to the
parent case, may request it with a reason only. The record is content-free: state, capability, outcome, missing material
kinds and digest. Missing or unverifiable material is an explicit REPLAY_UNAVAILABLE outcome, never a generic error,
and replay never falls back to re-analysis: a new analysis is offered only as a separate action that creates a new
evaluation.

## 7. Re-analysis and user correction

A new analysis (`createEvaluations` with a predecessor evaluation and a reason) creates a new evaluation and a new
governed input; the server derives its origin, and AI-assisted extraction is honoured only when enabled, with any
fallback shown from `ai_usage`. A user correction (`createCorrection`, case owner only) sends a free-text description
and a reason and creates a new USER_CORRECTION evaluation; there is no field-level editing because the accepted API
offers none, and the description is C4 and never appears in notifications or audit. In both cases the earlier
evaluation and its result stay unchanged and the new evaluation links to its predecessor.

## 8. Governed deletion

There is no delete verb. The scope owner requests deletion with a reason (REQUESTED); an administrator authorizes or
rejects it with If-Match and a reason, seeing no content, and only while it is REQUESTED (API-001 §26); a request
already authorized, rejected, in progress or finished stays viewable but offers no decision; the governed executor, which has no API, moves it through
IN_PROGRESS to COMPLETE, PARTIALLY_FAILED or FAILED, all read from `getDeletionRequest`. A request is not a deletion,
nothing is shown as removed optimistically, failures show their category only, and only COMPLETE claims completion. No
retention period is defined (OI-05).

<!-- UXP:labels:BEGIN -->
| Vocabulary | Value | Label | Meaning |
| --- | --- | --- | --- |
| api_report_state | GENERATING | Generating | The report is being generated from its pinned sources; nothing is ready yet. |
| api_report_state | GENERATED | Ready | The report was generated from its pinned sources. |
| api_report_state | FAILED | Generation failed | The report could not be generated. |
| api_report_state | INTEGRITY_FAILED | Integrity check failed | The report content did not pass its integrity check and is withheld. |
| api_report_state | REGENERATION_UNAVAILABLE | Cannot be regenerated | A pinned source is no longer available, so the report cannot be reproduced; nothing is approximated. |
| api_report_state | REMOVED_UNDER_GOVERNANCE | Removed under governance | The report was removed through governed deletion; it is not recreated. |
| api_replay_state | PENDING | Replay pending | The replay was accepted and has not finished; no outcome is implied. |
| api_replay_state | COMPLETED | Replay finished | The replay finished with the outcome shown. |
| replay_outcome | MATCH | Reproduced exactly | Replaying the pinned material produced the recorded result digest. |
| replay_outcome | MISMATCH | Did not reproduce | Replaying the pinned material produced a different digest; the recorded result is unchanged. |
| replay_outcome | FAILED_MISSING_MATERIAL | Replay unavailable: material missing | Required pinned material is missing, so the evaluation cannot be replayed. |
| replay_outcome | FAILED_INTEGRITY | Replay unavailable: integrity failure | Pinned material failed its integrity check, so the evaluation cannot be replayed. |
| replay_outcome | FAILED_ENGINE_UNAVAILABLE | Replay unavailable: engine unavailable | The pinned engine version is not available for replay. |
| replay_outcome | FAILED_BUNDLE_UNAVAILABLE | Replay unavailable: knowledge bundle unavailable | The pinned knowledge bundle is not available for replay. |
| api_deletion_state | REQUESTED | Requested | The request was recorded and awaits an administrator decision; nothing has been removed. |
| api_deletion_state | AUTHORIZED | Authorized | An administrator authorized the request; removal has not started. |
| api_deletion_state | IN_PROGRESS | In progress | Governed removal is running; it is not finished. |
| api_deletion_state | COMPLETE | Removal complete | Governed removal finished for the requested scope. |
| api_deletion_state | PARTIALLY_FAILED | Partly failed | Governed removal covered only part of the scope; it is not complete. |
| api_deletion_state | FAILED | Failed | Governed removal did not complete. |
| api_deletion_state | REJECTED | Rejected | An administrator rejected the request; nothing was removed. |
<!-- UXP:labels:END -->

## 9. Historical comparison

No accepted API compares evaluations or reports, so nothing is compared. History is shown as separate records in
requested order, each with its origin, predecessor, times and result availability, and no improvement, regression or
change is claimed. Source-pinned comparison is an owned deferred decision.

## 10. Protected copy, access consequences and scenarios

Protected copy is a closed set of governed messages, and every label and every meaning is checked on its own, so a safe
meaning never excuses an unsafe label: no deletion state before COMPLETE claims removal, a pending replay never claims completion or success,
replay never affirms substituting the current engine or any other material for what is unavailable (an explicit denial
is allowed), governed removal is
never worded as not found, regeneration never claims approximation, and re-analysis, correction and replay say the
earlier record is unchanged. Every operation that requires audit tells the person beforehand that it is recorded.

<!-- UXP:protected_text:BEGIN -->
| Protected display field | Governed text |
| --- | --- |
| reports.state_labels.GENERATING.label | Generating |
| reports.state_labels.GENERATING.meaning | The report is being generated from its pinned sources; nothing is ready yet. |
| reports.state_labels.GENERATED.label | Ready |
| reports.state_labels.GENERATED.meaning | The report was generated from its pinned sources. |
| reports.state_labels.FAILED.label | Generation failed |
| reports.state_labels.FAILED.meaning | The report could not be generated. |
| reports.state_labels.INTEGRITY_FAILED.label | Integrity check failed |
| reports.state_labels.INTEGRITY_FAILED.meaning | The report content did not pass its integrity check and is withheld. |
| reports.state_labels.REGENERATION_UNAVAILABLE.label | Cannot be regenerated |
| reports.state_labels.REGENERATION_UNAVAILABLE.meaning | A pinned source is no longer available, so the report cannot be reproduced; nothing is approximated. |
| reports.state_labels.REMOVED_UNDER_GOVERNANCE.label | Removed under governance |
| reports.state_labels.REMOVED_UNDER_GOVERNANCE.meaning | The report was removed through governed deletion; it is not recreated. |
| reports.content.pre_access_notice | Downloading this report is recorded in the audit log. |
| replay.state_labels.PENDING.label | Replay pending |
| replay.state_labels.PENDING.meaning | The replay was accepted and has not finished; no outcome is implied. |
| replay.state_labels.COMPLETED.label | Replay finished |
| replay.state_labels.COMPLETED.meaning | The replay finished with the outcome shown. |
| replay.outcome_labels.MATCH.label | Reproduced exactly |
| replay.outcome_labels.MATCH.meaning | Replaying the pinned material produced the recorded result digest. |
| replay.outcome_labels.MISMATCH.label | Did not reproduce |
| replay.outcome_labels.MISMATCH.meaning | Replaying the pinned material produced a different digest; the recorded result is unchanged. |
| replay.outcome_labels.FAILED_MISSING_MATERIAL.label | Replay unavailable: material missing |
| replay.outcome_labels.FAILED_MISSING_MATERIAL.meaning | Required pinned material is missing, so the evaluation cannot be replayed. |
| replay.outcome_labels.FAILED_INTEGRITY.label | Replay unavailable: integrity failure |
| replay.outcome_labels.FAILED_INTEGRITY.meaning | Pinned material failed its integrity check, so the evaluation cannot be replayed. |
| replay.outcome_labels.FAILED_ENGINE_UNAVAILABLE.label | Replay unavailable: engine unavailable |
| replay.outcome_labels.FAILED_ENGINE_UNAVAILABLE.meaning | The pinned engine version is not available for replay. |
| replay.outcome_labels.FAILED_BUNDLE_UNAVAILABLE.label | Replay unavailable: knowledge bundle unavailable |
| replay.outcome_labels.FAILED_BUNDLE_UNAVAILABLE.meaning | The pinned knowledge bundle is not available for replay. |
| reanalysis.notice | A new analysis creates a new evaluation. Earlier evaluations and results are kept unchanged. |
| correction.notice | Your correction creates a new evaluation. The earlier evaluation and its result are kept unchanged. |
| historical_comparison.notice | Each evaluation is shown as its own record. No comparison between them is computed. |
| deletion.state_labels.REQUESTED.label | Requested |
| deletion.state_labels.REQUESTED.meaning | The request was recorded and awaits an administrator decision; nothing has been removed. |
| deletion.state_labels.AUTHORIZED.label | Authorized |
| deletion.state_labels.AUTHORIZED.meaning | An administrator authorized the request; removal has not started. |
| deletion.state_labels.IN_PROGRESS.label | In progress |
| deletion.state_labels.IN_PROGRESS.meaning | Governed removal is running; it is not finished. |
| deletion.state_labels.COMPLETE.label | Removal complete |
| deletion.state_labels.COMPLETE.meaning | Governed removal finished for the requested scope. |
| deletion.state_labels.PARTIALLY_FAILED.label | Partly failed |
| deletion.state_labels.PARTIALLY_FAILED.meaning | Governed removal covered only part of the scope; it is not complete. |
| deletion.state_labels.FAILED.label | Failed |
| deletion.state_labels.FAILED.meaning | Governed removal did not complete. |
| deletion.state_labels.REJECTED.label | Rejected |
| deletion.state_labels.REJECTED.meaning | An administrator rejected the request; nothing was removed. |
<!-- UXP:protected_text:END -->

<!-- UXP:consequences:BEGIN -->
| Operation | Audit | Audit event | Audit notice shown |
| --- | --- | --- | --- |
| createReport | REQUIRED | REPORT_GENERATED | yes |
| listReports | NOT_REQUIRED | — | no |
| getReport | NOT_REQUIRED | — | no |
| getReportContent | REQUIRED | REPORT_EXPORTED | yes |
| createReplay | REQUIRED | REPLAY_EXECUTED | yes |
| getReplay | NOT_REQUIRED | — | no |
| createEvaluations | REQUIRED | EVALUATION_STARTED | yes |
| createCorrection | REQUIRED | USER_CORRECTION | yes |
| createDeletionRequest | REQUIRED | DELETION_REQUESTED | yes |
| listDeletionRequests | NOT_REQUIRED | — | no |
| getDeletionRequest | NOT_REQUIRED | — | no |
| authorizeDeletionRequest | REQUIRED | RETENTION_ACTION | yes |
| rejectDeletionRequest | REQUIRED | RETENTION_ACTION | yes |
<!-- UXP:consequences:END -->

The scenarios pin what the UX offers and presents for each action and condition. `validate_ux_reporting.py` re-derives
every row with an independent decision procedure built from the API's roles, resource authorization, modes and audit
requirements and the API-001 §17–§20 conditions.

<!-- UXP:scenarios:BEGIN -->
| Scenario | Situation | Action | Role / relationship / content / condition | Control | Request | Presented as | Content | New evaluation | Completion claimed | Audit notice |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RP-01 | Owner creates a report revision | CREATE_REPORT | USER / OWNER / yes / AVAILABLE | yes | yes | ACTION_PENDING | NONE | no | no | yes |
| RP-02 | Assigned analyst without content permission cannot create a report | CREATE_REPORT | ANALYST / ASSIGNED_ANALYST / no / AVAILABLE | no | no | CONTENT_PERMISSION_REQUIRED | NONE | no | no | no |
| RP-03 | Administrator cannot create a report | CREATE_REPORT | ADMINISTRATOR / NONE / no / AVAILABLE | no | no | ACCESS_DENIED | NONE | no | no | no |
| RP-04 | Owner lists case reports | LIST_REPORTS | USER / OWNER / yes / AVAILABLE | yes | yes | READY | NONE | no | no | no |
| RP-05 | Analyst without case visibility cannot list reports | LIST_REPORTS | ANALYST / NONE / no / AVAILABLE | no | no | NOT_FOUND_OR_NOT_VISIBLE | NONE | no | no | no |
| RP-06 | Owner downloads a generated report | DOWNLOAD_REPORT | USER / OWNER / yes / AVAILABLE | yes | yes | READY | ATTACHMENT | no | no | yes |
| RP-07 | Assigned analyst with content permission downloads a report | DOWNLOAD_REPORT | ANALYST / ASSIGNED_ANALYST / yes / AVAILABLE | yes | yes | READY | ATTACHMENT | no | no | yes |
| RP-08 | Report whose pinned source was removed cannot be regenerated (known from report metadata) | DOWNLOAD_REPORT | USER / OWNER / yes / REGENERATION_UNAVAILABLE | no | no | REPORT_REGENERATION_UNAVAILABLE | NONE | no | no | no |
| RP-09 | Report removed under governance (known from report metadata) | DOWNLOAD_REPORT | USER / OWNER / yes / REMOVED_UNDER_GOVERNANCE | no | no | REMOVED_UNDER_GOVERNANCE | NONE | no | no | no |
| RP-10 | Administrator with break-glass still has no report content | DOWNLOAD_REPORT | ADMINISTRATOR / BREAK_GLASS / yes / AVAILABLE | no | no | ACCESS_DENIED | NONE | no | no | no |
| RP-11 | Assigned analyst replays a completed evaluation | CREATE_REPLAY | ANALYST / ASSIGNED_ANALYST / no / AVAILABLE | yes | yes | ACTION_PENDING | NONE | no | no | yes |
| RP-12 | Administrator replays through an authorized reference | CREATE_REPLAY | ADMINISTRATOR / NONE / no / AVAILABLE | yes | yes | ACTION_PENDING | NONE | no | no | yes |
| RP-13 | Replay of a removed result is unavailable, not re-analysis | CREATE_REPLAY | ANALYST / ASSIGNED_ANALYST / no / REMOVED_UNDER_GOVERNANCE | no | no | REPLAY_UNAVAILABLE | NONE | no | no | no |
| RP-14 | Replay of an evaluation that has not completed | CREATE_REPLAY | ANALYST / ASSIGNED_ANALYST / no / EVALUATION_NOT_COMPLETED | no | no | CONDITIONAL_ON_EVALUATION_STATE | NONE | no | no | no |
| RP-15 | Owner cannot replay | CREATE_REPLAY | USER / OWNER / yes / AVAILABLE | no | no | ACCESS_DENIED | NONE | no | no | no |
| RP-16 | Replay finished with material missing is an explicit outcome | VIEW_REPLAY | ANALYST / ASSIGNED_ANALYST / no / REPLAY_MATERIAL_MISSING | yes | yes | REPLAY_UNAVAILABLE | NONE | no | no | no |
| RP-17 | Replay finished and reproduced | VIEW_REPLAY | ADMINISTRATOR / NONE / no / AVAILABLE | yes | yes | READY | NONE | no | no | no |
| RP-18 | Owner runs a new analysis | REANALYZE | USER / OWNER / yes / AVAILABLE | yes | yes | ACTION_PENDING | NONE | yes | no | yes |
| RP-19 | Assigned analyst runs a new analysis | REANALYZE | ANALYST / ASSIGNED_ANALYST / no / AVAILABLE | yes | yes | ACTION_PENDING | NONE | yes | no | yes |
| RP-20 | Administrator cannot run a new analysis | REANALYZE | ADMINISTRATOR / NONE / no / AVAILABLE | no | no | ACCESS_DENIED | NONE | no | no | no |
| RP-21 | Owner submits a correction as a new evaluation | CORRECT | USER / OWNER / yes / AVAILABLE | yes | yes | ACTION_PENDING | NONE | yes | no | yes |
| RP-22 | Assigned analyst cannot submit a user correction | CORRECT | ANALYST / ASSIGNED_ANALYST / yes / AVAILABLE | no | no | ACCESS_DENIED | NONE | no | no | no |
| RP-23 | Correction of an evaluation that has not completed | CORRECT | USER / OWNER / yes / EVALUATION_NOT_COMPLETED | no | no | CONDITIONAL_ON_EVALUATION_STATE | NONE | no | no | no |
| RP-24 | Owner requests governed deletion | REQUEST_DELETION | USER / OWNER / yes / AVAILABLE | yes | yes | READY | NONE | no | no | yes |
| RP-25 | Analyst cannot request deletion | REQUEST_DELETION | ANALYST / ASSIGNED_ANALYST / yes / AVAILABLE | no | no | ACCESS_DENIED | NONE | no | no | no |
| RP-26 | Administrator cannot request deletion | REQUEST_DELETION | ADMINISTRATOR / NONE / no / AVAILABLE | no | no | ACCESS_DENIED | NONE | no | no | no |
| RP-27 | Requested deletion claims nothing removed | VIEW_DELETION | USER / OWNER / yes / DELETION_REQUESTED | yes | yes | READY | NONE | no | no | no |
| RP-28 | Completed removal is the only completion claim | VIEW_DELETION | USER / OWNER / yes / DELETION_COMPLETE | yes | yes | READY | NONE | no | yes | no |
| RP-29 | Partly failed removal is not completion | VIEW_DELETION | ADMINISTRATOR / NONE / no / DELETION_PARTIALLY_FAILED | yes | yes | READY | NONE | no | no | no |
| RP-30 | Administrator authorizes a requested deletion | AUTHORIZE_DELETION | ADMINISTRATOR / NONE / no / DELETION_REQUESTED | yes | yes | ACTION_PENDING | NONE | no | no | yes |
| RP-31 | Stale ETag on authorization | AUTHORIZE_DELETION | ADMINISTRATOR / NONE / no / STALE_ETAG | yes | yes | STALE_STATE | NONE | no | no | yes |
| RP-32 | Owner cannot authorize deletion | AUTHORIZE_DELETION | USER / OWNER / yes / AVAILABLE | no | no | ACCESS_DENIED | NONE | no | no | no |
| RP-33 | Administrator rejects a requested deletion | REJECT_DELETION | ADMINISTRATOR / NONE / no / DELETION_REQUESTED | yes | yes | READY | NONE | no | no | yes |
| RP-34 | Analyst cannot reject deletion | REJECT_DELETION | ANALYST / ASSIGNED_ANALYST / yes / AVAILABLE | no | no | ACCESS_DENIED | NONE | no | no | no |
| RP-35 | Owner without case visibility cannot download | DOWNLOAD_REPORT | USER / NONE / no / AVAILABLE | no | no | NOT_FOUND_OR_NOT_VISIBLE | NONE | no | no | no |
| RP-36 | Knowledge approver has no deletion status | VIEW_DELETION | KNOWLEDGE_APPROVER / NONE / no / DELETION_REQUESTED | no | no | ACCESS_DENIED | NONE | no | no | no |
| RP-37 | Rejection not offered for a completed removal | REJECT_DELETION | ADMINISTRATOR / NONE / no / DELETION_COMPLETE | no | no | READY | NONE | no | no | no |
| RP-38 | Authorization not offered for a rejected request | AUTHORIZE_DELETION | ADMINISTRATOR / NONE / no / DELETION_REJECTED | no | no | READY | NONE | no | no | no |
| RP-39 | Authorization not offered again once authorized | AUTHORIZE_DELETION | ADMINISTRATOR / NONE / no / DELETION_AUTHORIZED | no | no | READY | NONE | no | no | no |
| RP-40 | Rejection not offered while removal is in progress | REJECT_DELETION | ADMINISTRATOR / NONE / no / DELETION_IN_PROGRESS | no | no | READY | NONE | no | no | no |
| RP-41 | A rejected request stays viewable | VIEW_DELETION | ADMINISTRATOR / NONE / no / DELETION_REJECTED | yes | yes | READY | NONE | no | no | no |
<!-- UXP:scenarios:END -->

## 11. Open decisions

<!-- UXP:decisions:BEGIN -->
| Unresolved decision | Owner | Status |
| --- | --- | --- |
| Report format and layout (REPORT-001); ReportContentDownload is opaque bytes until it is defined | Product / Reporting (REPORT-001), carried from UX-001 | DEFERRED |
| Source-pinned historical comparison has no accepted API capability; records are shown separately and no comparison is computed | API owner with Product / Reporting, carried from UX-001 | DEFERRED |
| User data export lacks an accepted API operation; no data-export surface is designed | API owner (governed API revision), carried from UX-001 | DEFERRED |
| createCorrection is an accepted operation placed on no UX-001 surface; its placement (UX-EVALUATION context) is recorded here pending a governed UX-001 revision | Programme UX governance | DEFERRED |
| reason_code for report, replay, re-analysis, correction and deletion commands has no governed vocabulary | API owner (governed vocabulary) | DEFERRED |
| Retention period and tombstone content after governed removal are not specified (OI-05) | Sponsor + legal/governance (OI-05) | DEFERRED |
| Final user-facing copy, translation and plain-language review of reporting and history labels | Product / Reporting UX with Phase 9 | DEFERRED |
| Detailed accessible and responsive layout of reporting and history surfaces | P7-WP6 / Accessibility UX | DEFERRED |
<!-- UXP:decisions:END -->

## 12. Carryovers and lifecycle

<!-- UXP:carryovers:BEGIN -->
| Item | Status | Owner |
| --- | --- | --- |
| G-09 | OPEN | Phase 10 (testing/evaluation; QA Lead) with Sponsor for any corpus access |
| OI-05 | OPEN | Sponsor + legal/governance |
| ASM-002 | UNCONFIRMED / PROVISIONAL | Sponsor / Programme |
| P6-WP7-LOW-1 | OPEN / NON-BLOCKING | Next governed Phase-6 snapshot revision / Programme governance |
<!-- UXP:carryovers:END -->

No tenant field is introduced and no numeric retention is invented. Detailed accessible and responsive layout belongs
to P7-WP6. `ENGINE_VERSION = 1.0.0` remains unchanged. The structured lifecycle in the machine contract is authoritative
and fails closed: a review round, an approval or merge evidence counts only when it equals the record pinned in
`validate_ux_reporting.py` by a governed bookkeeping step. Round 1 (initial independent review) returned
REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 2 / LOW 0 / INFO 0). Round 2 (targeted re-review) closed MEDIUM-2 and returned
REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 0 / INFO 0) on replay copy. Round 3 (targeted re-review) returned
APPROVE (BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 0 / INFO 0) with no open finding. PR #41 then merged with both
required CI jobs successful, and the governed post-merge step recorded the lifecycle as CLOSED; the merge evidence is
pinned in the validator, which checks exact agreement and does not contact GitHub. GATE-030 §7 holds the review record and
§8 the post-merge closure record.
