# UX-001 — Experience foundation and information architecture

| Field | Value |
| --- | --- |
| Document ID | UX-001 |
| Version | 0.1 |
| Status | P7-WP1 UX FOUNDATION APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING |
| Phase | Phase 7 — UX, Evidence & Reporting Design |
| Work package | P7-WP1 |
| Owner role | Product / UX Architecture |
| Baseline | bbe741b8ebfb7adbc399c1231b74f67f73ba2cfc |
| Gate | [GATE-026](../00-program/GATE-026-phase-7-ux-foundation.md) |
| Machine foundation | [ux-foundation-v1.json](../../contracts/ux/ux-foundation-v1.json) |
| Structural schema | [ux-foundation-contract.schema.json](../../contracts/ux/ux-foundation-contract.schema.json) |
| Builder validator | [validate_ux_foundation.py](../../knowledge/validation/validate_ux_foundation.py) |
| Last updated | 2026-10-05 |

## 1. Authority and scope

UX-001 is the authoritative Phase-7 UX foundation **approved following independent review**: product mental model, conceptual surface
architecture and permission-aware presentation requirements. Accepted domain/API contracts remain authoritative
for meaning. Remote CI and merge remain pending; P7-WP1 and GATE-026 are not finally closed.
P7-WP2 through P7-WP7 are NOT STARTED.

### Independent review and acceptance bookkeeping

The independent review results supplied for acceptance bookkeeping are:

| Review stage | Result | Disposition |
| --- | --- | --- |
| Initial independent review | BLOCKER 0 / HIGH 0 / MEDIUM 1 | REQUEST_CHANGES |
| MEDIUM-1 | Evaluation terminal failure could be presented as pending | Corrected by state-aware lifecycle mapping in §6 |
| Targeted independent re-review | BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 0 new / INFO 0 new | APPROVE; MEDIUM-1 CLOSED |

The reviewer confirmed readiness for acceptance bookkeeping and commit/PR closure, with P7-WP2 not started.
This records the completed independent review; it does not claim remote CI success, merge or final gate closure.
The corrected mapping remains `QUEUED` / `RUNNING` + `NOT_YET_AVAILABLE` + `EVALUATION_NOT_COMPLETED`
→ `ACTION_PENDING`, and `FAILED` + `NOT_PRODUCED` + `EVALUATION_NOT_COMPLETED` → `ACTION_FAILED`.
`EVALUATION_NOT_COMPLETED` alone is insufficient to determine presentation.

This document adds no detection, AI, authorization, content-access, replay, retention, persistence or network
semantics. It defines no frontend routes, React, CSS, FastAPI, components, design tokens, high-fidelity mockups,
workflow wireframes, pixel dimensions, palette, animation specifications, breakpoint numbers or production copy.
Surface IDs are stable conceptual references, never concrete browser routes or database dependencies.

The JSON companion encodes this foundation; marked tables below are exact projections checked by UXF-61.
A disagreement is a foundation defect, not permission to override accepted authority. Free prose is explanatory;
semantic requirements also live in structured fields checked by the offline validator. Automated checks do not
constitute an independent UX/security review, a working client, or runtime permission enforcement.

### Accepted inputs inspected

| Authority | Foundation consequence |
| --- | --- |
| [PHASE-6-CLOSURE](../00-program/PHASE-6-CLOSURE.md), especially §§6–12, 16–17 | Phase 6 CLOSED; historical pending wording in predecessor files is superseded; 19-artifact snapshot and OPEN LOW preserved |
| [DATA-001](../06-contracts/DATA-001-data-domain-lifecycle-contract.md), §§3.4, 5–6 | Canonical object names, sensitivity classes, immutability and provenance |
| [DATA-001-WP2](../06-contracts/DATA-001-WP2-postgresql-persistence-contract.md), §§3, 9–12 | Provisional tenancy, RM-01…RM-14, pinned reports and completion semantics |
| [API-001](../06-contracts/API-001-api-resource-protocol-contract.md), §§4–5, 10–25, 28–29, 34, 45; [api-v1.json](../../contracts/api/api-v1.json) | Five roles, per-operation/resource/content access, views, async errors and contract-active enrichment |
| [OAS-001](../06-contracts/OAS-001-openapi-contract.md), §§2–4, 20; [openapi-v1.json](../../contracts/api/openapi-v1.json) | Accepted operationIds and machine encoding parity; contract availability is not deployment |
| [INT-001](../06-contracts/INT-001-external-enrichment-integration-contract.md); [external-enrichment-v1.json](../../contracts/integrations/external-enrichment-v1.json) | Advisory provider assertions, indicator lookup only; no raw provider surface |
| [OPS-001](../06-contracts/OPS-001-operational-replay-persistence-contract.md), §§9–16; [operational-v1.json](../../contracts/operations/operational-v1.json) | Exact replay, new re-analysis, removal, no latest substitution, governed configuration |
| [DET-001 WP8](../03-detection/DET-001-WP8-integration-ci-closure.md); [DetectionResult schema](../../knowledge/schemas/detection/detection-result.schema.json) | Phase-3 categorical axes and authoritative immutable result; support-first semantics |
| [AI-001](../04-ai/AI-001-ai-intelligence-layer.md), §4; [AI WP4](../04-ai/AI-001-WP4-containment-provenance.md); [AI WP5](../04-ai/AI-001-WP5-phase3-integration.md) | Validated governed observation influence; exact consumed-artifact replay without AI recall |
| [ADR-0008](../../adr/ADR-0008-python-runtime-service-topology.md), [ADR-0009](../../adr/ADR-0009-identity-authentication-authorization.md), [ADR-0012](../../adr/ADR-0012-threat-intelligence-adapter-architecture-provider-selection.md) | Backend modularity, external identity plus backend authorization, controlled advisory enrichment |

These references are sources, not copies of persistence structure. Clients consume API representations only.

## 2. Core UX principles

