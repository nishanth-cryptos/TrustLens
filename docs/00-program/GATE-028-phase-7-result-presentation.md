# GATE-028 — Phase-7 result presentation

| Field | Value |
| --- | --- |
| Document ID | GATE-028 |
| Version | 0.1 |
| Status | P7-WP3 RESULT PRESENTATION APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING |
| Phase / work package | Phase 7 — UX, Evidence & Reporting Design / P7-WP3 |
| Owner role | Product / Result UX |
| Branch | phase7-wp3-result-presentation |
| Baseline | 47f57d1d8f2b9f2ddedb2b438bc40ac3f32e4a70 (P7-WP2 closure merge, PR #36) |
| Deliverable | [UX-003](../07-ux/UX-003-result-presentation.md); [`ux-result-v1.json`](../../contracts/ux/ux-result-v1.json); [`ux-result-contract.schema.json`](../../contracts/ux/ux-result-contract.schema.json); `contracts/ux/fixtures/result-negative-mutations.json`; `knowledge/validation/validate_ux_result.py` |
| Foundation | [UX-001](../07-ux/UX-001-experience-foundation-information-architecture.md) / GATE-026 and [UX-002](../07-ux/UX-002-submission-evidence-intake.md) / GATE-027 (consumed, not modified) |
| Independent review | Round 1: REQUEST_CHANGES (BLOCKER 0 / HIGH 1 / MEDIUM 5 / LOW 0 / INFO 0); Round 2: REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 3 / LOW 1 / INFO 1); Round 3: REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 1 / INFO 1); Round 4: REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 1 / INFO 1); Round 5: REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 1 / INFO 1); Round 6: REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 2 / LOW 1 / INFO 1); Round 7: REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 2 / LOW 2 / INFO 1); Round 8: APPROVE (BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 1 / INFO 1) |
| Last updated | 2026-10-11 |

## 1. Gate reservation and boundary

The builder confirmed that GATE-028 and UX-003 were unused at the baseline. It also confirmed that the P7-WP2 closure
merge (`47f57d1…`) had successful post-merge CI on both required jobs before starting.

The first independent review and six targeted re-reviews returned REQUEST_CHANGES (§6). After the builder's targeted
corrections, the final independent review (round 8, §6) returned **APPROVE**. P7-WP3 is **APPROVED following independent
review — remote CI + merge pending**. It is not merged and not CLOSED: CLOSED requires the PR merge and remote-CI
evidence pinned by the governed post-merge step. P7-WP4 and later work packages are not started. The gate adds
no API capability, persisted concept, frontend or runtime.

## 2. Acceptance criteria

