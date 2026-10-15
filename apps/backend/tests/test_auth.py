"""S2 authentication tests against a fake OIDC provider (real RSA signatures via PyJWT, served by httpx.MockTransport).

The real browser path uses the configured Keycloak; these controlled tests cover every rejection the real provider
cannot be made to produce on demand.
"""
import base64
import hashlib
import json
import time
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from trustlens_backend.audit import AuditUnavailable
from trustlens_backend.auth import AUTH_BOUNDARY_ROUTES, AuthRuntime
from trustlens_backend.config import AuthConfigurationError, AuthSettings
from trustlens_backend.main import create_app
from trustlens_backend.oidc import OIDCClient
from trustlens_backend.principals import Principal
from trustlens_backend.sessions import SessionStore, TransactionStore, pkce_challenge

ROOT = Path(__file__).resolve().parents[3]
ISSUER = "http://127.0.0.1:8081/realms/test"
CLIENT_ID = "trustlens-web"
SECRET = "synthetic-client-secret-for-tests"
APP = "http://127.0.0.1:5173"
BACKEND = "http://127.0.0.1:8000"
SUBJECT = "0b7f6c62-2f0a-4c55-9e64-6c1a3d4f9a01"
PRINCIPAL_ID = "5d1c8f0e-7a43-4b8e-9c6d-2e1f0a9b8c7d"


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


class FakeProvider:
    def __init__(self, clock):
        self.clock = clock
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        self.jwks = {"keys": [dict(jwk, kid="k1", use="sig", alg="RS256")]}
        self.codes = {}
        self.token_requests = []
        self.logout_requests = []
        self.down = False
        self.claims_override = {}
        self.token_signer = None

    def id_token(self, expected_nonce, **override):
        now = int(self.clock())
        claims = {"iss": ISSUER, "aud": CLIENT_ID, "azp": CLIENT_ID, "sub": SUBJECT, "nonce": expected_nonce,
                  "iat": now, "exp": now + 300, "nbf": now}
        claims.update(override)
        claims = {k: v for k, v in claims.items() if v is not None}
        key, alg, kid = self.token_signer or (self.key, "RS256", "k1")
        return jwt.encode(claims, key, algorithm=alg, headers={"kid": kid})

    def authorize(self, location):
        query = parse_qs(urlsplit(location).query)
        code = "code-" + query["state"][0][:8]
        self.codes[code] = (query["nonce"][0], query["code_challenge"][0])
        return code, query

    def handler(self, request: httpx.Request):
        if self.down:
            raise httpx.ConnectError("provider down")
        path = request.url.path
        if path.endswith("/.well-known/openid-configuration"):
            base = ISSUER + "/protocol/openid-connect"
            return httpx.Response(200, json={"issuer": ISSUER, "authorization_endpoint": base + "/auth",
                                             "token_endpoint": base + "/token", "jwks_uri": base + "/certs",
                                             "end_session_endpoint": base + "/logout", "code_challenge_methods_supported": ["S256"],
                                             "authorization_response_iss_parameter_supported": True})
        if path.endswith("/certs"):
            return httpx.Response(200, json=self.jwks)
        if path.endswith("/token"):
            form = parse_qs(request.content.decode())
            self.token_requests.append((request.headers.get("authorization"), form))
            code = form["code"][0]
            if code not in self.codes:
                return httpx.Response(400, json={"error": "invalid_grant"})
            nonce, challenge = self.codes.pop(code)        # provider codes are single use
            if pkce_challenge(form["code_verifier"][0]) != challenge or form["redirect_uri"][0] != BACKEND + "/auth/callback":
                return httpx.Response(400, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"token_type": "Bearer", "access_token": "synthetic-access-token-value",
                                             "refresh_token": "synthetic-refresh-token-value", "expires_in": 300,
                                             "id_token": self.id_token(nonce, **self.claims_override)})
        if path.endswith("/logout"):
            self.logout_requests.append((request.headers.get("authorization"), parse_qs(request.content.decode())))
            return httpx.Response(204)
        return httpx.Response(404)


class FakePrincipals:
    def __init__(self):
        self.by_identity = {(ISSUER, SUBJECT): PRINCIPAL_ID}
        self.roles = {PRINCIPAL_ID: ("USER",)}

    def find_active(self, issuer, subject):
        pid = self.by_identity.get((issuer, subject))
        return self.get_active(pid) if pid else None

    def get_active(self, pid):
        roles = self.roles.get(pid, ())
        return Principal(pid, "HUMAN", roles) if roles else None


class FakeAudit:
    def __init__(self):
        self.events = []
        self.fail = False

    def record(self, event):
        if self.fail:
            raise AuditUnavailable("synthetic audit outage")
        self.events.append(event)

    def types(self):
        return [(e.event_type, (e.safe_metadata or {}).get("reason")) for e in self.events]


