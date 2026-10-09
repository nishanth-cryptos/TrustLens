# GATE-027 — Phase-7 submission and evidence intake

| Field | Value |
| --- | --- |
| Document ID | GATE-027 |
| Version | 0.1 |
| Status | P7-WP2 SUBMISSION INTAKE APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING |
| Phase / work package | Phase 7 — UX, Evidence & Reporting Design / P7-WP2 |
| Owner role | Product / Intake UX |
| Branch | phase7-wp2-submission-intake |
| Baseline | d16ee7a8fd65a0428a0cde7cc1dceb7bd166d528 (P7-WP1 merge, PR #34) |
| Deliverable | [UX-002](../07-ux/UX-002-submission-evidence-intake.md); [`ux-intake-v1.json`](../../contracts/ux/ux-intake-v1.json); [`ux-intake-contract.schema.json`](../../contracts/ux/ux-intake-contract.schema.json); `contracts/ux/fixtures/intake-negative-mutations.json`; `knowledge/validation/validate_ux_intake.py` |
| Foundation | [UX-001](../07-ux/UX-001-experience-foundation-information-architecture.md) / GATE-026 (consumed, not modified) |
| Independent review | Round 1: REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 4 / LOW 2 / INFO 2); Round 2: REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 3 / LOW 2 / INFO 2); Round 3: REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 3 / LOW 2 / INFO 2); Round 4: REQUEST_CHANGES (BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 2 / INFO 2); Round 5: APPROVE (BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 2 / INFO 2) |
| Last updated | 2026-10-08 |

## 1. Gate reservation and boundary

The builder confirmed GATE-027 and UX-002 were unused at the baseline. Following four review/correction rounds, the final
independent review (§7) returned **APPROVE**; P7-WP2 is **APPROVED following independent review — remote CI + merge
pending**. It is not merged and not CLOSED: CLOSED requires the verified PR merge and remote-CI evidence pinned by the
governed post-merge step. P7-WP3 and later work packages are not started. This gate adds no API capability, persisted
concept, frontend or runtime.

## 2. Acceptance criteria

| # | Criterion | Evidence | State |
| --- | --- | --- | --- |
| 1 | Scope equals the UX-001 P7-WP2 handoff; differences from the request recorded | UX-002 §1; UXI-08, UXI-09 | MET (builder) |
| 2 | Submission, EvidenceItem, EvidenceDerivative, Evaluation and result kept separate | UX-002 §2; UXI-10, UXI-11, UXI-28 | MET (builder) |
| 3 | Accepted initiate → raw-byte PUT → finalize → evaluate sequence, in order | UX-002 §5; UXI-15…UXI-17, UXI-58 | MET (builder) |
| 4 | Every user action traces to an accepted operationId with exact API/OpenAPI parity | UXI-14…UXI-16, UXI-22 | MET (builder) |
| 5 | Every accepted error mapped to a UX-001 state with consistent recovery and key handling | UX-002 §7; UXI-18…UXI-21 | MET (builder) |
| 6 | Upload/submission/evaluation states never imply evaluated or safe; PROCESSING neutral; finalization only on observed PUT success; meanings bound to governed claims | UX-002 §6; UXI-23…UXI-26, UXI-64, UXI-71, UXI-72 | MET (builder) |
| 7 | Retries, duplicates, interruption and unknown outcomes use authoritative state; finite window; API-derived reconciliation bindings | UXI-30…UXI-32, UXI-61…UXI-63, UXI-65, UXI-66, UXI-70 | MET (builder) |
| 8 | Returned authoritative state takes precedence; complete lifecycle components; freshness and conflict rules | UX-002 §5; UXI-67…UXI-69, UXI-73, UXI-74 | MET (builder) |
| 9 | Metadata versus content separated; content only via the permissioned operation (P7-WP4) | UX-002 §8; UXI-33, UXI-34 | MET (builder) |
| 10 | Server-authoritative identity, resource authorization and safe errors | UXI-35, UXI-36 | MET (builder) |
| 11 | No invented limits, numbers, consent capture, score, probability or verdict | UXI-37, UXI-40, UXI-43 | MET (builder) |
| 12 | Accessible capture and mobile requirements without a conformance claim | UX-002 §10; UXI-44, UXI-45 | MET (builder) |
| 13 | Open items carried; unresolved decisions owned | UX-002 §11; UXI-47…UXI-51 | MET (builder) |
| 14 | Phase-6 API surface consumed exactly; DetectionResult untouched | UXI-07, UXI-57 | MET (builder) |
| 15 | Lifecycle evidence exact and consistent; no premature approval or closure | UXI-06, UXI-59, UXI-60 | MET (builder) |
| 16 | Validator, negative mutations and CI self-test defect bite | `validate_ux_intake.py`; fixtures; `ci_selftest.py` | MET (builder) |
| 17 | Independent review | §6 rounds 1–4 REQUEST_CHANGES; §7 round 5 final review APPROVE (0/0/0/2/2) | **MET** |
| 18 | Remote CI + merge | — | **PENDING** |

