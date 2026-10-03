# INT-001 — External enrichment / threat-intelligence integration contract

| Field | Value |
|---|---|
| Document ID | INT-001 |
| Version | 0.1 |
| Status | **P6-WP5 INTEGRATION CONTRACT APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING**; P6-WP5 not yet formally closed; not an implementation |
| Phase | Phase 6 — Data, API & Integration Contracts |
| Owner role | Integration Architect / Security Architect |
| Baseline | P6-WP4 merge `9fa022f74e1a4c76ab5875f8fe6715057fd5654c` (PR #29) |
| Machine contract | [`contracts/integrations/external-enrichment-v1.json`](../../contracts/integrations/external-enrichment-v1.json) (contract 0.1.0) + [`integration-contract.schema.json`](../../contracts/integrations/integration-contract.schema.json) |
| Validator | `knowledge/validation/validate_integration_contract.py` (IC-01…IC-51) + `contracts/integrations/fixtures/negative-mutations.json` |
| Decision record | [ADR-0012](../../adr/ADR-0012-threat-intelligence-adapter-architecture-provider-selection.md) (Accepted following independent P6-WP5 review) |
| Gate | [GATE-023](../00-program/GATE-023-phase-6-integration-contract.md) |
| Governing authority | DATA-001 §5.16/§20; DATA-001-WP2 (`external_enrichment_result`, RM-09); API-001 §22; OAS-001; ARCH-004 §8/E10; ADR-0007/0009/0010/0013/0016/0017; DET-001 |
| Last updated | 2026-10-03 |

## 1. Purpose and claim boundary

INT-001 defines the governed TrustLens boundary for optional external enrichment (FR-070/FR-071): what may leave
TrustLens, where it may go, who controls destinations, how provider responses are validated and recorded, what
failures mean, how caching, freshness, replay and re-analysis behave, and how SSRF, redirect abuse, DNS rebinding and
network pivoting are prevented **by contract**.

It is a contract only. It implements no connector, HTTP client, resolver, API endpoint, migration or provider SDK; it
selects no provider; it adds no Phase-3 rule or observation. The machine contract is validated offline (no DNS, no
socket, no HTTP, no API key). It prevents arbitrary outbound destination selection and requires destination
validation, peer binding and redirect revalidation; **implementation correctness remains to be verified during build
and security testing** (P6-WP6 / Phase-9). Nothing here claims that SSRF or DNS rebinding is impossible, that any
provider is trustworthy, that the system is production-ready, legally compliant or more accurate. G-09 remains
**OPEN** — no efficacy claim is made.

## 2. Authoritative inputs and non-duplication

INT-001 reuses, and does not redefine:

| Input | What INT-001 takes from it |
|---|---|
| DATA-001 §5.16 | `ExternalEnrichmentResult` logical model: advisory, untrusted, `C4` queried value / `C2` status; absence or failure never `CLEAN`; never sets a `DetectionResult`; replay never re-queries |
| DATA-001-WP2 `external_enrichment_result` | Physical row and vocabularies `enrichment_status`, `reputation_result`, `allowlist_result`, `domain_brand_match`; `consumed_in_governed_artifact = false`; RM-09 (no enrichment consumed) |
| url-observation schema | Indicator authority (`normalized_url`, `structural.hostname`, `structural.registered_domain`) and the reserved `assessments` vocabulary |
| API-001 §22 / OAS-001 | Reserved `listEvaluationEnrichments` (`FUTURE_INT_001`) and `EnrichmentView`; AC-11 / OA-24 no URL fetch |
| ARCH-004 §8 | ZONE 6 deny-by-default egress; §8.4 submitted URL never a fetch target; NFR-006 TLS posture |
| ADR-0007 / AI-001 | AI optional, default-OFF, non-authoritative; never sets a decision field |
| ADR-0017 | Audit vs telemetry separation; vendor-neutral observability |

INT-001 does **not** duplicate persistence rows (§33 lists only *additive* requirements) and does not change API-001,
OAS-001, DATA-001, DATA-001-WP2, ADR-0011, Phase-3, Phase-4 or the runtime/publication path.

## 3. Indicator lookup versus content retrieval

| Capability | Meaning | P6-WP5 |
|---|---|---|
| **INDICATOR LOOKUP** | Send a normalized indicator *value* as data to a predeclared operation of an approved provider and record the normalized answer | **Permitted** |
| **CONTENT RETRIEVAL** | Connect to, resolve, download, render, follow redirects of or execute an indicator's own destination | **Not permitted** |

If a user submits `https://suspicious.example/path`, TrustLens may normalize it, digest/reference it and send the
string as lookup data to an approved provider API. TrustLens may **not** connect to `suspicious.example`, resolve it,
download the page, follow its redirects or execute its scripts. A future safe-retrieval capability would need its own
governed contract and review. Inbound webhooks are **out of scope** (no accepted Phase-6 plan assigns them here).

There is no generic network primitive — no `fetch(url)`, `http_request(url)`, `download_url`, `proxy_request`,
`open_url` or generic webhook fetch — selectable by users, analysts, AI or providers. Adapter operations are closed and
predeclared in provider policy.

## 4. Integration objects

| Object | Store | Role | Key content |
|---|---|---|---|
| `ExternalEnrichmentRequest` | `MEM` | Transient adapter input | request ref, external correlation value, provider ref + operation, pinned policy ref/version, indicator type, normalized indicator value (`C4`) and digest ref, internal evaluation ref (never outbound), purpose, requested_at. **No** destination URL/host, scheme, port, method, headers, proxy, TLS switch, credential, raw template or redirect policy |
| `ExternalEnrichmentResult` | `OPS` | Advisory record | The accepted WP2 `external_enrichment_result` row (not redefined) + additive provenance (§24, §33) |
| `ExternalProviderIdentity` | `OPS` | Opaque provider identity | provider ref, provider category (§6), authentication-method ref; no vendor named |
| `ExternalProviderPolicy` | Governed configuration | Destination authority | §8 binding fields; versioned, immutable per version; no credential value |
| `ExternalProviderResponseArtifact` | `OPS` (+`ECS` only by governed raw-content policy) | What TrustLens accepted | artifact ref + digest, provider/policy/parser identity, observed_at, normalized payload, raw-content policy ref |
| `FreshnessMetadata` | `OPS` | Technical recency | observed_at, freshness state, freshness policy ref, cache_used |
| `FailureOutcome` | `OPS` | Technical outcome | lookup outcome, WP2 status, safe error category |
| `ReplayReference` | `OPS` | Replay pin | enrichment id, artifact digest, policy/adapter/parser versions |

## 5. Indicator types

Only indicator kinds already defined by accepted authority are permitted:

| Indicator type | Authority | Class | Outbound form |
|---|---|---|---|
| `URL` | url-observation `normalized_url` | `C4` | normalized URL without userinfo or fragment; query only where the provider policy sets `url_query_transmission = PERMITTED` |
| `HOSTNAME` | url-observation `structural.hostname` | `C4` | canonical hostname string (data, never a destination) |
| `REGISTERED_DOMAIN` | url-observation `structural.registered_domain` | `C4` | canonical eTLD+1 string (data, never a destination) |

Not permitted (no accepted authority): phone, UPI, bank-account, email, device-fingerprint, file-hash and IP
reputation. Adding any requires a governed contract change.

## 6. Provider categories and normalization

| Provider category (`EnrichmentView.provider_category`) | Normalizes into (existing vocabulary) |
|---|---|
| `REPUTATION_LOOKUP` | `reputation_result` |
| `ALLOWLIST_LOOKUP` | `allowlist_result` |
| `BRAND_DOMAIN_LOOKUP` | `domain_matches_claimed_brand` |

Each parser version carries a governed normalization map from the provider's documented answer to these values.
Unmapped or unknown provider values are `INVALID_RESPONSE`.

## 7. Egress and destination authority

Outbound integration is **DENY BY DEFAULT**. Only explicitly governed provider destinations may be contacted, and
destination policy is configuration authority. A destination must **never** come from: an end-user request, evidence
content, AI output, a model tool call, a provider response, or an HTTP redirect without revalidation. Egress denials are
audited (`EGRESS_DENIED`).

## 8. Provider endpoint allowlist (policy binding)

Every `ExternalProviderPolicy` version binds at minimum: provider identity; scheme (`https`); host (exact, or a governed
subdomain rule); allowed port; allowed path prefix and provider operation; allowed method; expected response media type;
authentication-method reference; credential reference (never a value); response parser/schema version; redirect policy
(`DO_NOT_FOLLOW` default or `REVALIDATE_WITHIN_PROVIDER_ALLOWLIST`); URL-query transmission flag; cache permission;
freshness-policy reference; retry-safety declaration; enabled flag. No credential value belongs in this registry.

## 9. Provider policy authority and versioning

Provider policy is changed only by **governed operator / configuration authority**. ANALYST, REVIEWER, end users, AI,
provider responses and the adapter runtime cannot change it. Each version is immutable and identifiable; the version
used is recorded on every enrichment and pinned for replay — an unpinned "latest provider config" is never used for
historical reproduction. Storage is not fixed (Git is not mandated) but the authoritative configuration must be
reproducible. The publication workflow is assigned to P6-WP6 / Phase-9. No tenant-specific provider configuration
exists (ASM-002).

## 10. Request construction and header policy

Adapters own request construction. User input may populate **only** the indicator value, encoded by the adapter as
data. User input never controls destination URL or host, scheme, port, path, HTTP method, proxy, `Host`,
`Authorization`, `Cookie`, arbitrary headers, redirect behaviour, TLS verification, provider credential or a raw request
template.

User-supplied network headers are rejected. `Host`, `Authorization`, `Proxy-Authorization`, `Cookie`, `Connection`,
`Transfer-Encoding`, `Forwarded` and `X-Forwarded-*` exist only as adapter-generated governed values. CR/LF header
injection is rejected.

## 11. Transport, HTTPS and schemes

Only `https` is permitted, with certificate verification and hostname verification. There is no `verify=false`,
insecure bypass, plaintext fallback, HTTP downgrade or self-signed bypass; an enterprise trust store is allowed only by
separate governance. The TLS protocol posture is inherited from NFR-006 / ARCH-004 §7 / ADR-0016 (TLS 1.3 where
boundaries apply); INT-001 adds no new minimum. `http`, `file`, `ftp`, `gopher`, `data`, `javascript`, `unix` socket
transports and custom URI schemes are rejected. There is no generic URI dispatcher.

## 12. Hostname canonicalization and IP literals

| Aspect | Rule |
|---|---|
| Case | lowercase before comparison |
| Trailing dot | strip a single trailing dot, then compare |
| IDNA | compare canonical A-labels (punycode) |
| Userinfo | reject |
| Port | explicit exact match to policy |
| Bracketed IPv6 | parse as an IP literal |
| Encoded delimiters | reject |
| Ambiguous or unparseable | reject |
| Allowlist comparison | exact host identity or governed subdomain rule; **never** substring (`"trusted.example" in host` is forbidden) |
| IP-literal destinations | rejected unless a governed policy explicitly requires one; a user can never select an IP destination |
| Alternate IP spellings | integer, hex, octal and short forms are rejected; validation uses parsed IP semantics |

## 13. DNS rebinding and resolve-time TOCTOU (closes WP4 LOW-3 at contract level)

"Resolve, check the IP, then let the HTTP client resolve again" is **not sufficient**. Every adapter must implement a
strategy equivalent to:

1. parse and canonicalize the governed provider destination;
2. resolve through the governed resolver;
3. validate every resolved address (including alias/CNAME results) on parsed IP semantics;
4. reject denied address space;
5. connect only to a validated address from that resolution decision;
6. preserve TLS SNI and hostname verification for the original approved hostname;
7. verify that the actually connected peer address is permitted;
8. repeat validation for each new connection (including every retry);
9. repeat validation for every redirect target.

Destination validation and the actual connection target can never be separated by an uncontrolled second resolution.
No Python HTTP library is mandated; the invariant is what matters. WP4 LOW-3 is therefore **addressed at contract
level; implementation verification remains OPEN** (P6-WP6 / security testing).

## 14. Mixed DNS answers

If **any** candidate answer is forbidden or ambiguous under policy, the lookup is **rejected** (`POLICY_REJECTED`,
`DESTINATION_ADDRESS_REJECTION`). TrustLens never lets a client choose among mixed answers and never relies on answer
ordering: an attacker who can return one public and one internal address must not be able to win a race or an ordering
choice.

## 15. Forbidden destination classes

Validation operates on parsed IP semantics, not string lists such as "localhost". Ranges below are the standard IANA
special-purpose allocations (not tuning values).

| Class | IPv4 | IPv6 |
|---|---|---|
| Loopback | `127.0.0.0/8` | `::1/128` |
| Private (RFC 1918) | `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` | — |
| Link-local | `169.254.0.0/16` | `fe80::/10` |
| Multicast | `224.0.0.0/4` | `ff00::/8` |
| Unspecified / this network | `0.0.0.0/8` | `::/128` |
| Reserved / non-routable | `100.64.0.0/10`, `192.0.0.0/24`, documentation nets, `198.18.0.0/15`, `240.0.0.0/4`, broadcast | `100::/64`, `2001:db8::/32` |
| IPv6 unique-local | — | `fc00::/7` |
| IPv4-mapped / IPv4-embedding IPv6 | — | `::ffff:0:0/96`, `::/96`, `64:ff9b::/96`, `2002::/16`, `2001::/32` — embedded IPv4 always evaluated against every IPv4 class |
| Instance metadata | `169.254.169.254/32` + any deployment-declared metadata address | — |
| Local host aliases | denied by the address they resolve to | denied by the address they resolve to |

Any address the IANA registries do not mark globally reachable is denied even if not enumerated; an unclassifiable
address is rejected.

## 16. Redirect policy

Redirects never inherit trust. The default provider policy is `DO_NOT_FOLLOW`. A policy may opt into
`REVALIDATE_WITHIN_PROVIDER_ALLOWLIST`; each hop is then a new destination authorization that revalidates scheme, host,
port, path/provider scope, DNS resolution, resolved addresses and the connected peer. HTTPS → HTTP is rejected; a hop
outside the provider allowlist or to private/internal space is rejected (`POLICY_REJECTED`,
`REDIRECT_POLICY_REJECTION`); credentials are forwarded only to the same governed destination binding. The redirect
count is bounded by a **finite implementation-configured maximum — NOT YET SPECIFIED** (owner: P6-WP6 / implementation
security profile).

Provider-controlled redirect attacks modelled in the machine contract (`conformance_scenarios`) and evaluated offline:
approved provider → 302 → `127.0.0.1`; → `169.254.169.254`; → an RFC 1918 address; → an unapproved Internet host;
→ HTTPS-to-HTTP downgrade. All must yield `POLICY_REJECTED`.

## 17. Governed egress proxy

`HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY` and their lowercase forms are never inherited automatically.
Configuring a proxy does **not** make it trusted. An enterprise egress proxy may be used **only** when all of these hold:

| # | Requirement | Machine contract (`proxy.*`) |
|---|---|---|
| P-1 | Declared in governed configuration — never user, evidence, AI or provider input | `governed_proxy = OPTIONAL_GOVERNED_ONLY` |
| P-2 | Adapter validates the final provider destination before requesting a tunnel | `adapter_destination_validation_before_tunnel = REQUIRED` |
| P-3 | TLS end-to-end to the provider with certificate and hostname verification | `end_to_end_tls_to_provider = true` |
| P-4 | **Final-hop enforcement required and verified** by governed, verifiable evidence | `final_hop_enforcement = REQUIRED_AND_VERIFIED`; `enforcement_evidence = GOVERNED_VERIFIABLE_EVIDENCE_REQUIRED` |
| P-5 | Enforcement scope equivalent to the direct connector: every forbidden class in §15 (loopback, RFC1918, link-local, multicast, unspecified, reserved, IPv6 ULA and link-local, IPv4-mapped / IPv4-embedding IPv6, instance metadata, local host aliases) plus mixed-answer rejection (§14), alias/CNAME validation (§13 step 3) and final connected-peer enforcement where applicable (§13 step 7) | `enforcement_scope_equivalent_to = DIRECT_CONNECTOR_DENIED_ADDRESS_AND_CONNECTION_BINDING_POLICY`; `enforcement_scope` |
| P-6 | The proxy never weakens DNS or redirect authorization | `may_weaken_dns_or_redirect_authorization = false` |
| P-7 | Proxy credentials are `SEC` references only | `proxy_credentials = SEC_REFERENCE_ONLY` |

The adapter cannot observe the proxy's own resolution, so P-4/P-5 evidence stands in for the adapter's own §13 check on
the final hop.

**Deployment blocker.** If governed, verifiable evidence of equivalent final-hop enforcement is absent, proxy-based
enrichment **must not run**: proxy egress is `DEPLOYMENT_BLOCKED` (`unverified_enforcement`) and every proxy-based lookup
is `POLICY_REJECTED` with `safe_error_category = PROXY_ENFORCEMENT_UNVERIFIED` (`unverified_enforcement_outcome`). There
is no fallback to trusting the proxy and no bypass of destination validation (`unverified_fallback = NONE`). A proxy is
never an SSRF escape hatch. What counts as verification evidence, and who signs it off, is an implementation-time
governance deliverable (P6-WP6 / deployment security review); P6-WP5 defines only the requirement.

## 18. Credentials

Provider credentials come only from approved secret/key management (`SEC`, `C7`) and are used by reference. They are
never stored in contract JSON or provider-policy records, persisted as enrichment content, included in audit events,
logged, emitted to telemetry, returned through APIs, made available to AI prompts, or placed in URLs. Rotation period:
NOT YET SPECIFIED. A credential-reference failure yields `UNAVAILABLE` / `CREDENTIAL_UNAVAILABLE` and is audited.

## 19. Least data outbound and correlation

Only the minimum normalized indicator value, an adapter-generated external correlation value and governed
authentication leave TrustLens. Never sent to a generic threat-intelligence provider in v1: raw message bodies,
surrounding message text, screenshots, documents, evidence bytes, full case files, user identity, case notes,
adjudication rationale, internal database identifiers, `DetectionResult`s. URL userinfo and fragments are never sent;
the query component is sent only where the provider policy permits it (default not sent). A future provider needing raw
evidence requires an explicit governed contract change plus privacy/security review.

Outbound correlation uses a generated value suitable for external sharing; database UUIDs, case identifiers and internal
topology are not sent.

## 20. Provider response boundary, size and timeouts

Provider responses are **untrusted external input**, even from an allowlisted provider. Adapters validate HTTP status,
media type, decoded size, schema shape, required fields, enum values, timestamp format, provider identity and
parser/schema version. They never deserialize arbitrary objects and never execute provider-returned content; an unknown
enum value is `INVALID_RESPONSE`.

| Bound | Requirement | Value | Owner |
|---|---|---|---|
| Wire bytes | finite configured maximum | NOT YET SPECIFIED | P6-WP6 / Sponsor / implementation security profile |
| Decoded bytes | finite configured maximum; streaming decompression aborts on the bound | NOT YET SPECIFIED | P6-WP6 / Sponsor / implementation security profile |
| Connect timeout | finite | NOT YET SPECIFIED | P6-WP6 / implementation security profile |
| Read timeout | finite | NOT YET SPECIFIED | P6-WP6 / implementation security profile |
| Overall deadline | finite; infinite waiting forbidden | NOT YET SPECIFIED | P6-WP6 / implementation security profile |

## 21. Retries, backoff, rate limiting and circuit breaking

- **Retries** are bounded (maximum attempts NOT YET SPECIFIED) and only for lookups the provider policy declares
  retry-safe and idempotent; a non-idempotent call is never blindly retried. Every attempt repeats §13 validation.
- **Backoff** is bounded and jitter-capable; values NOT YET SPECIFIED.
- **Rate limiting:** HTTP 429 means *provider unavailable / rate-limited for this lookup* → `UNAVAILABLE` /
  `RATE_LIMITED`, never "indicator safe". `Retry-After` is honoured only within the bounded policy. No quota is invented.
- **Circuit breaker (conceptual):** `CLOSED` / `OPEN` / `HALF_OPEN`; an open circuit yields `UNAVAILABLE` /
  `PROVIDER_UNAVAILABLE`. Thresholds and windows NOT YET SPECIFIED (P6-WP6).

## 22. Integration outcomes and failure semantics

Outcomes are **integration technical outcomes, not scam classifications**.

| Outcome | WP2 `status` | `reputation_result` | `allowlist_result` | `domain_matches_claimed_brand` |
|---|---|---|---|---|
| `FOUND` | `SUCCEEDED` | `MALICIOUS`, `SUSPICIOUS`, `CLEAN`, `UNKNOWN` (governed normalization) | any | any |
| `NOT_FOUND` | `SUCCEEDED` | `UNKNOWN` only | `NOT_ALLOWLISTED` or `NOT_EVALUATED` | `UNKNOWN` |
| `UNAVAILABLE` | `FAILED` or `TIMED_OUT` | `NOT_EVALUATED` | `NOT_EVALUATED` | `UNKNOWN` |
| `POLICY_REJECTED` | `REJECTED` | `NOT_EVALUATED` | `NOT_EVALUATED` | `UNKNOWN` |
| `INVALID_RESPONSE` | `FAILED` | `NOT_EVALUATED` | `NOT_EVALUATED` | `UNKNOWN` |
| (not attempted) | `NOT_EVALUATED` | `NOT_EVALUATED` | `NOT_EVALUATED` | `UNKNOWN` |

`CLEAN` under `FOUND` means only "the provider asserted no adverse reputation at `observed_at`" — an advisory provider
assertion, never TrustLens "safe".

| Condition | Outcome | Status | `safe_error_category` | Retry |
|---|---|---|---|---|
| DNS failure | `UNAVAILABLE` | `FAILED` | `DNS_FAILURE` | governed, bounded |
| Connection failure | `UNAVAILABLE` | `FAILED` | `CONNECTION_FAILURE` | governed, bounded |
| TLS failure | `UNAVAILABLE` | `FAILED` | `TLS_FAILURE` | none (security signal) |
| Timeout | `UNAVAILABLE` | `TIMED_OUT` | `TIMEOUT` | governed, bounded |
| Provider 4xx | `UNAVAILABLE` | `FAILED` | `PROVIDER_CLIENT_ERROR` | none (only a parser-documented "no entry" answer is `NOT_FOUND`) |
| Provider 5xx | `UNAVAILABLE` | `FAILED` | `PROVIDER_SERVER_ERROR` | governed, bounded |
| Rate limit (429) | `UNAVAILABLE` | `FAILED` | `RATE_LIMITED` | governed, bounded |
| Invalid content type | `INVALID_RESPONSE` | `FAILED` | `INVALID_CONTENT_TYPE` | none |
| Oversized response | `INVALID_RESPONSE` | `FAILED` | `OVERSIZED_RESPONSE` | none |
| Decompression limit | `INVALID_RESPONSE` | `FAILED` | `DECOMPRESSION_LIMIT_EXCEEDED` | none |
| Schema-invalid response | `INVALID_RESPONSE` | `FAILED` | `SCHEMA_INVALID_RESPONSE` | none |
| Policy rejection | `POLICY_REJECTED` | `REJECTED` | `POLICY_REJECTION` | none |
| Redirect policy rejection | `POLICY_REJECTED` | `REJECTED` | `REDIRECT_POLICY_REJECTION` | none |
| DNS / private-address rejection | `POLICY_REJECTED` | `REJECTED` | `DESTINATION_ADDRESS_REJECTION` | none |
| Governed proxy without verified final-hop enforcement | `POLICY_REJECTED` | `REJECTED` | `PROXY_ENFORCEMENT_UNVERIFIED` | none (deployment-blocked) |
| Credential unavailable | `UNAVAILABLE` | `FAILED` | `CREDENTIAL_UNAVAILABLE` | none |
| Provider unavailable (disabled / circuit open) | `UNAVAILABLE` | `FAILED` | `PROVIDER_UNAVAILABLE` | none |

No external lookup failure collapses into `NO_SCAM_PATTERN`; no successful enrichment is fabricated.

## 23. External result is not a TrustLens verdict

A provider response is an **external assertion / enrichment artifact**. It never directly becomes
`SCAM_PATTERN_DETECTED`, `SCAM_PATTERN_SUSPECTED`, `NO_SCAM_PATTERN`, safe, legitimate, verified, a fraud probability,
TrustLens confidence, severity or risk. **`NOT_FOUND` is not safe**: "not found", "unknown", "no match" or "no reputation
entry" never means safe, legitimate, verified or no scam.

No provider may set `DetectionResult`, classification, severity, risk, confidence, governing rule or recommended
action, nor override or suppress a rule. P6-WP5 **does not introduce a new Phase-3 rule or observation**. External
enrichment could affect deterministic decisions only after a separately governed change adds validated normalization,
a governed mapping into accepted rule/observation semantics, and pinning inside a new `GovernedInputArtifact`. Until
then `consumed_in_governed_artifact = false` and RM-09 asserts no enrichment is consumed. Phase-3 remains the sole
decision authority; `ENGINE_VERSION = 1.0.0` is unchanged. No scam probability, score, likelihood or ranking field is
introduced anywhere.

## 24. Provenance

| Question | Field | Persistence |
|---|---|---|
| Which provider policy? | `provider_policy_ref` | additive WP2 |
| Which policy version governed the call? | `provider_policy_version` | additive WP2 |
| Which provider identity? | `provider_ref` | WP2 `provider_ref` |
| Which adapter version? | `adapter_version` | WP2 `adapter_version` |
| Which parser/schema version? | `parser_schema_version` | additive WP2 |
| Which INT-001 version? | `integration_contract_version` | WP2 `integration_contract_version` |
| What indicator type? | `indicator_type` | additive WP2 |
| What normalized indicator? | `normalized_indicator_ref` (digest/reference) | additive WP2 |
| Request identity | `request_ref` | WP2 `request_ref` |
| When did the request begin? | `requested_at` | WP2 `requested_at` |
| When was the response observed? | `observed_at` | WP2 `responded_at` |
| Technical outcome | `lookup_outcome` | additive WP2 |
| Persisted status | `status` | WP2 `status` |
| Provider response status/category | `provider_response_category` | additive WP2 |
| Safe error category | `safe_error_category` | WP2 `safe_error_category` |
| Freshness state | `freshness_state` | additive WP2 |
| Response artifact identity/digest | `response_artifact_digest` | additive WP2 |
| Was cache used? | `cache_used` | additive WP2 |

The raw indicator value is not required in telemetry; a digest/reference suffices.

## 25. Response artifact and provider authenticity

TrustLens preserves an immutable governed representation of each accepted provider result for audit, later explanation
and replay. Its digest follows the existing TrustLens convention (SHA-256, 64-hex, over `TRUSTLENS_CANONICAL_JSON_V1`).
The artifact proves **what TrustLens accepted and recorded** from that interaction — not provider truth. Hash integrity
is not provider authenticity.

TLS authenticates the connection endpoint under the Web PKI model. A provider response is **not** treated as a
cryptographically signed assertion unless the provider supplies a signature and TrustLens verifies it; no such
mechanism is specified in v1. Even an allowlisted provider may be compromised or wrong, so its output stays
provenance-carrying, schema-validated external information — trust is not binary.

## 26. Cache, case isolation and freshness

- Caching is allowed only where the provider policy permits it.
- Cache key: provider ref, provider operation, indicator type, normalized indicator ref, provider policy version, parser
  schema version — preventing semantic collisions.
- Every entry retains `observed_at`, freshness state, freshness-policy reference and source provenance; cache use is
  recorded on the enrichment. TTL: NOT YET SPECIFIED (governed provider policy).
- **Case isolation:** cache entries carry no case identity or evidence. Reusing a public-indicator result across cases
  never leaks one case into another; a provider-response artifact may be shared only where domain/persistence rules
  permit safe deduplication; case linkage stays a separate per-evaluation record. WP2 storage is not redesigned here.
- **Freshness** states `FRESH` / `STALE` / `UNKNOWN` (`UNKNOWN` when expiry semantics are absent, unverifiable or
  undeclared). Freshness is not confidence and not scam risk. Periods: NOT YET SPECIFIED (governed provider policy).
  Stale data never silently appears fresh.

## 27. Historical replay versus re-analysis

| Aspect | Historical replay | Re-analysis |
|---|---|---|
| Provider call | **Never** | Permitted under current policy |
| Material used | Exact retained enrichment artifact + policy/adapter/parser identity pinned to the evaluation | New lookup (or a governed cache entry with recorded freshness) |
| Refresh / replace stale / newest response / latest policy | Never | Current policy governs |
| AI substitution | Never | Never as a provider substitute |
| Missing material | **Replay unavailable** — no approximation | Not applicable |
| Effect on history | None (verification only) | New evaluation + new enrichment record; historical enrichment never overwritten |

Under current contracts no enrichment is consumed (RM-09), so replay of current results never needs enrichment
material. Governed deletion of enrichment material can make exact replay or regeneration unavailable (§32).

## 28. AI boundary

AI cannot control a provider destination, supply URL/host network targets, inject provider credentials, mutate provider
policy or bypass SSRF policy. If future AI tooling requests enrichment it may select only a predeclared integration
operation with a structured indicator input; the governed connector remains authoritative for destination selection.
Phase-4 AI stays optional, default-OFF and non-authoritative (ADR-0007).

## 29. Threat model

| # | Threat | Vector | Control | Residual / owner |
|---|---|---|---|---|
| T-01 | SSRF | Submitted URL or parameter becomes a server-side destination | Indicator lookup only; destinations from governed policy only; no generic fetch | Implementation verification — P6-WP6 |
| T-02 | DNS rebinding | Approved name re-resolves to internal space after validation | Connect only to a validated address from the same decision; peer verification | Resolver/client integration — P6-WP6 |
| T-03 | DNS TOCTOU | Client resolves separately from the validator | No uncontrolled second resolution; per-connection revalidation | As T-02 |
| T-04 | Redirect to private host | Provider 30x to loopback/metadata/RFC1918 | Default do-not-follow; each hop revalidated; private targets rejected | Hop bound value — P6-WP6 |
| T-05 | IPv6 bypass | ULA, link-local, NAT64, 6to4, Teredo, mapped forms | Parsed IPv6 classes; embedded IPv4 evaluated | New IANA allocations — governed review |
| T-06 | IP textual-encoding bypass | Integer/hex/octal/short IPv4 spellings | IP literals rejected by default; alternate encodings rejected | — |
| T-07 | Userinfo / host parser confusion | `approved@evil`, encoded delimiters, suffix tricks | Canonicalization; userinfo rejected; exact host or governed subdomain rule | Parser differential — implementation testing |
| T-08 | CNAME / alias to internal space | Approved name aliases to internal address | Validate final addresses of alias chains | As T-02 |
| T-09 | Proxy bypass | Ambient `HTTP_PROXY`, or a proxy resolving names into internal space | Env proxies ignored; governed proxy only with REQUIRED_AND_VERIFIED final-hop enforcement of the full connector scope; otherwise DEPLOYMENT_BLOCKED / `POLICY_REJECTED` | Quality of the verification evidence — P6-WP6 / deployment security review |
| T-10 | Credential leakage | Key in URL, logs, audit, API, AI prompt | `SEC` references only; logging/telemetry exclusions | Secret-store selection — P6-WP6 |
| T-11 | Header injection | User-supplied `Host`/`Authorization`/CRLF | Adapter-generated headers only; user headers and CRLF rejected | — |
| T-12 | Oversized response | Large body exhausts memory | Finite wire bound | Value NOT YET SPECIFIED |
| T-13 | Decompression bomb | Small compressed body expands hugely | Finite decoded bound; streaming abort | Value NOT YET SPECIFIED |
| T-14 | Schema poisoning | Unexpected types/enums/fields | Strict schema + enum validation; unknown → `INVALID_RESPONSE`; no arbitrary deserialization | Parser quality — implementation |
| T-15 | Provider compromise | Allowlisted provider returns malicious data | Content untrusted; advisory only; never a verdict; provenance retained | Cannot be eliminated |
| T-16 | Stale cache | Old reputation shown as current | Explicit freshness; stale never fresh; observed_at retained | Periods NOT YET SPECIFIED |
| T-17 | Rate-limit ambiguity | 429 read as "nothing found" | 429 → `UNAVAILABLE`, never safe | — |
| T-18 | Provider outage | Provider down or hanging | Finite timeouts; bounded retries; circuit breaker; deterministic core unaffected (FR-071) | Thresholds — P6-WP6 |
| T-19 | Replay drift | Replay sees newer provider data | No refetch; pinned artifact and policy; missing → unavailable | — |
| T-20 | AI tool misuse | Model supplies URL/host/credential | AI controls no destination, credential or policy | Future AI tooling needs its own review |
| T-21 | Cross-case cache leakage | Shared cache carries case data | Cache keyed by indicator/provider only; no case identity/evidence; linkage per evaluation | Dedup rules — additive WP2 / P6-WP6 |

## 30. Audit, telemetry and logging

Governed audit and observability telemetry stay separate (ADR-0017).

| Audit concept | WP2 `audit_event_type` | Status |
|---|---|---|
| Enrichment requested | — | additive WP2 vocabulary required |
| Provider policy selected | — | additive WP2 vocabulary required |
| Policy rejection | `EGRESS_DENIED` | existing |
| SSRF / destination rejection | `EGRESS_DENIED` | existing |
| Enrichment accepted | — | additive WP2 vocabulary required |
| Credential-reference failure | — | additive WP2 vocabulary required |

Audit excludes credential values, authorization headers, raw evidence and raw provider bodies. Telemetry may record
latency, outcome category, adapter health and circuit state only (`C8`); never credentials, authorization headers, raw
`C4` evidence, raw indicator values or full submitted URLs. Logs never contain API keys, authorization headers, raw
provider credentials, raw evidence or full sensitive submitted content; they use bounded, opaque identifiers.

## 31. Privacy classification

| Datum | Class (DATA-001) |
|---|---|
| Outbound indicator value | `C4` |
| Provider response content | `C4` |
| Provenance metadata | `C2` |
| Provider policy | `C2` |
| Credentials | `C7` (`SEC` only) |
| Audit records | `C6` |
| Telemetry | `C8` |

No legal-compliance claim is made.

## 32. Deletion and retention

OI-05 remains **OPEN**: no retention duration is defined. Enrichment artifacts containing queried values or retained
provider content participate in the eventual deletion / classification graph (DATA-001: delete with evaluation or
evidence). Governed deletion can make exact replay and regeneration unavailable; this is acknowledged, not
approximated. Persistence implementation: P6-WP6 / additive WP2 revision.

## 33. Additive persistence requirements (for P6-WP6; WP2 not modified)

The accepted `external_enrichment_result` row lacks: `indicator_type`, `normalized_indicator_ref`, `lookup_outcome`,
`provider_response_category`, `freshness_state`, `cache_used`, `provider_policy_ref`, `provider_policy_version`,
`parser_schema_version`, `response_artifact_digest`; a CHECK vocabulary for `safe_error_category` (§22); and enrichment
`audit_event_type` values (§30). These are **additive** requirements for a DATA-001-WP2 revision and P6-WP6. They do not
contradict WP2 (which already anticipates INT-001 via `integration_contract_version` and
`raw_provider_content_policy_ref`), so no accepted artifact is changed in P6-WP5.

## 34. API surface

No public endpoint is added. API-001 already reserves `GET /api/v1/evaluations/{evaluation_id}/enrichments`
(`listEvaluationEnrichments`, `FUTURE_INT_001`). It stays inactive until an implementation exists (P6-WP6) and is then
activated through governed API-001 / OAS-001 bookkeeping. `EnrichmentView` maps as: `enrichment_id` ←
`external_enrichment_result_id`; `provider_category` ← provider identity category (§6); `status` ← WP2 `status`;
`reputation_result` ← WP2 `reputation_result`; `observed_at` ← WP2 `responded_at`; `advisory` = `true`. The OpenAPI/API
freeze is respected: `api-v1.json`, `openapi-v1.json`, API-001, OAS-001, GATE-021 and GATE-022 are unchanged.

## 35. Tenancy

ASM-002 remains **UNCONFIRMED / PROVISIONAL**. No `tenant_id`, `X-Tenant`, tenant routing or tenant-specific provider
configuration is introduced.

## 36. Offline validation

Canonical CI stays offline: no real provider, DNS lookup, HTTP request, Internet access or API key. Validation uses the
static contract, its schema, negative mutations and fictional provider artifacts under a reserved `.example` name.
`validate_integration_contract.py` checks the contract against its schema, WP2, the API catalog/OpenAPI, the
url-observation schema, ADR-0012, this document and GATE-023, and replays the conformance scenarios through a reference
decision model driven by the contract's own policy values (standard-library parsing only). It proves contract coherence,
not connector correctness.

The validator's small local URL splitter (`_split_url`) exists **only** for static contract validation of the fictional
conformance scenarios. It is **not** a production URL parser, **not** a security-boundary implementation, **not**
reusable runtime parsing code, and **not** evidence that runtime parsing is safe. The runtime implementation must use a
security-reviewed parser consistent with the ADR-0012 invariants (§12 canonicalization, §13 binding); no runtime parser
is added in P6-WP5.

## 37. Traceability matrices

### A. Threat → control

| Threat | Control (section) |
|---|---|
| SSRF | §3, §7, §10 |
| DNS rebinding / TOCTOU | §13 |
| Redirect to private host | §16 |
| IPv6 / encoding / parser bypass | §12, §15 |
| CNAME to internal | §13 step 3 |
| Proxy bypass | §17 |
| Credential leakage | §18, §30 |
| Header injection | §10 |
| Oversized / decompression bomb | §20 |
| Schema poisoning / provider compromise | §20, §25 |
| Stale cache / cross-case leakage | §26 |
| Rate-limit ambiguity / outage | §21, §22 |
| Replay drift | §27 |
| AI tool misuse | §28 |

### B. Outbound datum → allowed destination / use

| Datum | Allowed destination | Use |
|---|---|---|
| Normalized indicator value (`C4`) | Approved provider operation in pinned policy | Lookup data only |
| External correlation value | Same | Request correlation |
| Governed authentication | Same, adapter-generated header from `SEC` reference | Provider authentication |
| Raw evidence, bodies, screenshots, documents, case files, identity, notes, rationale, internal IDs, results | **None** | Never outbound |

### C. Provider response → normalized integration outcome

| Provider response | Outcome |
|---|---|
| Valid, documented answer with an entry | `FOUND` |
| Valid, documented "no entry / unknown / no match" answer | `NOT_FOUND` |
| Network, TLS, timeout, 4xx (other than documented no-entry), 5xx, 429, credential, circuit open | `UNAVAILABLE` |
| Wrong media type, oversized, decompression limit, schema/enum/timestamp/identity/parser failure | `INVALID_RESPONSE` |
| Egress, destination, mixed-answer, redirect or minimization refusal | `POLICY_REJECTED` |

### D. Integration outcome → allowed TrustLens meaning

| Outcome | Allowed meaning | Never means |
|---|---|---|
| `FOUND` | Advisory provider assertion (normalized), with provenance | A TrustLens verdict, safe, verified, a score |
| `NOT_FOUND` | Provider had no entry (`UNKNOWN`) | Safe, legitimate, verified, no scam |
| `UNAVAILABLE` | Lookup could not be completed (`NOT_EVALUATED`) | Safe or clean |
| `POLICY_REJECTED` | TrustLens refused the call (`NOT_EVALUATED`) | Safe or clean |
| `INVALID_RESPONSE` | Response failed validation (`NOT_EVALUATED`) | Safe or clean |

### E. Network phase → validation requirement

| Phase | Requirement |
|---|---|
| Destination selection | Pinned governed policy only |
| Parse / canonicalize | §12 rules; reject ambiguous |
| Resolve | Governed resolver |
| Validate | Every answer, parsed IP semantics, alias finals; mixed → reject |
| Connect | Only a validated address from the same decision; governed proxy only with verified equivalent final-hop enforcement (else deployment-blocked) |
| TLS | SNI + certificate + hostname for the approved name |
| Peer check | Connected peer address permitted |
| Request | Adapter-built; restricted headers adapter-generated |
| Response | Status, media type, bounded size, schema, enums, timestamps, identity, parser version |
| Retry / new connection | Repeat from resolve |

### F. Redirect phase → revalidation requirement

| Phase | Requirement |
|---|---|
| Receive 30x | Default `DO_NOT_FOLLOW` → `POLICY_REJECTED` unless policy opts in |
| Target scheme | `https` only; downgrade rejected |
| Target host / port / path | Within the same provider allowlist and scope |
| Target resolution | Governed resolver; every answer validated; mixed → reject |
| Connect / peer | Bound to validated address; peer verified |
| Credentials | Only to the same governed destination binding |
| Hop count | Finite maximum — NOT YET SPECIFIED |

### G. Provenance field → purpose

See §24 (each row states its purpose and persistence target).

### H. Cache / freshness field → semantics

| Field | Semantics |
|---|---|
| Cache key components | Provider, operation, indicator type, indicator ref, policy version, parser version — no semantic collision |
| `observed_at` | When the provider answer was observed |
| `freshness_state` | `FRESH` / `STALE` / `UNKNOWN` technical recency; not confidence or risk |
| `freshness_policy_ref` | Governed expiry semantics (period NOT YET SPECIFIED) |
| Source provenance | §24 fields of the originating lookup |
| `cache_used` | Recorded on every enrichment |

### I. Replay versus re-analysis

See §27.

### J. ADR-0012 decision → machine-contract field

| ADR-0012 decision | Machine-contract field |
|---|---|
| D1 provider-neutral adapters, no provider selected | `provider_selection`, `indicator_types`, `provider_categories` |
| D2 indicator lookup only | `scope.permitted_capabilities`, `scope.submitted_url_semantics` |
| D3 no generic network primitive | `egress.generic_fetch_primitive`, `egress.operations_closed_and_predeclared`, `api_surface.new_endpoints` |
| D4 deny-by-default; governed destinations | `egress`, `request_construction`, `ai_boundary`, `policy_authority` |
| D5 resolve–validate–bind–verify | `dns`, `destination_validation`, `forbidden_destination_classes`, `redirects`, `proxy` |
| D6 HTTPS only | `transport` |
| D7 provider output is not a verdict | `outcomes`, `failure_semantics`, `decision_boundary` |
| D8 replay never contacts a provider | `replay`, `cache`, `freshness`, `provenance`, `response_artifact` |
| Credentials / minimization / observability | `credentials`, `data_minimization`, `correlation`, `audit`, `telemetry`, `logging`, `classification` |

### K. Integration invariant → validator check

| Check | Invariant |
|---|---|
| IC-01 | contract is valid against its JSON Schema (Draft 2020-12, local only) |
| IC-02 | ADR-0012 exists at the declared path; status Proposed (acceptance effective only after independent review) or Accepted, consistent between file and contract |
| IC-03 | INT-001 exists, Version 0.1, status APPROVED FOLLOWING INDEPENDENT REVIEW with remote CI + merge pending (contract status agrees); never claimed closed/merged before that |
| IC-04 | GATE-023 exists with status P6-WP5 INTEGRATION CONTRACT APPROVED, remote CI + merge pending (not closed) |
| IC-05 | egress is deny-by-default and denials are audited |
| IC-06 | destinations come only from governed provider policy (never user/evidence/AI/tool/provider/unrevalidated redirect) |
| IC-07 | HTTPS-only transport with certificate + hostname verification; unsafe schemes and TLS bypasses rejected |
| IC-08 | user input populates only the indicator value; never host/scheme/port/method/proxy/credential/template |
| IC-09 | AI controls no destination, credential, policy or SSRF control (future tool scope = predeclared operation only) |
| IC-10 | no generic fetch/download/proxy/open-url primitive; indicator lookup only; submitted URL is lookup data only |
| IC-11 | DNS resolution through a governed resolver; every answer validated on parsed IP semantics; no answer ordering |
| IC-12 | connected address bound to the validated resolution decision; SNI/hostname kept; peer verified; per connection |
| IC-13 | forbidden destination classes present with parseable ranges (loopback, RFC1918, link-local, multicast, unspecified, reserved, ULA, IPv6 link-local, metadata, local aliases); unclassifiable addresses rejected |
| IC-14 | IPv4-mapped / IPv4-embedding IPv6 forms covered |
| IC-15 | mixed public/private (or ambiguous) DNS answers reject the lookup |
| IC-16 | every redirect hop revalidated as a new destination decision; finite hop bound with no invented number |
| IC-17 | no HTTPS -> HTTP downgrade |
| IC-18 | redirects cannot escape the provider allowlist or reach private/internal space |
| IC-19 | environment proxies are not inherited; a governed proxy needs REQUIRED_AND_VERIFIED final-hop enforcement of the full direct-connector denied-address/binding scope; unverified proxy egress is DEPLOYMENT_BLOCKED and POLICY_REJECTED with no fallback; SEC-reference credentials; cannot weaken DNS/redirect authorization |
| IC-20 | credentials are SEC references only (never literal, URL, enrichment, audit, log, telemetry, API or AI) |
| IC-21 | sensitive network headers are adapter-generated only; never user controlled; CRLF rejected |
| IC-22 | raw evidence / identity / notes / rationale never outbound; least-data indicator only; no internal IDs outbound |
| IC-23 | provider response validated as untrusted input (status, media type, size, schema, enums, timestamps, identity) |
| IC-24 | response wire/decoded size finitely bounded without a fabricated number; decompression bounded |
| IC-25 | connect/read/overall timeouts finite without fabricated values |
| IC-26 | retries/backoff bounded without fabricated counts; only retry-safe lookups; 429 never safe |
| IC-27 | provider NOT_FOUND never maps to CLEAN/safe/no-scam |
| IC-28 | provider/network/policy failures never map to safe; every required failure condition defined |
| IC-29 | provider result cannot set DetectionResult, classification, severity, risk, confidence or rules; not consumed |
| IC-30 | no scam/fraud probability, score, likelihood, confidence, risk or severity field introduced |
| IC-31 | provenance complete (policy, provider, adapter, parser, indicator, times, outcome, freshness, digest, cache) |
| IC-32 | cache governed; collision-safe key; entries carry observed_at/freshness/provenance; no TTL; case isolation |
| IC-33 | stale never presented as fresh; freshness is neither confidence nor risk |
| IC-34 | historical replay never calls/refetches/refreshes the provider |
| IC-35 | historical replay never uses the newest provider response or latest provider policy |
| IC-36 | replay with missing enrichment material is unavailable (no approximation) |
| IC-37 | re-analysis may perform a new enrichment and records a new record (never overwrites history) |
| IC-38 | canonical CI offline: no live network, DNS, HTTP, real provider or API key; no HTTP client dependency |
| IC-39 | no tenant concept (ASM-002 UNCONFIRMED / PROVISIONAL) |
| IC-40 | ADR-0012 topic/status consistent with the reserved index entry and adr/README.md |
| IC-41 | G-09 remains OPEN |
| IC-42 | OI-05 remains OPEN (no retention duration) |
| IC-43 | provider policy is governed operator configuration, versioned, binds the full endpoint; analysts/AI/providers cannot change it |
| IC-44 | indicator types map exactly to existing url-observation authority; unsupported indicator kinds not permitted |
| IC-45 | outcome vocabulary and mappings use only accepted WP2 vocabularies and columns |
| IC-46 | no public API endpoint added; reserved listEvaluationEnrichments surface unchanged and mapped |
| IC-47 | provider-neutral: no vendor named, no provider selected |
| IC-48 | no numeric limit invented anywhere in the contract |
| IC-49 | audit and telemetry separated; no secrets/raw evidence in audit, telemetry or logs; data classified |
| IC-50 | response artifact integrity is not provider truth/authenticity; signed assertions not assumed |
| IC-51 | offline conformance scenarios evaluate to their expected outcome under the contract's own policy |

### L. Negative mutation → validator check

| Mutation | Description | Rejected by |
|---|---|---|
| NEG-IC-01 | egress default ALLOW | IC-05 |
| NEG-IC-02 | user input controls the destination URL | IC-08 |
| NEG-IC-03 | AI controls the destination URL | IC-09 |
| NEG-IC-04 | generic fetch(url) primitive added | IC-10 |
| NEG-IC-05 | plain HTTP permitted as a provider scheme | IC-07 |
| NEG-IC-06 | TLS certificate verification disabled (verify=false) | IC-07 |
| NEG-IC-07 | naive preflight DNS check, then the HTTP client re-resolves independently | IC-12 |
| NEG-IC-08 | loopback range no longer forbidden | IC-13 |
| NEG-IC-09 | RFC1918 private ranges no longer forbidden | IC-13 |
| NEG-IC-10 | IPv4 link-local no longer forbidden | IC-13 |
| NEG-IC-11 | IPv6 unique-local no longer forbidden | IC-13 |
| NEG-IC-12 | IPv4-mapped IPv6 handling omitted | IC-14 |
| NEG-IC-13 | mixed public/private DNS answers permitted (use any allowed answer) | IC-15 |
| NEG-IC-14 | redirects followed without revalidation (trust inherited) | IC-16 |
| NEG-IC-15 | redirect HTTPS -> HTTP downgrade allowed | IC-17 |
| NEG-IC-16 | redirect to a host outside the provider allowlist allowed | IC-18 |
| NEG-IC-17 | redirect-to-127.0.0.1 scenario weakened to permitted | IC-51 |
| NEG-IC-18 | redirect to private/internal space such as 169.254.169.254 allowed | IC-18 |
| NEG-IC-19 | environment proxy (HTTP_PROXY etc.) trusted automatically | IC-19 |
| NEG-IC-20 | user input controls the Host header | IC-21 |
| NEG-IC-21 | user input controls the Authorization header | IC-21 |
| NEG-IC-22 | credential literal stored in the provider policy | IC-20 |
| NEG-IC-23 | credential placed in a provider URL | IC-20 |
| NEG-IC-24 | raw evidence outbound allowed | IC-22 |
| NEG-IC-25 | unlimited response size | IC-24 |
| NEG-IC-26 | infinite timeout | IC-25 |
| NEG-IC-27 | unbounded retries | IC-26 |
| NEG-IC-28 | NOT_FOUND mapped to NO_SCAM_PATTERN | IC-27 |
| NEG-IC-29 | provider error (UNAVAILABLE) mapped to CLEAN | IC-28 |
| NEG-IC-30 | provider may set classification | IC-29 |
| NEG-IC-31 | provider may set confidence | IC-29 |
| NEG-IC-32 | scam_probability field added to the enrichment result | IC-30 |
| NEG-IC-33 | provenance response-artifact digest omitted | IC-31 |
| NEG-IC-34 | provenance provider identity omitted | IC-31 |
| NEG-IC-35 | stale cache presented as fresh | IC-33 |
| NEG-IC-36 | historical replay refetches from the provider | IC-34 |
| NEG-IC-37 | historical replay uses the latest provider result | IC-35 |
| NEG-IC-38 | historical replay substitutes missing enrichment material | IC-36 |
| NEG-IC-39 | canonical CI calls a real provider | IC-38 |
| NEG-IC-40 | API key required in CI | IC-38 |
| NEG-IC-41 | tenant_id introduced on the enrichment request | IC-39 |
| NEG-IC-42 | redirect to 169.254.169.254 scenario weakened to permitted | IC-51 |
| NEG-IC-43 | redirect to RFC1918 scenario weakened to permitted | IC-51 |
| NEG-IC-44 | connect binding weakened to resolve-again-at-connect | IC-12 |
| NEG-IC-45 | rebinding scenario evaluated under a weakened binding connects to private space | IC-51 |
| NEG-IC-46 | substring allowlist matching enabled | IC-18 |
| NEG-IC-47 | file scheme no longer rejected | IC-07 |
| NEG-IC-48 | destination host field added to the enrichment request | IC-08 |
| NEG-IC-49 | content retrieval permitted alongside indicator lookup | IC-10 |
| NEG-IC-50 | suspicious submitted URL is connected to | IC-10 |
| NEG-IC-51 | DNS validation by string blacklist only | IC-11 |
| NEG-IC-52 | DNS answer ordering relied on | IC-11 |
| NEG-IC-53 | invented numeric redirect hop limit | IC-16 |
| NEG-IC-54 | invented numeric connect timeout | IC-25 |
| NEG-IC-55 | invented numeric retry count | IC-26 |
| NEG-IC-56 | cache TTL invented | IC-32 |
| NEG-IC-57 | cache key omits indicator type (semantic collision) | IC-32 |
| NEG-IC-58 | freshness treated as confidence | IC-33 |
| NEG-IC-59 | re-analysis overwrites historical enrichment | IC-37 |
| NEG-IC-60 | ANALYST allowed to change provider policy | IC-43 |
| NEG-IC-61 | phone reputation indicator added | IC-44 |
| NEG-IC-62 | NOT_FOUND mapped to an invented enrichment status | IC-45 |
| NEG-IC-63 | new public fetch endpoint added | IC-46 |
| NEG-IC-64 | real vendor selected | IC-47 |
| NEG-IC-65 | raw indicator value allowed in telemetry | IC-49 |
| NEG-IC-66 | response digest claimed as provider authenticity | IC-50 |
| NEG-IC-67 | TIMEOUT mapped to a FOUND outcome | IC-28 |
| NEG-IC-68 | rate-limit failure condition removed | IC-28 |
| NEG-IC-69 | case notes no longer prohibited outbound | IC-22 |
| NEG-IC-70 | provider response trusted because provider is allowlisted | IC-23 |
| NEG-IC-71 | OI-05 marked closed with a retention duration | IC-42 |
| NEG-IC-72 | G-09 marked closed | IC-41 |
| NEG-IC-73 | contract status claims P6-WP5 closure before remote CI + merge | IC-03 |
| NEG-IC-74 | ADR-0012 repurposed to an unrelated topic | IC-40 |
| NEG-IC-75 | AI allowed to mutate provider policy | IC-09 |
| NEG-IC-76 | credentials persisted in enrichment records | IC-20 |
| NEG-IC-77 | ENGINE_VERSION pin changed | IC-29 |
| NEG-IC-78 | proxy final-hop enforcement requirement removed | IC-19 |
| NEG-IC-79 | proxy final-hop enforcement downgraded from REQUIRED_AND_VERIFIED to OPTIONAL | IC-19 |
| NEG-IC-80 | unverified proxy use permitted (fallback to trusting the proxy) | IC-19 |
| NEG-IC-81 | unverified proxy enforcement changed from DEPLOYMENT_BLOCKED to ALLOW | IC-19 |
| NEG-IC-82 | proxy denied-address scope weakened (RFC1918 not enforced on the final hop) | IC-19 |
| NEG-IC-83 | proxy allowed to bypass mixed-answer rejection | IC-19 |
| NEG-IC-84 | proxy allowed to bypass metadata-address rejection | IC-19 |
| NEG-IC-85 | proxy final-hop enforcement accepted without governed verifiable evidence | IC-19 |
| NEG-IC-86 | unverified proxy lookup outcome changed to FOUND | IC-19 |
| NEG-IC-87 | proxy permitted to weaken DNS/redirect authorization | IC-19 |
| NEG-IC-88 | proxy credentials stored inline instead of SEC references | IC-19 |
| NEG-IC-89 | proxy enforcement scope no longer equivalent to the direct connector policy | IC-19 |
| NEG-IC-90 | unverified-proxy scenario weakened to permitted | IC-51 |
| NEG-IC-91 | PROXY_ENFORCEMENT_UNVERIFIED failure condition removed | IC-28 |

### M. Deferred issue → owner

| Issue | Owner |
|---|---|
| Connector / adapter, resolver and peer-binding implementation | P6-WP6 |
| Governed-proxy final-hop enforcement evidence process (only if a proxy is deployed) | P6-WP6 / deployment security review |
| Numeric timeouts, retries, backoff, redirect hops, wire/decoded bytes, circuit thresholds | P6-WP6 / Sponsor / implementation security profile |
| Cache TTL and freshness periods | Governed provider policy / P6-WP6 |
| Additive WP2 provenance columns, `safe_error_category` vocabulary, enrichment audit events | Additive DATA-001-WP2 revision / P6-WP6 |
| Provider policy publication workflow and operator authority | P6-WP6 / Phase-9 |
| Provider selection | Sponsor (ASM-005) / governed operator |
| Activation of `listEvaluationEnrichments` | P6-WP6 + governed API-001/OAS-001 bookkeeping |
| Governed mapping of enrichment into deterministic observations (if ever) | Future governed Phase-3 change |
| Implementation security testing of SSRF / rebinding controls | P6-WP6 / Phase-9 |
| Retention duration | OI-05 (Sponsor + legal/governance) |
| Durable API idempotency persistence (carried LOW) | Additive DATA-001-WP2 revision + P6-WP6 |
| ETag server-revision persistence (carried LOW) | Additive DATA-001-WP2 revision + P6-WP6 |

## 38. Open items and carryovers

| Item | Status |
|---|---|
| G-09 | **OPEN** — no efficacy claim |
| OI-05 | **OPEN** — retention duration NOT YET SPECIFIED |
| ASM-002 | **UNCONFIRMED / PROVISIONAL** |
| ASM-005 | Open — no provider budget confirmed; provider selection deferred |
| WP4 LOW-3 | Addressed at contract level (§13); implementation verification OPEN (P6-WP6) |
| Idempotency persistence | OPEN / NON-BLOCKING — additive DATA-001-WP2 revision + P6-WP6 |
| ETag revision persistence | OPEN / NON-BLOCKING — additive DATA-001-WP2 revision + P6-WP6 |
| WP4 INFO collection-ETag refinement | Informational |
| WP4 INFO `action_code` enum refinement | Informational |
| P6-WP5 LOW-2 — external-enrichment persistence follow-ups (§33 additive columns, `safe_error_category` vocabulary, enrichment audit events) | OPEN / NON-BLOCKING — additive DATA-001-WP2 revision + P6-WP6 |
| P6-WP5 INFO-A — a builder summary mentioned a loopback proxy scenario that does not exist | Informational; loopback is covered by `proxy.enforcement_scope` (IC-19) |
| P6-WP5 INFO-B — IC-19 checks uppercase proxy variable names only; `environment_proxy_inheritance = false` is the binding rule | Informational |
| P6-WP5 INFO-C — IC-19 checks the `PROXY_ENFORCEMENT_UNVERIFIED` outcome/status but not separately its `safe_error_category` value | Informational (diagnostic) |
| P6-WP5 INFO-D — present provider `CLEAN` as a provider assertion when `listEvaluationEnrichments` is activated; carried WP4 collection-ETag and `action_code` INFOs | Informational → P6-WP6 activation |

## 39. Change log

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-10-03 | P6-WP5: initial integration contract candidate (provider-neutral indicator lookup, outbound network / SSRF control, outcomes, provenance, cache/freshness, replay), machine contract + schema + validator + negative mutations; ADR-0012 issued |
| 0.1 (review correction) | 2026-10-03 | Independent-review corrections: MEDIUM-1 governed-proxy final-hop assurance (§17: REQUIRED_AND_VERIFIED enforcement of the full connector scope, DEPLOYMENT_BLOCKED / `POLICY_REJECTED` when unverified, `PROXY_ENFORCEMENT_UNVERIFIED`; structural IC-19; proxy conformance scenarios and negative mutations); LOW-1 ADR-0012 returned to Proposed pending review; INFO-1 ADR embedded-IPv4 wording aligned; INFO-3 validator-only URL splitter statement (§36) |
| 0.1 (approved) | 2026-10-03 | Acceptance bookkeeping: targeted independent re-review APPROVE (BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 1 / INFO 4); status APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING; ADR-0012 Accepted; LOW-2 and INFO-A…D carried (§38); review history in GATE-023 §7–§8 |
