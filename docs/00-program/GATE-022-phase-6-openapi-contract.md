# GATE-022 — Phase 6 OpenAPI contract checkpoint

| Field | Value |
|---|---|
| Document ID | GATE-022 |
| Version | 1.0 |
| Status | **P6-WP4 OPENAPI CONTRACT APPROVED — REMOTE CI + MERGE PENDING**; P6-WP4 not yet formally closed; not Phase-6 closure |
| Phase assessed | Phase 6 — P6-WP4 OpenAPI specification + contract consistency validation |
| Owner role | API Architect / Backend Architect |
| Baseline | P6-WP3 merge `4d08c5e570b9a08b87a56a51213f0423ea74166f` (PR #28) |
| Primary deliverables | [`contracts/api/openapi-v1.json`](../../contracts/api/openapi-v1.json) (OpenAPI 3.1.0); [OAS-001](../06-contracts/OAS-001-openapi-contract.md) v0.1; `knowledge/validation/validate_openapi_contract.py`; `contracts/api/fixtures/openapi-negative-mutations.json` |
| Governing authority | API-001 + `contracts/api/api-v1.json` (authoritative API semantics); DATA-001; DATA-001-WP2; ADR-0009/0010/0011/0013/0014/0016/0017; DET-001 |
| Independent review | BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 2 / INFO 4 — **APPROVE** (§7a) |
| Related open items | Idempotency persistence (LOW, WP2 revision + P6-WP6); ETag implementation dependency (WP2 revision); ASM-002; OI-05; G-09; WP4 LOW-3 (→ P6-WP5 / ADR-0012) |
| Last updated | 2026-10-03 |

## 1. Checkpoint purpose

GATE-022 assesses whether the OpenAPI 3.1 artifact encodes API-001 exactly and is mechanically kept in parity with the
accepted API catalog, while preserving the Phase-3 result semantics and the Phase-5/Phase-6 security and authority
boundaries. It does not accept OAS-001, implement an API or close Phase 6.

## 2. Acceptance criteria

| # | Criterion | Evidence | State |
|---:|---|---|---|
| 1 | OpenAPI 3.1 artifact exists (JSON) | `openapi-v1.json` (`openapi: 3.1.0`); OA-01 | PASS — LOCAL BUILDER |
| 2 | All 53 API operations represented; no extra operation; no duplicate operationId | OA-03; NEG-OA-01/02/04 | PASS — LOCAL BUILDER |
| 3 | Method/path parity | OA-04; NEG-OA-03 | PASS — LOCAL BUILDER |
| 4 | Request and response schema parity | OA-06, OA-07, OA-16; NEG-OA-41 | PASS — LOCAL BUILDER |
| 5 | Success-status parity | OA-05; NEG-OA-23 | PASS — LOCAL BUILDER |
| 6 | Authentication and role parity | OA-08; NEG-OA-05, NEG-OA-07 | PASS — LOCAL BUILDER |
| 7 | Resource-authorization / content-permission parity | OA-09; NEG-OA-06 | PASS — LOCAL BUILDER |
| 8 | Idempotency parity (`Idempotency-Key` required where REQUIRED; 409 IDEMPOTENCY_KEY_REUSED) | OA-10; NEG-OA-22 | PASS — LOCAL BUILDER |
| 9 | Audit, sensitivity and sync/async parity | OA-11, OA-12, OA-13; NEG-OA-37/38/39 | PASS — LOCAL BUILDER |
| 10 | Error code / HTTP status parity; canonical error envelope | OA-15; NEG-OA-40 | PASS — LOCAL BUILDER |
| 11 | All local `$ref`s resolve; no external `$ref` | OA-17; NEG-OA-24, NEG-OA-25 | PASS — LOCAL BUILDER |
| 12 | DetectionResult immutable; no DELETE | OA-20; NEG-OA-08; CI self-test | PASS — LOCAL BUILDER |
| 13 | No invented decision fields; no priority, probability or score; AC-24 traces preserved | OA-19, OA-21; NEG-OA-09/10/43 | PASS — LOCAL BUILDER |
| 14 | Break-glass ADMINISTRATOR-only creator | OA-25; NEG-OA-15 | PASS — LOCAL BUILDER |
| 15 | Review self-assignment prohibited (`ASSIGNEE_NOT_CALLER`) | OA-26; NEG-OA-16 | PASS — LOCAL BUILDER |
| 16 | C4 adjudication rationale keeps content permission; returning operations C4 | OA-27; NEG-OA-17 | PASS — LOCAL BUILDER |
| 17 | Replay exact / no-AI / no-latest semantics | OA-28; NEG-OA-18/19/44 | PASS — LOCAL BUILDER |
| 18 | Knowledge activation requires content_digest; no bundle_version or activate-latest | OA-22, OA-23; NEG-OA-13/14/34 | PASS — LOCAL BUILDER |
| 19 | No arbitrary URL fetch | OA-24; NEG-OA-12 | PASS — LOCAL BUILDER |
| 20 | No tenant_id anywhere | OA-18; NEG-OA-11 | PASS — LOCAL BUILDER |
| 21 | ETag strategy explicitly resolved at API level | OAS-001 §8 (Decision B); OA-34; NEG-OA-33 | AUTHORED — VALIDATED |
| 22 | Mass-assignment protections encoded | OA-29, OA-31; NEG-OA-20/21 | PASS — LOCAL BUILDER |
| 23 | Pagination encoded without invented numbers; filters allow-listed | OA-30; NEG-OA-29/30 | PASS — LOCAL BUILDER |
| 24 | No hostname/topology; health detail not leaked | OA-02, OA-32; NEG-OA-31/35 | PASS — LOCAL BUILDER |
| 25 | OpenAPI 3.1 semantics only (no `nullable`); component schemas valid JSON Schema 2020-12 | OA-01, OA-36; NEG-OA-26/27/42 | PASS — LOCAL BUILDER |
| 26 | Version independence (info.version ≠ ENGINE_VERSION); no framework dependency | OA-35; NEG-OA-36 | PASS — LOCAL BUILDER |
| 27 | OpenAPI validator exists (36 checks); 44 negative mutations rejected | `validate_openapi_contract.py` | PASS — LOCAL BUILDER |
| 28 | Canonical runner includes validator; self-test proves it bites | `run_all.py` (26 checks); `ci_selftest.py` (11 defects) | PASS — LOCAL BUILDER |
| 29 | CI path coverage | Existing `contracts/**` and `docs/06-contracts/**` filters (workflow unchanged) | CONFIRMED |
| 30 | ADR-0012 remains Planned; no new ADR | `adr/README.md` unchanged | CONFIRMED |
| 31 | WP4 LOW-3 remains OPEN / deferred to P6-WP5 | OAS-001 §§15–16 | CONFIRMED |
| 32 | ASM-002 provisional; G-09 and OI-05 OPEN | OAS-001 §18 | CONFIRMED |
| 33 | API-001, GATE-021, DATA-001, DATA-001-WP2, ADR-0011 unchanged | Change surface §7 | CONFIRMED |
| 34 | No implementation, deployment, certification or compliance claim | OAS-001 §§1, 18 | AUTHORED |
| 35 | Independent review before acceptance | §§6, 7a | **APPROVE** (independent reviewer) |

## 3. Decision records

No ADR is issued. The ETag derivation (OAS-001 §8, Decision B) is an API-contract decision that creates a persistence
implementation dependency; it changes no accepted ADR. ADR-0012 remains **Planned / not issued** (P6-WP5).

## 4. Programme and claim status

| Item | Status |
|---|---|
| Phase 6 | **IN PROGRESS** — P6-WP1, P6-WP2, P6-WP3 merged (PRs #26–#28); P6-WP4 approved following independent review, remote CI + merge pending; P6-WP5/WP6 not started |
| Idempotency persistence | OPEN / NON-BLOCKING — additive DATA-001-WP2 revision + P6-WP6 |
| ETag | API-design decision made (server-authoritative monotonic revision); implementation blocked on an additive WP2 revision |
| ASM-002 | UNCONFIRMED / PROVISIONAL |
| OI-05 | OPEN |
| G-09 | OPEN |
| WP4 LOW-3 | OPEN / DEFERRED → P6-WP5 / ADR-0012 |

Validation is deterministic structural validation plus catalog parity. No official OpenAPI conformance validator is
pinned, so no full-compliance claim is made. No implementation, deployment, runtime-authorization test, penetration
test, load test, production readiness, compliance, legal-admissibility or detection-efficacy claim is made.

## 5. Required local builder validation

| Check | Required result | State |
|---|---|---|
| `.venv/bin/python knowledge/validation/run_all.py` | PASS — 26/26 | PASS — LOCAL BUILDER |
| `.venv/bin/python knowledge/validation/run_all.py --json` | `gate=PASS`, `validators_run=26`, `validators_failed=0` | PASS — LOCAL BUILDER |
| `.venv/bin/python knowledge/validation/ci_selftest.py` | PASS — 11/11 defects caught | PASS — LOCAL BUILDER |
| `validate_openapi_contract.py` negative mutations | 44/44 rejected by the expected check | PASS — LOCAL BUILDER |
| Phase-3/Phase-4/runtime/publish freeze; `ENGINE_VERSION` | zero diff; `1.0.0` | PASS — LOCAL BUILDER |
| `git diff --check` + whitespace of all P6-WP4 files | clean | PASS — LOCAL BUILDER |

## 6. Finalisation conditions

| # | Condition | State |
|---:|---|---|
| 1 | Independent review APPROVE (builder did not self-review) | **SATISFIED** |
| 2 | Canonical validation PASS (26/26) and CI self-test PASS (11/11) | **SATISFIED** — reviewer and local builder runs |
| 3 | Remote GitHub Actions PASS | **PENDING** |
| 4 | Merge to `main` | **PENDING** |

Until conditions 3 and 4 are met the correct state is **P6-WP4 OPENAPI CONTRACT APPROVED — REMOTE CI + MERGE
PENDING**, not P6-WP4 CLOSED.

## 7. Change boundary

New: `contracts/api/openapi-v1.json`; `contracts/api/fixtures/openapi-negative-mutations.json`;
`docs/06-contracts/OAS-001-openapi-contract.md`; `docs/00-program/GATE-022-phase-6-openapi-contract.md`;
`knowledge/validation/validate_openapi_contract.py`.
Modified: `knowledge/validation/run_all.py` (26th check); `knowledge/validation/ci_selftest.py` (11th defect).
Unchanged: the CI workflow, API-001, GATE-021, `contracts/api/api-v1.json`, `api-contract.schema.json`, DATA-001,
DATA-001-WP2, `contracts/postgresql/**`, all ADRs and the ADR index, ARCH documents, Phase-3/Phase-4 runtime, schemas,
rules and taxonomies.

## 7a. Independent review outcome

Independent P6-WP4 review: **BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 2 / INFO 4 — FINAL RECOMMENDATION: APPROVE.**
Reviewer canonical validation: `run_all` PASS 26/26; `run_all --json` `gate=PASS`, `validators_run=26`,
`validators_failed=0`; `ci_selftest` PASS 11/11; `ENGINE_VERSION = 1.0.0`.

| Finding | Severity | Disposition | Owner |
|---|---|---|---|
| Durable idempotency persistence not solved by OpenAPI | LOW | **OPEN / NON-BLOCKING** — DOES_NOT_BLOCK_P6_WP4_CONTRACT. Future record needs idempotency key, scope, request fingerprint, execution state, prior resource/outcome, and retention/deletion treatment; no retention invented | Additive DATA-001-WP2 revision + P6-WP6 |
| ETag persistence | LOW | **API-design ABA question CLOSED** by Decision B (opaque strong validator from a server-authoritative monotonic mutation revision). Current WP2 persistence is insufficient for all mutable resources: DOES_NOT_BLOCK_P6_WP4_CONTRACT_BUT_REQUIRES_PERSISTENCE_REVISION_BEFORE_IMPLEMENTATION; no field created here | Additive DATA-001-WP2 revision + P6-WP6 |
| INFO-1 no official OpenAPI validator pinned | INFO | Assurance is deterministic structural validation + catalog parity; no official certification claimed | Future CI decision |
| INFO-2 `GET /review-queue` returns `ETag`, but a collection ETag source is not defined under the single-resource revision model | INFO | Carried unchanged | Future OAS/API implementation refinement |
| INFO-3 `RecommendedActionView.action_code` is a string, not a Phase-3 enum | INFO | Matches accepted API-001/catalog semantics; unchanged | Future catalog/API revision |
| INFO-4 carried WP3 informational items | INFO | `artifact_kind OTHER`; audit-read event type; break-glass existence signal; reserved-field deny-set maintenance — all carried with their existing owners | As recorded in API-001 §44 / GATE-021 §7b |

Preserved: ADR-0012 Planned / not issued; WP4 LOW-3 OPEN / DEFERRED → P6-WP5 / ADR-0012; ASM-002 UNCONFIRMED /
PROVISIONAL; G-09 OPEN; OI-05 OPEN; `ENGINE_VERSION = 1.0.0`.

## 8. Builder findings carried to review

| Severity | Finding | Owner |
|---|---|---|
| LOW | ETag requires a server-authoritative monotonic revision that DATA-001-WP2 lacks for `case_record` and `review_routing_state`; implementation blocked until an additive WP2 revision | DATA-001-WP2 revision + P6-WP6 |
| LOW | Durable API idempotency record still absent from WP2 (carried from P6-WP3) | DATA-001-WP2 revision + P6-WP6 |
| INFO | Validation is structural + parity; no official OpenAPI conformance validator is pinned | Future CI decision |
| INFO | Evidence upload body declared `*/*` because accepted media types are configuration (server enforces `415`) | Implementation |
| INFO | Cookie-session/CSRF variant and user data export remain open (API-001 §41) | Phase 7 |

## 9. Recommendation

Proceed to the P6-WP4 commit and PR. After remote CI PASS and merge to `main`, P6-WP4 may be recorded as CLOSED. Do
not issue ADR-0012 and do not begin P6-WP5 under this checkpoint.
