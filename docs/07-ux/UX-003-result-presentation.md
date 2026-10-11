# UX-003 — Detection result presentation

| Field | Value |
| --- | --- |
| Document ID | UX-003 |
| Version | 0.1 |
| Status | P7-WP3 RESULT PRESENTATION CLOSED |
| Phase | Phase 7 — UX, Evidence & Reporting Design |
| Work package | P7-WP3 |
| Owner role | Product / Result UX |
| Baseline | 47f57d1d8f2b9f2ddedb2b438bc40ac3f32e4a70 (P7-WP2 closure merge, PR #36) |
| Gate | [GATE-028](../00-program/GATE-028-phase-7-result-presentation.md) |
| Foundation | [UX-001](UX-001-experience-foundation-information-architecture.md) (consumed, not modified); [UX-002](UX-002-submission-evidence-intake.md) (consumed, not modified) |
| Machine contract | [ux-result-v1.json](../../contracts/ux/ux-result-v1.json) |
| Structural schema | [ux-result-contract.schema.json](../../contracts/ux/ux-result-contract.schema.json) |
| Builder validator | [validate_ux_result.py](../../knowledge/validation/validate_ux_result.py) (UXR-01…UXR-78) |
| Last updated | 2026-10-11 |

## 1. Authority and scope

UX-003 is the P7-WP3 UX contract for presenting one immutable `DetectionResult`. The first independent
review returned REQUEST_CHANGES (BLOCKER 0 / HIGH 1 / MEDIUM 5). The targeted re-review (round 2) closed four of those
findings and returned REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 3 / LOW 1 / INFO 1). Round 3 closed the rule-identity
and field-presence findings and returned REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 1 / INFO 1), and rounds 4
and 5 returned REQUEST_CHANGES with the same counts on the review-table structure and the heading grammar. Round 6
returned REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 2 / LOW 1 / INFO 1) on table recognition and container context,
and round 7 returned REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 2 / LOW 2 / INFO 1) on native-GFM precedence and list
containers. After the builder's correction, the final independent review (round 8) returned APPROVE (BLOCKER 0 / HIGH 0 /
MEDIUM 0 / LOW 1 / INFO 1), and the contract was CLOSED after PR #37 merged (GATE-028 §8). It consumes, and changes nothing
in:

- the closed Phase-6 contracts (PHASE-6-CLOSURE: PHASE 6 CLOSED);
- the accepted API catalog and OpenAPI encoding (exactly the bytes pinned by the Phase-6 snapshot);
- DATA-001 / DATA-001-WP2;
- the promoted Phase-3 `detection-result` and `rule-evaluation-result` schemas and the governed action policy v1.0.0;
- DET-001 and DET-001-WP5/WP6;
- UX-001 (P7-WP1) and the closed UX-002 (P7-WP2).

It adds no endpoint, API field, HTTP status, error code, persisted concept, frontend, route, component, copy deck,
server, migration or network integration.

