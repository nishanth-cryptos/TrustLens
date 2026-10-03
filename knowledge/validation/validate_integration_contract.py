"""TrustLens Phase 6 P6-WP5 — static validator for the INT-001 external-enrichment integration contract.

Validates contracts/integrations/external-enrichment-v1.json (the provider-neutral, machine-readable integration
policy) against contracts/integrations/integration-contract.schema.json, the accepted P6-WP2 persistence contract
(external_enrichment_result + vocabularies), the accepted P6-WP3/WP4 API surface (the reserved
listEvaluationEnrichments operation), the url-observation schema (indicator authority), ADR-0012, INT-001 and GATE-023.
It also replays the contract's offline conformance scenarios (provider redirect to loopback / metadata / RFC1918 /
unapproved host, HTTPS downgrade, DNS rebinding, mixed answers, IPv4-mapped IPv6, alternate IP encodings, userinfo and
suffix confusion) through a small REFERENCE DECISION MODEL driven by the contract's own policy values, using only the
the standard-library ipaddress parser and a minimal local URL splitter (the canonical gate forbids any urllib
import). It performs NO DNS lookup, NO socket and NO HTTP request; it proves the
CONTRACT is coherent, not that any connector implementation is correct (none exists).

  IC-01 contract is valid against its JSON Schema (Draft 2020-12, local only)
  IC-02 ADR-0012 exists at the declared path; status Proposed (acceptance effective only after independent review) or
        Accepted, consistent between file and contract
  IC-03 INT-001 exists, Version 0.1, status APPROVED FOLLOWING INDEPENDENT REVIEW with remote CI + merge pending
        (contract status agrees); never claimed closed/merged before that
  IC-04 GATE-023 exists with status P6-WP5 INTEGRATION CONTRACT APPROVED, remote CI + merge pending (not closed)
  IC-05 egress is deny-by-default and denials are audited
  IC-06 destinations come only from governed provider policy (never user/evidence/AI/tool/provider/unrevalidated redirect)
  IC-07 HTTPS-only transport with certificate + hostname verification; unsafe schemes and TLS bypasses rejected
  IC-08 user input populates only the indicator value; never host/scheme/port/method/proxy/credential/template
  IC-09 AI controls no destination, credential, policy or SSRF control (future tool scope = predeclared operation only)
  IC-10 no generic fetch/download/proxy/open-url primitive; indicator lookup only; submitted URL is lookup data only
  IC-11 DNS resolution through a governed resolver; every answer validated on parsed IP semantics; no answer ordering
  IC-12 connected address bound to the validated resolution decision; SNI/hostname kept; peer verified; per connection
  IC-13 forbidden destination classes present with parseable ranges (loopback, RFC1918, link-local, multicast,
        unspecified, reserved, ULA, IPv6 link-local, metadata, local aliases); unclassifiable addresses rejected
  IC-14 IPv4-mapped / IPv4-embedding IPv6 forms covered
  IC-15 mixed public/private (or ambiguous) DNS answers reject the lookup
  IC-16 every redirect hop revalidated as a new destination decision; finite hop bound with no invented number
  IC-17 no HTTPS -> HTTP downgrade
  IC-18 redirects cannot escape the provider allowlist or reach private/internal space
  IC-19 environment proxies are not inherited; a governed proxy needs REQUIRED_AND_VERIFIED final-hop enforcement of
        the full direct-connector denied-address/binding scope; unverified proxy egress is DEPLOYMENT_BLOCKED and
        POLICY_REJECTED with no fallback; SEC-reference credentials; cannot weaken DNS/redirect authorization
  IC-20 credentials are SEC references only (never literal, URL, enrichment, audit, log, telemetry, API or AI)
  IC-21 sensitive network headers are adapter-generated only; never user controlled; CRLF rejected
  IC-22 raw evidence / identity / notes / rationale never outbound; least-data indicator only; no internal IDs outbound
  IC-23 provider response validated as untrusted input (status, media type, size, schema, enums, timestamps, identity)
  IC-24 response wire/decoded size finitely bounded without a fabricated number; decompression bounded
  IC-25 connect/read/overall timeouts finite without fabricated values
  IC-26 retries/backoff bounded without fabricated counts; only retry-safe lookups; 429 never safe
  IC-27 provider NOT_FOUND never maps to CLEAN/safe/no-scam
  IC-28 provider/network/policy failures never map to safe; every required failure condition defined
  IC-29 provider result cannot set DetectionResult, classification, severity, risk, confidence or rules; not consumed
  IC-30 no scam/fraud probability, score, likelihood, confidence, risk or severity field introduced
  IC-31 provenance complete (policy, provider, adapter, parser, indicator, times, outcome, freshness, digest, cache)
  IC-32 cache governed; collision-safe key; entries carry observed_at/freshness/provenance; no TTL; case isolation
  IC-33 stale never presented as fresh; freshness is neither confidence nor risk
  IC-34 historical replay never calls/refetches/refreshes the provider
  IC-35 historical replay never uses the newest provider response or latest provider policy
  IC-36 replay with missing enrichment material is unavailable (no approximation)
  IC-37 re-analysis may perform a new enrichment and records a new record (never overwrites history)
  IC-38 canonical CI offline: no live network, DNS, HTTP, real provider or API key; no HTTP client dependency
  IC-39 no tenant concept (ASM-002 UNCONFIRMED / PROVISIONAL)
  IC-40 ADR-0012 topic/status consistent with the reserved index entry and adr/README.md
  IC-41 G-09 remains OPEN
  IC-42 OI-05 remains OPEN (no retention duration)
  IC-43 provider policy is governed operator configuration, versioned, binds the full endpoint; analysts/AI/providers
        cannot change it
  IC-44 indicator types map exactly to existing url-observation authority; unsupported indicator kinds not permitted
  IC-45 outcome vocabulary and mappings use only accepted WP2 vocabularies and columns
  IC-46 no public API endpoint added; reserved listEvaluationEnrichments surface unchanged and mapped
  IC-47 provider-neutral: no vendor named, no provider selected
  IC-48 no numeric limit invented anywhere in the contract
  IC-49 audit and telemetry separated; no secrets/raw evidence in audit, telemetry or logs; data classified
  IC-50 response artifact integrity is not provider truth/authenticity; signed assertions not assumed
  IC-51 offline conformance scenarios evaluate to their expected outcome under the contract's own policy

It then applies every mutation in contracts/integrations/fixtures/negative-mutations.json and requires the named
check to fail. Offline and deterministic: reads repository files only.

Usage:  .venv/bin/python knowledge/validation/validate_integration_contract.py [--quiet]
Exit 0 = integration contract consistent and every negative mutation rejected by its expected check.
"""

from __future__ import annotations

import copy
import ipaddress
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "contracts" / "integrations" / "external-enrichment-v1.json"
SCHEMA_PATH = ROOT / "contracts" / "integrations" / "integration-contract.schema.json"
NEGATIVE_PATH = ROOT / "contracts" / "integrations" / "fixtures" / "negative-mutations.json"
PERSISTENCE_PATH = ROOT / "contracts" / "postgresql" / "schema-v1.json"
CATALOG_PATH = ROOT / "contracts" / "api" / "api-v1.json"
OPENAPI_PATH = ROOT / "contracts" / "api" / "openapi-v1.json"
URL_OBS_PATH = ROOT / "knowledge" / "schemas" / "url-observation.schema.json"
ADR_INDEX_PATH = ROOT / "adr" / "README.md"
INT_DOC_PATH = ROOT / "docs" / "06-contracts" / "INT-001-external-enrichment-integration-contract.md"
GATE_PATH = ROOT / "docs" / "00-program" / "GATE-023-phase-6-integration-contract.md"
REQUIREMENTS_PATH = ROOT / "requirements.txt"
ENGINE_PATH = ROOT / "knowledge" / "runtime" / "engine.py"

NYS = "NOT YET SPECIFIED"
APPROVED = "P6-WP5 INTEGRATION CONTRACT APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING"
GATE_APPROVED = "P6-WP5 INTEGRATION CONTRACT APPROVED"
PENDING = "REMOTE CI + MERGE PENDING"
PREMATURE = re.compile(r"\b(CLOSED|MERGED|REMOTE CI PASS)", re.I)
NEGATED = re.compile(r"\bnot (yet )?(formally )?(closed|merged)\b", re.I)
RESERVED_TITLE = "Threat-intelligence adapter architecture and provider selection"

REQ_FORBIDDEN_SOURCES = {"END_USER_REQUEST", "EVIDENCE_CONTENT", "AI_OUTPUT", "MODEL_TOOL_CALL", "PROVIDER_RESPONSE",
                         "UNREVALIDATED_REDIRECT"}
REQ_REJECTED_SCHEMES = {"http", "file", "ftp", "gopher", "data", "javascript", "unix", "CUSTOM_URI_SCHEMES"}
REQ_NEVER_USER = {"destination_url", "destination_host", "scheme", "port", "path", "http_method", "proxy", "host_header",
                  "authorization_header", "cookie_header", "arbitrary_headers", "redirect_behavior", "tls_verification",
                  "provider_credential", "raw_request_template"}
USER_POPULATABLE = {"indicator_value"}
DESTINATION_FIELDS = {"destination_url", "destination_host", "scheme", "port", "http_method", "headers", "proxy",
                      "tls_verification", "credential", "raw_request_template", "redirect_policy", "url", "host",
                      "target_url"}