def settings(**extra):
    env = {"TRUSTLENS_OIDC_ISSUER": ISSUER, "TRUSTLENS_OIDC_CLIENT_ID": CLIENT_ID, "TRUSTLENS_OIDC_CLIENT_SECRET": SECRET}
    env.update(extra)
    return AuthSettings.from_environment(env)


class AuthTestCase(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()            # monotonic clock for transactions and sessions (advanced by tests)
        self.wall = Clock()             # wall clock for ID tokens: PyJWT checks exp/nbf/iat against real time
        self.wall.now = time.time()
        self.provider = FakeProvider(self.wall)
        self.principals = FakePrincipals()
        self.audit = FakeAudit()
        s = settings()
        oidc = OIDCClient(s, httpx.Client(transport=httpx.MockTransport(self.provider.handler)), clock=self.wall)
        self.runtime = AuthRuntime(settings=s, oidc=oidc, transactions=TransactionStore(300, 100, clock=self.clock),
                                   sessions=SessionStore(1800, 28800, 100, clock=self.clock), principals=self.principals,
                                   audit=self.audit)
        app = create_app(self.runtime)
        from trustlens_backend.admission import Admission, BucketProfile
        generous = BucketProfile(capacity=10_000, refill_per_second=10_000)       # admission has its own tests
        app.state.admission = Admission(generous, generous)
        self.client = TestClient(app, base_url=BACKEND)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    # ---- helpers
    def login(self):
        response = self.client.get("/auth/login", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        code, query = self.provider.authorize(response.headers["location"])
        return response, code, query

    def callback(self, code, state, iss=ISSUER, **extra):
        params = {"code": code, "state": state, "iss": iss, **extra}
        return self.client.get("/auth/callback", params={k: v for k, v in params.items() if v is not None}, follow_redirects=False)

    def sign_in(self):
        _, code, query = self.login()
        response = self.callback(code, query["state"][0])
        self.assertEqual(response.headers["location"], APP + "/")
        return response

    def set_cookie_header(self, response, name):
        for header in response.headers.get_list("set-cookie"):
            cookie = SimpleCookie(header)
            if name in cookie:
                return header, cookie[name]
        return None, None

    def me(self):
        return self.client.get("/api/v1/me")


class LoginRedirectTests(AuthTestCase):
    def test_authorization_redirect_uses_pkce_s256_state_and_nonce(self):
        response = self.client.get("/auth/login", follow_redirects=False)
        location = urlsplit(response.headers["location"])
        self.assertEqual(f"{location.scheme}://{location.netloc}{location.path}", ISSUER + "/protocol/openid-connect/auth")
        q = {k: v[0] for k, v in parse_qs(location.query).items()}
        self.assertEqual(q["response_type"], "code")
        self.assertEqual(q["client_id"], CLIENT_ID)
        self.assertEqual(q["redirect_uri"], BACKEND + "/auth/callback")
        self.assertEqual(q["scope"], "openid")
        self.assertEqual(q["code_challenge_method"], "S256")
        self.assertEqual(len(q["code_challenge"]), 43)
        self.assertGreaterEqual(len(q["state"]), 43)
        self.assertGreaterEqual(len(q["nonce"]), 43)
        self.assertNotIn("code_verifier", q)
        self.assertNotIn(SECRET, response.headers["location"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        header, cookie = self.set_cookie_header(response, "tl_oidc_tx")
        self.assertIn("httponly", header.lower())
        self.assertIn("samesite=lax", header.lower())
        self.assertEqual(cookie["path"], "/auth")
        self.assertNotIn("secure", header.lower())          # loopback HTTP development profile only
        self.assertNotIn(q["state"], header)                 # the browser binding is not the state

    def test_each_login_gets_fresh_random_values(self):
        a = parse_qs(urlsplit(self.client.get("/auth/login", follow_redirects=False).headers["location"]).query)
        b = parse_qs(urlsplit(self.client.get("/auth/login", follow_redirects=False).headers["location"]).query)
        for key in ("state", "nonce", "code_challenge"):
            self.assertNotEqual(a[key], b[key])


class CallbackTests(AuthTestCase):
    def test_successful_sign_in_establishes_opaque_server_side_session(self):
        response = self.sign_in()
        header, cookie = self.set_cookie_header(response, "tl_session")
        self.assertIn("httponly", header.lower())
        self.assertIn("samesite=lax", header.lower())
        self.assertEqual(cookie["path"], "/")
        self.assertNotIn("domain", header.lower())
        auth, form = self.provider.token_requests[-1]
        self.assertEqual(base64.b64decode(auth.split()[1]).decode(), f"{CLIENT_ID}:{SECRET}")
        self.assertEqual(form["grant_type"], ["authorization_code"])
        self.assertTrue(43 <= len(form["code_verifier"][0]) <= 128)
        me = self.me()
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json(), {"principal_id": PRINCIPAL_ID, "principal_kind": "HUMAN", "roles": ["USER"], "capabilities": []})
        self.assertEqual(me.headers["cache-control"], "no-store")

    def test_no_token_or_secret_reaches_the_browser(self):
        responses = [self.sign_in(), self.me(), self.client.get("/auth/csrf")]
        for r in responses:
            exposed = r.text + json.dumps(dict(r.headers)) + json.dumps(r.headers.get_list("set-cookie"))
            for secret in ("synthetic-access-token-value", "synthetic-refresh-token-value", SECRET, "eyJ"):
                self.assertNotIn(secret, exposed)

    def test_missing_state_is_rejected(self):
        _, code, _ = self.login()
        response = self.callback(code, None)
        self.assertEqual(response.headers["location"], APP + "/?signin=failed")
        self.assertEqual(self.provider.token_requests, [])

    def test_unknown_state_is_rejected(self):
        _, code, _ = self.login()
        self.assertEqual(self.callback(code, "forged-state").headers["location"], APP + "/?signin=failed")
        self.assertEqual(self.provider.token_requests, [])

    def test_state_from_another_browser_is_rejected(self):
        _, code, query = self.login()
        self.client.cookies.clear()                       # attacker's browser lacks the transaction binding
        self.assertEqual(self.callback(code, query["state"][0]).headers["location"], APP + "/?signin=failed")
        self.assertEqual(self.provider.token_requests, [])

    def test_callback_replay_is_rejected(self):
        _, code, query = self.login()
        tx_cookie = self.client.cookies.get("tl_oidc_tx")
        first = self.callback(code, query["state"][0])
        self.assertEqual(first.headers["location"], APP + "/")
        self.client.cookies.set("tl_oidc_tx", tx_cookie, domain="127.0.0.1", path="/auth")
        replay = self.callback(code, query["state"][0])
        self.assertEqual(replay.headers["location"], APP + "/?signin=failed")
        self.assertEqual(len(self.provider.token_requests), 1)

    def test_expired_transaction_is_rejected(self):
        _, code, query = self.login()
        self.clock.now += 301
        self.assertEqual(self.callback(code, query["state"][0]).headers["location"], APP + "/?signin=failed")

    def test_provider_error_response_is_rejected(self):
        _, _, query = self.login()
        response = self.client.get("/auth/callback", params={"error": "access_denied", "state": query["state"][0], "iss": ISSUER},
                                   follow_redirects=False)
        self.assertEqual(response.headers["location"], APP + "/?signin=failed")

    def test_issuer_mix_up_parameter_is_rejected(self):
        _, code, query = self.login()
        self.assertEqual(self.callback(code, query["state"][0], iss="http://127.0.0.1:9999/realms/evil").headers["location"],
                         APP + "/?signin=failed")
        self.assertEqual(self.provider.token_requests, [])

    def test_missing_issuer_parameter_is_rejected_when_provider_advertises_it(self):
        _, code, query = self.login()
        self.assertEqual(self.callback(code, query["state"][0], iss=None).headers["location"], APP + "/?signin=failed")

    def test_duplicate_or_oversized_parameters_are_rejected(self):
        _, code, query = self.login()
        dup = self.client.get(f"/auth/callback?code={code}&code=x&state={query['state'][0]}&iss={ISSUER}", follow_redirects=False)
        self.assertEqual(dup.headers["location"], APP + "/?signin=failed")
        _, code, query = self.login()
        big = self.callback("c" * 5000, query["state"][0])
        self.assertEqual(big.headers["location"], APP + "/?signin=failed")

    def test_provider_outage_is_reported_as_unavailable(self):
        _, code, query = self.login()
        self.provider.down = True
        self.assertEqual(self.callback(code, query["state"][0]).headers["location"], APP + "/?signin=unavailable")


class IdTokenTests(AuthTestCase):
    def rejected(self, **claims):
        self.provider.claims_override = claims
        _, code, query = self.login()
        response = self.callback(code, query["state"][0])
        self.assertEqual(response.headers["location"], APP + "/?signin=failed")
        self.assertIsNone(self.set_cookie_header(response, "tl_session")[1].value or None)
        self.assertEqual(self.me().status_code, 401)

    def test_nonce_mismatch(self):
        self.rejected(nonce="different-nonce")

    def test_missing_nonce(self):
        self.rejected(nonce=None)

    def test_invalid_issuer(self):
        self.rejected(iss="http://127.0.0.1:8081/realms/other")

    def test_invalid_audience(self):
        self.rejected(aud="another-client")

    def test_foreign_authorized_party(self):
        self.rejected(aud=[CLIENT_ID, "another-client"], azp="another-client")

    def test_expired_token(self):
        self.rejected(exp=int(self.wall.now) - 120, iat=int(self.wall.now) - 600)

    def test_not_yet_valid_token(self):
        self.rejected(nbf=int(self.wall.now) + 600)

    def test_token_issued_in_the_future(self):
        self.rejected(iat=int(self.wall.now) + 600, exp=int(self.wall.now) + 900)

    def test_invalid_signature(self):
        self.provider.token_signer = (self.provider.other_key, "RS256", "k1")
        self.rejected()

    def test_unknown_key(self):
        self.provider.token_signer = (self.provider.other_key, "RS256", "k2")
        self.rejected()

    def test_hmac_and_none_algorithms_are_refused(self):
        self.provider.token_signer = (SECRET, "HS256", "k1")
        self.rejected()
        self.provider.token_signer = (None, "none", "k1")
        self.rejected()


class AuthorizationTests(AuthTestCase):
    def test_valid_but_unprovisioned_identity_is_denied(self):
        self.principals.by_identity.clear()
        _, code, query = self.login()
        response = self.callback(code, query["state"][0])
        self.assertEqual(response.headers["location"], APP + "/?signin=denied")
        self.assertEqual(self.me().status_code, 401)

    def test_principal_without_active_role_is_denied(self):
        self.principals.roles[PRINCIPAL_ID] = ()
        _, code, query = self.login()
        self.assertEqual(self.callback(code, query["state"][0]).headers["location"], APP + "/?signin=denied")

    def test_revocation_after_sign_in_ends_access_on_next_request(self):
        self.sign_in()
        self.assertEqual(self.me().status_code, 200)
        self.principals.roles[PRINCIPAL_ID] = ()
        self.assertEqual(self.me().status_code, 401)
        self.principals.roles[PRINCIPAL_ID] = ("USER",)
        self.assertEqual(self.me().status_code, 401)        # the session was invalidated, not merely refused once

    def test_browser_supplied_roles_and_identity_are_ignored(self):
        self.principals.by_identity.clear()
        _, code, query = self.login()
        self.callback(code, query["state"][0], role="ADMINISTRATOR")
        r = self.client.get("/api/v1/me", headers={"X-Roles": "ADMINISTRATOR", "X-User": SUBJECT})
        self.assertEqual(r.status_code, 401)

    def test_unauthenticated_envelope_matches_contract(self):
        r = self.me()
        catalog = json.loads((ROOT / "contracts/api/api-v1.json").read_text())
        body = r.json()["error"]
        self.assertEqual(r.status_code, 401)
        self.assertEqual(set(body), {f["name"] for f in catalog["schemas"]["ApiErrorBody"]["fields"] if f["required"]})
        self.assertEqual(body["code"], "UNAUTHENTICATED")
        self.assertEqual(body["retryability"], "RETRY_WITH_CHANGES")
        self.assertEqual(body["request_id"], r.headers["x-request-id"])

    def test_me_response_matches_contract(self):
        self.sign_in()
        catalog = json.loads((ROOT / "contracts/api/api-v1.json").read_text())
        op = next(o for o in catalog["operations"] if o["operation_id"] == "getMe")
        fields = {f["name"] for f in catalog["schemas"][op["response_schema"]]["fields"]}
        body = self.me().json()
        self.assertEqual(set(body), fields)
        roles = json.loads((ROOT / "contracts/postgresql/schema-v1.json").read_text())["vocabularies"]
        self.assertTrue(set(body["roles"]) <= set(roles["trustlens_role"]["values"]))
        self.assertIn(body["principal_kind"], roles["principal_kind"]["values"])


class SessionTests(AuthTestCase):
    def test_sign_in_rotates_session_and_invalidates_presented_one(self):
        self.sign_in()
        first = self.client.cookies.get("tl_session")
        self.sign_in()
        second = self.client.cookies.get("tl_session")
        self.assertNotEqual(first, second)
        self.client.cookies.set("tl_session", first, domain="127.0.0.1", path="/")
        self.assertEqual(self.me().status_code, 401)

    def test_attacker_chosen_session_value_is_never_adopted(self):
        self.client.cookies.set("tl_session", "attacker-chosen-value", domain="127.0.0.1", path="/")
        self.sign_in()
        self.assertNotEqual(self.client.cookies.get("tl_session"), "attacker-chosen-value")

    def test_denied_sign_in_invalidates_an_earlier_session(self):
        self.sign_in()
        earlier = self.client.cookies.get("tl_session")
        self.principals.by_identity.clear()
        _, code, query = self.login()
        self.callback(code, query["state"][0])
        self.client.cookies.set("tl_session", earlier, domain="127.0.0.1", path="/")
        self.assertEqual(self.me().status_code, 401)

    def test_idle_timeout(self):
        self.sign_in()
        self.clock.now += 1799
        self.assertEqual(self.me().status_code, 200)
        self.clock.now += 1800
        self.assertEqual(self.me().status_code, 401)

    def test_absolute_lifetime(self):
        self.sign_in()
        for _ in range(16):                       # active every 1700 s: idle limit never reached (27 200 s)
            self.clock.now += 1700
            self.assertEqual(self.me().status_code, 200)
        self.clock.now += 1700                    # 28 900 s > 8 h absolute lifetime
        self.assertEqual(self.me().status_code, 401)


class CsrfAndLogoutTests(AuthTestCase):
    def logout(self, origin=APP, token=True, site=None):
        headers = {}
        if origin:
            headers["Origin"] = origin
        if site:
            headers["Sec-Fetch-Site"] = site
        if token:
            headers["X-CSRF-Token"] = self.client.get("/auth/csrf").json()["csrf_token"]
        return self.client.post("/auth/logout", headers=headers)

    def test_logout_requires_trusted_origin(self):
        self.sign_in()
        self.assertEqual(self.logout(origin=None).status_code, 403)
        self.assertEqual(self.logout(origin="http://127.0.0.1:6666").status_code, 403)
        self.assertEqual(self.logout(origin="http://localhost:5173").status_code, 403)
        self.assertEqual(self.logout(site="cross-site").status_code, 403)
        self.assertEqual(self.me().status_code, 200)

    def test_logout_requires_csrf_token(self):
        self.sign_in()
        self.assertEqual(self.logout(token=False).status_code, 403)
        r = self.client.post("/auth/logout", headers={"Origin": APP, "X-CSRF-Token": "forged"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.me().status_code, 200)

    def test_logout_invalidates_session_and_ends_provider_session_server_side(self):
        self.sign_in()
        old = self.client.cookies.get("tl_session")
        r = self.logout()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"status": "SIGNED_OUT", "provider_session": "ENDED"})
        self.client.cookies.set("tl_session", old, domain="127.0.0.1", path="/")
        self.assertEqual(self.me().status_code, 401)
        auth, form = self.provider.logout_requests[-1]
        self.assertEqual(form["refresh_token"], ["synthetic-refresh-token-value"])
        self.assertNotIn("synthetic-refresh-token-value", r.text)

    def test_logout_survives_provider_failure(self):
        self.sign_in()
        old = self.client.cookies.get("tl_session")
        self.provider.down = True
        r = self.logout()
        self.assertEqual(r.json()["provider_session"], "NOT_CONFIRMED")
        self.client.cookies.set("tl_session", old, domain="127.0.0.1", path="/")
        self.assertEqual(self.me().status_code, 401)

    def test_future_protected_mutations_require_origin_and_token(self):
        self.sign_in()
        self.assertEqual(self.client.post("/api/v1/cases", headers={"Origin": APP}).status_code, 403)
        self.assertEqual(self.client.post("/api/v1/cases").status_code, 403)

    def test_no_wildcard_cors(self):
        r = self.client.options("/api/v1/me", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})
        self.assertNotIn("access-control-allow-origin", {k.lower() for k in r.headers})
        r = self.client.get("/api/v1/me", headers={"Origin": "http://evil.example"})
        self.assertNotIn("access-control-allow-origin", {k.lower() for k in r.headers})


class FailClosedTests(unittest.TestCase):
    def test_missing_configuration_disables_sign_in(self):
        with TestClient(create_app(None, configure_from_environment=False), base_url=BACKEND) as client:
            self.assertEqual(client.get("/auth/login", follow_redirects=False).status_code, 503)
            r = client.get("/api/v1/me")
            self.assertEqual(r.status_code, 503)
            self.assertEqual(r.json()["error"]["code"], "DEPENDENCY_UNAVAILABLE")
            self.assertEqual(client.post("/auth/logout", headers={"Origin": APP}).status_code, 403)
            self.assertEqual(client.get("/health/live").json(), {"status": "OK"})
            self.assertEqual(client.get("/health/ready").json(), {"status": "NOT_READY"})

    def test_configuration_rules(self):
        with self.assertRaises(AuthConfigurationError):
            AuthSettings.from_environment({})
        for bad in ({"TRUSTLENS_APP_ORIGIN": "http://192.168.1.5:5173"},
                    {"TRUSTLENS_OIDC_REDIRECT_URI": "http://localhost:8000/auth/callback"},
                    {"TRUSTLENS_APP_ORIGIN": "http://localhost:5173"},
                    {"TRUSTLENS_OIDC_REDIRECT_URI": "http://127.0.0.1:8000/other"},
                    {"TRUSTLENS_SESSION_IDLE_SECONDS": "10"},
                    {"TRUSTLENS_SESSION_ABSOLUTE_SECONDS": "999999"},
                    {"TRUSTLENS_PROVIDER_TIMEOUT_SECONDS": "x"},
                    {"TRUSTLENS_SESSION_IDLE_SECONDS": "7200", "TRUSTLENS_SESSION_ABSOLUTE_SECONDS": "3600"}):
            with self.subTest(bad=bad), self.assertRaises(AuthConfigurationError):
                settings(**bad)
        self.assertNotIn(SECRET, repr(settings()))
        self.assertFalse(settings().secure_cookies)
        https = settings(TRUSTLENS_APP_ORIGIN="https://trustlens.example", TRUSTLENS_OIDC_REDIRECT_URI="https://trustlens.example/auth/callback",
                         TRUSTLENS_OIDC_ISSUER="https://id.example/realms/x")
        self.assertTrue(https.secure_cookies)

    def test_secure_cookie_name_and_flag_under_https(self):
        s = settings(TRUSTLENS_APP_ORIGIN="https://trustlens.example", TRUSTLENS_OIDC_REDIRECT_URI="https://trustlens.example/auth/callback")
        runtime = AuthRuntime(s, None, TransactionStore(300, 10), SessionStore(1800, 28800, 10), FakePrincipals(), FakeAudit())
        self.assertEqual(runtime.session_cookie, "__Host-tl_session")


class AuditMappingTests(AuthTestCase):
    def test_successful_sign_in_records_authentication_succeeded(self):
        self.sign_in()
        self.assertEqual(self.audit.types(), [("AUTHENTICATION_SUCCEEDED", None)])
        e = self.audit.events[0]
        self.assertEqual((e.outcome, e.actor_kind, e.actor_principal_id, e.target_kind, e.target_id),
                         ("SUCCEEDED", "HUMAN", PRINCIPAL_ID, "PRINCIPAL", PRINCIPAL_ID))
        self.assertEqual(e.safe_metadata, {"method": "OIDC_AUTHORIZATION_CODE_PKCE"})

    def test_audit_failure_fails_sign_in_closed(self):
        self.audit.fail = True
        _, code, query = self.login()
        response = self.callback(code, query["state"][0])
        self.assertEqual(response.headers["location"], APP + "/?signin=unavailable")
        self.assertEqual(self.me().status_code, 401)
        self.assertEqual(len(self.runtime.sessions), 0)          # the session created before the append was discarded

    def test_failures_are_recorded_with_categorical_reasons(self):
        _, code, _ = self.login()
        self.callback(code, "forged-state")
        _, code, query = self.login()
        self.callback(code, query["state"][0], iss="http://127.0.0.1:9999/realms/evil")
        self.provider.claims_override = {"nonce": "wrong"}
        _, code, query = self.login()
        self.callback(code, query["state"][0])
        self.assertEqual(self.audit.types(), [("AUTHENTICATION_FAILED", "STATE_INVALID"),
                                              ("AUTHENTICATION_FAILED", "ISSUER_MISMATCH"),
                                              ("AUTHENTICATION_FAILED", "ID_TOKEN_INVALID")])
        self.assertTrue(all(e.actor_principal_id is None and e.outcome == "FAILED" for e in self.audit.events))

    def test_unprovisioned_identity_records_authorization_denied_without_identity(self):
        self.principals.by_identity.clear()
        _, code, query = self.login()
        self.callback(code, query["state"][0])
        self.assertEqual(self.audit.types(), [("AUTHORIZATION_DENIED", "PRINCIPAL_NOT_PROVISIONED")])
        e = self.audit.events[0]
        self.assertEqual((e.outcome, e.actor_principal_id, e.target_id), ("DENIED", None, None))

    def test_revoked_principal_records_authorization_denied(self):
        self.sign_in()
        self.principals.roles[PRINCIPAL_ID] = ()
        self.me()
        self.assertEqual(self.audit.types()[-1], ("AUTHORIZATION_DENIED", "PRINCIPAL_INACTIVE_OR_NO_ROLE"))
        self.assertEqual(self.audit.events[-1].actor_principal_id, PRINCIPAL_ID)

    def test_csrf_and_origin_denials_are_recorded_and_attributed(self):
        self.sign_in()
        self.client.post("/auth/logout", headers={"Origin": "http://127.0.0.1:6666"})
        self.client.post("/auth/logout", headers={"Origin": APP, "X-CSRF-Token": "forged"})
        self.assertEqual(self.audit.types()[-2:], [("AUTHORIZATION_DENIED", "UNTRUSTED_ORIGIN"),
                                                   ("AUTHORIZATION_DENIED", "CSRF_TOKEN_INVALID")])
        self.assertTrue(all(e.actor_principal_id == PRINCIPAL_ID for e in self.audit.events[-2:]))

    def test_denials_still_refuse_when_audit_is_unavailable(self):
        self.sign_in()
        self.audit.fail = True
        self.assertEqual(self.client.post("/auth/logout", headers={"Origin": "http://127.0.0.1:6666"}).status_code, 403)
        self.principals.roles[PRINCIPAL_ID] = ()
        self.assertEqual(self.me().status_code, 401)

    def test_no_sensitive_values_in_any_event(self):
        _, code, query = self.login()
        self.callback(code, "forged-state")
        self.sign_in()
        self.client.post("/auth/logout", headers={"Origin": APP, "X-CSRF-Token": "forged"})
        self.principals.by_identity.clear()
        _, code2, query2 = self.login()
        self.callback(code2, query2["state"][0])
        dump = json.dumps([e.__dict__ for e in self.audit.events], default=str)
        for secret in (SUBJECT, ISSUER, SECRET, code, code2, query["state"][0], query2["state"][0], "synthetic-access-token-value",
                       "synthetic-refresh-token-value", "eyJ", "127.0.0.1", "Mozilla"):
            self.assertNotIn(secret, dump)


class ReviewRound1Tests(AuthTestCase):
    """Independent review round 1: findings 1 (callback logout CSRF) and 2 (non-ASCII security values)."""

    def assert_still_signed_in(self, response):
        self.assertIsNone(self.set_cookie_header(response, "tl_session")[1])     # session cookie untouched
        self.assertEqual(self.me().status_code, 200)

    # ---- finding 1
    def test_signed_in_session_survives_unsolicited_invalid_state_callback(self):
        self.sign_in()
        r = self.client.get("/auth/callback", params={"state": "unknown", "code": "invalid"}, follow_redirects=False)
        self.assertEqual(r.headers["location"], APP + "/?signin=failed")
        self.assert_still_signed_in(r)
        self.assertEqual(self.audit.types()[-1], ("AUTHENTICATION_FAILED", "STATE_INVALID"))

    def test_signed_in_session_survives_callbacks_without_state_or_with_malformed_parameters(self):
        self.sign_in()
        for params in ({"code": "invalid"}, {}, {"state": "x", "unexpected": "y"}, {"state": "s" * 500, "code": "c"}):
            with self.subTest(params=params):
                self.assert_still_signed_in(self.client.get("/auth/callback", params=params, follow_redirects=False))

    def test_signed_in_session_survives_callback_without_browser_binding(self):
        self.sign_in()
        _, code, query = self.login()
        self.client.cookies.delete("tl_oidc_tx", domain="127.0.0.1", path="/auth")
        r = self.callback(code, query["state"][0])
        self.assertEqual(r.headers["location"], APP + "/?signin=failed")
        self.assert_still_signed_in(r)
        self.assertEqual(len(self.provider.token_requests), 1)          # only the original sign-in exchanged a code

    def test_callback_replay_cannot_log_out_the_current_user(self):
        _, code, query = self.login()
        tx_cookie = self.client.cookies.get("tl_oidc_tx")
        self.callback(code, query["state"][0])
        self.client.cookies.set("tl_oidc_tx", tx_cookie, domain="127.0.0.1", path="/auth")
        self.assert_still_signed_in(self.callback(code, query["state"][0]))

    def test_legitimate_reauthentication_still_rotates_the_session(self):
        self.sign_in()
        first = self.client.cookies.get("tl_session")
        self.sign_in()
        self.assertNotEqual(self.client.cookies.get("tl_session"), first)
        self.client.cookies.set("tl_session", first, domain="127.0.0.1", path="/")
        self.assertEqual(self.me().status_code, 401)

    def test_validated_reauthentication_failure_follows_fail_closed_policy(self):
        for failure in ("provider_error", "bad_nonce"):
            with self.subTest(failure=failure):
                self.provider.claims_override = {}
                self.sign_in()
                _, code, query = self.login()                     # browser-bound transaction: policy applies
                if failure == "provider_error":
                    r = self.client.get("/auth/callback", params={"error": "access_denied", "state": query["state"][0], "iss": ISSUER},
                                        follow_redirects=False)
                else:
                    self.provider.claims_override = {"nonce": "wrong"}
                    r = self.callback(code, query["state"][0])
                self.assertEqual(r.headers["location"], APP + "/?signin=failed")
                self.assertEqual(self.me().status_code, 401)

    # ---- finding 2
    def test_non_ascii_nonce_is_a_safe_authentication_failure(self):
        self.provider.claims_override = {"nonce": "nonce-\u00e9-\u4e2d"}
        _, code, query = self.login()
        r = self.callback(code, query["state"][0])
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], APP + "/?signin=failed")
        self.assertEqual(self.audit.types()[-1], ("AUTHENTICATION_FAILED", "ID_TOKEN_INVALID"))
        self.assertEqual(self.me().status_code, 401)

    def test_malformed_nonce_types_and_lengths_are_rejected(self):
        for nonce in (12345, ["n"], {"n": 1}, "n" * 129, ""):
            with self.subTest(nonce=nonce):
                self.provider.claims_override = {"nonce": nonce}
                _, code, query = self.login()
                self.assertEqual(self.callback(code, query["state"][0]).headers["location"], APP + "/?signin=failed")
        self.assertEqual(self.me().status_code, 401)

    def test_non_ascii_csrf_header_is_a_safe_denial(self):
        self.sign_in()
        r = self.client.post("/auth/logout", headers={"Origin": APP, "X-CSRF-Token": "tok\u00e9n-\u4e2d".encode("utf-8")})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["error"]["code"], "FORBIDDEN")
        self.assertEqual(self.audit.types()[-1], ("AUTHORIZATION_DENIED", "CSRF_TOKEN_INVALID"))
        self.assertEqual(self.audit.events[-1].actor_principal_id, PRINCIPAL_ID)
        self.assertEqual(self.me().status_code, 200)                    # nothing was authorized, nothing was ended

    def test_oversized_or_malformed_csrf_values_are_safe_denials(self):
        self.sign_in()
        for token in ("a" * 129, "has space", "x" * 10000, "tok<script>"):
            with self.subTest(length=len(token)):
                self.assertEqual(self.client.post("/auth/logout", headers={"Origin": APP, "X-CSRF-Token": token}).status_code, 403)
        self.assertEqual(self.me().status_code, 200)

    def test_non_ascii_state_and_session_cookie_are_safe_rejections(self):
        self.sign_in()
        r = self.client.get("/auth/callback?state=%C3%A9%E4%B8%AD&code=x", follow_redirects=False)
        self.assertEqual(r.headers["location"], APP + "/?signin=failed")
        self.assertEqual(self.me().status_code, 200)
        r = self.client.get("/api/v1/me", headers={"Cookie": "tl_session=t\u00e9".encode("utf-8")})
        self.assertEqual(r.status_code, 401)

    def test_valid_ascii_nonce_and_csrf_still_succeed(self):
        self.sign_in()
        token = self.client.get("/auth/csrf").json()["csrf_token"]
        self.assertEqual(self.client.post("/auth/logout", headers={"Origin": APP, "X-CSRF-Token": token}).status_code, 200)

    def test_rejected_values_are_never_echoed(self):
        self.sign_in()
        bad = "tok\u00e9n-secret-marker"
        r = self.client.post("/auth/logout", headers={"Origin": APP, "X-CSRF-Token": bad.encode("utf-8")})
        r2 = self.client.get("/auth/callback", params={"state": "state-secret-marker", "code": "code-secret-marker"}, follow_redirects=False)
        exposed = r.text + json.dumps(dict(r.headers)) + r2.text + json.dumps(dict(r2.headers)) + \
            json.dumps([e.__dict__ for e in self.audit.events], default=str)
        for marker in ("secret-marker", "tok\u00e9n"):
            self.assertNotIn(marker, exposed)