The baseline is the P7-WP2 closure merge (PR #36, `47f57d1…`); its merge-commit CI run succeeded on both required
jobs. UX-001 / GATE-026 still carry their pre-merge "remote CI + merge pending" status rows. That is historical
wording and is not rewritten here. The machine-readable companion encodes every rule below, and the marked tables
are exact projections checked by UXR-59. Automated checks are not independent review, usability testing,
accessibility evaluation or runtime authorization testing.

The owned scope is exactly the UX-001 P7-WP3 handoff:

<!-- UXR:scope:BEGIN -->
| Owned P7-WP3 scope (UX-001 handoff) |
| --- |
| DetectionResult presentation |
| Classification labels |
| Risk/severity/confidence |
| Matched and indeterminate rules |
| Negative indicators |
| Uncertainty |
| Recommended actions |
| Explanation hierarchy |
<!-- UXR:scope:END -->

Each requested item maps onto one handoff item:

<!-- UXR:request_mapping:BEGIN -->
| Requested item | UX-001 handoff item |
| --- | --- |
| DetectionResult presentation | DetectionResult presentation |
| Classification labels | Classification labels |
| Risk, severity and confidence | Risk/severity/confidence |
| Matched and indeterminate rules | Matched and indeterminate rules |
| Negative and mitigating indicators | Negative indicators |
| Uncertainty and limitations | Uncertainty |
| Recommended actions | Recommended actions |
| Explanation hierarchy and provenance | Explanation hierarchy |
<!-- UXR:request_mapping:END -->

Deferred to their owners (handoff only, not started):

<!-- UXR:deferred:BEGIN -->
| Deferred item | Owner |
| --- | --- |
| Evidence content viewing, break-glass, review assignment, adjudication and C4 rationale | P7-WP4 |
| Reports, replay, re-analysis, user correction and governed deletion workflows | P7-WP5 |
| Detailed accessibility and responsive patterns, the unsupported-language experience and enrichment presentation | P7-WP6 |
| Frontend, API and runtime implementation | Phase 9 |
<!-- UXR:deferred:END -->

Differences between the request and the accepted API are recorded rather than designed around. These five items are
open decisions (§16):

1. Negative and mitigating indicator identities are not exposed by `DetectionResultResponse` v1.
2. Supporting observations and spans are not exposed.
3. Per-action reason identifiers are not exposed.
4. Priority is not exposed.
5. AI provenance comes only from `EvaluationResponse.ai_usage`.

### Review history and lifecycle

P7-WP3 is **CLOSED**: independently approved in round 8 (GATE-028 §6) and closed after PR #37 merged with both required
CI jobs successful (GATE-028 §8). Rounds 1 to 7 (GATE-028 §6) returned
REQUEST_CHANGES, and round 8 (GATE-028 §6) returned APPROVE. HIGH-1, MEDIUM-2, MEDIUM-4 and MEDIUM-5 were closed in round
2; MEDIUM-3, MEDIUM-3-R2 and R2-MEDIUM-1 were closed in round 3. The review-governance findings (MEDIUM-1, MEDIUM-1-R2,
R3-MEDIUM-1, R4-MEDIUM-1, R5-MEDIUM-1) and the round-6/7 findings (R6- and R7-MEDIUM-1/2) were closed in round 8. The
carried LOW (clause-detection heuristic, P7-WP3) and INFO (Phase-3 matched-rule counting, Detection owner) stay open and
non-blocking. The recorded merge evidence (PR #37, PR-head run 38116825962, merge-commit run 38118409062) is pinned in
the validator; the offline validator checks exact agreement with that pin and does not contact GitHub. Approval and
closure are fail-closed:

- **Independence:** a review record counts only when its kind is an independent review kind, its reviewer role is an
  independent reviewer role distinct from the P7-WP3 builder, its evidence source is the permitted programme-supplied
  classification, and it cites a GATE-028 section that is an independent-review record. That bounded section must
  itself hold exactly one row for the round in a real review table (the exact review header and separator), equal to the structured entry (round, kind,
  decision, counts, reviewer role, evidence source and reference). The section runs from its real `## N.` heading to the
  next real heading of the same or a higher level, numbered or not, so an unnumbered `## Appendix` ends it. Fenced code
  blocks and HTML comments are not Markdown content for this purpose: heading-like text inside them neither opens nor
  closes a section, and table rows inside them are not evidence. A matching title, or a matching record elsewhere in
  GATE-028, is not enough (UXR-76).
- **Table structure:** lines keep their positions and classes; excluded content is never deleted. A review table is one
  uninterrupted run of table lines (exact header, delimiter row, data rows); any blank line, text line, fenced block or
  HTML comment ends it, so separated blocks can never be spliced into a record. Any other visible review-looking line
  for the same round in the section is rejected as a duplicate. Fences follow GFM: an opener is 3+ backticks or tildes
  (at most 3 spaces indent); a backtick opener whose info string contains a backtick is ordinary text, not a fence; a
  closer repeats the opener's character at least as often with nothing after it.
- **Heading grammar (round 5):** a numbered reference `GATE-028 §N` resolves only to a real ATX heading `## N. title`;
  a setext heading never satisfies it. Setext headings still end sections, but only when the underline follows a
  top-level paragraph (single- or multi-line). A list item, blockquote, table line, code block, lazy continuation or
  thematic break never becomes a setext heading, and `---` in those contexts is a thematic break, which neither
  starts nor ends a section. A thematic break takes precedence over a list marker, and an ordered item interrupts a
  paragraph only when it starts at 1. Supported Markdown subset for this check: ATX and setext headings, paragraphs
  with lazy continuation, list items, blockquotes, thematic breaks, pipe tables, indented and fenced code, and HTML
  comments. Nested containers, link reference definitions and other raw HTML blocks are not modelled. During
  development the heading structure was compared with an independent CommonMark-with-tables parser
  (markdown-it-py, outside the project dependencies) and matched on every case checked.
- **Block structure (round 6):** one bounded parser produces both headings and tables. A pipe alone never makes a
  table: a table starts only at a header line followed by a delimiter row with the same number of cells, each of
  hyphens with optional colons. Otherwise the line is ordinary paragraph text and can still be underlined into a
  setext heading that ends the section. Tables are recognised only at top level; lines that lazily continue a
  blockquote or list item stay in that container, as do indented list continuations. Review evidence comes only from
  such top-level tables inside the referenced section. Every row must be a pipe row, and a malformed row disqualifies
  the table. A complete table that follows a blockquote or list item after a blank line is recognised normally. Table and container
  boundaries were checked against the same independent parser during development.
- **Native GFM precedence and containers (round 7):** native cmark-gfm is the structural reference for this subset
  (markdown-it differs on one-column tables). Indented code (4+ columns) is recognised before the table extension, so
  it never supplies a review header or delimiter. A delimiter that is a bare setext underline (`---`, `===`) makes a
  setext heading, so `| Appendix |` + `---` is a heading and `| Appendix |` + `| --- |` is a one-column table. A table
  row indented 4+ columns ends the table. A list item owns every following line indented at least its content offset,
  whatever it is (thematic breaks, setext underlines, fences, comments, nested lists and tables), plus lazy paragraph
  text while its paragraph is open. A thematic break inside an item never ends the list, while a less-indented line
  after a closed paragraph does. Blockquotes own `>` lines and lazy text of an open paragraph. Only top-level tables
  inside the referenced section count. Two governance rules are intentionally stricter than GFM and fail closed: a
  review table with a non-pipe row is disqualified, and fences or comments between table lines end the table. A builder self-review,
  builder-asserted evidence or a non-review section never approves (UXR-06, UXR-67). Offline validation cannot
  authenticate a reviewer; it only refuses records that are not classified as independent.
- **Approval** requires an exact `APPROVE` decision in the structured review history, with BLOCKER/HIGH/MEDIUM at 0
  and a resolvable GATE-028 record.
- **CLOSED** additionally requires structured merge evidence equal to the record that a governed post-merge step
  pins in the validator after independent checking. That record is currently `None`.

<!-- UXR:review_history:BEGIN -->
| Round | Kind | Decision | BLOCKER | HIGH | MEDIUM | LOW | INFO | Reviewer role | Evidence source | Record |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | INITIAL_INDEPENDENT_REVIEW | REQUEST_CHANGES | 0 | 1 | 5 | 0 | 0 | Independent reviewer | Independent review result supplied to the builder by the programme | GATE-028 §6 |
| 2 | TARGETED_INDEPENDENT_REREVIEW | REQUEST_CHANGES | 0 | 0 | 3 | 1 | 1 | Independent reviewer | Independent review result supplied to the builder by the programme | GATE-028 §6 |
| 3 | TARGETED_INDEPENDENT_REREVIEW | REQUEST_CHANGES | 0 | 0 | 1 | 1 | 1 | Independent reviewer | Independent review result supplied to the builder by the programme | GATE-028 §6 |
| 4 | TARGETED_INDEPENDENT_REREVIEW | REQUEST_CHANGES | 0 | 0 | 1 | 1 | 1 | Independent reviewer | Independent review result supplied to the builder by the programme | GATE-028 §6 |
| 5 | TARGETED_INDEPENDENT_REREVIEW | REQUEST_CHANGES | 0 | 0 | 1 | 1 | 1 | Independent reviewer | Independent review result supplied to the builder by the programme | GATE-028 §6 |
| 6 | TARGETED_INDEPENDENT_REREVIEW | REQUEST_CHANGES | 0 | 0 | 2 | 1 | 1 | Independent reviewer | Independent review result supplied to the builder by the programme | GATE-028 §6 |
| 7 | TARGETED_INDEPENDENT_REREVIEW | REQUEST_CHANGES | 0 | 0 | 2 | 2 | 1 | Independent reviewer | Independent review result supplied to the builder by the programme | GATE-028 §6 |
| 8 | FINAL_INDEPENDENT_REVIEW | APPROVE | 0 | 0 | 0 | 1 | 1 | Independent reviewer | Independent review result supplied to the builder by the programme | GATE-028 §6 |
<!-- UXR:review_history:END -->

## 2. Result surface and API binding

The result surface is UX-001's `UX-RESULT` (RESOURCE_DETAIL, parent `UX-EVALUATION`). Every rendered value comes from
one operation; Evaluation status comes from `getEvaluation`.

<!-- UXR:operation:BEGIN -->
| operationId | Method / path | Roles | Resource authorization | Content gate | Break-glass | Sensitivity | Audit | Response | View parameter |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| getDetectionResult | GET /api/v1/evaluations/{evaluation_id}/result | USER, ANALYST | CASE_DERIVED_CONTENT | DERIVED_CONTENT | none | C4 | EVIDENCE_ACCESSED | DetectionResultResponse | view = STANDARD \| DETAILED (default STANDARD) |
<!-- UXR:operation:END -->

- **Resource authorization:** `CASE_DERIVED_CONTENT` means case access **and** `permits_evidence_content`, because
  results quote evidence.
- **Access:** no break-glass role reaches the result, and no administrator or knowledge role reaches it by role.
- **Audit:** each read is audited (`EVIDENCE_ACCESSED`).
- **No writes:** the path exposes only `GET`; no edit, overwrite or delete control exists for a result.

## 3. Lifecycle — when a result may be requested and shown

Presentation follows the authoritative Evaluation lifecycle (API-001 §13, §19), never a guess:

<!-- UXR:status_gating:BEGIN -->
| Evaluation state | result_availability | Presentation state | Result request permitted | Failure shown | Meaning |
| --- | --- | --- | --- | --- | --- |
| QUEUED | NOT_YET_AVAILABLE | ACTION_PENDING | no | no | Evaluation accepted and waiting; no result exists yet and no outcome is implied. |
| RUNNING | NOT_YET_AVAILABLE | ACTION_PENDING | no | no | Evaluation executing; no result exists yet and no outcome is implied. |
| COMPLETED | AVAILABLE | READY | yes | no | A result may be read; only a successful result response is presented, and readiness is not a verdict. |
| FAILED | NOT_PRODUCED | ACTION_FAILED | no | yes | Evaluation failed and produced no result; the categorical failure reason is shown and is never a classification. |
| COMPLETED | REMOVED_UNDER_GOVERNANCE | REMOVED_UNDER_GOVERNANCE | no | no | The result was removed under governance; governed unavailability, distinct from empty or not found. |
| any other or missing | any other or missing | RESULT_STATUS_UNRESOLVED | no | no | No pending, failure, result or safety inference. |
<!-- UXR:status_gating:END -->

- **QUEUED / RUNNING** means a result is not available. No result is requested and no outcome is implied.
- **FAILED** is a failure, never a classification. Show only the returned categorical `failure_class`, `reason` and
  `retry_guidance`. Retry and re-analysis interactions are P7-WP5.
- **COMPLETED + AVAILABLE** permits a result read. A result is presented only from a successful response for the
  requested `evaluation_id`; status alone never produces a result.
- **Completed `UNSUPPORTED` and `ERROR`** classifications are valid results. They are not transport failures and are
  never benign.
- **REMOVED_UNDER_GOVERNANCE** is governed unavailability. It is distinct from empty and from not-found.
- **Missing, inaccessible or inconsistent status** means no result, pending, failure or safety is inferred.
- **Cached or result-shaped data** is ignored whenever the authoritative status does not permit a result request.

`EVALUATION_NOT_COMPLETED` keeps UX-001's conditional handling. The error alone is insufficient: the presentation
comes from the refreshed authoritative state, and a terminal `FAILED` evaluation is never shown as pending. These
rows are identical to the closed UX-002 evaluation-status hand-off (UXR-17).

Only an observed successful response renders. Every other response kind fails closed, and any result-shaped data it
carries is discarded (UXR-68). A transport outcome is a presentation-model concept, not an API field:

<!-- UXR:response_kinds:BEGIN -->
| Response kind | Result may render | Meaning |
| --- | --- | --- |
| SUCCESS | yes | A 200 getDetectionResult response was observed for this request. |
| ERROR | no | An accepted error response was observed; it maps to its governed presentation state. |
| NONE | no | No result request was issued or no response was observed. |
| TIMEOUT | no | The request ended without a response. |
| missing, null or unrecognised | no | Presented as RESULT_RESPONSE_UNCONFIRMED. |
| unrecognised error code | no | Presented as RESULT_RESPONSE_UNCONFIRMED. |
<!-- UXR:response_kinds:END -->

P7-WP3 adds four presentation-only states that do not collide with UX-001 or UX-002:

<!-- UXR:result_states:BEGIN -->
| Result presentation state | Kind | Meaning |
| --- | --- | --- |
| RESULT_STATUS_UNRESOLVED | PRESENTATION_ONLY | Authoritative evaluation state is missing, inaccessible or inconsistent; no result, pending, failure or safety inference. |
| RESULT_UNRENDERABLE | PRESENTATION_ONLY | The response lacks a required field, carries an unrecognised value, contradicts itself or does not match the requested evaluation; the decision is withheld and nothing is guessed. |
| RESULT_VIEW_NOT_AUTHORIZED | PRESENTATION_ONLY | The response view or its fields do not match the view requested and authorized for this caller; the payload is discarded and an authorized response is required. |
| RESULT_RESPONSE_UNCONFIRMED | PRESENTATION_ONLY | No confirmed successful result response was observed; any result-shaped data is discarded and nothing is inferred. |
<!-- UXR:result_states:END -->

## 4. Errors and recovery

Every accepted `getDetectionResult` error is mapped. HTTP status and retryability are exactly the API error catalog.
No error renders a result or implies safety.

<!-- UXR:errors:BEGIN -->
| Error code | HTTP | Retryability | Presentation state | Alternate (authorized metadata only) | Recovery | Result rendered |
| --- | --- | --- | --- | --- | --- | --- |
| DEPENDENCY_UNAVAILABLE | 503 | RETRYABLE | TEMPORARILY_UNAVAILABLE | — | WAIT_THEN_RETRY_SAME_REQUEST | no |
| EVALUATION_NOT_COMPLETED | 409 | RETRYABLE | CONDITIONAL_ON_EVALUATION_STATE | — | REFRESH_EVALUATION_STATUS | no |
| FORBIDDEN | 403 | NOT_RETRYABLE | ACCESS_DENIED | CONTENT_PERMISSION_REQUIRED | STOP_NO_RETRY | no |
| INTEGRITY_FAILURE | 500 | NOT_RETRYABLE | INTEGRITY_ERROR | — | STOP_NO_RETRY | no |
| INTERNAL_ERROR | 500 | RETRYABLE | SERVER_ERROR | — | RETRY_SAME_REQUEST | no |
| INVALID_REQUEST | 400 | RETRY_WITH_CHANGES | ACTION_FAILED | — | CORRECT_REQUEST | no |
| NOT_FOUND | 404 | NOT_RETRYABLE | NOT_FOUND_OR_NOT_VISIBLE | — | STOP_NO_RETRY | no |
| RATE_LIMITED | 429 | RETRYABLE | RATE_LIMITED | — | WAIT_THEN_RETRY_SAME_REQUEST | no |
| REMOVED_UNDER_GOVERNANCE | 410 | NOT_RETRYABLE | REMOVED_UNDER_GOVERNANCE | — | STOP_NO_RETRY | no |
| UNAUTHENTICATED | 401 | RETRY_WITH_CHANGES | AUTHENTICATION_REQUIRED | — | REAUTHENTICATE_THEN_RETRY | no |
<!-- UXR:errors:END -->

`FORBIDDEN` is `ACCESS_DENIED`. `CONTENT_PERMISSION_REQUIRED` is used only when authorized metadata establishes the
separate content restriction. A refused DETAILED request is never silently downgraded, and nothing from DETAILED is
reconstructed. A separate explicit STANDARD request remains possible where permitted. `410` is never empty or
not-found.

Recovery is limited to:

<!-- UXR:recovery:BEGIN -->
| Recovery | Retryability | Meaning |
| --- | --- | --- |
| RETRY_SAME_REQUEST | RETRYABLE | Repeat the same read; a read changes nothing. |
| WAIT_THEN_RETRY_SAME_REQUEST | RETRYABLE | Repeat the same read later, honouring any returned Retry-After; no countdown is invented. |
| REFRESH_EVALUATION_STATUS | RETRYABLE | Read the authoritative Evaluation state before choosing a presentation. |
| CORRECT_REQUEST | RETRY_WITH_CHANGES | Correct the request (for example the view selector) before any new read. |
| REAUTHENTICATE_THEN_RETRY | RETRY_WITH_CHANGES | Re-establish authentication, then repeat the read. |
| STOP_NO_RETRY | NOT_RETRYABLE | Do not retry the read; show the governed state only. |
<!-- UXR:recovery:END -->

No retry interval, countdown or polling cadence is invented.

## 5. Response validation (render preconditions)

A successful response is rendered only when all of the following hold:

- It carries every required `DetectionResultResponse` field.
- Its `evaluation_id` matches the request.
- Every enumerated value is recognised.
- `not_an_official_determination` is `true`.
- Its `input_support_status` / `classification` pair is permitted by the Phase-3 classification state machine
  (DET-001-WP5 §9).

<!-- UXR:support_classification:BEGIN -->
| input_support_status | Permitted classifications (DET-001-WP5 §9) |
| --- | --- |
| SUPPORTED | NO_SCAM_PATTERN, INSUFFICIENT_EVIDENCE, SCAM_PATTERN_SUSPECTED, SCAM_PATTERN_DETECTED, ERROR |
| PARTIALLY_SUPPORTED | NO_SCAM_PATTERN, INSUFFICIENT_EVIDENCE, SCAM_PATTERN_SUSPECTED, SCAM_PATTERN_DETECTED, ERROR |
| UNSUPPORTED | UNSUPPORTED |
| INSUFFICIENT_INFORMATION | INSUFFICIENT_EVIDENCE |
| ERROR | ERROR |
<!-- UXR:support_classification:END -->

The six returned axes must also agree with each other under the accepted Phase-3 semantics (DET-001-WP5 §4–§9 and
the runtime envelope invariants in `knowledge/runtime/result.py`):

- `risk_level` equals risk-matrix-v1 for the returned `decision_severity` and `matched_evidence_strength`; an illegal
  cell is a contradiction. The table must equal the accepted runtime matrix in `knowledge/runtime/aggregation.py`
  (UXR-72).
- When `matched_rules` is non-empty, the classification is fixed by `detection_confidence`: LOW requires
  `SCAM_PATTERN_SUSPECTED`; MEDIUM or HIGH requires `SCAM_PATTERN_DETECTED`; NOT_APPLICABLE is a contradiction.
- When `matched_rules` is empty, the classification is neither of the two scam-pattern classes; severity, strength
  and risk are NONE, and confidence is NOT_APPLICABLE. This covers NO_SCAM_PATTERN, INSUFFICIENT_EVIDENCE, UNSUPPORTED and ERROR.
- A degraded evaluation never carries HIGH confidence (the accepted cap is MEDIUM).
- In a DETAILED response, the number of COMPOSITE + MATCHED rule results equals `matched_rules`, a finding requires
  rule results, and exactly one governing rule exists when a finding exists, on an eligible rule.

<!-- UXR:risk_matrix:BEGIN -->
| decision_severity | matched_evidence_strength | risk_level |
| --- | --- | --- |
| NONE | NONE | NONE |
| LOW | WEAK | LOW |
| LOW | MODERATE | LOW |
| LOW | STRONG | MEDIUM |
| MEDIUM | WEAK | LOW |
| MEDIUM | MODERATE | MEDIUM |
| MEDIUM | STRONG | MEDIUM |
| HIGH | WEAK | MEDIUM |
| HIGH | MODERATE | HIGH |
| HIGH | STRONG | HIGH |
| CRITICAL | WEAK | HIGH |
| CRITICAL | MODERATE | HIGH |
| CRITICAL | STRONG | CRITICAL |
<!-- UXR:risk_matrix:END -->

<!-- UXR:confidence_map:BEGIN -->
| detection_confidence (matched_rules non-empty) | Required classification |
| --- | --- |
| LOW | SCAM_PATTERN_SUSPECTED |
| MEDIUM | SCAM_PATTERN_DETECTED |
| HIGH | SCAM_PATTERN_DETECTED |
<!-- UXR:confidence_map:END -->

**Rule identity (UXR-77).** References are compared by identity — `rule_id` and `rule_version`, the fields of the API
`RuleReference` and `RuleResultView` — never by count alone:

- `matched_rules` has no duplicate rule; a finding requires a governing reference, which must be one of the matched
  references; without a finding there is no governing reference (DET-001-WP5 §3). These checks use only STANDARD
  fields.
- In a DETAILED response that carries `rule_results`, the COMPOSITE + MATCHED rule results are exactly the matched
  references (same identities and versions; none missing, extra or duplicated), and the single governing rule result
  carries the governing reference's identity. A SUPPRESSION-kind rule can never be that rule.
- STANDARD never needs, requests or reveals the DETAILED-only decomposition; no lookup endpoint is invented.

Contradictory references withhold the result as `RESULT_UNRENDERABLE`; no identity is substituted. Rendered scenarios
use governed rule identities from `knowledge/rules` with their versions and kinds. The suppression-kind examples use
`TL-SUP-001`, the only governed SUPPRESSION rule, which is APPROVED rather than PUBLISHED, so those scenarios are
schema-valid hypotheticals.

A whole-evaluation error on supported input is a valid `ERROR` result (DET-001-WP5 §9), so `ERROR` is permitted with
SUPPORTED and PARTIALLY_SUPPORTED input.

Otherwise the decision is withheld as `RESULT_UNRENDERABLE`. There is no partial render, and the client never repairs,
re-derives or reclassifies the result. Unknown extra fields are tolerated and not rendered. The rendered view is the response's own `view`
field, and per-rule results are rendered only when that view is `DETAILED`.

## 6. Decision axes — separate and categorical

`input_support_status`, `classification`, `decision_severity`, `matched_evidence_strength`, `risk_level` and
`detection_confidence` are six separate axes. Each is shown as its canonical categorical value with a label and
the question it answers (DET-001 §1). None is rendered as a number, percentage, gauge, colour alone, combined
indicator, trust/safety score or ranking. The client derives no axis. Severity is not risk, and confidence is not a
probability and is never merged into risk.

<!-- UXR:axes:BEGIN -->
| Axis | Label | Question it answers | Vocabulary | Display |
| --- | --- | --- | --- | --- |
| input_support_status | Input support | Could TrustLens evaluate this input? | SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED, INSUFFICIENT_INFORMATION, ERROR | CATEGORICAL_TEXT |
| classification | Classification | What did TrustLens conclude from the evidence evaluated? | NO_SCAM_PATTERN, INSUFFICIENT_EVIDENCE, SCAM_PATTERN_SUSPECTED, SCAM_PATTERN_DETECTED, UNSUPPORTED, ERROR | CATEGORICAL_TEXT |
| decision_severity | Severity if genuine | If the pattern is genuine, how harmful would it be? | NONE, LOW, MEDIUM, HIGH, CRITICAL | CATEGORICAL_TEXT |
| matched_evidence_strength | Matched evidence strength (feeds the risk band) | How strong is the evidence that actually matched? | NONE, WEAK, MODERATE, STRONG | CATEGORICAL_TEXT |
| risk_level | Risk level (band) | What is the exposure band for this submission? | NONE, LOW, MEDIUM, HIGH, CRITICAL | CATEGORICAL_TEXT |
| detection_confidence | Detection confidence (not a probability) | How much does TrustLens trust its own analysis of this submission? | NOT_APPLICABLE, LOW, MEDIUM, HIGH | CATEGORICAL_TEXT |
<!-- UXR:axes:END -->

## 7. Classification and input-support labels

Labels and meanings are governed presentation requirements, not final copy. The canonical code is always shown with
them. `NO_SCAM_PATTERN` is never presented as safe or legitimate. `INSUFFICIENT_EVIDENCE`, `UNSUPPORTED` and `ERROR`
are never benign. Suspected patterns keep visible uncertainty. A detected pattern is not legal guilt or an official
determination.

<!-- UXR:classification:BEGIN -->
| Classification | Label | Meaning | UX-001 meaning | Absence notice |
| --- | --- | --- | --- | --- |
| NO_SCAM_PATTERN | No governed scam pattern established | No governed scam pattern was established from the evidence evaluated. This is not a determination that the content is safe or legitimate. | NO_GOVERNED_PATTERN_MATCHED_NOT_SAFETY | yes |
| INSUFFICIENT_EVIDENCE | Insufficient evidence to conclude | TrustLens could not reach a conclusion from the evidence evaluated. This is not a determination that the content is safe. | INSUFFICIENT_BASIS_NOT_SAFETY | no |
| SCAM_PATTERN_SUSPECTED | Scam pattern suspected | A governed scam pattern matched with low detection confidence; the uncertainty shown with this result remains. | UNCERTAINTY_VISIBLE | no |
| SCAM_PATTERN_DETECTED | Scam pattern detected | A governed scam pattern matched the evidence evaluated. This is not a legal finding, an official determination or proof of guilt. | NOT_LEGAL_GUILT | no |
| UNSUPPORTED | Not evaluated: unsupported input | The input is outside the supported detection scope and was not evaluated. This is not a determination that the content is safe. | CANNOT_EVALUATE_NOT_SAFETY | no |
| ERROR | Evaluation error: no conclusion | The evaluation stopped without reaching a conclusion. This is not a determination that the content is safe. | ERROR_NOT_SAFETY | no |
<!-- UXR:classification:END -->

<!-- UXR:support:BEGIN -->
| input_support_status | Label | Meaning |
| --- | --- | --- |
| SUPPORTED | Supported input | The input was within the supported detection scope and was evaluated. |
| PARTIALLY_SUPPORTED | Partially supported input | Part of the input could not be used; only the available evidence was evaluated and the gap is listed with this result. |
| UNSUPPORTED | Unsupported input | The input is outside the supported detection scope and was not evaluated. |
| INSUFFICIENT_INFORMATION | Insufficient information | The input was supported but too little could be observed to evaluate any governed pattern. |
| ERROR | Evaluation error | The input could not be evaluated safely; no conclusion was reached. |
<!-- UXR:support:END -->

`language` and `script` are rendered verbatim. The client performs no language detection, and the detailed
unsupported-language experience is P7-WP6.

**Display-text binding.** Every user-reachable string is inventoried and must equal its governed text exactly (UXR-73).
This includes section headings, classification titles, status and announcement text, recovery text, action
instructions and analyst detail headings. Wording is also checked by a classifier that does not strip uppercase words.
It rejects the unsupported-assertion categories listed in `display_text_policy.unsupported_assertions`. A negator only counts when it precedes the term in the same clause
(UXR-25), and the classifier is calibrated on pinned unsafe probes and qualified controls (UXR-74). An `and` that
begins a new clause (followed by a subject such as "the" or "this") ends the negation scope, so a leading "No …"
cannot license a later claim (round-2 R2-LOW-1). Remaining limitation: clause detection is a heuristic, and a
subject-less conjunction can still extend a negation's scope. The exact governed-text binding (UXR-73) remains the
primary control for every displayable string.

<!-- UXR:display_inventory:BEGIN -->
| Displayable string (bound to exact governed text) |
| --- |
| explanation_hierarchy[].title |
| classification_presentation[].label |
| classification_presentation[].meaning |
| input_support_presentation[].label |
| input_support_presentation[].meaning |
| decision_axes[].axis_label |
| decision_axes[].question |
| rule_outcome_presentation[].label |
| rule_outcome_presentation[].meaning |
| rule_kind_presentation[].meaning |
| status_gating.rules[].meaning |
| result_presentation_states[].meaning |
| recovery_vocabulary[].meaning |
| recommended_action_presentation.actions[].instruction |
| recommended_action_presentation.reason_statement |
| uncertainty_presentation.degraded_meaning |
| ai_presentation.statement |
| accessible_announcements[].text |
| response_kinds.kinds[].meaning |
| hierarchy_rules.optional_field_absent_text |
| hierarchy_rules.empty_list_text |
<!-- UXR:display_inventory:END -->

## 8. Explanation hierarchy (A–K)

Sections render together in this order, so a classification is never shown without its interpretation notice. Every
field traces to an accepted API field, and every `DetectionResultResponse` field is presented (UXR-27, UXR-28).

<!-- UXR:hierarchy:BEGIN -->
| Section | Key | Title | Accepted fields | Views |
| --- | --- | --- | --- | --- |
| A | CLASSIFICATION | What TrustLens concluded | classification | STANDARD, DETAILED |
| B | INPUT_SUPPORT | Input support and language | input_support_status, language[], script[] | STANDARD, DETAILED |
| C | DECISION_AXES | Severity, evidence strength, risk band and confidence | decision_severity, matched_evidence_strength, risk_level, detection_confidence | STANDARD, DETAILED |
| D | EXPLANATION | Why | explanation.summary, explanation.evidence_basis[] | STANDARD, DETAILED |
| E | RULES | Governing and matched rules | governing_rule.rule_id, governing_rule.rule_version, matched_rules[].rule_id, matched_rules[].rule_version | STANDARD, DETAILED |
| F | SOURCES_AND_PROVENANCE_TYPES | Sources and provenance | governing_rule.source_references[], matched_rules[].source_references[] | STANDARD, DETAILED |
| G | RULE_DECOMPOSITION | Per-rule outcomes (matched, indeterminate, suppressed, not applicable, not matched) | rule_results[].rule_id, rule_results[].rule_version, rule_results[].kind, rule_results[].evaluation_state, rule_results[].governing, rule_results[].effective_severity, rule_results[].rule_evidence_strength, rule_results[].rule_detection_confidence | DETAILED |
| H | UNCERTAINTY | Unknowns, ambiguities, limitations and degraded evaluation | unknowns[], ambiguities[], limitations[], degraded | STANDARD, DETAILED |
| I | RECOMMENDED_ACTIONS | Recommended next steps | recommended_actions[].action_code | STANDARD, DETAILED |
| J | ENGINE_BUNDLE_PROVENANCE | How this result was produced | evaluation_id, result_contract_version, result_digest, view, provenance.engine_version, provenance.result_contract_version, provenance.bundle_version, provenance.bundle_content_digest, provenance.evaluation_profile_id, provenance.evaluation_timestamp, EvaluationResponse.ai_usage.requested, EvaluationResponse.ai_usage.enabled_by_policy, EvaluationResponse.ai_usage.used, EvaluationResponse.ai_usage.fallback_reason | STANDARD, DETAILED |
| K | DISCLAIMER_AND_NOTICE | Interpretation notice | not_an_official_determination, absence_of_finding_notice | STANDARD, DETAILED |
<!-- UXR:hierarchy:END -->

- **Absent optional field:** stated as not provided in this response.
- **Empty list:** stated as none listed. Neither implies safety or certainty.
- **For `NO_SCAM_PATTERN`:** the returned `absence_of_finding_notice` is rendered verbatim. If it is absent, the
  governed meaning still states that this is not a safety determination.
- **No aggregates:** there is no case-level, submission-level or cross-evaluation verdict. Each Evaluation has its own
  result.

## 9. Rules, negative indicators and uncertainty

Rule outcomes stay distinct and are shown only in the DETAILED per-rule decomposition:

<!-- UXR:rule_outcomes:BEGIN -->
| evaluation_state | Label | Meaning | Finding | May govern | Group |
| --- | --- | --- | --- | --- | --- |
| MATCHED | Matched | The governed rule's required combination matched the evidence evaluated. | yes | yes | MATCHED_FINDINGS |
| INDETERMINATE | Could not be determined | A decisive part of the rule could not be resolved; the uncertainty is carried forward and is not a finding. | no | no | UNRESOLVED |
| SUPPRESSED | Suppressed by a governed suppression | The rule matched and was then cancelled by a governed suppression; it is not an active finding and not proof of safety. | no | no | SUPPRESSED |
| NOT_APPLICABLE | Not applicable or not evaluated | The rule did not apply to this input or could not be evaluated; this is not a finding and not proof of safety. | no | no | NOT_APPLICABLE |
| NOT_MATCHED | Did not match | The rule's required combination did not match; this is not a finding and not proof of safety. | no | no | NOT_MATCHED |
<!-- UXR:rule_outcomes:END -->

<!-- UXR:rule_kinds:BEGIN -->
| Rule kind | May be a finding | May govern | Display group | Meaning |
| --- | --- | --- | --- | --- |
| COMPOSITE | yes | yes | BY_STATE | A governed detection rule; only a MATCHED composite rule is a finding. |
| SUPPRESSION | no | no | SUPPRESSION_RULES | A governed suppression rule; whatever its state, it is never a scam finding and never proof of safety. |
<!-- UXR:rule_kinds:END -->

**Rule outcomes.**

- Only a COMPOSITE rule in MATCHED state is an active finding (DET-001-WP5 §2). Kind and state are both checked; no
  rule identifier is special-cased.
- A SUPPRESSION-kind rule is never a finding or the governing rule, whatever its state; it is shown in its own
  suppression group.
- `SUPPRESSED` is not an active finding.
- `INDETERMINATE` carries uncertainty forward.
- `NOT_MATCHED` is never shown as "cleared".
- None of these outcomes is proof of safety.

**Governing rule and corroboration.**

- The governing rule comes only from the API's governing fields; the client never selects one.
- Rule counts are never shown as evidence strength or independent corroboration (no false corroboration).

**Negative and mitigating indicators.** These are not exposed by the result API, so they are not displayed. Their
absence is not inferred as safety, and mitigating context is never presented as safety.

**Uncertainty.** `unknowns`, `ambiguities` and `limitations` are rendered verbatim, never paraphrased. An empty list
is not certainty. `degraded = true` is always shown as limited confidence and is not a safety determination.

## 10. Provenance, quotes, AI and enrichment

Provenance types stay visibly distinct and are never merged:

<!-- UXR:provenance_types:BEGIN -->
| Provenance type | On the result surface | Source | Owner |
| --- | --- | --- | --- |
| USER_PROVIDED_MATERIAL | no | NONE | P7-WP4 |
| RETAINED_EVIDENCE | no | NONE | P7-WP4 |
| SYSTEM_DERIVED_OBSERVATIONS | no | NOT_EXPOSED_BY_RESULT_API | API owner (governed API revision) |
| AI_DERIVED_GOVERNED_OBSERVATIONS | yes | EvaluationResponse.ai_usage | P7-WP3 |
| EXTERNAL_PROVIDER_ASSERTIONS | no | NONE | P7-WP6 |
| DETERMINISTIC_RESULT | yes | DetectionResultResponse | P7-WP3 |
| HUMAN_ADJUDICATION | no | NONE | P7-WP4 |
<!-- UXR:provenance_types:END -->

**Quotes.** Quotes come only from the returned `explanation.evidence_basis`, rendered verbatim. The summary is never
rendered as a quote or attributed to an official body. Source references are shown as identifiers, and no quote is
manufactured.

**AI.** AI usage is shown only as governed provenance metadata from `EvaluationResponse.ai_usage`. AI may indirectly
affect the deterministic result only through validated governed observations. It cannot directly set, override or
bypass the deterministic decision. AI output is never presented as the decision, and no model confidence is shown.

**Enrichment.** Enrichment is not presented on the result surface (P7-WP6). Provider reputation is never a
classification, and no provider assertion is presented as a safety determination.

## 11. Recommended actions

Actions are governed `action_code` values in response order, each with a governed instruction. They have no priority,
rank, urgency, URL, phone number, contact detail or free text. Priority is a schema-reserved Phase-3 field that the
runtime does not emit and the API does not expose. Per-action reason identifiers are not exposed, so each action
carries only the policy-basis statement: "Recommended by the governed action policy in the knowledge bundle
identified in this result's provenance." An unrecognised code is withheld, never shown as free text. An empty list is
not safety.

<!-- UXR:actions:BEGIN -->
| action_code | Governed instruction (not final copy) | Governed trigger in action policy v1.0.0 |
| --- | --- | --- |
| DO_NOT_SHARE_CREDENTIALS | Do not share passwords, one-time codes, PINs or other credentials in response to this message. | yes |
| DO_NOT_ENTER_PIN | Do not enter a payment or card PIN in response to this message. | yes |
| DO_NOT_TRANSFER_MONEY | Do not transfer money in response to this message. | yes |
| DO_NOT_INSTALL_APP | Do not install an app or grant device access requested by this message. | yes |
| DO_NOT_CONNECT_WALLET | Do not connect a crypto wallet as requested by this message. | yes |
| DO_NOT_DIAL_CODE | Do not dial a code requested by this message. | no |
| DISCONNECT_REMOTE_ACCESS | End any remote-access or screen-sharing session started at this message's request. | yes |
| VERIFY_INDEPENDENTLY | Verify the claim independently through a channel you already trust, not one supplied in this message. | yes |
| CONTACT_BANK | Contact your bank through a channel you already trust. | yes |
| CONTACT_OFFICIAL_CHANNEL | Contact the organisation concerned through an official channel you find independently. | yes |
| REPORT_CYBERCRIME | Consider reporting this to the appropriate cybercrime reporting authority. | yes |
| PRESERVE_EVIDENCE | Keep the original message and related records. | yes |
| PROCEED_WITH_CAUTION | Proceed with caution. | no |
| SEEK_HUMAN_REVIEW | Seek review of this result by a person. | yes |
| RESUBMIT_IN_SUPPORTED_LANGUAGE | This input was not evaluated; resubmit it in a supported language where possible. | yes |
<!-- UXR:actions:END -->

## 12. Views and access

`STANDARD` is the default. `DETAILED` is only for an assigned analyst whose grant has `permits_evidence_content`.
The table is derived from the accepted API operation roles, `CASE_DERIVED_CONTENT`, break-glass roles and Matrix D
field visibility (UXR-42):

<!-- UXR:view_access:BEGIN -->
| Role | Relationship | permits_evidence_content | View | Permitted |
| --- | --- | --- | --- | --- |
| USER | OWNER | yes | STANDARD | yes |
| USER | OWNER | yes | DETAILED | no |
| USER | NONE | no | STANDARD | no |
| USER | NONE | no | DETAILED | no |
| ANALYST | ASSIGNED_ANALYST | yes | STANDARD | yes |
| ANALYST | ASSIGNED_ANALYST | yes | DETAILED | yes |
| ANALYST | ASSIGNED_ANALYST | no | STANDARD | no |
| ANALYST | ASSIGNED_ANALYST | no | DETAILED | no |
| ANALYST | NONE | no | STANDARD | no |
| ANALYST | NONE | no | DETAILED | no |
| ANALYST | BREAK_GLASS | yes | STANDARD | no |
| ANALYST | BREAK_GLASS | yes | DETAILED | no |
| ADMINISTRATOR | NONE | no | STANDARD | no |
| ADMINISTRATOR | NONE | no | DETAILED | no |
| ADMINISTRATOR | BREAK_GLASS | yes | STANDARD | no |
| ADMINISTRATOR | BREAK_GLASS | yes | DETAILED | no |
| KNOWLEDGE_EDITOR | NONE | no | STANDARD | no |
| KNOWLEDGE_EDITOR | NONE | no | DETAILED | no |
| KNOWLEDGE_APPROVER | NONE | no | STANDARD | no |
| KNOWLEDGE_APPROVER | NONE | no | DETAILED | no |
<!-- UXR:view_access:END -->

**Field presence comes from the payload (UXR-78).** No presence flag is trusted. `rule_results` is optional and
DETAILED_VIEW_ONLY in the API, so whether the property is present is read from the response itself. In a STANDARD
response the property is never acceptable, whether non-empty or empty, because the field belongs only to DETAILED; the
payload is withheld as `RESULT_VIEW_NOT_AUTHORIZED` together with its announcements and any copied or cached output. In
DETAILED, an absent property and an empty list are both valid when there is no finding; a finding requires the
property. A `null` value is malformed and withheld.

**Rendering is bound to the actual caller (UXR-69).** A successful response renders only when all hold:

- the requested view is permitted for the actual caller (role, relationship and evidence-content permission from
  authorized metadata);
- the returned `view` equals the requested view and is itself permitted for that caller;
- DETAILED-only `rule_results` never appear in a STANDARD response.

Otherwise the whole payload is discarded as `RESULT_VIEW_NOT_AUTHORIZED`. The client never hides section G and
renders the rest, and an unknown access context is treated the same way. The client is a defensive presentation
boundary, not an authorization service.

- **Authorization:** the backend is authoritative and a hidden UI is not a security control.
- **No role-based access:** an administrator has no result access by role, and break-glass does not grant result access.
- **DETAILED offer:** the DETAILED view is offered only when authorized metadata indicates it. It is never
  reconstructed from STANDARD.
- **Form factors:** permissions are identical across form factors.

## 13. Immutability, adjudication and aggregation

The result is immutable and its only action is `READ`. Adjudication is a separate record (P7-WP4): it never
overwrites the result and its outcome never replaces the classification. Correction and re-analysis create a new
Evaluation (P7-WP5). No evidence content, C4 rationale, provider body or internal identifier appears on the result
surface, and existence masking is preserved.

## 14. Scenarios

Each scenario's expected outcome was hand-authored and pinned in the validator; none is generated by either procedure.
A reference model over the contract tables (UXR-63) and a separately written decision procedure over the accepted
authority (UXR-64) must both reproduce every row. The decision procedure evaluates the actual caller, reads
risk-matrix-v1 from the accepted Phase-3 runtime, and uses the closed UX-002 status hand-off.

UXR-75 then generates adversarial variants of every rendered scenario. These are other response kinds, a flipped
view, every caller tuple, every single-axis change and every rule-kind swap. The two procedures must agree on each
variant, and non-success kinds and view flips must never render.

Round-2 additions: SC-93 to SC-107 cover rule identity and version consistency, and SC-108 to SC-113 cover
payload-derived presence. They include the reviewer's TL-CRED-001 / TL-PAY-001 counterexample (SC-93) and the
non-empty `rule_results` in a STANDARD payload (SC-108), plus valid single- and multi-rule controls in both views
(SC-102, SC-103, SC-110, SC-111, SC-113). UXR-75 now also injects DETAILED-only data into STANDARD, removes it from
DETAILED, and perturbs rule identities, versions and the governing reference.

Correction note: SC-38 was previously expected to render a STANDARD payload for a DETAILED request. The returned view
must now equal the requested view, so SC-38 is withheld. SC-43 to SC-92 are the round-1 regression and control
scenarios.

<!-- UXR:scenarios:BEGIN -->
| Scenario | Situation | Viewer | Requested view | Status | Response | Presented as | Rendered view | Sections | Active findings | Actions shown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SC-01 | Owner reads a NO_SCAM_PATTERN result | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD NO_SCAM_PATTERN / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] | READY | STANDARD | ABCDEFHIJK | — | — |
| SC-02 | Owner reads a SCAM_PATTERN_DETECTED result with governed actions | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 | READY | STANDARD | ABCDEFHIJK | — | DO_NOT_SHARE_CREDENTIALS, REPORT_CYBERCRIME |
| SC-03 | Owner reads a SCAM_PATTERN_SUSPECTED result | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_SUSPECTED / SUPPORTED / sev MEDIUM / str WEAK / risk LOW / conf LOW / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 | READY | STANDARD | ABCDEFHIJK | — | VERIFY_INDEPENDENTLY |
| SC-04 | Insufficient information yields INSUFFICIENT_EVIDENCE | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD INSUFFICIENT_EVIDENCE / INSUFFICIENT_INFORMATION / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] | READY | STANDARD | ABCDEFHIJK | — | SEEK_HUMAN_REVIEW |
| SC-05 | Completed UNSUPPORTED classification is a result, not a transport failure | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD UNSUPPORTED / UNSUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] | READY | STANDARD | ABCDEFHIJK | — | RESUBMIT_IN_SUPPORTED_LANGUAGE, SEEK_HUMAN_REVIEW |
| SC-06 | Completed ERROR classification is a result with no conclusion | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD ERROR / ERROR / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] | READY | STANDARD | ABCDEFHIJK | — | SEEK_HUMAN_REVIEW |
| SC-07 | Queued evaluation: no result request | USER / OWNER / content yes | STANDARD | QUEUED + NOT_YET_AVAILABLE | not requested | ACTION_PENDING | — | — | — | — |
| SC-08 | Running evaluation: no result request | USER / OWNER / content yes | STANDARD | RUNNING + NOT_YET_AVAILABLE | not requested | ACTION_PENDING | — | — | — | — |
| SC-09 | Failed evaluation is a failure, never pending or a classification | USER / OWNER / content yes | STANDARD | FAILED + NOT_PRODUCED | not requested | ACTION_FAILED | — | — | — | — |
| SC-10 | Result removed under governance (status) | USER / OWNER / content yes | STANDARD | COMPLETED + REMOVED_UNDER_GOVERNANCE | not requested | REMOVED_UNDER_GOVERNANCE | — | — | — | — |
| SC-11 | Missing evaluation status: nothing inferred | USER / OWNER / content yes | STANDARD | missing | kind NONE | RESULT_STATUS_UNRESOLVED | — | — | — | — |
| SC-12 | Inconsistent status COMPLETED + NOT_YET_AVAILABLE | USER / OWNER / content yes | STANDARD | COMPLETED + NOT_YET_AVAILABLE | not requested | RESULT_STATUS_UNRESOLVED | — | — | — | — |
| SC-13 | Inconsistent status FAILED + AVAILABLE | USER / OWNER / content yes | STANDARD | FAILED + AVAILABLE | not requested | RESULT_STATUS_UNRESOLVED | — | — | — | — |
| SC-14 | 409 EVALUATION_NOT_COMPLETED with refreshed RUNNING status | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | EVALUATION_NOT_COMPLETED | ACTION_PENDING | — | — | — | — |
| SC-15 | 409 EVALUATION_NOT_COMPLETED with refreshed FAILED status | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | EVALUATION_NOT_COMPLETED | ACTION_FAILED | — | — | — | — |
| SC-16 | 409 EVALUATION_NOT_COMPLETED without refreshed status | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | EVALUATION_NOT_COMPLETED | RESULT_STATUS_UNRESOLVED | — | — | — | — |
| SC-17 | 409 EVALUATION_NOT_COMPLETED while status still reads COMPLETED + AVAILABLE | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | EVALUATION_NOT_COMPLETED | RESULT_STATUS_UNRESOLVED | — | — | — | — |
| SC-18 | 410 REMOVED_UNDER_GOVERNANCE is governed unavailability, not empty | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | REMOVED_UNDER_GOVERNANCE | REMOVED_UNDER_GOVERNANCE | — | — | — | — |
| SC-19 | 404 keeps existence masking | USER / NONE / content no | STANDARD | COMPLETED + AVAILABLE | NOT_FOUND | NOT_FOUND_OR_NOT_VISIBLE | — | — | — | — |
| SC-20 | Owner requests DETAILED and is refused | USER / OWNER / content yes | DETAILED | COMPLETED + AVAILABLE | FORBIDDEN | ACCESS_DENIED | — | — | — | — |
| SC-21 | Assigned analyst with content permission reads DETAILED | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-CRED-001@1.0.0 COMPOSITE:MATCHED*, TL-PAY-001@1.0.0 COMPOSITE:INDETERMINATE, TL-KYC-001@1.0.0 COMPOSITE:SUPPRESSED, TL-INV-001@1.0.0 COMPOSITE:NOT_APPLICABLE, TL-AUTH-001@1.0.0 COMPOSITE:NOT_MATCHED] | READY | DETAILED | ABCDEFGHIJK | TL-CRED-001@1.0.0 | DO_NOT_ENTER_PIN |
| SC-22 | Assigned analyst without content permission is refused | ANALYST / ASSIGNED_ANALYST / content no | STANDARD | COMPLETED + AVAILABLE | FORBIDDEN | ACCESS_DENIED | — | — | — | — |
| SC-23 | Content restriction established by authorized metadata | ANALYST / ASSIGNED_ANALYST / content no | STANDARD | COMPLETED + AVAILABLE | FORBIDDEN | CONTENT_PERMISSION_REQUIRED | — | — | — | — |
| SC-24 | Administrator has no result access by role | ADMINISTRATOR / NONE / content no | STANDARD | COMPLETED + AVAILABLE | FORBIDDEN | ACCESS_DENIED | — | — | — | — |
| SC-25 | Integrity failure withholds the result | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | INTEGRITY_FAILURE | INTEGRITY_ERROR | — | — | — | — |
| SC-26 | Internal error | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | INTERNAL_ERROR | SERVER_ERROR | — | — | — | — |
| SC-27 | Dependency unavailable | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | DEPENDENCY_UNAVAILABLE | TEMPORARILY_UNAVAILABLE | — | — | — | — |
| SC-28 | Rate limited | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | RATE_LIMITED | RATE_LIMITED | — | — | — | — |
| SC-29 | Authentication required | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | UNAUTHENTICATED | AUTHENTICATION_REQUIRED | — | — | — | — |
| SC-30 | Invalid request | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | INVALID_REQUEST | ACTION_FAILED | — | — | — | — |
| SC-31 | Response for a different evaluation is not rendered | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD NO_SCAM_PATTERN / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-32 | Response missing a required field is not rendered | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD NO_SCAM_PATTERN / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-33 | Unrecognised classification value is not rendered | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD UNRECOGNISED_LOOKS_SAFE / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-34 | UNSUPPORTED input with NO_SCAM_PATTERN is contradictory and not rendered | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD NO_SCAM_PATTERN / UNSUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-35 | Disclaimer flag not true: result withheld | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD NO_SCAM_PATTERN / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-36 | NO_SCAM_PATTERN without a returned notice keeps its not-safe meaning | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD NO_SCAM_PATTERN / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] | READY | STANDARD | ABCDEFHIJK | — | — |
| SC-37 | Unrecognised action code is withheld, never free text | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 | READY | STANDARD | ABCDEFHIJK | — | DO_NOT_TRANSFER_MONEY |
| SC-38 | Analyst asks for DETAILED but the response view is STANDARD (view mismatch withheld) | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_SUSPECTED / SUPPORTED / sev MEDIUM / str WEAK / risk LOW / conf LOW / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 | RESULT_VIEW_NOT_AUTHORIZED | — | — | — | — |
| SC-39 | Knowledge editor has no result access | KNOWLEDGE_EDITOR / NONE / content no | STANDARD | COMPLETED + AVAILABLE | FORBIDDEN | ACCESS_DENIED | — | — | — | — |
| SC-40 | Degraded supported evaluation with INSUFFICIENT_EVIDENCE | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD INSUFFICIENT_EVIDENCE / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] / degraded | READY | STANDARD | ABCDEFHIJK | — | SEEK_HUMAN_REVIEW |
| SC-41 | Suppressed and indeterminate rules only: no active finding | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED NO_SCAM_PATTERN / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] / rule_results [TL-KYC-001@1.0.0 COMPOSITE:SUPPRESSED, TL-PAY-001@1.0.0 COMPOSITE:INDETERMINATE, TL-AUTH-001@1.0.0 COMPOSITE:NOT_MATCHED] | READY | DETAILED | ABCDEFGHIJK | — | — |
| SC-42 | Break-glass grants no result access | ADMINISTRATOR / BREAK_GLASS / content yes | STANDARD | COMPLETED + AVAILABLE | FORBIDDEN | ACCESS_DENIED | — | — | — | — |
| SC-43 | HIGH-1: owner requests STANDARD but the response is DETAILED | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-CRED-001@1.0.0 COMPOSITE:MATCHED*, TL-PAY-001@1.0.0 COMPOSITE:INDETERMINATE] | RESULT_VIEW_NOT_AUTHORIZED | — | — | — | — |
| SC-44 | HIGH-1: owner requests DETAILED and a DETAILED payload is returned | USER / OWNER / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-CRED-001@1.0.0 COMPOSITE:MATCHED*, TL-PAY-001@1.0.0 COMPOSITE:INDETERMINATE] | RESULT_VIEW_NOT_AUTHORIZED | — | — | — | — |
| SC-45 | HIGH-1: unassigned analyst receives DETAILED | ANALYST / NONE / content no | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-CRED-001@1.0.0 COMPOSITE:MATCHED*, TL-PAY-001@1.0.0 COMPOSITE:INDETERMINATE] | RESULT_VIEW_NOT_AUTHORIZED | — | — | — | — |
| SC-46 | HIGH-1: assigned analyst without content permission receives DETAILED | ANALYST / ASSIGNED_ANALYST / content no | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-CRED-001@1.0.0 COMPOSITE:MATCHED*, TL-PAY-001@1.0.0 COMPOSITE:INDETERMINATE] | RESULT_VIEW_NOT_AUTHORIZED | — | — | — | — |
| SC-47 | HIGH-1: administrator receives DETAILED without result authorization | ADMINISTRATOR / NONE / content no | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-CRED-001@1.0.0 COMPOSITE:MATCHED*, TL-PAY-001@1.0.0 COMPOSITE:INDETERMINATE] | RESULT_VIEW_NOT_AUTHORIZED | — | — | — | — |
| SC-48 | HIGH-1: break-glass evidence grant treated as result access (administrator, STANDARD) | ADMINISTRATOR / BREAK_GLASS / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 | RESULT_VIEW_NOT_AUTHORIZED | — | — | — | — |
| SC-49 | HIGH-1: break-glass analyst receives DETAILED | ANALYST / BREAK_GLASS / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-CRED-001@1.0.0 COMPOSITE:MATCHED*, TL-PAY-001@1.0.0 COMPOSITE:INDETERMINATE] | RESULT_VIEW_NOT_AUTHORIZED | — | — | — | — |
| SC-50 | HIGH-1: STANDARD response carries DETAILED-only rule_results | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-CRED-001@1.0.0 COMPOSITE:MATCHED*] | RESULT_VIEW_NOT_AUTHORIZED | — | — | — | — |
| SC-51 | HIGH-1 control: authorized owner receives a proper STANDARD result | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf HIGH / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 | READY | STANDARD | ABCDEFHIJK | — | DO_NOT_SHARE_CREDENTIALS |
| SC-52 | HIGH-1 control: assigned analyst with content permission receives a proper DETAILED result | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_SUSPECTED / SUPPORTED / sev MEDIUM / str WEAK / risk LOW / conf LOW / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-CRED-001@1.0.0 COMPOSITE:MATCHED*, TL-SUP-001@1.0.0 SUPPRESSION:NOT_MATCHED] | READY | DETAILED | ABCDEFGHIJK | TL-CRED-001@1.0.0 | — |
| SC-53 | HIGH-1: unauthorized caller requests STANDARD and a payload is returned | KNOWLEDGE_APPROVER / NONE / content no | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD NO_SCAM_PATTERN / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] | RESULT_VIEW_NOT_AUTHORIZED | — | — | — | — |
| SC-54 | MEDIUM-2: result-shaped fields with a NONE response kind | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | kind NONE with result-shaped fields | RESULT_RESPONSE_UNCONFIRMED | — | — | — | — |
| SC-55 | MEDIUM-2: result-shaped fields with a TIMEOUT response kind | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | kind TIMEOUT with result-shaped fields | RESULT_RESPONSE_UNCONFIRMED | — | — | — | — |
| SC-56 | MEDIUM-2: result-shaped fields with a null response kind | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | kind None with result-shaped fields | RESULT_RESPONSE_UNCONFIRMED | — | — | — | — |
| SC-57 | MEDIUM-2: result-shaped fields with a unrecognised response kind | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | kind UNRECOGNISED_PARTIAL_SUCCESS with result-shaped fields | RESULT_RESPONSE_UNCONFIRMED | — | — | — | — |
| SC-58 | MEDIUM-2: result-shaped fields with no response kind | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | kind MISSING with result-shaped fields | RESULT_RESPONSE_UNCONFIRMED | — | — | — | — |
| SC-59 | MEDIUM-2: cached success payload while the evaluation is RUNNING | USER / OWNER / content yes | STANDARD | RUNNING + NOT_YET_AVAILABLE | 200 STANDARD SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 | ACTION_PENDING | — | — | — | — |
| SC-60 | MEDIUM-2: unrecognised error code | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | UNRECOGNISED_PAYMENT_REQUIRED | RESULT_RESPONSE_UNCONFIRMED | — | — | — | — |
| SC-61 | MEDIUM-2: cached success payload after a FAILED evaluation | USER / OWNER / content yes | STANDARD | FAILED + NOT_PRODUCED | 200 STANDARD NO_SCAM_PATTERN / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] | ACTION_FAILED | — | — | — | — |
| SC-62 | MEDIUM-3: SUPPRESSION-kind MATCHED rule with NO_SCAM_PATTERN is not a finding | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED NO_SCAM_PATTERN / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] / rule_results [TL-SUP-001@1.0.0 SUPPRESSION:MATCHED, TL-KYC-001@1.0.0 COMPOSITE:SUPPRESSED] | READY | DETAILED | ABCDEFGHIJK | — | — |
| SC-63 | MEDIUM-3: SUPPRESSION-kind rule marked governing is contradictory | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-SUP-001@1.0.0 SUPPRESSION:MATCHED*] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-64 | MEDIUM-3: composite finding beside a SUPPRESSION-kind MATCHED rule | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-CRED-001@1.0.0 COMPOSITE:MATCHED*, TL-SUP-001@1.0.0 SUPPRESSION:MATCHED] | READY | DETAILED | ABCDEFGHIJK | TL-CRED-001@1.0.0 | — |
| SC-65 | MEDIUM-3: COMPOSITE INDETERMINATE only gives no finding | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED INSUFFICIENT_EVIDENCE / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] / rule_results [TL-PAY-001@1.0.0 COMPOSITE:INDETERMINATE] | READY | DETAILED | ABCDEFGHIJK | — | — |
| SC-66 | MEDIUM-3: COMPOSITE NOT_MATCHED only gives no finding | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED NO_SCAM_PATTERN / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] / rule_results [TL-AUTH-001@1.0.0 COMPOSITE:NOT_MATCHED] | READY | DETAILED | ABCDEFGHIJK | — | — |
| SC-67 | MEDIUM-3: COMPOSITE NOT_APPLICABLE with degraded evaluation gives no finding | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED INSUFFICIENT_EVIDENCE / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] / degraded / rule_results [TL-INV-001@1.0.0 COMPOSITE:NOT_APPLICABLE] | READY | DETAILED | ABCDEFGHIJK | — | — |
| SC-68 | MEDIUM-3: SUPPRESSION-kind INDETERMINATE rule gives no finding | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED NO_SCAM_PATTERN / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] / rule_results [TL-SUP-001@1.0.0 SUPPRESSION:INDETERMINATE, TL-AUTH-001@1.0.0 COMPOSITE:NOT_MATCHED] | READY | DETAILED | ABCDEFGHIJK | — | — |
| SC-69 | MEDIUM-3: matched count claims a finding but only a SUPPRESSION-kind rule matched | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-SUP-001@1.0.0 SUPPRESSION:MATCHED] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-70 | MEDIUM-3: eligible composite match under a NO_SCAM_PATTERN classification | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED NO_SCAM_PATTERN / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] / rule_results [TL-CRED-001@1.0.0 COMPOSITE:MATCHED] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-71 | MEDIUM-3: two governing rules | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0, TL-PAY-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-CRED-001@1.0.0 COMPOSITE:MATCHED*, TL-PAY-001@1.0.0 COMPOSITE:MATCHED*] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-72 | MEDIUM-3: governing flag on a SUPPRESSED composite rule | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-CRED-001@1.0.0 COMPOSITE:MATCHED, TL-KYC-001@1.0.0 COMPOSITE:SUPPRESSED*] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-73 | MEDIUM-3: unrecognised rule kind | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-CRED-001@1.0.0 UNRECOGNISED_HEURISTIC_ONLY:MATCHED*] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-74 | MEDIUM-3: DETAILED finding without any rule_results | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 | RESULT_UNRENDERABLE | — | — | — | — |
| SC-75 | MEDIUM-4: DETECTED with LOW detection confidence | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf LOW / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 | RESULT_UNRENDERABLE | — | — | — | — |
| SC-76 | MEDIUM-4: SUSPECTED with MEDIUM detection confidence | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_SUSPECTED / SUPPORTED / sev MEDIUM / str WEAK / risk LOW / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 | RESULT_UNRENDERABLE | — | — | — | — |
| SC-77 | MEDIUM-4: risk band disagrees with the risk matrix | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk MEDIUM / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 | RESULT_UNRENDERABLE | — | — | — | — |
| SC-78 | MEDIUM-4: illegal severity/strength cell (finding with NONE strength) | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str NONE / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 | RESULT_UNRENDERABLE | — | — | — | — |
| SC-79 | MEDIUM-4: NO_SCAM_PATTERN with a non-NONE severity | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD NO_SCAM_PATTERN / SUPPORTED / sev LOW / str WEAK / risk LOW / conf NOT_APPLICABLE / matched [] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-80 | MEDIUM-4: NO_SCAM_PATTERN with a detection confidence instead of NOT_APPLICABLE | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD NO_SCAM_PATTERN / SUPPORTED / sev NONE / str NONE / risk NONE / conf LOW / matched [] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-81 | MEDIUM-4: ERROR classification with a detection confidence | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD ERROR / ERROR / sev NONE / str NONE / risk NONE / conf MEDIUM / matched [] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-82 | MEDIUM-4: UNSUPPORTED classification with a risk band | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD UNSUPPORTED / UNSUPPORTED / sev LOW / str STRONG / risk MEDIUM / conf NOT_APPLICABLE / matched [] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-83 | MEDIUM-4: DETECTED with NOT_APPLICABLE detection confidence | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf NOT_APPLICABLE / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 | RESULT_UNRENDERABLE | — | — | — | — |
| SC-84 | MEDIUM-4: unrecognised risk value | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk UNRECOGNISED_EXTREME / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 | RESULT_UNRENDERABLE | — | — | — | — |
| SC-85 | MEDIUM-4: finding classification with decision severity NONE | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_SUSPECTED / SUPPORTED / sev NONE / str WEAK / risk LOW / conf LOW / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 | RESULT_UNRENDERABLE | — | — | — | — |
| SC-86 | MEDIUM-4: degraded evaluation with HIGH confidence exceeds the cap | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf HIGH / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 / degraded | RESULT_UNRENDERABLE | — | — | — | — |
| SC-87 | MEDIUM-4: NO_SCAM_PATTERN while matched_rules is non-empty | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD NO_SCAM_PATTERN / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 | RESULT_UNRENDERABLE | — | — | — | — |
| SC-88 | MEDIUM-4: DETECTED while matched_rules is empty | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-89 | MEDIUM-4 control: degraded DETECTED capped at MEDIUM is valid | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_DETECTED / SUPPORTED / sev CRITICAL / str MODERATE / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 / degraded | READY | STANDARD | ABCDEFHIJK | — | — |
| SC-90 | MEDIUM-4 control: whole-evaluation ERROR on supported input is valid | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD ERROR / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] | READY | STANDARD | ABCDEFHIJK | — | SEEK_HUMAN_REVIEW |
| SC-91 | MEDIUM-4 control: LOW severity with STRONG evidence gives a MEDIUM risk band | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_SUSPECTED / SUPPORTED / sev LOW / str STRONG / risk MEDIUM / conf LOW / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 | READY | STANDARD | ABCDEFHIJK | — | — |
| SC-92 | MEDIUM-4: INSUFFICIENT_INFORMATION input with NO_SCAM_PATTERN | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD NO_SCAM_PATTERN / INSUFFICIENT_INFORMATION / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-93 | MEDIUM-3: matched and governing name TL-CRED-001 but the governing rule result is TL-PAY-001 | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-PAY-001@1.0.0 COMPOSITE:MATCHED*] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-94 | MEDIUM-3: governing reference outside the matched set (DETAILED) | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-PAY-001@1.0.0 / rule_results [TL-CRED-001@1.0.0 COMPOSITE:MATCHED*] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-95 | MEDIUM-3: governing reference outside the matched set (STANDARD) | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-PAY-001@1.0.0 | RESULT_UNRENDERABLE | — | — | — | — |
| SC-96 | MEDIUM-3: matched rule version differs from the rule result version | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-CRED-001@1.1.0 COMPOSITE:MATCHED*] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-97 | MEDIUM-3: duplicate rule identity in matched_rules (STANDARD) | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0, TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 | RESULT_UNRENDERABLE | — | — | — | — |
| SC-98 | MEDIUM-3: duplicate rule identity in rule_results | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-CRED-001@1.0.0 COMPOSITE:MATCHED*, TL-CRED-001@1.0.0 COMPOSITE:INDETERMINATE] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-99 | MEDIUM-3: extra eligible rule result not in matched_rules | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-CRED-001@1.0.0 COMPOSITE:MATCHED*, TL-PAY-001@1.0.0 COMPOSITE:MATCHED] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-100 | MEDIUM-3: matched rule missing from rule_results | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0, TL-PAY-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-CRED-001@1.0.0 COMPOSITE:MATCHED*] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-101 | MEDIUM-3: per-rule governing flag disagrees with the governing reference | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0, TL-PAY-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-CRED-001@1.0.0 COMPOSITE:MATCHED, TL-PAY-001@1.0.0 COMPOSITE:MATCHED*] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-102 | MEDIUM-3 control: two eligible matched rules with consistent references (DETAILED) | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0, TL-PAY-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-CRED-001@1.0.0 COMPOSITE:MATCHED*, TL-PAY-001@1.0.0 COMPOSITE:MATCHED, TL-KYC-001@1.0.0 COMPOSITE:SUPPRESSED] | READY | DETAILED | ABCDEFGHIJK | TL-CRED-001@1.0.0, TL-PAY-001@1.0.0 | — |
| SC-103 | MEDIUM-3 control: two matched rules with a consistent governing reference (STANDARD) | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0, TL-PAY-001@1.0.0] governing TL-CRED-001@1.0.0 | READY | STANDARD | ABCDEFHIJK | — | — |
| SC-104 | MEDIUM-3: finding without a governing reference (STANDARD) | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-105 | MEDIUM-3: governing reference without any finding (STANDARD) | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD NO_SCAM_PATTERN / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] governing TL-CRED-001@1.0.0 | RESULT_UNRENDERABLE | — | — | — | — |
| SC-106 | MEDIUM-3: SUPPRESSION-kind rule presented as the governing finding with matching references | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-SUP-001@1.0.0] governing TL-SUP-001@1.0.0 / rule_results [TL-SUP-001@1.0.0 SUPPRESSION:MATCHED*] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-107 | MEDIUM-3: malformed rule identity | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [cred-1@1.0.0] governing cred-1@1.0.0 / rule_results [TL-CRED-001@1.0.0 COMPOSITE:MATCHED*] | RESULT_UNRENDERABLE | — | — | — | — |
| SC-108 | R2-MEDIUM-1: STANDARD response carries non-empty rule_results (no presence flag is consulted) | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD SCAM_PATTERN_DETECTED / SUPPORTED / sev HIGH / str STRONG / risk HIGH / conf MEDIUM / matched [TL-CRED-001@1.0.0] governing TL-CRED-001@1.0.0 / rule_results [TL-CRED-001@1.0.0 COMPOSITE:MATCHED*] | RESULT_VIEW_NOT_AUTHORIZED | — | — | — | — |
| SC-109 | R2-MEDIUM-1: STANDARD response carries the DETAILED-only rule_results property even when empty | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD NO_SCAM_PATTERN / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] / rule_results [] | RESULT_VIEW_NOT_AUTHORIZED | — | — | — | — |
| SC-110 | R2-MEDIUM-1 control: DETAILED NO_SCAM_PATTERN with an empty rule_results collection | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED NO_SCAM_PATTERN / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] / rule_results [] | READY | DETAILED | ABCDEFGHIJK | — | — |
| SC-111 | R2-MEDIUM-1 control: DETAILED NO_SCAM_PATTERN with rule_results absent | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED NO_SCAM_PATTERN / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] | READY | DETAILED | ABCDEFGHIJK | — | — |
| SC-112 | R2-MEDIUM-1: rule_results present as null | ANALYST / ASSIGNED_ANALYST / content yes | DETAILED | COMPLETED + AVAILABLE | 200 DETAILED NO_SCAM_PATTERN / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] / rule_results null | RESULT_UNRENDERABLE | — | — | — | — |
| SC-113 | R2-MEDIUM-1 control: STANDARD NO_SCAM_PATTERN with an empty matched_rules collection | USER / OWNER / content yes | STANDARD | COMPLETED + AVAILABLE | 200 STANDARD NO_SCAM_PATTERN / SUPPORTED / sev NONE / str NONE / risk NONE / conf NOT_APPLICABLE / matched [] | READY | STANDARD | ABCDEFHIJK | — | — |
<!-- UXR:scenarios:END -->

