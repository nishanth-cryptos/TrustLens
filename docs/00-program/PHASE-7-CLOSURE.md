# PHASE-7-CLOSURE — Integrated Phase-7 closure record and Phase-8 handoff

| Field | Value |
| --- | --- |
| Document ID | PHASE-7-CLOSURE |
| Version | 0.1 |
| Status | PHASE 7 CLOSED |
| Phase / work package | Phase 7 — UX, Evidence & Reporting Design / P7-WP7 |
| Owner role | Programme / Product |
| Branch | phase7-wp7-integrated-closure |
| Baseline | 324fc320c47498a42f68c6bac941cc4a5dde9b39 (P7-WP6 delivery merge, PR #42); the P7-WP6 post-merge closure shipped in PR #43 |
| Machine record | [`phase7-closure-v1.json`](../../contracts/phase7/phase7-closure-v1.json) with [`phase7-closure-contract.schema.json`](../../contracts/phase7/phase7-closure-contract.schema.json) |
| Validation | `knowledge/validation/validate_phase7_closure.py`; `contracts/phase7/fixtures/phase7-closure-negative-mutations.json` |
| Gate | [GATE-032](GATE-032-phase-7-closure.md) |
| Last updated | 2026-10-12 |

## 1. Purpose and scope

This record documents verified design-contract closure of Phase 7 and its Phase-8 handoff.
PR #43 is merged and both required jobs succeeded on PR-head CI #84 and post-merge CI #85; GATE-032 §8 records the exact evidence. It checks the six
Phase-7 work packages together: what each package's own validator cannot see. It adds no API operation, persisted field,
permission, supported language, breakpoint value, report format, frontend or backend. Each package's own rules stay with
its canonical validator (`validate_ux_foundation.py` through `validate_ux_accessibility.py`), which the canonical suite
runs before `validate_phase7_closure.py`; nothing is re-validated or re-reviewed here.

Phase 7 delivered UX-001 to UX-006: the experience foundation, intake, result presentation, evidence review and
security, reporting and history, and accessibility, responsive behaviour, unsupported language and external enrichment.
None of it is implemented, tested with users or assistive technologies, or production-ready.

## 2. Work-package register

Every package passed independent review and merged with both required CI jobs successful. P7-WP2 to P7-WP6 record
their closure in their own contracts and gates. UX-001 and GATE-026 keep their pre-merge status rows because the later
Phase-7 contracts hash-pin UX-001; this record therefore pins P7-WP1's merge and CI evidence instead, which the builder
verified on GitHub: PR #34 merged as `d16ee7a`, head `1d99bcc`, PR-head run 37309265948 (#65) and merge-commit run
37309298428 (#66), both jobs successful in both runs. Changing UX-001's status row is left to a governed snapshot
revision (P7C-02).

<!-- PC7:work_packages:BEGIN -->
| Work package | Contract | Gate | Effective state | Final review | PR | Merge commit | PR-head run | Merge run | Record |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P7-WP1 | UX-001 | GATE-026 | MERGED_CI_VERIFIED | APPROVE | 34 | d16ee7a | 37309265948 | 37309298428 | PHASE-7-CLOSURE §2 |
| P7-WP2 | UX-002 | GATE-027 | CLOSED | APPROVE | 35 | 4567b9b | 37932022803 | 37934882890 | GATE-027 §8 |
| P7-WP3 | UX-003 | GATE-028 | CLOSED | APPROVE | 37 | 8d9b71a | 38116825962 | 38118409062 | GATE-028 §8 |
| P7-WP4 | UX-004 | GATE-029 | CLOSED | APPROVE | 39 | 5f8c373 | 38139502369 | 38142036162 | GATE-029 §8 |
| P7-WP5 | UX-005 | GATE-030 | CLOSED | APPROVE | 41 | 7f3c289 | 38161387705 | 38163633985 | GATE-030 §8 |
| P7-WP6 | UX-006 | GATE-031 | CLOSED | APPROVE | 42 | 324fc32 | 38238792863 | 38244422412 | GATE-031 §8 |
<!-- PC7:work_packages:END -->

## 3. Handoff integrity

Each UX-001 handoff is consumed by exactly one package with an identical scope; the P7-WP7 handoff is this record.

<!-- PC7:handoffs:BEGIN -->
| Handoff | Consumed by | Scope |
| --- | --- | --- |
| P7-WP2 | UX-002 | Submission flow, Evidence capture, Upload interaction, Evidence metadata preview, Submission progress, Capture errors, Supported consent/instruction copy |
| P7-WP3 | UX-003 | DetectionResult presentation, Classification labels, Risk/severity/confidence, Matched and indeterminate rules, Negative indicators, Uncertainty, Recommended actions, Explanation hierarchy |
| P7-WP4 | UX-004 | Evidence review, Content permission, Review queue, Assignment, Break-glass, Adjudication, C4 rationale, Audit access |
| P7-WP5 | UX-005 | Reports, Replay, Re-analysis, Governed deletion, 410 removed, Replay unavailable, Report regeneration unavailable, Historical comparison |
| P7-WP6 | UX-006 | Accessibility patterns, Unsupported language, Responsive behavior, External enrichment, Provider attribution, CLEAN / NOT_FOUND / UNAVAILABLE interpretation |
| P7-WP7 | PHASE-7-CLOSURE | Integrated Phase-7 closure |
<!-- PC7:handoffs:END -->

## 4. API operation coverage

Every public operation of the accepted API is accounted for exactly once: designed in detail by UX-002 to UX-006,
placed on a UX-001 surface only (foundation access and presentation rules, no detailed workflow), or not designed and
carried as integration gap P7C-01. No Phase-7 contract adds, changes or removes an operation, and every operation a
contract restates carries the accepted roles, resource authorization, content permission and audit requirement.

<!-- PC7:coverage_gaps:BEGIN -->
| Coverage | Operations |
| --- | --- |
| FOUNDATION_SURFACE | closeCase, getActiveKnowledge, getKnowledgeBundle, listKnowledgeActivations, reopenCase |
| NOT_DESIGNED | activateKnowledgeBundle, getOperationalHealth, rollbackKnowledgeBundle, withdrawKnowledgeBundle |
<!-- PC7:coverage_gaps:END -->

## 5. Cross-package consistency

Checked across all six contracts by `validate_phase7_closure.py`:

- **Permissions.** Backend authorization stays authoritative; operation access equals the accepted API everywhere, and
  no operation has two owning packages. Existence masking (API-001 §5) and the separate content permission hold in
  every package that presents case-scoped content.
- **Privacy.** UX-001's global exposure rules are closed; packages that restate them agree, surface-specific exposure
  flags are closed, and the existence-masking safeguard holds. No tenant field is enabled and no retention period is
  invented.
- **Claims.** No package claims an implemented frontend or API, production readiness, accessibility conformance,
  usability or security testing, or detection effectiveness.
- **Carryovers.** G-09, OI-05, ASM-002 and P6-WP7-LOW-1 are identical in every package.
- **Phase-6 constraints.** The 19-artifact Phase-6 snapshot is intact and `ENGINE_VERSION = 1.0.0` everywhere.

## 6. Roadmap deviations

The roadmap lists REPORT-001 as a Phase-7 output and WCAG 2.2 AA in the Phase-7 gate. Neither was met, and neither is
claimed. The user explicitly accepted Option A: both are accepted exceptions to design-contract closure, with their
future deliverables still required. PROGRAM-001 §4.1 identifies the user as the programme sponsor for delivery, scope
and technical direction; this decision is attributed to the user, with no named official, signature or external
authorization asserted. REPORT-001 remains undelivered: Phase 8 must define the report format before planning the report
implementation slice. WCAG 2.2 AA remains NOT VERIFIED: Phase 10 owns conformance testing and evidence.

<!-- PC7:programme_acceptance:BEGIN -->
| Acceptance field | Value |
| --- | --- |
| decision | OPTION_A_ACCEPTED |
| accepted_by | User (programme sponsor) |
| authority_reference | PROGRAM-001 §4.1 |
| evidence_source | User's explicit Option A decision in the P7-WP7 Final Acceptance Bookkeeping request (2026-10-12) |
| record_reference | GATE-032 §6 |
| deviation_ids | P7D-01, P7D-02 |
| scope | DESIGN_CONTRACT_CLOSURE_ONLY |
| future_deliverables_waived | False |
<!-- PC7:programme_acceptance:END -->

<!-- PC7:deviations:BEGIN -->
| Deviation | Roadmap item | Kind | Statement | Linked decision | Target | Status | Programme acceptance |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P7D-01 | REPORT-001 | OUTPUT_NOT_PRODUCED | Phase 7 did not produce REPORT-001; the report format remains deferred and report content is opaque bytes | UX-005#0 | PHASE_8 | ACCEPTED | ACCEPTED_OPTION_A |
| P7D-02 | WCAG 2.2 AA | GATE_CRITERION_NOT_VERIFIED | Accessibility is specified as design requirements only; conformance with WCAG 2.2 AA is not claimed or tested | UX-006#6 | PHASE_10 | ACCEPTED | ACCEPTED_OPTION_A |
<!-- PC7:deviations:END -->

## 7. Deferred-decision register

Every deferred decision of UX-001 to UX-006 is listed once, verbatim, with its disposition. CARRIED decisions move to a
Phase-8, Phase-9, Phase-10 or programme owner; no carried decision is left with a Phase-7 package. RESOLVED_BY means a
later closed package designed it; SUPERSEDED_BY points to the later carried entry that covers the outstanding decision.
UX-003#6, UX-004#8 and UX-005#7 are superseded by UX-006#1: its responsive layout details remain separately
actionable in Phase 9, owned by the Phase 9 design system with Product / Accessibility UX. UX-006 governs accessibility
and responsive behaviour requirements, while detailed layouts and breakpoint values remain NOT YET SPECIFIED.

<!-- PC7:disposition_counts:BEGIN -->
| Disposition | Count |
| --- | --- |
| CARRIED | 38 |
| SUPERSEDED_BY | 9 |
| RESOLVED_BY | 1 |
<!-- PC7:disposition_counts:END -->

<!-- PC7:decisions:BEGIN -->
| Decision | Text | Source owner | Disposition | Target | Carried owner / reference |
| --- | --- | --- | --- | --- | --- |
| UX-001#0 | Browser session / CSRF profile; accepted OIDC boundary unchanged | Phase 7 / Security Architect before browser implementation | CARRIED | PHASE_8 | Security Architect (browser session / CSRF profile before any browser implementation; PLAN-001 prerequisite) |
| UX-001#1 | User data export lacks an accepted API operation; no UX data-export surface | P7-WP5 / API owner; later governed API revision | SUPERSEDED_BY | — | UX-005#2 |
| UX-001#2 | Administrator assignment target and If-Match acquisition; no queue-read or principal-directory capability for administrator-only callers | P7-WP4 / API owner; resolve before detailed assignment workflow | SUPERSEDED_BY | — | UX-004#0 |
| UX-001#3 | Report format and source-pinned comparison | P7-WP5 / Reporting | SUPERSEDED_BY | — | UX-005#0 |
| UX-001#4 | Provider identity and detailed outcome attribution beyond current EnrichmentView | P7-WP6 / API owner; governed API revision if needed | SUPERSEDED_BY | — | UX-006#0 |
| UX-001#5 | Detailed intake, result, review and accessibility interactions | P7-WP2 through P7-WP6 owners | RESOLVED_BY | — | UX-002, UX-003, UX-004, UX-005, UX-006 |
| UX-001#6 | Breakpoints and responsive behavior | P7-WP6 / Accessibility UX | SUPERSEDED_BY | — | UX-006#1 |
| UX-002#0 | Accepted media types and size limit are configuration with no discovery operation; how users learn limits before upload | API owner / Phase 9 configuration (governed API revision if a discovery operation is needed) | CARRIED | PHASE_9 | API owner / Phase 9 configuration (governed API revision only if a discovery operation is needed) |
| UX-002#1 | Consent / acknowledgement capture has no accepted API field | Sponsor + legal/governance with API owner | CARRIED | PROGRAMME | Sponsor + legal/governance with API owner |
| UX-002#2 | Email source accepted media type(s) | API owner / Phase 9 configuration | CARRIED | PHASE_9 | API owner / Phase 9 configuration |
| UX-002#3 | Whether intake offers an AI-assisted analysis_mode choice | Programme / P7-WP3 with AI governance | SUPERSEDED_BY | — | UX-003#4 |
| UX-002#4 | Local draft persistence on the device (sensitive content at rest in the browser) | Security Architect / Phase 9 | CARRIED | PHASE_9 | Security Architect / Phase 9 |
| UX-002#5 | Abandoned AWAITING_CONTENT items: user-visible cleanup path beyond governed deletion | P7-WP5 / API owner | CARRIED | PHASE_8 | API owner (governed API revision, scheduled in PLAN-001) |
| UX-002#6 | Polling cadence, retry limits and backoff values | Phase 9 implementation profile (OPS-001 parameters) | CARRIED | PHASE_9 | Phase 9 implementation profile (OPS-001 parameters) |
| UX-002#7 | Dedicated artifact_kind for user context (currently OTHER + vendor media type) | Next DATA-001-WP2 vocabulary revision (API-001 §41 #3) | CARRIED | PHASE_8 | Data owner (next governed DATA-001-WP2 vocabulary revision, scheduled in PLAN-001) |
| UX-002#8 | No accepted API field distinguishes PROCESSING sub-states (CONTENT_PENDING / FAILED_RETRYABLE): re-PUT and finalize behaviour after an interrupted PUT, or a readiness indicator, needs API-owner clarification; until then finalization is unavailable without an observed successful PUT | API owner (governed API revision if required) | CARRIED | PHASE_8 | API owner (governed API revision, scheduled in PLAN-001) |
| UX-003#0 | Negative and mitigating indicator identities are not exposed by DetectionResultResponse v1; presenting them needs a governed API revision | API owner (governed API revision) | CARRIED | PHASE_8 | API owner (governed API revision, scheduled in PLAN-001) |
| UX-003#1 | Supporting observations and spans are not exposed by DetectionResultResponse v1; observation-level explanation needs a governed API revision and the P7-WP4 content boundary | API owner with P7-WP4 | CARRIED | PHASE_8 | API owner (governed API revision, scheduled in PLAN-001) |
| UX-003#2 | Per-action reason identifiers are not exposed by RecommendedActionView; action-specific reasons need a governed API revision | API owner (governed API revision) | CARRIED | PHASE_8 | API owner (governed API revision, scheduled in PLAN-001) |
| UX-003#3 | Explanation evidence_basis is a list of strings in the API; its exact rendering as source statements needs confirmation of the serialized form | API owner | CARRIED | PHASE_8 | API owner (governed API revision, scheduled in PLAN-001) |
| UX-003#4 | Whether intake offers an AI-assisted analysis_mode choice (carried from UX-002; not resolved here) | Programme with AI governance | CARRIED | PROGRAMME | Programme with AI governance |
| UX-003#5 | Final user-facing copy, translation and plain-language review of labels and meanings | Product / Result UX with Phase 9 | CARRIED | PHASE_9 | Product / Result UX with Phase 9 |
| UX-003#6 | Detailed accessible and responsive result layout | P7-WP6 / Accessibility UX | SUPERSEDED_BY | — | UX-006#1 |
| UX-003#7 | Phase-3 result.py matched_rule_ids() counts any MATCHED rule result as fired while aggregation eligibility requires COMPOSITE; impact: a SUPPRESSION-kind MATCHED result could be counted as a fired rule by the envelope validator; the result surface follows aggregation eligibility (a SUPPRESSION-kind rule is never a finding) pending Phase-3 owner clarification (round-2 R2-INFO-1) | Detection owner (Phase-3 governance) | CARRIED | PROGRAMME | Detection owner (Phase-3 governance) |
| UX-004#0 | Administrator assignment target and If-Match acquisition: no administrator queue-read or principal-directory capability exists, so the assignment command can only act on a review item reference, ETag and analyst identifier supplied through an accepted channel | API owner (governed API revision), carried from UX-001 | CARRIED | PHASE_8 | API owner (governed API revision, scheduled in PLAN-001) |
| UX-004#1 | A CASE_EVIDENCE break-glass grant has no accepted evidence-listing operation for administrators (listEvidence and getCase are USER/ANALYST only); evidence identifiers are reachable only from content-free audit metadata | API owner with Security Architect | CARRIED | PHASE_8 | API owner (governed API revision, scheduled in PLAN-001) with Security Architect |
| UX-004#2 | No operation lists break-glass grants awaiting review; reviewers find grants through listAuditEvents (BREAK_GLASS_ACTIVATED) and then getBreakGlassGrant | API owner with Security Architect | CARRIED | PHASE_8 | API owner (governed API revision, scheduled in PLAN-001) with Security Architect |
| UX-004#3 | reason_code on assignment and access-grant revocation has no governed vocabulary | API owner (governed vocabulary) | CARRIED | PHASE_8 | API owner (governed API revision, scheduled in PLAN-001) (governed vocabulary) |
| UX-004#4 | Principals appear as opaque identifiers; no principal display-name capability exists for queues, grants or audit | API owner with Product / Security UX | CARRIED | PHASE_8 | API owner (governed API revision, scheduled in PLAN-001) with Product / Security UX |
| UX-004#5 | An assigned analyst without permits_evidence_content may author a C4 rationale that the same analyst cannot read back; confirm the intended authoring rule | API owner with Security Architect | CARRIED | PHASE_8 | API owner (governed API revision, scheduled in PLAN-001) with Security Architect |
| UX-004#6 | Break-glass duration is server-set and NOT YET SPECIFIED; the UX shows only the server's expires_at | Security Architect / P5-WP5 implementation | CARRIED | PHASE_9 | Security Architect / Phase 9 implementation |
| UX-004#7 | Final user-facing copy, translation and plain-language review of review and security labels | Product / Security UX with Phase 9 | CARRIED | PHASE_9 | Product / Security UX with Phase 9 |
| UX-004#8 | Detailed accessible and responsive layout of review and security surfaces | P7-WP6 / Accessibility UX | SUPERSEDED_BY | — | UX-006#1 |
| UX-005#0 | Report format and layout (REPORT-001); ReportContentDownload is opaque bytes until it is defined | Product / Reporting (REPORT-001), carried from UX-001 | CARRIED | PHASE_8 | Product / Reporting (REPORT-001 must be produced before the report slice is planned) |
| UX-005#1 | Source-pinned historical comparison has no accepted API capability; records are shown separately and no comparison is computed | API owner with Product / Reporting, carried from UX-001 | CARRIED | PHASE_8 | API owner (governed API revision, scheduled in PLAN-001) with Product / Reporting |
| UX-005#2 | User data export lacks an accepted API operation; no data-export surface is designed | API owner (governed API revision), carried from UX-001 | CARRIED | PHASE_8 | API owner (governed API revision, scheduled in PLAN-001) |
| UX-005#3 | createCorrection is an accepted operation placed on no UX-001 surface; its placement (UX-EVALUATION context) is recorded here pending a governed UX-001 revision | Programme UX governance | CARRIED | PROGRAMME | Programme UX governance (governed UX-001 revision) |
| UX-005#4 | reason_code for report, replay, re-analysis, correction and deletion commands has no governed vocabulary | API owner (governed vocabulary) | CARRIED | PHASE_8 | API owner (governed API revision, scheduled in PLAN-001) (governed vocabulary) |
| UX-005#5 | Retention period and tombstone content after governed removal are not specified (OI-05) | Sponsor + legal/governance (OI-05) | CARRIED | PROGRAMME | Sponsor + legal/governance (OI-05) |
| UX-005#6 | Final user-facing copy, translation and plain-language review of reporting and history labels | Product / Reporting UX with Phase 9 | CARRIED | PHASE_9 | Product / Reporting UX with Phase 9 |
| UX-005#7 | Detailed accessible and responsive layout of reporting and history surfaces | P7-WP6 / Accessibility UX | SUPERSEDED_BY | — | UX-006#1 |
| UX-006#0 | Provider identity and detailed outcome attribution beyond the current EnrichmentView | API owner (governed API revision), carried from UX-001 | CARRIED | PHASE_8 | API owner (governed API revision, scheduled in PLAN-001) |
| UX-006#1 | Breakpoint values and responsive layout details are NOT YET SPECIFIED; only behaviour rules are governed here | Phase 9 design system with Product / Accessibility UX, carried from UX-001 | CARRIED | PHASE_9 | Phase 9 design system with Product / Accessibility UX |
| UX-006#2 | The integration lookup outcome (FOUND, NOT_FOUND, UNAVAILABLE, INVALID_RESPONSE) is not exposed by EnrichmentView, so NOT_FOUND and UNAVAILABLE cannot be told apart from neighbouring outcomes | API owner with INT-001 owner (governed API revision) | CARRIED | PHASE_8 | API owner (governed API revision, scheduled in PLAN-001) with INT-001 owner |
| UX-006#3 | Enrichment freshness (FRESH, STALE, UNKNOWN) is not exposed by EnrichmentView and has no governed period | API owner with provider policy owner | CARRIED | PHASE_8 | API owner (governed API revision, scheduled in PLAN-001) with provider policy owner |
| UX-006#4 | Detection scope beyond English (ADR-0014 options B/C) requires verified non-English evidence | Sponsor with Knowledge governance (ADR-0014) | CARRIED | PROGRAMME | Sponsor with Knowledge governance (ADR-0014) |
| UX-006#5 | Interface language, translation and final user-facing copy | Product / Accessibility UX with Phase 9 | CARRIED | PHASE_9 | Product / Accessibility UX with Phase 9 |
| UX-006#6 | Accessibility conformance testing with assistive technologies; no conformance is claimed | Phase 10 / QA Lead | CARRIED | PHASE_10 | Phase 10 / QA Lead (assistive-technology and conformance testing) |
<!-- PC7:decisions:END -->

## 8. Phase-8 handoff

What Phase 8 (PLAN-001, the implementation blueprint) receives, grouped by owner phase. Items marked PHASE_8 must be
planned in PLAN-001, most as governed API or vocabulary revisions that the dependent Phase-9 slice needs; PHASE_9 items
are implementation choices; PHASE_10 items are testing; PROGRAMME items are sponsor or governance decisions. RSK-006
remains the prerequisite for any Phase-9 implementation.

<!-- PC7:phase8:BEGIN -->
| Target | Item | Description | Owner |
| --- | --- | --- | --- |
| PHASE_8 prerequisite | RSK-006 | Docker and PostgreSQL must be installed before Phase 9 implementation can begin (roadmap: resolve in Phase 8) | Sponsor (admin install) |
| PHASE_8 | P7C-01 | Knowledge-lifecycle commands and operational health have no Phase-7 UX surface or design | Product with Knowledge governance and Operations (decide in PLAN-001 whether operator UX is in scope) |
| PHASE_8 | UX-001#0 | Browser session / CSRF profile; accepted OIDC boundary unchanged | Security Architect (browser session / CSRF profile before any browser implementation; PLAN-001 prerequisite) |
| PHASE_8 | UX-002#5 | Abandoned AWAITING_CONTENT items: user-visible cleanup path beyond governed deletion | API owner (governed API revision, scheduled in PLAN-001) |
| PHASE_8 | UX-002#7 | Dedicated artifact_kind for user context (currently OTHER + vendor media type) | Data owner (next governed DATA-001-WP2 vocabulary revision, scheduled in PLAN-001) |
| PHASE_8 | UX-002#8 | No accepted API field distinguishes PROCESSING sub-states (CONTENT_PENDING / FAILED_RETRYABLE): re-PUT and finalize behaviour after an interrupted PUT, or a readiness indicator, needs API-owner clarification; until then finalization is unavailable without an observed successful PUT | API owner (governed API revision, scheduled in PLAN-001) |
| PHASE_8 | UX-003#0 | Negative and mitigating indicator identities are not exposed by DetectionResultResponse v1; presenting them needs a governed API revision | API owner (governed API revision, scheduled in PLAN-001) |
| PHASE_8 | UX-003#1 | Supporting observations and spans are not exposed by DetectionResultResponse v1; observation-level explanation needs a governed API revision and the P7-WP4 content boundary | API owner (governed API revision, scheduled in PLAN-001) |
| PHASE_8 | UX-003#2 | Per-action reason identifiers are not exposed by RecommendedActionView; action-specific reasons need a governed API revision | API owner (governed API revision, scheduled in PLAN-001) |
| PHASE_8 | UX-003#3 | Explanation evidence_basis is a list of strings in the API; its exact rendering as source statements needs confirmation of the serialized form | API owner (governed API revision, scheduled in PLAN-001) |
| PHASE_8 | UX-004#0 | Administrator assignment target and If-Match acquisition: no administrator queue-read or principal-directory capability exists, so the assignment command can only act on a review item reference, ETag and analyst identifier supplied through an accepted channel | API owner (governed API revision, scheduled in PLAN-001) |
| PHASE_8 | UX-004#1 | A CASE_EVIDENCE break-glass grant has no accepted evidence-listing operation for administrators (listEvidence and getCase are USER/ANALYST only); evidence identifiers are reachable only from content-free audit metadata | API owner (governed API revision, scheduled in PLAN-001) with Security Architect |
| PHASE_8 | UX-004#2 | No operation lists break-glass grants awaiting review; reviewers find grants through listAuditEvents (BREAK_GLASS_ACTIVATED) and then getBreakGlassGrant | API owner (governed API revision, scheduled in PLAN-001) with Security Architect |
| PHASE_8 | UX-004#3 | reason_code on assignment and access-grant revocation has no governed vocabulary | API owner (governed API revision, scheduled in PLAN-001) (governed vocabulary) |
| PHASE_8 | UX-004#4 | Principals appear as opaque identifiers; no principal display-name capability exists for queues, grants or audit | API owner (governed API revision, scheduled in PLAN-001) with Product / Security UX |
| PHASE_8 | UX-004#5 | An assigned analyst without permits_evidence_content may author a C4 rationale that the same analyst cannot read back; confirm the intended authoring rule | API owner (governed API revision, scheduled in PLAN-001) with Security Architect |
| PHASE_8 | UX-005#0 | Report format and layout (REPORT-001); ReportContentDownload is opaque bytes until it is defined | Product / Reporting (REPORT-001 must be produced before the report slice is planned) |
| PHASE_8 | UX-005#1 | Source-pinned historical comparison has no accepted API capability; records are shown separately and no comparison is computed | API owner (governed API revision, scheduled in PLAN-001) with Product / Reporting |
| PHASE_8 | UX-005#2 | User data export lacks an accepted API operation; no data-export surface is designed | API owner (governed API revision, scheduled in PLAN-001) |
| PHASE_8 | UX-005#4 | reason_code for report, replay, re-analysis, correction and deletion commands has no governed vocabulary | API owner (governed API revision, scheduled in PLAN-001) (governed vocabulary) |
| PHASE_8 | UX-006#0 | Provider identity and detailed outcome attribution beyond the current EnrichmentView | API owner (governed API revision, scheduled in PLAN-001) |
| PHASE_8 | UX-006#2 | The integration lookup outcome (FOUND, NOT_FOUND, UNAVAILABLE, INVALID_RESPONSE) is not exposed by EnrichmentView, so NOT_FOUND and UNAVAILABLE cannot be told apart from neighbouring outcomes | API owner (governed API revision, scheduled in PLAN-001) with INT-001 owner |
| PHASE_8 | UX-006#3 | Enrichment freshness (FRESH, STALE, UNKNOWN) is not exposed by EnrichmentView and has no governed period | API owner (governed API revision, scheduled in PLAN-001) with provider policy owner |
| PHASE_9 | UX-002#0 | Accepted media types and size limit are configuration with no discovery operation; how users learn limits before upload | API owner / Phase 9 configuration (governed API revision only if a discovery operation is needed) |
| PHASE_9 | UX-002#2 | Email source accepted media type(s) | API owner / Phase 9 configuration |
| PHASE_9 | UX-002#4 | Local draft persistence on the device (sensitive content at rest in the browser) | Security Architect / Phase 9 |
| PHASE_9 | UX-002#6 | Polling cadence, retry limits and backoff values | Phase 9 implementation profile (OPS-001 parameters) |
| PHASE_9 | UX-003#5 | Final user-facing copy, translation and plain-language review of labels and meanings | Product / Result UX with Phase 9 |
| PHASE_9 | UX-004#6 | Break-glass duration is server-set and NOT YET SPECIFIED; the UX shows only the server's expires_at | Security Architect / Phase 9 implementation |
| PHASE_9 | UX-004#7 | Final user-facing copy, translation and plain-language review of review and security labels | Product / Security UX with Phase 9 |
| PHASE_9 | UX-005#6 | Final user-facing copy, translation and plain-language review of reporting and history labels | Product / Reporting UX with Phase 9 |
| PHASE_9 | UX-006#1 | Breakpoint values and responsive layout details are NOT YET SPECIFIED; only behaviour rules are governed here | Phase 9 design system with Product / Accessibility UX |
| PHASE_9 | UX-006#5 | Interface language, translation and final user-facing copy | Product / Accessibility UX with Phase 9 |
| PHASE_10 | UX-006#6 | Accessibility conformance testing with assistive technologies; no conformance is claimed | Phase 10 / QA Lead (assistive-technology and conformance testing) |
| PROGRAMME | P7C-02 | UX-001 and GATE-026 keep their pre-merge status rows because later contracts hash-pin UX-001; P7-WP1 merge and CI are recorded in this closure instead | Programme governance (next governed UX snapshot revision) |
| PROGRAMME | UX-002#1 | Consent / acknowledgement capture has no accepted API field | Sponsor + legal/governance with API owner |
| PROGRAMME | UX-003#4 | Whether intake offers an AI-assisted analysis_mode choice (carried from UX-002; not resolved here) | Programme with AI governance |
| PROGRAMME | UX-003#7 | Phase-3 result.py matched_rule_ids() counts any MATCHED rule result as fired while aggregation eligibility requires COMPOSITE; impact: a SUPPRESSION-kind MATCHED result could be counted as a fired rule by the envelope validator; the result surface follows aggregation eligibility (a SUPPRESSION-kind rule is never a finding) pending Phase-3 owner clarification (round-2 R2-INFO-1) | Detection owner (Phase-3 governance) |
| PROGRAMME | UX-005#3 | createCorrection is an accepted operation placed on no UX-001 surface; its placement (UX-EVALUATION context) is recorded here pending a governed UX-001 revision | Programme UX governance (governed UX-001 revision) |
| PROGRAMME | UX-005#5 | Retention period and tombstone content after governed removal are not specified (OI-05) | Sponsor + legal/governance (OI-05) |
| PROGRAMME | UX-006#4 | Detection scope beyond English (ADR-0014 options B/C) requires verified non-English evidence | Sponsor with Knowledge governance (ADR-0014) |
<!-- PC7:phase8:END -->

## 9. Carryovers

<!-- PC7:carryovers:BEGIN -->
| Item | Status | Owner |
| --- | --- | --- |
| G-09 | OPEN | Phase 10 (testing/evaluation; QA Lead) with Sponsor for any corpus access |
| OI-05 | OPEN | Sponsor + legal/governance |
| ASM-002 | UNCONFIRMED / PROVISIONAL | Sponsor / Programme |
| P6-WP7-LOW-1 | OPEN / NON-BLOCKING | Next governed Phase-6 snapshot revision / Programme governance |
<!-- PC7:carryovers:END -->

## 10. Claim boundary and lifecycle

This is a design-contract closure only. No frontend, backend or API was built or changed, nothing was tested with users
or assistive technologies, no accessibility conformance is claimed, and no real-world detection effectiveness is
claimed (G-09). The structured lifecycle in the machine record is authoritative and fails closed: a review round,
approval or merge evidence counts only when it equals the record pinned in `validate_phase7_closure.py` by a governed
bookkeeping step. Round 1 remains REQUEST_CHANGES (0 BLOCKER, 0 HIGH, 2 MEDIUM, 0 LOW, 0 INFO);
Round 2 targeted independent rereview returned APPROVE (0/0/0/0/0) and closed both findings in GATE-032 §7.
WP7 lifecycle and final Phase-7 design-contract lifecycle are CLOSED. PR #43 merged as
`0a21d1f858eb7680e05ce703966201f06902e4c8`, with PR head `5af988d2740c4d826abc0f2e3074cd1fe3d28526`.
PR-head CI #84 (`38266862243`) and post-merge CI #85 (`38273120361`) completed SUCCESS, both required jobs,
as recorded in GATE-032 §8 and pinned in the machine record and validator. Both independent review rounds and their
closed findings are preserved. Option A acceptance (GATE-032 §6) does not satisfy or waive REPORT-001 or WCAG: the
report format remains required in Phase 8, and accessibility conformance testing/evidence remain required in Phase 10.
PLAN-001 approval is recorded separately; Phase 8 itself is NOT CLOSED and no Phase 9 implementation has begun.