## 3. Validation evidence (local builder)

Recorded in the P7-WP2 acceptance-bookkeeping STOP REPORT and reproduced by the final independent review (§7): `run_all` 31/31; `run_all --json` gate=PASS, validators_run=31,
validators_failed=0; `ci_selftest` 16/16 (defect 16 makes FINALIZED evidence imply a completed evaluation and is caught
by `validate_ux_intake.py` only); `validate_ux_intake.py` 77/77 checks with every negative mutation rejected by its named
check; `ENGINE_VERSION = 1.0.0`. This is builder evidence, not independent review or remote CI.

## 4. Preserved items

G-09 OPEN; OI-05 OPEN; ASM-002 UNCONFIRMED / PROVISIONAL; P6-WP7-LOW-1 OPEN / NON-BLOCKING; Phase 6 CLOSED and frozen;
P7-WP1 artifacts unmodified. No tenant field, retention period, frontend, production-readiness, usability-testing,
accessibility-conformance or detection-effectiveness claim.

## 5. Decision

**P7-WP2 SUBMISSION INTAKE APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING.** Recommendation: proceed to the P7-WP2 commit and PR. After the PR merges with successful remote CI, the governed
post-merge step may pin the verified merge evidence and record P7-WP2 as CLOSED. Not merged, not closed; P7-WP3 not
started.

## 6. Independent review record

<!-- UXI:review_history:BEGIN -->
| Round | Kind | Decision | BLOCKER | HIGH | MEDIUM | LOW | INFO | Record |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | INITIAL_INDEPENDENT_REVIEW | REQUEST_CHANGES | 0 | 0 | 4 | 2 | 2 | GATE-027 §6 |
| 2 | TARGETED_INDEPENDENT_REREVIEW | REQUEST_CHANGES | 0 | 0 | 3 | 2 | 2 | GATE-027 §6 |
| 3 | TARGETED_INDEPENDENT_REREVIEW | REQUEST_CHANGES | 0 | 0 | 3 | 2 | 2 | GATE-027 §6 |
| 4 | TARGETED_INDEPENDENT_REREVIEW | REQUEST_CHANGES | 0 | 0 | 1 | 2 | 2 | GATE-027 §6 |
| 5 | FINAL_INDEPENDENT_REVIEW | APPROVE | 0 | 0 | 0 | 2 | 2 | GATE-027 §7 |
<!-- UXI:review_history:END -->

Rounds 1–4 were supplied to the builder by the programme. Round 2 closed MEDIUM-1 and round 4 closed MEDIUM-2 and
MEDIUM-3 (including their R2/R3 entries). The remaining MEDIUM-4 findings (MEDIUM-4, R2-MEDIUM-4, R3-MEDIUM-4,
R4-MEDIUM-4) are corrected and await the next targeted re-review — they are not closed.
LOW and INFO findings are carried with owners and are not claimed closed.

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

MEDIUM correction summary: MEDIUM-1 — exact structured decision vocabulary, resolvable GATE-027 record, structured merge
evidence with static plausibility checks and an explicit limit on what offline validation can prove (UXI-06, UXI-59,
UXI-60); MEDIUM-2 — request identity separate from authorization, same-principal reauthentication keeps the key, finite
OPS-001 window, explicit unknown-outcome reconciliation and stop (UXI-21, UXI-61…UXI-63); MEDIUM-3 — PROCESSING facts
derived from the API internal-state mapping, local transfer separate from server state, per-state recovery (UXI-64…UXI-66);
MEDIUM-4 — every step renders the returned authoritative state with precedence rules evaluated over fifteen scenarios
(UXI-67…UXI-69).