<!-- UXF:principles:BEGIN -->
1. Explainable over impressive.
2. Uncertainty must be visible.
3. Provenance must be distinguishable from interpretation.
4. UX must never imply more certainty than accepted contracts provide.
5. Destructive and privileged actions require explicit intent.
6. Sensitive content visibility is permission-aware.
7. Backend authorization remains authoritative.
8. Hiding UI is not a security control.
9. Empty, loading and error states never imply safety.
10. Historical state must not silently become current state.
11. Provider assertions remain provider assertions.
12. System result and human adjudication remain separate.
<!-- UXF:principles:END -->

## 3. Canonical product mental model

<!-- UXF:model:BEGIN -->
| UX concept | Trace | Meaning |
| --- | --- | --- |
| Case | Case | Primary workspace/container for related activity; accepted lifecycle and resource authorization unchanged; no case-level verdict. |
| Submission | Submission | Material presented in one submission act, separate from evidence, execution and result; content-bearing context follows the evidence boundary. |
| EvidenceItem | EvidenceItem | Retained original material with integrity/custody provenance; metadata visibility does not grant content visibility. |
| EvidenceDerivative | EvidenceDerivative | A governed transform with exact parent lineage; never replaces its original; no standalone derivative API surface is available. |
| Evaluation | Evaluation | One governed analysis execution with its own historical context, exact input and pins. |
| GovernedInputArtifact | GovernedInputArtifact | Exact governed input consumed by exactly one Evaluation; distinct from raw evidence and never ordinary editable user content; no standalone API editor or viewer. |
| DetectionResult | DetectionResultRecord | Immutable completed deterministic result of one Evaluation; no edit, override or aggregate case verdict. |
| Adjudication | AnalystAdjudication | Separate append-only human review/context of a pinned result; never overwrites that result; C4 rationale requires permission. |
| Report | ReportBundleRecord | Report / ReportBundle revision with pinned sources; metadata and content are separate; format deferred to P7-WP5. |
| Replay | ReplayExecution | Reproduce/verify the historical deterministic result from exact required historical material; not current analysis. |
| ExternalEnrichment | ExternalEnrichmentResult | Advisory supporting provider assertions; no TrustLens verdict and no governed-artifact consumption. |
| GovernedRemoval | GovernedRemovalTombstone | Content-free governed removal fact, where the API exposes it; distinct from ordinary not-found and never reconstruction of content. |
| DeletionRequest | DeletionRequest | Governed request and server-confirmed outcome; completion is not inferred from an accepted request. |
| ReviewItem | ReviewRoutingState | Content-free routing/assignment metadata; neither a detection score nor an adjudication. |
| CaseAccessGrant | CaseAccessGrant | Accepted resource grant; metadata and content permission remain separate. |
| BreakGlassGrant | BreakGlassGrant | Explicit scoped temporary administrator privilege with reason, audit and independent post-event review. |
| AuditEvent | AuditEventReference | Governed accountability metadata; ordinary activity and telemetry never substitute for it. |
| Principal | PrincipalReference | Authenticated caller reference from getMe; no client-authored identity authority. |
| KnowledgeBundle | KnowledgeBundleReference | Exact governed bundle reference; no application rule authoring or database knowledge authority. |
| KnowledgeActivation | KnowledgeActivationRecord | Accepted activation history metadata; historical pins do not become the current active bundle. |
| Home | PRESENTATION_ONLY | Navigation shell only; no workload aggregate or persisted dashboard object. |
| Overview | PRESENTATION_ONLY | Composition of permitted case metadata; not a new aggregate verdict. |
| Activity | PRESENTATION_ONLY | Summary of already permitted resource timestamps/statuses only; no invented activity-feed API or audit authority. |
| History | PRESENTATION_ONLY | Composition of permitted evaluation/report/adjudication records; no new history entity. |
| SupportingContext | PRESENTATION_ONLY | Presentation grouping of attributed advisory enrichment separate from the deterministic result. |
| ReAnalysis | PRESENTATION_ONLY | Task that creates a NEW Evaluation and NEW GovernedInputArtifact under current governed conditions; never overwrites history. |
| SessionEntry | PRESENTATION_ONLY | UI entry to the accepted external identity boundary; no invented login API or local credential store. |
<!-- UXF:model:END -->

Submission, EvidenceItem, Evaluation and DetectionResult are separate identities. A case groups activity and
resource access; its lifecycle is unchanged and it has no combined case-level verdict. Evidence existence does
not mean the current principal can view its content. Derivatives retain lineage and sensitivity even when redacted.

A completed Evaluation retains historical time, exact governed input and knowledge/engine/profile context. Its
GovernedInputArtifact is an immutable one-to-one input, not a raw-evidence alias or an editable user document.
The API provides no standalone governed-input or derivative viewer; only permitted existing response fields may
represent their provenance. This mental model does not create retrieval endpoints for every logical object.

DetectionResult is immutable after completion. No action may edit/override a result or change classification,
severity, risk, confidence, matched rule or deterministic verdict. Human judgement is a separately attributed
Adjudication pinned to the exact result; a revised adjudication is a new record. Correction/re-analysis creates
a new Evaluation and new governed input. It never rewrites the prior result.

**Replay** reproduces/verifies the historical deterministic result using all applicable RM-01…RM-14 material:
exact historical governed artifact, knowledge, engine/profile, retained evidence/lineage and required AI snapshot.
No current knowledge, current evidence, AI call, provider call, material approximation or new Evaluation is replay.
Replay reports verification, never a replacement authoritative result. **Re-analysis** creates a NEW Evaluation
under current governed conditions and may legitimately differ. Unavailable replay is never relabelled as re-analysis.

## 4. Roles, permissions and sensitivity

Accepted RBAC vocabulary is exactly `USER`, `ANALYST`, `KNOWLEDGE_EDITOR`, `KNOWLEDGE_APPROVER`,
`ADMINISTRATOR` (API catalog `roles`). Reporter, Reviewer and Operator are **UX PERSONA ONLY**; none confers a role
or authorization. A single principal may have multiple accepted roles; separation-of-duty constraints still apply.

Every data-bearing surface requires authentication and the accepted operation's role **and resource authorization**.
Its ordinary `allowed_roles` is a union for navigation eligibility, not permission to invoke every listed operation.
The per-operation matrix below is binding; content and field permission apply additionally. The backend decides
every request. Hiding a control is not a security control, and parent/child navigation never inherits authorization.