## 15. Accessibility, claims and carried items

These are design requirements, not achieved conformance:

- the canonical text accompanies every visual;
- meaning never relies on colour, green never means safe, and red never replaces classification text;
- every section has a heading;
- result changes are announced, and an announcement carries at most the classification label for a READY result.

Withheld states render no section and announce no result field. Error summaries, screen-reader descriptions, cached
presentation data, hidden components and exported or copied text never hold the withheld payload (UXR-70).

<!-- UXR:announcements:BEGIN -->
| Presentation state | Announced result fields | Announcement text (not final copy) |
| --- | --- | --- |
| READY | classification | Result available: {classification_label}. |
| ACTION_PENDING | none | The evaluation has not finished; no result is available yet. |
| ACTION_FAILED | none | The evaluation or request did not produce a result. |
| REMOVED_UNDER_GOVERNANCE | none | This result was removed under governance and cannot be shown. |
| AUTHENTICATION_REQUIRED | none | Sign-in is required before a result can be shown. |
| ACCESS_DENIED | none | This result is not available with your access. |
| CONTENT_PERMISSION_REQUIRED | none | Content permission is required before this result can be shown. |
| NOT_FOUND_OR_NOT_VISIBLE | none | No result can be shown here. |
| INTEGRITY_ERROR | none | The result could not be verified and is not shown. |
| SERVER_ERROR | none | The result could not be loaded. |
| TEMPORARILY_UNAVAILABLE | none | The result is temporarily unavailable. |
| RATE_LIMITED | none | Too many requests; the result was not loaded. |
| RESULT_STATUS_UNRESOLVED | none | The result status could not be confirmed; no result is shown. |
| RESULT_UNRENDERABLE | none | The response was incomplete or inconsistent; no result is shown. |
| RESULT_VIEW_NOT_AUTHORIZED | none | The response did not match the view available to you; no result is shown. |
| RESULT_RESPONSE_UNCONFIRMED | none | No confirmed result was received; no result is shown. |
<!-- UXR:announcements:END -->