| # | Criterion | Evidence | State |
| --- | --- | --- | --- |
| 1 | Scope equals the UX-001 P7-WP3 handoff; deferred items owned; request differences recorded | UX-003 §1; UXR-08, UXR-09 | MET (builder) |
| 2 | Exact `getDetectionResult` binding with API/OpenAPI parity; GET only | UX-003 §2; UXR-10, UXR-11 | MET (builder) |
| 3 | Lifecycle gating: no result before COMPLETED + AVAILABLE; FAILED is not a classification; 410 is governed unavailability; conditional EVALUATION_NOT_COMPLETED | UX-003 §3; UXR-15…UXR-17, UXR-66 | MET (builder) |
| 4 | Every accepted error mapped to a UX-001 state with retryability-consistent recovery | UX-003 §4; UXR-12…UXR-14 | MET (builder) |
| 5 | Missing or inconsistent metadata yields no invented result | UX-003 §5; UXR-18, UXR-19 | MET (builder) |
| 6 | Six decision axes separate and categorical; no probability, percentage, score, gauge or ranking | UX-003 §6; UXR-20…UXR-22 | MET (builder) |
| 7 | Classification and support labels never safe, benign or legal guilt | UX-003 §7; UXR-23…UXR-25 | MET (builder) |
| 8 | Explanation hierarchy A–K; every field traced; nothing dropped; no aggregate | UX-003 §8; UXR-26…UXR-30, UXR-45 | MET (builder) |
| 9 | Rule outcomes distinct; suppressed is not a finding; no false corroboration; negative indicators not safety | UX-003 §9; UXR-31…UXR-35 | MET (builder) |
| 10 | Provenance types distinct; no manufactured quote; AI and enrichment boundaries | UX-003 §10; UXR-36…UXR-39 | MET (builder) |
| 11 | Governed actions only; no invented priority, URL or phone number | UX-003 §11; UXR-40, UXR-41 | MET (builder) |
| 12 | STANDARD vs DETAILED access derived from the accepted API; no administrator access by role | UX-003 §12; UXR-42, UXR-43 | MET (builder) |
| 13 | Result immutable; adjudication separate | UX-003 §13; UXR-44 | MET (builder) |
| 14 | Scenario outcomes pinned and reproduced by a reference model and an independent decision procedure | UX-003 §14; UXR-62…UXR-64 | MET (builder) |
| 15 | Carried items unchanged; open decisions owned; no unsupported claims | UX-003 §15–§16; UXR-49…UXR-58 | MET (builder) |
| 16 | Validator, negative mutations and CI self-test defect bite | `validate_ux_result.py`; fixtures; `ci_selftest.py` | MET (builder) |
| 17 | Independent review | §6 round 1 REQUEST_CHANGES (0/1/5/0/0); round 2 REQUEST_CHANGES (0/0/3/1/1); round 3 REQUEST_CHANGES (0/0/1/1/1); round 4 REQUEST_CHANGES (0/0/1/1/1); round 5 REQUEST_CHANGES (0/0/1/1/1); round 6 REQUEST_CHANGES (0/0/2/1/1); round 7 REQUEST_CHANGES (0/0/2/2/1); round 8 final review APPROVE (0/0/0/1/1) | **MET** |
| 18 | Remote CI + merge | Not yet performed | **PENDING** |
| 19 | Rendering bound to the actual caller; unauthorized or mismatched payloads withheld; announcements leak nothing (HIGH-1) | UX-003 §12, §15; UXR-69, UXR-70, UXR-75 | CLOSED (round 2) |
| 20 | Builder self-review and false provenance never approve; review references resolve to the Markdown-bounded section holding the record, excluding fenced and commented content (MEDIUM-1, MEDIUM-1-R2, R3-MEDIUM-1, R4-MEDIUM-1, R5-MEDIUM-1, R6-MEDIUM-1, R6-MEDIUM-2, R7-MEDIUM-1, R7-MEDIUM-2) | UX-003 §1; UXR-06, UXR-67, UXR-76 | CLOSED (round 8) |
| 21 | Only an observed SUCCESS response renders (MEDIUM-2) | UX-003 §3; UXR-68, UXR-75 | CLOSED (round 2) |
| 22 | Finding eligibility is COMPOSITE + MATCHED; rule references agree by identity and version (MEDIUM-3, MEDIUM-3-R2) | UX-003 §5, §9; UXR-71, UXR-77, UXR-75 | CLOSED (round 3) |
| 23 | Six returned axes carried and cross-checked against Phase-3 authority (MEDIUM-4) | UX-003 §5; UXR-19, UXR-72, UXR-75 | CLOSED (round 2) |
| 24 | Every displayable string bound to governed text; scoped-negation wording classifier (MEDIUM-5) | UX-003 §7; UXR-25, UXR-73, UXR-74 | CLOSED (round 2) |
| 25 | Field presence read from the payload; DETAILED-only data in STANDARD never renders (R2-MEDIUM-1) | UX-003 §12; UXR-78, UXR-75 | CLOSED (round 3) |
| 26 | Clause-starting conjunction ends a negation's scope; residual clause-detection heuristic documented (R2-LOW-1, R3-LOW-1, R4-LOW-1, R5-LOW-1, R6-LOW-1, R7-LOW-1, R8-LOW-1) | UX-003 §7; UXR-74 | OPEN / NON-BLOCKING |
| 27 | Phase-3 matched-rule counting discrepancy kept with its owner (R2-INFO-1, R3-INFO-1, R4-INFO-1, R5-INFO-1, R6-INFO-1, R7-INFO-1, R8-INFO-1) | UX-003 §16 | OPEN (Detection owner) |

## 3. Validation evidence (local builder)

The authoritative figures are those recorded in the P7-WP3 builder STOP REPORT:

