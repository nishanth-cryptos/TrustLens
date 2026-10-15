"""S7 governed indicator-lookup egress boundary (INT-001, ADR-0012). Provider-neutral and deny-by-default.

The adapter sends ONE normalized indicator (URL, hostname or registered domain) as DATA to ONE destination declared by an
immutable, digest-identified provider policy. It never connects to, resolves, downloads or follows a submitted URL, has no
generic fetch primitive, and takes no destination, method, header, proxy or TLS choice from user, evidence, AI or provider
input. Each attempt follows INT-001 dns.steps:

  canonicalize the governed host -> resolve through the governed resolver -> validate EVERY answer (one bad answer rejects
  the lookup) -> connect only to a validated address, with SNI and certificate verification against the approved hostname
  -> verify the connected peer address -> validate the response (status, media type, wire and decoded size, schema, enums,
  timestamp, provider identity, parser version).

Redirects are refused unless the pinned policy allows REVALIDATE_WITHIN_PROVIDER_ALLOWLIST, and then every hop is a new
destination decision. A governed proxy is refused (PROXY_ENFORCEMENT_UNVERIFIED) unless its final-hop enforcement evidence
is verified, and the shipped transport has no proxy support at all. Environment proxies are never read. Credentials are
references resolved at call time; their values never leave the request headers.

The numeric limits are a LOCAL TEST PROFILE: finite and enforced, but NOT approved values (INT-001 / OPS-001: owned by
P6-WP6 / T09 / implementation security profile). No live provider is selected, so the feature is disabled by default.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import ssl
import time
import uuid
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Mapping, Protocol
from urllib.parse import quote, urljoin, urlsplit

from knowledge.ai.governance import canonical_json

ADAPTER_VERSION = "1.0.0"
INTEGRATION_CONTRACT_VERSION = "0.1.0"                  # INT-001 contract_version
USER_AGENT = f"TrustLens-IndicatorLookup/{ADAPTER_VERSION}"
INDICATOR_TYPES = ("URL", "HOSTNAME", "REGISTERED_DOMAIN")
PROVIDER_CATEGORIES = ("REPUTATION_LOOKUP", "ALLOWLIST_LOOKUP", "BRAND_DOMAIN_LOOKUP")
REDIRECT_POLICIES = ("DO_NOT_FOLLOW", "REVALIDATE_WITHIN_PROVIDER_ALLOWLIST")
METHODS = ("GET", "POST")
AUTH_HEADERS = ("Authorization", "X-Api-Key")         # adapter-generated only, from a credential reference
RAW_CONTENT_POLICY = "NO_RAW_PROVIDER_CONTENT_RETAINED"


@dataclass(frozen=True)
class Limits:
    """Finite bounds for every wait, size, retry and redirect (OPS-001 runtime_parameters: none may be infinite)."""
    connect_timeout: float
    read_timeout: float
    overall_deadline: float
    max_attempts: int
    backoff_initial: float
    backoff_max: float
    max_redirect_hops: int
    wire_max_bytes: int
    decoded_max_bytes: int

    def __post_init__(self):
        for name in ("connect_timeout", "read_timeout", "overall_deadline", "backoff_initial", "backoff_max"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not 0 < value < 600:
                raise ValueError(f"{name} must be finite and positive")
        for name in ("max_attempts", "max_redirect_hops", "wire_max_bytes", "decoded_max_bytes"):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0 or value > 10 * 1024 * 1024:
                raise ValueError(f"{name} must be a bounded integer")
        if self.max_attempts < 1 or self.backoff_initial > self.backoff_max:
            raise ValueError("attempts and backoff must be bounded and ordered")


# LOCAL TEST PROFILE ONLY — not production-approved values (T09 / P6-WP6 own the real ones).
LOCAL_TEST_PROFILE = Limits(connect_timeout=3.0, read_timeout=5.0, overall_deadline=10.0, max_attempts=2, backoff_initial=0.2,
                            backoff_max=1.0, max_redirect_hops=2, wire_max_bytes=32 * 1024, decoded_max_bytes=64 * 1024)


# ================================================================ outcomes (INT-001 outcomes / failure_semantics)
@dataclass(frozen=True)
class Failure:
    outcome: str
    status: str
    category: str
    retry: bool


FAILURES = {
    "DNS_FAILURE": Failure("UNAVAILABLE", "FAILED", "DNS_FAILURE", True),
    "CONNECTION_FAILURE": Failure("UNAVAILABLE", "FAILED", "CONNECTION_FAILURE", True),
    "TLS_FAILURE": Failure("UNAVAILABLE", "FAILED", "TLS_FAILURE", False),
    "TIMEOUT": Failure("UNAVAILABLE", "TIMED_OUT", "TIMEOUT", True),
    "PROVIDER_CLIENT_ERROR": Failure("UNAVAILABLE", "FAILED", "PROVIDER_CLIENT_ERROR", False),
    "PROVIDER_SERVER_ERROR": Failure("UNAVAILABLE", "FAILED", "PROVIDER_SERVER_ERROR", True),
    "RATE_LIMITED": Failure("UNAVAILABLE", "FAILED", "RATE_LIMITED", True),
    "INVALID_CONTENT_TYPE": Failure("INVALID_RESPONSE", "FAILED", "INVALID_CONTENT_TYPE", False),
    "OVERSIZED_RESPONSE": Failure("INVALID_RESPONSE", "FAILED", "OVERSIZED_RESPONSE", False),
    "DECOMPRESSION_LIMIT_EXCEEDED": Failure("INVALID_RESPONSE", "FAILED", "DECOMPRESSION_LIMIT_EXCEEDED", False),
    "SCHEMA_INVALID_RESPONSE": Failure("INVALID_RESPONSE", "FAILED", "SCHEMA_INVALID_RESPONSE", False),
    "POLICY_REJECTION": Failure("POLICY_REJECTED", "REJECTED", "POLICY_REJECTION", False),
    "REDIRECT_POLICY_REJECTION": Failure("POLICY_REJECTED", "REJECTED", "REDIRECT_POLICY_REJECTION", False),
    "DESTINATION_ADDRESS_REJECTION": Failure("POLICY_REJECTED", "REJECTED", "DESTINATION_ADDRESS_REJECTION", False),
    "PROXY_ENFORCEMENT_UNVERIFIED": Failure("POLICY_REJECTED", "REJECTED", "PROXY_ENFORCEMENT_UNVERIFIED", False),
    "CREDENTIAL_UNAVAILABLE": Failure("UNAVAILABLE", "FAILED", "CREDENTIAL_UNAVAILABLE", False),
    "PROVIDER_UNAVAILABLE": Failure("UNAVAILABLE", "FAILED", "PROVIDER_UNAVAILABLE", False),
}


class Refused(Exception):
    """A governed refusal or failure with its INT-001 safe category. Messages never carry indicator or credential values."""

    def __init__(self, category: str, response_category: str = "NO_RESPONSE"):
        super().__init__(category)
        self.category = category
        self.response_category = response_category


@dataclass(frozen=True)
class LookupResult:
    """The normalized, provider-neutral outcome. Never a TrustLens classification; CLEAN is only a provider assertion."""
    outcome: str
    status: str
    safe_error_category: str | None
    provider_response_category: str
    reputation_result: str
    allowlist_result: str
    domain_matches_claimed_brand: str
    responded_at: datetime | None
    artifact: Mapping | None                 # normalized payload TrustLens recorded (FOUND / NOT_FOUND only)
    attempts: int

    @property
    def artifact_digest(self) -> str | None:
        return hashlib.sha256(canonical_json(self.artifact).encode()).hexdigest() if self.artifact is not None else None


def _failed(category: str, response_category: str, attempts: int, responded_at=None) -> LookupResult:
    f = FAILURES[category]
    return LookupResult(f.outcome, f.status, f.category, response_category, "NOT_EVALUATED", "NOT_EVALUATED", "UNKNOWN",
                        responded_at, None, attempts)


# ================================================================ address and destination policy
_EMBEDDED_V4 = [ipaddress.ip_network(n) for n in ("::ffff:0:0/96", "::/96", "64:ff9b::/96", "2002::/16", "2001::/32")]
_DENIED = [ipaddress.ip_network(n) for n in (
    "127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "224.0.0.0/4", "0.0.0.0/8",
    "100.64.0.0/10", "192.0.0.0/24", "192.0.2.0/24", "198.18.0.0/15", "198.51.100.0/24", "203.0.113.0/24", "240.0.0.0/4",
    "255.255.255.255/32", "::1/128", "fe80::/10", "ff00::/8", "::/128", "100::/64", "2001:db8::/32", "fc00::/7")]
METADATA = [ipaddress.ip_address("169.254.169.254")]


def address_permitted(text: str, extra_metadata: tuple = ()) -> bool:
    """INT-001 forbidden_destination_classes with PARSED_IP_SEMANTICS: only a strictly parsed, globally reachable unicast
    address that is in no denied class passes. Alternate encodings, IPv4-embedded IPv6 forms and anything the IANA
    special-purpose registries do not mark global are rejected."""
    try:
        address = ipaddress.ip_address(text)
    except (ValueError, TypeError):
        return False                                       # unclassifiable_address: REJECT
    if address.version == 6:
        if address.scope_id is not None or any(address in n for n in _EMBEDDED_V4) or address.ipv4_mapped is not None:
            return False
    if any(address.version == n.version and address in n for n in _DENIED):
        return False
    if address in METADATA or address in [ipaddress.ip_address(a) for a in extra_metadata]:
        return False
    return address.is_global and not address.is_multicast


_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def canonical_host(host) -> str:
    """INT-001 destination_validation.hostname_canonicalization: lowercase, one trailing dot stripped, IDNA A-labels,
    no userinfo, no encoded delimiters, no IP literal, nothing ambiguous."""
    if not isinstance(host, str) or not host or len(host) > 253:
        raise Refused("POLICY_REJECTION")
    if any(c in host for c in "@%\\/?#[]: \t\r\n") or any(ord(c) < 0x21 for c in host):
        raise Refused("POLICY_REJECTION")
    name = host[:-1] if host.endswith(".") else host
    try:
        name = name.encode("idna").decode("ascii").lower()
    except UnicodeError:
        raise Refused("POLICY_REJECTION") from None
    labels = name.split(".")
    if len(labels) < 2 or not all(_LABEL.match(label) for label in labels) or labels[-1].isdigit():
        raise Refused("POLICY_REJECTION")                  # single labels and numeric TLDs could be IP encodings
    try:
        ipaddress.ip_address(name)
        raise Refused("POLICY_REJECTION")                  # ip_literal_destinations: REJECT
    except ValueError:
        pass
    return name


# ================================================================ governed provider policy
@dataclass(frozen=True)
class ProxyPolicy:
    host: str
    port: int
    final_hop_enforcement_verified: bool


@dataclass(frozen=True)
class ProviderPolicy:
    """INT-001 ExternalProviderPolicy, immutable per version and identified by the SHA-256 of its canonical document."""
    provider_policy_ref: str
    provider_policy_version: str
    provider_ref: str
    provider_category: str
    provider_operation: str
    indicator_type: str
    scheme: str
    host: str
    port: int
    path_prefix: str
    method: str
    indicator_parameter: str
    expected_media_type: str
    parser_schema_version: str
    redirect_policy: str
    url_query_transmission: str
    retry_safe: bool
    enabled: bool
    authentication_header: str | None = None
    credential_ref: str | None = None
    freshness_policy_ref: str | None = None
    raw_provider_content_policy_ref: str = RAW_CONTENT_POLICY
    proxy: ProxyPolicy | None = None
    document: Mapping = field(default_factory=dict, compare=False, repr=False)

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_json(dict(self.document)).encode()).hexdigest()


_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")
_POLICY_FIELDS = {"provider_policy_ref", "provider_policy_version", "provider_ref", "provider_category", "provider_operation",
                  "indicator_type", "scheme", "host", "port", "path_prefix", "method", "indicator_parameter", "expected_media_type",
                  "parser_schema_version", "redirect_policy", "url_query_transmission", "retry_safe", "enabled",
                  "authentication_header", "credential_ref", "freshness_policy_ref", "raw_provider_content_policy_ref", "proxy"}


def load_policy(document: Mapping) -> ProviderPolicy:
    """Validate a governed policy document strictly; anything unknown, ambiguous or outside INT-001 is refused."""
    if not isinstance(document, Mapping) or set(document) - _POLICY_FIELDS:
        raise ValueError("provider policy has unknown or missing fields")
    d = dict(document)
    for key in ("provider_policy_ref", "provider_policy_version", "provider_ref", "provider_operation", "parser_schema_version",
                "indicator_parameter"):
        if not isinstance(d.get(key), str) or not _REF.match(d[key]):
            raise ValueError(f"provider policy {key} is not a governed reference")
    if d.get("scheme") != "https" or d.get("method") not in METHODS or d.get("indicator_type") not in INDICATOR_TYPES \
            or d.get("provider_category") not in PROVIDER_CATEGORIES or d.get("redirect_policy") not in REDIRECT_POLICIES \
            or d.get("url_query_transmission") not in ("PERMITTED", "NOT_PERMITTED") or d.get("expected_media_type") != "application/json":
        raise ValueError("provider policy violates INT-001 transport, method or vocabulary rules")
    if not isinstance(d.get("port"), int) or not 1 <= d["port"] <= 65535 or not isinstance(d.get("retry_safe"), bool) \
            or not isinstance(d.get("enabled"), bool):
        raise ValueError("provider policy port or flags are invalid")
    path = d.get("path_prefix")
    if not isinstance(path, str) or not path.startswith("/") or any(c in path for c in "?#%\\ \r\n@") or ".." in path:
        raise ValueError("provider policy path_prefix is not a fixed absolute path")
    try:
        host = canonical_host(d.get("host"))
    except Refused:
        raise ValueError("provider policy host is not a canonical hostname") from None
    if host != d["host"]:
        raise ValueError("provider policy host must already be canonical")
    if (d.get("authentication_header") is None) != (d.get("credential_ref") is None) or \
            (d.get("authentication_header") is not None and d["authentication_header"] not in AUTH_HEADERS):
        raise ValueError("authentication header and credential reference must be governed together")
    if d.get("credential_ref") is not None and not _REF.match(d["credential_ref"]):
        raise ValueError("credential_ref must be a reference, never a value")
    if d.get("parser_schema_version") not in PARSERS:
        raise ValueError("no governed parser exists for this parser_schema_version")
    proxy = None
    if d.get("proxy") is not None:
        p = d["proxy"]
        if not isinstance(p, Mapping) or set(p) != {"host", "port", "final_hop_enforcement_verified"}:
            raise ValueError("proxy must be declared in governed configuration only")
        proxy = ProxyPolicy(canonical_host(p["host"]), int(p["port"]), p["final_hop_enforcement_verified"] is True)
    return ProviderPolicy(**{k: d.get(k) for k in _POLICY_FIELDS if k not in ("proxy",) and k in d},
                          proxy=proxy, document=json.loads(canonical_json(d)))


# ================================================================ normalized indicator (data, never a destination)
@dataclass(frozen=True)
class Indicator:
    indicator_type: str
    value: str

    @property
    def ref(self) -> str:                    # normalized_indicator_ref: SHA-256 over canonical {type, value}
        return hashlib.sha256(canonical_json({"indicator_type": self.indicator_type, "normalized_value": self.value}).encode()).hexdigest()


def indicators_from_url_observation(url: Mapping, policy: ProviderPolicy) -> Indicator | None:
    """The single outbound form INT-001 permits for the policy's indicator type, from an S4 url-observation. Userinfo and
    fragment are never sent; the query only when the policy permits it."""
    structural = url.get("structural") or {}
    if policy.indicator_type == "HOSTNAME":
        value = structural.get("hostname")
    elif policy.indicator_type == "REGISTERED_DOMAIN":
        value = structural.get("registered_domain")
    else:
        normalized = url.get("normalized_url")
        if not isinstance(normalized, str):
            return None
        try:
            parts = urlsplit(normalized if "://" in normalized else "https://" + normalized)
            port = parts.port
        except ValueError:
            return None                                       # malformed: not sent
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return None
        netloc = parts.hostname + (f":{port}" if port else "")
        query = f"?{parts.query}" if parts.query and policy.url_query_transmission == "PERMITTED" else ""
        value = f"{parts.scheme}://{netloc}{parts.path or '/'}{query}"
    if not isinstance(value, str) or not value or len(value) > 2048 or any(ord(c) < 0x20 or ord(c) == 0x7f for c in value):
        return None
    return Indicator(policy.indicator_type, value)


# ================================================================ injectable network seams
class Resolver(Protocol):
    def resolve(self, host: str, timeout: float) -> list: ...


class ResolverError(Exception):
    pass


@dataclass(frozen=True)
class Connection:
    address: str                 # the validated address to connect to (never a name)
    port: int
    server_hostname: str         # SNI and certificate verification name: the approved hostname
    proxy: ProxyPolicy | None = None


@dataclass(frozen=True)
class TransportResponse:
    status: int
    headers: Mapping[str, str]   # lower-case names
    body: bytes                  # at most wire_max_bytes + 1 bytes were read


class TransportError(Exception):
    def __init__(self, kind: str):                 # CONNECTION | TLS | TIMEOUT | PROXY_UNSUPPORTED
        super().__init__(kind)
        self.kind = kind


class Channel(Protocol):
    """A connected but still SILENT socket: peer_address is the socket's actual remote address, read before any
    application byte (no TLS ClientHello, header, credential or indicator) has been sent."""
    peer_address: str

    def exchange(self, method: str, target: str, headers: Mapping[str, str], body: bytes | None, *,
                 remaining: Callable[[], float], read_timeout: float, max_wire_bytes: int) -> TransportResponse: ...

    def close(self) -> None: ...


class Transport(Protocol):
    def connect(self, connection: Connection, *, timeout: float) -> Channel: ...


class CredentialStore(Protocol):
    def get(self, credential_ref: str) -> str | None: ...


class _PinnedChannel:
    def __init__(self, raw, connection):
        self._raw, self._connection = raw, connection
        self.peer_address = raw.getpeername()[0]      # before TLS: nothing has been sent yet

    def close(self):
        try:
            self._raw.close()
        except OSError:
            pass

    def exchange(self, method, target, headers, body, *, remaining, read_timeout, max_wire_bytes):
        import socket

        def budget():
            left = remaining()
            if left <= 0:
                raise TransportError("TIMEOUT")
            return min(left, read_timeout)

        context = ssl.create_default_context()        # certificate + hostname verification, default trust store
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        try:
            self._raw.settimeout(budget())
            tls = context.wrap_socket(self._raw, server_hostname=self._connection.server_hostname)
        except ssl.SSLError:
            raise TransportError("TLS") from None
        except socket.timeout:
            raise TransportError("TIMEOUT") from None
        except OSError:
            raise TransportError("CONNECTION") from None
        self._raw = tls
        lines = [f"{method} {target} HTTP/1.1"] + [f"{k}: {v}" for k, v in headers.items()] + ["Connection: close", "", ""]
        data = b""
        try:
            tls.settimeout(budget())
            tls.sendall("\r\n".join(lines).encode("ascii") + (body or b""))
            while len(data) <= max_wire_bytes + 16 * 1024:
                tls.settimeout(budget())                  # every chunk is bounded by the remaining overall deadline
                chunk = tls.recv(16 * 1024)
                if not chunk:
                    break
                data += chunk
        except socket.timeout:
            raise TransportError("TIMEOUT") from None
        except (OSError, ssl.SSLError):
            raise TransportError("CONNECTION") from None
        head, _, payload = data.partition(b"\r\n\r\n")
        try:
            status_line, *header_lines = head.decode("iso-8859-1").split("\r\n")
            status = int(status_line.split(" ")[1])
        except (ValueError, IndexError):
            raise TransportError("CONNECTION") from None
        parsed = {}
        for line in header_lines:
            name, _, value = line.partition(":")
            parsed[name.strip().lower()] = value.strip()
        if "chunked" in parsed.get("transfer-encoding", "").lower():
            raise TransportError("CONNECTION")              # not supported by this bounded reader: fail closed
        return TransportResponse(status, parsed, payload[:max_wire_bytes + 1])


class PinnedHTTPSTransport:
    """Live transport: TCP to the validated address only; the channel exposes the socket peer BEFORE the TLS handshake,
    so the adapter can refuse a wrong peer with zero bytes sent. TLS then uses SNI and certificate + hostname
    verification for the approved hostname; handshake, send and every read are bounded by the remaining overall deadline.
    Never follows redirects, never reads proxy environment variables, has no proxy support. Not exercised live: live
    execution also needs GovernedResolver, which is deliberately non-executable (see below)."""

    def connect(self, connection, *, timeout):
        import socket
        if connection.proxy is not None:
            raise TransportError("PROXY_UNSUPPORTED")
        try:
            raw = socket.create_connection((connection.address, connection.port), timeout=timeout)
        except socket.timeout:
            raise TransportError("TIMEOUT") from None
        except OSError:
            raise TransportError("CONNECTION") from None
        try:
            return _PinnedChannel(raw, connection)
        except OSError:
            raw.close()
            raise TransportError("CONNECTION") from None


class GovernedResolver:
    """DELIBERATELY NON-EXECUTABLE. The only live resolution primitive available (getaddrinfo) cannot be bounded by the
    INT-001 overall deadline, so a live governed resolver is not implemented and live lookups cannot be constructed.
    A deadline-bounded resolver needs separate review before live enablement."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError("live DNS resolution is disabled: no deadline-bounded governed resolver exists")