`ADMINISTRATOR` alone cannot read raw evidence, results, reports or C4 rationale. The accepted raw-evidence operation
has an explicit administrator break-glass exception; no such exception is invented for result/report/rationale
operations. Holding an independently authorized USER/ANALYST role still requires the applicable resource and content
grant. `ANALYST` cannot create administrator break-glass. Reserved WP4 privileged interaction requires explicit
intent, reason, visible scope, temporary nature, audit consequence and post-event review by a different principal
(`REVIEWER_NOT_GRANTEE`). There is no one-click sudo or silent elevation, and no duration is invented.

Assignment keeps `ASSIGNEE_NOT_CALLER`, including a caller holding both ANALYST and ADMINISTRATOR. UI must not
intentionally offer forbidden self-assignment; backend enforcement remains authoritative. An administrator's ability
to assign does not grant the analyst-only queue view or evidence content. WP4 must resolve the target/ETag discovery
limitation recorded below before a usable assignment flow is claimed.

The accepted sensitivity vocabulary (DATA-001 §3.4) is:

| Class | Meaning | UX consequence |
| --- | --- | --- |
| C1 | Public / governed knowledge | Governed provenance; role/operation access still applies |
| C2 | Operational metadata | Content-free authorized identifiers, timestamps and categorical state |
| C3 | Sensitive submitted evidence | Separate content gate; no metadata-based disclosure |
| C4 | Derived sensitive content | No default visibility without required permission; redaction does not remove sensitivity |
| C5 | Security / identity metadata | Authorized account/grant context; no credentials |
| C6 | Audit / accountability metadata | Governed authorized audit, not an ordinary activity feed |
| C7 | Secret / key material | No ordinary application content or UX surface |
| C8 | Telemetry | Non-authoritative diagnostics; no evidence/result/audit substitute |

Labels describe handling, not statutory certification. Evidence metadata and content are separate surfaces.
DetectionResult STANDARD requires derived-content permission; DETAILED additionally requires assigned ANALYST.
Adjudication outcome/time may be available to an authorized owner, but rationale is included only for an assigned
analyst with `permits_evidence_content`. All locked states/placeholders must be content-free, including accessible
labels, previews and narrow-layout alternatives. Do not fetch protected content merely to hide it visually.

Preserve API existence masking: `404 NOT_FOUND` means absent **or not visible**, without revealing which. Only an
already authorized metadata context may justify a distinct content-permission placeholder after `403 FORBIDDEN`;
otherwise present denial without guessing the cause. A UI content-permission state is not a new API error code.

## 5. Information architecture and navigation

Twenty-two conceptual surfaces: 20 data-bearing and 2 non-resource shells. Every data surface maps to accepted
operationIds in both API and OpenAPI. Availability here means contract-supported, never runtime deployed.

