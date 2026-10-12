# GATE-031 — Phase-7 accessibility, responsive behaviour and external enrichment

| Field | Value |
| --- | --- |
| Document ID | GATE-031 |
| Version | 0.1 |
| Status | P7-WP6 ACCESSIBILITY, RESPONSIVE AND ENRICHMENT UX APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING |
| Phase / work package | Phase 7 — UX, Evidence & Reporting Design / P7-WP6 |
| Owner role | Product / Accessibility UX |
| Branch | phase7-wp6-accessibility-ux |
| Baseline | 7f3c2899dae693d3b497faa3a68f691890488d2d (P7-WP5 delivery merge, PR #41); the P7-WP5 post-merge closure (GATE-030 §8) ships alongside on this branch |
| Deliverable | [UX-006](../07-ux/UX-006-accessibility-responsive-enrichment.md); [`ux-accessibility-v1.json`](../../contracts/ux/ux-accessibility-v1.json); [`ux-accessibility-contract.schema.json`](../../contracts/ux/ux-accessibility-contract.schema.json); `contracts/ux/fixtures/accessibility-negative-mutations.json`; `knowledge/validation/validate_ux_accessibility.py` |
| Foundation | [UX-001](../07-ux/UX-001-experience-foundation-information-architecture.md) / GATE-026, consuming UX-002 to UX-005 / GATE-027 to GATE-030 (closed, not modified), INT-001 and ADR-0014 / DEC-008 |
| Independent review | Round 1: REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 2 / LOW 0 / INFO 0); Round 2: APPROVE (BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 0 / INFO 0) |
| Last updated | 2026-10-12 |

## 1. Gate reservation and boundary

