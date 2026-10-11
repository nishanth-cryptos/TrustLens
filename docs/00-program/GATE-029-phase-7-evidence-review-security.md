# GATE-029 — Phase-7 evidence review and security UX

| Field | Value |
| --- | --- |
| Document ID | GATE-029 |
| Version | 0.1 |
| Status | P7-WP4 EVIDENCE REVIEW AND SECURITY UX CLOSED |
| Phase / work package | Phase 7 — UX, Evidence & Reporting Design / P7-WP4 |
| Owner role | Product / Security UX |
| Branch | phase7-wp4-evidence-review |
| Baseline | e58dac6bff63a8cb79512338919af6d15db958c1 (P7-WP3 closure merge, PR #38) |
| Deliverable | [UX-004](../07-ux/UX-004-evidence-review-security.md); [`ux-review-v1.json`](../../contracts/ux/ux-review-v1.json); [`ux-review-contract.schema.json`](../../contracts/ux/ux-review-contract.schema.json); `contracts/ux/fixtures/review-negative-mutations.json`; `knowledge/validation/validate_ux_review.py` |
| Foundation | [UX-001](../07-ux/UX-001-experience-foundation-information-architecture.md) / GATE-026, consuming UX-002 / GATE-027 and UX-003 / GATE-028 (closed, not modified) |
| Independent review | Round 1: REQUEST_CHANGES (BLOCKER 0 / HIGH 1 / MEDIUM 3 / LOW 0 / INFO 0); Round 2: REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 2 / LOW 0 / INFO 0); Round 3: REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 0 / INFO 0); Round 4: APPROVE (BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 0 / INFO 0) |
| Last updated | 2026-10-11 |

## 1. Gate reservation and boundary