<!-- UXF:surfaces:BEGIN -->
| Stable surface ID | Task / category | Parent | Ordinary eligible roles | API operationIds | Content permission | Boundary |
| --- | --- | --- | --- | --- | --- | --- |
| UX-SESSION | Session / sign-in / NON_RESOURCE_SURFACE | — | USER, ANALYST, KNOWLEDGE_EDITOR, KNOWLEDGE_APPROVER, ADMINISTRATOR | NON_RESOURCE_SURFACE | NONE | No TrustLens login operation; external OIDC boundary; browser session/CSRF choice deferred. |
| UX-HOME | Work overview / NON_RESOURCE_SURFACE | — | USER, ANALYST, KNOWLEDGE_EDITOR, KNOWLEDGE_APPROVER, ADMINISTRATOR | NON_RESOURCE_SURFACE | NONE | Task navigation only; no aggregate work counters or cross-case content. |
| UX-CASES | Cases / COLLECTION | UX-HOME | USER, ANALYST | listCases, createCase | NONE | Permitted case metadata only; creating a case remains USER-only. |
| UX-CASE | Case workspace / RESOURCE_WORKSPACE | UX-CASES | USER, ANALYST | getCase, closeCase, reopenCase | NONE | No case verdict or free-text case-note editor; activity is permitted metadata composition. |
| UX-SUBMISSION | Submission detail / RESOURCE_DETAIL | UX-CASE | USER, ANALYST | listSubmissions, getSubmission | NONE | Intake details deferred to WP2; no content-bearing free text in submission metadata. |
| UX-EVIDENCE-METADATA | Evidence metadata / RESOURCE_DETAIL | UX-SUBMISSION | USER, ANALYST | listEvidence, getEvidenceMetadata | NONE | Metadata never includes evidence bytes or storage locators. |
| UX-EVIDENCE-CONTENT | Evidence content / RESOURCE_DETAIL | UX-EVIDENCE-METADATA | USER, ANALYST | getEvidenceContent | CONTENT_PERMISSION_REQUIRED | Application-mediated attachment download only; no inline raw rendering promised. ADMINISTRATOR needs accepted scoped break-glass. |
| UX-EVALUATION | Evaluation history / execution / RESOURCE_DETAIL | UX-CASE | USER, ANALYST | listCaseEvaluations, getEvaluation, createEvaluations | NONE | Status and existing API provenance only; no raw governed artifact exposure; current analysis creates a new Evaluation. |
| UX-RESULT | Detection result / RESOURCE_DETAIL | UX-EVALUATION | USER, ANALYST | getDetectionResult | CONTENT_PERMISSION_REQUIRED | STANDARD requires content permission; DETAILED additionally requires assigned ANALYST; no editing. |
| UX-ADJUDICATION | Human review history / REVIEW_WORKSPACE | UX-EVALUATION | USER, ANALYST | listAdjudications, getAdjudication, createAdjudication | FIELD_PERMISSION_REQUIRED | Outcome/time available per case access; rationale only for assigned ANALYST with content permission; create is separately restricted. |
| UX-REPORTS | Reports / history / REPORTING | UX-CASE | USER, ANALYST | listReports, getReport | NONE | Case-scoped report metadata; no global report collection endpoint. |
| UX-REPORT-CONTENT | Report generation / content / REPORTING | UX-REPORTS | USER, ANALYST | createReport, getReportContent | CONTENT_PERMISSION_REQUIRED | Derived content permission; no automatic transmission; exact pinned regeneration only. |
| UX-REPLAY | Historical verification / SUPPORTING_CONTEXT | UX-EVALUATION | ANALYST, ADMINISTRATOR | createReplay, getReplay | NONE | Content-free outcomes/digests; administrator can enter through an authorized reference without access to the parent case. |
| UX-REVIEW-QUEUE | Review queue / REVIEW_WORKSPACE | UX-HOME | ANALYST | listReviewQueue | NONE | ANALYST-only content-free queue; deployment scope remains provisional under ASM-002. |
| UX-ASSIGNMENT | Review assignment / PRIVILEGED_ACTION | UX-HOME | ADMINISTRATOR | assignReview | NONE | Administrator command for an already-authorized target reference. No administrator queue-read or principal-directory API exists; target/ETag discovery is unresolved for WP4/API owner. |
| UX-AUDIT | Audit / accountability / AUDIT_ADMIN | UX-HOME | ADMINISTRATOR | listAuditEvents | NONE | Content-free governed audit; authorized administrator read is itself audited. |
| UX-ENRICHMENT | External supporting context / SUPPORTING_CONTEXT | UX-EVALUATION | ANALYST | listEvaluationEnrichments | NONE | ANALYST-only normalized advisory metadata; attribute provider category and observed time if returned; no raw provider body or invented provider identity field. |
| UX-BREAK-GLASS | Privileged evidence access / PRIVILEGED_ACTION | UX-HOME | ADMINISTRATOR | createBreakGlassGrant, getBreakGlassGrant, endBreakGlassGrant, reviewBreakGlassGrant | NONE | Explicit reason, scope, temporary nature, audit and post-event review; no silent elevation; reviewer differs from grantee. |
| UX-DELETION | Governed removal requests / PRIVILEGED_ACTION | UX-HOME | USER, ADMINISTRATOR | createDeletionRequest, listDeletionRequests, getDeletionRequest, authorizeDeletionRequest, rejectDeletionRequest | NONE | Owner request and administrator decision are different actions; no optimistic completion or numeric retention. |
| UX-ACCESS-GRANTS | Case access administration / AUDIT_ADMIN | UX-CASE | USER, ADMINISTRATOR | listCaseAccessGrants, revokeCaseAccessGrant | NONE | Content-free grants; owner may list, administrator may revoke; direct authorized entry does not grant parent case access. |
| UX-ACCOUNT | Account / role context / RESOURCE_DETAIL | UX-HOME | USER, ANALYST, KNOWLEDGE_EDITOR, KNOWLEDGE_APPROVER, ADMINISTRATOR | getMe | NONE | Authenticated self summary only; no credential, role-editing or account-directory operation. |
| UX-KNOWLEDGE | Knowledge provenance / history / SUPPORTING_CONTEXT | UX-HOME | ANALYST, KNOWLEDGE_EDITOR, KNOWLEDGE_APPROVER, ADMINISTRATOR | getActiveKnowledge, getKnowledgeBundle, listKnowledgeActivations | NONE | Read-only permitted bundle identities and activation history; per-operation roles apply; no rule-body editing. |
<!-- UXF:surfaces:END -->

Navigation follows tasks: Cases for authorized USER/ANALYST work; Review queue only for ANALYST; authorized
Audit/accountability and Knowledge provenance entries; Account for the caller. Reports/history is a **case-context**
entry because `listReports` is case-scoped. Home remains a navigation-only shell: no invented aggregate endpoint,
workload score, global report list or activity feed. Ordinary users see no irrelevant administrator navigation.

Case workspace composition reserves Overview, Submissions, Evidence, Evaluations, Adjudication/review history,
Reports, Activity and External supporting context. Regions compose the listed child surfaces when authorized;
Activity uses already-permitted resource timestamps/statuses and is PRESENTATION_ONLY. External supporting context
is analyst-only. Collapsed tabs/regions and mobile layouts cannot weaken any child permission. Authorized direct
entry to content-free replay or grant metadata does not grant access to the parent case workspace.

No standalone note/derivative/governed-artifact editor, provider-policy editor, identity/role administration or user
data-export surface is introduced: the accepted API does not support those product flows. Knowledge references are
read-only here; rule authoring remains governed Git/CI authority. The catalog supports additional operations that
WP1 need not surface. Detailed intake commands, correction and knowledge controls are not silently implemented.

### Per-operation access and sensitivity trace

`NONE` in the content-gate column does not bypass resource access or field visibility. Break-glass roles are separate
exceptions accepted by that individual operation, not ordinary surface roles. C4 adjudication rationale has the
field gate described above even when the metadata read has `sensitive_content_permission = NONE`.