class PkceTests(unittest.TestCase):
    def test_challenge_is_rfc7636_s256(self):
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"   # RFC 7636 Appendix B
        self.assertEqual(pkce_challenge(verifier), "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")
        tx, _ = TransactionStore(300, 10).begin()
        self.assertTrue(43 <= len(tx.code_verifier) <= 128)
        self.assertTrue(set(tx.code_verifier) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"))


class RouteSurfaceTests(unittest.TestCase):
    def test_only_contract_operations_and_documented_auth_boundary_routes(self):
        catalog = json.loads((ROOT / "contracts/api/api-v1.json").read_text())
        probes = {o["path"] for o in catalog["operations"] if o.get("internal")}
        me = next(o["path"] for o in catalog["operations"] if o["operation_id"] == "getMe")
        from trustlens_backend.cases import OPERATIONS
        from trustlens_backend.evidence import OPERATIONS as EVIDENCE_OPERATIONS
        from trustlens_backend.knowledge_seam import OPERATIONS as KNOWLEDGE_OPERATIONS
        from trustlens_backend.evaluation import OPERATIONS as EVALUATION_OPERATIONS
        from trustlens_backend.history import OPERATIONS as HISTORY_OPERATIONS
        s2 = {o["path"] for o in catalog["operations"]
              if o["operation_id"] in {**OPERATIONS, **EVIDENCE_OPERATIONS, **KNOWLEDGE_OPERATIONS, **EVALUATION_OPERATIONS,
                                       **HISTORY_OPERATIONS}}
        app = create_app(None, configure_from_environment=False)
        self.assertEqual({r.path for r in app.routes}, probes | {me} | s2 | AUTH_BOUNDARY_ROUTES)
        served = {(m, r.path) for r in app.routes for m in getattr(r, "methods", ()) if r.path.startswith("/api/")}
        catalogued = {(o["method"], o["path"]) for o in catalog["operations"]}
        self.assertTrue(served <= catalogued, served - catalogued)          # no invented operation or method
        self.assertFalse(any(p.startswith(catalog["base_path"]) for p in AUTH_BOUNDARY_ROUTES))
        # DEC-011 scope: only activateKnowledgeBundle is served; rollback and withdrawal stay with S9 (PLAN-001 §6).
        writes = {o["operation_id"]: (o["method"], o["path"]) for o in catalog["operations"]
                  if o["operation_id"] in {"activateKnowledgeBundle", "rollbackKnowledgeBundle", "withdrawKnowledgeBundle"}}
        self.assertEqual(len(writes), 3)
        self.assertIn(writes["activateKnowledgeBundle"], served)
        self.assertFalse({writes["rollbackKnowledgeBundle"], writes["withdrawKnowledgeBundle"]} & served)


if __name__ == "__main__":
    unittest.main()
