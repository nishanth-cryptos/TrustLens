# GATE-030 — Phase-7 reporting and historical workflows

| Field | Value |
| --- | --- |
| Document ID | GATE-030 |
| Version | 0.1 |
| Status | P7-WP5 REPORTING AND HISTORICAL WORKFLOWS UX APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING |
| Phase / work package | Phase 7 — UX, Evidence & Reporting Design / P7-WP5 |
| Owner role | Product / Reporting UX |
| Branch | phase7-wp5-reporting-workflows |
| Baseline | b5a663a6dd6343b17b7cf8dfa927c0aae4f8ebd9 (P7-WP4 closure merge, PR #40) |
| Deliverable | [UX-005](../07-ux/UX-005-reporting-historical-workflows.md); [`ux-reporting-v1.json`](../../contracts/ux/ux-reporting-v1.json); [`ux-reporting-contract.schema.json`](../../contracts/ux/ux-reporting-contract.schema.json); `contracts/ux/fixtures/reporting-negative-mutations.json`; `knowledge/validation/validate_ux_reporting.py` |
| Foundation | [UX-001](../07-ux/UX-001-experience-foundation-information-architecture.md) / GATE-026, consuming UX-002 / GATE-027, UX-003 / GATE-028 and UX-004 / GATE-029 (closed, not modified) |
| Independent review | Round 1: REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 2 / LOW 0 / INFO 0); Round 2: REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 0 / INFO 0); Round 3: APPROVE (BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 0 / INFO 0) |
| Last updated | 2026-10-11 |

## 1. Gate reservation and boundary

