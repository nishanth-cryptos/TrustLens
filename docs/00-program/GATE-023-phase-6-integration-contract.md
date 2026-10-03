# GATE-023 — Phase 6 integration contract checkpoint

| Field | Value |
|---|---|
| Document ID | GATE-023 |
| Version | 1.0 |
| Status | **P6-WP5 INTEGRATION CONTRACT APPROVED — REMOTE CI + MERGE PENDING**; P6-WP5 not yet formally closed; not Phase-6 closure |
| Phase assessed | Phase 6 — P6-WP5 external enrichment / threat-intelligence integration contract + ADR-0012 |
| Owner role | Integration Architect / Security Architect |
| Baseline | P6-WP4 merge `9fa022f74e1a4c76ab5875f8fe6715057fd5654c` (PR #29) |
| Primary deliverables | [INT-001](../06-contracts/INT-001-external-enrichment-integration-contract.md) v0.1; [ADR-0012](../../adr/ADR-0012-threat-intelligence-adapter-architecture-provider-selection.md); [`contracts/integrations/external-enrichment-v1.json`](../../contracts/integrations/external-enrichment-v1.json); [`integration-contract.schema.json`](../../contracts/integrations/integration-contract.schema.json); `contracts/integrations/fixtures/negative-mutations.json`; `knowledge/validation/validate_integration_contract.py` |
| Governing authority | DATA-001 §5.16/§20; DATA-001-WP2; API-001 §22; OAS-001; ARCH-004 §8; ADR-0007/0009/0010/0013/0016/0017; DET-001 |
| Independent review | Initial: BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 2 / INFO 4 — REQUEST_CHANGES (§7). Targeted re-review: BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 1 / INFO 4 — **APPROVE** (§8) |
| Related open items | G-09; OI-05; ASM-002; ASM-005; idempotency persistence (LOW); ETag revision persistence (LOW); WP4 LOW-3 (contract level addressed; implementation verification OPEN) |
| Last updated | 2026-10-03 |

## 1. Checkpoint purpose

GATE-023 assesses whether the P6-WP5 integration contract defines a governed, provider-neutral, indicator-lookup-only
boundary for external enrichment that prevents arbitrary outbound destination selection, addresses DNS rebinding /
resolve-time TOCTOU at contract level, keeps provider output outside the Phase-3 decision authority, and is mechanically
validated offline. It does not accept INT-001, implement a connector, activate an API endpoint or close Phase 6.

## 2. Acceptance criteria

| # | Criterion | Evidence | State |
|---|---|---|---|
| 1 | ADR-0012 issued under its reserved topic and Accepted following independent review | ADR-0012 header; `adr/README.md` (Accepted table); IC-02, IC-40 | MET |
| 2 | INT-001 exists (v0.1, Candidate) | INT-001; IC-03 | MET |
| 3 | Machine contract exists | `external-enrichment-v1.json` | MET |
| 4 | Schema exists and validates the contract | `integration-contract.schema.json`; IC-01 | MET |
| 5 | Deny-by-default egress | INT-001 §7; IC-05 | MET |
| 6 | Provider-controlled (governed policy) destinations only | INT-001 §7–§9; IC-06, IC-43 | MET |
| 7 | No generic fetch; indicator lookup only | INT-001 §3; IC-10 | MET |
| 8 | HTTPS-only provider transport unless separately governed | INT-001 §11; IC-07 | MET |
| 9 | TLS certificate + hostname verification required | INT-001 §11; IC-07 | MET |
| 10 | DNS-rebinding / TOCTOU invariant defined | INT-001 §13; IC-11, IC-12 | MET |
| 11 | Connected-peer binding defined | INT-001 §13 steps 5–7; IC-12, IC-51 (SC-06) | MET |
| 12 | Private/internal destination rejection | INT-001 §15; IC-13, IC-51 | MET |
| 13 | IPv4/IPv6 protections incl. IPv4-mapped IPv6 | INT-001 §12, §15; IC-13, IC-14 | MET |
| 14 | Mixed public/private DNS answers rejected | INT-001 §14; IC-15 | MET |
| 15 | Redirect revalidation every hop | INT-001 §16; IC-16, IC-18 | MET |
| 16 | No HTTPS → HTTP downgrade | INT-001 §16; IC-17 | MET |
| 17 | Proxy policy (no environment inheritance; governed proxy only) | INT-001 §17; IC-19 | MET |
| 17a | Governed proxy final-hop enforcement REQUIRED_AND_VERIFIED with scope equivalent to the direct connector (all forbidden classes, IPv4-mapped IPv6, metadata, mixed-answer rejection, alias validation, peer enforcement) | INT-001 §17 P-4/P-5; `proxy.final_hop_enforcement`, `proxy.enforcement_scope`; IC-19; SC-17/SC-18 (IC-51) | MET |
| 17b | **Deployment blocker:** without governed, verifiable final-hop enforcement evidence, proxy egress is DEPLOYMENT_BLOCKED and lookups are POLICY_REJECTED (`PROXY_ENFORCEMENT_UNVERIFIED`); no fallback to trusting the proxy | INT-001 §17, §22; ADR-0012 §8; `proxy.unverified_enforcement`, `proxy.unverified_fallback`; IC-19, IC-28; SC-16 (IC-51) | MET |
| 18 | Credential references only | INT-001 §18; IC-20 | MET |
| 19 | User/AI cannot control destination or sensitive headers | INT-001 §10, §28; IC-08, IC-09, IC-21 | MET |
| 20 | No raw evidence outbound | INT-001 §19; IC-22 | MET |
| 21 | Response schema validation | INT-001 §20; IC-23 | MET |
| 22 | Bounded response (no invented number) | INT-001 §20; IC-24, IC-48 | MET |
| 23 | Finite timeouts (no invented number) | INT-001 §20; IC-25, IC-48 | MET |
| 24 | Bounded retries (no invented count) | INT-001 §21; IC-26, IC-48 | MET |
| 25 | Provider NOT_FOUND not safe | INT-001 §22–§23; IC-27 | MET |
| 26 | Provider failure not safe | INT-001 §22; IC-28 | MET |
| 27 | Provider result cannot set DetectionResult directly | INT-001 §23; IC-29, IC-30 | MET |
| 28 | Provenance complete | INT-001 §24; IC-31 | MET |
| 29 | Cache / freshness semantics | INT-001 §26; IC-32, IC-33 | MET |
| 30 | Historical replay no-refetch | INT-001 §27; IC-34, IC-35, IC-36 | MET |
| 31 | Re-analysis creates a new enrichment | INT-001 §27; IC-37 | MET |
| 32 | No live network in CI | INT-001 §36; IC-38 | MET |
| 33 | Negative mutations present and each names its check | `negative-mutations.json` (91); INT-001 matrix L | MET |
| 34 | Validator integrated into the canonical gate | `run_all.py` (27 validators) | MET |
| 35 | Self-test proves the validator bites | `ci_selftest.py` defect 12 (user-controlled destination URL) | MET |
| 36 | ADR-0012 indexed correctly | `adr/README.md`; IC-40 | MET |
| 37 | No public API endpoint added; API/OpenAPI frozen | INT-001 §34; IC-46 | MET |
| 38 | Provider-neutral (no vendor, no provider selected) | IC-47 | MET |
| 39 | G-09 OPEN | §4; IC-41 | MET |
| 40 | OI-05 OPEN | §4; IC-42 | MET |
| 41 | ASM-002 provisional (no tenant concept) | §4; IC-39 | MET |
| 42 | Independent review | Initial REQUEST_CHANGES (§7) → targeted re-review APPROVE (§8) | **MET** |

## 3. Validation evidence (builder, local)

| Check | Result |
|---|---|
| `validate_integration_contract.py` | PASS — 51 checks, 19 offline conformance scenarios, 91 negative mutations rejected |
| `run_all.py` | See STOP REPORT (expected 27/27) |
| `ci_selftest.py` | See STOP REPORT (expected 12/12) |
| `ENGINE_VERSION` | `1.0.0` (unchanged) |

Validation is static and offline: no DNS lookup, socket, HTTP request, provider or API key. It proves contract
coherence, not connector correctness — no connector exists.

## 4. Preserved open items

| Item | Status |
|---|---|
| G-09 | **OPEN** — no efficacy claim |
| OI-05 | **OPEN** — retention duration NOT YET SPECIFIED |
| ASM-002 | **UNCONFIRMED / PROVISIONAL** |
| ASM-005 | Open — provider selection deferred |
| WP4 LOW-3 | Addressed at contract level (INT-001 §13 / ADR-0012 §5); implementation verification OPEN → P6-WP6 |
| Idempotency persistence | OPEN / NON-BLOCKING — additive DATA-001-WP2 revision + P6-WP6 |
| ETag revision persistence | OPEN / NON-BLOCKING — additive DATA-001-WP2 revision + P6-WP6 |
| WP4 INFO collection ETag / `action_code` enum | Informational |
| Additive WP2 enrichment provenance + audit vocabulary | NEW requirement → additive DATA-001-WP2 revision + P6-WP6 (INT-001 §33) |

## 5. Claim boundary

No production-readiness, compliance, legal-admissibility, efficacy or "SSRF / DNS rebinding impossible" claim is made.
Nothing has been network- or penetration-tested. Phase-3, Phase-4, `ENGINE_VERSION`, DATA-001, DATA-001-WP2, ADR-0011,
API-001, OAS-001, GATE-021, GATE-022 and the runtime/publication path are unchanged.

## 6. Decision

**P6-WP5 INTEGRATION CONTRACT APPROVED — REMOTE CI + MERGE PENDING.** ADR-0012 Accepted following independent review.
P6-WP5 is not yet formally closed (remote CI + merge outstanding); P6-WP6 not started.

## 7. Initial independent review (REQUEST_CHANGES) and corrections — historical record

| Finding | Correction |
|---|---|
| MEDIUM-1 — governed proxy final-hop assurance not explicit, not blocking, weakly encoded, IC-19 count-based, no targeted mutation | ADR-0012 §8 and INT-001 §17 require REQUIRED_AND_VERIFIED final-hop enforcement with scope equivalent to the direct connector and make unverified proxy egress DEPLOYMENT_BLOCKED / `POLICY_REJECTED` (`PROXY_ENFORCEMENT_UNVERIFIED`) with no fallback; machine contract `proxy.*` structured fields + failure condition + SC-16…SC-19; IC-19 rewritten as structural checks; 14 targeted negative mutations (NEG-IC-78…91) |
| LOW-1 — ADR-0012 Accepted before independent review | ADR-0012 returned to **Proposed** (existing index status value; a temporary "Proposed" index section, removed at acceptance — see §8); acceptance becomes effective only after independent review approval; IC-02/IC-40 check status consistency |
| INFO-1 — ADR embedded-IPv4 wording looser than the machine contract | ADR-0012 §7 now states IPv4-mapped / IPv4-embedding IPv6 forms are denied by default and allowed only by explicit governed policy when the embedded IPv4 is itself permitted |
| INFO-3 — local URL splitter could be mistaken for runtime parsing | INT-001 §36 states it is validator-only: not a production parser, not a security boundary, not reusable runtime code, not evidence of safe runtime parsing |
| Other LOW/INFO | Recorded by the reviewer; no change requested |

Provider `CLEAN` semantics are unchanged (provider assertion only — never TrustLens safe, legitimate, verified or
`NO_SCAM_PATTERN`).

All four corrected findings are **CLOSED**: MEDIUM-1, LOW-1, INFO-1, INFO-3.

## 8. Targeted independent re-review — APPROVE

| Item | Result |
|---|---|
| Counts | BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 1 / INFO 4 — **APPROVE** |
| Reviewer canonical validation | `run_all` PASS 27/27; `run_all --json` gate=PASS, validators_run=27, validators_failed=0; `ci_selftest` PASS 12/12; `ENGINE_VERSION = 1.0.0` |
| MEDIUM-1 | **CLOSED** — `proxy.final_hop_enforcement = REQUIRED_AND_VERIFIED`; unverified enforcement `DEPLOYMENT_BLOCKED`; outcome `POLICY_REJECTED`; `safe_error_category = PROXY_ENFORCEMENT_UNVERIFIED`; no fallback to trusting the proxy; no bypass of destination validation; enforcement scope equivalent to the direct-connector destination policy |
| IC-19 | Structural, no longer count-based: environment proxy inheritance disabled; governed proxy only; REQUIRED_AND_VERIFIED; governed verifiable evidence; DEPLOYMENT_BLOCKED when unverified; POLICY_REJECTED failure; equivalent denied-address scope incl. mixed-answer and metadata protection; DNS/redirect authorization not weakened; SEC-reference credentials; no fallback/bypass |
| Negative mutations | 91 total, all rejected; 14 proxy-targeted (NEG-IC-78…NEG-IC-91) |
| LOW-1 | **CLOSED** — ADR-0012 was held as Proposed while review was outstanding; acceptance bookkeeping promotes it to Accepted |
| INFO-1 | **CLOSED** — embedded-IPv4 IPv6 forms denied by default; allowed only by explicit governed policy and only when the embedded IPv4 is itself permitted |
| INFO-3 | **CLOSED** — validator URL splitter is validation-only: not a production parser, not a runtime security boundary, not reusable runtime code, not evidence of safe runtime parsing |

Carried (non-blocking):

| Item | Status / owner |
|---|---|
| LOW-2 — external-enrichment persistence follow-ups (INT-001 §33 additive columns, `safe_error_category` vocabulary, enrichment audit events) | OPEN / NON-BLOCKING — additive DATA-001-WP2 revision + P6-WP6 (WP2 not modified) |
| INFO-A — a builder summary referred to a loopback proxy scenario that does not exist | Informational; loopback enforcement is covered by the proxy enforcement scope |
| INFO-B — IC-19 checks uppercase proxy environment-variable names; `environment_proxy_inheritance = false` is the binding rule | Informational |
| INFO-C — IC-19 validates the `PROXY_ENFORCEMENT_UNVERIFIED` outcome/status but not separately its `safe_error_category` | Diagnostic only |
| INFO-D — present provider `CLEAN` as a provider assertion when `listEvaluationEnrichments` is activated; carried WP4 collection-ETag INFO and `action_code` enum INFO | Informational → P6-WP6 activation |

Provider `CLEAN` remains a provider assertion only — never TrustLens safe, `NO_SCAM_PATTERN`, legitimate or verified; no
direct provider-to-`DetectionResult` path exists.

Future ownership (not performed in P6-WP5): enrichment persistence additions, `safe_error_category` vocabulary and
integration audit-event persistence → additive DATA-001-WP2 revision + P6-WP6; `listEvaluationEnrichments` activation →
P6-WP6 + API-001/OAS-001 bookkeeping; provider policy publication workflow, connector/resolver/peer-binding
implementation and deployment security verification → P6-WP6 / Phase-9.