Detailed accessible and responsive patterns are P7-WP6. There is no accessibility certification or conformance
claim.

<!-- UXR:carryovers:BEGIN -->
| Item | Status | Owner |
| --- | --- | --- |
| G-09 | OPEN | Phase 10 (testing/evaluation; QA Lead) with Sponsor for any corpus access |
| OI-05 | OPEN | Sponsor + legal/governance |
| ASM-002 | UNCONFIRMED / PROVISIONAL | Sponsor / Programme |
| P6-WP7-LOW-1 | OPEN / NON-BLOCKING | Next governed Phase-6 snapshot revision / Programme governance |
<!-- UXR:carryovers:END -->

No tenant_id, tenant selector or organization switcher is introduced, and no numeric retention duration is invented.
G-09 means no labelled real-world evaluation corpus, so there is no accuracy or effectiveness claim. There is no
frontend or API implementation and no production-readiness or usability-testing claim. The round-8 independent approval
(GATE-028 §6) and the post-merge closure (GATE-028 §8) cover this design contract only; no result experience is
implemented.
`ENGINE_VERSION = 1.0.0` remains unchanged. P7-WP4 is not started.

## 16. Open decisions

<!-- UXR:decisions:BEGIN -->
| Unresolved decision | Owner | Status |
| --- | --- | --- |
| Negative and mitigating indicator identities are not exposed by DetectionResultResponse v1; presenting them needs a governed API revision | API owner (governed API revision) | DEFERRED |
| Supporting observations and spans are not exposed by DetectionResultResponse v1; observation-level explanation needs a governed API revision and the P7-WP4 content boundary | API owner with P7-WP4 | DEFERRED |
| Per-action reason identifiers are not exposed by RecommendedActionView; action-specific reasons need a governed API revision | API owner (governed API revision) | DEFERRED |
| Explanation evidence_basis is a list of strings in the API; its exact rendering as source statements needs confirmation of the serialized form | API owner | DEFERRED |
| Whether intake offers an AI-assisted analysis_mode choice (carried from UX-002; not resolved here) | Programme with AI governance | DEFERRED |
| Final user-facing copy, translation and plain-language review of labels and meanings | Product / Result UX with Phase 9 | DEFERRED |
| Detailed accessible and responsive result layout | P7-WP6 / Accessibility UX | DEFERRED |
| Phase-3 result.py matched_rule_ids() counts any MATCHED rule result as fired while aggregation eligibility requires COMPOSITE; impact: a SUPPRESSION-kind MATCHED result could be counted as a fired rule by the envelope validator; the result surface follows aggregation eligibility (a SUPPRESSION-kind rule is never a finding) pending Phase-3 owner clarification (round-2 R2-INFO-1) | Detection owner (Phase-3 governance) | DEFERRED |
<!-- UXR:decisions:END -->

## 17. Validation

`knowledge/validation/validate_ux_result.py` runs UXR-01…UXR-75 against this document, GATE-028 and the machine
contract. It then requires every negative mutation in `contracts/ux/fixtures/result-negative-mutations.json` to be
rejected by its named check. It is integrated into `run_all.py`, and `ci_selftest.py` carries a P7-WP3 defect
(the NO_SCAM_PATTERN not-safe flag inverted) that only this validator catches. This is builder evidence, not independent
review.