REQ_HEADERS = {"Host", "Authorization", "Proxy-Authorization", "Cookie", "Connection", "Transfer-Encoding", "Forwarded",
               "X-Forwarded-*"}
HEADERISH = re.compile(r"(header|host|authorization|cookie|forwarded|connection|transfer)", re.I)
GENERIC_OP = re.compile(r"(fetch|download|open_?url|http_?request|proxy_?request|crawl|scrape|webhook|retriev)", re.I)
REQ_DNS_STEPS = ["PARSE_AND_CANONICALIZE_GOVERNED_DESTINATION", "RESOLVE_THROUGH_GOVERNED_RESOLVER",
                 "VALIDATE_EVERY_RESOLVED_ADDRESS", "REJECT_DENIED_ADDRESS_SPACE", "CONNECT_ONLY_TO_VALIDATED_ADDRESS",
                 "PRESERVE_SNI_AND_HOSTNAME_VERIFICATION", "VERIFY_CONNECTED_PEER", "REVALIDATE_EACH_NEW_CONNECTION",
                 "REVALIDATE_EACH_REDIRECT_TARGET"]
BINDING = "CONNECT_ONLY_TO_VALIDATED_ADDRESS_FROM_SAME_RESOLUTION_DECISION"
PEER = "VERIFY_CONNECTED_PEER_ADDRESS_PERMITTED"
REQ_CLASSES = {
    "LOOPBACK": {"127.0.0.0/8", "::1/128"},
    "PRIVATE_RFC1918": {"10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"},
    "LINK_LOCAL": {"169.254.0.0/16", "fe80::/10"},
    "MULTICAST": {"224.0.0.0/4", "ff00::/8"},
    "UNSPECIFIED": {"0.0.0.0/8", "::/128"},
    "RESERVED_NON_ROUTABLE": {"240.0.0.0/4", "100.64.0.0/10"},
    "IPV6_UNIQUE_LOCAL": {"fc00::/7"},
    "IPV6_LINK_LOCAL": {"fe80::/10"},
    "IPV4_EMBEDDED_IPV6": {"::ffff:0:0/96"},
    "INSTANCE_METADATA": {"169.254.169.254/32"},
    "LOCAL_HOST_ALIAS": set(),
}
REQ_REVALIDATE = {"scheme", "host", "port", "path_scope", "dns_resolution", "resolved_addresses", "connected_peer"}
REQ_PROXY_ENV = {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}
PROXY_BEHAVIOUR_SCOPE = {"MIXED_ANSWER_REJECTION", "ALIAS_CHAIN_VALIDATION", "CONNECTED_PEER_ENFORCEMENT"}
CRED_FLAGS = ("literal_values_in_contract", "in_url", "persisted_in_enrichment", "in_audit", "in_logs", "in_telemetry",
              "in_api", "in_ai_prompt")
CRED_KEYS = {"api_key", "apikey", "secret", "password", "token", "access_token", "credential_value", "client_secret",
             "private_key", "bearer"}
CRED_LITERAL = re.compile(r"(?i)(bearer\s+[a-z0-9._~+/-]{8,}|[?&](api[_-]?key|key|token|access_token|secret|sig)=|"
                          r"\bsk-[a-z0-9]{8,}|https?://[^/\s@]+:[^/\s@]+@)")
REQ_PROHIBITED = {"RAW_MESSAGE_BODY", "SCREENSHOT", "DOCUMENT", "EVIDENCE_BYTES", "FULL_CASE_FILE", "USER_IDENTITY",
                  "CASE_NOTES", "ADJUDICATION_RATIONALE", "INTERNAL_DATABASE_IDENTIFIERS"}
ALLOWED_OUTBOUND = {"NORMALIZED_INDICATOR_VALUE", "ADAPTER_GENERATED_EXTERNAL_CORRELATION_VALUE",
                    "GOVERNED_AUTHENTICATION_FROM_CREDENTIAL_REFERENCE"}
REQ_RESPONSE_VALIDATE = {"http_status", "media_type", "decoded_size", "schema_shape", "required_fields", "enum_values",
                         "timestamp_format", "provider_identity", "parser_schema_version"}
OUTCOMES = ["FOUND", "NOT_FOUND", "UNAVAILABLE", "POLICY_REJECTED", "INVALID_RESPONSE"]
FAILURE_OUTCOMES = {"UNAVAILABLE", "POLICY_REJECTED", "INVALID_RESPONSE"}
REQ_CONDITIONS = {"DNS_FAILURE", "CONNECTION_FAILURE", "TLS_FAILURE", "TIMEOUT", "PROVIDER_4XX", "PROVIDER_5XX",
                  "RATE_LIMITED", "INVALID_CONTENT_TYPE", "OVERSIZED_RESPONSE", "SCHEMA_INVALID_RESPONSE",
                  "POLICY_REJECTION", "REDIRECT_POLICY_REJECTION", "DESTINATION_ADDRESS_REJECTION",
                  "CREDENTIAL_UNAVAILABLE", "PROVIDER_UNAVAILABLE", "PROXY_ENFORCEMENT_UNVERIFIED"}
REQ_NEVER_SET = {"DetectionResult", "classification", "severity", "risk", "confidence", "governing_rule",
                 "rule_override", "rule_suppression"}
REQ_FORBIDDEN_MEANINGS = {"SCAM_PATTERN_DETECTED", "SCAM_PATTERN_SUSPECTED", "NO_SCAM_PATTERN", "SAFE", "LEGITIMATE",
                          "VERIFIED"}
INVENTED = re.compile(r"(probab|score|likelihood|percent|confidence|risk|severity|verdict)", re.I)
INVENTED_ALLOWED_KEYS = {"is_confidence", "is_risk"}
REQ_PROVENANCE = {"provider_policy_ref", "provider_policy_version", "provider_ref", "adapter_version",
                  "parser_schema_version", "integration_contract_version", "indicator_type", "normalized_indicator_ref",
                  "request_ref", "requested_at", "observed_at", "lookup_outcome", "provider_response_category",
                  "freshness_state", "response_artifact_digest", "cache_used"}
REQ_CACHE_KEY = {"provider_ref", "indicator_type", "normalized_indicator_ref", "provider_policy_version",
                 "parser_schema_version"}
REQ_CACHE_ENTRY = {"observed_at", "freshness_state", "source_provenance"}
TENANT = re.compile(r"(tenant[_-]?(id|ref|key|routing)|x-tenant|\btenant\b)", re.I)
VENDORS = re.compile(r"(virus\s*total|urlscan|abuse\s*ipdb|safe\s*browsing|google|microsoft|phishtank|openphish|"
                     r"spamhaus|talos|crowdstrike|recorded\s*future|alienvault|cloudflare|amazon|\baws\b|azure)", re.I)
REQ_POLICY_BINDING = {"provider_ref", "scheme", "host", "port", "path_prefix", "provider_operation", "method",
                      "expected_media_type", "authentication_method_ref", "parser_schema_version"}
REQ_POLICY_IMMUTABLE_BY = {"ANALYST", "END_USER", "AI", "PROVIDER_RESPONSE"}
INDICATOR_AUTHORITY = {"URL", "HOSTNAME", "REGISTERED_DOMAIN"}
REQ_NOT_PERMITTED = {"PHONE", "UPI", "BANK_ACCOUNT", "EMAIL", "DEVICE_FINGERPRINT"}
NUMERIC_EXEMPT = {("conformance_scenarios", "fixture_provider", "port")}
TELEMETRY_ALLOWED = {"LATENCY", "OUTCOME_CATEGORY", "ADAPTER_HEALTH", "CIRCUIT_STATE"}
REQ_TELEMETRY_FORBIDDEN = {"CREDENTIAL_VALUE", "AUTHORIZATION_HEADER", "RAW_C4_EVIDENCE", "RAW_INDICATOR_VALUE"}
REQ_LOG_FORBIDDEN = {"API_KEY", "AUTHORIZATION_HEADER", "RAW_PROVIDER_CREDENTIAL", "RAW_EVIDENCE"}
REQ_CLASSIFICATION = {"OUTBOUND_INDICATOR": "C4", "PROVIDER_RESPONSE_CONTENT": "C4", "PROVENANCE_METADATA": "C2",
                      "CREDENTIALS": "C7", "AUDIT_RECORDS": "C6", "TELEMETRY": "C8"}
HTTP_CLIENT_DEPS = re.compile(r"^\s*(requests|httpx|aiohttp|urllib3|pycurl|httplib2|treq)\b", re.I | re.M)
NETWORK_IMPORT = re.compile(r"^\s*(import|from)\s+(socket|requests|httpx|aiohttp|urllib|http|ssl)\b",
                            re.M)
REQ_SCENARIO_NAMES = ("loopback", "metadata", "rfc1918", "unapproved", "downgrade", "rebinding", "mixed",
                      "ipv4-mapped", "proxy without verified")


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def walk(node, fn, path=()):
    fn(node, path)
    if isinstance(node, dict):
        for k, v in node.items():
            walk(v, fn, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, fn, path + (i,))


def status_line(text: str) -> str:
    m = re.search(r"^\|\s*Status\s*\|\s*(.+?)\s*\|\s*$", text, re.M)
    return m.group(1) if m else ""