<!-- UXF:access:BEGIN -->
| Surface | Operation | Ordinary roles | Resource authorization | Content gate | Break-glass roles | Sensitivity | Caller constraints |
| --- | --- | --- | --- | --- | --- | --- | --- |
| UX-CASES | listCases | USER, ANALYST | CASE_ACCESS | NONE | — | C2 | — |
| UX-CASES | createCase | USER | SELF | NONE | — | C2 | — |
| UX-CASE | getCase | USER, ANALYST | CASE_ACCESS | NONE | — | C2 | — |
| UX-CASE | closeCase | USER, ANALYST | CASE_ACCESS | NONE | — | C2 | — |
| UX-CASE | reopenCase | USER, ANALYST | CASE_ACCESS | NONE | — | C2 | — |
| UX-SUBMISSION | listSubmissions | USER, ANALYST | CASE_ACCESS | NONE | — | C2 | — |
| UX-SUBMISSION | getSubmission | USER, ANALYST | CASE_ACCESS | NONE | — | C2 | — |
| UX-EVIDENCE-METADATA | listEvidence | USER, ANALYST | CASE_ACCESS | NONE | — | C2 | — |
| UX-EVIDENCE-METADATA | getEvidenceMetadata | USER, ANALYST | CASE_ACCESS | NONE | — | C2 | — |
| UX-EVIDENCE-CONTENT | getEvidenceContent | USER, ANALYST | CASE_EVIDENCE_CONTENT | EVIDENCE_CONTENT | ADMINISTRATOR | C3 | — |
| UX-EVALUATION | listCaseEvaluations | USER, ANALYST | CASE_ACCESS | NONE | — | C2 | — |
| UX-EVALUATION | getEvaluation | USER, ANALYST | CASE_ACCESS | NONE | — | C2 | — |
| UX-EVALUATION | createEvaluations | USER, ANALYST | CASE_ACCESS | NONE | — | C2 | — |
| UX-RESULT | getDetectionResult | USER, ANALYST | CASE_DERIVED_CONTENT | DERIVED_CONTENT | — | C4 | — |
| UX-ADJUDICATION | listAdjudications | USER, ANALYST | CASE_ACCESS | NONE | — | C4 | — |
| UX-ADJUDICATION | getAdjudication | USER, ANALYST | CASE_ACCESS | NONE | — | C4 | — |
| UX-ADJUDICATION | createAdjudication | ANALYST | CASE_ASSIGNED_ANALYST | DERIVED_CONTENT | — | C4 | — |
| UX-REPORTS | listReports | USER, ANALYST | CASE_ACCESS | NONE | — | C2 | — |
| UX-REPORTS | getReport | USER, ANALYST | CASE_ACCESS | NONE | — | C2 | — |
| UX-REPORT-CONTENT | createReport | USER, ANALYST | CASE_DERIVED_CONTENT | DERIVED_CONTENT | — | C4 | — |
| UX-REPORT-CONTENT | getReportContent | USER, ANALYST | CASE_DERIVED_CONTENT | DERIVED_CONTENT | — | C4 | — |
| UX-REPLAY | createReplay | ANALYST, ADMINISTRATOR | CASE_ASSIGNED_ANALYST_OR_PLATFORM_ADMIN | NONE | — | C2 | — |
| UX-REPLAY | getReplay | ANALYST, ADMINISTRATOR | CASE_ASSIGNED_ANALYST_OR_PLATFORM_ADMIN | NONE | — | C2 | — |
| UX-REVIEW-QUEUE | listReviewQueue | ANALYST | REVIEW_QUEUE | NONE | — | C2 | — |
| UX-ASSIGNMENT | assignReview | ADMINISTRATOR | PLATFORM_ADMIN | NONE | — | C2 | ASSIGNEE_NOT_CALLER |
| UX-AUDIT | listAuditEvents | ADMINISTRATOR | AUDIT_READ | NONE | — | C6 | — |
| UX-ENRICHMENT | listEvaluationEnrichments | ANALYST | CASE_ACCESS | NONE | — | C2 | — |
| UX-BREAK-GLASS | createBreakGlassGrant | ADMINISTRATOR | BREAK_GLASS_SELF | NONE | — | C5 | — |
| UX-BREAK-GLASS | getBreakGlassGrant | ADMINISTRATOR | BREAK_GLASS_GRANTEE_OR_PLATFORM_ADMIN | NONE | — | C5 | — |
| UX-BREAK-GLASS | endBreakGlassGrant | ADMINISTRATOR | BREAK_GLASS_GRANTEE | NONE | — | C5 | — |
| UX-BREAK-GLASS | reviewBreakGlassGrant | ADMINISTRATOR | BREAK_GLASS_REVIEWER | NONE | — | C5 | REVIEWER_NOT_GRANTEE |
| UX-DELETION | createDeletionRequest | USER | DELETION_SCOPE_OWNER | NONE | — | C2 | — |
| UX-DELETION | listDeletionRequests | USER, ADMINISTRATOR | DELETION_SCOPE_OWNER_OR_PLATFORM_ADMIN | NONE | — | C2 | — |
| UX-DELETION | getDeletionRequest | USER, ADMINISTRATOR | DELETION_SCOPE_OWNER_OR_PLATFORM_ADMIN | NONE | — | C2 | — |
| UX-DELETION | authorizeDeletionRequest | ADMINISTRATOR | PLATFORM_ADMIN | NONE | — | C2 | — |
| UX-DELETION | rejectDeletionRequest | ADMINISTRATOR | PLATFORM_ADMIN | NONE | — | C2 | — |
| UX-ACCESS-GRANTS | listCaseAccessGrants | USER, ADMINISTRATOR | CASE_OWNER_OR_PLATFORM_ADMIN | NONE | — | C5 | — |
| UX-ACCESS-GRANTS | revokeCaseAccessGrant | ADMINISTRATOR | PLATFORM_ADMIN | NONE | — | C5 | — |
| UX-ACCOUNT | getMe | USER, ANALYST, KNOWLEDGE_EDITOR, KNOWLEDGE_APPROVER, ADMINISTRATOR | SELF | NONE | — | C5 | — |
| UX-KNOWLEDGE | getActiveKnowledge | ANALYST, KNOWLEDGE_EDITOR, KNOWLEDGE_APPROVER, ADMINISTRATOR | KNOWLEDGE_READ | NONE | — | C1 | — |
| UX-KNOWLEDGE | getKnowledgeBundle | ANALYST, KNOWLEDGE_EDITOR, KNOWLEDGE_APPROVER, ADMINISTRATOR | KNOWLEDGE_READ | NONE | — | C1 | — |
| UX-KNOWLEDGE | listKnowledgeActivations | KNOWLEDGE_EDITOR, KNOWLEDGE_APPROVER, ADMINISTRATOR | KNOWLEDGE_READ | NONE | — | C2 | — |
<!-- UXF:access:END -->

## 6. Global presentation states

All names below are **presentation states**, not persisted backend states. Error codes are accepted API mappings;
HTTP status alone is insufficient. The UI retains distinct error identity and safe retry guidance. A completed
`UNSUPPORTED` result is distinct from upload media rejection or an infrastructure-failed Evaluation.