- `run_all` covers 32 validators, including `validate_ux_result.py`.
- `ci_selftest` carries 17 defects. Defect 17 inverts the NO_SCAM_PATTERN not-safe flag and is caught by
  `validate_ux_result.py` only.
- `validate_ux_result.py` passes 78/78 checks, every negative mutation is rejected by its named check, and every positive
  control is accepted.
- `ENGINE_VERSION = 1.0.0`.

This is builder evidence, not independent review or remote CI.

## 4. Preserved items

The following items are preserved:

- G-09 OPEN;
- OI-05 OPEN;
- ASM-002 UNCONFIRMED / PROVISIONAL;
- P6-WP7-LOW-1 OPEN / NON-BLOCKING;
- Phase 6 CLOSED and frozen;
- P7-WP1 and P7-WP2 artifacts unmodified.

There is no tenant field, retention period or frontend, and no production-readiness, usability-testing,
accessibility-conformance or detection-effectiveness claim.

## 5. Decision

**P7-WP3 RESULT PRESENTATION APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING.** Recommendation:
proceed to the authorized P7-WP3 commit and PR. After the PR merges with successful remote CI, the governed post-merge
step may pin the merge evidence and record P7-WP3 as CLOSED. Not merged, not closed and not an implemented result
experience; P7-WP4 is not started.

## 6. Independent review record

**Round 1 — initial independent review: REQUEST_CHANGES** (BLOCKER 0 / HIGH 1 / MEDIUM 5 / LOW 0 / INFO 0). The
result was supplied to the builder by the programme. The reviewer reproduced six defects with adversarial tests while
the existing suite passed. The builder reproduced all six against the pre-correction candidate before correcting them.
No reviewer identity is recorded here, and offline validation cannot authenticate one. The structured history below is
authoritative in the machine contract. Every finding is CORRECTED_PENDING_TARGETED_REREVIEW; none is closed until an
independent re-review closes it.

**Round 2 — targeted independent re-review: REQUEST_CHANGES** (BLOCKER 0 / HIGH 0 / MEDIUM 3 / LOW 1 / INFO 1). The
result was supplied to the builder by the programme. HIGH-1, MEDIUM-2, MEDIUM-4 and MEDIUM-5 are closed. MEDIUM-1 and
MEDIUM-3 are re-raised as MEDIUM-1-R2 (review-section reference integrity) and MEDIUM-3-R2 (rule identity and version
integrity). A new finding, R2-MEDIUM-1, covers payload presence contradicting a flag; R2-LOW-1 covers conjunction scope
in the supplemental wording classifier. R2-INFO-1 is the Phase-3 matched-rule counting discrepancy, which stays with
the Detection owner. The builder reproduced the three MEDIUM counterexamples against the round-1 candidate before
correcting them. No reviewer identity is recorded here.

**Round 3 — targeted independent re-review: REQUEST_CHANGES** (BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 1 / INFO 1). The
result was supplied to the builder by the programme. MEDIUM-3, MEDIUM-3-R2 and R2-MEDIUM-1 are closed. R3-MEDIUM-1
re-raises the review-section reference finding: the parser stopped only at the next numbered heading, so a matching
record under an unnumbered heading, inside a fenced code block or inside an HTML comment satisfied a reference. The
builder reproduced all three against the round-2 candidate before correcting the parser. R3-LOW-1 re-confirms the
non-blocking clause-detection limitation, and R3-INFO-1 re-confirms the Phase-3 discrepancy owned by Detection. No
reviewer identity is recorded here, and offline validation cannot authenticate one.

**Round 4 — targeted independent re-review: REQUEST_CHANGES** (BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 1 / INFO 1). The
result was supplied to the builder by the programme. R4-MEDIUM-1 re-raises R3-MEDIUM-1: deleting fenced or commented
lines made separated blocks adjacent, so a review header and delimiter followed by a fence or comment and then an
approval row read as one table, and a backtick opener with a backtick in its info string hid a real `## Appendix`
heading. The builder reproduced all three against the round-3 candidate before correcting the parser. R4-LOW-1 and
R4-INFO-1 re-confirm the carried LOW and INFO. No reviewer identity is recorded here.