# ================================================================ response parsing (governed, per parser version)
def _strict_json(data: bytes):
    def pairs(items):
        keys = [k for k, _ in items]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate key")
        return dict(items)
    return json.loads(data.decode("utf-8"), object_pairs_hook=pairs)


_RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$")


def fixture_parser_v1(document, policy: ProviderPolicy, indicator: Indicator, now: datetime) -> dict:
    """TL-FIXTURE-PARSER-1.0.0: the parser for the FICTIONAL fixture provider schema used by tests (no real provider is
    selected). Strict: exact keys, closed enums, RFC 3339 timestamp, echoed provider identity, parser version and indicator."""
    keys = {"schema_version", "provider_ref", "indicator", "observed_at", "entry", "reputation", "allowlist", "brand_match"}
    if not isinstance(document, dict) or set(document) != keys or not isinstance(document["indicator"], dict) \
            or set(document["indicator"]) != {"type", "value"}:
        raise Refused("SCHEMA_INVALID_RESPONSE", "HTTP_2XX")
    # every field's type and shape before any comparison, membership check or nested access
    if not all(isinstance(document[k], str) for k in keys - {"indicator"}) \
            or not all(isinstance(v, str) for v in document["indicator"].values()):
        raise Refused("SCHEMA_INVALID_RESPONSE", "HTTP_2XX")
    if document["schema_version"] != "1.0.0" or document["provider_ref"] != policy.provider_ref \
            or document["indicator"] != {"type": indicator.indicator_type, "value": indicator.value}:
        raise Refused("SCHEMA_INVALID_RESPONSE", "HTTP_2XX")   # wrong parser version, provider identity or indicator echo
    observed = document["observed_at"]
    if not isinstance(observed, str) or not _RFC3339.match(observed):
        raise Refused("SCHEMA_INVALID_RESPONSE", "HTTP_2XX")
    try:
        observed_at = datetime.fromisoformat(observed.replace("Z", "+00:00"))
    except ValueError:
        raise Refused("SCHEMA_INVALID_RESPONSE", "HTTP_2XX") from None
    if observed_at > now + timedelta(minutes=5):
        raise Refused("SCHEMA_INVALID_RESPONSE", "HTTP_2XX")
    entry, reputation, allowlist, brand = document["entry"], document["reputation"], document["allowlist"], document["brand_match"]
    allowed = {"FOUND": (("MALICIOUS", "SUSPICIOUS", "CLEAN", "UNKNOWN"), ("ALLOWLISTED", "NOT_ALLOWLISTED", "NOT_EVALUATED"),
                         ("MATCH", "MISMATCH", "UNKNOWN")),
               "NOT_FOUND": (("UNKNOWN",), ("NOT_ALLOWLISTED", "NOT_EVALUATED"), ("UNKNOWN",))}
    if entry not in allowed or reputation not in allowed[entry][0] or allowlist not in allowed[entry][1] or brand not in allowed[entry][2]:
        raise Refused("SCHEMA_INVALID_RESPONSE", "HTTP_2XX")   # unknown_enum_value: INVALID_RESPONSE
    return {"lookup_outcome": entry, "reputation_result": reputation, "allowlist_result": allowlist,
            "domain_matches_claimed_brand": brand, "provider_observed_at": observed}