The builder confirmed that GATE-030 and UX-005 were unused at the baseline and that P7-WP4 was CLOSED there (PR #40).
The initial independent review (round 1, §7) and the targeted re-review (round 2) returned REQUEST_CHANGES. After the
builder's corrections, the round-3 targeted re-review returned **APPROVE** (§7) with no open finding. The work package
is **approved following independent review — remote CI + merge pending**; it is not merged and not CLOSED: CLOSED
requires the PR merge and remote-CI evidence pinned by the governed post-merge step. The gate adds no API capability,
persisted concept, permission grant, report format, retention rule, frontend or runtime. P7-WP6 and later work packages
are not started.

## 2. Acceptance criteria

| # | Criterion | Evidence | State |
| --- | --- | --- | --- |
| 1 | Scope equals the UX-001 P7-WP5 handoff; every request item mapped; deferred items owned | UX-005 §1; UXP-08 | MET (builder) |
| 2 | Surfaces and operation access equal UX-001; correction placement recorded without changing UX-001 | UX-005 §2; UXP-09…UXP-11 | MET (builder) |
| 3 | Every owned operation equals the accepted API and OpenAPI | UX-005 §2; UXP-10 | MET (builder) |
| 4 | Errors map to UX-001 states with retryability-consistent recovery | UX-005 §3; UXP-13…UXP-15 | MET (builder) |
| 5 | Governed removal (410) distinct from not found or not visible (404); tombstone behaviour exact | UX-005 §4; UXP-16 | MET (builder) |
| 6 | Reports case-scoped, source-pinned, revisioned, attachment-only, audited, never automatic | UX-005 §5; UXP-17, UXP-19, UXP-20 | MET (builder) |
| 7 | Report regeneration unavailable is honest: no approximation, substitution, AI or reconstruction | UX-005 §5; UXP-18 | MET (builder) |
| 8 | Replay exact historical verification; unavailable an explicit outcome; never re-analysis | UX-005 §6; UXP-21 | MET (builder) |
| 9 | Re-analysis and correction create new evaluations; history kept | UX-005 §7; UXP-22, UXP-23 | MET (builder) |
| 10 | Deletion request, decision, execution and completion distinct; only COMPLETE claims completion | UX-005 §8; UXP-24 | MET (builder) |
| 11 | Historical comparison never computed without an API capability | UX-005 §9; UXP-25 | MET (builder) |
| 12 | Protected copy governed; audit consequences shown | UX-005 §10; UXP-26…UXP-30 | MET (builder) |
| 13 | Scenarios reproduced by an independent decision procedure | UX-005 §10; UXP-34…UXP-36 | MET (builder) |
| 14 | Missing capabilities recorded as owned deferred decisions | UX-005 §11; UXP-31 | MET (builder) |
| 15 | Validator, negative mutations, positive controls and CI self-test defect bite | `validate_ux_reporting.py`; fixtures; `ci_selftest.py` | MET (builder) |
| 16 | Independent review | §7 round 1 REQUEST_CHANGES (0/0/2/0/0); round 2 REQUEST_CHANGES (0/0/1/0/0); round 3 APPROVE (0/0/0/0/0) | **MET** |
| 17 | Remote CI + merge | Not yet performed | **PENDING** |
| 18 | Every security-critical label and meaning governed and checked on its own (round-1 MEDIUM-1) | UX-005 §10; UXP-28, UXP-29 | CLOSED (round 3) |
| 19 | Deletion decisions offered only for REQUESTED requests; terminal requests read-only (round-1 MEDIUM-2) | UX-005 §8; UXP-24, UXP-34…UXP-36 | CLOSED (round 2) |
| 20 | Replay-state copy governed; a pending replay never claims completion; an explicit denial of engine substitution is allowed (round-2 R2-MEDIUM-1) | UX-005 §10; UXP-28, UXP-29 | CLOSED (round 3) |

## 3. Validation evidence (local builder)

The authoritative figures are those recorded in the P7-WP5 builder STOP REPORT. `validate_ux_reporting.py` runs in the
canonical `run_all` suite, and `ci_selftest` carries a P7-WP5 defect (deletion request presented as completed removal)
that only `validate_ux_reporting.py` catches. `ENGINE_VERSION = 1.0.0`. This is builder evidence, not independent review
or remote CI.

## 4. Preserved items

<!-- UXP:carryovers:BEGIN -->
| Item | Status | Owner |
| --- | --- | --- |
| G-09 | OPEN | Phase 10 (testing/evaluation; QA Lead) with Sponsor for any corpus access |
| OI-05 | OPEN | Sponsor + legal/governance |
| ASM-002 | UNCONFIRMED / PROVISIONAL | Sponsor / Programme |
| P6-WP7-LOW-1 | OPEN / NON-BLOCKING | Next governed Phase-6 snapshot revision / Programme governance |
<!-- UXP:carryovers:END -->

Phase 6 stays CLOSED and frozen (19-artifact snapshot), and the P7-WP1 to P7-WP4 deliverables are unmodified. There is
no tenant field, retention period, report format or frontend, and no production-readiness, usability-testing,
accessibility-conformance, security-testing or detection-effectiveness claim.

## 5. Decision

**P7-WP5 REPORTING AND HISTORICAL WORKFLOWS UX APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING**. Recommendation: proceed to the authorized P7-WP5 commit and PR. After the PR merges with successful
remote CI, the governed post-merge step may pin the merge evidence and record the work package as CLOSED. Not merged, not
closed and not an implemented reporting experience; P7-WP6 is not started.

## 6. Open decisions

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

## 7. Independent review record

**Round 1 — initial independent review: REQUEST_CHANGES** (BLOCKER 0 / HIGH 0 / MEDIUM 2 / LOW 0 / INFO 0). The result
was supplied to the builder by the programme. MEDIUM-1: security-critical labels were not governed, so a REQUESTED or
AUTHORIZED deletion could read as completed removal, a removed report as not found, and a replay outcome could claim the
current engine replaces an unavailable one, even with synchronized documentation. MEDIUM-2: a rejection was offered and
issued for a COMPLETE deletion request because decision eligibility ignored the request state. The builder reproduced
all five counterexamples against the round-0 candidate before correcting them; both findings are
CORRECTED_PENDING_TARGETED_REREVIEW. No reviewer identity is recorded here, and offline validation cannot authenticate
one.

**Round 2 — targeted independent re-review: REQUEST_CHANGES** (BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 0 / INFO 0). The
result was supplied to the builder by the programme. MEDIUM-2 (deletion-decision eligibility) is closed. R2-MEDIUM-1
re-raises MEDIUM-1: replay-state labels were ungoverned, so a PENDING replay could read as completed successfully, and
the engine-substitution rule rejected an explicit denial ("The current engine is not used for replay."). The builder
reproduced both against the round-1 candidate, governed the replay-state copy and made the substitution rule
clause-aware; MEDIUM-1 and R2-MEDIUM-1 are CORRECTED_PENDING_TARGETED_REREVIEW. No reviewer identity is recorded here.

**Round 3 — targeted independent re-review: APPROVE** (BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 0 / INFO 0). The result was
supplied to the builder by the programme. MEDIUM-1 and R2-MEDIUM-1 are closed; with MEDIUM-2 (round 2), no finding
remains open. No reviewer identity, external review URL, signed artifact, commit, PR or CI run is recorded here because
none was supplied. Lifecycle effect: CANDIDATE → APPROVED; merge evidence is absent, so CLOSED remains unavailable
(fails closed).

A review round, approval or merge evidence counts only when a governed bookkeeping step pins the exact record in
`validate_ux_reporting.py`; the tables below are its projections.

<!-- UXP:review_history:BEGIN -->
| Round | Kind | Decision | BLOCKER | HIGH | MEDIUM | LOW | INFO | Reviewer role | Evidence source | Record |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | INITIAL_INDEPENDENT_REVIEW | REQUEST_CHANGES | 0 | 0 | 2 | 0 | 0 | Independent reviewer | Independent review result supplied to the builder by the programme | GATE-030 §7 |
| 2 | TARGETED_INDEPENDENT_REREVIEW | REQUEST_CHANGES | 0 | 0 | 1 | 0 | 0 | Independent reviewer | Independent review result supplied to the builder by the programme | GATE-030 §7 |
| 3 | TARGETED_INDEPENDENT_REREVIEW | APPROVE | 0 | 0 | 0 | 0 | 0 | Independent reviewer | Independent review result supplied to the builder by the programme | GATE-030 §7 |
<!-- UXP:review_history:END -->

<!-- UXP:findings:BEGIN -->
| Finding | Round | Severity | Summary | Disposition | Closed in round | Owner |
| --- | --- | --- | --- | --- | --- | --- |
| MEDIUM-1 | 1 | MEDIUM | Security-critical display labels were not governed: REQUESTED and AUTHORIZED could read as completed removal, a removed report as not found, and a replay outcome could claim current-engine substitution | CLOSED_BY_REREVIEW | 3 | P7-WP5 builder |
| MEDIUM-2 | 1 | MEDIUM | Deletion authorization and rejection were offered for any visible request: a rejection was offered and issued for a COMPLETE request | CLOSED_BY_REREVIEW | 2 | P7-WP5 builder |
| R2-MEDIUM-1 | 2 | MEDIUM | Re-raised MEDIUM-1: replay-state labels were ungoverned (a PENDING replay could read as completed successfully), and an explicit denial of current-engine substitution was wrongly rejected | CLOSED_BY_REREVIEW | 3 | P7-WP5 builder |
<!-- UXP:findings:END -->