def is_nys_limit(lim) -> bool:
    return (isinstance(lim, dict) and lim.get("bound") == "FINITE" and lim.get("value") == NYS
            and bool(lim.get("owner")))


def premature(status: str) -> bool:
    """True if a status claims closure/merge/remote-CI success (explicit negations such as 'not yet closed' excepted)."""
    return bool(PREMATURE.search(NEGATED.sub("", status)))


def obj(c: dict, name: str) -> dict:
    return next((o for o in c.get("integration_objects", []) if o.get("name") == name), {})


# ---------------------------------------------------------------- offline reference decision model (no network)

def _ip_literal(host: str):
    """Parse a host as an IP literal, including alternate textual encodings (integer, hex, octal, short forms)."""
    h = host.strip("[]")
    try:
        return ipaddress.ip_address(h)
    except ValueError:
        pass
    if re.fullmatch(r"(0x[0-9a-f]+|\d+)(\.(0x[0-9a-f]+|\d+)){0,3}", h, re.I):
        return "ALTERNATE_ENCODING"
    return None


def _denied(addr: str, c: dict, scope: set | None = None) -> bool:
    """True if addr falls in a forbidden class (optionally only the classes in scope, e.g. a proxy's enforced scope)."""
    if addr == c["conformance_scenarios"]["global_address_placeholder"]:
        return False
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return c.get("unclassifiable_address") == "REJECT"
    for cls in c["forbidden_destination_classes"]:
        if scope is not None and cls.get("class") not in scope:
            continue
        for cidr in cls.get("ipv4", []) + cls.get("ipv6", []):
            try:
                net = ipaddress.ip_network(cidr, strict=False)
            except ValueError:
                continue
            if net.version == ip.version and ip in net:
                return True
    return False


def _split_url(url: str) -> tuple[str, str, str]:
    """Return (scheme, userinfo, host) by plain string splitting — no network-capable module is imported."""
    scheme, _, rest = url.partition("://")
    authority = re.split(r"[/?#]", rest, maxsplit=1)[0]
    userinfo, _, hostport = authority.rpartition("@")
    if hostport.startswith("["):
        host = hostport[1:hostport.find("]")] if "]" in hostport else hostport
    else:
        host = hostport.rsplit(":", 1)[0] if ":" in hostport else hostport
    return scheme.lower(), userinfo, host


def _evaluate_proxy(s: dict, c: dict) -> str:
    """Governed-proxy final hop: unverified enforcement must block; verified enforcement applies only its declared scope."""
    px = c["proxy"]
    if not s.get("proxy_enforcement_verified"):
        blocked = (px.get("final_hop_enforcement") == "REQUIRED_AND_VERIFIED"
                   and px.get("unverified_enforcement") == "DEPLOYMENT_BLOCKED" and px.get("unverified_fallback") == "NONE")
        return px.get("unverified_enforcement_outcome", "PERMITTED") if blocked else "PERMITTED"
    scope = set(px.get("enforcement_scope", []))
    answers = list(s.get("resolved", []))
    denied = [a for a in answers if _denied(a, c, scope)]
    if denied and ("MIXED_ANSWER_REJECTION" in scope or len(denied) == len(answers)):
        return "POLICY_REJECTED"
    return "PERMITTED"


def evaluate(s: dict, c: dict) -> str:
    """Decide one conformance scenario from the contract's OWN policy values. Purely local parsing."""
    fixture = c["conformance_scenarios"]["fixture_provider"]
    red, dv, dns = c["redirects"], c["destination_validation"], c["dns"]
    is_redirect = s["kind"] == "REDIRECT"
    if s["kind"] == "PROXY":
        return _evaluate_proxy(s, c)
    if is_redirect and (red.get("inherit_trust") or not red.get("each_hop_is_new_destination_decision")):
        return "PERMITTED"  # trust inherited: the hop is never re-authorized
    scheme, userinfo, raw_host = _split_url(s["target"])
    downgrade_ok = is_redirect and scheme == "http" and red.get("https_to_http") != "REJECT"
    if scheme not in c["transport"]["permitted_schemes"] and not downgrade_ok:
        return "POLICY_REJECTED"
    if userinfo and dv["hostname_canonicalization"].get("userinfo") == "REJECT":
        return "POLICY_REJECTED"
    host = raw_host.lower().rstrip(".")
    if _ip_literal(host) is not None and str(dv.get("ip_literal_destinations", "")).startswith("REJECT"):
        return "POLICY_REJECTED"
    allowed_host = fixture["host"].lower()
    matched = (allowed_host in host) if dv.get("substring_matching") else (host == allowed_host)
    if not matched and not (is_redirect and red.get("outside_provider_allowlist") != "REJECT"):
        return "POLICY_REJECTED"
    answers = list(s.get("resolved", []))
    if not answers and _ip_literal(host) not in (None, "ALTERNATE_ENCODING"):
        answers = [host.strip("[]")]
    checked = answers if dns.get("validate_every_answer") else answers[:1]
    denied = [a for a in checked if _denied(a, c)]
    if is_redirect and red.get("private_or_internal_target") != "REJECT":
        denied = []
    if denied:
        if dns.get("mixed_answers") == "REJECT_LOOKUP" or len(denied) == len(checked):
            return "POLICY_REJECTED"
    if s["kind"] == "REBINDING":
        bound = (dns.get("connect_binding") == BINDING and dns.get("uncontrolled_re_resolution") is False
                 and dns.get("peer_verification") == PEER)
        connected = answers if bound else s.get("connect_time_resolved", [])
        if any(_denied(a, c) for a in connected):
            return "CONNECTED_TO_DENIED_ADDRESS"
        return "CONNECTS_ONLY_TO_VALIDATED_ADDRESS"
    return "PERMITTED"


# ---------------------------------------------------------------- checks

