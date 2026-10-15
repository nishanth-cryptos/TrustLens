"""S7 egress boundary, fully offline: fake DNS, fake transports, the FICTIONAL fixture provider, and a hard guard that
fails any real socket or DNS use. Every INT-001 conformance scenario (SC-01..SC-19) is exercised."""
import gzip
import json
import socket
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from trustlens_backend import egress
from trustlens_backend.egress import Adapter, Indicator, Limits, TransportError, TransportResponse, address_permitted, canonical_host, load_policy

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = json.loads((ROOT / "contracts/integrations/external-enrichment-v1.json").read_text())
HOST = "lookup.provider-fixture.example"
GLOBAL = "93.184.216.34"                                 # stands in for GLOBAL_UNICAST_PLACEHOLDER
SECRET = "synthetic-fixture-key-0123456789"              # a fixture credential VALUE: must never leave the request header
NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
POLICY = {"provider_policy_ref": "TL-PPOL-FIXTURE", "provider_policy_version": "1.0.0", "provider_ref": "FICTIONAL_FIXTURE_PROVIDER",
          "provider_category": "REPUTATION_LOOKUP", "provider_operation": "URL_REPUTATION", "indicator_type": "URL", "scheme": "https",
          "host": HOST, "port": 443, "path_prefix": "/v1/lookup", "method": "GET", "indicator_parameter": "indicator",
          "expected_media_type": "application/json", "parser_schema_version": "TL-FIXTURE-PARSER-1.0.0", "redirect_policy": "DO_NOT_FOLLOW",
          "url_query_transmission": "NOT_PERMITTED", "retry_safe": True, "enabled": True, "authentication_header": "X-Api-Key",
          "credential_ref": "SEC:FIXTURE-PROVIDER-KEY"}
INDICATOR = Indicator("URL", "https://trust-wallet-verify.example/")


def policy(**overrides):
    return load_policy({**POLICY, **overrides})


def assertion(entry="FOUND", reputation="MALICIOUS", allowlist="NOT_ALLOWLISTED", brand="UNKNOWN", **overrides):
    body = {"schema_version": "1.0.0", "provider_ref": "FICTIONAL_FIXTURE_PROVIDER",
            "indicator": {"type": INDICATOR.indicator_type, "value": INDICATOR.value}, "observed_at": "2026-10-15T11:59:00Z",
            "entry": entry, "reputation": reputation, "allowlist": allowlist, "brand_match": brand}
    body.update(overrides)
    return json.dumps(body).encode()


class FakeResolver:
    def __init__(self, answers):
        self.answers, self.calls = answers, []

    def resolve(self, host, timeout):
        self.calls.append(host)
        answer = self.answers.get(host, egress.ResolverError("nx")) if isinstance(self.answers, dict) else self.answers
        if isinstance(answer, Exception):
            raise answer
        return list(answer)


class FakeTransport:
    """Scripted responses through the connect -> (adapter verifies peer) -> exchange seam. `calls` records every exchange,
    i.e. every time application bytes (headers, credential, indicator) were actually sent."""

    def __init__(self, *responses, peer=None, on_connect=None, on_exchange=None):
        self.responses, self.calls, self.connects, self.peer = list(responses), [], [], peer
        self.on_connect, self.on_exchange = on_connect, on_exchange

    def connect(self, connection, *, timeout):
        self.connects.append((connection, timeout))
        if self.on_connect:
            self.on_connect()
        return FakeChannel(self, connection, connection.address if self.peer is None else self.peer)


class FakeChannel:
    def __init__(self, transport, connection, peer):
        self.transport, self.connection, self.peer_address, self.closed = transport, connection, peer, False

    def close(self):
        self.closed = True

    def exchange(self, method, target, headers, body, *, remaining, read_timeout, max_wire_bytes):
        t = self.transport
        t.calls.append({"connection": self.connection, "method": method, "target": target, "headers": dict(headers), "body": body,
                        "read_timeout": read_timeout, "remaining": remaining(), "max": max_wire_bytes})
        item = t.responses.pop(0) if len(t.responses) > 1 else t.responses[0]
        if t.on_exchange:
            t.on_exchange()
        if isinstance(item, Exception):
            raise item
        status, headers_out, payload = item
        return TransportResponse(status, headers_out, payload[:max_wire_bytes + 1])


JSON = {"content-type": "application/json"}


def ok(payload=None, headers=None):
    return (200, headers or JSON, payload if payload is not None else assertion())


class Credentials:
    def get(self, ref):
        return SECRET if ref == "SEC:FIXTURE-PROVIDER-KEY" else None