PARSERS: dict[str, Callable] = {"TL-FIXTURE-PARSER-1.0.0": fixture_parser_v1}


def _decode_body(response: TransportResponse, limits: Limits) -> bytes:
    if len(response.body) > limits.wire_max_bytes:
        raise Refused("OVERSIZED_RESPONSE", "HTTP_2XX")
    encoding = response.headers.get("content-encoding", "identity").strip().lower()
    if encoding in ("", "identity"):
        data = response.body
    elif encoding in ("gzip", "deflate"):
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS if encoding == "gzip" else zlib.MAX_WBITS)
        try:
            data = decoder.decompress(response.body, limits.decoded_max_bytes + 1)   # streaming, bounded
        except zlib.error:                                   # malformed stream or checksum failure
            raise Refused("SCHEMA_INVALID_RESPONSE", "HTTP_2XX") from None
        if len(data) > limits.decoded_max_bytes or decoder.unconsumed_tail:
            raise Refused("DECOMPRESSION_LIMIT_EXCEEDED", "HTTP_2XX")
        if not decoder.eof or decoder.unused_data:           # truncated (no verified trailer), or concatenated/trailing data
            raise Refused("SCHEMA_INVALID_RESPONSE", "HTTP_2XX")
    else:
        raise Refused("INVALID_CONTENT_TYPE", "HTTP_2XX")
    if len(data) > limits.decoded_max_bytes:
        raise Refused("OVERSIZED_RESPONSE", "HTTP_2XX")
    return data