def check(c: dict, ctx: dict) -> list[tuple[str, str]]:
    errs: list[tuple[str, str]] = []

    def e(code, msg):
        errs.append((code, msg))

    def g(*keys, default=None):
        node = c
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    # IC-01 schema
    for err in sorted(ctx["validator"].iter_errors(c), key=lambda x: list(x.path)):
        e("IC-01", f"schema: {'/'.join(map(str, err.path)) or '<root>'}: {err.message[:160]}")

    # IC-02 ADR-0012 file + status (Proposed pending independent review, or Accepted), consistent
    adr_path = ROOT / str(g("adr", "path", default=""))
    adr_text = read(adr_path) if g("adr", "path") else ""
    adr_status = g("adr", "status")
    if not adr_text or not adr_path.name.startswith("ADR-0012-"):
        e("IC-02", f"ADR-0012 not found at {g('adr', 'path')!r}")
    elif adr_status not in ("Proposed", "Accepted") or not status_line(adr_text).startswith(f"**{adr_status}**"):
        e("IC-02", "ADR-0012 status must be Proposed or Accepted and identical in the file status line and contract")
    elif adr_status == "Proposed" and "independent" not in status_line(adr_text).lower():
        e("IC-02", "a Proposed ADR-0012 must state that acceptance follows independent review")

    # IC-03 INT-001
    int_text = ctx["int_text"]
    if not int_text:
        e("IC-03", "INT-001 document missing")
    else:
        st = status_line(int_text)
        if APPROVED not in st or premature(st) or \
                not re.search(r"^\|\s*Version\s*\|\s*0\.1\s*\|", int_text, re.M):
            e("IC-03", f"INT-001 must be Version 0.1 with status {APPROVED!r} (not closed/merged)")
    if g("status") != APPROVED:
        e("IC-03", f"contract status {g('status')!r} must be {APPROVED!r}")

    # IC-04 GATE-023
    gate_text = ctx["gate_text"]
    gst = status_line(gate_text)
    if not gate_text or GATE_APPROVED not in gst or PENDING not in gst or premature(gst):
        e("IC-04", "GATE-023 missing or not 'P6-WP5 INTEGRATION CONTRACT APPROVED — REMOTE CI + MERGE PENDING' (not closed)")

    # IC-05 deny by default
    if g("egress", "default") != "DENY":
        e("IC-05", f"egress default must be DENY, got {g('egress', 'default')!r}")
    if g("egress", "denial_audited") is not True:
        e("IC-05", "egress denials must be audited")

    # IC-06 destination authority
    if g("egress", "destination_authority") != "GOVERNED_PROVIDER_POLICY":
        e("IC-06", "destination authority must be GOVERNED_PROVIDER_POLICY")
    missing = REQ_FORBIDDEN_SOURCES - set(g("egress", "destination_sources_forbidden", default=[]))
    if missing:
        e("IC-06", f"destination sources not forbidden: {sorted(missing)}")
    if g("egress", "operations_closed_and_predeclared") is not True:
        e("IC-06", "provider adapter operations must be closed and predeclared")

    # IC-07 HTTPS + TLS
    if g("transport", "permitted_schemes") != ["https"]:
        e("IC-07", f"permitted schemes must be exactly ['https'], got {g('transport', 'permitted_schemes')!r}")
    missing = REQ_REJECTED_SCHEMES - set(g("transport", "rejected_schemes", default=[]))
    if missing:
        e("IC-07", f"schemes not rejected: {sorted(missing)}")
    if g("transport", "unix_socket_transport") is not False or g("transport", "generic_uri_dispatcher") is not False:
        e("IC-07", "unix socket transport / generic URI dispatcher must be false")
    tls = g("transport", "tls", default={}) or {}
    if tls.get("certificate_verification") != "REQUIRED" or tls.get("hostname_verification") != "REQUIRED":
        e("IC-07", "certificate and hostname verification must be REQUIRED")
    for f in ("insecure_bypass_permitted", "plaintext_fallback", "self_signed_bypass"):
        if tls.get(f) is not False:
            e("IC-07", f"tls.{f} must be false")
    if tls.get("enterprise_trust_store") != "SEPARATELY_GOVERNED_ONLY":
        e("IC-07", "enterprise trust store must be SEPARATELY_GOVERNED_ONLY")

    # IC-08 user cannot control destination
    populate = set(g("request_construction", "user_input_may_populate", default=[]))
    if not populate <= USER_POPULATABLE:
        e("IC-08", f"user input may populate only the indicator value, also got {sorted(populate - USER_POPULATABLE)}")
    missing = REQ_NEVER_USER - set(g("request_construction", "never_user_controlled", default=[]))
    if missing:
        e("IC-08", f"not declared never-user-controlled: {sorted(missing)}")
    if g("request_construction", "owner") != "ADAPTER":
        e("IC-08", "request construction must be owned by the adapter")
    req = obj(c, "ExternalEnrichmentRequest")
    bad = DESTINATION_FIELDS & set(req.get("fields", []))
    if bad:
        e("IC-08", f"ExternalEnrichmentRequest carries destination-controlling fields {sorted(bad)}")
    if g("destination_validation", "user_selectable_ip") is not False:
        e("IC-08", "user must never select an IP destination")
    if g("scope", "submitted_url_semantics", "treated_as") != "LOOKUP_DATA_ONLY":
        e("IC-08", "a submitted URL must be lookup data only")

    # IC-09 AI boundary
    ai = g("ai_boundary", default={}) or {}
    if ai.get("ai_controllable_fields"):
        e("IC-09", f"AI may control no request field, got {ai.get('ai_controllable_fields')}")
    for f in ("destination_control", "url_or_host_targets", "credential_injection", "ssrf_policy_bypass",
              "provider_policy_mutation"):
        if ai.get(f) is not False:
            e("IC-09", f"ai_boundary.{f} must be false")
    if ai.get("future_tool_scope") != "PREDECLARED_OPERATION_AND_STRUCTURED_INDICATOR_ONLY":
        e("IC-09", "future AI tool scope must be a predeclared operation + structured indicator only")
    if ai.get("phase4_ai_default") != "OFF" or ai.get("phase4_authority") != "NON_AUTHORITATIVE":
        e("IC-09", "Phase-4 AI must stay default-OFF and non-authoritative")

    # IC-10 no generic fetch
    if g("egress", "generic_fetch_primitive") is not False:
        e("IC-10", "generic fetch primitive must not exist")
    if g("scope", "permitted_capabilities") != ["INDICATOR_LOOKUP"]:
        e("IC-10", f"only INDICATOR_LOOKUP is permitted, got {g('scope', 'permitted_capabilities')!r}")
    missing = {"CONTENT_RETRIEVAL", "GENERIC_FETCH"} - set(g("scope", "forbidden_capabilities", default=[]))
    if missing:
        e("IC-10", f"capabilities not forbidden: {sorted(missing)}")
    sus = g("scope", "submitted_url_semantics", default={}) or {}
    for f in ("connect_to_submitted_destination", "resolve_submitted_destination", "download_submitted_content",
              "follow_submitted_redirects", "execute_submitted_content"):
        if sus.get(f) is not False:
            e("IC-10", f"submitted_url_semantics.{f} must be false")
    op_names = [o.get("name", "") for o in c.get("integration_objects", [])]
    op_names += [p.get("category", "") for p in c.get("provider_categories", [])]
    op_names += list(g("scope", "permitted_capabilities", default=[]) or [])
    op_names += list(g("api_surface", "new_endpoints", default=[]) or [])
    op_names += list(g("scope", "public_api_endpoints_added", default=[]) or [])
    for o in c.get("integration_objects", []):
        op_names += list(o.get("fields", []))
    hits = sorted({n for n in op_names if isinstance(n, str) and GENERIC_OP.search(n)})
    if hits:
        e("IC-10", f"generic network operation/field present: {hits}")

    # IC-11 DNS validated
    if g("dns", "resolver") != "GOVERNED_RESOLVER":
        e("IC-11", "resolution must go through the governed resolver")
    if g("dns", "validate_every_answer") is not True:
        e("IC-11", "every DNS answer must be validated")
    if g("dns", "address_validation") != "PARSED_IP_SEMANTICS" or \
            g("destination_validation", "ip_semantics") != "PARSED_IP_SEMANTICS":
        e("IC-11", "address validation must use parsed IP semantics")
    if g("destination_validation", "string_blacklist_only") is not False:
        e("IC-11", "a string blacklist alone is not address validation")
    if g("dns", "alias_chains") != "VALIDATE_FINAL_ADDRESSES":
        e("IC-11", "alias (CNAME) chains must be validated on final addresses")
    if g("dns", "rely_on_answer_ordering") is not False:
        e("IC-11", "must not rely on DNS answer ordering")

    # IC-12 connect binding
    if g("dns", "connect_binding") != BINDING:
        e("IC-12", f"connect binding must be {BINDING}")
    if g("dns", "uncontrolled_re_resolution") is not False:
        e("IC-12", "uncontrolled re-resolution between validation and connect must be false")
    if g("dns", "peer_verification") != PEER:
        e("IC-12", "connected peer address must be verified")
    if g("dns", "tls_sni_and_verification_name") != "ORIGINAL_APPROVED_HOSTNAME":
        e("IC-12", "SNI/hostname verification must use the original approved hostname")
    if g("dns", "per_connection_revalidation") is not True:
        e("IC-12", "validation must repeat for each new connection")
    if g("dns", "steps") != REQ_DNS_STEPS:
        e("IC-12", "DNS/connect strategy steps must be the nine ordered invariant steps")
    if g("retries", "each_attempt_revalidates_destination") is not True:
        e("IC-12", "every retry attempt must revalidate the destination")

    # IC-13 forbidden classes
    classes = {cl.get("class"): cl for cl in c.get("forbidden_destination_classes", []) if isinstance(cl, dict)}
    for name, cidrs in REQ_CLASSES.items():
        if name == "IPV4_EMBEDDED_IPV6":
            continue
        cl = classes.get(name)
        if cl is None:
            e("IC-13", f"forbidden destination class {name} missing")
            continue
        have = set(cl.get("ipv4", [])) | set(cl.get("ipv6", []))
        if not cidrs <= have:
            e("IC-13", f"class {name} lacks ranges {sorted(cidrs - have)}")
    for cl in classes.values():
        for cidr in cl.get("ipv4", []) + cl.get("ipv6", []):
            try:
                ipaddress.ip_network(cidr, strict=True)
            except ValueError:
                e("IC-13", f"class {cl.get('class')}: unparseable range {cidr!r}")
    if g("unclassifiable_address") != "REJECT":
        e("IC-13", "unclassifiable addresses must be rejected")

    # IC-14 IPv4-mapped IPv6
    emb = classes.get("IPV4_EMBEDDED_IPV6")
    if emb is None or "::ffff:0:0/96" not in emb.get("ipv6", []):
        e("IC-14", "IPv4-mapped IPv6 (::ffff:0:0/96) must be a forbidden/embedded-evaluated class")

    # IC-15 mixed answers
    if g("dns", "mixed_answers") != "REJECT_LOOKUP" or g("dns", "ambiguous_answers") != "REJECT_LOOKUP":
        e("IC-15", "mixed public/private and ambiguous DNS answers must reject the lookup")

    # IC-16 redirect revalidation
    red = g("redirects", default={}) or {}
    if red.get("inherit_trust") is not False or red.get("each_hop_is_new_destination_decision") is not True:
        e("IC-16", "redirects must not inherit trust; each hop is a new destination decision")
    missing = REQ_REVALIDATE - set(red.get("revalidate", []))
    if missing:
        e("IC-16", f"redirect revalidation omits {sorted(missing)}")
    if red.get("default_provider_redirect_policy") != "DO_NOT_FOLLOW" or not set(
            red.get("permitted_provider_redirect_policies", [])) <= {"DO_NOT_FOLLOW",
                                                                     "REVALIDATE_WITHIN_PROVIDER_ALLOWLIST"}:
        e("IC-16", "redirect policy must default to DO_NOT_FOLLOW and allow only revalidated in-allowlist following")
    if g("dns", "per_redirect_revalidation") is not True:
        e("IC-16", "DNS/address validation must repeat for every redirect target")
    if not is_nys_limit(red.get("max_hops")):
        e("IC-16", "redirect hop bound must be FINITE with value NOT YET SPECIFIED and an owner (no invented number)")

    # IC-17 no downgrade
    if red.get("https_to_http") != "REJECT":
        e("IC-17", "HTTPS -> HTTP redirect downgrade must be rejected")

    # IC-18 allowlist escape
    if red.get("outside_provider_allowlist") != "REJECT":
        e("IC-18", "redirect outside the provider allowlist must be rejected")
    if red.get("private_or_internal_target") != "REJECT":
        e("IC-18", "redirect to private/internal space must be rejected")
    if red.get("credential_forwarding") != "ONLY_TO_SAME_GOVERNED_DESTINATION_BINDING":
        e("IC-18", "credentials must not be forwarded across redirect destinations")
    if red.get("rejection_outcome") != "POLICY_REJECTED":
        e("IC-18", "redirect rejection outcome must be POLICY_REJECTED")
    if g("destination_validation", "substring_matching") is not False or \
            g("destination_validation", "allowlist_matching") != "EXACT_HOST_OR_GOVERNED_SUBDOMAIN_RULE":
        e("IC-18", "allowlist matching must be exact host or governed subdomain rule, never substring")

    # IC-19 proxy
    px = g("proxy", default={}) or {}
    if px.get("environment_proxy_inheritance") is not False:
        e("IC-19", "environment proxy settings must not be inherited automatically")
    missing = REQ_PROXY_ENV - set(px.get("ignored_environment_variables", []))
    if missing:
        e("IC-19", f"environment proxy variables not ignored: {sorted(missing)}")
    if px.get("governed_proxy") != "OPTIONAL_GOVERNED_ONLY" or px.get("proxy_as_policy_escape") is not False:
        e("IC-19", "only a governed proxy may be used and it must never escape destination policy")
    if px.get("final_hop_enforcement") != "REQUIRED_AND_VERIFIED":
        e("IC-19", "governed proxy final-hop enforcement must be REQUIRED_AND_VERIFIED")
    if px.get("enforcement_evidence") != "GOVERNED_VERIFIABLE_EVIDENCE_REQUIRED":
        e("IC-19", "proxy final-hop enforcement needs governed, verifiable evidence (configuration alone is not trust)")
    if px.get("unverified_enforcement") != "DEPLOYMENT_BLOCKED":
        e("IC-19", "proxy egress without verified final-hop enforcement must be DEPLOYMENT_BLOCKED")
    if px.get("unverified_enforcement_outcome") != "POLICY_REJECTED":
        e("IC-19", "an unverified proxy lookup must be POLICY_REJECTED")
    if px.get("unverified_fallback") != "NONE":
        e("IC-19", "no fallback to trusting the proxy or skipping destination validation")
    if px.get("enforcement_scope_equivalent_to") != "DIRECT_CONNECTOR_DENIED_ADDRESS_AND_CONNECTION_BINDING_POLICY":
        e("IC-19", "proxy enforcement scope must equal the direct connector denied-address/connection-binding policy")
    need = set(REQ_CLASSES) | {cl.get("class") for cl in c.get("forbidden_destination_classes", [])
                               if isinstance(cl, dict)} | PROXY_BEHAVIOUR_SCOPE
    missing = need - set(px.get("enforcement_scope", []))
    if missing:
        e("IC-19", f"proxy final-hop enforcement scope weaker than the connector: missing {sorted(missing)}")
    if px.get("adapter_destination_validation_before_tunnel") != "REQUIRED" or \
            px.get("end_to_end_tls_to_provider") is not True:
        e("IC-19", "adapter must validate the provider destination before tunnelling; TLS end-to-end to the provider")
    if px.get("may_weaken_dns_or_redirect_authorization") is not False:
        e("IC-19", "a proxy must never weaken DNS or redirect authorization")
    if px.get("proxy_credentials") != "SEC_REFERENCE_ONLY":
        e("IC-19", "proxy credentials must be SEC references only")
    pfs = next((fs for fs in c.get("failure_semantics", []) if fs.get("condition") == "PROXY_ENFORCEMENT_UNVERIFIED"), {})
    if pfs.get("outcome") != "POLICY_REJECTED" or pfs.get("enrichment_status") != "REJECTED":
        e("IC-19", "PROXY_ENFORCEMENT_UNVERIFIED must be a POLICY_REJECTED / REJECTED failure")

    # IC-20 credentials
    cr = g("credentials", default={}) or {}
    if cr.get("model") != "REFERENCE_ONLY" or cr.get("store") != "SEC":
        e("IC-20", "credentials must be SEC references only")
    for f in CRED_FLAGS:
        if cr.get(f) is not False:
            e("IC-20", f"credentials.{f} must be false")
    if cr.get("rotation_period") != NYS:
        e("IC-20", "credential rotation period must be NOT YET SPECIFIED (no invented duration)")

    def cred_scan(node, path):
        if isinstance(node, dict):
            for k in node:
                if str(k).lower() in CRED_KEYS:
                    e("IC-20", f"credential-valued key {k!r} at {'/'.join(map(str, path)) or '<root>'}")
        elif isinstance(node, str) and CRED_LITERAL.search(node):
            e("IC-20", f"credential-like literal at {'/'.join(map(str, path))}")
    walk(c, cred_scan)

    # IC-21 headers
    hp = g("request_construction", "header_policy", default={}) or {}
    missing = REQ_HEADERS - set(hp.get("restricted_headers", []))
    if missing:
        e("IC-21", f"restricted headers missing: {sorted(missing)}")
    if hp.get("user_supplied_headers") != "REJECT" or hp.get("crlf_injection") != "REJECT":
        e("IC-21", "user-supplied headers and CRLF injection must be rejected")
    if hp.get("restricted_header_source") != "ADAPTER_GENERATED_GOVERNED_VALUE_ONLY":
        e("IC-21", "restricted headers must be adapter-generated governed values only")
    hdr = sorted(p for p in populate if HEADERISH.search(p))
    if hdr:
        e("IC-21", f"user input may populate network headers: {hdr}")

    # IC-22 least data outbound
    dm = g("data_minimization", default={}) or {}
    if dm.get("raw_evidence_outbound") is not False:
        e("IC-22", "raw evidence outbound must be false")
    missing = REQ_PROHIBITED - set(dm.get("outbound_prohibited", []))
    if missing:
        e("IC-22", f"outbound prohibitions missing: {sorted(missing)}")
    extra = set(dm.get("outbound_permitted", [])) - ALLOWED_OUTBOUND
    if extra:
        e("IC-22", f"outbound data beyond the minimum: {sorted(extra)}")
    uc = dm.get("url_components", {}) or {}
    if uc.get("userinfo") != "NEVER_SENT" or uc.get("fragment") != "NEVER_SENT":
        e("IC-22", "URL userinfo and fragment must never be sent")
    if dm.get("raw_evidence_change_requires") != "EXPLICIT_GOVERNED_CONTRACT_CHANGE_AND_PRIVACY_SECURITY_REVIEW":
        e("IC-22", "raw evidence outbound requires an explicit governed change + privacy/security review")
    if g("correlation", "internal_identifiers_outbound") is not False or g("correlation", "topology_disclosure") is not False:
        e("IC-22", "internal identifiers/topology must not be sent outbound")

    # IC-23 response validation
    rv = g("response_validation", default={}) or {}
    missing = REQ_RESPONSE_VALIDATE - set(rv.get("validate", []))
    if missing:
        e("IC-23", f"response validation omits {sorted(missing)}")
    if rv.get("provider_response_trust") != "UNTRUSTED_EXTERNAL_INPUT" or \
            rv.get("allowlisted_provider_content_trusted") is not False:
        e("IC-23", "provider responses are untrusted even from allowlisted providers")
    if rv.get("arbitrary_object_deserialization") is not False or rv.get("execute_provider_content") is not False:
        e("IC-23", "no arbitrary deserialization or execution of provider content")
    if rv.get("unknown_enum_value") != "INVALID_RESPONSE":
        e("IC-23", "unknown provider enum values must be INVALID_RESPONSE")

    # IC-24 response size
    lim = rv.get("limits", {}) or {}
    for f in ("wire_bytes", "decoded_bytes"):
        if not is_nys_limit(lim.get(f)):
            e("IC-24", f"response {f} must be FINITE with value NOT YET SPECIFIED and an owner")
    if lim.get("decompression") != "STREAMING_BOUNDED_ABORT_ON_LIMIT":
        e("IC-24", "decompression must be bounded (abort on limit)")

    # IC-25 timeouts
    for f in ("connect", "read", "overall_deadline"):
        if not is_nys_limit(g("timeouts", f)):
            e("IC-25", f"{f} timeout must be FINITE with value NOT YET SPECIFIED and an owner")
    if g("timeouts", "infinite_wait_permitted") is not False:
        e("IC-25", "infinite waiting must not be permitted")

    # IC-26 retries / backoff / rate limit
    rt = g("retries", default={}) or {}
    if rt.get("bounded") is not True or not is_nys_limit(rt.get("max_attempts")):
        e("IC-26", "retries must be bounded with max attempts NOT YET SPECIFIED (no invented count)")
    if rt.get("non_idempotent_blind_retry") is not False or \
            rt.get("retry_only_if") != "PROVIDER_POLICY_DECLARES_RETRY_SAFE_IDEMPOTENT_LOOKUP":
        e("IC-26", "only retry-safe idempotent lookups may be retried")
    if rt.get("retry_after") != "HONOURED_ONLY_WITHIN_BOUNDED_POLICY":
        e("IC-26", "Retry-After may be honoured only within the bounded policy")
    if g("backoff", "bounded") is not True or g("backoff", "values") != NYS:
        e("IC-26", "backoff must be bounded with values NOT YET SPECIFIED")
    if g("rate_limit", "http_429_outcome") != "UNAVAILABLE" or g("rate_limit", "indicator_safe_on_rate_limit") is not False \
            or g("rate_limit", "quota") != NYS:
        e("IC-26", "429 is UNAVAILABLE, never safe; no invented quota")
    if g("circuit_breaker", "thresholds") != NYS or g("circuit_breaker", "open_outcome") != "UNAVAILABLE":
        e("IC-26", "circuit breaker: no invented thresholds; open circuit is UNAVAILABLE")
    for fs in c.get("failure_semantics", []):
        if fs.get("retry") not in ("NONE", "GOVERNED_BOUNDED"):
            e("IC-26", f"failure {fs.get('condition')}: retry must be NONE or GOVERNED_BOUNDED")

    # IC-27 / IC-28 outcome safety
    mapping = {m.get("outcome"): m for m in g("outcomes", "mapping", default=[]) or []}
    nf = mapping.get("NOT_FOUND", {})
    if not nf or set(nf.get("reputation_result", [])) != {"UNKNOWN"} or "ALLOWLISTED" in nf.get("allowlist_result", []) \
            or set(nf.get("domain_matches_claimed_brand", [])) - {"UNKNOWN"}:
        e("IC-27", "NOT_FOUND must normalize only to reputation UNKNOWN (never CLEAN/ALLOWLISTED/MATCH)")
    for oc in FAILURE_OUTCOMES:
        m = mapping.get(oc, {})
        if not m or m.get("reputation_result") != ["NOT_EVALUATED"] or m.get("allowlist_result") != ["NOT_EVALUATED"] \
                or set(m.get("domain_matches_claimed_brand", [])) - {"UNKNOWN"} \
                or set(m.get("enrichment_status", [])) - {"FAILED", "TIMED_OUT", "REJECTED"}:
            e("IC-28", f"{oc} must map to a failure status with reputation/allowlist NOT_EVALUATED (never safe)")
    conds = {fs.get("condition"): fs for fs in c.get("failure_semantics", [])}
    missing = REQ_CONDITIONS - set(conds)
    if missing:
        e("IC-28", f"failure conditions undefined: {sorted(missing)}")
    for name, fs in conds.items():
        if fs.get("outcome") not in FAILURE_OUTCOMES:
            e("IC-28", f"failure {name} must be a failure outcome, got {fs.get('outcome')!r}")
        elif fs.get("enrichment_status") not in mapping.get(fs["outcome"], {}).get("enrichment_status", []):
            e("IC-28", f"failure {name}: status {fs.get('enrichment_status')!r} inconsistent with {fs['outcome']}")
    forbidden_meanings = REQ_FORBIDDEN_MEANINGS
    for m in mapping.values():
        for k in ("reputation_result", "allowlist_result", "domain_matches_claimed_brand", "enrichment_status"):
            hit = forbidden_meanings & set(m.get(k, []))
            if hit:
                code = "IC-27" if m.get("outcome") == "NOT_FOUND" else "IC-28"
                e(code, f"{m.get('outcome')} maps to a TrustLens verdict {sorted(hit)}")

    # IC-29 decision boundary
    db = g("decision_boundary", default={}) or {}
    if db.get("provider_may_set"):
        e("IC-29", f"provider may set nothing in the decision, got {db.get('provider_may_set')}")
    missing = REQ_NEVER_SET - set(db.get("provider_may_never_set", []))
    if missing:
        e("IC-29", f"provider_may_never_set omits {sorted(missing)}")
    missing = REQ_FORBIDDEN_MEANINGS - set(db.get("forbidden_result_meanings", []))
    if missing:
        e("IC-29", f"forbidden result meanings omit {sorted(missing)}")
    if db.get("consumed_in_governed_artifact") is not False or db.get("new_phase3_rule_or_observation") is not False:
        e("IC-29", "enrichment is not consumed and introduces no Phase-3 rule/observation")
    if db.get("phase3_sole_decision_authority") is not True:
        e("IC-29", "Phase-3 must remain the sole decision authority")
    if not {"VALIDATED_NORMALIZATION", "GOVERNED_MAPPING", "ACCEPTED_RULE_OBSERVATION_SEMANTICS"} <= set(
            db.get("future_decision_use_requires", [])):
        e("IC-29", "future decision use must require validated normalization + governed mapping + accepted semantics")
    if db.get("engine_version") != ctx["engine_version"] or ctx["engine_version"] != "1.0.0":
        e("IC-29", f"ENGINE_VERSION must remain 1.0.0 (engine {ctx['engine_version']!r})")

    # IC-30 no invented decision fields
    if "scam_probability" not in db.get("forbidden_invented_fields", []):
        e("IC-30", "scam_probability must be declared forbidden")

    def invented_scan(node, path):
        if path and path[0] == "decision_boundary":
            return
        if isinstance(node, dict):
            for k in node:
                if k not in INVENTED_ALLOWED_KEYS and INVENTED.search(str(k)):
                    e("IC-30", f"invented decision key {k!r} at {'/'.join(map(str, path)) or '<root>'}")
    walk(c, invented_scan)
    field_names = [f for o in c.get("integration_objects", []) for f in o.get("fields", [])]
    field_names += [p.get("field", "") for p in g("provenance", "required_fields", default=[]) or []]
    field_names += list(g("cache", "key_components", default=[]) or [])
    field_names += list(g("persistence_additive_requirements", default=[]) or [])
    hits = sorted({f for f in field_names if isinstance(f, str) and INVENTED.search(f)})
    if hits:
        e("IC-30", f"invented score/probability/confidence/risk fields: {hits}")

    # IC-31 provenance
    prov = g("provenance", "required_fields", default=[]) or []
    names = {p.get("field") for p in prov}
    missing = REQ_PROVENANCE - names
    if missing:
        e("IC-31", f"provenance omits {sorted(missing)}")
    additive = set(g("persistence_additive_requirements", default=[]) or [])
    cols = ctx["wp2_columns"]
    for p in prov:
        dest = str(p.get("persistence", ""))
        if dest.startswith("external_enrichment_result."):
            if dest.split(".", 1)[1] not in cols:
                e("IC-31", f"provenance {p.get('field')}: WP2 column {dest!r} does not exist")
        elif dest == "ADDITIVE_WP2_REVISION_REQUIRED":
            if p.get("field") not in additive:
                e("IC-31", f"provenance {p.get('field')}: additive WP2 requirement not recorded")
        else:
            e("IC-31", f"provenance {p.get('field')}: persistence target {dest!r} invalid")
    if g("provenance", "raw_indicator_in_telemetry") is not False:
        e("IC-31", "raw indicator must not be required in telemetry")

    # IC-32 cache
    ca = g("cache", default={}) or {}
    if ca.get("permitted") != "GOVERNED_ONLY":
        e("IC-32", "cache must be governed-only")
    missing = REQ_CACHE_KEY - set(ca.get("key_components", []))
    if missing:
        e("IC-32", f"cache key omits {sorted(missing)} (semantic collision)")
    missing = REQ_CACHE_ENTRY - set(ca.get("entry_requires", []))
    if missing:
        e("IC-32", f"cache entries lack {sorted(missing)}")
    if ca.get("ttl") != NYS:
        e("IC-32", "cache TTL must be NOT YET SPECIFIED (no invented TTL)")
    if ca.get("cache_use_recorded") is not True:
        e("IC-32", "cache use must be recorded")
    iso = ca.get("case_isolation", {}) or {}
    if iso.get("case_identity_in_cache") is not False or iso.get("evidence_in_cache") is not False or \
            iso.get("case_linkage") != "SEPARATE_PER_EVALUATION_RECORD":
        e("IC-32", "cache must not carry case identity/evidence; case linkage stays per evaluation")

    # IC-33 freshness
    if ca.get("stale_presented_as_fresh") is not False:
        e("IC-33", "stale cache must never be presented as fresh")
    fr = g("freshness", default={}) or {}
    if fr.get("states") != ["FRESH", "STALE", "UNKNOWN"]:
        e("IC-33", "freshness states must be FRESH/STALE/UNKNOWN")
    if fr.get("is_confidence") is not False or fr.get("is_risk") is not False:
        e("IC-33", "freshness is neither confidence nor risk")
    if fr.get("period") != NYS:
        e("IC-33", "freshness period must be NOT YET SPECIFIED")

    # IC-34..IC-37 replay / re-analysis
    hist = g("replay", "historical", default={}) or {}
    for f in ("provider_call", "refetch", "refresh"):
        if hist.get(f) is not False:
            e("IC-34", f"historical replay {f} must be false")
    for f in ("use_newest_provider_response", "use_latest_provider_policy", "replace_stale", "ai_substitute"):
        if hist.get(f) is not False:
            e("IC-35", f"historical replay {f} must be false")
    if hist.get("uses") != "EXACT_RETAINED_ARTIFACT_AND_PINNED_POLICY_ADAPTER_PARSER_IDENTITY" or \
            g("policy_authority", "unpinned_latest_in_replay") is not False:
        e("IC-35", "replay must use the exact retained artifact and pinned policy/adapter/parser identity")
    if hist.get("missing_material") != "REPLAY_UNAVAILABLE" or hist.get("approximation") is not False:
        e("IC-36", "missing enrichment material must make replay unavailable (no approximation)")
    if g("retention", "deletion_makes_replay_unavailable") is not True:
        e("IC-36", "governed deletion must be acknowledged to make replay unavailable")
    ra = g("replay", "reanalysis", default={}) or {}
    if ra.get("new_provider_call_permitted") is not True or ra.get("creates") != "NEW_ENRICHMENT_RECORD" or \
            ra.get("overwrite_historical") is not False:
        e("IC-37", "re-analysis may call under current policy, creates a new record and never overwrites history")

    # IC-38 CI offline
    ci = g("ci", default={}) or {}
    for f in ("live_network", "dns_lookups", "http_requests", "real_provider_calls", "api_keys_required"):
        if ci.get(f) is not False:
            e("IC-38", f"canonical CI {f} must be false")
    fx = g("conformance_scenarios", "fixture_provider", default={}) or {}
    if fx.get("fictional") is not True or not str(fx.get("host", "")).endswith(".example"):
        e("IC-38", "conformance fixture provider must be fictional under a reserved .example name")
    if HTTP_CLIENT_DEPS.search(ctx["requirements"]):
        e("IC-38", "an HTTP client dependency is present in requirements.txt")
    if NETWORK_IMPORT.search(ctx["self_source"]):
        e("IC-38", "the integration validator imports a network module")

    # IC-39 tenancy
    def tenant_scan(node, path):
        if path and path[0] == "tenancy":
            return
        if isinstance(node, dict):
            for k in node:
                if TENANT.search(str(k)):
                    e("IC-39", f"tenant key {k!r} at {'/'.join(map(str, path)) or '<root>'}")
        elif isinstance(node, str) and len(path) >= 2 and path[-2] in ("fields", "key_components", "forbidden_fields",
                                                                        "never_user_controlled") \
                and TENANT.search(node):
            e("IC-39", f"tenant field {node!r} at {'/'.join(map(str, path))}")
    walk(c, tenant_scan)
    if g("tenancy", "tenant_specific_provider_config") is not False or \
            g("tenancy", "assumption_status") != "UNCONFIRMED / PROVISIONAL":
        e("IC-39", "no tenant-specific provider config; ASM-002 stays UNCONFIRMED / PROVISIONAL")

    # IC-40 ADR topic / index
    if g("adr", "id") != "ADR-0012" or g("adr", "reserved_title") != RESERVED_TITLE:
        e("IC-40", "ADR-0012 must keep the reserved topic 'Threat-intelligence adapter architecture and provider selection'")
    if adr_text and RESERVED_TITLE not in adr_text.splitlines()[0]:
        e("IC-40", "ADR-0012 title must carry the reserved topic")
    if not {"SSRF", "DNS_REBINDING_TOCTOU", "REDIRECT_HANDLING", "EGRESS_TRUST_BOUNDARY"} <= set(
            g("adr", "decision_area", default=[]) or []):
        e("IC-40", "ADR-0012 decision area must cover SSRF, DNS rebinding/TOCTOU, redirects and the egress boundary")
    idx = ctx["adr_index"]
    row = re.search(r"^\|\s*\[ADR-0012\]\(([^)]+)\)\s*\|\s*([^|]+)\|\s*(Proposed|Accepted)\s*\|", idx, re.M)
    section = re.findall(r"^## (\w+)", idx[:row.start()], re.M)[-1] if row else None
    if not row or row.group(1) != Path(str(g("adr", "path", default=""))).name or RESERVED_TITLE not in row.group(2) \
            or row.group(3) != adr_status or section != adr_status:
        e("IC-40", "adr/README.md must list ADR-0012 with the reserved title, correct link and the contract status, "
                   "under the matching status section")
    planned = idx.split("## Planned", 1)[1].split("**Numbering note.**", 1)[0] if "## Planned" in idx else ""
    if re.search(r"^\|\s*ADR-0012\s*\|", planned, re.M):
        e("IC-40", "ADR-0012 must no longer be listed as Planned")

    # IC-41 / IC-42 open items
    if g("open_items", "G-09") != "OPEN" or not re.search(r"G-09[^\n]{0,40}OPEN", int_text) \
            or not re.search(r"G-09[^\n]{0,40}OPEN", gate_text):
        e("IC-41", "G-09 must remain OPEN (contract, INT-001 and GATE-023)")
    if g("open_items", "OI-05") != "OPEN" or g("retention", "duration") != NYS or \
            not re.search(r"OI-05[^\n]{0,40}OPEN", int_text) or not re.search(r"OI-05[^\n]{0,40}OPEN", gate_text):
        e("IC-42", "OI-05 must remain OPEN with no retention duration (contract, INT-001 and GATE-023)")

    # IC-43 provider policy authority + binding
    pa = g("policy_authority", default={}) or {}
    if pa.get("authority") != "GOVERNED_OPERATOR_CONFIGURATION":
        e("IC-43", "provider policy authority must be governed operator configuration")
    missing = REQ_POLICY_IMMUTABLE_BY - set(pa.get("may_not_change", []))
    if missing:
        e("IC-43", f"parties not barred from changing provider policy: {sorted(missing)}")
    if pa.get("versioned") is not True or pa.get("immutable_per_version") is not True:
        e("IC-43", "provider policy must be versioned and immutable per version")
    pol = obj(c, "ExternalProviderPolicy")
    missing = REQ_POLICY_BINDING - set(pol.get("fields", []))
    if missing:
        e("IC-43", f"provider policy does not bind {sorted(missing)}")
    if CRED_KEYS & {f.lower() for f in pol.get("fields", [])}:
        e("IC-43", "provider policy carries a credential value field")

    # IC-44 indicator types
    url_obs = ctx["url_obs"]
    seen = set()
    for it in g("indicator_types", "permitted", default=[]) or []:
        t = it.get("type")
        seen.add(t)
        if t not in INDICATOR_AUTHORITY:
            e("IC-44", f"indicator type {t!r} has no accepted authority")
        src = str(it.get("source", ""))
        ref, _, ptr = src.partition("#")
        node = url_obs if ref == "knowledge/schemas/url-observation.schema.json" else None
        for part in [p for p in ptr.split("/") if p]:
            node = node.get(part) if isinstance(node, dict) else None
        if node is None:
            e("IC-44", f"indicator type {t!r} source {src!r} does not resolve")
        if it.get("classification") != "C4":
            e("IC-44", f"indicator type {t!r} outbound value must be classified C4")
    np_ = set(g("indicator_types", "not_permitted", default=[]) or [])
    if not REQ_NOT_PERMITTED <= np_ or seen & np_:
        e("IC-44", "phone/UPI/bank/email/device indicator kinds must be listed as not permitted")

    # IC-45 vocabulary + column parity with WP2
    voc = ctx["wp2_vocab"]
    if g("outcomes", "vocabulary") != OUTCOMES:
        e("IC-45", f"outcome vocabulary must be exactly {OUTCOMES}")
    if set(mapping) != set(OUTCOMES):
        e("IC-45", "every outcome must have exactly one mapping")
    keymap = {"enrichment_status": "enrichment_status", "reputation_result": "reputation_result",
              "allowlist_result": "allowlist_result", "domain_matches_claimed_brand": "domain_brand_match"}
    for m in mapping.values():
        for k, vname in keymap.items():
            bad = set(m.get(k, [])) - set(voc.get(vname, []))
            if bad:
                e("IC-45", f"{m.get('outcome')}.{k} uses values outside WP2 vocabulary {vname}: {sorted(bad)}")
    if g("outcomes", "not_attempted_status") != "NOT_EVALUATED":
        e("IC-45", "a not-attempted enrichment is NOT_EVALUATED")
    res = obj(c, "ExternalEnrichmentResult")
    if res.get("persistence_table") != "external_enrichment_result" or set(res.get("fields", [])) - cols:
        e("IC-45", f"ExternalEnrichmentResult fields not in WP2 table: {sorted(set(res.get('fields', [])) - cols)}")
    if g("related_contracts", "persistence_table") != "external_enrichment_result":
        e("IC-45", "persistence table must be the accepted external_enrichment_result")

    # IC-46 API surface
    api = g("api_surface", default={}) or {}
    if api.get("new_endpoints") or g("scope", "public_api_endpoints_added"):
        e("IC-46", "no public API endpoint may be added by P6-WP5")
    op = ctx["catalog_op"]
    if not op or op.get("availability") != "FUTURE_INT_001" or api.get("existing_operation") != op.get("operation_id") \
            or api.get("path") != op.get("path") or not ctx["openapi_has_op"]:
        e("IC-46", "the reserved listEvaluationEnrichments operation must exist unchanged (FUTURE_INT_001) in API/OpenAPI")
    if set((api.get("enrichment_view_mapping") or {})) != ctx["enrichment_view_fields"]:
        e("IC-46", "enrichment_view_mapping must cover exactly the accepted EnrichmentView fields")

    # IC-47 provider neutrality
    if g("provider_selection", "provider_selected") is not False or g("provider_selection", "providers"):
        e("IC-47", "no provider may be selected in P6-WP5")

    def vendor_scan(node, path):
        if isinstance(node, str) and VENDORS.search(node):
            e("IC-47", f"vendor named at {'/'.join(map(str, path))}: {VENDORS.search(node).group(0)!r}")
        elif isinstance(node, dict):
            for k in node:
                if VENDORS.search(str(k)):
                    e("IC-47", f"vendor-named key {k!r}")
    walk(c, vendor_scan)
    for label, text in (("INT-001", int_text), ("GATE-023", gate_text), ("ADR-0012", adr_text)):
        m = VENDORS.search(text)
        if m:
            e("IC-47", f"{label} names a vendor: {m.group(0)!r}")

    # IC-48 no numeric invention
    def num_scan(node, path):
        if isinstance(node, bool):
            return
        if isinstance(node, (int, float)) and tuple(path) not in NUMERIC_EXEMPT:
            e("IC-48", f"numeric value {node!r} at {'/'.join(map(str, path))} (no invented limits)")
        if isinstance(node, dict):
            for k in ("value", "ttl", "period", "quota", "thresholds", "values", "duration", "rotation_period"):
                if k in node and node[k] != NYS:
                    e("IC-48", f"{'/'.join(map(str, path + (k,)))} must be NOT YET SPECIFIED, got {node[k]!r}")
    walk(c, num_scan)

    # IC-49 audit / telemetry / logging / classification
    au = g("audit", default={}) or {}
    if au.get("separate_from_telemetry") is not True:
        e("IC-49", "audit must stay separate from telemetry")
    concepts = {ev.get("concept"): ev for ev in au.get("events", [])}
    for need in ("ENRICHMENT_REQUESTED", "PROVIDER_POLICY_SELECTED", "POLICY_REJECTION", "ENRICHMENT_ACCEPTED",
                 "CREDENTIAL_REFERENCE_FAILURE", "SSRF_DESTINATION_REJECTION"):
        if need not in concepts:
            e("IC-49", f"audit event concept {need} missing")
    for ev in concepts.values():
        t = ev.get("audit_event_type")
        if t is not None and t not in voc.get("audit_event_type", []):
            e("IC-49", f"audit event type {t!r} not in WP2 audit_event_type")
        if t is None and ev.get("persistence") != "ADDITIVE_WP2_REVISION_REQUIRED":
            e("IC-49", f"audit concept {ev.get('concept')} without a WP2 type must be an additive requirement")
    for need in ("POLICY_REJECTION", "SSRF_DESTINATION_REJECTION"):
        if concepts.get(need, {}).get("audit_event_type") != "EGRESS_DENIED":
            e("IC-49", f"{need} must map to the existing EGRESS_DENIED audit event")
    if not {"CREDENTIAL_VALUE", "AUTHORIZATION_HEADER", "RAW_EVIDENCE"} <= set(au.get("forbidden_content", [])):
        e("IC-49", "audit must exclude credentials, authorization headers and raw evidence")
    tel = g("telemetry", default={}) or {}
    if set(tel.get("permitted", [])) - TELEMETRY_ALLOWED:
        e("IC-49", f"telemetry carries more than operational signals: {sorted(set(tel.get('permitted', [])) - TELEMETRY_ALLOWED)}")
    if REQ_TELEMETRY_FORBIDDEN - set(tel.get("forbidden", [])) or tel.get("classification") != "C8":
        e("IC-49", "telemetry must forbid credentials/raw evidence/raw indicator and be C8")
    if REQ_LOG_FORBIDDEN - set(g("logging", "forbidden", default=[]) or []):
        e("IC-49", "logs must exclude API keys, authorization headers, credentials and raw evidence")
    cls = {x.get("datum"): x.get("class") for x in c.get("classification", [])}
    for datum, want in REQ_CLASSIFICATION.items():
        if cls.get(datum) != want:
            e("IC-49", f"classification of {datum} must be {want}, got {cls.get(datum)!r}")

    # IC-50 artifact integrity vs authenticity
    art = g("response_artifact", default={}) or {}
    if art.get("immutable") is not True or art.get("digest_proves") != "WHAT_TRUSTLENS_RECORDED":
        e("IC-50", "response artifact must be immutable; digest proves only what TrustLens recorded")
    if not {"PROVIDER_TRUTH", "PROVIDER_AUTHENTICITY"} <= set(art.get("digest_does_not_prove", [])):
        e("IC-50", "digest must not be claimed as provider truth or authenticity")
    pauth = art.get("provider_authenticity", {}) or {}
    if pauth.get("signed_assertion") != "NOT_ASSUMED" or pauth.get("transport") != "TLS_WEB_PKI_ENDPOINT_AUTHENTICATION":
        e("IC-50", "transport authentication must not be overclaimed as a signed provider assertion")

    # IC-51 conformance scenarios through the reference decision model
    try:
        scen = g("conformance_scenarios", "scenarios", default=[]) or []
        names = " ".join(s.get("name", "").lower() for s in scen)
        for need in REQ_SCENARIO_NAMES:
            if need not in names.replace("rfc 1918", "rfc1918"):
                e("IC-51", f"required conformance scenario missing: {need}")
        if not any(s.get("expected") == "PERMITTED" for s in scen):
            e("IC-51", "a permitted control scenario is required (proves the model is not trivially rejecting)")
        for s in scen:
            got = evaluate(s, c)
            if got != s.get("expected"):
                e("IC-51", f"{s.get('id')} '{s.get('name')}': contract policy yields {got}, expected {s.get('expected')}")
    except (KeyError, TypeError, AttributeError) as ex:
        e("IC-51", f"conformance scenarios cannot be evaluated: {ex!r}")

    return errs