The builder confirmed that GATE-031 and UX-006 were unused at the baseline, and that P7-WP5 was merged there (PR #41)
and is recorded CLOSED by its post-merge closure (GATE-030 §8), which ships on this branch as a separately identifiable
change. The gate adds no API capability, persisted concept, permission grant, provider identity field, lookup-outcome
field, supported language, breakpoint value, frontend or runtime, and makes no accessibility-conformance claim. The
initial independent review (round 1, §7) returned REQUEST_CHANGES; after the builder's corrections, the round-2 targeted
re-review returned **APPROVE** (§7) with no open finding. Remote CI and merge are pending, so the work package is not
closed. P7-WP7 and later work packages are not started.

## 2. Acceptance criteria

| # | Criterion | Evidence | State |
| --- | --- | --- | --- |
| 1 | Scope equals the UX-001 P7-WP6 handoff; every request item mapped; deferred items owned | UX-006 §1; UXA-08 | MET (builder) |
| 2 | Enrichment surface and operation equal UX-001, the accepted API, OpenAPI and INT-001; no new endpoint | UX-006 §2; UXA-09, UXA-10 | MET (builder) |
| 3 | Errors map to UX-001 states with retryability-consistent recovery | UX-006 §2; UXA-11 | MET (builder) |
| 4 | Enrichment advisory only, off the result surface, attributed by category and observation time, no identity, body or freshness claim | UX-006 §3; UXA-12 | MET (builder) |
| 5 | Interpretation derived from INT-001; an outcome is distinguished only when one outcome fits the record | UX-006 §3; UXA-13 | MET (builder) |
| 6 | Provider CLEAN never TrustLens safety; NOT_FOUND and UNAVAILABLE never claimed where the record cannot establish them | UX-006 §3; UXA-14 | MET (builder) |
| 7 | Unsupported language anchored to the English-only scope; never benign; no conclusion; no client detection | UX-006 §4; UXA-16 | MET (builder) |
| 8 | Every UX-001 accessibility commitment covered; announcements field-limited; no conformance claim | UX-006 §5; UXA-17, UXA-18, UXA-23 | MET (builder) |
| 9 | Responsive behaviour without invented breakpoints; permission, control and redaction parity across layouts | UX-006 §6; UXA-19, UXA-20, UXA-29 | MET (builder) |
| 10 | Protected copy governed | UX-006 §7; UXA-15 | MET (builder) |
| 11 | Scenarios reproduced by an independent decision procedure | UX-006 §8; UXA-27…UXA-29 | MET (builder) |
| 12 | Missing capabilities recorded as owned deferred decisions | UX-006 §9; UXA-24 | MET (builder) |
| 13 | Validator, negative mutations, positive controls and CI self-test defect bite | `validate_ux_accessibility.py`; fixtures; `ci_selftest.py` | MET (builder) |
| 14 | Independent review | §7 round 1 REQUEST_CHANGES (0/0/2/0/0); round 2 APPROVE (0/0/0/0/0) | **MET** |
| 15 | Remote CI + merge | Not yet available | PENDING |
| 16 | Duplicate provider-outcome or announcement rows rejected; every original row validated (round-1 MEDIUM-1) | UX-006 §3, §5; UXA-13, UXA-15, UXA-18 | CLOSED (round 2) |
| 17 | A case-scoped resource without case visibility answers the masked not-found state in every layout; a visible case without the role answers access denied (round-1 MEDIUM-2) | UX-006 §2, §8; UXA-27, UXA-29 | CLOSED (round 2) |

## 3. Validation evidence (local builder)

The authoritative figures are those recorded in the P7-WP6 builder STOP REPORT. `validate_ux_accessibility.py` runs in
the canonical `run_all` suite, and `ci_selftest` carries a P7-WP6 defect (provider CLEAN presented as TrustLens safety)
that only `validate_ux_accessibility.py` catches. `ENGINE_VERSION = 1.0.0`. This is builder evidence, not independent
review, assistive-technology testing or remote CI.

## 4. Preserved items

<!-- UXA:carryovers:BEGIN -->
| Item | Status | Owner |
| --- | --- | --- |
| G-09 | OPEN | Phase 10 (testing/evaluation; QA Lead) with Sponsor for any corpus access |
| OI-05 | OPEN | Sponsor + legal/governance |
| ASM-002 | UNCONFIRMED / PROVISIONAL | Sponsor / Programme |
| P6-WP7-LOW-1 | OPEN / NON-BLOCKING | Next governed Phase-6 snapshot revision / Programme governance |
<!-- UXA:carryovers:END -->

Phase 6 stays CLOSED and frozen (19-artifact snapshot), and the P7-WP1 to P7-WP5 deliverables are unmodified apart from
the P7-WP5 closure bookkeeping recorded in GATE-030 §8. There is no tenant field, retention period or frontend, and no
production-readiness, usability-testing, accessibility-conformance, security-testing or detection-effectiveness claim.

## 5. Decision

**P7-WP6 ACCESSIBILITY, RESPONSIVE AND ENRICHMENT UX APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING**. Independently approved (§7, round 2) as a design and contract deliverable; remote CI and merge are
pending, and closure is recorded only by a governed post-merge step. This is not an
implemented accessible or responsive experience.

## 6. Open decisions

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

## 7. Independent review record

**Round 1 — initial independent review: REQUEST_CHANGES** (BLOCKER 0 / HIGH 0 / MEDIUM 2 / LOW 0 / INFO 0). The result
was supplied to the builder by the programme. MEDIUM-1: the validator keyed provider-outcome and announcement rows into
dictionaries before detecting duplicates, so a duplicate CLEAN row labelled "TrustLens safe" with `implies_safe = true`,
or a duplicate CONTENT_WITHHELD announcement reading out `evidence_content`, placed before the valid row, passed every
check. MEDIUM-2: the decision procedure checked role before case visibility, so an administrator or owner without case
visibility was told access denied instead of the masked not-found state required by API-001 §5. The builder reproduced
all four counterexample contexts against the round-0 candidate before correcting them; both findings are
CORRECTED_PENDING_TARGETED_REREVIEW. No reviewer identity is recorded here, and offline validation cannot authenticate
one. Lifecycle effect: none; the work package stays a candidate.

**Round 2 — targeted independent re-review: APPROVE** (BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 0 / INFO 0). The result was
supplied to the builder by the programme. MEDIUM-1 and MEDIUM-2 are closed and no finding remains open. No reviewer
identity, external review URL, signed artifact, commit, PR or CI run is recorded here because none was supplied.
Lifecycle effect: CANDIDATE → APPROVED; merge evidence is absent, so CLOSED remains unavailable (fails closed).

A review round, approval or merge evidence counts only when a governed bookkeeping step pins the exact record in
`validate_ux_accessibility.py`; the tables below are its projections.

<!-- UXA:review_history:BEGIN -->
| Round | Kind | Decision | BLOCKER | HIGH | MEDIUM | LOW | INFO | Reviewer role | Evidence source | Record |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | INITIAL_INDEPENDENT_REVIEW | REQUEST_CHANGES | 0 | 0 | 2 | 0 | 0 | Independent reviewer | Independent review result supplied to the builder by the programme | GATE-031 §7 |
| 2 | TARGETED_INDEPENDENT_REREVIEW | APPROVE | 0 | 0 | 0 | 0 | 0 | Independent reviewer | Independent review result supplied to the builder by the programme | GATE-031 §7 |
<!-- UXA:review_history:END -->

<!-- UXA:findings:BEGIN -->
| Finding | Round | Severity | Summary | Disposition | Closed in round | Owner |
| --- | --- | --- | --- | --- | --- | --- |
| MEDIUM-1 | 1 | MEDIUM | Duplicate semantic rows: provider-outcome and announcement rows were keyed into dictionaries before duplicates were detected, so an earlier unsafe row could hide behind a later valid one | CLOSED_BY_REREVIEW | 2 | Builder (P7-WP6) |
| MEDIUM-2 | 1 | MEDIUM | Case-existence masking: role was checked before case visibility, so a caller without case visibility was told access denied instead of the masked not-found state (API-001 §5) | CLOSED_BY_REREVIEW | 2 | Builder (P7-WP6) |
<!-- UXA:findings:END -->