def _media_type_ok(value: str | None, expected: str) -> bool:
    if not value:
        return False
    parts = [p.strip().lower() for p in value.split(";")]
    if parts[0] != expected:
        return False
    params = dict(p.split("=", 1) for p in parts[1:] if "=" in p)
    return params.get("charset", "utf-8").strip('"') == "utf-8" and len(parts) <= 2


def _response_category(status: int) -> str:
    if status == 429:
        return "HTTP_429"
    return {2: "HTTP_2XX", 3: "HTTP_3XX", 4: "HTTP_4XX", 5: "HTTP_5XX"}.get(status // 100, "NO_RESPONSE")


def _canonical_path(path: str, allow_empty: bool = False) -> bool:
    """True only for an already-canonical absolute path: no '.' or '..' segment, no empty segment, no encoding."""
    if path == "":
        return allow_empty
    if "%" in path or "\\" in path:
        return False
    segments = path.split("/")
    if segments[0] == "":                                    # absolute
        segments = segments[1:]
    return all(seg not in (".", "..") for seg in segments) and all(seg for seg in segments[:-1])


def _within_prefix(path: str, prefix: str) -> bool:
    """The effective canonical path is the approved prefix itself or below it on a segment boundary."""
    if not path.startswith("/") or not _canonical_path(path):
        return False
    base = prefix.rstrip("/")
    return path == prefix or path == base or path.startswith(base + "/")


# ================================================================ the lookup
_TRANSPORT_FAILURES = {"TLS": "TLS_FAILURE", "TIMEOUT": "TIMEOUT", "PROXY_UNSUPPORTED": "PROXY_ENFORCEMENT_UNVERIFIED"}


@dataclass
class Adapter:
    resolver: Resolver
    transport: Transport
    credentials: CredentialStore | None = None
    limits: Limits = LOCAL_TEST_PROFILE
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    extra_metadata_addresses: tuple = ()

    def lookup(self, policy: ProviderPolicy, indicator: Indicator) -> LookupResult:
        """Deny by default: every refusal is POLICY_REJECTED, every network or provider failure UNAVAILABLE, every
        unusable response INVALID_RESPONSE. No branch ever yields a reputation without a validated provider response."""
        deadline = self.clock() + self.limits.overall_deadline
        attempts, response_category = 0, "NO_RESPONSE"
        try:
            request = self._prepare(policy, indicator)
        except Refused as refused:
            return _failed(refused.category, refused.response_category, attempts)
        while True:
            attempts += 1
            try:
                if self.clock() >= deadline:
                    raise Refused("TIMEOUT")
                return self._attempt(policy, indicator, request, deadline, attempts)
            except Refused as refused:
                response_category = refused.response_category
                failure = FAILURES[refused.category]
                retryable = failure.retry and policy.retry_safe and attempts < self.limits.max_attempts
                if not retryable:
                    return _failed(refused.category, response_category, attempts,
                                   self.now() if response_category != "NO_RESPONSE" else None)
                wait = min(self.limits.backoff_initial * 2 ** (attempts - 1), self.limits.backoff_max)
                if self.clock() + wait >= deadline:
                    return _failed(refused.category, response_category, attempts)
                self.sleep(wait)

    def _prepare(self, policy, indicator):
        if not policy.enabled:
            raise Refused("POLICY_REJECTION")
        if indicator.indicator_type != policy.indicator_type or indicator.indicator_type not in INDICATOR_TYPES:
            raise Refused("POLICY_REJECTION")
        if policy.proxy is not None and not policy.proxy.final_hop_enforcement_verified:
            raise Refused("PROXY_ENFORCEMENT_UNVERIFIED")      # DEPLOYMENT_BLOCKED: no fallback, no proxy trust
        host = canonical_host(policy.host)
        encoded = quote(indicator.value, safe="")             # ADAPTER_ENCODED_AS_DATA, never a path or destination
        if policy.method == "GET":
            target, body = f"{policy.path_prefix}?{quote(policy.indicator_parameter, safe='')}={encoded}", None
        else:
            target = policy.path_prefix
            body = canonical_json({policy.indicator_parameter: indicator.value, "indicator_type": indicator.indicator_type}).encode()
        headers = {"Host": host if policy.port == 443 else f"{host}:{policy.port}", "Accept": policy.expected_media_type,
                   "User-Agent": USER_AGENT, "X-Correlation-Id": str(uuid.uuid4())}   # never an internal identifier
        if body is not None:
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(body))
        if policy.credential_ref is not None:
            value = self.credentials.get(policy.credential_ref) if self.credentials else None
            if not value:
                raise Refused("CREDENTIAL_UNAVAILABLE")
            headers[policy.authentication_header] = value
        for name, value in headers.items():
            if any(c in str(value) or c in name for c in "\r\n\0"):
                raise Refused("POLICY_REJECTION")             # header / CRLF injection
        return {"host": host, "target": target, "body": body, "headers": headers}

    def _remaining(self, deadline: float) -> float:
        """The one monotonic overall deadline: every step gets only what is left, and nothing continues past it."""
        left = deadline - self.clock()
        if left <= 0:
            raise Refused("TIMEOUT")
        return left

    def _resolve_validated(self, host: str, deadline: float) -> str:
        try:
            answers = self.resolver.resolve(host, min(self.limits.connect_timeout, self._remaining(deadline)))
        except ResolverError:
            raise Refused("DNS_FAILURE") from None
        self._remaining(deadline)                              # a slow answer past the deadline is not used
        if not isinstance(answers, (list, tuple)) or not answers:
            raise Refused("DNS_FAILURE")
        if not all(isinstance(a, str) and address_permitted(a, self.extra_metadata_addresses) for a in answers):
            raise Refused("DESTINATION_ADDRESS_REJECTION")     # mixed or any denied answer rejects the lookup
        return sorted(answers)[0]                              # every answer is valid; ordering is not relied on

    def _attempt(self, policy, indicator, request, deadline, attempts):
        host, target, port = request["host"], request["target"], policy.port
        for hop in range(self.limits.max_redirect_hops + 1):
            address = self._resolve_validated(host, deadline)                # each hop and attempt revalidates
            connection = Connection(address, port, host, policy.proxy)
            try:
                channel = self.transport.connect(connection, timeout=min(self.limits.connect_timeout, self._remaining(deadline)))
            except TransportError as error:
                raise Refused(_TRANSPORT_FAILURES.get(error.kind, "CONNECTION_FAILURE")) from None
            try:
                peer = getattr(channel, "peer_address", None)
                if not isinstance(peer, str) or peer != address or not address_permitted(peer, self.extra_metadata_addresses):
                    raise Refused("DESTINATION_ADDRESS_REJECTION")  # verified BEFORE any byte: wrong or unknown peer gets nothing
                response = channel.exchange(policy.method, target, request["headers"], request["body"],
                                            remaining=lambda: deadline - self.clock(),
                                            read_timeout=min(self.limits.read_timeout, self._remaining(deadline)),
                                            max_wire_bytes=self.limits.wire_max_bytes)
            except TransportError as error:
                raise Refused(_TRANSPORT_FAILURES.get(error.kind, "CONNECTION_FAILURE")) from None
            finally:
                channel.close()
            self._remaining(deadline)                              # a response finishing after the deadline is rejected
            category = _response_category(response.status)
            if 300 <= response.status < 400:
                if policy.redirect_policy == "DO_NOT_FOLLOW" or hop == self.limits.max_redirect_hops:
                    raise Refused("REDIRECT_POLICY_REJECTION", category)
                host, target = self._redirect_target(policy, host, target, response.headers.get("location"))
                continue
            if response.status == 429:
                raise Refused("RATE_LIMITED", category)
            if 400 <= response.status < 500:
                raise Refused("PROVIDER_CLIENT_ERROR", category)
            if response.status >= 500:
                raise Refused("PROVIDER_SERVER_ERROR", category)
            if response.status != 200:
                raise Refused("SCHEMA_INVALID_RESPONSE", category)
            if not _media_type_ok(response.headers.get("content-type"), policy.expected_media_type):
                raise Refused("INVALID_CONTENT_TYPE", category)
            data = _decode_body(response, self.limits)
            self._remaining(deadline)
            try:
                document = _strict_json(data)
            except (ValueError, UnicodeDecodeError, RecursionError):
                raise Refused("SCHEMA_INVALID_RESPONSE", category) from None
            try:
                normalized = PARSERS[policy.parser_schema_version](document, policy, indicator, self.now())
            except Refused:
                raise
            except Exception:                                  # contained: no provider body or traceback escapes
                raise Refused("SCHEMA_INVALID_RESPONSE", category) from None
            self._remaining(deadline)                              # accepted only while the deadline holds
            responded_at = self.now()
            artifact = {"provider_ref": policy.provider_ref, "provider_policy_version": policy.provider_policy_version,
                        "provider_policy_digest": policy.digest, "parser_schema_version": policy.parser_schema_version,
                        "indicator_type": indicator.indicator_type, "normalized_indicator_ref": indicator.ref,
                        "observed_at": responded_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "normalized_payload": normalized}
            return LookupResult(normalized["lookup_outcome"], "SUCCEEDED", None, category, normalized["reputation_result"],
                                normalized["allowlist_result"], normalized["domain_matches_claimed_brand"], responded_at,
                                artifact, attempts)
        raise Refused("REDIRECT_POLICY_REJECTION", "HTTP_3XX")

    def _redirect_target(self, policy, host, target, location):
        """REVALIDATE_WITHIN_PROVIDER_ALLOWLIST: a new destination decision per hop — https only, the exact approved host
        and port, and a canonical path inside the exact approved prefix; DNS and peer are revalidated by the next hop.
        Dot segments and percent-encodings are refused outright (raw and resolved), so no normalization can escape."""
        if not isinstance(location, str) or not location or any(c in location for c in "\r\n\0\\%;"):
            raise Refused("REDIRECT_POLICY_REJECTION", "HTTP_3XX")
        if not _canonical_path(urlsplit(location).path, allow_empty=True):
            raise Refused("REDIRECT_POLICY_REJECTION", "HTTP_3XX")
        absolute = urljoin(f"https://{host}{'' if policy.port == 443 else f':{policy.port}'}{target}", location)
        parts = urlsplit(absolute)
        try:
            port = parts.port or 443
            next_host = canonical_host(parts.hostname or "")
        except (ValueError, Refused):
            raise Refused("REDIRECT_POLICY_REJECTION", "HTTP_3XX") from None
        if parts.scheme != "https" or parts.username or parts.password or "@" in parts.netloc or next_host != policy.host \
                or port != policy.port or not _within_prefix(parts.path, policy.path_prefix):
            raise Refused("REDIRECT_POLICY_REJECTION", "HTTP_3XX")
        return next_host, parts.path + (f"?{parts.query}" if parts.query else "")

