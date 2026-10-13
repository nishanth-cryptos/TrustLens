"""OIDC relying-party operations for the backend-for-frontend profile (Authorization Code + PKCE S256).

ID tokens are verified by PyJWT against the provider's published keys (signature, issuer, audience, expiry, not-before,
issued-at); nonce and authorized-party binding are checked here. Every failure maps to a categorical OIDCError so no
token, code, credential or provider response detail can leak to a caller or a log.
"""
import json
import threading
import time
from urllib.parse import urlencode, urlsplit, quote

import httpx
import jwt

from .config import MAX_PROVIDER_RESPONSE_BYTES, AuthSettings
from .sessions import Transaction, pkce_challenge, tokens_equal

ALLOWED_ID_TOKEN_ALGORITHMS = ("RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "EdDSA")
CLOCK_LEEWAY_SECONDS = 30
JWKS_REFRESH_INTERVAL_SECONDS = 60
MAX_SUBJECT_LENGTH = 255


class OIDCError(Exception):
    """Categorical failure: PROVIDER_UNAVAILABLE, PROVIDER_RESPONSE_INVALID, CODE_EXCHANGE_REJECTED or ID_TOKEN_INVALID."""

    def __init__(self, category: str):
        super().__init__(category)
        self.category = category


class OIDCClient:
    def __init__(self, settings: AuthSettings, http: httpx.Client | None = None, clock=time.time):
        self.settings = settings
        self._http = http or httpx.Client(timeout=settings.provider_timeout_seconds, follow_redirects=False, trust_env=False)
        self._clock = clock
        self._lock = threading.Lock()
        self._metadata: dict | None = None
        self._jwks: jwt.PyJWKSet | None = None
        self._jwks_fetched = 0.0

    # ---- provider documents
    def _read(self, response: httpx.Response) -> dict:
        body = b""
        for chunk in response.iter_bytes():
            body += chunk
            if len(body) > MAX_PROVIDER_RESPONSE_BYTES:
                raise OIDCError("PROVIDER_RESPONSE_INVALID")
        try:
            value = json.loads(body)
        except ValueError:
            raise OIDCError("PROVIDER_RESPONSE_INVALID") from None
        if not isinstance(value, dict):
            raise OIDCError("PROVIDER_RESPONSE_INVALID")
        return value

    def _request(self, method: str, url: str, **kwargs) -> tuple[int, dict | None]:
        try:
            with self._http.stream(method, url, **kwargs) as response:
                status = response.status_code
                if status == 204:
                    return status, None
                return status, self._read(response)
        except httpx.HTTPError:
            raise OIDCError("PROVIDER_UNAVAILABLE") from None

    def metadata(self) -> dict:
        with self._lock:
            if self._metadata is not None:
                return self._metadata
        status, doc = self._request("GET", self.settings.issuer + "/.well-known/openid-configuration")
        if status != 200 or doc.get("issuer") != self.settings.issuer:
            raise OIDCError("PROVIDER_RESPONSE_INVALID")
        issuer_origin = "{0.scheme}://{0.netloc}".format(urlsplit(self.settings.issuer))
        for key in ("authorization_endpoint", "token_endpoint", "jwks_uri", "end_session_endpoint"):
            value = doc.get(key)
            if not isinstance(value, str) or "{0.scheme}://{0.netloc}".format(urlsplit(value)) != issuer_origin:
                raise OIDCError("PROVIDER_RESPONSE_INVALID")   # endpoints must stay on the configured issuer's origin
        if "S256" not in doc.get("code_challenge_methods_supported", []):
            raise OIDCError("PROVIDER_RESPONSE_INVALID")
        with self._lock:
            self._metadata = doc
        return doc

    def _keys(self, refresh: bool = False) -> jwt.PyJWKSet:
        now = self._clock()
        with self._lock:
            if self._jwks is not None and not (refresh and now - self._jwks_fetched >= JWKS_REFRESH_INTERVAL_SECONDS):
                return self._jwks
        status, doc = self._request("GET", self.metadata()["jwks_uri"])
        if status != 200:
            raise OIDCError("PROVIDER_RESPONSE_INVALID")
        try:
            keys = jwt.PyJWKSet.from_dict(doc)
        except (jwt.PyJWKSetError, jwt.InvalidKeyError, ValueError, TypeError):
            raise OIDCError("PROVIDER_RESPONSE_INVALID") from None
        with self._lock:
            self._jwks, self._jwks_fetched = keys, now
        return keys

    # ---- authorization request
    def authorization_url(self, tx: Transaction) -> str:
        params = {"response_type": "code", "client_id": self.settings.client_id, "redirect_uri": self.settings.redirect_uri,
                  "scope": "openid", "state": tx.state, "nonce": tx.nonce,
                  "code_challenge": pkce_challenge(tx.code_verifier), "code_challenge_method": "S256"}
        return self.metadata()["authorization_endpoint"] + "?" + urlencode(params)

    def _client_auth(self) -> tuple[str, str]:
        # RFC 6749 §2.3.1: client_secret_basic with form-urlencoded identifier and secret.
        return quote(self.settings.client_id, safe=""), quote(self.settings.client_secret, safe="")

    # ---- token exchange and ID-token validation
    def exchange_code(self, code: str, code_verifier: str) -> dict:
        status, body = self._request("POST", self.metadata()["token_endpoint"], auth=self._client_auth(),
                                     data={"grant_type": "authorization_code", "code": code,
                                           "redirect_uri": self.settings.redirect_uri, "code_verifier": code_verifier},
                                     headers={"Accept": "application/json"})
        if status in (400, 401):
            raise OIDCError("CODE_EXCHANGE_REJECTED")
        if status != 200 or not isinstance(body, dict) or not isinstance(body.get("id_token"), str):
            raise OIDCError("PROVIDER_RESPONSE_INVALID")
        if str(body.get("token_type", "")).lower() != "bearer":
            raise OIDCError("PROVIDER_RESPONSE_INVALID")
        return body

    def validate_id_token(self, id_token: str, expected_nonce: str) -> dict:
        try:
            header = jwt.get_unverified_header(id_token)
        except jwt.PyJWTError:
            raise OIDCError("ID_TOKEN_INVALID") from None
        algorithm, kid = header.get("alg"), header.get("kid")
        if algorithm not in ALLOWED_ID_TOKEN_ALGORITHMS or not isinstance(kid, str):
            raise OIDCError("ID_TOKEN_INVALID")      # rejects "none", HMAC and key-confusion attempts
        key = self._find_key(kid) or self._find_key(kid, refresh=True)
        if key is None:
            raise OIDCError("ID_TOKEN_INVALID")
        try:
            claims = jwt.decode(id_token, key=key.key, algorithms=[algorithm], audience=self.settings.client_id,
                                issuer=self.settings.issuer, leeway=CLOCK_LEEWAY_SECONDS,
                                options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]})
        except jwt.PyJWTError:
            raise OIDCError("ID_TOKEN_INVALID") from None
        audiences = claims["aud"] if isinstance(claims["aud"], list) else [claims["aud"]]
        azp = claims.get("azp")
        if (len(audiences) > 1 or azp is not None) and azp != self.settings.client_id:
            raise OIDCError("ID_TOKEN_INVALID")      # OIDC Core §3.1.3.7: authorized party must be this client
        if not tokens_equal(claims["nonce"], expected_nonce):   # type, ASCII shape and length first; then constant time
            raise OIDCError("ID_TOKEN_INVALID")
        if claims["iat"] > self._clock() + CLOCK_LEEWAY_SECONDS:
            raise OIDCError("ID_TOKEN_INVALID")
        subject = claims["sub"]
        if not isinstance(subject, str) or not 0 < len(subject) <= MAX_SUBJECT_LENGTH or not subject.isprintable():
            raise OIDCError("ID_TOKEN_INVALID")
        return claims

    def _find_key(self, kid: str, refresh: bool = False):
        keys = self._keys(refresh=refresh)
        for key in keys.keys:
            if key.key_id == kid and key.public_key_use in (None, "sig"):
                return key
        return None

    # ---- logout
    def end_provider_session(self, refresh_token: str | None) -> bool:
        """Back-channel end of the provider session (no token ever placed in a browser URL). Best effort, bounded."""
        if not refresh_token:
            return False
        try:
            status, _ = self._request("POST", self.metadata()["end_session_endpoint"], auth=self._client_auth(),
                                      data={"refresh_token": refresh_token})
        except OIDCError:
            return False
        return status in (200, 204)