The builder confirmed that GATE-029 and UX-004 were unused at the baseline and that P7-WP3 was CLOSED there (PR #38).
The initial independent review (round 1, §7) and the targeted re-reviews of rounds 2 and 3 returned REQUEST_CHANGES.
After the builder's corrections, the round-4 targeted re-review returned **APPROVE** (§7). PR #39 then merged with
both required CI jobs successful on the PR-head and merge-commit runs, and the governed post-merge step (§8) recorded
the work package as **CLOSED**. Independent design approval (§7, round 4) and post-merge closure (§8)
are separate records; no further review round was created for the closure. The gate adds no API capability,
persisted concept, permission grant, frontend or runtime. P7-WP5 and later work packages are not started.

## 2. Acceptance criteria

| # | Criterion | Evidence | State |
| --- | --- | --- | --- |
| 1 | Scope equals the UX-001 P7-WP4 handoff; every request item mapped; deferred items owned | UX-004 §1; UXV-08 | MET (builder) |
| 2 | Surfaces and per-operation access equal UX-001 | UX-004 §2; UXV-09, UXV-11 | MET (builder) |
| 3 | Every operation equals the accepted API and exists in OpenAPI; no invented operation | UX-004 §2; UXV-10, UXV-12 | MET (builder) |
| 4 | Errors map to UX-001 states with retryability-consistent recovery | UX-004 §3; UXV-13…UXV-15 | MET (builder) |
| 5 | Evidence content backend-authoritative, permission-gated, attachment-only and audited | UX-004 §4; UXV-16, UXV-17 | MET (builder) |
| 6 | Administrators reach content only through scoped break-glass | UX-004 §4, §8; UXV-18 | MET (builder) |
| 7 | Review queue content-free and provisional under ASM-002 | UX-004 §6; UXV-19 | MET (builder) |
| 8 | Assignment administrator-only, assignee not caller, explicit content choice, If-Match; discovery deferred | UX-004 §7; UXV-20 | MET (builder) |
| 9 | Break-glass explicit, scoped, reasoned, server-timed, signalled, audited and independently reviewed | UX-004 §8; UXV-21 | MET (builder) |
| 10 | Adjudication separate from the immutable DetectionResult; exact-result digest; server actor and time | UX-004 §9; UXV-22, UXV-23 | MET (builder) |
| 11 | C4 rationale only for an assigned analyst with content permission; reads audited | UX-004 §10; UXV-24, UXV-25 | MET (builder) |
| 12 | Audit content-free and administrator-only; audit reads audited; access consequences shown | UX-004 §11; UXV-26, UXV-27 | MET (builder) |
| 13 | Security scenarios reproduced by an independent decision procedure | UX-004 §12; UXV-37…UXV-39 | MET (builder) |
| 14 | No invented operation, field, grant or retention; no exposure; no unsupported claim | UX-004 §13, §15; UXV-30…UXV-36 | MET (builder) |
| 15 | Unresolved capabilities recorded as owned deferred decisions | UX-004 §14; UXV-33 | MET (builder) |
| 16 | Validator, negative mutations, positive controls and CI self-test defect bite | `validate_ux_review.py`; fixtures; `ci_selftest.py` | MET (builder) |
| 19 | Break-glass evidence access caller-bound: grantee, active grant, case and item in scope (round-1 HIGH-1) | UX-004 §8; UXV-21, UXV-37 | CLOSED (round 2) |
| 20 | Protected copy bound to governed messages and disclosure-safe semantics (round-1 MEDIUM-1) | UX-004 §13; UXV-43, UXV-44 | CLOSED (round 3) |
| 21 | Exactly one governed projection per security table; no contradictory rows (round-1 MEDIUM-2) | UX-004; UXV-45 | CLOSED (round 4) |
| 22 | APPROVED and CLOSED require both approval and independent-review claims (round-1 MEDIUM-3) | UX-004 §16; UXV-05 | CLOSED (round 2) |
| 23 | Announcements carry only the fields their presentation state may show; masked states announce no resource metadata (round-2 R2-MEDIUM-1) | UX-004 §13; UXV-47 | CLOSED (round 3) |
| 24 | Security tables recognized as GFM with or without outer pipes; no contradictory visible table (round-2 R2-MEDIUM-2) | UX-004; UXV-45 | CLOSED (round 4) |
| 25 | Security-policy tables recognized by structure and assertions; harmless explanatory tables mentioning a role stay valid (round-3 R3-MEDIUM-2) | UX-004; UXV-45 | CLOSED (round 4) |
| 17 | Independent review | §7 round 1 REQUEST_CHANGES (0/1/3/0/0); round 2 REQUEST_CHANGES (0/0/2/0/0); round 3 REQUEST_CHANGES (0/0/1/0/0); round 4 APPROVE (0/0/0/0/0) | **MET** |
| 18 | Remote CI + merge | §8 — PR #39 merged as `5f8c373`; runs 38139502369 (PR head) and 38142036162 (merge commit) success | **MET** |

## 3. Validation evidence (local builder)

The authoritative figures are those recorded in the P7-WP4 builder STOP REPORT. `validate_ux_review.py` runs in the
canonical `run_all` suite, and `ci_selftest` carries a P7-WP4 defect (administrator evidence content by role) that only
`validate_ux_review.py` catches. `ENGINE_VERSION = 1.0.0`. This is builder evidence, not independent review or remote CI.

## 4. Preserved items

<!-- UXV:carryovers:BEGIN -->
| Item | Status | Owner |
| --- | --- | --- |
| G-09 | OPEN | Phase 10 (testing/evaluation; QA Lead) with Sponsor for any corpus access |
| OI-05 | OPEN | Sponsor + legal/governance |
| ASM-002 | UNCONFIRMED / PROVISIONAL | Sponsor / Programme |
| P6-WP7-LOW-1 | OPEN / NON-BLOCKING | Next governed Phase-6 snapshot revision / Programme governance |
<!-- UXV:carryovers:END -->

Phase 6 stays CLOSED and frozen (19-artifact snapshot), and the P7-WP1, P7-WP2 and P7-WP3 deliverables are unmodified.
There is no tenant field, retention period, break-glass duration or frontend, and no production-readiness,
usability-testing, accessibility-conformance, security-testing or detection-effectiveness claim.

## 5. Decision

**P7-WP4 EVIDENCE REVIEW AND SECURITY UX CLOSED**. The work package is closed as a design and contract deliverable: independently approved (§7, round 4) and merged
with successful remote CI (§8). This is not an implemented review or security experience. P7-WP5 is not started.

## 6. Open decisions

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

## 7. Independent review record

**Round 1 — initial independent review: REQUEST_CHANGES** (BLOCKER 0 / HIGH 1 / MEDIUM 3 / LOW 0 / INFO 0). The result
was supplied to the builder by the programme. The reviewer reproduced four defects: break-glass evidence access was not
bound to the calling grantee; protected display copy could disclose existence, leak rationale detail or claim that an
adjudication replaces the result; a contradictory second security matrix could coexist with the accepted projection;
and an approved or closed record was accepted with a false independent-review claim. The builder reproduced all four
against the round-0 candidate before correcting them. Every finding is CORRECTED_PENDING_TARGETED_REREVIEW until an
independent re-review closes it. No reviewer identity is recorded here, and offline validation cannot authenticate one.

**Round 2 — targeted independent re-review: REQUEST_CHANGES** (BLOCKER 0 / HIGH 0 / MEDIUM 2 / LOW 0 / INFO 0). The
result was supplied to the builder by the programme. HIGH-1 (caller-bound break-glass) and MEDIUM-3 (approval and review
claims) are closed. R2-MEDIUM-1 re-raises MEDIUM-1: the announcement for a masked resource could carry adjudication
outcome and time, because announcement fields were checked only against a global allowlist. R2-MEDIUM-2 re-raises
MEDIUM-2: a contradictory security table written without outer pipes, valid GitHub Flavored Markdown, evaded the
projection check. The builder reproduced both against the round-1 candidate before correcting them; MEDIUM-1, MEDIUM-2
and their round-2 re-raises are CORRECTED_PENDING_TARGETED_REREVIEW. No reviewer identity is recorded here.

**Round 3 — targeted independent re-review: REQUEST_CHANGES** (BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 0 / INFO 0). The
result was supplied to the builder by the programme. MEDIUM-1 and R2-MEDIUM-1 are closed. R3-MEDIUM-2 re-raises MEDIUM-2:
the projection check rejected a harmless explanatory table only because a cell named a role. The builder reproduced the
false rejection against the round-2 candidate and narrowed the check to recognize security-policy tables by structure
and assertions; MEDIUM-2, R2-MEDIUM-2 and R3-MEDIUM-2 are CORRECTED_PENDING_TARGETED_REREVIEW. No reviewer identity is
recorded here.

**Round 4 — targeted independent re-review: APPROVE** (BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 0 / INFO 0). The result was
supplied to the builder by the programme, after the builder bounded the security-table check so it also rejects explicit
administrator evidence-access claims in prose or tables. MEDIUM-2, R2-MEDIUM-2 and R3-MEDIUM-2 are closed; with HIGH-1 and
MEDIUM-3 (round 2) and MEDIUM-1 and R2-MEDIUM-1 (round 3), no finding remains open. No reviewer identity, external review
URL, signed artifact, commit, PR or CI run is recorded here because none was supplied. Lifecycle effect: CANDIDATE →
**APPROVED**; merge evidence is absent, so CLOSED remains unavailable (fails closed).

A review round, approval or merge evidence counts only when a governed bookkeeping step pins the exact record in
`validate_ux_review.py`; the tables below are its projections.

<!-- UXV:review_history:BEGIN -->
| Round | Kind | Decision | BLOCKER | HIGH | MEDIUM | LOW | INFO | Reviewer role | Evidence source | Record |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | INITIAL_INDEPENDENT_REVIEW | REQUEST_CHANGES | 0 | 1 | 3 | 0 | 0 | Independent reviewer | Independent review result supplied to the builder by the programme | GATE-029 §7 |
| 2 | TARGETED_INDEPENDENT_REREVIEW | REQUEST_CHANGES | 0 | 0 | 2 | 0 | 0 | Independent reviewer | Independent review result supplied to the builder by the programme | GATE-029 §7 |
| 3 | TARGETED_INDEPENDENT_REREVIEW | REQUEST_CHANGES | 0 | 0 | 1 | 0 | 0 | Independent reviewer | Independent review result supplied to the builder by the programme | GATE-029 §7 |
| 4 | TARGETED_INDEPENDENT_REREVIEW | APPROVE | 0 | 0 | 0 | 0 | 0 | Independent reviewer | Independent review result supplied to the builder by the programme | GATE-029 §7 |
<!-- UXV:review_history:END -->

<!-- UXV:findings:BEGIN -->
| Finding | Round | Severity | Summary | Disposition | Closed in round | Owner |
| --- | --- | --- | --- | --- | --- | --- |
| HIGH-1 | 1 | HIGH | Break-glass evidence access was not caller-bound: a different administrator inherited the grantee's authorization in the decision procedure | CLOSED_BY_REREVIEW | 2 | P7-WP4 builder |
| MEDIUM-1 | 1 | MEDIUM | Security-sensitive display copy was not bound to governed meaning: existence disclosure, leaked rationale detail and adjudication-replaces-result wording passed | CLOSED_BY_REREVIEW | 3 | P7-WP4 builder |
| MEDIUM-2 | 1 | MEDIUM | A contradictory second security matrix could coexist with the accepted projection in UX-004 | CLOSED_BY_REREVIEW | 4 | P7-WP4 builder |
| MEDIUM-3 | 1 | MEDIUM | APPROVED or CLOSED was accepted with claims.independently_reviewed = false | CLOSED_BY_REREVIEW | 2 | P7-WP4 builder |
| R2-MEDIUM-1 | 2 | MEDIUM | Re-raised MEDIUM-1: an accessible announcement for a masked (not found or not visible) resource could carry adjudication outcome and time; announcement fields were checked only against a global allowlist | CLOSED_BY_REREVIEW | 3 | P7-WP4 builder |
| R2-MEDIUM-2 | 2 | MEDIUM | Re-raised MEDIUM-2: a contradictory security table written without outer pipes (valid GFM) evaded the projection-integrity check | CLOSED_BY_REREVIEW | 4 | P7-WP4 builder |
| R3-MEDIUM-2 | 3 | MEDIUM | Re-raised MEDIUM-2: the projection-integrity check rejected harmless explanatory tables that merely mentioned a role name such as ADMINISTRATOR | CLOSED_BY_REREVIEW | 4 | P7-WP4 builder |
<!-- UXV:findings:END -->

## 8. Post-merge closure record

| Item | Value |
| --- | --- |
| Repository | `nishanth-cryptos/TrustLens` |
| PR | #39 — https://github.com/nishanth-cryptos/TrustLens/pull/39 — merged into `main` from `phase7-wp4-evidence-review` (2026-10-11) |
| Original baseline | `e58dac6bff63a8cb79512338919af6d15db958c1` (P7-WP3 closure merge, PR #38) |
| PR-head commit | `cf4ca8d37388f0f1a7e132a716e4cb776d0b38bc` |
| Merge commit | `5f8c373d63cbf0544ddccf414020659b9fd3330a` |
| Workflow | `knowledge-validation` (`.github/workflows/knowledge-validation.yml`) |
| PR-head run | 38139502369 (run number 76) — completed / success — https://github.com/nishanth-cryptos/TrustLens/actions/runs/38139502369 |
| Merge-commit run | 38142036162 (run number 77) — completed / success — https://github.com/nishanth-cryptos/TrustLens/actions/runs/38142036162 |
| Required jobs (both runs) | "Knowledge validation suite" — success; "Quality-gate self-test (gate must bite)" — success |
| Closure rests on | Independent approval round 4 (§7); no later approval round exists |
| Evidence source | Programme-supplied GitHub evidence, re-checked by the builder. Local git confirms `origin/main` equals merge commit `5f8c373…` ("Merge pull request #39") with parents `e58dac6…` and `cf4ca8d…`. GitHub API independently verified: PR #39 merged; PR-head run #76 (38139502369) SUCCESS, both jobs; post-merge run #77 (38142036162) SUCCESS, both jobs. Merge commit 5f8c373d63cbf0544ddccf414020659b9fd3330a. |
| Offline boundary | The validator pins this record (VERIFIED_MERGE_EVIDENCE) and requires the contract's merge evidence to match it exactly; it cannot authenticate GitHub and does not contact it |
| Lifecycle effect | APPROVED → **CLOSED** |
| Not implied | No production frontend, backend runtime or user-facing review or security experience exists; P7-WP5 not started |
