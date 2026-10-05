# GATE-026 — Phase-7 UX foundation

| Field | Value |
| --- | --- |
| Document ID | GATE-026 |
| Version | 0.1 |
| Status | P7-WP1 UX FOUNDATION APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING |
| Phase / work package | Phase 7 — UX, Evidence & Reporting Design / P7-WP1 |
| Owner role | Product / UX Architecture |
| Branch | phase7-wp1-ux-foundation |
| Baseline | bbe741b8ebfb7adbc399c1231b74f67f73ba2cfc |
| Foundation | [UX-001](../07-ux/UX-001-experience-foundation-information-architecture.md) |
| Phase-6 prerequisite | [PHASE-6-CLOSURE](PHASE-6-CLOSURE.md): PHASE 6 CLOSED with recorded review, merge and CI evidence |
| Last updated | 2026-10-05 |

## 1. Gate reservation and acceptance boundary

Builder confirmed GATE-026 was unused at the exact baseline before creating this file. This is the first Phase-7
work package. P7-WP1 is approved following independent review and targeted re-review; MEDIUM-1 is CLOSED.
Remote CI and merge remain pending. P7-WP1 is NOT CLOSED and GATE-026 is not finally closed or merged.
The builder stops without commit/push; P7-WP2 and later packages remain NOT STARTED.

## 2. Required acceptance evidence