def _select(node, seg):
    if isinstance(seg, dict):
        (k, v), = seg.items()
        for i, item in enumerate(node):
            if isinstance(item, dict) and item.get(k) == v:
                return i
        raise KeyError(f"no element with {k}={v!r}")
    return seg


def apply_mutation(doc: dict, m: dict) -> dict:
    c = copy.deepcopy(doc)
    node = c
    for seg in m["path"][:-1]:
        node = node[_select(node, seg)]
    last = _select(node, m["path"][-1])
    if m["op"] == "set":
        node[last] = copy.deepcopy(m["value"])
    elif m["op"] == "append":
        node[last].append(copy.deepcopy(m["value"]))
    elif m["op"] == "remove":
        del node[last]
    else:
        raise ValueError(f"unknown op {m['op']}")
    return c


def context() -> dict:
    schema = load(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    persistence, catalog, openapi = load(PERSISTENCE_PATH), load(CATALOG_PATH), load(OPENAPI_PATH)
    table = next(t for t in persistence["tables"] if t["name"] == "external_enrichment_result")
    op = next((o for o in catalog["operations"] if o.get("operation_id") == "listEvaluationEnrichments"), None)
    view = catalog["schemas"].get("EnrichmentView", {"fields": []})
    oas_op = (openapi.get("paths", {}).get("/api/v1/evaluations/{evaluation_id}/enrichments", {}) or {}).get("get", {})
    eng = re.search(r'ENGINE_VERSION\s*=\s*"([^"]+)"', ENGINE_PATH.read_text(encoding="utf-8"))
    return {
        "validator": Draft202012Validator(schema),
        "wp2_columns": {col["name"] for col in table["columns"]},
        "wp2_vocab": {k: v["values"] for k, v in persistence["vocabularies"].items()},
        "catalog_op": op,
        "openapi_has_op": oas_op.get("operationId") == "listEvaluationEnrichments",
        "enrichment_view_fields": {f["name"] for f in view["fields"]},
        "url_obs": load(URL_OBS_PATH),
        "adr_index": read(ADR_INDEX_PATH),
        "int_text": read(INT_DOC_PATH),
        "gate_text": read(GATE_PATH),
        "requirements": read(REQUIREMENTS_PATH),
        "self_source": Path(__file__).read_text(encoding="utf-8"),
        "engine_version": eng.group(1) if eng else None,
    }


def main() -> int:
    quiet = "--quiet" in sys.argv
    try:
        ctx = context()
    except (SchemaError, StopIteration, OSError, json.JSONDecodeError) as ex:
        print(f"  FAIL  IC-01  integration contract inputs unreadable or schema invalid: {ex!r}")
        print("INTEGRATION CONTRACT: FAIL")
        return 1
    contract = load(CONTRACT_PATH)
    errs = check(contract, ctx)
    if errs:
        for code, msg in errs:
            print(f"  FAIL  {code}  {msg}")
        print(f"INTEGRATION CONTRACT: FAIL — {len(errs)} violation(s) in {CONTRACT_PATH.relative_to(ROOT)}")
        return 1
    negatives = load(NEGATIVE_PATH)["mutations"]
    failures = []
    for m in negatives:
        try:
            mutated = apply_mutation(contract, m)
        except (KeyError, IndexError, ValueError, TypeError) as ex:
            failures.append(f"{m['id']}: mutation could not be applied ({ex})")
            continue
        found = {code for code, _ in check(mutated, ctx)}
        if m["expect"] not in found:
            failures.append(f"{m['id']}: expected {m['expect']}, got {sorted(found) or 'no violation'}")
        elif not quiet:
            print(f"  ok    {m['id']} rejected by {m['expect']}: {m['description']}")
    if failures:
        for f in failures:
            print(f"  FAIL  negative fixture {f}")
        print("INTEGRATION CONTRACT: FAIL — a guard did not bite")
        return 1
    n_sc = len(contract["conformance_scenarios"]["scenarios"])
    print(f"INTEGRATION CONTRACT: PASS — INT-001 {contract['contract_version']} provider-neutral indicator-lookup policy "
          f"(deny-by-default egress, governed destinations, DNS/connect binding, redirect revalidation, decision "
          f"boundary, no-refetch replay); {n_sc} offline conformance scenarios; {len(negatives)} negative mutations "
          f"rejected (static contract validation; no connector exists and no network is used)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