<!-- UXF:states:BEGIN -->
| Presentation state | Accepted API error code(s) | Meaning |
| --- | --- | --- |
| LOADING | Presentation only | Waiting for an authorized response; no provisional verdict. |
| EMPTY | Presentation only | Nothing is available for this surface/query; no safety inference. |
| READY | Presentation only | Authorized representation is available; readiness is not a verdict. |
| ACTION_PENDING | IDEMPOTENCY_IN_PROGRESS | Accepted or executing work; no completion claim. |
| ACTION_FAILED | INVALID_REQUEST | Action did not complete; preserve safe field errors without values. |
| AUTHENTICATION_REQUIRED | UNAUTHENTICATED | Authentication boundary required. |
| ACCESS_DENIED | FORBIDDEN | Operation refused; no protected content or invented reason. |
| CONTENT_PERMISSION_REQUIRED | FORBIDDEN | Use only when authorized metadata establishes the separate content-permission restriction; otherwise ACCESS_DENIED. |
| NOT_FOUND_OR_NOT_VISIBLE | NOT_FOUND | Preserve existence masking; do not disclose whether a hidden resource exists. |
| PRECONDITION_REQUIRED | PRECONDITION_REQUIRED | Required concurrency precondition absent. |
| STALE_STATE | PRECONDITION_FAILED | State changed; refresh permitted state; never silently overwrite. |
| CONFLICT | CONFLICT, STATE_CONFLICT, IDEMPOTENCY_KEY_REUSED | Material conflict; distinguish safe backend code; do not resubmit blindly. |
| REMOVED_UNDER_GOVERNANCE | REMOVED_UNDER_GOVERNANCE | Governed-unavailability state; 410 is distinct from ordinary 404 or empty; never recreate content. |
| TEMPORARILY_UNAVAILABLE | DEPENDENCY_UNAVAILABLE | Dependency unavailable; no safety or completion inference. |
| UNSUPPORTED_INPUT | UNSUPPORTED_MEDIA_TYPE | Unsupported capability, never benign; a completed UNSUPPORTED classification remains a result, not a transport failure. |
| REPLAY_UNAVAILABLE | REPLAY_UNAVAILABLE | Required historical material unavailable; never latest substitution; separate permitted re-analysis may create a new Evaluation. |
| REPORT_REGENERATION_UNAVAILABLE | REPORT_REGENERATION_UNAVAILABLE | Required pinned report source unavailable; never regenerate from latest. |
| INTEGRITY_ERROR | INTEGRITY_FAILURE | Withhold unverified content; no result or safety inference. |
| SERVER_ERROR | INTERNAL_ERROR | Safe server failure; distinct from integrity failure. |
| RATE_LIMITED | RATE_LIMITED | Admission control; respect governed retry guidance; no invented countdown. |
| INPUT_LIMIT_EXCEEDED | PAYLOAD_TOO_LARGE | Configured input bound exceeded; no invented limit value. |
<!-- UXF:states:END -->

### Evaluation completion errors require authoritative state (MEDIUM-1 correction)

`EVALUATION_NOT_COMPLETED` is not itself sufficient to determine whether work is still pending. API-001 §29.1
allows this error for queued/running **or failed** evaluations. Combine the error semantic with the authoritative
Evaluation lifecycle state before choosing presentation; do not reinterpret the backend error or its retryability.

The existing `getEvaluation` operation returns `EvaluationResponse.state` and `result_availability`, both required
by the accepted API/OpenAPI schema. API state vocabulary is `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`.
API-001 §13.1 maps DATA-001 §5.9.1 statuses as follows: `REQUESTED` → `QUEUED`; `RUNNING` and
`RESULT_COMPUTED_PERSISTENCE_PENDING` → `RUNNING`; `COMPLETED` → `COMPLETED`; `FAILED_PRECONDITION`,
`FAILED_INTEGRITY` and `FAILED_INFRASTRUCTURE` → `FAILED`. The last three produce no DetectionResult and expose
`result_availability = NOT_PRODUCED`; queued/running expose `NOT_YET_AVAILABLE`.

The following **conditional** mapping replaces the former flat error-to-pending entry:

<!-- UXF:evaluation_error:BEGIN -->
| API error | Authoritative Evaluation state | Result availability | Presentation state |
| --- | --- | --- | --- |
| EVALUATION_NOT_COMPLETED | QUEUED | NOT_YET_AVAILABLE | ACTION_PENDING |
| EVALUATION_NOT_COMPLETED | RUNNING | NOT_YET_AVAILABLE | ACTION_PENDING |
| EVALUATION_NOT_COMPLETED | FAILED | NOT_PRODUCED | ACTION_FAILED |
<!-- UXF:evaluation_error:END -->

A terminal `FAILED` Evaluation must never be presented as `ACTION_PENDING`. If authoritative lifecycle context is
missing, inaccessible, inconsistent or stale, retain the safe error meaning without inferring pending or terminal
failure from the error code alone. Obtain/refresh the existing Evaluation representation only where already
authorized; this creates no new access path. No matching state/availability pair means no pending/failure inference.
`COMPLETED` is not a pending execution; completed `ERROR`/`UNSUPPORTED` classifications and governed-removal
semantics remain unchanged. Detailed recovery interaction stays deferred to P7-WP3 / P7-WP5.


Empty means only nothing available for that surface/query. Loading, processing and async pending never imply safe,
clean, cleared or no scam. READY means authorized data is available, not that a case is safe. Server errors and
integrity failures remain distinct. Unsupported/non-English input cannot become benign because it cannot be evaluated.

Where authorized API semantics provide `410 REMOVED_UNDER_GOVERNANCE`, show governed unavailability distinctly
from 404/empty. Never recreate removed content or reveal it from cached/hidden previews. Missing required historical
material means `REPLAY_UNAVAILABLE`; a separate authorized re-analysis action can create a new Evaluation.
Missing pinned report sources means `REPORT_REGENERATION_UNAVAILABLE`; never use latest material or retain a hidden
copy solely to reproduce a report. Exact capability/missing-material detail is limited to what the API returns.

## 7. Result, AI, enrichment and provenance guardrails