| Area | Acceptance requirement |
| --- | --- |
| Foundation | UX-001, machine contract and closed offline schema exist; mental model and IA are explicit. |
| API traceability | Every data-bearing surface maps to accepted operationIds; no persisted UX-only object or direct DB dependency. |
| Authorization | Exact role/persona distinction, resource authorization and separate content permission; backend remains authoritative. |
| Privileges | No administrator evidence access by role, no analyst break-glass, no forbidden self-assignment, C4 permission preserved. |
| History | Immutable DetectionResult, separate Adjudication, exact replay and new-Evaluation re-analysis. |
| Semantic safety | Advisory enrichment, provider CLEAN not safety, unsupported/empty/pending/error not safety; no arbitrary score/probability. |
| States and accessibility | Distinct governed-removal/unavailable/stale states, keyboard/focus/text/colour foundations; no conformance claim. |
| Evaluation completion error | EVALUATION_NOT_COMPLETED requires authoritative Evaluation state: QUEUED/RUNNING may present ACTION_PENDING; terminal FAILED / NOT_PRODUCED must present ACTION_FAILED, never pending. |
| Carryovers | No tenancy; G-09/OI-05 OPEN; ASM-002 provisional; Phase-6 snapshot LOW OPEN / NON-BLOCKING. |
| Freeze | Phase-6 accepted artifacts, ADRs, Phase-3/4 and runtime/publish/rules/taxonomies unchanged. |
| Validation | UXF validator, named negative mutations, canonical runner, content-permission self-test; Phase-6 closure green. |
| CI | Only docs/07-ux/** added to the shared path filter; job logic, versions, dependencies and other triggers unchanged. |
| Review and scope | Independent review and targeted re-review completed with APPROVE; remote CI and merge pending; no implementation/production claim; no P7-WP2+ work started. |

## 3. Approved artifacts and authorized change surface

| Kind | Path |
| --- | --- |
| New | docs/07-ux/UX-001-experience-foundation-information-architecture.md |
| New | docs/00-program/GATE-026-phase-7-ux-foundation.md |
| New | contracts/ux/ux-foundation-v1.json |
| New | contracts/ux/ux-foundation-contract.schema.json |
| New | contracts/ux/fixtures/negative-mutations.json |
| New | knowledge/validation/validate_ux_foundation.py |
| Modified | knowledge/validation/run_all.py |
| Modified | knowledge/validation/ci_selftest.py |
| Modified | .github/workflows/knowledge-validation.yml |

Expected and permitted total: **9 files**. Accepted Phase-6 substantive artifacts and closure validator are frozen.
Machine status: P7-WP1 UX FOUNDATION APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING.
JSON Schema uses closed objects and no external references; the
Draft 2020-12 metaschema identifier is not a fetched reference. Validation is deterministic and offline.

## 4. Local builder evidence

Original builder measurements before the MEDIUM-1 correction (2026-10-04); targeted correction evidence follows:

| Verification | Actual result |
| --- | --- |
| `.venv/bin/python knowledge/validation/run_all.py` | PASS — 30/30 |
| `.venv/bin/python knowledge/validation/run_all.py --json` | `gate=PASS`, `validators_run=30`, `validators_failed=0` |
| `.venv/bin/python knowledge/validation/ci_selftest.py` | PASS — 15/15 representative defects caught by expected validators |
| UX validator directly | PASS — 65/65 UXF checks; 86/86 negative mutations rejected by their named checks; all 65 checks have a targeted mutation |
| New P7-WP1 self-test | Evidence-content surface changed from `CONTENT_PERMISSION_REQUIRED` to `ROLE_ONLY`; caught specifically and exclusively by `validate_ux_foundation.py` (UXF-20, plus structural/projection checks) |
| Frozen Phase-6 closure validator | PASS — 64 checks, 2 accepted lifecycle scenarios, 111 rejected negative mutations; existing 19-artifact snapshot unchanged |
| Canonical validator count | 29 before → 30 after |
| Self-test defect count | 14 before → 15 after |
| Surface inventory | 22 total; 20 data-bearing; 2 non-resource shells |
| Presentation-only concepts / generic states | 7 / 21 |
| Exact change surface | 6 created + 3 modified = 9 files; no unrelated changes |
| Frozen accepted surface | No changes to Phase-6 closure/contracts/schemas/gates, ADRs, Phase-3/4, runtime/publish/rules/taxonomies |
| CI path filter | Exactly one `docs/07-ux/**` entry added to the shared push/PR path list; no job, version, dependency or other trigger change |
| `git diff --check` | PASS |
| All nine files, including untracked files | No trailing whitespace or tabs; newline-terminated |
| Engine version | `ENGINE_VERSION = 1.0.0` unchanged |

These are local builder measurements, not remote CI or merge evidence. The subsequent independent review reported
BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 0 new — REQUEST_CHANGES. MEDIUM-1 was the sole scope of the targeted correction.

### MEDIUM-1 targeted correction evidence

The builder replaced the flat error mapping with a closed conditional mapping over the accepted
`EvaluationResponse.state` and `result_availability`. UXF-64 derives pending/failure groups from API-001's
persistence-to-API state and failure-class mappings and cross-checks the response vocabularies with OpenAPI.
No backend state, surface, role or permission was added. Detailed recovery remains P7-WP3 / P7-WP5.

| Targeted verification | Actual result |
| --- | --- |
| QUEUED / NOT_YET_AVAILABLE + EVALUATION_NOT_COMPLETED → ACTION_PENDING | Accepted |
| RUNNING / NOT_YET_AVAILABLE + EVALUATION_NOT_COMPLETED → ACTION_PENDING | Accepted |
| FAILED / NOT_PRODUCED + EVALUATION_NOT_COMPLETED → ACTION_PENDING | Rejected by UXF-64 |
| FAILED / NOT_PRODUCED + EVALUATION_NOT_COMPLETED → ACTION_FAILED | Accepted |
| Targeted mutations | NEG-UXF-087…089: failed-as-pending, failed branch removed, unconditional pending mapping; all rejected by UXF-64 |
| Direct UX validator | PASS — 65/65 checks; 89/89 mutations rejected by intended checks (86 existing + 3 targeted) |
| Canonical runner | PASS — 30/30 |
| Canonical JSON result | gate=PASS, validators_run=30, validators_failed=0 |
| Existing self-test | PASS — 15/15; P7-WP1 role-only content defect still caught exclusively by validate_ux_foundation.py |
| Frozen Phase-6 closure validator | PASS — 64 checks, 2 accepted lifecycle scenarios, 111 rejected mutations |
| Correction surface | Six files: UX-001, UX machine contract, UX schema, negative mutations, UX validator, GATE-026 |
| Schema change | One required closed conditional-mapping object; existing schema constraints unchanged |
| GATE-026 change | One narrow Evaluation pending/failure criterion; review history and correction evidence recorded |
| Preserved integration files | run_all.py, ci_selftest.py and knowledge-validation.yml byte-for-byte unchanged by this correction |
| Scope / freeze | All unrelated machine semantics and prior 86 mutations unchanged; no accepted Phase-6 artifact changed |
| Whitespace | git diff --check PASS; all six correction files have no trailing whitespace/tabs and terminate with a newline |
| Engine / baseline | ENGINE_VERSION = 1.0.0; HEAD remains bbe741b8ebfb7adbc399c1231b74f67f73ba2cfc |

MEDIUM-1 was corrected by the builder and CLOSED by targeted independent re-review.
No new self-test, validator entry or UXF check was added (65 checks, 30 validators, 15 self-tests).

Builder validation is not independent review, self-approval, runtime authorization verification, accessibility
certification, frontend implementation or production readiness. Independent approval is recorded separately below.

### Independent approval and acceptance bookkeeping

The following independent review results were supplied for acceptance bookkeeping on 2026-10-05:

| Review stage | Findings | Recommendation / finding state |
| --- | --- | --- |
| Initial independent review | BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 0 new | REQUEST_CHANGES |
| MEDIUM-1 correction | Evaluation terminal failure could be presented as pending; state-aware lifecycle mapping introduced | Correction completed; regression mutations retained |
| Targeted independent re-review | BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 0 new / INFO 0 new | APPROVE; MEDIUM-1 CLOSED |

Reviewer final statement: "P7-WP1 is ready for acceptance bookkeeping and commit/PR closure.
P7-WP2 has not started."

Approval advances the foundation's status and its existing `independently_reviewed` / `approved` machine claims.
The schema already permits these values and is unchanged. Existing status mutations now reject premature closure
and remote-CI/merge claims; the total remains 89. All substantive UX invariants, including UXF-64, are preserved.
No PR number, merge SHA or remote CI result is recorded because none exists yet.

## 5. Handoff, open items and known limits

UX-001 §§10–12 records all owners and the explicit builder self-challenge. P7-WP2 owns intake; WP3 results; WP4
review/permission/privilege; WP5 reporting/history/removal; WP6 accessibility/responsive/language/enrichment; WP7
integrated closure. None has started. Assignment discovery/If-Match acquisition, browser session/CSRF, user data
export, expanded provider attribution and report format remain owned deferred decisions, not invented capabilities.

**P6-WP7-LOW-1: OPEN / NON-BLOCKING.** Four contract JSON Schemas remain outside the canonical 19-artifact hash
snapshot. Owner: **next governed Phase-6 snapshot revision / Programme governance**. This WP does not fix it.
G-09 and OI-05 stay OPEN; ASM-002 stays UNCONFIRMED / PROVISIONAL. No numeric retention or tenancy UX.

The exact access matrix and structured semantics are machine-checked; independent foundation review is complete.
Usability and later runtime enforcement still require evaluation. P7-WP1 has no working screens or later-flow detail.

## 6. Builder stop disposition

Final independent review: **BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 0 new / INFO 0 new — APPROVE**.
**MEDIUM-1: CLOSED.** Builder-reported unresolved findings: **BLOCKER 0 / HIGH 0 / MEDIUM 0**.
The accepted Phase-6 snapshot LOW remains OPEN / NON-BLOCKING with its existing owner; the owned deferred design
decisions above remain open. The independent counts above are the supplied reviewer outcome, not builder self-approval.

Recommendation: **READY_TO_COMMIT_P7_WP1**. Approved following independent review; remote CI and merge pending.
No commit or push performed; HEAD remains the requested baseline. No P7-WP2 work started.

P7-WP1 is NOT CLOSED. GATE-026 is not finally closed or merged. No new review cycle is opened.
STOP WITHOUT COMMIT. DO NOT START P7-WP2.