class EgressTests(unittest.TestCase):
    def setUp(self):
        def no_network(*args, **kwargs):
            raise AssertionError("the test suite must never touch the real network")
        for target in ("socket.create_connection", "socket.getaddrinfo", "socket.socket.connect"):
            guard = patch(target, no_network)
            guard.start()
            self.addCleanup(guard.stop)
        self.slept = []

    def adapter(self, transport, answers=(GLOBAL,), **kwargs):
        return Adapter(resolver=FakeResolver({HOST: list(answers)} if not isinstance(answers, dict) else answers), transport=transport,
                       credentials=Credentials(), now=lambda: NOW, sleep=self.slept.append, **kwargs)

    def lookup(self, transport, answers=(GLOBAL,), pol=None, **kwargs):
        return self.adapter(transport, answers, **kwargs).lookup(pol or policy(), INDICATOR)

    # ---- provider assertions are advisory, normalized and never TrustLens verdicts
    def test_provider_assertions_normalize_to_the_accepted_vocabularies(self):
        cases = [(("FOUND", "MALICIOUS"), ("FOUND", "SUCCEEDED", "MALICIOUS")), (("FOUND", "SUSPICIOUS"), ("FOUND", "SUCCEEDED", "SUSPICIOUS")),
                 (("FOUND", "CLEAN"), ("FOUND", "SUCCEEDED", "CLEAN")), (("FOUND", "UNKNOWN"), ("FOUND", "SUCCEEDED", "UNKNOWN"))]
        for (entry, reputation), expected in cases:
            with self.subTest(reputation=reputation):
                r = self.lookup(FakeTransport(ok(assertion(entry, reputation))))
                self.assertEqual((r.outcome, r.status, r.reputation_result), expected)
                self.assertIsNotNone(r.artifact_digest)
                self.assertEqual(r.responded_at, NOW)
        missing = self.lookup(FakeTransport(ok(assertion("NOT_FOUND", "UNKNOWN", "NOT_EVALUATED"))))
        self.assertEqual((missing.outcome, missing.status, missing.reputation_result, missing.allowlist_result),
                         ("NOT_FOUND", "SUCCEEDED", "UNKNOWN", "NOT_EVALUATED"))     # absence of information, never CLEAN
        for value in (missing.artifact, self.lookup(FakeTransport(ok())).artifact):
            for forbidden in ("SAFE", "LEGITIMATE", "VERIFIED", "NO_SCAM_PATTERN", "risk_score", "classification"):
                self.assertNotIn(forbidden, json.dumps(value))

    def test_failures_and_unusable_responses_are_never_a_reputation(self):
        big = assertion(observed_at="2026-10-15T11:59:00Z") + b" " * (40 * 1024)
        bomb = gzip.compress(b"[" + b"0," * (200 * 1024) + b"0]")
        cases = {
            "outage": (FakeTransport(TransportError("CONNECTION")), ("UNAVAILABLE", "FAILED", "CONNECTION_FAILURE")),
            "timeout": (FakeTransport(TransportError("TIMEOUT")), ("UNAVAILABLE", "TIMED_OUT", "TIMEOUT")),
            "tls": (FakeTransport(TransportError("TLS")), ("UNAVAILABLE", "FAILED", "TLS_FAILURE")),
            "rate_limited": (FakeTransport((429, {}, b"")), ("UNAVAILABLE", "FAILED", "RATE_LIMITED")),
            "server_error": (FakeTransport((503, {}, b"")), ("UNAVAILABLE", "FAILED", "PROVIDER_SERVER_ERROR")),
            "client_error": (FakeTransport((404, JSON, b"{}")), ("UNAVAILABLE", "FAILED", "PROVIDER_CLIENT_ERROR")),
            "html": (FakeTransport(ok(headers={"content-type": "text/html"})), ("INVALID_RESPONSE", "FAILED", "INVALID_CONTENT_TYPE")),
            "oversized": (FakeTransport(ok(big)), ("INVALID_RESPONSE", "FAILED", "OVERSIZED_RESPONSE")),
            "bomb": (FakeTransport(ok(bomb, {"content-type": "application/json", "content-encoding": "gzip"})),
                     ("INVALID_RESPONSE", "FAILED", "DECOMPRESSION_LIMIT_EXCEEDED")),
            "not_json": (FakeTransport(ok(b"<xml/>")), ("INVALID_RESPONSE", "FAILED", "SCHEMA_INVALID_RESPONSE")),
            "unknown_enum": (FakeTransport(ok(assertion(reputation="PROBABLY_FINE"))), ("INVALID_RESPONSE", "FAILED", "SCHEMA_INVALID_RESPONSE")),
            "extra_field": (FakeTransport(ok(assertion(verdict="SAFE"))), ("INVALID_RESPONSE", "FAILED", "SCHEMA_INVALID_RESPONSE")),
            "wrong_provider": (FakeTransport(ok(assertion(provider_ref="SOMEONE_ELSE"))), ("INVALID_RESPONSE", "FAILED", "SCHEMA_INVALID_RESPONSE")),
            "wrong_parser": (FakeTransport(ok(assertion(schema_version="2.0.0"))), ("INVALID_RESPONSE", "FAILED", "SCHEMA_INVALID_RESPONSE")),
            "bad_time": (FakeTransport(ok(assertion(observed_at="yesterday"))), ("INVALID_RESPONSE", "FAILED", "SCHEMA_INVALID_RESPONSE")),
            "future_time": (FakeTransport(ok(assertion(observed_at="2027-01-01T00:00:00Z"))), ("INVALID_RESPONSE", "FAILED", "SCHEMA_INVALID_RESPONSE")),
            "other_indicator": (FakeTransport(ok(assertion(indicator={"type": "URL", "value": "https://elsewhere.example/"}))),
                                ("INVALID_RESPONSE", "FAILED", "SCHEMA_INVALID_RESPONSE")),
            "not_found_clean": (FakeTransport(ok(assertion("NOT_FOUND", "CLEAN"))), ("INVALID_RESPONSE", "FAILED", "SCHEMA_INVALID_RESPONSE")),
            "duplicate_keys": (FakeTransport(ok(b'{"entry":"FOUND","entry":"NOT_FOUND"}')), ("INVALID_RESPONSE", "FAILED", "SCHEMA_INVALID_RESPONSE")),
        }
        for name, (transport, expected) in cases.items():
            with self.subTest(case=name):
                r = self.lookup(transport)
                self.assertEqual((r.outcome, r.status, r.safe_error_category), expected)
                self.assertEqual((r.reputation_result, r.allowlist_result, r.domain_matches_claimed_brand, r.artifact),
                                 ("NOT_EVALUATED", "NOT_EVALUATED", "UNKNOWN", None))

    def test_retries_are_bounded_backed_off_and_revalidate_every_attempt(self):
        transport = FakeTransport((503, {}, b""))
        resolver_answers = {HOST: [GLOBAL]}
        adapter = self.adapter(transport, resolver_answers)
        r = adapter.lookup(policy(), INDICATOR)
        self.assertEqual((r.safe_error_category, r.attempts), ("PROVIDER_SERVER_ERROR", egress.LOCAL_TEST_PROFILE.max_attempts))
        self.assertEqual(len(transport.calls), egress.LOCAL_TEST_PROFILE.max_attempts)
        self.assertEqual(adapter.resolver.calls, [HOST] * egress.LOCAL_TEST_PROFILE.max_attempts)   # re-resolved each attempt
        self.assertTrue(all(0 < s <= egress.LOCAL_TEST_PROFILE.backoff_max for s in self.slept))
        recovered = self.lookup(FakeTransport((503, {}, b""), ok()))
        self.assertEqual((recovered.outcome, recovered.attempts), ("FOUND", 2))
        no_retry = self.lookup(FakeTransport((503, {}, b"")), pol=policy(retry_safe=False))
        self.assertEqual(no_retry.attempts, 1)
        tls = FakeTransport(TransportError("TLS"))
        self.assertEqual(self.lookup(tls).attempts, 1)                                    # TLS failures are never retried
        clock = iter([0, 0, 11, 11, 11])
        slow = Adapter(resolver=FakeResolver([GLOBAL]), transport=FakeTransport((503, {}, b"")), credentials=Credentials(),
                       clock=lambda: next(clock), sleep=lambda s: None, now=lambda: NOW)
        late = slow.lookup(policy(), INDICATOR)
        self.assertEqual((late.status, late.safe_error_category), ("TIMED_OUT", "TIMEOUT"))   # the overall deadline bounds everything
        with self.assertRaises(ValueError):
            Limits(connect_timeout=float("inf"), read_timeout=1, overall_deadline=1, max_attempts=1, backoff_initial=0.1,
                   backoff_max=1, max_redirect_hops=0, wire_max_bytes=1, decoded_max_bytes=1)

    # ---- INT-001 conformance scenarios SC-01..SC-19
    def scenario(self, sc):
        resolved = [GLOBAL if a == "GLOBAL_UNICAST_PLACEHOLDER" else a for a in sc["resolved"]]
        if sc["kind"] == "REDIRECT":
            target = sc["target"]
            answers = {HOST: [GLOBAL]}
            from urllib.parse import urlsplit
            redirect_host = urlsplit(target).hostname
            if redirect_host and redirect_host != HOST:
                answers[redirect_host] = resolved
            elif resolved:
                answers = {HOST: [GLOBAL]}
            pol = policy(redirect_policy="REVALIDATE_WITHIN_PROVIDER_ALLOWLIST")
            transport = FakeTransport((302, {"location": target}, b""), ok())
            if redirect_host == HOST and resolved != [GLOBAL]:                          # same host now answers privately
                resolver = FakeResolver({HOST: [GLOBAL]})
                calls = iter([[GLOBAL], resolved])
                resolver.resolve = lambda host, timeout: next(calls)
                return Adapter(resolver=resolver, transport=transport, credentials=Credentials(), now=lambda: NOW,
                               sleep=lambda s: None).lookup(pol, INDICATOR), transport
            return self.lookup(transport, answers, pol=pol), transport
        if sc["kind"] == "PROXY":
            pol = policy(proxy={"host": "egress-proxy.trustlens-fixture.example", "port": 3128,
                                "final_hop_enforcement_verified": sc["proxy_enforcement_verified"]})
            transport = FakeTransport(ok())
            return self.lookup(transport, resolved, pol=pol), transport
        target = sc["target"]
        from urllib.parse import urlsplit
        parts = urlsplit(target)
        if parts.hostname != HOST or "@" in parts.netloc:
            # The confusable destination can neither be a governed policy host (refused, or simply not the approved host)
            # nor be reached by redirect from the approved provider (exact-host allowlist, no substring/userinfo tricks).
            try:
                load_policy({**POLICY, "host": parts.netloc})
                self.assertNotEqual(parts.netloc, HOST)
            except ValueError:
                pass
            pol = policy(redirect_policy="REVALIDATE_WITHIN_PROVIDER_ALLOWLIST", path_prefix="/")
            transport = FakeTransport((302, {"location": target}, b""), ok())
            answers = {HOST: [GLOBAL]}
            if parts.hostname:
                answers[parts.hostname] = resolved or [GLOBAL]
            return self.lookup(transport, answers, pol=pol), transport
        transport = FakeTransport(ok())
        if sc["kind"] == "REBINDING":
            transport.rebinding = sc["connect_time_resolved"]                              # what an uncontrolled re-resolution would give
        return self.lookup(transport, resolved), transport

    def test_every_int001_conformance_scenario(self):
        scenarios = CONTRACT["conformance_scenarios"]["scenarios"]
        self.assertEqual(len(scenarios), 19)
        for sc in scenarios:
            with self.subTest(scenario=sc["id"], name=sc["name"]):
                result, transport = self.scenario(sc)
                if sc["expected"] == "PERMITTED":
                    self.assertEqual(result.outcome, "FOUND")
                    self.assertEqual(transport.calls[-1]["connection"].address, GLOBAL)
                elif sc["expected"] == "CONNECTS_ONLY_TO_VALIDATED_ADDRESS":
                    self.assertEqual(result.outcome, "FOUND")
                    self.assertEqual([c["connection"].address for c in transport.calls], [GLOBAL])   # never the rebinding answer
                    self.assertEqual(transport.calls[0]["connection"].server_hostname, HOST)
                else:
                    self.assertTrue(result == "POLICY_LOAD_REFUSED" or result.outcome == "POLICY_REJECTED", result)
                    if result != "POLICY_LOAD_REFUSED":
                        self.assertEqual(result.status, "REJECTED")
                        self.assertTrue(all(c["connection"].address == GLOBAL for c in (transport.calls if transport else [])))

    def test_address_classes_and_encodings(self):
        denied = ["127.0.0.1", "127.0.0.2", "10.0.0.5", "172.16.5.4", "192.168.1.10", "169.254.169.254", "169.254.1.1", "0.0.0.0",
                  "100.64.0.1", "192.0.2.1", "198.51.100.1", "203.0.113.1", "198.18.0.1", "240.0.0.1", "255.255.255.255", "224.0.0.1",
                  "::1", "::", "fe80::1", "fd12:3456::1", "fc00::1", "ff02::1", "::ffff:127.0.0.1", "::ffff:93.184.216.34",
                  "64:ff9b::7f00:1", "2002:7f00:1::1", "2001:db8::1", "2001::1", "100::1", "2130706433", "0x7f.0.0.1", "127.1",
                  "017.0.0.1", "", "lookup.provider-fixture.example", "fe80::1%eth0"]
        for address in denied:
            with self.subTest(address=address):
                self.assertFalse(address_permitted(address))
        self.assertTrue(address_permitted(GLOBAL))
        self.assertTrue(address_permitted("2606:4700:4700::1111"))
        self.assertFalse(address_permitted("93.184.216.34", extra_metadata=("93.184.216.34",)))   # deployment-declared metadata

    def test_connected_peer_must_be_the_validated_address(self):
        transport = FakeTransport(ok(), peer="10.0.0.9")
        r = self.lookup(transport)
        self.assertEqual((r.outcome, r.safe_error_category), ("POLICY_REJECTED", "DESTINATION_ADDRESS_REJECTION"))
        self.assertEqual(transport.calls, [])
        mixed = self.lookup(FakeTransport(ok()), [GLOBAL, "10.1.2.3"])
        self.assertEqual(mixed.safe_error_category, "DESTINATION_ADDRESS_REJECTION")
        dns = self.lookup(FakeTransport(ok()), {HOST: egress.ResolverError("nx")})
        self.assertEqual((dns.outcome, dns.safe_error_category), ("UNAVAILABLE", "DNS_FAILURE"))
        empty = self.lookup(FakeTransport(ok()), [])
        self.assertEqual(empty.safe_error_category, "DNS_FAILURE")

    def test_redirects_are_refused_by_default_and_revalidated_per_hop_when_governed(self):
        refused = self.lookup(FakeTransport((302, {"location": f"https://{HOST}/v1/lookup/next"}, b""), ok()))
        self.assertEqual((refused.outcome, refused.safe_error_category), ("POLICY_REJECTED", "REDIRECT_POLICY_REJECTION"))
        governed = policy(redirect_policy="REVALIDATE_WITHIN_PROVIDER_ALLOWLIST")
        transport = FakeTransport((302, {"location": "/v1/lookup/next?x=1"}, b""), ok())
        followed = self.adapter(transport).lookup(governed, INDICATOR)
        self.assertEqual(followed.outcome, "FOUND")
        self.assertEqual([c["target"] for c in transport.calls][1], "/v1/lookup/next?x=1")
        for location in ("https://lookup.provider-fixture.example/elsewhere", "https://lookup.provider-fixture.example:8443/v1/lookup",
                         "https://user@lookup.provider-fixture.example/v1/lookup", "//unapproved.example/v1/lookup",
                         "https://lookup.provider-fixture.example/v1/lookup%2f..%2fadmin", "http://lookup.provider-fixture.example/v1/lookup"):
            with self.subTest(location=location):
                r = self.adapter(FakeTransport((302, {"location": location}, b""), ok())).lookup(governed, INDICATOR)
                self.assertEqual(r.safe_error_category, "REDIRECT_POLICY_REJECTION")
        loop = self.adapter(FakeTransport((302, {"location": "/v1/lookup/again"}, b""))).lookup(governed, INDICATOR)
        self.assertEqual(loop.safe_error_category, "REDIRECT_POLICY_REJECTION")         # finite hop bound

    def test_requests_carry_only_governed_parts_and_the_credential_stays_in_the_header(self):
        transport = FakeTransport(ok())
        attack = Indicator("URL", "https://evil.example/?x=1&indicator=../../admin\r\nX-Injected: 1")
        result = self.adapter(transport).lookup(policy(), attack)
        call = transport.calls[0]
        self.assertEqual((call["method"], call["connection"].address, call["connection"].port, call["connection"].server_hostname),
                         ("GET", GLOBAL, 443, HOST))
        self.assertTrue(call["target"].startswith("/v1/lookup?indicator="))
        self.assertNotIn("\r", call["target"])
        self.assertNotIn("\n", call["target"])
        self.assertEqual(set(call["headers"]), {"Host", "Accept", "User-Agent", "X-Correlation-Id", "X-Api-Key"})
        self.assertLessEqual(call["read_timeout"], call["remaining"])                     # never more than the budget left
        self.assertEqual(call["headers"]["X-Api-Key"], SECRET)
        self.assertNotIn(SECRET, json.dumps([result.artifact, result.outcome, result.safe_error_category, str(result)]))
        self.assertEqual(result.safe_error_category, "SCHEMA_INVALID_RESPONSE")         # the echo does not match: rejected
        no_key = Adapter(resolver=FakeResolver([GLOBAL]), transport=FakeTransport(ok()), credentials=None, now=lambda: NOW)
        r = no_key.lookup(policy(), INDICATOR)
        self.assertEqual((r.outcome, r.safe_error_category), ("UNAVAILABLE", "CREDENTIAL_UNAVAILABLE"))
        self.assertEqual(no_key.transport.calls, [])                                       # nothing sent without the credential

    def test_indicators_are_minimized_lookup_data_only(self):
        url = {"url_id": "u1", "raw_url": "x", "normalized_url": "https://user:pw@shop.example/pay?session=abc#frag",
               "structural": {"hostname": "shop.example", "registered_domain": "shop.example", "flags": {}}}
        self.assertEqual(egress.indicators_from_url_observation(url, policy()).value, "https://shop.example/pay")
        self.assertEqual(egress.indicators_from_url_observation(url, policy(url_query_transmission="PERMITTED")).value,
                         "https://shop.example/pay?session=abc")
        self.assertEqual(egress.indicators_from_url_observation(url, policy(indicator_type="HOSTNAME")).value, "shop.example")
        self.assertIsNone(egress.indicators_from_url_observation({"normalized_url": "javascript:alert(1)"}, policy()))
        r = self.lookup(FakeTransport(ok()), pol=policy(indicator_type="HOSTNAME"))
        self.assertEqual((r.outcome, r.safe_error_category), ("POLICY_REJECTED", "POLICY_REJECTION"))   # wrong indicator type

    def test_policies_are_strict_governed_documents(self):
        self.assertEqual(policy().digest, policy().digest)
        self.assertNotEqual(policy().digest, policy(provider_policy_version="1.0.1").digest)
        for bad in ({"scheme": "http"}, {"host": "Lookup.Provider-Fixture.Example"}, {"host": "127.0.0.1"}, {"host": "2130706433"},
                    {"host": "user@lookup.provider-fixture.example"}, {"host": "localhost"}, {"method": "DELETE"},
                    {"path_prefix": "/v1/../admin"}, {"path_prefix": "v1"}, {"parser_schema_version": "UNGOVERNED"},
                    {"credential_ref": None}, {"authentication_header": "Cookie"}, {"redirect_policy": "FOLLOW_ALL"},
                    {"expected_media_type": "text/html"}, {"destination_url": "https://x.example/"}, {"port": 0}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                load_policy({**POLICY, **bad})
        disabled = self.lookup(FakeTransport(ok()), pol=policy(enabled=False))
        self.assertEqual(disabled.outcome, "POLICY_REJECTED")
        for host in ("Example.COM.", "xn--bcher-kva.example", "bücher.example"):
            canonical_host(host)
        for host in ("a.b@c.example", "a%2eb.example", "[::1]", "a b.example", "x", "1.2.3.4"):
            with self.subTest(host=host), self.assertRaises(egress.Refused):
                canonical_host(host)

    def test_no_proxy_environment_is_ever_read_and_the_live_transport_refuses_proxies(self):
        with patch.dict("os.environ", {"HTTPS_PROXY": "http://10.0.0.1:3128", "HTTP_PROXY": "http://10.0.0.1:3128", "NO_PROXY": "*"}):
            transport = FakeTransport(ok())
            r = self.lookup(transport)
        self.assertEqual(r.outcome, "FOUND")
        self.assertIsNone(transport.calls[0]["connection"].proxy)
        source = (ROOT / "apps/backend/trustlens_backend/egress.py").read_text()
        for forbidden in ("os.environ", "getenv", "urllib.request", "requests", "httpx", "getproxies", "follow_redirects"):
            self.assertNotIn(forbidden, source)
        verified = policy(proxy={"host": "egress-proxy.trustlens-fixture.example", "port": 3128, "final_hop_enforcement_verified": True})
        with self.assertRaises(TransportError):
            egress.PinnedHTTPSTransport().connect(egress.Connection(GLOBAL, 443, HOST, verified.proxy), timeout=1)
        with self.assertRaises(NotImplementedError):
            egress.GovernedResolver()                                                      # live DNS is deliberately disabled


if __name__ == "__main__":
    unittest.main()


# ---- Codex S7 findings 1-4 and 6: regressions (finding 5 is in test_enrichment_db and the frontend tests)
class CodexS7Regressions(unittest.TestCase):
    def setUp(self):
        def no_network(*args, **kwargs):
            raise AssertionError("the test suite must never touch the real network")
        for target in ("socket.create_connection", "socket.getaddrinfo"):
            guard = patch(target, no_network)
            guard.start()
            self.addCleanup(guard.stop)
        self.now = [0.0]

    def clock(self):
        return self.now[0]

    def adapter(self, transport, resolver=None, pol_answers=(GLOBAL,)):
        return Adapter(resolver=resolver or FakeResolver({HOST: list(pol_answers)}), transport=transport, credentials=Credentials(),
                       now=lambda: NOW, sleep=lambda s: None, clock=self.clock)

    # finding 1: redirect path scope
    def test_redirects_cannot_escape_the_approved_path(self):
        governed = policy(redirect_policy="REVALIDATE_WITHIN_PROVIDER_ALLOWLIST")
        for location in (f"https://{HOST}/v1/lookup/../../admin", f"https://{HOST}/v1/lookup/./x/../../../admin", "/v1/lookup/../admin",
                         "../admin", f"https://{HOST}/v1/lookup/%2e%2e/admin", f"https://{HOST}/v1/lookup/%2E%2E%2Fadmin",
                         f"https://{HOST}/v1/lookupadmin", f"https://{HOST}/v1/lookup//admin", f"https://{HOST}/v1/lookup;/../admin",
                         f"https://{HOST}/admin?next=/v1/lookup"):
            with self.subTest(location=location):
                transport = FakeTransport((302, {"location": location}, b""), ok())
                r = self.adapter(transport).lookup(governed, INDICATOR)
                self.assertEqual((r.outcome, r.safe_error_category), ("POLICY_REJECTED", "REDIRECT_POLICY_REJECTION"))
                self.assertEqual(len(transport.calls), 1)                                  # the forbidden endpoint got no request
                self.assertTrue(all(c["target"].startswith("/v1/lookup?") for c in transport.calls))
        transport = FakeTransport((302, {"location": f"https://{HOST}/v1/lookup/v2"}, b""), ok())
        self.assertEqual(self.adapter(transport).lookup(governed, INDICATOR).outcome, "FOUND")   # inside the scope: allowed
        self.assertEqual(transport.calls[1]["target"], "/v1/lookup/v2")

    # finding 2: peer verified before any byte
    def test_a_forbidden_or_unknown_peer_receives_zero_bytes(self):
        for peer in ("10.0.0.9", "169.254.169.254", "::ffff:127.0.0.1", "", None):
            with self.subTest(peer=peer):
                transport = FakeTransport(ok())
                transport.peer = peer if peer is not None else "unknown"
                if peer is None:
                    transport.connect = lambda connection, *, timeout: type("C", (), {"close": lambda self: None,
                                                                                      "exchange": lambda self, *a, **k: ok()})()
                r = self.adapter(transport).lookup(policy(), INDICATOR)
                self.assertEqual((r.outcome, r.safe_error_category), ("POLICY_REJECTED", "DESTINATION_ADDRESS_REJECTION"))
                self.assertEqual(transport.calls, [])                                       # no header, credential or indicator

    def test_the_live_transport_checks_the_socket_peer_before_tls_or_any_send(self):
        sent, wrapped = [], []

        class RawSocket:
            def getpeername(self):
                return ("10.0.0.9", 443)                                                    # the kernel connected elsewhere
            def sendall(self, data):
                sent.append(data)
            def settimeout(self, t):
                pass
            def close(self):
                pass

        with patch("socket.create_connection", lambda address, timeout=None: RawSocket()), \
                patch("ssl.SSLContext.wrap_socket", lambda *a, **k: wrapped.append(1)):
            adapter = Adapter(resolver=FakeResolver({HOST: [GLOBAL]}), transport=egress.PinnedHTTPSTransport(),
                              credentials=Credentials(), now=lambda: NOW, sleep=lambda s: None)
            r = adapter.lookup(policy(), INDICATOR)
        self.assertEqual(r.safe_error_category, "DESTINATION_ADDRESS_REJECTION")
        self.assertEqual((sent, wrapped), ([], []))                                        # no TLS hello, no request bytes

    def test_the_live_channel_bounds_every_read_by_the_overall_deadline(self):
        clock = [0.0]

        class TLS:
            def settimeout(self, t):
                assert t > 0
            def sendall(self, data):
                pass
            def recv(self, n):
                clock[0] += 6                                                               # each chunk is slow
                return b"x"

        class Raw(TLS):
            def getpeername(self):
                return (GLOBAL, 443)

        channel = egress._PinnedChannel(Raw(), egress.Connection(GLOBAL, 443, HOST))
        with patch("ssl.SSLContext.wrap_socket", lambda *a, **k: TLS()):
            with self.assertRaises(TransportError) as raised:
                channel.exchange("GET", "/v1/lookup", {}, None, remaining=lambda: 10 - clock[0], read_timeout=5, max_wire_bytes=100)
        self.assertEqual(raised.exception.kind, "TIMEOUT")

    # finding 3: one end-to-end deadline
    def test_slow_dns_connect_or_response_never_yields_found(self):
        limit = egress.LOCAL_TEST_PROFILE.overall_deadline

        def late(seconds):
            def advance():
                self.now[0] += seconds
            return advance

        class SlowResolver(FakeResolver):
            def resolve(inner, host, timeout):
                self.now[0] += limit + 1
                return [GLOBAL]

        transport = FakeTransport(ok())
        r = self.adapter(transport, SlowResolver({})).lookup(policy(retry_safe=False), INDICATOR)
        self.assertEqual((r.status, r.safe_error_category, transport.connects), ("TIMED_OUT", "TIMEOUT", []))
        for name, transport in (("slow connect", FakeTransport(ok(), on_connect=late(limit + 1))),
                                ("slow response", FakeTransport(ok(), on_exchange=late(limit + 1))),
                                ("slow chunks then success", FakeTransport(ok(), on_exchange=late(limit + 0.001)))):
            with self.subTest(case=name):
                self.now[0] = 0.0
                r = self.adapter(transport).lookup(policy(retry_safe=False), INDICATOR)
                self.assertEqual((r.outcome, r.status, r.safe_error_category), ("UNAVAILABLE", "TIMED_OUT", "TIMEOUT"))
                self.assertIsNone(r.artifact)
        self.now[0] = 0.0
        on_time = self.adapter(FakeTransport(ok(), on_exchange=late(limit - 1))).lookup(policy(), INDICATOR)
        self.assertEqual(on_time.outcome, "FOUND")
        budgets = FakeTransport(ok(), on_connect=late(7))
        self.now[0] = 0.0
        self.adapter(budgets).lookup(policy(), INDICATOR)
        self.assertLessEqual(budgets.calls[0]["read_timeout"], limit - 7)                 # the remaining budget is passed on

    # finding 4: malformed provider content is contained
    def test_malformed_fields_are_invalid_responses_never_exceptions(self):
        variants = [{"entry": []}, {"entry": None}, {"entry": {"x": 1}}, {"entry": 1}, {"reputation": []}, {"reputation": None},
                    {"allowlist": ["NOT_ALLOWLISTED"]}, {"brand_match": 0}, {"observed_at": 0}, {"schema_version": 1.0},
                    {"provider_ref": None}, {"indicator": []}, {"indicator": None}, {"indicator": {"type": "URL"}},
                    {"indicator": {"type": "URL", "value": ["x"]}}, {"indicator": {"type": None, "value": INDICATOR.value}}]
        for change in variants:
            with self.subTest(change=change):
                body = json.loads(assertion())
                body.update(change)
                r = self.adapter(FakeTransport(ok(json.dumps(body).encode()))).lookup(policy(), INDICATOR)
                self.assertEqual((r.outcome, r.safe_error_category), ("INVALID_RESPONSE", "SCHEMA_INVALID_RESPONSE"))
        for raw in (b"[]", b"null", b"1", b'"x"', b'{"entry": []}', b"{}"):
            with self.subTest(raw=raw):
                r = self.adapter(FakeTransport(ok(raw))).lookup(policy(), INDICATOR)
                self.assertEqual(r.outcome, "INVALID_RESPONSE")
        missing = json.loads(assertion())
        del missing["brand_match"]
        self.assertEqual(self.adapter(FakeTransport(ok(json.dumps(missing).encode()))).lookup(policy(), INDICATOR).outcome,
                         "INVALID_RESPONSE")
        with patch.dict(egress.PARSERS, {"TL-FIXTURE-PARSER-1.0.0": lambda *a: {}["boom"]}):
            r = self.adapter(FakeTransport(ok())).lookup(policy(), INDICATOR)               # any parser defect is contained
        self.assertEqual((r.outcome, r.safe_error_category), ("INVALID_RESPONSE", "SCHEMA_INVALID_RESPONSE"))

    # finding 6: complete gzip framing
    def test_incomplete_or_tampered_gzip_is_rejected(self):
        body = assertion()
        whole = gzip.compress(body)
        gz = {"content-type": "application/json", "content-encoding": "gzip"}
        self.assertEqual(self.adapter(FakeTransport(ok(whole, gz))).lookup(policy(), INDICATOR).outcome, "FOUND")
        corrupted_crc = whole[:-8] + bytes([whole[-8] ^ 0xFF]) + whole[-7:]
        for name, payload in (("missing trailer", whole[:-8]), ("truncated", whole[:-3]), ("crc failure", corrupted_crc),
                              ("concatenated members", whole + gzip.compress(body)), ("trailing data", whole + b"junk")):
            with self.subTest(case=name):
                r = self.adapter(FakeTransport(ok(payload, gz))).lookup(policy(), INDICATOR)
                self.assertEqual((r.outcome, r.safe_error_category), ("INVALID_RESPONSE", "SCHEMA_INVALID_RESPONSE"))
                self.assertIsNone(r.artifact)