No final result copy is specified here; P7-WP3 owns labels and explanation hierarchy. Preserve accepted categorical
classification, decision severity, matched evidence strength, risk and detection confidence. These axes are distinct;
none becomes a percentage, scam probability, confidence gauge or arbitrary trust/safety/scam/reputation score.
`NO_SCAM_PATTERN`, `INSUFFICIENT_EVIDENCE`, `UNSUPPORTED` and `ERROR` never mean SAFE. Suspected patterns retain
visible uncertainty; detected patterns do not imply legal guilt or an official determination.

Future explanations must support observed material, contributing governed rule semantics, relevant negative/mitigating
indicators, uncertainty, provenance and next actions. Keep user-provided material, retained evidence, system-derived
observations, AI-derived governed observations, external provider assertions, deterministic result and human
adjudication visibly distinguishable. Do not flatten them into an AI result or merge system and human conclusions.

**AI may indirectly affect deterministic output through validated governed observations. AI cannot directly set,
override or bypass deterministic decision semantics.** It remains optional/default-OFF. AI verdict/score/engine-override
wording and the claim that AI can never influence output are both prohibited. Historical replay never calls AI.

Enrichment is attributed **supporting/advisory context**, never the primary TrustLens verdict. Provider `CLEAN` remains
a provider assertion; it cannot become Safe, Verified safe, Legitimate, TrustLens cleared or No scam. `NOT_FOUND` and
`UNAVAILABLE` never imply safety either. Enrichment remains outside the governed artifact under current authority.

Respect the actual `EnrichmentView`: `enrichment_id`, `provider_category`, `status`, `reputation_result`, optional
`observed_at`, `advisory`. Attribute the provider category and returned observed time without inventing a vendor identity,
freshness field or `lookup_outcome` field. `NOT_FOUND`/`UNAVAILABLE` are integration-level outcomes: detailed copy must
wait for a supported representation; do not derive one merely from `UNKNOWN` or `NOT_EVALUATED`. Expanded attribution
is an owned WP6/API decision. Raw provider responses, destinations, locators and credentials are never shown.

## 8. Interaction foundations

Destructive/privileged actions require an explicit action, clear affected resource, stated consequence, confirmation
where appropriate and the authoritative server outcome. No optimistic deletion/completion claim precedes confirmation.
Detailed deletion and privileged workflows remain WP5 and WP4 respectively.

For `If-Match`, show `428 PRECONDITION_REQUIRED` distinctly from `412 PRECONDITION_FAILED` / stale state. Refresh
permitted state and make the conflict visible; never silently overwrite. Users experience safe retry, while
Idempotency-Key remains protocol machinery and never authorization or a normal user-facing concept. Do not expose
key/fence material. An accepted 202 means work is pending; poll only the accepted resource/status operations and
claim completion only from the authoritative terminal outcome. No invented percentage or polling interval.

Governed audit remains distinct from ordinary activity/telemetry. Prohibit raw provider bodies, credentials/secrets,
connector topology, internal host/IP details, EvidenceContentStore locators, unpermitted raw evidence/C4 rationale,
internal execution/fence tokens and idempotency-key material in all ordinary UI, errors, labels and placeholders.
Submitted URLs are evidence/indicator data, not a new content-fetch or embedded browsing capability.

## 9. Accessibility and responsive foundation

Require keyboard-operable interaction, logical focus order, visible focus, semantic headings/regions, meaning beyond
colour, textual status equivalents, associated field errors and error summaries, screen-reader labels for important
controls, and designed announcements for processing/result changes. Animation must not be required for comprehension.
Green never automatically means SAFE; red never replaces canonical classification text; icons need accessible meaning.
These are design requirements, not achieved accessibility compliance, certification or evaluated conformance.

The architecture must support different form factors. **BREAKPOINT_VALUES = NOT YET SPECIFIED.** No pixel values,
brand palette or exact layout is selected. Permissions behave identically across form factors: a narrow/mobile layout
must never expose content hidden on desktop. Detailed patterns, responsive behavior and evaluation belong to P7-WP6.

## 10. Open programme items and claim boundaries

<!-- UXF:carryovers:BEGIN -->
| Item | Status | Owner | Boundary |
| --- | --- | --- | --- |
| G-09 | OPEN | Phase 10 (testing/evaluation; QA Lead) with Sponsor for any corpus access | No labelled real-world evaluation corpus. |
| OI-05 | OPEN | Sponsor + legal/governance | Retention and permitted residual metadata remain governed decisions; no numeric duration. |
| ASM-002 | UNCONFIRMED / PROVISIONAL | Sponsor / Programme | No tenancy authority; tenancy-sensitive implementation blocked as recorded by DATA-001-WP2. |
| P6-WP7-LOW-1 | OPEN / NON-BLOCKING | next governed Phase-6 snapshot revision / Programme governance | Four contract JSON Schemas are not included in the canonical 19-artifact hash snapshot; not fixed by P7-WP1. |
<!-- UXF:carryovers:END -->

No tenant_id, tenant selector, organization switcher, workspace tenancy or multi-tenant navigation is introduced.
No numeric retention duration is invented. G-09 means no labelled real-world evaluation corpus, so there is no
accuracy, high-accuracy, low-false-positive or trusted-detection-rate claim. Synthetic validation is not effectiveness.
There is no frontend/API implementation, production-readiness, accessibility-compliance or independent-approval claim.
`ENGINE_VERSION = 1.0.0` remains unchanged.

## 11. Later-work ownership (handoff only)