**Round 5 — targeted independent re-review: REQUEST_CHANGES** (BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 1 / INFO 1). The
result was supplied to the builder by the programme. The round-4 splicing and fence exploits are closed. R5-MEDIUM-1
re-raises the review-section finding for heading grammar. An ordered-list line `7. …`, or a lazy paragraph line,
followed by `---` was taken as a numbered setext heading and could satisfy a §7 reference. A list note directly
before a horizontal rule was taken as a heading that ended a real `## 7.` section. The builder reproduced both false
approvals and both false rejections against the round-4 candidate before correcting the grammar, and checked the
heading structure against an independent CommonMark-with-tables parser during development. R5-LOW-1 and R5-INFO-1
re-confirm the carried LOW and INFO. No reviewer identity is recorded here.

**Round 6 — targeted independent re-review: REQUEST_CHANGES** (BLOCKER 0 / HIGH 0 / MEDIUM 2 / LOW 1 / INFO 1). The
result was supplied to the builder by the programme. The round-5 setext and list cases are closed. R6-MEDIUM-1: a
pipe-leading paragraph (`| Appendix | Notes |`) followed by `---` or `===` was taken as a table, so the real setext
heading that ends §7 was missed. R6-MEDIUM-2: table lines lazily continuing a blockquote or list item were taken as a
top-level review table. The builder reproduced all four false approvals against the round-5 candidate before replacing
the heading-only model with a bounded block parser for headings and top-level tables, checked against an independent
CommonMark-with-tables parser. R6-LOW-1 and R6-INFO-1 re-confirm the carried LOW and INFO. No reviewer identity is
recorded here.

**Round 7 — targeted independent re-review: REQUEST_CHANGES** (BLOCKER 0 / HIGH 0 / MEDIUM 2 / LOW 2 / INFO 1). The
result was supplied to the builder by the programme. Against native GitHub Flavored Markdown, R7-MEDIUM-1 re-raises
table precedence: a one-column `| Appendix |` + `---` is a setext heading, not a table, and indented code could supply a
review-table header or delimiter. R7-MEDIUM-2 re-raises container integrity: an indented thematic break inside a list
item reset the list, promoting the item's nested table to top-level evidence. R7-LOW-2 records that this record held a
duplicated Round 6 summary (one copy before Round 5); the duplicate is removed and the order restored. The builder
reproduced the false approvals against the round-6 candidate and compared the corrected parser with native cmark-gfm
across a systematic matrix. R7-LOW-1 and R7-INFO-1 re-confirm the carried LOW and INFO. No reviewer identity is
recorded here.

**Round 8 — final independent review: APPROVE** (BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 1 / INFO 1). The result was
supplied to the builder by the programme, with the final recommendation READY_FOR_P7_WP3_ACCEPTANCE_BOOKKEEPING. The two
last remaining MEDIUM findings, R7-MEDIUM-1 and R7-MEDIUM-2, are independently closed, and with them the review-governance
findings they re-raised (MEDIUM-1, MEDIUM-1-R2, R3-MEDIUM-1, R4-MEDIUM-1, R5-MEDIUM-1, R6-MEDIUM-1 and R6-MEDIUM-2). The
reviewer reported 42/42 native GFM adversarial probes in agreement, 28/28 positive controls accepted, 503/503 negative
mutations rejected, 78/78 UX checks, 32/32 canonical validators, 17/17 CI self-test defects, 77/77 intake checks with
247/247 intake negative mutations, 274 protected tracked artifacts unchanged, all 19 Phase-6 snapshot hashes, and no
unauthorized integration or runtime modification. R8-LOW-1 (heuristic clause detection in the supplemental wording
classifier; exact governed-text binding remains primary; owner P7-WP3) and R8-INFO-1 (Phase-3 `result.py`
`matched_rule_ids()` and aggregation treat SUPPRESSION/MATCHED entries differently; owner Detection / Phase-3 governance)
stay open and non-blocking. R7-LOW-2 keeps its corrected disposition. No reviewer identity, external review URL, signed
artifact, commit, PR or CI run is recorded here because none was supplied. Lifecycle effect: CANDIDATE → **APPROVED**;
merge evidence is absent, so CLOSED remains unavailable (fails closed).

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

