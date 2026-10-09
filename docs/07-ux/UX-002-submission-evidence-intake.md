# UX-002 — Submission and evidence intake experience

| Field | Value |
| --- | --- |
| Document ID | UX-002 |
| Version | 0.1 |
| Status | P7-WP2 SUBMISSION INTAKE APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING |
| Phase | Phase 7 — UX, Evidence & Reporting Design |
| Work package | P7-WP2 |
| Owner role | Product / Intake UX |
| Baseline | d16ee7a8fd65a0428a0cde7cc1dceb7bd166d528 (P7-WP1 merge, PR #34) |
| Gate | [GATE-027](../00-program/GATE-027-phase-7-submission-intake.md) |
| Foundation | [UX-001](UX-001-experience-foundation-information-architecture.md) (consumed, not modified) |
| Machine contract | [ux-intake-v1.json](../../contracts/ux/ux-intake-v1.json) |
| Structural schema | [ux-intake-contract.schema.json](../../contracts/ux/ux-intake-contract.schema.json) |
| Builder validator | [validate_ux_intake.py](../../knowledge/validation/validate_ux_intake.py) (UXI-01…UXI-77) |
| Last updated | 2026-10-08 |

## 1. Authority and scope

UX-002 is the P7-WP2 UX contract, **approved following independent review** (remote CI and merge pending), for submitting suspicious material and preserving it as evidence. It
consumes, and changes nothing in, the closed Phase-6 contracts (PHASE-6-CLOSURE: PHASE 6 CLOSED), the accepted API
catalog and OpenAPI encoding (exactly the bytes pinned by the Phase-6 snapshot), DATA-001 / DATA-001-WP2, ADR-0014 and
the P7-WP1 foundation UX-001. It adds no endpoint, API field, HTTP status, error code, persisted concept, frontend,
route, component, copy deck, server, migration or network integration.

Repository state at baseline: P7-WP1 merged as PR #34 (`d16ee7a…`). UX-001 / GATE-026 still carry their pre-merge
"remote CI + merge pending" status rows; that is historical wording and is not rewritten here (see §12). The
machine-readable companion encodes every rule below; marked tables are exact projections checked by UXI-56. Automated
checks are not independent review, usability testing, accessibility evaluation or runtime authorization testing.

### Review history and lifecycle

P7-WP2 is **APPROVED following independent review — remote CI + merge pending**; it is not CLOSED. The structured lifecycle in the machine contract is authoritative: approval requires an
exact `APPROVE` decision in the review history with BLOCKER/HIGH/MEDIUM 0 and a resolvable GATE-027 record; CLOSED
additionally requires structured merge evidence (repository, base, PR, PR head, merge commit, both required CI jobs with
run identifiers) that equals the independently verified record pinned in the validator by the governed post-merge step
(the Phase-6 P6C-05 precedent); until that record exists, CLOSED fails closed. The offline validator checks structure,
exact vocabulary, consistency and plausibility only — the truth of reviewer identity, PR, merge and CI runs must be
independently verified against GitHub. No merge or CI result is claimed here. Round 2 (targeted re-review)
closed MEDIUM-1 and requested changes for three further MEDIUM findings (reconciliation, PROCESSING action eligibility,
freshness/availability). Round 3 kept MEDIUM-1 closed and requested changes for the same three areas (identifier
identity in reconciliation, readiness-witness binding and recovery prose, internal-lifecycle derivation and ordering);
Round 4 closed MEDIUM-2 and MEDIUM-3 and kept one MEDIUM-4 finding open (an overlapping exchange labelled FRESH kept
its label). Round 5, the final independent review, returned **APPROVE** (BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 2 /
INFO 2) and closed MEDIUM-4; the review record is GATE-027 §7. LOW-1, LOW-2, INFO-1 and INFO-2 remain OPEN.

<!-- UXI:review_history:BEGIN -->
| Round | Kind | Decision | BLOCKER | HIGH | MEDIUM | LOW | INFO | Record |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | INITIAL_INDEPENDENT_REVIEW | REQUEST_CHANGES | 0 | 0 | 4 | 2 | 2 | GATE-027 §6 |
| 2 | TARGETED_INDEPENDENT_REREVIEW | REQUEST_CHANGES | 0 | 0 | 3 | 2 | 2 | GATE-027 §6 |
| 3 | TARGETED_INDEPENDENT_REREVIEW | REQUEST_CHANGES | 0 | 0 | 3 | 2 | 2 | GATE-027 §6 |
| 4 | TARGETED_INDEPENDENT_REREVIEW | REQUEST_CHANGES | 0 | 0 | 1 | 2 | 2 | GATE-027 §6 |
| 5 | FINAL_INDEPENDENT_REVIEW | APPROVE | 0 | 0 | 0 | 2 | 2 | GATE-027 §7 |
<!-- UXI:review_history:END -->

Round-1 findings and dispositions (also recorded in GATE-027 §6); MEDIUM findings are corrected and await the targeted
re-review, and LOW/INFO findings are carried — none is claimed closed:

<!-- UXI:findings:BEGIN -->
| Finding | Round | Severity | Summary | Disposition | Closed in round | Owner |
| --- | --- | --- | --- | --- | --- | --- |
| MEDIUM-1 | 1 | MEDIUM | Unsupported approval/closure evidence accepted (substring APPROVE, arbitrary PR integer, generic 40-hex SHA) | CLOSED_BY_REREVIEW | 2 | P7-WP2 builder |
| MEDIUM-2 | 1 | MEDIUM | Unsafe reauthentication/retry identity model and unqualified duplicate-outcome guarantee; no unknown-outcome state | CLOSED_BY_REREVIEW | 4 | P7-WP2 builder |
| MEDIUM-3 | 1 | MEDIUM | PROCESSING presented as bytes received/verifying although it also covers CONTENT_PENDING and FAILED_RETRYABLE | CLOSED_BY_REREVIEW | 4 | P7-WP2 builder |
| MEDIUM-4 | 1 | MEDIUM | Fixed success presentation states override returned authoritative lifecycle fields | CLOSED_BY_REREVIEW | 5 | P7-WP2 builder |
| LOW-1 | 1 | LOW | UXI-51 checks only five of the eight owned decisions; NEG-UXI-081 description says 'media list' but the mutation invents a size limit | OPEN_CARRIED | — | P7-WP2 builder (next P7-WP2 revision) |
| LOW-2 | 1 | LOW | Stale P7-WP1 closure wording (UX-001 / GATE-026 / UXF-01..02 still pending) and P7-WP2 dependency on that foundation | OPEN_CARRIED | — | Programme governance (P7-WP1 post-merge closure correction) |
| INFO-1 | 1 | INFO | roadmap.md Phase-7 decomposition is stale | OPEN_INFORMATIONAL | — | Programme / roadmap owner |
| INFO-2 | 1 | INFO | Insignificant owner capitalisation difference for P6-WP7-LOW-1 between UX-001 and the Phase-6 manifest | OPEN_INFORMATIONAL | — | Programme governance |
| R2-MEDIUM-2 | 2 | MEDIUM | Reconciliation reads accepted getEvidenceContent / getActiveKnowledge and an empty read list (not bound to resource, caller or content semantics) | CLOSED_BY_REREVIEW | 4 | P7-WP2 builder |
| R2-MEDIUM-3 | 2 | MEDIUM | Finalization granted from the collapsed PROCESSING label; recovery action prose (ASSUME_FINALIZED) and display meaning not bound to semantics | CLOSED_BY_REREVIEW | 4 | P7-WP2 builder |
| R2-MEDIUM-4 | 2 | MEDIUM | Missing result_availability defaulted to READY; cached FINALIZED overrode fresh contradictory metadata | CLOSED_BY_REREVIEW | 5 | P7-WP2 builder |
| R2-LOW-1 | 2 | LOW | Round 2 re-confirms LOW-1 (eight-decision coverage; NEG-UXI-081 description) | OPEN_CARRIED | — | P7-WP2 builder (next P7-WP2 revision) |
| R2-LOW-2 | 2 | LOW | Round 2 re-confirms LOW-2 (P7-WP1 closure bookkeeping) | OPEN_CARRIED | — | Programme governance (separate P7-WP1 lifecycle correction) |
| R2-INFO-1 | 2 | INFO | Round 2 re-confirms INFO-1 (stale roadmap decomposition) | OPEN_INFORMATIONAL | — | Programme / roadmap owner |
| R2-INFO-2 | 2 | INFO | Round 2 re-confirms INFO-2 (owner capitalisation) | OPEN_INFORMATIONAL | — | Programme governance |
| R3-MEDIUM-2 | 3 | MEDIUM | Identifier provenance not identity-checked (case_id accepted as submission_id); essential submission filter removable | CLOSED_BY_REREVIEW | 4 | P7-WP2 builder |
| R3-MEDIUM-3 | 3 | MEDIUM | PUT-success witness not bound to the evidence item and upload attempt; recovery reason prose unbound | CLOSED_BY_REREVIEW | 4 | P7-WP2 builder |
| R3-MEDIUM-4 | 3 | MEDIUM | Public lifecycle not derived from the accepted internal machine (ORPHAN_DETECTED -> FINALIZED); staleness from send order despite overlap; ambiguous unordered pair forced to one state | CLOSED_BY_REREVIEW | 5 | P7-WP2 builder |
| R3-LOW-1 | 3 | LOW | Round 3 re-confirms LOW-1 (eight-decision coverage; NEG-UXI-081 description) | OPEN_CARRIED | — | P7-WP2 builder (next P7-WP2 revision) |
| R3-LOW-2 | 3 | LOW | Round 3 re-confirms LOW-2 (P7-WP1 closure bookkeeping) | OPEN_CARRIED | — | Programme governance (separate P7-WP1 lifecycle correction) |
| R3-INFO-1 | 3 | INFO | Round 3 re-confirms INFO-1 (stale roadmap decomposition) | OPEN_INFORMATIONAL | — | Programme / roadmap owner |
| R3-INFO-2 | 3 | INFO | Round 3 re-confirms INFO-2 (owner capitalisation) | OPEN_INFORMATIONAL | — | Programme governance |
| R4-MEDIUM-4 | 4 | MEDIUM | Overlapping exchanges labelled FRESH kept their label (only KNOWN_STALE was normalized), so REJECTED/FINALIZED pairs gained unsupported server-order certainty | CLOSED_BY_REREVIEW | 5 | P7-WP2 builder |
| R4-LOW-1 | 4 | LOW | Round 4 re-confirms LOW-1 (eight-decision coverage; NEG-UXI-081 description) | OPEN_CARRIED | — | P7-WP2 builder (next P7-WP2 revision) |
| R4-LOW-2 | 4 | LOW | Round 4 re-confirms LOW-2 (P7-WP1 closure bookkeeping) | OPEN_CARRIED | — | Programme governance (separate P7-WP1 lifecycle correction) |
| R4-INFO-1 | 4 | INFO | Round 4 re-confirms INFO-1 (stale roadmap decomposition) | OPEN_INFORMATIONAL | — | Programme / roadmap owner |
| R4-INFO-2 | 4 | INFO | Round 4 re-confirms INFO-2 (owner capitalisation) | OPEN_INFORMATIONAL | — | Programme governance |
| R5-LOW-1 | 5 | LOW | Final review re-confirms LOW-1 (eight-decision coverage; NEG-UXI-081 description) | OPEN_CARRIED | — | P7-WP2 builder (next P7-WP2 revision) |
| R5-LOW-2 | 5 | LOW | Final review re-confirms LOW-2 (stale P7-WP1 closure bookkeeping) | OPEN_CARRIED | — | Programme governance (separate P7-WP1 lifecycle correction) |
| R5-INFO-1 | 5 | INFO | Final review re-confirms INFO-1 (stale Phase-7 roadmap decomposition) | OPEN_INFORMATIONAL | — | Programme / roadmap owner |
| R5-INFO-2 | 5 | INFO | Final review re-confirms INFO-2 (owner capitalisation difference) | OPEN_INFORMATIONAL | — | Programme governance |
<!-- UXI:findings:END -->

<!-- UXI:scope:BEGIN -->
| Owned P7-WP2 scope (UX-001 handoff) |
| --- |
| Submission flow |
| Evidence capture |
| Upload interaction |
| Evidence metadata preview |
| Submission progress |
| Capture errors |
| Supported consent/instruction copy |
<!-- UXI:scope:END -->

<!-- UXI:deferred:BEGIN -->
| Deferred item | Owner |
| --- | --- |
| Evidence-content viewing, content-permission flows and evidence review | P7-WP4 |
| DetectionResult presentation, classification labels, explanation and uncertainty | P7-WP3 |
| Re-analysis, retry-after-failure, user correction, replay and governed deletion of evidence | P7-WP5 |
| Detailed accessibility patterns, responsive breakpoints and the unsupported-language experience | P7-WP6 |
| External-enrichment presentation | P7-WP6 |
<!-- UXI:deferred:END -->

**Scope differences recorded before implementation.** The request for this work package asked for broader coverage
than UX-001 assigns to P7-WP2. Following the accepted authority: (1) evidence *content* access is stated only as a
boundary — viewing, permission flows and review are P7-WP4; (2) Evaluation is covered only as the explicit initial
analysis request and its pending/terminal hand-off — result presentation is P7-WP3; (3) retry-after-failure,
re-analysis and correction (`predecessor_evaluation_id`, `createCorrection`) are P7-WP5; (4) consent capture has no
accepted API field, so only supported instruction requirements are specified; (5) `roadmap.md` lists only UX-001 /
REPORT-001 for Phase 7 and is stale — the accepted UX-001 decomposition governs.

## 2. Domain concepts kept separate

<!-- UXI:concepts:BEGIN -->
| Concept | DATA-001 object | Intake meaning |
| --- | --- | --- |
| Case | Case | Container and access scope; created empty; no verdict. |
| Submission | Submission | One act of presenting material; categorical metadata only; not evidence, not an evaluation. |
| EvidenceItem | EvidenceItem | One original artifact with server-computed SHA-256 and custody metadata; bytes immutable once stored. |
| EvidenceDerivative | EvidenceDerivative | Server-produced transform with exact lineage; not created, uploaded or shown by intake. |
| Evaluation | Evaluation | One governed analysis execution requested separately after evidence is finalized. |
<!-- UXI:concepts:END -->

A submission is not evidence; a successful upload is not an evaluation; FINALIZED evidence is preserved, not
analysed; an accepted evaluation request (`202`) is not a result; a PROCESSED submission is not an outcome. There is no
case- or submission-level verdict: the server derives one evaluation per governed input envelope (one for MVP text,
URL and email submissions, with user context folded into that envelope). Derivatives are produced by the server and
have no intake or API surface.

## 3. Materials

<!-- UXI:materials:BEGIN -->
| Material | artifact_kind | declared_input_type | Media type | Availability | Offered |
| --- | --- | --- | --- | --- | --- |
| MESSAGE_TEXT | TEXT_BODY | TEXT, SMS, CHAT_MESSAGE | text/plain; charset=utf-8 | MVP | yes |
| URL | URL | URL | text/uri-list | MVP | yes |
| EMAIL_SOURCE | EMAIL_SOURCE | EMAIL | ACCEPTED_TYPE_CONFIGURATION_NOT_YET_SPECIFIED | MVP | yes |
| USER_CONTEXT | OTHER | — | application/vnd.trustlens.user-context+json | MVP | yes |
| SCREENSHOT_IMAGE | IMAGE | — | ACCEPTED_TYPE_CONFIGURATION_NOT_YET_SPECIFIED | POST_MVP | no |
| DOCUMENT | DOCUMENT | — | ACCEPTED_TYPE_CONFIGURATION_NOT_YET_SPECIFIED | FUTURE | no |
<!-- UXI:materials:END -->

Pasted SMS/chat text is sent as `text/plain; charset=utf-8`; a submitted URL as `text/uri-list` and is **never
fetched, opened, previewed, unfurled or rendered as a live link**. Optional user context (sender, channel,
description) is its own evidence item (`OTHER` + the TrustLens user-context media type), never submission JSON.
Screenshots/images are Post-MVP and documents are future: intake does not offer them. Multiple items may belong to one
submission. Email-source media types are configuration and not yet specified.

## 4. Surfaces

The intake adds three conceptual surfaces under the UX-001 case workspace. They are stable references, not routes.

<!-- UXI:surfaces:BEGIN -->
| Surface | Title / category | Parent | API operationIds | Content gate |
| --- | --- | --- | --- | --- |
| UX-INTAKE-COMPOSE | Submission composer / RESOURCE_WORKSPACE | UX-CASE | createSubmission | NONE |
| UX-INTAKE-EVIDENCE | Evidence capture and upload / RESOURCE_DETAIL | UX-INTAKE-COMPOSE | createEvidenceUpload, putEvidenceContent, finalizeEvidence, getEvidenceMetadata | UPLOAD_OWN_CONTENT_ONLY |
| UX-INTAKE-PROGRESS | Submission progress and analysis request / RESOURCE_DETAIL | UX-INTAKE-COMPOSE | getSubmission, listEvidence, createEvaluations, getEvaluation | NONE |
<!-- UXI:surfaces:END -->

Case creation stays on the UX-001 `UX-CASES` surface. Intake commands are USER-only and require `CASE_OWNER`; the
backend decides every request. `UPLOAD_OWN_CONTENT_ONLY` means `putEvidenceContent` writes the owner's own bytes under
the accepted `EVIDENCE_CONTENT` gate; it grants no read-back of content.

## 5. User journey and API traceability

<!-- UXI:journey:BEGIN -->
| Step | User action | Surface | operationId | Method / path | Success | Mode | Idempotency | Roles | Resource authorization | Content gate | Presentation on success (authoritative) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| INT-S01 | Start or choose a case | UX-CASES | createCase | POST /api/v1/cases | 201 | SYNC | REQUIRED | USER | SELF | NONE | returned state via case_state_presentation |
| INT-S02 | Declare the submission (categorical metadata only) | UX-INTAKE-COMPOSE | createSubmission | POST /api/v1/cases/{case_id}/submissions | 201 | SYNC | REQUIRED | USER | CASE_OWNER | NONE | returned state via submission_state_presentation |
| INT-S03 | Initiate one evidence item per material | UX-INTAKE-EVIDENCE | createEvidenceUpload | POST /api/v1/submissions/{submission_id}/evidence | 201 | SYNC | REQUIRED | USER | CASE_OWNER | NONE | returned upload_state via upload_state_presentation |
| INT-S04 | Send the exact bytes of that item | UX-INTAKE-EVIDENCE | putEvidenceContent | PUT /api/v1/evidence/{evidence_id}/content | 200 | SYNC | NATURALLY_IDEMPOTENT | USER | CASE_OWNER | EVIDENCE_CONTENT | returned upload_state via upload_state_presentation |
| INT-S05 | Request server verification and finalization | UX-INTAKE-EVIDENCE | finalizeEvidence | POST /api/v1/evidence/{evidence_id}/finalize | 202 | ASYNC | REQUIRED | USER | CASE_OWNER | NONE | returned upload_state via upload_state_presentation |
| INT-S06 | Confirm authoritative evidence state | UX-INTAKE-EVIDENCE | getEvidenceMetadata | GET /api/v1/evidence/{evidence_id} | 200 | SYNC | NOT_APPLICABLE | USER, ANALYST | CASE_ACCESS | NONE | returned upload_state via upload_state_presentation |
| INT-S07 | Review the submission's evidence metadata | UX-INTAKE-PROGRESS | listEvidence | GET /api/v1/submissions/{submission_id}/evidence | 200 | SYNC | NOT_APPLICABLE | USER, ANALYST | CASE_ACCESS | NONE | returned upload_state via upload_state_presentation |
| INT-S08 | Confirm submission state | UX-INTAKE-PROGRESS | getSubmission | GET /api/v1/submissions/{submission_id} | 200 | SYNC | NOT_APPLICABLE | USER, ANALYST | CASE_ACCESS | NONE | returned state via submission_state_presentation |
| INT-S09 | Request analysis as a separate explicit action | UX-INTAKE-PROGRESS | createEvaluations | POST /api/v1/submissions/{submission_id}/evaluations | 202 | ASYNC | REQUIRED | USER, ANALYST | CASE_ACCESS | NONE | returned state via evaluation_status_presentation |
| INT-S10 | Observe analysis status until terminal | UX-INTAKE-PROGRESS | getEvaluation | GET /api/v1/evaluations/{evaluation_id} | 200 | SYNC | NOT_APPLICABLE | USER, ANALYST | CASE_ACCESS | NONE | returned state via evaluation_status_presentation |
<!-- UXI:journey:END -->

**Authoritative state takes precedence (MEDIUM-4).** Every step renders the lifecycle field the server actually
returned (`state`, `upload_state`, or each `evaluations[].state` + `result_availability`) through the matching state
table; a successful HTTP status never implies the expected initial state, and a `202` never implies pending. Every
component needed to decide the presentation must be present and valid: a missing, null or unrecognised
`result_availability` (or state) becomes `STATE_UNKNOWN_RECONCILE` and is never defaulted, and an inconsistent
combination (for example `COMPLETED` + `NOT_PRODUCED`) becomes `STATE_CONFLICT_RECONCILE`; neither can conceal governed
removal or unavailability. Freshness uses only supported information — the client's own request order and explicit
reconciliation reads; no server timestamp, revision or ordering guarantee is assumed:

- **overlapping exchanges are normalized first, at one point:** if the two request/response exchanges overlapped, the
  pair is treated as **unordered whatever the client label says** (`FRESH` or `KNOWN_STALE`). Concurrent dispatch order
  and response arrival order never establish server snapshot order, client labels are never authoritative ordering,
  and the accepted API provides no server ordering evidence (none is invented). A transition that the lifecycle permits
  is never treated as proof that it occurred;
- a **known-stale** response — established only when its request/response exchange completed before the later
  observation's request was sent — never regresses that observation, provided the lifecycle can explain the order;
  otherwise it is a conflict;
- a **fresh** (non-overlapping) response is shown when the accepted lifecycle can reach it from the earlier observation (for example
  `FINALIZED` → `REJECTED` after a later integrity failure, or → governed deletion), and is a conflict otherwise
  (for example cached `FINALIZED` followed by fresh `PROCESSING` or `AWAITING_CONTENT`);
- **unordered** responses follow lifecycle order only when exactly one direction is reachable; otherwise they are a
  conflict.

Upload reachability is derived from the accepted DATA-001-WP2 §11 internal state machine projected through the API's
internal-to-public mapping: a public transition exists when an internal path connects covered internal states. Because
`ORPHAN_DETECTED` (public `REJECTED`) can be reconciled to `FINALIZED` and `FINALIZED` can later fail integrity
(`REJECTED`), `REJECTED` and `FINALIZED` are reachable in both directions, so an unordered or overlapping pair of them is a
conflict — including when the overlapping exchanges were labelled `FRESH` — while a non-overlapping fresh `FINALIZED`
after `REJECTED` (orphan reconciliation) is shown.

`STATE_CONFLICT_RECONCILE` shows neither state as confirmed current state and never presents a conflict as success;
the client re-reads and reconciles. Server state wins over local belief.

1. **Case.** The owner creates an empty case or opens a permitted one (`listCases` / `getCase`). An existing case may
   already contain submissions and evaluations: prior analysis is never assumed absent and is discovered only through
   `listCaseEvaluations`. No verdict exists on a case.
2. **Submission.** The owner declares the submission with categorical metadata only (`declared_input_type`, optional
   `relationship_to_content`). Free text never goes into submission JSON.
3. **Initiate → transfer → finalize, per item.** `createEvidenceUpload` creates the item; `putEvidenceContent` sends
   the exact bytes, which the server streams and hashes; `finalizeEvidence` (`202`) asks the server to verify
   durability. An identical re-PUT or a repeated finalize may already return `FINALIZED`; that state is shown and never
   regressed. Only a server-reported `FINALIZED` means preserved. `client_declared_sha256` is advisory.
4. **Review metadata.** `getEvidenceMetadata` / `listEvidence` show metadata only (§8).
5. **Request analysis — a separate, explicit action.** When the server reports every item `FINALIZED`, the owner may
   request analysis (`createEvaluations`, `202`). The client gate is a convenience: the backend rejects out-of-order
   requests with `STATE_CONFLICT`. Nothing is analysed automatically after upload.
6. **Observe status.** The batch response and `getEvaluation` give authoritative state; an already terminal state in
   the `202` body is honoured. Intake never presents the result: a completed evaluation hands off to the P7-WP3 result
   surface.

Intake sends no `analysis_mode`, `predecessor_evaluation_id` or `reason_code`; the request can never carry any
decision, provenance or knowledge field. AI may contribute only validated governed observations, is default-OFF, and
is reported through `AiUsageSummary`; intake shows no AI verdict and offers no AI selector (owned decision, §11).

## 6. States

All names below are presentation states, not persisted states. None implies safe, clean, cleared, evaluated or "no scam".

**PROCESSING is neutral (MEDIUM-3).** The API maps `CONTENT_PENDING`, `CONTENT_STORED`, `INTEGRITY_VERIFIED` and
`FAILED_RETRYABLE` to `PROCESSING`. The upload-state facts below are derived from that mapping: `PROCESSING` alone never
proves that bytes were stored or verified, and only `FINALIZED` proves both. Public presentation, readiness evidence and
permitted action are separate: no accepted response field distinguishes the PROCESSING sub-states, and re-reading the
same label is not readiness. The only accepted readiness evidence for finalization is this client's own successful
`putEvidenceContent` response (`200`, `EvidenceMetadataResponse`) for that item. Local transfer progress never proves
receipt or verification and never upgrades the server state; an interrupted transfer without a response is
`RECEIPT_UNKNOWN` until `getEvidenceMetadata` is re-read. Each displayed meaning is built only from the governed claim
texts of its state (machine contract `semantic_claims`); recovery reasons are governed too, and every prose string in
the machine contract is scanned. Preserved evidence is never presented as an evaluation, a verdict, safety or detection
success. The readiness witness is bound to **this** evidence item and **this** upload attempt: the PUT response's
`evidence_id` must equal the item to finalize and its `content_sha256` must equal the digest of the exact bytes this
client sent; a witness is never reused for another item or another attempt and is not persisted beyond the attempt.

<!-- UXI:finalization:BEGIN -->
| Scenario | Situation | Witness | Target item / sent digest | Server state | Finalization allowed |
| --- | --- | --- | --- | --- | --- |
| FE-01 | witness for the same item and attempt | A / D1 | A / D1 | PROCESSING | yes |
| FE-02 | witness for item A reused to finalize item B | A / D1 | B / D1 | PROCESSING | no |
| FE-03 | witness from a different upload attempt (different bytes) | A / D0 | A / D1 | PROCESSING | no |
| FE-04 | no witness (interrupted PUT) | none | A / D1 | PROCESSING | no |
| FE-05 | valid witness but the server already reports FINALIZED | A / D1 | A / D1 | FINALIZED | no |
<!-- UXI:finalization:END -->

<!-- UXI:upload_states:BEGIN -->
| api upload_state | Presentation state | Covers internal states | Proves bytes stored | Proves verified | Claims | Meaning (built from claims) |
| --- | --- | --- | --- | --- | --- | --- |
| AWAITING_CONTENT | EVIDENCE_AWAITING_CONTENT | RECEIVED | no | no | NOT_FINAL, NO_STORED_BYTES_REPORTED, NO_OUTCOME_IMPLIED | Not finalized. The server has not reported stored bytes. No analysis outcome, verdict or safety is implied. |
| PROCESSING | EVIDENCE_PROCESSING_NOT_FINALIZED | CONTENT_PENDING, CONTENT_STORED, INTEGRITY_VERIFIED, FAILED_RETRYABLE | no | no | NOT_FINAL, RECEIPT_NOT_PROVEN, MAY_BE_STORING_OR_RETRYING, NO_OUTCOME_IMPLIED | Not finalized. Not proof that bytes were received or verified. The server may still be storing, verifying or retrying. No analysis outcome, verdict or safety is implied. |
| FINALIZED | EVIDENCE_FINALIZED | FINALIZED | yes | yes | BYTES_STORED_VERIFIED, PRESERVED_NOT_ANALYSED, NO_OUTCOME_IMPLIED | Bytes durably stored and digest-verified by the server. Evidence is preserved, not analysed. No analysis outcome, verdict or safety is implied. |
| REJECTED | EVIDENCE_REJECTED | FAILED_TERMINAL, ORPHAN_DETECTED, INTEGRITY_FAILED, QUARANTINED | no | no | REJECTED_NEW_ITEM_NEEDED, NO_OUTCOME_IMPLIED | Not usable; the client cannot resume it, and server reconciliation may still change its state. No analysis outcome, verdict or safety is implied. |
| DELETION_PENDING | EVIDENCE_REMOVAL_PENDING | DELETION_PENDING | no | no | GOVERNED_REMOVAL_PENDING, NO_OUTCOME_IMPLIED | Governed removal is in progress; content is not shown. No analysis outcome, verdict or safety is implied. |
| DELETED | EVIDENCE_REMOVED | DELETED | no | no | REMOVED_NOT_RECONSTRUCTED, NO_OUTCOME_IMPLIED | Removed under governance; never reconstructed or previewed. No analysis outcome, verdict or safety is implied. |
<!-- UXI:upload_states:END -->

<!-- UXI:case_states:BEGIN -->
| api case state | Presentation state | Meaning |
| --- | --- | --- |
| OPEN | CASE_OPEN | Case open; it may already contain submissions and evaluations; no verdict. |
| UNDER_REVIEW | CASE_UNDER_REVIEW | Case under analyst review; prior analysis exists or may exist; no verdict. |
| CLOSED | CASE_CLOSED | Case closed; reopen is a separate governed command; no verdict. |
| DELETION_PENDING | CASE_REMOVAL_PENDING | Governed removal in progress; no intake. |
| DELETED | CASE_REMOVED | Removed under governance; never reconstructed. |
<!-- UXI:case_states:END -->

<!-- UXI:submission_states:BEGIN -->
| api submission state | Presentation state | Meaning |
| --- | --- | --- |
| RECEIVING | SUBMISSION_RECEIVING | Submission open for evidence intake. No analysis outcome, verdict or safety is implied. |
| RECEIVED | SUBMISSION_RECEIVED | Evidence intake recorded by the server. Analysis is a separate request. No analysis outcome, verdict or safety is implied. |
| PROCESSING | SUBMISSION_PROCESSING | Server-side processing recorded. No analysis outcome, verdict or safety is implied. |
| PROCESSED | SUBMISSION_PROCESSED | Server-side processing recorded as finished. No analysis outcome, verdict or safety is implied. |
| PARTIALLY_FAILED | SUBMISSION_PARTIALLY_FAILED | Some processing failed; items that are not finalized are shown. No analysis outcome, verdict or safety is implied. |
| FAILED | SUBMISSION_FAILED | Processing failed. No analysis outcome, verdict or safety is implied. |
<!-- UXI:submission_states:END -->

<!-- UXI:evaluation_status:BEGIN -->
| Evaluation state | result_availability | Presentation state | Result shown by intake |
| --- | --- | --- | --- |
| QUEUED | NOT_YET_AVAILABLE | ACTION_PENDING | no |
| RUNNING | NOT_YET_AVAILABLE | ACTION_PENDING | no |
| COMPLETED | AVAILABLE | READY | no |
| COMPLETED | REMOVED_UNDER_GOVERNANCE | REMOVED_UNDER_GOVERNANCE | no |
| FAILED | NOT_PRODUCED | ACTION_FAILED | no |
<!-- UXI:evaluation_status:END -->

This follows the UX-001 MEDIUM-1 rule: pending versus failed comes from the authoritative `state` +
`result_availability`, never from an error code alone; a `FAILED` evaluation is never shown as pending. Intake-local
and fallback states are presentation-only:

<!-- UXI:intake_states:BEGIN -->
| Intake presentation state | Meaning |
| --- | --- |
| DRAFT_NOT_SENT | Material exists only on the user's device; nothing has been submitted. |
| TRANSFER_IN_PROGRESS | Bytes are being sent; sending is not storage, verification or analysis. |
| RECEIPT_UNKNOWN | A transfer was interrupted before a response; whether the server stored the bytes is unknown until metadata is re-read. |
| OUTCOME_UNKNOWN | Whether a command was accepted cannot be established from the original outcome or a permitted authoritative read; no blind resubmission. |
| STATE_UNKNOWN_RECONCILE | The response omitted or used an unrecognised lifecycle value; re-read authoritative state; no optimistic state is shown. |
| ANALYSIS_NOT_REQUESTED | Evidence is preserved but no analysis has been requested. |
| STATE_CONFLICT_RECONCILE | A fresh or unordered server state contradicts an earlier observation in a way the lifecycle cannot explain; neither state is shown as confirmed; re-read and reconcile. |
<!-- UXI:intake_states:END -->

An empty evidence list means only that nothing is listed. Sending bytes is not storage, verification or analysis.

**Progress.** Transfer may show an indeterminate indicator or client-measured bytes sent, labelled as sending only.
There is no server-processing or evaluation percentage, no ETA/SLA, and no invented polling interval (NOT YET
SPECIFIED). Completion is claimed only from authoritative state; state changes are announced to assistive technology.

## 7. Errors, retries, duplicates and interruption

Every accepted error of every journey operation is mapped; HTTP status and retryability are the API's own. Field
errors name paths only and never echo submitted values; no internals are shown. `404` preserves existence masking.

<!-- UXI:errors:BEGIN -->
| operationId | Error code | HTTP | Retryability | Presentation state | Recovery | Idempotency key |
| --- | --- | --- | --- | --- | --- | --- |
| createCase | DEPENDENCY_UNAVAILABLE | 503 | RETRYABLE | TEMPORARILY_UNAVAILABLE | RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| createCase | IDEMPOTENCY_IN_PROGRESS | 409 | RETRYABLE | ACTION_PENDING | WAIT_THEN_RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| createCase | IDEMPOTENCY_KEY_REUSED | 409 | RETRY_WITH_CHANGES | CONFLICT | REFRESH_AUTHORITATIVE_STATE | NO_RESUBMISSION |
| createCase | INTERNAL_ERROR | 500 | RETRYABLE | SERVER_ERROR | RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| createCase | INVALID_REQUEST | 400 | RETRY_WITH_CHANGES | ACTION_FAILED | CORRECT_INPUT_AS_NEW_ATTEMPT | NEW_KEY_CORRECTED_REQUEST |
| createCase | RATE_LIMITED | 429 | RETRYABLE | RATE_LIMITED | WAIT_THEN_RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| createCase | UNAUTHENTICATED | 401 | RETRY_WITH_CHANGES | AUTHENTICATION_REQUIRED | REAUTHENTICATE_SAME_PRINCIPAL_THEN_RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| createSubmission | DEPENDENCY_UNAVAILABLE | 503 | RETRYABLE | TEMPORARILY_UNAVAILABLE | RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| createSubmission | FORBIDDEN | 403 | NOT_RETRYABLE | ACCESS_DENIED | STOP_NO_BLIND_RETRY | NO_RESUBMISSION |
| createSubmission | IDEMPOTENCY_IN_PROGRESS | 409 | RETRYABLE | ACTION_PENDING | WAIT_THEN_RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| createSubmission | IDEMPOTENCY_KEY_REUSED | 409 | RETRY_WITH_CHANGES | CONFLICT | REFRESH_AUTHORITATIVE_STATE | NO_RESUBMISSION |
| createSubmission | INTERNAL_ERROR | 500 | RETRYABLE | SERVER_ERROR | RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| createSubmission | INVALID_REQUEST | 400 | RETRY_WITH_CHANGES | ACTION_FAILED | CORRECT_INPUT_AS_NEW_ATTEMPT | NEW_KEY_CORRECTED_REQUEST |
| createSubmission | NOT_FOUND | 404 | NOT_RETRYABLE | NOT_FOUND_OR_NOT_VISIBLE | STOP_NO_BLIND_RETRY | NO_RESUBMISSION |
| createSubmission | RATE_LIMITED | 429 | RETRYABLE | RATE_LIMITED | WAIT_THEN_RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| createSubmission | STATE_CONFLICT | 409 | NOT_RETRYABLE | CONFLICT | REFRESH_AUTHORITATIVE_STATE | NO_RESUBMISSION |
| createSubmission | UNAUTHENTICATED | 401 | RETRY_WITH_CHANGES | AUTHENTICATION_REQUIRED | REAUTHENTICATE_SAME_PRINCIPAL_THEN_RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| createEvidenceUpload | DEPENDENCY_UNAVAILABLE | 503 | RETRYABLE | TEMPORARILY_UNAVAILABLE | RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| createEvidenceUpload | FORBIDDEN | 403 | NOT_RETRYABLE | ACCESS_DENIED | STOP_NO_BLIND_RETRY | NO_RESUBMISSION |
| createEvidenceUpload | IDEMPOTENCY_IN_PROGRESS | 409 | RETRYABLE | ACTION_PENDING | WAIT_THEN_RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| createEvidenceUpload | IDEMPOTENCY_KEY_REUSED | 409 | RETRY_WITH_CHANGES | CONFLICT | REFRESH_AUTHORITATIVE_STATE | NO_RESUBMISSION |
| createEvidenceUpload | INTERNAL_ERROR | 500 | RETRYABLE | SERVER_ERROR | RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| createEvidenceUpload | INVALID_REQUEST | 400 | RETRY_WITH_CHANGES | ACTION_FAILED | CORRECT_INPUT_AS_NEW_ATTEMPT | NEW_KEY_CORRECTED_REQUEST |
| createEvidenceUpload | NOT_FOUND | 404 | NOT_RETRYABLE | NOT_FOUND_OR_NOT_VISIBLE | STOP_NO_BLIND_RETRY | NO_RESUBMISSION |
| createEvidenceUpload | PAYLOAD_TOO_LARGE | 413 | RETRY_WITH_CHANGES | INPUT_LIMIT_EXCEEDED | CORRECT_INPUT_AS_NEW_ATTEMPT | NEW_KEY_CORRECTED_REQUEST |
| createEvidenceUpload | RATE_LIMITED | 429 | RETRYABLE | RATE_LIMITED | WAIT_THEN_RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| createEvidenceUpload | STATE_CONFLICT | 409 | NOT_RETRYABLE | CONFLICT | REFRESH_AUTHORITATIVE_STATE | NO_RESUBMISSION |
| createEvidenceUpload | UNAUTHENTICATED | 401 | RETRY_WITH_CHANGES | AUTHENTICATION_REQUIRED | REAUTHENTICATE_SAME_PRINCIPAL_THEN_RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| createEvidenceUpload | UNSUPPORTED_MEDIA_TYPE | 415 | RETRY_WITH_CHANGES | UNSUPPORTED_INPUT | CORRECT_INPUT_AS_NEW_ATTEMPT | NEW_KEY_CORRECTED_REQUEST |
| putEvidenceContent | DEPENDENCY_UNAVAILABLE | 503 | RETRYABLE | TEMPORARILY_UNAVAILABLE | RETRY_SAME_REQUEST | NOT_APPLICABLE |
| putEvidenceContent | FORBIDDEN | 403 | NOT_RETRYABLE | ACCESS_DENIED | STOP_NO_BLIND_RETRY | NOT_APPLICABLE |
| putEvidenceContent | INTEGRITY_FAILURE | 500 | NOT_RETRYABLE | INTEGRITY_ERROR | START_NEW_EVIDENCE_ITEM | NOT_APPLICABLE |
| putEvidenceContent | INTERNAL_ERROR | 500 | RETRYABLE | SERVER_ERROR | RETRY_SAME_REQUEST | NOT_APPLICABLE |
| putEvidenceContent | INVALID_REQUEST | 400 | RETRY_WITH_CHANGES | ACTION_FAILED | CORRECT_INPUT_AS_NEW_ATTEMPT | NOT_APPLICABLE |
| putEvidenceContent | NOT_FOUND | 404 | NOT_RETRYABLE | NOT_FOUND_OR_NOT_VISIBLE | STOP_NO_BLIND_RETRY | NOT_APPLICABLE |
| putEvidenceContent | PAYLOAD_TOO_LARGE | 413 | RETRY_WITH_CHANGES | INPUT_LIMIT_EXCEEDED | CORRECT_INPUT_AS_NEW_ATTEMPT | NOT_APPLICABLE |
| putEvidenceContent | RATE_LIMITED | 429 | RETRYABLE | RATE_LIMITED | WAIT_THEN_RETRY_SAME_REQUEST | NOT_APPLICABLE |
| putEvidenceContent | STATE_CONFLICT | 409 | NOT_RETRYABLE | CONFLICT | START_NEW_EVIDENCE_ITEM | NOT_APPLICABLE |
| putEvidenceContent | UNAUTHENTICATED | 401 | RETRY_WITH_CHANGES | AUTHENTICATION_REQUIRED | REAUTHENTICATE_SAME_PRINCIPAL_THEN_RETRY_SAME_REQUEST | NOT_APPLICABLE |
| putEvidenceContent | UNSUPPORTED_MEDIA_TYPE | 415 | RETRY_WITH_CHANGES | UNSUPPORTED_INPUT | CORRECT_INPUT_AS_NEW_ATTEMPT | NOT_APPLICABLE |
| finalizeEvidence | DEPENDENCY_UNAVAILABLE | 503 | RETRYABLE | TEMPORARILY_UNAVAILABLE | RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| finalizeEvidence | FORBIDDEN | 403 | NOT_RETRYABLE | ACCESS_DENIED | STOP_NO_BLIND_RETRY | NO_RESUBMISSION |
| finalizeEvidence | IDEMPOTENCY_IN_PROGRESS | 409 | RETRYABLE | ACTION_PENDING | WAIT_THEN_RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| finalizeEvidence | IDEMPOTENCY_KEY_REUSED | 409 | RETRY_WITH_CHANGES | CONFLICT | REFRESH_AUTHORITATIVE_STATE | NO_RESUBMISSION |
| finalizeEvidence | INTEGRITY_FAILURE | 500 | NOT_RETRYABLE | INTEGRITY_ERROR | START_NEW_EVIDENCE_ITEM | NO_RESUBMISSION |
| finalizeEvidence | INTERNAL_ERROR | 500 | RETRYABLE | SERVER_ERROR | RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| finalizeEvidence | INVALID_REQUEST | 400 | RETRY_WITH_CHANGES | ACTION_FAILED | CORRECT_INPUT_AS_NEW_ATTEMPT | NEW_KEY_CORRECTED_REQUEST |
| finalizeEvidence | NOT_FOUND | 404 | NOT_RETRYABLE | NOT_FOUND_OR_NOT_VISIBLE | STOP_NO_BLIND_RETRY | NO_RESUBMISSION |
| finalizeEvidence | RATE_LIMITED | 429 | RETRYABLE | RATE_LIMITED | WAIT_THEN_RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| finalizeEvidence | STATE_CONFLICT | 409 | NOT_RETRYABLE | CONFLICT | REFRESH_AUTHORITATIVE_STATE | NO_RESUBMISSION |
| finalizeEvidence | UNAUTHENTICATED | 401 | RETRY_WITH_CHANGES | AUTHENTICATION_REQUIRED | REAUTHENTICATE_SAME_PRINCIPAL_THEN_RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| getEvidenceMetadata | DEPENDENCY_UNAVAILABLE | 503 | RETRYABLE | TEMPORARILY_UNAVAILABLE | RETRY_SAME_REQUEST | NOT_APPLICABLE |
| getEvidenceMetadata | FORBIDDEN | 403 | NOT_RETRYABLE | ACCESS_DENIED | STOP_NO_BLIND_RETRY | NOT_APPLICABLE |
| getEvidenceMetadata | INTERNAL_ERROR | 500 | RETRYABLE | SERVER_ERROR | RETRY_SAME_REQUEST | NOT_APPLICABLE |
| getEvidenceMetadata | INVALID_REQUEST | 400 | RETRY_WITH_CHANGES | ACTION_FAILED | CORRECT_INPUT_AS_NEW_ATTEMPT | NOT_APPLICABLE |
| getEvidenceMetadata | NOT_FOUND | 404 | NOT_RETRYABLE | NOT_FOUND_OR_NOT_VISIBLE | STOP_NO_BLIND_RETRY | NOT_APPLICABLE |
| getEvidenceMetadata | RATE_LIMITED | 429 | RETRYABLE | RATE_LIMITED | WAIT_THEN_RETRY_SAME_REQUEST | NOT_APPLICABLE |
| getEvidenceMetadata | UNAUTHENTICATED | 401 | RETRY_WITH_CHANGES | AUTHENTICATION_REQUIRED | REAUTHENTICATE_SAME_PRINCIPAL_THEN_RETRY_SAME_REQUEST | NOT_APPLICABLE |
| listEvidence | DEPENDENCY_UNAVAILABLE | 503 | RETRYABLE | TEMPORARILY_UNAVAILABLE | RETRY_SAME_REQUEST | NOT_APPLICABLE |
| listEvidence | FORBIDDEN | 403 | NOT_RETRYABLE | ACCESS_DENIED | STOP_NO_BLIND_RETRY | NOT_APPLICABLE |
| listEvidence | INTERNAL_ERROR | 500 | RETRYABLE | SERVER_ERROR | RETRY_SAME_REQUEST | NOT_APPLICABLE |
| listEvidence | INVALID_REQUEST | 400 | RETRY_WITH_CHANGES | ACTION_FAILED | CORRECT_INPUT_AS_NEW_ATTEMPT | NOT_APPLICABLE |
| listEvidence | NOT_FOUND | 404 | NOT_RETRYABLE | NOT_FOUND_OR_NOT_VISIBLE | STOP_NO_BLIND_RETRY | NOT_APPLICABLE |
| listEvidence | RATE_LIMITED | 429 | RETRYABLE | RATE_LIMITED | WAIT_THEN_RETRY_SAME_REQUEST | NOT_APPLICABLE |
| listEvidence | UNAUTHENTICATED | 401 | RETRY_WITH_CHANGES | AUTHENTICATION_REQUIRED | REAUTHENTICATE_SAME_PRINCIPAL_THEN_RETRY_SAME_REQUEST | NOT_APPLICABLE |
| getSubmission | DEPENDENCY_UNAVAILABLE | 503 | RETRYABLE | TEMPORARILY_UNAVAILABLE | RETRY_SAME_REQUEST | NOT_APPLICABLE |
| getSubmission | FORBIDDEN | 403 | NOT_RETRYABLE | ACCESS_DENIED | STOP_NO_BLIND_RETRY | NOT_APPLICABLE |
| getSubmission | INTERNAL_ERROR | 500 | RETRYABLE | SERVER_ERROR | RETRY_SAME_REQUEST | NOT_APPLICABLE |
| getSubmission | INVALID_REQUEST | 400 | RETRY_WITH_CHANGES | ACTION_FAILED | CORRECT_INPUT_AS_NEW_ATTEMPT | NOT_APPLICABLE |
| getSubmission | NOT_FOUND | 404 | NOT_RETRYABLE | NOT_FOUND_OR_NOT_VISIBLE | STOP_NO_BLIND_RETRY | NOT_APPLICABLE |
| getSubmission | RATE_LIMITED | 429 | RETRYABLE | RATE_LIMITED | WAIT_THEN_RETRY_SAME_REQUEST | NOT_APPLICABLE |
| getSubmission | UNAUTHENTICATED | 401 | RETRY_WITH_CHANGES | AUTHENTICATION_REQUIRED | REAUTHENTICATE_SAME_PRINCIPAL_THEN_RETRY_SAME_REQUEST | NOT_APPLICABLE |
| createEvaluations | DEPENDENCY_UNAVAILABLE | 503 | RETRYABLE | TEMPORARILY_UNAVAILABLE | RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| createEvaluations | FORBIDDEN | 403 | NOT_RETRYABLE | ACCESS_DENIED | STOP_NO_BLIND_RETRY | NO_RESUBMISSION |
| createEvaluations | IDEMPOTENCY_IN_PROGRESS | 409 | RETRYABLE | ACTION_PENDING | WAIT_THEN_RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| createEvaluations | IDEMPOTENCY_KEY_REUSED | 409 | RETRY_WITH_CHANGES | CONFLICT | REFRESH_AUTHORITATIVE_STATE | NO_RESUBMISSION |
| createEvaluations | INTERNAL_ERROR | 500 | RETRYABLE | SERVER_ERROR | RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| createEvaluations | INVALID_REQUEST | 400 | RETRY_WITH_CHANGES | ACTION_FAILED | CORRECT_INPUT_AS_NEW_ATTEMPT | NEW_KEY_CORRECTED_REQUEST |
| createEvaluations | NOT_FOUND | 404 | NOT_RETRYABLE | NOT_FOUND_OR_NOT_VISIBLE | STOP_NO_BLIND_RETRY | NO_RESUBMISSION |
| createEvaluations | RATE_LIMITED | 429 | RETRYABLE | RATE_LIMITED | WAIT_THEN_RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| createEvaluations | STATE_CONFLICT | 409 | NOT_RETRYABLE | CONFLICT | REFRESH_AUTHORITATIVE_STATE | NO_RESUBMISSION |
| createEvaluations | UNAUTHENTICATED | 401 | RETRY_WITH_CHANGES | AUTHENTICATION_REQUIRED | REAUTHENTICATE_SAME_PRINCIPAL_THEN_RETRY_SAME_REQUEST | SAME_KEY_SAME_REQUEST |
| getEvaluation | DEPENDENCY_UNAVAILABLE | 503 | RETRYABLE | TEMPORARILY_UNAVAILABLE | RETRY_SAME_REQUEST | NOT_APPLICABLE |
| getEvaluation | FORBIDDEN | 403 | NOT_RETRYABLE | ACCESS_DENIED | STOP_NO_BLIND_RETRY | NOT_APPLICABLE |
| getEvaluation | INTERNAL_ERROR | 500 | RETRYABLE | SERVER_ERROR | RETRY_SAME_REQUEST | NOT_APPLICABLE |
| getEvaluation | INVALID_REQUEST | 400 | RETRY_WITH_CHANGES | ACTION_FAILED | CORRECT_INPUT_AS_NEW_ATTEMPT | NOT_APPLICABLE |
| getEvaluation | NOT_FOUND | 404 | NOT_RETRYABLE | NOT_FOUND_OR_NOT_VISIBLE | STOP_NO_BLIND_RETRY | NOT_APPLICABLE |
| getEvaluation | RATE_LIMITED | 429 | RETRYABLE | RATE_LIMITED | WAIT_THEN_RETRY_SAME_REQUEST | NOT_APPLICABLE |
| getEvaluation | UNAUTHENTICATED | 401 | RETRY_WITH_CHANGES | AUTHENTICATION_REQUIRED | REAUTHENTICATE_SAME_PRINCIPAL_THEN_RETRY_SAME_REQUEST | NOT_APPLICABLE |
<!-- UXI:errors:END -->

- **Request identity is not authorization (MEDIUM-2).** The Idempotency-Key is invisible protocol machinery scoped
  to principal + operation + target resource (OPS-001); it is never authorization. After `UNAUTHENTICATED`, the same
  principal reauthenticates and retries the **same semantic request with the same key** — credential renewal never
  creates a new logical command. If a different principal signs in, the original attempt stops; a new request needs an
  explicit user decision. A corrected request uses a new key. `IDEMPOTENCY_IN_PROGRESS` means wait;
  `IDEMPOTENCY_KEY_REUSED` means refresh state; not-retryable errors are never retried automatically. Retry limits and
  backoff values are NOT YET SPECIFIED.
- **Finite window.** The original outcome is returned only within OPS-001's finite, server-set idempotency active
  window (NOT YET SPECIFIED). After expiry the server treats the key as a new request, so the client reconciles before
  any resubmission; no expiry guarantee is promised.
- **Write-once bytes.** An identical re-PUT is a no-op; different bytes after content exists → `STATE_CONFLICT`, and
  the recovery is a new evidence item. A finalize `INTEGRITY_FAILURE` likewise needs a new item.
- **Duplicates.** Same key + same request returns the original outcome within the active window. A deliberate resubmission creates a new
  submission and new evidence items. There is no global digest deduplication and no "already analysed" claim from a
  digest match.
- **Limits.** Size limit and accepted media types are configuration (NOT YET SPECIFIED) with no discovery operation;
  the UI never invents values. Client checks are advisory; the server validates media beyond extension.

<!-- UXI:recovery:BEGIN -->
| api upload_state | Readiness evidence | Recovery action | Resend bytes | May finalize | New item | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| AWAITING_CONTENT | ANY | RESEND_SAME_ORIGINAL_BYTES | ORIGINAL_BYTES | no | NO | The first PUT is allowed while AWAITING_CONTENT. |
| PROCESSING | PUT_SUCCESS_OBSERVED | REQUEST_FINALIZATION_AFTER_OBSERVED_PUT_SUCCESS | NOT_OFFERED | yes | NO | This client observed its own successful PUT for this item and attempt. |
| PROCESSING | NONE | RECHECK_STATE_FINALIZATION_UNAVAILABLE | NOT_OFFERED | no | EXPLICIT_USER_DECISION_ONLY | PROCESSING may be CONTENT_PENDING or FAILED_RETRYABLE; readiness is unobservable. |
| FINALIZED | ANY | NONE_ALREADY_PRESERVED | NOT_OFFERED | no | NO | The server reported FINALIZED; evidence is preserved, not analysed. |
| REJECTED | ANY | START_NEW_EVIDENCE_ITEM | NOT_OFFERED | no | EXPLICIT_USER_DECISION_ONLY | A new item is an explicit user decision; the original may still be reconciled by the server (possible duplicate). |
| DELETION_PENDING | ANY | NONE_GOVERNED_REMOVAL | NOT_OFFERED | no | NO | Governed removal; no re-upload. |
| DELETED | ANY | NONE_GOVERNED_REMOVAL | NOT_OFFERED | no | NO | Governed removal; no re-upload. |
<!-- UXI:recovery:END -->

After an interruption (network loss, tab close, mobile backgrounding) the client re-reads `getEvidenceMetadata`,
`listEvidence`, `getSubmission` and `getEvaluation`; it never assumes completion and never downloads evidence content to
resume. There is no resumable partial transfer. Recovery actions come from a governed action table (each action fixes
whether finalization may be requested, whether bytes may be resent, whether a new item may be created and whether the
item is presented as finalized) and every action requires reconciliation first:

- `AWAITING_CONTENT`: resend the original bytes (the first PUT is allowed in this state);
- `PROCESSING` **with** an observed successful PUT: request finalization;
- `PROCESSING` **without** that evidence: re-check state; finalization is unavailable; a new item only by explicit user
  decision. Re-PUT is not offered: the API guarantees a no-op only for identical bytes after content exists, and
  `CONTENT_PENDING` / `FAILED_RETRYABLE` cannot be told apart (API-owner dependency, §11);
- `FINALIZED`: nothing to do; `REJECTED`: a new item by explicit user decision; governed-deletion states: no action and
  never an automatic replacement item.

If metadata cannot be read the state is `OUTCOME_UNKNOWN`. "Cancel" stops the local transfer only; the server item
remains and no removal is claimed — removal is a governed deletion request (P7-WP5). Local draft persistence is not
specified.

**Unknown outcome.** When a command was sent but no response arrived, the client (1) retries with the same key and the
same request if it still holds both in memory, (2) otherwise reconciles through the command's reconciliation binding,
and (3) stops in `OUTCOME_UNKNOWN` when neither establishes the outcome. Each binding (below) is derived from the API
catalog: the read is a public metadata GET whose representation is the same resource type the command affects, it is
available to every role allowed to issue the command, it is case-access authorized and carries no content gate, and
each path identifier comes from the original command's path or an earlier authoritative response — never from the
lost response. Identifier meaning comes from the API resource catalog (each resource's canonical identifier parameter and
representation schema), never from structural UUID validity: a parent identifier (`case_id`, `submission_id`) only
scopes a collection and can never stand in for the created child, and a field from an earlier response must identify the
same resource as the path parameter it fills (`createCase.case_id` can never become a `submission_id`). Creation
commands can never claim exact identity, because the new resource's identifier exists only in the lost response, and
every scoping parameter of the original command must survive as a path parameter or a supported filter (for
`createEvaluations`, the `submission_id` filter on `listCaseEvaluations` is mandatory). Collection reads only present permitted candidates and never bind one automatically. A required
identifier that is not held, a failed or denied read, or no unambiguous match stops in `OUTCOME_UNKNOWN`. There is no
blind resubmission with a new key, no new lookup API and no local persistence guarantee; a new request after
`OUTCOME_UNKNOWN` is an explicit user decision, warned as a possible duplicate.

<!-- UXI:unknown_outcome:BEGIN -->
| Command | Reconciled resource | Read | Method / path | Response | Read roles | Authorization | Content gate | Identity | Identifiers (role → resource, source) | Required scope filters | Outcomes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| createCase | Case | listCases | GET /api/v1/cases | CaseListResponse | USER, ANALYST | CASE_ACCESS | NONE | UNSCOPED_CANDIDATES | — | — | zero: OUTCOME_UNKNOWN, one: OUTCOME_UNKNOWN_CANDIDATE_SHOWN_NO_BINDING, many: OUTCOME_UNKNOWN_CANDIDATES_SHOWN_NO_BINDING |
| createSubmission | Submission | listSubmissions | GET /api/v1/cases/{case_id}/submissions | SubmissionListResponse | USER, ANALYST | CASE_ACCESS | NONE | PARENT_SCOPED_CANDIDATES | case_id (PARENT_SCOPE → Case, ORIGINAL_COMMAND_PATH) | — | zero: OUTCOME_UNKNOWN, one: OUTCOME_UNKNOWN_CANDIDATE_SHOWN_NO_BINDING, many: OUTCOME_UNKNOWN_CANDIDATES_SHOWN_NO_BINDING |
| createEvidenceUpload | EvidenceItem | listEvidence | GET /api/v1/submissions/{submission_id}/evidence | EvidenceListResponse | USER, ANALYST | CASE_ACCESS | NONE | PARENT_SCOPED_CANDIDATES | submission_id (PARENT_SCOPE → Submission, ORIGINAL_COMMAND_PATH) | — | zero: OUTCOME_UNKNOWN, one: OUTCOME_UNKNOWN_CANDIDATE_SHOWN_NO_BINDING, many: OUTCOME_UNKNOWN_CANDIDATES_SHOWN_NO_BINDING |
| putEvidenceContent | EvidenceItem | getEvidenceMetadata | GET /api/v1/evidence/{evidence_id} | EvidenceMetadataResponse | USER, ANALYST | CASE_ACCESS | NONE | EXACT_TARGET | evidence_id (TARGET → EvidenceItem, ORIGINAL_COMMAND_PATH) | — | found: RENDER_RETURNED_AUTHORITATIVE_STATE, not_found_or_denied: OUTCOME_UNKNOWN |
| finalizeEvidence | EvidenceItem | getEvidenceMetadata | GET /api/v1/evidence/{evidence_id} | EvidenceMetadataResponse | USER, ANALYST | CASE_ACCESS | NONE | EXACT_TARGET | evidence_id (TARGET → EvidenceItem, ORIGINAL_COMMAND_PATH) | — | found: RENDER_RETURNED_AUTHORITATIVE_STATE, not_found_or_denied: OUTCOME_UNKNOWN |
| createEvaluations | Evaluation | listCaseEvaluations | GET /api/v1/cases/{case_id}/evaluations | EvaluationListResponse | USER, ANALYST | CASE_ACCESS | NONE | PARENT_SCOPED_CANDIDATES | case_id (PARENT_SCOPE → Case, PRIOR_AUTHORITATIVE_RESPONSE getSubmission.case_id) | submission_id (→ Submission, ORIGINAL_COMMAND_PATH) | zero: OUTCOME_UNKNOWN, one: OUTCOME_UNKNOWN_CANDIDATE_SHOWN_NO_BINDING, many: OUTCOME_UNKNOWN_CANDIDATES_SHOWN_NO_BINDING |
<!-- UXI:unknown_outcome:END -->

**Scenarios.** Expected outcomes are authored independently and pinned in the validator (UXI-74); the reference model
must reproduce every one (UXI-69).

<!-- UXI:scenarios:BEGIN -->
| Scenario | Situation | operationId | Returned state | Companion | Previously shown | Provenance | Overlap | Presented as |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SC-01 | identical PUT retry returns FINALIZED after PROCESSING was shown | putEvidenceContent | FINALIZED | absent | PROCESSING | FRESH | no | EVIDENCE_FINALIZED |
| SC-02 | 202 batch already reports COMPLETED/AVAILABLE | createEvaluations | COMPLETED | AVAILABLE | — | — | no | READY |
| SC-03 | 202 batch already reports FAILED/NOT_PRODUCED | createEvaluations | FAILED | NOT_PRODUCED | — | — | no | ACTION_FAILED |
| SC-04 | existing case under review (prior evaluations exist) | createCase | UNDER_REVIEW | absent | — | — | no | CASE_UNDER_REVIEW |
| SC-05 | repeated finalize returns advanced FINALIZED | finalizeEvidence | FINALIZED | absent | PROCESSING | FRESH | no | EVIDENCE_FINALIZED |
| SC-06 | client believes sent; server reports AWAITING_CONTENT | getEvidenceMetadata | AWAITING_CONTENT | absent | — | — | no | EVIDENCE_AWAITING_CONTENT |
| SC-07 | response omits the lifecycle field | putEvidenceContent | — | absent | — | — | no | STATE_UNKNOWN_RECONCILE |
| SC-08 | submission response has an unrecognised lifecycle value | getSubmission | ARCHIVED_FUTURE_VALUE | absent | — | — | no | STATE_UNKNOWN_RECONCILE |
| SC-09 | known-stale PROCESSING response after a trusted FINALIZED observation | putEvidenceContent | PROCESSING | absent | FINALIZED | KNOWN_STALE | no | EVIDENCE_FINALIZED |
| SC-10 | PROCESSING covering CONTENT_PENDING is not receipt | getEvidenceMetadata | PROCESSING | absent | — | — | no | EVIDENCE_PROCESSING_NOT_FINALIZED |
| SC-11 | PROCESSING covering FAILED_RETRYABLE is not receipt or verification | getEvidenceMetadata | PROCESSING | absent | — | — | no | EVIDENCE_PROCESSING_NOT_FINALIZED |
| SC-12 | interrupted PUT without response | putEvidenceContent | — | absent | — | — | no | RECEIPT_UNKNOWN |
| SC-13 | interrupted createSubmission, reconciliation inconclusive | createSubmission | — | absent | — | — | no | OUTCOME_UNKNOWN |
| SC-14 | fresh DELETION_PENDING after FINALIZED | getEvidenceMetadata | DELETION_PENDING | absent | FINALIZED | FRESH | no | EVIDENCE_REMOVAL_PENDING |
| SC-15 | 202 batch reports QUEUED | createEvaluations | QUEUED | NOT_YET_AVAILABLE | — | — | no | ACTION_PENDING |
| SC-16 | COMPLETED with null result_availability | getEvaluation | COMPLETED | null | — | — | no | STATE_UNKNOWN_RECONCILE |
| SC-17 | COMPLETED with result_availability missing | getEvaluation | COMPLETED | absent | — | — | no | STATE_UNKNOWN_RECONCILE |
| SC-18 | COMPLETED with an unknown result_availability value | getEvaluation | COMPLETED | MAYBE_LATER | — | — | no | STATE_UNKNOWN_RECONCILE |
| SC-19 | cached FINALIZED then fresh PROCESSING | getEvidenceMetadata | PROCESSING | absent | FINALIZED | FRESH | no | STATE_CONFLICT_RECONCILE |
| SC-20 | cached FINALIZED then fresh AWAITING_CONTENT | getEvidenceMetadata | AWAITING_CONTENT | absent | FINALIZED | FRESH | no | STATE_CONFLICT_RECONCILE |
| SC-21 | unordered COMPLETED/AVAILABLE versus FAILED/NOT_PRODUCED | getEvaluation | FAILED | NOT_PRODUCED | COMPLETED\|AVAILABLE | UNORDERED | no | STATE_CONFLICT_RECONCILE |
| SC-22 | fresh REJECTED after FINALIZED (later integrity failure) | getEvidenceMetadata | REJECTED | absent | FINALIZED | FRESH | no | EVIDENCE_REJECTED |
| SC-23 | fresh DELETED after FINALIZED | getEvidenceMetadata | DELETED | absent | FINALIZED | FRESH | no | EVIDENCE_REMOVED |
| SC-24 | valid terminal evaluation response | getEvaluation | FAILED | NOT_PRODUCED | RUNNING\|NOT_YET_AVAILABLE | FRESH | no | ACTION_FAILED |
| SC-25 | evidence response with an unrecognised lifecycle value | getEvidenceMetadata | QUARANTINED_PUBLIC_FUTURE | absent | — | — | no | STATE_UNKNOWN_RECONCILE |
| SC-26 | evaluation response missing its state component | getEvaluation | — | AVAILABLE | — | — | no | STATE_UNKNOWN_RECONCILE |
| SC-27 | COMPLETED with NOT_PRODUCED (inconsistent combination) | getEvaluation | COMPLETED | NOT_PRODUCED | — | — | no | STATE_CONFLICT_RECONCILE |
| SC-28 | known-stale REJECTED after a trusted PROCESSING observation (lifecycle-inconsistent) | getEvidenceMetadata | REJECTED | absent | PROCESSING | KNOWN_STALE | no | STATE_CONFLICT_RECONCILE |
| SC-29 | fresh FINALIZED after REJECTED (ORPHAN_DETECTED reconciled to FINALIZED) | getEvidenceMetadata | FINALIZED | absent | REJECTED | FRESH | no | EVIDENCE_FINALIZED |
| SC-30 | send-order 'stale' FINALIZED after REJECTED with overlapping requests | getEvidenceMetadata | FINALIZED | absent | REJECTED | KNOWN_STALE | yes | STATE_CONFLICT_RECONCILE |
| SC-31 | unordered REJECTED versus FINALIZED (both directions reachable) | getEvidenceMetadata | FINALIZED | absent | REJECTED | UNORDERED | no | STATE_CONFLICT_RECONCILE |
| SC-32 | overlapping send-order 'stale' PROCESSING after FINALIZED (lifecycle order still unambiguous) | getEvidenceMetadata | PROCESSING | absent | FINALIZED | KNOWN_STALE | yes | EVIDENCE_FINALIZED |
| SC-33 | overlapping FRESH FINALIZED after REJECTED | getEvidenceMetadata | FINALIZED | absent | REJECTED | FRESH | yes | STATE_CONFLICT_RECONCILE |
| SC-34 | overlapping FRESH REJECTED after FINALIZED | getEvidenceMetadata | REJECTED | absent | FINALIZED | FRESH | yes | STATE_CONFLICT_RECONCILE |
| SC-35 | overlapping KNOWN_STALE REJECTED after FINALIZED | getEvidenceMetadata | REJECTED | absent | FINALIZED | KNOWN_STALE | yes | STATE_CONFLICT_RECONCILE |
| SC-36 | overlapping FRESH FINALIZED after PROCESSING (lifecycle admits one direction only) | getEvidenceMetadata | FINALIZED | absent | PROCESSING | FRESH | yes | EVIDENCE_FINALIZED |
| SC-37 | overlapping FRESH DELETION_PENDING after FINALIZED (governed deletion, one direction) | getEvidenceMetadata | DELETION_PENDING | absent | FINALIZED | FRESH | yes | EVIDENCE_REMOVAL_PENDING |
<!-- UXI:scenarios:END -->

## 8. Metadata versus content

The metadata preview shows only `EvidenceMetadataResponse` fields: no bytes and no storage locator.
`display_filename` is untrusted, shown as escaped text and never used as a path or markup. A `content_link` or the
`viewer_access.can_view_evidence_content` hint is not authorization. The user's own unsent input may be echoed back
before submission; after upload, content is displayed only through `getEvidenceContent` with content permission, which
is P7-WP4. Protected content is never fetched merely to hide it, and narrow layouts never expose more than wide ones.

## 9. Supported instruction requirements

These are required meanings, not final copy. Consent capture is not designed: no accepted API field exists (§11).

<!-- UXI:instructions:BEGIN -->
| Instruction requirement | Required meaning (not final copy) |
| --- | --- |
| INTAKE_IS_NOT_A_VERDICT | Uploading and preserving evidence is not an analysis result and never means safe. |
| ANALYSIS_IS_SEPARATE | Analysis is requested as a separate step and its result is presented separately. |
| URL_NOT_VISITED | A submitted URL is treated as text evidence; TrustLens does not open, fetch or preview it. |
| ENGLISH_DETECTION_SCOPE | Current detection scope is English (ADR-0014); other languages are not evaluated as safe. |
| ORIGINAL_PRESERVED | The original material is preserved unmodified; corrections never edit it. |
| SENSITIVE_MATERIAL_HANDLING | Submitted material is sensitive evidence; visibility follows permissions. |
| NO_RETENTION_PERIOD_STATED | Retention wording stays policy-neutral; no period is stated while OI-05 is open. |
<!-- UXI:instructions:END -->

## 10. Accessibility and mobile

Capture is keyboard-operable with a non-drag-and-drop alternative; controls are labelled; an error summary is linked to
each field and receives focus; status changes are announced and every status has text (no colour-only meaning); no time
limit and no hover-only interaction. On mobile the platform file picker is the only capture path, there is no camera
capture (images are Post-MVP), permissions behave identically across form factors, breakpoints are NOT YET SPECIFIED,
and backgrounding follows the interruption rules. These are design requirements; no accessibility conformance is
claimed. Detailed patterns are P7-WP6.

## 11. Non-goals, unresolved decisions and carryovers

Non-goals: no frontend or runtime; no new API capability; no content viewer, result, re-analysis, correction, replay,
report or deletion flow; no image/document capture; no consent capture; no client scoring, probability, verdict,
deduplication or language gating. Unsupported or non-English input is never treated as safe; the server identifies
language, and the detailed experience is P7-WP6.

<!-- UXI:decisions:BEGIN -->
| Unresolved decision | Owner | Status |
| --- | --- | --- |
| Accepted media types and size limit are configuration with no discovery operation; how users learn limits before upload | API owner / Phase 9 configuration (governed API revision if a discovery operation is needed) | DEFERRED |
| Consent / acknowledgement capture has no accepted API field | Sponsor + legal/governance with API owner | DEFERRED |
| Email source accepted media type(s) | API owner / Phase 9 configuration | DEFERRED |
| Whether intake offers an AI-assisted analysis_mode choice | Programme / P7-WP3 with AI governance | DEFERRED |
| Local draft persistence on the device (sensitive content at rest in the browser) | Security Architect / Phase 9 | DEFERRED |
| Abandoned AWAITING_CONTENT items: user-visible cleanup path beyond governed deletion | P7-WP5 / API owner | DEFERRED |
| Polling cadence, retry limits and backoff values | Phase 9 implementation profile (OPS-001 parameters) | DEFERRED |
| Dedicated artifact_kind for user context (currently OTHER + vendor media type) | Next DATA-001-WP2 vocabulary revision (API-001 §41 #3) | DEFERRED |
| No accepted API field distinguishes PROCESSING sub-states (CONTENT_PENDING / FAILED_RETRYABLE): re-PUT and finalize behaviour after an interrupted PUT, or a readiness indicator, needs API-owner clarification; until then finalization is unavailable without an observed successful PUT | API owner (governed API revision if required) | DEFERRED |
<!-- UXI:decisions:END -->

<!-- UXI:carryovers:BEGIN -->
| Item | Status | Owner |
| --- | --- | --- |
| G-09 | OPEN | Phase 10 (testing/evaluation; QA Lead) with Sponsor for any corpus access |
| OI-05 | OPEN | Sponsor + legal/governance |
| ASM-002 | UNCONFIRMED / PROVISIONAL | Sponsor / Programme |
| P6-WP7-LOW-1 | OPEN / NON-BLOCKING | Next governed Phase-6 snapshot revision / Programme governance |
<!-- UXI:carryovers:END -->

No tenant field or selector is introduced. No retention period is stated. G-09 remains OPEN, so there is no detection
accuracy or effectiveness claim. There is no frontend, API implementation, production-readiness, usability-testing or
accessibility-conformance claim. `ENGINE_VERSION = 1.0.0` is unchanged.

## 12. Builder observations (not independent review)

1. (Review LOW-2, carried.) UX-001 / GATE-026 status rows and `validate_ux_foundation.py` (UXF-01/02) still pin "APPROVED … REMOTE CI + MERGE
   PENDING" although PR #34 is merged. Recording P7-WP1 as CLOSED will need a governed lifecycle correction like the
   Phase-6 post-merge finalization; P7-WP2 does not modify P7-WP1 artifacts.
2. UX-001 handoff rows still read "NOT STARTED" for P7-WP2; they are closure-time history in an accepted artifact.
3. This validator ties its status pin to the recorded lifecycle (CANDIDATE → APPROVED → CLOSED with evidence) and has
   no file-existence guard, so later Phase-7 work cannot be blocked by its mere existence (P6C-46 lesson).
4. The P7-WP1 foundation is checked semantically (handoff scope, presentation states, surfaces, evaluation mapping),
   not by hash pin, so a governed P7-WP1 bookkeeping change does not break this validator; freeze of P7-WP1 files is a
   builder git-diff obligation reported in the STOP REPORT.