<!-- UXF:handoffs:BEGIN -->
| Work package | Status | Owner | Detailed scope deferred |
| --- | --- | --- | --- |
| P7-WP2 | NOT STARTED | Product / Intake UX | Submission flow; Evidence capture; Upload interaction; Evidence metadata preview; Submission progress; Capture errors; Supported consent/instruction copy |
| P7-WP3 | NOT STARTED | Product / Result UX | DetectionResult presentation; Classification labels; Risk/severity/confidence; Matched and indeterminate rules; Negative indicators; Uncertainty; Recommended actions; Explanation hierarchy |
| P7-WP4 | NOT STARTED | Product / Security UX | Evidence review; Content permission; Review queue; Assignment; Break-glass; Adjudication; C4 rationale; Audit access |
| P7-WP5 | NOT STARTED | Product / Reporting UX | Reports; Replay; Re-analysis; Governed deletion; 410 removed; Replay unavailable; Report regeneration unavailable; Historical comparison |
| P7-WP6 | NOT STARTED | Product / Accessibility UX | Accessibility patterns; Unsupported language; Responsive behavior; External enrichment; Provider attribution; CLEAN / NOT_FOUND / UNAVAILABLE interpretation |
| P7-WP7 | NOT STARTED | Programme / Independent Reviewer | Integrated Phase-7 closure |
<!-- UXF:handoffs:END -->

P7-WP1 stops at foundation/IA. Each later work package must resolve its detailed design through its own authorized
gate and consume the existing contracts; this table does not start or complete any later work.

<!-- UXF:decisions:BEGIN -->
| Unresolved decision | Owner | Status |
| --- | --- | --- |
| Browser session / CSRF profile; accepted OIDC boundary unchanged | Phase 7 / Security Architect before browser implementation | DEFERRED |
| User data export lacks an accepted API operation; no UX data-export surface | P7-WP5 / API owner; later governed API revision | DEFERRED |
| Administrator assignment target and If-Match acquisition; no queue-read or principal-directory capability for administrator-only callers | P7-WP4 / API owner; resolve before detailed assignment workflow | DEFERRED |
| Report format and source-pinned comparison | P7-WP5 / Reporting | DEFERRED |
| Provider identity and detailed outcome attribution beyond current EnrichmentView | P7-WP6 / API owner; governed API revision if needed | DEFERRED |
| Detailed intake, result, review and accessibility interactions | P7-WP2 through P7-WP6 owners | DEFERRED |
| Breakpoints and responsive behavior | P7-WP6 / Accessibility UX | DEFERRED |
<!-- UXF:decisions:END -->

## 12. Validation boundary and builder self-challenge

The offline validator has 65 checks (UXF-01…UXF-65): the requested 56 plus graph integrity, per-operation parity,
interaction requirements, exposure/representation limits, human/machine projections, efficacy claims, the carried
snapshot LOW, distinct error mappings and result/provenance/responsive scope. Negative fixtures require rejection
by the named check, rather than by schema validation alone. Canonical runner and temporary-copy CI self-test include
one P7-WP1 content-access defect. GATE-026 records measured local results.

The freeze check recomputes the existing 19 artifact hashes and pins the accepted closure bookkeeping/validator.
It does not add the four omitted schemas to the Phase-6 snapshot or close its LOW. Builder git comparison separately
checks the full protected surface, including those schemas. This validator is not a prose theorem prover, browser
accessibility test or live authorization test. Completed independent review and targeted approval are recorded in §1;
automated checks do not replace that review. No later workflow, unsupported API capability or performance/accuracy
claim is validated here.

| Builder challenge (not independent review) | Answer |
| --- | --- |
| Did I invent a new RBAC role? | No. |
| Did I confuse persona with authorization role? | No. |
| Can ADMINISTRATOR see evidence content by role alone? | No — prohibited by this foundation; backend remains authoritative for access. |
| Can ANALYST create break-glass? | No — prohibited by this foundation; backend remains authoritative for access. |
| Can forbidden self-assignment happen? | No permitted UX path; ASSIGNEE_NOT_CALLER also covers dual-role callers. Runtime enforcement is not implemented or proven here. |
| Can C4 rationale appear without permission? | No — prohibited by this foundation; backend remains authoritative for access. |
| Can UX edit DetectionResult? | No — prohibited by this foundation; backend remains authoritative for access. |
| Can Adjudication overwrite DetectionResult? | No — prohibited by this foundation; backend remains authoritative for access. |
| Does Replay look like re-analysis? | No — exact historical verification and new current Evaluation are separate concepts/surfaces/actions. |
| Does re-analysis overwrite history? | No — new Evaluation and new GovernedInputArtifact. |
| Can NO_SCAM_PATTERN display as SAFE? | No — prohibited by this foundation; backend remains authoritative for access. |
| Can INSUFFICIENT_EVIDENCE display as SAFE? | No — prohibited by this foundation; backend remains authoritative for access. |
| Can UNSUPPORTED display as SAFE? | No — prohibited by this foundation; backend remains authoritative for access. |
| Can ERROR display as SAFE? | No — prohibited by this foundation; backend remains authoritative for access. |
| Can provider CLEAN display as TrustLens safe? | No — prohibited by this foundation; backend remains authoritative for access. |
| Can NOT_FOUND or UNAVAILABLE mean safe? | No — prohibited by this foundation; backend remains authoritative for access. |
| Did I introduce scam probability? | No. |
| Did I introduce a 0–100 score? | No. |
| Did I describe AI as the final decision-maker? | No. |
| Did I incorrectly claim AI can never influence output? | No. |
| Can empty/loading/processing imply safe? | No — prohibited by this foundation; backend remains authoritative for access. |
| Does governed removal look identical to ordinary empty/not-found? | No — authorized 410 has its own governed-unavailability state; 404 masking is preserved. |
| Can replay silently use latest material? | No — prohibited by this foundation; backend remains authoritative for access. |
| Can report regeneration silently use latest material? | No — prohibited by this foundation; backend remains authoritative for access. |
| Does every data-bearing surface map to real API operationIds? | Yes — 20 surfaces; API/OpenAPI trace and per-operation access matrix above. |
| Did I invent a persisted UX domain object? | No. |
| Did I expose raw provider material? | No. |
| Did I expose raw evidence without permission? | No. |
| Did I introduce tenant_id or tenant switching? | No. |
| Did I invent retention duration? | No. |
| Did I close G-09? | No. |
| Did I close OI-05? | No. |
| Did I confirm ASM-002? | No. |
| Did I claim accessibility compliance? | No. |
| Did I claim frontend implementation? | No. |
| Did I claim production readiness? | No. |
| Did I modify Phase-6 accepted artifacts? | No. |
| Did I start P7-WP2? | No. |