<!-- UXR:findings:BEGIN -->
| Finding | Round | Severity | Summary | Disposition | Closed in round | Owner |
| --- | --- | --- | --- | --- | --- | --- |
| HIGH-1 | 1 | HIGH | Rendering not bound to the actual caller: a USER requesting STANDARD could be shown a DETAILED payload (section G) | CLOSED_BY_REREVIEW | 2 | P7-WP3 builder |
| MEDIUM-1 | 1 | MEDIUM | Lifecycle accepted a builder self-review as independent approval | CLOSED_BY_REREVIEW | 8 | P7-WP3 builder |
| MEDIUM-2 | 1 | MEDIUM | Non-success response kinds (NONE, TIMEOUT, unknown) could render cached result fields as READY | CLOSED_BY_REREVIEW | 2 | P7-WP3 builder |
| MEDIUM-3 | 1 | MEDIUM | Finding eligibility ignored rule kind: a SUPPRESSION-kind MATCHED rule was shown as an active scam finding | CLOSED_BY_REREVIEW | 3 | P7-WP3 builder |
| MEDIUM-4 | 1 | MEDIUM | Scenarios could not carry the six result axes, so contradictory envelopes (e.g. DETECTED with LOW confidence) rendered | CLOSED_BY_REREVIEW | 2 | P7-WP3 builder |
| MEDIUM-5 | 1 | MEDIUM | Wording scan stripped uppercase tokens and accepted unrelated negation, letting unsupported display titles pass | CLOSED_BY_REREVIEW | 2 | P7-WP3 builder |
| MEDIUM-1-R2 | 2 | MEDIUM | Re-raised MEDIUM-1: an approval reference was accepted on the section title alone; the referenced GATE-028 section need not contain the review record | CLOSED_BY_REREVIEW | 8 | P7-WP3 builder |
| MEDIUM-3-R2 | 2 | MEDIUM | Re-raised MEDIUM-3: matched, governing and per-rule references were compared by count only, so mismatched rule identities rendered READY | CLOSED_BY_REREVIEW | 3 | P7-WP3 builder |
| R2-MEDIUM-1 | 2 | MEDIUM | A presence flag was relied on instead of the payload: non-empty DETAILED-only rule_results with presence=false rendered a STANDARD result | CLOSED_BY_REREVIEW | 3 | P7-WP3 builder |
| R2-LOW-1 | 2 | LOW | Supplemental wording classifier let an unrelated leading negation excuse a later unsupported claim joined by 'and' | OPEN_CARRIED | — | P7-WP3 builder |
| R2-INFO-1 | 2 | INFO | Phase-3 discrepancy: aggregation excludes SUPPRESSION rules from eligible findings while result.py matched_rule_ids counts any MATCHED entry | OPEN_INFORMATIONAL | — | Detection owner (Phase-3 governance) |
| R3-MEDIUM-1 | 3 | MEDIUM | Re-raised MEDIUM-1: the GATE-028 section parser stopped only at the next numbered heading and read fenced or commented rows, so a record under an unnumbered heading, in a code fence or in an HTML comment satisfied a reference | CLOSED_BY_REREVIEW | 8 | P7-WP3 builder |
| R3-LOW-1 | 3 | LOW | Round 3 re-confirms R2-LOW-1: clause detection in the supplemental wording classifier is heuristic (non-blocking; exact governed-text binding remains primary) | OPEN_CARRIED | — | P7-WP3 builder |
| R3-INFO-1 | 3 | INFO | Round 3 re-confirms R2-INFO-1: Phase-3 result.py matched_rule_ids counts any MATCHED entry while aggregation excludes SUPPRESSION rules | OPEN_INFORMATIONAL | — | Detection owner (Phase-3 governance) |
| R4-MEDIUM-1 | 4 | MEDIUM | Re-raised R3-MEDIUM-1: removing fenced or commented lines joined separated Markdown blocks into a valid-looking review table, and a backtick opener with a backtick in its info string was treated as a fence that hid a real heading | CLOSED_BY_REREVIEW | 8 | P7-WP3 builder |
| R4-LOW-1 | 4 | LOW | Round 4 re-confirms R2-LOW-1: clause detection in the supplemental wording classifier is heuristic (non-blocking; exact governed-text binding remains primary) | OPEN_CARRIED | — | P7-WP3 builder |
| R4-INFO-1 | 4 | INFO | Round 4 re-confirms R2-INFO-1: Phase-3 result.py matched_rule_ids counts any MATCHED entry while aggregation excludes SUPPRESSION rules | OPEN_INFORMATIONAL | — | Detection owner (Phase-3 governance) |
| R5-MEDIUM-1 | 5 | MEDIUM | Re-raised MEDIUM-1: a list item or lazy paragraph line followed by '---' was taken as a setext heading, so a non-heading could satisfy a numbered section reference and a list note before a horizontal rule ended a real section | CLOSED_BY_REREVIEW | 8 | P7-WP3 builder |
| R5-LOW-1 | 5 | LOW | Round 5 re-confirms R2-LOW-1: clause detection in the supplemental wording classifier is heuristic (non-blocking; exact governed-text binding remains primary) | OPEN_CARRIED | — | P7-WP3 builder |
| R5-INFO-1 | 5 | INFO | Round 5 re-confirms R2-INFO-1: Phase-3 result.py matched_rule_ids counts any MATCHED entry while aggregation excludes SUPPRESSION rules | OPEN_INFORMATIONAL | — | Detection owner (Phase-3 governance) |
| R6-MEDIUM-1 | 6 | MEDIUM | A pipe-leading paragraph followed by a setext underline was taken as a table, so a real level-1/2 setext heading that ends the referenced section was missed | CLOSED_BY_REREVIEW | 8 | P7-WP3 builder |
| R6-MEDIUM-2 | 6 | MEDIUM | Lazy blockquote or list continuation lines were taken as a top-level review table, so nonexistent approval evidence was accepted | CLOSED_BY_REREVIEW | 8 | P7-WP3 builder |
| R6-LOW-1 | 6 | LOW | Round 6 re-confirms R2-LOW-1: clause detection in the supplemental wording classifier is heuristic (non-blocking; exact governed-text binding remains primary) | OPEN_CARRIED | — | P7-WP3 builder |
| R6-INFO-1 | 6 | INFO | Round 6 re-confirms R2-INFO-1: Phase-3 result.py matched_rule_ids counts any MATCHED entry while aggregation excludes SUPPRESSION rules | OPEN_INFORMATIONAL | — | Detection owner (Phase-3 governance) |
| R7-MEDIUM-1 | 7 | MEDIUM | Re-raised R6-MEDIUM-1 under native GFM: a one-column '\| Appendix \|' + '---' was taken as a table instead of a setext heading, and indented code supplied a review-table header or delimiter | CLOSED_BY_REREVIEW | 8 | P7-WP3 builder |
| R7-MEDIUM-2 | 7 | MEDIUM | Re-raised R6-MEDIUM-2 under native GFM: an indented thematic break inside a list item reset the list context, promoting the item's nested table to top-level review evidence | CLOSED_BY_REREVIEW | 8 | P7-WP3 builder |
| R7-LOW-1 | 7 | LOW | Round 7 re-confirms R2-LOW-1: clause detection in the supplemental wording classifier is heuristic (non-blocking; exact governed-text binding remains primary) | OPEN_CARRIED | — | P7-WP3 builder |
| R7-LOW-2 | 7 | LOW | GATE-028 carried a duplicated Round 6 summary, one copy placed before the Round 5 summary | CORRECTED_PENDING_TARGETED_REREVIEW | — | P7-WP3 builder |
| R7-INFO-1 | 7 | INFO | Round 7 re-confirms R2-INFO-1: Phase-3 result.py matched_rule_ids counts any MATCHED entry while aggregation excludes SUPPRESSION rules | OPEN_INFORMATIONAL | — | Detection owner (Phase-3 governance) |
| R8-LOW-1 | 8 | LOW | Round 8 re-confirms R2-LOW-1: clause detection in the supplemental wording classifier is heuristic (non-blocking; exact governed-text binding remains primary) | OPEN_CARRIED | — | P7-WP3 builder |
| R8-INFO-1 | 8 | INFO | Round 8 re-confirms R2-INFO-1: Phase-3 result.py matched_rule_ids counts any MATCHED entry while aggregation excludes SUPPRESSION rules | OPEN_INFORMATIONAL | — | Detection owner (Phase-3 governance) |
<!-- UXR:findings:END -->
