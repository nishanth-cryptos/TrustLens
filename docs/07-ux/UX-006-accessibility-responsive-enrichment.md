# UX-006 — Accessibility, responsive behaviour, unsupported language and external enrichment

| Field | Value |
| --- | --- |
| Document ID | UX-006 |
| Version | 0.1 |
| Status | P7-WP6 ACCESSIBILITY, RESPONSIVE AND ENRICHMENT UX APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING |
| Phase / work package | Phase 7 — UX, Evidence & Reporting Design / P7-WP6 |
| Owner role | Product / Accessibility UX |
| Branch | phase7-wp6-accessibility-ux |
| Baseline | 7f3c2899dae693d3b497faa3a68f691890488d2d (P7-WP5 delivery merge, PR #41); the P7-WP5 post-merge closure ships alongside on this branch |
| Machine contract | [`ux-accessibility-v1.json`](../../contracts/ux/ux-accessibility-v1.json) with [`ux-accessibility-contract.schema.json`](../../contracts/ux/ux-accessibility-contract.schema.json) |
| Validation | `knowledge/validation/validate_ux_accessibility.py`; `contracts/ux/fixtures/accessibility-negative-mutations.json` |
| Gate | [GATE-031](../00-program/GATE-031-phase-7-accessibility-enrichment.md) |
| Foundation | [UX-001](UX-001-experience-foundation-information-architecture.md) / GATE-026; consumes UX-002, UX-003, UX-004 and [UX-005](UX-005-reporting-historical-workflows.md) (closed, not modified), INT-001 and ADR-0014 / DEC-008 |
| Last updated | 2026-10-12 |

## 1. Authority and scope

UX-006 is the P7-WP6 UX design and contract for the cross-cutting experience rules UX-001 handed to this
work package: accessibility patterns, responsive behaviour, unsupported language, external enrichment, provider
attribution and the interpretation of CLEAN, NOT_FOUND and UNAVAILABLE. It is approved following independent review
(GATE-031 §7, round 2); remote CI and merge are pending. It is a
design and contract package only: there is no frontend, API or runtime implementation, and nothing here is a
production-readiness, usability-testing, accessibility-conformance or security-testing claim.

Scope equals the UX-001 P7-WP6 handoff. The machine contract is authoritative; the tables below are exact projections
checked by `validate_ux_accessibility.py`. Authority is not redefined: the backend decides every access through role,
resource authorization and the separate content permission (API-001 §3), results stay immutable, and no API operation,
provider identity field, lookup-outcome field, supported language, breakpoint value or frontend is introduced. The
rules here apply to every UX-001 surface; the only owned operation is the existing enrichment read.

Two scope differences are recorded. First, the accepted `EnrichmentView` exposes `status` and `reputation_result` only,
so some integration outcomes cannot be told apart (§3). Second, unsupported input at intake (`415`, `413`) stays owned by
UX-002; this package adds its accessible and responsive presentation and the unsupported-language explanation on the
result.

## 2. Enrichment surface and operation

External enrichment lives on its own surface (UX-ENRICHMENT), available to an assigned analyst only and never on the
result surface. Existence is masked as API-001 §5 requires: without case visibility every role, including an
administrator or the case owner, sees the not-found-or-not-visible state, and only a visible case without the analyst
role shows access denied, identically in every layout. The operation equals the accepted API and INT-001's API surface exactly; it requires no audit, so no
audit notice is shown. A `404` from this read is the ordinary not-found-or-not-visible state and says nothing about any
provider.

<!-- UXA:operations:BEGIN -->
| Operation | Surface | Method | Path | Roles | Resource authorization | Audit | Sensitivity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| listEvaluationEnrichments | UX-ENRICHMENT | GET | /api/v1/evaluations/{evaluation_id}/enrichments | ANALYST | CASE_ACCESS | NOT_REQUIRED | C2 |
<!-- UXA:operations:END -->

<!-- UXA:errors:BEGIN -->
| API error | HTTP | Retryability | Presentation state | Recovery |
| --- | --- | --- | --- | --- |
| DEPENDENCY_UNAVAILABLE | 503 | RETRYABLE | TEMPORARILY_UNAVAILABLE | WAIT_THEN_RETRY_SAME_REQUEST |
| FORBIDDEN | 403 | NOT_RETRYABLE | ACCESS_DENIED | STOP_NO_RETRY |
| INTERNAL_ERROR | 500 | RETRYABLE | SERVER_ERROR | RETRY_SAME_REQUEST |
| INVALID_REQUEST | 400 | RETRY_WITH_CHANGES | ACTION_FAILED | CORRECT_REQUEST |
| NOT_FOUND | 404 | NOT_RETRYABLE | NOT_FOUND_OR_NOT_VISIBLE | STOP_NO_RETRY |
| RATE_LIMITED | 429 | RETRYABLE | RATE_LIMITED | WAIT_THEN_RETRY_SAME_REQUEST |
| UNAUTHENTICATED | 401 | RETRY_WITH_CHANGES | AUTHENTICATION_REQUIRED | REAUTHENTICATE_THEN_RETRY |
<!-- UXA:errors:END -->

## 3. Enrichment interpretation: CLEAN, NOT_FOUND and UNAVAILABLE

External lookups are advisory supporting context. They never change the classification, severity, risk or confidence,
never enter a governed artifact, and are always labelled as advisory. Each record shows the provider category, status,
reputation and observation time (`provider_category`, `observed_at` are the attribution); a missing observation time is
stated, not guessed. Provider identity, raw provider bodies and freshness are not shown, because the accepted view has
no such fields.

The interpretation table is derived from INT-001's outcome mapping. A record is presented as a specific integration
outcome only when exactly one outcome can produce its (status, reputation) pair:

- **CLEAN** is shown only as the provider's assertion of no adverse reputation, never as TrustLens safety.
- **NOT_FOUND** cannot be shown as such. A finished lookup without a reputation (`SUCCEEDED` / `UNKNOWN`) is either a
  provider with no entry or an entry of unknown reputation, so it is presented as "no provider assertion" without
  claiming which.
- **UNAVAILABLE** is distinguished only for a timeout (`TIMED_OUT`). A failed lookup (`FAILED`) is either an
  unavailable provider or an unusable response, so it is presented as "did not complete" without claiming which.

No row other than CLEAN mentions a clean or empty outcome, and none implies safety. A pair outside the mapping is shown
as an unrecognized record, never as a provider assertion. Exposing the lookup outcome is an owned deferred decision (§9).

<!-- UXA:interpretation:BEGIN -->
| Status | Reputation result | Possible integration outcomes | Distinguishes outcome | Presented as | Label | Meaning |
| --- | --- | --- | --- | --- | --- | --- |
| FAILED | NOT_EVALUATED | INVALID_RESPONSE, UNAVAILABLE | no | LOOKUP_DID_NOT_COMPLETE | Lookup did not complete | The lookup failed or its response could not be used, so there is no provider assertion. |
| NOT_EVALUATED | NOT_EVALUATED | — | no | NOT_LOOKED_UP | Not looked up | No external lookup was made for this indicator. |
| REJECTED | NOT_EVALUATED | POLICY_REJECTED | yes | LOOKUP_NOT_PERMITTED | Lookup not permitted | TrustLens policy did not allow this lookup, so there is no provider assertion. |
| SUCCEEDED | CLEAN | FOUND | yes | PROVIDER_CLEAN_ASSERTION | Provider reports no adverse reputation | An external provider reported no adverse reputation for this indicator at the time shown. This is the provider's assertion only, not a TrustLens judgement. |
| SUCCEEDED | MALICIOUS | FOUND | yes | PROVIDER_ADVERSE_ASSERTION | Provider reports malicious | An external provider reported this indicator as malicious at the time shown. This is the provider's assertion, not a TrustLens finding. |
| SUCCEEDED | SUSPICIOUS | FOUND | yes | PROVIDER_CAUTION_ASSERTION | Provider reports suspicious | An external provider reported this indicator as suspicious at the time shown. This is the provider's assertion, not a TrustLens finding. |
| SUCCEEDED | UNKNOWN | FOUND, NOT_FOUND | no | NO_PROVIDER_ASSERTION | No provider assertion | The lookup finished without a reputation from the provider. Whether the provider had an entry cannot be told from this record. |
| TIMED_OUT | NOT_EVALUATED | UNAVAILABLE | yes | LOOKUP_UNAVAILABLE | Lookup timed out | The provider did not answer in time, so there is no provider assertion. |
<!-- UXA:interpretation:END -->

## 4. Unsupported language and unsupported input

Detection scope is English only (`en` / `Latn`; ADR-0014 / DEC-008). Content in any other language is UNSUPPORTED:
never inferred benign and never given a conclusion. The client never detects language; `language[]` and `script[]` are
shown verbatim from the result. When the input support status is UNSUPPORTED and `language[]` holds a value outside the
detection scope, the result carries the unsupported-language explanation; otherwise the unsupported-input
presentation from UX-002 applies. The interface language is not the detection scope; translation and final copy are
deferred.

<!-- UXA:support:BEGIN -->
| Input support status | Presented as | Conclusion reached |
| --- | --- | --- |
| SUPPORTED | SUPPORTED_INPUT | yes |
| PARTIALLY_SUPPORTED | PARTIALLY_SUPPORTED_INPUT | yes |
| UNSUPPORTED | UNSUPPORTED_INPUT | no |
| INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION_INPUT | no |
| ERROR | ERROR_INPUT | no |
<!-- UXA:support:END -->

## 5. Accessibility patterns and announcements

Every UX-001 accessibility commitment is covered by a pattern. Meaning never depends on colour, hover, motion or a time
limit. These are design requirements; no conformance with any accessibility standard is claimed, and assistive-technology
testing belongs to Phase 10.

<!-- UXA:patterns:BEGIN -->
| Pattern | Requirement | UX-001 commitment |
| --- | --- | --- |
| KEYBOARD_OPERATION | Every action, disclosure, table and dialog is reachable and operable from the keyboard, with no keyboard trap. | keyboard_operable |
| FOCUS_ORDER | Focus follows the reading order of each surface. | logical_focus_order |
| VISIBLE_FOCUS | The focused element is always visibly indicated. | visible_focus |
| HEADINGS_AND_REGIONS | Each surface and section has a heading and a named region; tables have header cells. | semantic_headings_regions |
| TEXT_STATUS_EQUIVALENTS | Every state, outcome and provider assertion is stated in text; colour, icons and position only repeat it. | textual_status_equivalents |
| ERROR_SUMMARY | Errors appear in a summary linked to the affected fields, and focus moves to the summary. | error_summary_field_association |
| CONTROL_LABELS | Every control has a programmatic name that matches its visible label. | screen_reader_control_labels |
| STATUS_ANNOUNCEMENTS | State changes are announced politely; only blocking errors interrupt. | dynamic_announcements |
| NO_MANDATORY_MOTION | No meaning depends on animation, and motion can be avoided. | mandatory_animation |
<!-- UXA:patterns:END -->

Announcements are polite and carry only the fields their state may announce; no protected or C4 field is ever
announced. Each announcement state and each enrichment interpretation appears exactly once, and every row is checked on
its own, so a later valid row can never conceal an earlier unsafe one.

<!-- UXA:announcements:BEGIN -->
| Announcement state | Announced fields |
| --- | --- |
| ENRICHMENT_PROVIDER_ASSERTION | provider_category, reputation_result |
| ENRICHMENT_NO_ASSERTION | provider_category |
| UNSUPPORTED_LANGUAGE | — |
| CONTENT_WITHHELD | — |
<!-- UXA:announcements:END -->

## 6. Responsive behaviour and redaction across devices

Breakpoint values are NOT YET SPECIFIED; only behaviour is governed. The contract names two layout classes, NARROW and
WIDE. Content reflows; wide tables scroll within their region and keep their headers; orientation is never locked. Permissions, controls and redaction are identical in every layout: a narrow layout never exposes
content the permission withholds, never offers a control the wide layout lacks, and never hides a control as a
security measure. Withheld content is never rendered and then hidden, and never appears in placeholders, tooltips,
titles, alternative text, notifications, previews, print or copy.

## 7. Protected copy

Protected copy is a closed set of governed messages, and every label and meaning is checked on its own.

<!-- UXA:protected_text:BEGIN -->
| Protected display field | Governed text |
| --- | --- |
| enrichment.advisory_notice | External lookups are advisory. They come from outside TrustLens and do not change the TrustLens result. |
| enrichment.observed_at_absent_text | Observation time not provided. |
| enrichment.unrecognized_pair.label | Unrecognized lookup record |
| enrichment.unrecognized_pair.meaning | This lookup record could not be interpreted and is not shown as a provider assertion. |
| enrichment.interpretation.LOOKUP_DID_NOT_COMPLETE.label | Lookup did not complete |
| enrichment.interpretation.LOOKUP_DID_NOT_COMPLETE.meaning | The lookup failed or its response could not be used, so there is no provider assertion. |
| enrichment.interpretation.NOT_LOOKED_UP.label | Not looked up |
| enrichment.interpretation.NOT_LOOKED_UP.meaning | No external lookup was made for this indicator. |
| enrichment.interpretation.LOOKUP_NOT_PERMITTED.label | Lookup not permitted |
| enrichment.interpretation.LOOKUP_NOT_PERMITTED.meaning | TrustLens policy did not allow this lookup, so there is no provider assertion. |
| enrichment.interpretation.PROVIDER_CLEAN_ASSERTION.label | Provider reports no adverse reputation |
| enrichment.interpretation.PROVIDER_CLEAN_ASSERTION.meaning | An external provider reported no adverse reputation for this indicator at the time shown. This is the provider's assertion only, not a TrustLens judgement. |
| enrichment.interpretation.PROVIDER_ADVERSE_ASSERTION.label | Provider reports malicious |
| enrichment.interpretation.PROVIDER_ADVERSE_ASSERTION.meaning | An external provider reported this indicator as malicious at the time shown. This is the provider's assertion, not a TrustLens finding. |
| enrichment.interpretation.PROVIDER_CAUTION_ASSERTION.label | Provider reports suspicious |
| enrichment.interpretation.PROVIDER_CAUTION_ASSERTION.meaning | An external provider reported this indicator as suspicious at the time shown. This is the provider's assertion, not a TrustLens finding. |
| enrichment.interpretation.NO_PROVIDER_ASSERTION.label | No provider assertion |
| enrichment.interpretation.NO_PROVIDER_ASSERTION.meaning | The lookup finished without a reputation from the provider. Whether the provider had an entry cannot be told from this record. |
| enrichment.interpretation.LOOKUP_UNAVAILABLE.label | Lookup timed out |
| enrichment.interpretation.LOOKUP_UNAVAILABLE.meaning | The provider did not answer in time, so there is no provider assertion. |
| unsupported_language.explanation | This content is in a language TrustLens does not evaluate yet, so no conclusion was reached and none is implied. |
| accessibility.announcements.ENRICHMENT_PROVIDER_ASSERTION.text | External lookup: provider assertion available. |
| accessibility.announcements.ENRICHMENT_NO_ASSERTION.text | External lookup: no provider assertion. |
| accessibility.announcements.UNSUPPORTED_LANGUAGE.text | Unsupported language. No conclusion was reached. |
| accessibility.announcements.CONTENT_WITHHELD.text | Some content is not shown. |
<!-- UXA:protected_text:END -->

## 8. Scenarios

The scenarios pin what the UX presents for each role, relationship, layout and record. `validate_ux_accessibility.py`
re-derives every row with an independent decision procedure built from the API's roles and resource authorization,
INT-001's outcome mapping, the input-support vocabulary and the ADR-0014 detection scope; scenarios that differ only by
layout must present identically.

<!-- UXA:scenarios:BEGIN -->
| Scenario | Situation | Action | Role / relationship / layout | Presented | Presented as | Distinguishes outcome | Provider assertion | Conclusion |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AX-01 | Provider reports no adverse reputation | VIEW_ENRICHMENT | ANALYST / ASSIGNED_ANALYST / WIDE | yes | PROVIDER_CLEAN_ASSERTION | yes | yes | no |
| AX-02 | Provider reports malicious | VIEW_ENRICHMENT | ANALYST / ASSIGNED_ANALYST / WIDE | yes | PROVIDER_ADVERSE_ASSERTION | yes | yes | no |
| AX-03 | Lookup finished without a reputation (not found or unknown) | VIEW_ENRICHMENT | ANALYST / ASSIGNED_ANALYST / WIDE | yes | NO_PROVIDER_ASSERTION | no | no | no |
| AX-04 | Lookup timed out | VIEW_ENRICHMENT | ANALYST / ASSIGNED_ANALYST / WIDE | yes | LOOKUP_UNAVAILABLE | yes | no | no |
| AX-05 | Lookup failed or response unusable | VIEW_ENRICHMENT | ANALYST / ASSIGNED_ANALYST / WIDE | yes | LOOKUP_DID_NOT_COMPLETE | no | no | no |
| AX-06 | Lookup refused by policy | VIEW_ENRICHMENT | ANALYST / ASSIGNED_ANALYST / WIDE | yes | LOOKUP_NOT_PERMITTED | yes | no | no |
| AX-07 | No lookup made | VIEW_ENRICHMENT | ANALYST / ASSIGNED_ANALYST / WIDE | yes | NOT_LOOKED_UP | no | no | no |
| AX-08 | Inconsistent record is not interpreted | VIEW_ENRICHMENT | ANALYST / ASSIGNED_ANALYST / WIDE | yes | UNRECOGNIZED_RECORD | no | no | no |
| AX-09 | Same clean assertion on a narrow screen | VIEW_ENRICHMENT | ANALYST / ASSIGNED_ANALYST / NARROW | yes | PROVIDER_CLEAN_ASSERTION | yes | yes | no |
| AX-10 | Owner has no enrichment surface | VIEW_ENRICHMENT | USER / OWNER / WIDE | no | ACCESS_DENIED | no | no | no |
| AX-11 | Owner has no enrichment surface on a narrow screen either | VIEW_ENRICHMENT | USER / OWNER / NARROW | no | ACCESS_DENIED | no | no | no |
| AX-12 | Analyst without case visibility | VIEW_ENRICHMENT | ANALYST / NONE / WIDE | no | NOT_FOUND_OR_NOT_VISIBLE | no | no | no |
| AX-13 | Administrator without case visibility gets the masked not-found state | VIEW_ENRICHMENT | ADMINISTRATOR / NONE / WIDE | no | NOT_FOUND_OR_NOT_VISIBLE | no | no | no |
| AX-14 | Unsupported language explained on the result | VIEW_LANGUAGE_SUPPORT | USER / OWNER / WIDE | yes | UNSUPPORTED_LANGUAGE | no | no | no |
| AX-15 | Unsupported language explained on a narrow screen | VIEW_LANGUAGE_SUPPORT | USER / OWNER / NARROW | yes | UNSUPPORTED_LANGUAGE | no | no | no |
| AX-16 | Unsupported input in scope language gets no language explanation | VIEW_LANGUAGE_SUPPORT | USER / OWNER / WIDE | yes | UNSUPPORTED_INPUT | no | no | no |
| AX-17 | Supported English input | VIEW_LANGUAGE_SUPPORT | USER / OWNER / WIDE | yes | SUPPORTED_INPUT | no | no | yes |
| AX-18 | Partially supported input lists its gap | VIEW_LANGUAGE_SUPPORT | ANALYST / ASSIGNED_ANALYST / WIDE | yes | PARTIALLY_SUPPORTED_INPUT | no | no | yes |
| AX-19 | Insufficient information is not a conclusion | VIEW_LANGUAGE_SUPPORT | USER / OWNER / WIDE | yes | INSUFFICIENT_INFORMATION_INPUT | no | no | no |
| AX-20 | No language detected for unsupported input | VIEW_LANGUAGE_SUPPORT | USER / OWNER / WIDE | yes | UNSUPPORTED_INPUT | no | no | no |
| AX-21 | Owner without content permission sees no result language detail | VIEW_LANGUAGE_SUPPORT | USER / OWNER / WIDE | no | CONTENT_PERMISSION_REQUIRED | no | no | no |
| AX-22 | Same withheld result on a narrow screen | VIEW_LANGUAGE_SUPPORT | USER / OWNER / NARROW | no | CONTENT_PERMISSION_REQUIRED | no | no | no |
| AX-23 | Provider reports suspicious | VIEW_ENRICHMENT | ANALYST / ASSIGNED_ANALYST / WIDE | yes | PROVIDER_CAUTION_ASSERTION | yes | yes | no |
| AX-24 | Mixed-language unsupported input explained | VIEW_LANGUAGE_SUPPORT | USER / OWNER / WIDE | yes | UNSUPPORTED_LANGUAGE | no | no | no |
| AX-25 | Owner without case visibility gets the masked not-found state | VIEW_ENRICHMENT | USER / NONE / WIDE | no | NOT_FOUND_OR_NOT_VISIBLE | no | no | no |
| AX-26 | Administrator without case visibility masked on a narrow screen too | VIEW_ENRICHMENT | ADMINISTRATOR / NONE / NARROW | no | NOT_FOUND_OR_NOT_VISIBLE | no | no | no |
| AX-27 | Administrator without case visibility gets no result language detail | VIEW_LANGUAGE_SUPPORT | ADMINISTRATOR / NONE / WIDE | no | NOT_FOUND_OR_NOT_VISIBLE | no | no | no |
<!-- UXA:scenarios:END -->

## 9. Open decisions

<!-- UXA:decisions:BEGIN -->
| Unresolved decision | Owner | Status |
| --- | --- | --- |
| Provider identity and detailed outcome attribution beyond the current EnrichmentView | API owner (governed API revision), carried from UX-001 | DEFERRED |
| Breakpoint values and responsive layout details are NOT YET SPECIFIED; only behaviour rules are governed here | Phase 9 design system with Product / Accessibility UX, carried from UX-001 | DEFERRED |
| The integration lookup outcome (FOUND, NOT_FOUND, UNAVAILABLE, INVALID_RESPONSE) is not exposed by EnrichmentView, so NOT_FOUND and UNAVAILABLE cannot be told apart from neighbouring outcomes | API owner with INT-001 owner (governed API revision) | DEFERRED |
| Enrichment freshness (FRESH, STALE, UNKNOWN) is not exposed by EnrichmentView and has no governed period | API owner with provider policy owner | DEFERRED |
| Detection scope beyond English (ADR-0014 options B/C) requires verified non-English evidence | Sponsor with Knowledge governance (ADR-0014) | DEFERRED |
| Interface language, translation and final user-facing copy | Product / Accessibility UX with Phase 9 | DEFERRED |
| Accessibility conformance testing with assistive technologies; no conformance is claimed | Phase 10 / QA Lead | DEFERRED |
<!-- UXA:decisions:END -->

## 10. Carryovers and lifecycle

<!-- UXA:carryovers:BEGIN -->
| Item | Status | Owner |
| --- | --- | --- |
| G-09 | OPEN | Phase 10 (testing/evaluation; QA Lead) with Sponsor for any corpus access |
| OI-05 | OPEN | Sponsor + legal/governance |
| ASM-002 | UNCONFIRMED / PROVISIONAL | Sponsor / Programme |
| P6-WP7-LOW-1 | OPEN / NON-BLOCKING | Next governed Phase-6 snapshot revision / Programme governance |
<!-- UXA:carryovers:END -->

No tenant field is introduced and no numeric retention is invented. `ENGINE_VERSION = 1.0.0` remains unchanged. The
structured lifecycle in the machine contract is authoritative and fails closed: a review round, an approval or merge
evidence counts only when it equals the record pinned in `validate_ux_accessibility.py` by a governed bookkeeping step.
Round 1 (initial independent review) returned REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 2 / LOW 0 / INFO 0):
duplicate semantic rows and case-existence masking. Round 2 (targeted re-review) returned APPROVE (BLOCKER 0 / HIGH 0 /
MEDIUM 0 / LOW 0 / INFO 0) and closed both, so the lifecycle is APPROVED. Merge evidence is absent, so CLOSED remains
unavailable until a governed post-merge step pins it. GATE-031 §7 holds the review record.
