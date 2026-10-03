# GATE-021 — Phase 6 API contract checkpoint

| Field | Value |
|---|---|
| Document ID | GATE-021 |
| Version | 1.0 |
| Status | **P6-WP3 API CONTRACT APPROVED — REMOTE CI + MERGE PENDING**; P6-WP3 not yet formally closed; not Phase-6 closure |
| Phase assessed | Phase 6 — P6-WP3 API resource, authorization & protocol contract |
| Owner role | API Architect / Backend Architect |
| Baseline | P6-WP2 merge `58c8853dc6ee6ea7cf621ff88fe7c54bceae15a3` (PR #27) |
| Primary deliverables | [API-001](../06-contracts/API-001-api-resource-protocol-contract.md) v0.1; [`contracts/api/api-v1.json`](../../contracts/api/api-v1.json) + JSON Schema + negative fixtures; `knowledge/validation/validate_api_contract.py` |
| Governing authority | DATA-001, DATA-001-WP2, ADR-0008/0009/0010/0011/0013/0014/0016/0017, ARCH-002…007, DET-001, AI-001 WP4/WP5 |
| Independent review | Initial: BLOCKER 0 / HIGH 0 / MEDIUM 2 / LOW 4 / INFO 4 — REQUEST_CHANGES (§7a). Targeted re-review: BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 2 / INFO 5 — **APPROVE** (§7b) |
| Related open items | ASM-002 (single tenancy, unconfirmed), OI-05, G-09, WP4 LOW-3 (→ P6-WP5 / ADR-0012) |
| Last updated | 2026-10-02 |

## 1. Checkpoint purpose

GATE-021 assesses whether API-001 gives P6-WP4 (OpenAPI), backend and future client work an implementation-independent
API v1 contract — resources, operations, authorization, protocol and error semantics — that preserves DATA-001,
DATA-001-WP2 and the accepted Phase-5 architecture. It does not accept API-001, create OpenAPI, implement an API or
close Phase 6.

## 2. Acceptance criteria

| # | Criterion | Evidence | State |
|---:|---|---|---|
| 1 | API-001 exists | API-001 metadata | AUTHORED |
| 2 | Resource catalog complete | API-001 §7 (Matrix A, generated) | AUTHORED — VALIDATED |
| 3 | Operation catalog complete (53 operations) | API-001 §8 (Matrix B, generated); `api-v1.json` | AUTHORED — VALIDATED |
| 4 | Authorization matrix complete | API-001 §9 (Matrix C, generated) | AUTHORED — VALIDATED |
| 5 | Resource-level authorization preserved (role + resource, deny by default) | API-001 §5; AC-04/AC-05 | AUTHORED — VALIDATED |
| 6 | Administrator not automatically granted evidence access | API-001 §§5, 34; AC-05, AC-23; NEG-03, NEG-21 | AUTHORED — VALIDATED |
| 6a | Break-glass: ADMINISTRATOR-only creation/activation in v1; no analyst self-elevation; review by a different principal (MEDIUM-2) | API-001 §23; AC-25; NEG-27, NEG-28 | **CLOSED** — approved at targeted re-review |
| 6b | No self-assignment through review assignment, including dual-role principals (LOW-1) | API-001 §16; AC-26; NEG-29 | **CLOSED** — approved at targeted re-review |
| 7 | Evidence metadata and content separated; raw evidence access controlled and audited | API-001 §12; AC-05, AC-08; NEG-02, NEG-19 | AUTHORED — VALIDATED |
| 8 | Evaluation creation cannot set result, provenance or knowledge fields | API-001 §§13, 32; AC-15; NEG-10 | AUTHORED — VALIDATED |
| 9 | DetectionResult immutable through the API | API-001 §14; AC-06; NEG-01; CI self-test | AUTHORED — VALIDATED |
| 10 | Adjudication separate, actor server-side, pins the exact result digest | API-001 §15; AC-15; NEG-09 | AUTHORED — VALIDATED |
| 10a | C4 adjudication rationale needs content permission; adjudication reads classified C4 (LOW-4) | API-001 §15; AC-27; NEG-30…NEG-32 | **CLOSED** — approved at targeted re-review |
| 10b | No API-invented result semantics: no action priority; every governed result field traced to Phase-3 or an API-only category (MEDIUM-1) | API-001 §14.1; AC-24; NEG-23…NEG-26 | **CLOSED** — approved at targeted re-review |
| 11 | Report and replay semantics explicit | API-001 §§17–18 | AUTHORED |
| 12 | Replay never recalls AI and never substitutes latest/current knowledge | API-001 §18; AC-14; NEG-08, NEG-15 | AUTHORED — VALIDATED |
| 13 | Post-deletion unavailable behaviour explicit (tombstones fail closed) | API-001 §19 | AUTHORED |
| 14 | Knowledge API cannot bypass Git/CI governance; no rule-body mutation | API-001 §21; AC-10; NEG-20 | AUTHORED — VALIDATED |
| 15 | `content_digest` load-bearing for activation; no bundle_version-only or latest activation | API-001 §21; AC-10; NEG-04, NEG-05 | AUTHORED — VALIDATED |
| 16 | No arbitrary server-side URL-fetch endpoint; WP4 LOW-3 stays deferred | API-001 §22; AC-11; NEG-06 | AUTHORED — VALIDATED |
| 17 | Idempotency defined (REQUIRED on every POST; conflicting reuse = 409; retention not invented) | API-001 §27; AC-09; NEG-16 | AUTHORED — VALIDATED |
| 18 | Concurrency strategy defined (ETag / If-Match; immutable resources excluded) | API-001 §28; AC-21 | AUTHORED — VALIDATED |
| 19 | Canonical error envelope and safe error model | API-001 §29 | AUTHORED |
| 20 | HTTP status mapping defined | API-001 §29.1 (Matrix F, generated); AC-19 | AUTHORED — VALIDATED |
| 21 | Pagination and filtering defined (cursor; allow-listed filters; no invented numbers) | API-001 §30; AC-20; NEG-22 | AUTHORED — VALIDATED |
| 22 | API versioning defined and kept independent of engine, bundle, contract and migration versions | API-001 §37 | AUTHORED |
| 23 | Mass-assignment protections explicit; request DTOs reject unknown fields | API-001 §32; AC-15/AC-16; NEG-17 | AUTHORED — VALIDATED |
| 24 | Audit-operation matrix defined | API-001 §35 (Matrix G, generated); AC-08 | AUTHORED — VALIDATED |
| 25 | Field-visibility matrix defined; no secrets exposed | API-001 §34 (Matrix D); AC-23 | AUTHORED — VALIDATED |
| 26 | State-transition/command matrix; API states map every persistence state | API-001 §26 (Matrix H), §13.1; AC-17; NEG-18 | AUTHORED — VALIDATED |
| 27 | DATA-001 and Phase-5/6 authority traceability | API-001 §§38–39 (Matrices I, J) | AUTHORED |
| 28 | Required Mermaid diagrams (submission flow, review/adjudication, report/replay, knowledge control, authorization, deletion) | API-001 §§5, 10 | AUTHORED |
| 29 | Machine-readable API catalog + JSON Schema exist | `contracts/api/**` | PASS — LOCAL BUILDER |
| 30 | API validator exists (AC-01…AC-27); 32 negative mutations rejected | `validate_api_contract.py` | PASS — LOCAL BUILDER |
| 31 | Canonical gate includes the validator; CI self-test proves it bites | `run_all.py` (25 checks), `ci_selftest.py` (10 defects) | PASS — LOCAL BUILDER |
| 32 | CI path coverage for `docs/06-contracts/**` and `contracts/**` | Existing P6-WP2 filters (workflow unchanged) | CONFIRMED |
| 33 | ASM-002 provisional; no `tenant_id` anywhere | API-001 §6; AC-12; NEG-07 | AUTHORED — VALIDATED |
| 34 | ADR-0012 remains Planned; no new ADR issued | `adr/README.md` unchanged | CONFIRMED |
| 35 | DATA-001, DATA-001-WP2 and ADR-0011 unchanged | Change surface §7 | CONFIRMED |
| 36 | Phase-3/Phase-4 frozen; `ENGINE_VERSION = 1.0.0` | Validation §5 | PASS — LOCAL BUILDER |
| 37 | G-09 and OI-05 OPEN; no production-readiness, compliance or efficacy claim | API-001 §§1, 43 | AUTHORED |
| 38 | Independent review before acceptance | §§6, 7a, 7b | INITIAL REQUEST_CHANGES → corrections → TARGETED RE-REVIEW **APPROVE** |

## 3. Decision records

No ADR is issued by P6-WP3: every decision here (REST style, upload mechanism, existence masking, ETag/If-Match,
cursor pagination, error envelope, versioning) is an API-contract choice inside the accepted architecture. ADR-0012
remains **Planned / not issued** (P6-WP5). ADR-0011 is unchanged.

## 4. Programme and claim status

| Item | Status |
|---|---|
| Phase 6 | **IN PROGRESS** — P6-WP1 and P6-WP2 merged (PRs #26, #27); P6-WP3 approved following independent review, remote CI + merge pending; P6-WP4…WP6 not started |
| ASM-002 | **UNCONFIRMED / PROVISIONAL** — does not block this contract; blocks tenancy-sensitive implementation |
| OI-05 | **OPEN** |
| G-09 | **OPEN** |
| WP4 LOW-3 | **OPEN / DEFERRED** → P6-WP5 / ADR-0012 |

No API implementation, deployment, penetration test, load test, availability, compliance, legal-admissibility or
detection-efficacy claim is made.

## 5. Required local builder validation

| Check | Required result | State |
|---|---|---|
| `.venv/bin/python knowledge/validation/run_all.py` | PASS — 25/25 | PASS — LOCAL BUILDER |
| `.venv/bin/python knowledge/validation/run_all.py --json` | `gate=PASS`, `validators_run=25`, `validators_failed=0` | PASS — LOCAL BUILDER |
| `.venv/bin/python knowledge/validation/ci_selftest.py` | PASS — 10/10 defects caught | PASS — LOCAL BUILDER |
| `validate_api_contract.py` negative mutations | 32/32 rejected by the expected check | PASS — LOCAL BUILDER |
| Phase-3/Phase-4/runtime/publish freeze; `ENGINE_VERSION` | zero diff; `1.0.0` | PASS — LOCAL BUILDER |
| `git diff --check` + whitespace of all P6-WP3 files | clean | PASS — LOCAL BUILDER |

## 6. Finalisation conditions

| # | Condition | State |
|---:|---|---|
| 1 | Independent review APPROVE (builder did not self-review) | **SATISFIED** — targeted re-review APPROVE |
| 2 | Canonical validation PASS (25/25) and CI self-test PASS (10/10) | **SATISFIED** — reviewer and local builder runs |
| 3 | Remote GitHub Actions PASS | **PENDING** |
| 4 | Merge to `main` | **PENDING** |

Until conditions 3 and 4 are met the correct state is **P6-WP3 API CONTRACT APPROVED — REMOTE CI + MERGE PENDING**,
not P6-WP3 CLOSED.

## 7. Change boundary

New: `docs/06-contracts/API-001-api-resource-protocol-contract.md`; `docs/00-program/GATE-021-phase-6-api-contract.md`;
`contracts/api/api-v1.json`; `contracts/api/api-contract.schema.json`; `contracts/api/fixtures/negative-mutations.json`;
`knowledge/validation/validate_api_contract.py`.
Modified: `knowledge/validation/run_all.py` (25th check); `knowledge/validation/ci_selftest.py` (10th defect).
Unchanged: the CI workflow, DATA-001, DATA-001-WP2, `contracts/postgresql/**`, all ADRs and the ADR index, ARCH
documents, Phase-3/Phase-4 runtime, schemas, rules and taxonomies.

## 7a. Independent review outcome and corrections

Initial independent P6-WP3 review: **BLOCKER 0 / HIGH 0 / MEDIUM 2 / LOW 4 / INFO 4 — REQUEST_CHANGES.**

| Finding | Severity | Status | Owner |
|---|---|---|---|
| MEDIUM-1 invented `RecommendedAction` priority | MEDIUM | **CORRECTED** — field removed; structural traceability (AC-24) incl. rejection of the schema-reserved, never-emitted Phase-3 `priority`; NEG-23…NEG-26 | — |
| MEDIUM-2 ANALYST self-activated break-glass | MEDIUM | **CORRECTED** — ADMINISTRATOR-only creation/activation and content use in v1; review by a different principal; AC-25; NEG-27, NEG-28 | — |
| LOW-1 review self-assignment (dual role) | LOW | **CORRECTED** — `ASSIGNEE_NOT_CALLER`; AC-26; NEG-29 | — |
| LOW-4 C4 adjudication rationale visible without content permission | LOW | **CORRECTED** — `IF_GRANTED_CONTENT`; adjudication reads C4 + audited; AC-27; NEG-30…NEG-32 | — |
| LOW-2 API idempotency persistence | LOW | **RECORDED** — does not block this contract; additive DATA-001-WP2 revision required before implementation (key, principal scope, operation/resource scope, request fingerprint, execution state, original outcome/resource identity, response material as policy allows, retention once defined; C4 outcomes under classification/retention/deletion governance) | DATA-001-WP2 revision + P6-WP6 |
| LOW-3 ETag ABA risk | LOW | **RECORDED** — ETag + If-Match retained; derivation defined in P6-WP4; additive WP2 `state_changed_at`/version if needed before implementation | P6-WP4 |
| INFO-1 `artifact_kind OTHER` for user context | INFO | Non-blocking (hashed, ECS-only, enters envelope construction) | Later WP2 vocabulary revision |
| INFO-2 audit-read event type | INFO | Unresolved; not invented | P6-WP6 |
| INFO-3 numeric limits | INFO | NOT YET SPECIFIED (page size, upload size, break-glass duration, rate thresholds, idempotency retention) | P6-WP4 / P6-WP6 / Sponsor |
| INFO-4 break-glass create reveals case existence | INFO | Exposure now confined to administrators; general masking rule unchanged | — |

CI self-test: unchanged at **10** defects. The new guards are proven by the validator's own negative mutations, which
run inside the canonical gate (a guard that stopped biting fails the gate), and the existing API defect (PATCH on the
completed `DetectionResult`) remains in force.

## 7b. Targeted re-review and acceptance

Targeted independent re-review: **BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 2 / INFO 5 — FINAL RECOMMENDATION: APPROVE.**

Reviewer canonical validation: `run_all` PASS 25/25; `run_all --json` `gate=PASS`, `validators_run=25`,
`validators_failed=0`; `ci_selftest` PASS 10/10; `git diff --check` clean; `ENGINE_VERSION = 1.0.0`.

| Item | Disposition | Owner |
|---|---|---|
| MEDIUM-1 | **CLOSED** — `RecommendedActionView` exposes no API-invented priority; AC-24 structurally traces every governed result field to runtime-emitted Phase-3 semantics or a narrowly allow-listed non-decision API-only category; NEG-23…NEG-26 prove invented/unsupported fields fail | — |
| MEDIUM-2 | **CLOSED** — ANALYST can no longer create or self-activate break-glass; ADMINISTRATOR is the only v1 creator under governed controls; AC-25, NEG-27, NEG-28 | — |
| LOW-1 | **CLOSED** — no self-assignment (`ASSIGNEE_NOT_CALLER`), incl. dual-role principals; AC-26, NEG-29 | — |
| LOW-4 | **CLOSED** — C4 rationale requires content permission; adjudication reads C4 and audited; AC-27, NEG-30…NEG-32 | — |
| LOW — idempotency persistence | **OPEN / NON-BLOCKING** — DOES_NOT_BLOCK_P6_WP3_CONTRACT_BUT_REQUIRES_PERSISTENCE_REVISION_BEFORE_IMPLEMENTATION; no retention invented | Additive DATA-001-WP2 revision + P6-WP6 |
| LOW — ETag ABA risk | **OPEN / NON-BLOCKING** — ETag + If-Match retained | P6-WP4 (concrete derivation); additive WP2 resource-version / `state_changed_at` before implementation if needed |
| INFO-1 `artifact_kind OTHER` | Acceptable for current user context | Possible later WP2 vocabulary refinement |
| INFO-2 audit-read event type | Unresolved | P6-WP6 |
| INFO-3 numeric operational limits | NOT YET SPECIFIED | P6-WP4 / P6-WP6 / Sponsor |
| INFO-4 break-glass existence signal | Informational; limited to the administrator-only operation | — |
| INFO-5 reserved-not-emitted Phase-3 fields | AC-24 knows `recommendedAction.priority` explicitly; any future reserved-but-not-emitted Phase-3 result field requires updating the API traceability guard with the Phase-3 schema change | Owner of that Phase-3 change |

Preserved: ADR-0012 Planned / not issued; WP4 LOW-3 OPEN / DEFERRED → P6-WP5 / ADR-0012; ASM-002 UNCONFIRMED /
PROVISIONAL; G-09 OPEN; OI-05 OPEN; `ENGINE_VERSION = 1.0.0`.

## 8. Builder findings carried to review

| Severity | Finding | Owner |
|---|---|---|
| LOW (was MEDIUM; review reclassified) | API idempotency records not in DATA-001-WP2 (see §7a LOW-2) | DATA-001-WP2 revision + P6-WP6 |
| LOW | ETag source / ABA (see §7a LOW-3) | P6-WP4 |
| INFO | User context via `artifact_kind OTHER` | Later WP2 vocabulary revision |
| INFO | Audit-read event type pending | P6-WP6 |
| INFO | Numeric limits NOT YET SPECIFIED | P6-WP4 / P6-WP6 / Sponsor |

## 9. Recommendation

Proceed to the P6-WP3 commit and PR. After remote CI PASS and merge to `main`, P6-WP3 may be recorded as CLOSED. Do
not create OpenAPI, do not issue ADR-0012 and do not begin P6-WP4 under this checkpoint.