Second-correction summary (round 2): R2-MEDIUM-2 — every reconciliation binding is derived from the API catalog and
must read metadata of the same resource type the command affects, be available to every command role, be case-access
authorized without a content gate, and take identifiers only from the command path or an earlier authoritative
response; otherwise recovery stops in OUTCOME_UNKNOWN (UXI-63, UXI-70). R2-MEDIUM-3 — finalization only with an observed
successful PUT, governed recovery-action semantics, a bounded re-PUT claim, display meanings built only from governed
claim texts and an unsafe-claim scan; API-owner dependency recorded for PROCESSING sub-states (UXI-66, UXI-71, UXI-72).
R2-MEDIUM-4 — required lifecycle components never defaulted, fresh/known-stale/unordered handling with an explicit
conflict state, lifecycle transitions and 28 scenario outcomes pinned to independent oracles (UXI-69, UXI-73, UXI-74).

Third-correction summary (round 3): R3-MEDIUM-2 — identifier meaning derived from the API resource catalog (canonical
identifier parameters and representation schemas); parent identifiers only scope collections; creation commands never
claim exact identity; command-scope filters mandatory; zero/one/many candidates all stop in OUTCOME_UNKNOWN without
automatic binding (UXI-70). R3-MEDIUM-3 — the PUT-success witness is bound to the evidence item and the exact upload
attempt (evidence_id + content_sha256) and is never reused; recovery reasons governed; every contract prose string scanned
(UXI-71, UXI-72, UXI-75). R3-MEDIUM-4 — public upload reachability parsed from the DATA-001-WP2 §11 internal machine
(ORPHAN_DETECTED → FINALIZED, FINALIZED → INTEGRITY_FAILED), overlapping exchanges unordered, both-direction pairs are
conflicts (UXI-69, UXI-76).

Fourth-correction summary (round 4, MEDIUM-4 only): one central freshness normalizer treats every overlapping exchange as
UNORDERED whatever its client label (FRESH or KNOWN_STALE); client labels are never authoritative server ordering and
the accepted API provides none; possible transitions are not proof of occurrence. Pinned regressions SC-33 (overlapping
FRESH REJECTED → FINALIZED) and SC-34 (overlapping FRESH FINALIZED → REJECTED) both give STATE_CONFLICT_RECONCILE, with
controls SC-35…SC-37; a metamorphic check requires every overlapping scenario to evaluate exactly as UNORDERED (UXI-68,
UXI-69, UXI-74, UXI-77).

## 7. Final independent review — APPROVE

| Item | Result |
| --- | --- |
| Round | 5 — final independent review (after targeted corrections for rounds 1–4) |
| Decision | **APPROVE** — READY_FOR_P7_WP2_ACCEPTANCE_BOOKKEEPING |
| Counts | BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 2 / INFO 2 |
| MEDIUM findings | MEDIUM-1 CLOSED (round 2); MEDIUM-2 and MEDIUM-3 CLOSED (round 4); MEDIUM-4 CLOSED (round 5) |
| Reviewer verification | Both overlapping REJECTED/FINALIZED counterexamples reconcile to STATE_CONFLICT_RECONCILE; all 37 lifecycle scenarios; all 5 upload-witness scenarios; all 108 overlapping upload-state combinations against an independently derived oracle with zero mismatches; 77/77 intake checks; 231/231 negative mutations; 31/31 canonical validators; 16/16 CI self-test defects; 10 accepted API operations and 89 operation/error mappings; all 19 Phase-6 snapshot hashes |
| Carried (OPEN, non-blocking) | LOW-1 (P7-WP2 builder); LOW-2 (programme governance); INFO-1 (roadmap owner); INFO-2 (programme governance) |
| Provenance | Independent review result supplied to the builder by the programme. No reviewer identity, external review URL, signed artifact, commit, PR or CI run is recorded here because none was supplied. |
| Lifecycle effect | CANDIDATE → **APPROVED**; merge evidence absent, so CLOSED remains unavailable (fails closed) |
