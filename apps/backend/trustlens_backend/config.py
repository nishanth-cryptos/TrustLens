"""S2 authentication settings. Fail closed: missing or unsafe configuration disables sign-in rather than weakening it.

Secrets come from process variables or explicitly named files outside Git and are never part of repr() or logs.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

from dotenv import dotenv_values

from .disposable import PermanentConfigurationRefused, guard_env_file


class AuthConfigurationError(ValueError):
    pass


LOOPBACK_HOST = "127.0.0.1"

# Bounded runtime parameters for the authentication slice (T09 subset; values recorded in PLAN-001 T05 profile).
DEFAULTS = {
    "TRUSTLENS_OIDC_TRANSACTION_SECONDS": 300,      # login must complete within 5 minutes
    "TRUSTLENS_SESSION_IDLE_SECONDS": 1800,         # 30 minutes without a request ends the session
    "TRUSTLENS_SESSION_ABSOLUTE_SECONDS": 28800,    # 8 hours after sign-in, whatever the activity
    "TRUSTLENS_PROVIDER_TIMEOUT_SECONDS": 5,        # each request to the identity provider
    "TRUSTLENS_MAX_PENDING_TRANSACTIONS": 1000,     # concurrent unfinished sign-ins
    "TRUSTLENS_MAX_SESSIONS": 10000,                # concurrent sessions held in this process
}
LIMITS = {   # (minimum, maximum) accepted for each bounded parameter
    "TRUSTLENS_OIDC_TRANSACTION_SECONDS": (60, 600),
    "TRUSTLENS_SESSION_IDLE_SECONDS": (300, 7200),
    "TRUSTLENS_SESSION_ABSOLUTE_SECONDS": (900, 43200),
    "TRUSTLENS_PROVIDER_TIMEOUT_SECONDS": (1, 15),
    "TRUSTLENS_MAX_PENDING_TRANSACTIONS": (10, 10000),
    "TRUSTLENS_MAX_SESSIONS": (10, 100000),
}
MAX_CALLBACK_PARAMETER_LENGTH = {"code": 4096, "state": 128, "iss": 512, "error": 64, "session_state": 256}
MAX_PROVIDER_RESPONSE_BYTES = 256 * 1024


def _origin(url: str, name: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise AuthConfigurationError(f"{name} must be an absolute http(s) URL without credentials, query or fragment")
    if parts.scheme == "http" and parts.hostname != LOOPBACK_HOST:
        raise AuthConfigurationError(f"{name} may use plain HTTP only on {LOOPBACK_HOST} (loopback development)")
    return f"{parts.scheme}://{parts.netloc}"


@dataclass(frozen=True)
class AuthSettings:
    issuer: str
    client_id: str
    client_secret: str = field(repr=False)
    redirect_uri: str
    app_origin: str
    post_logout_redirect_uri: str
    transaction_seconds: int
    session_idle_seconds: int
    session_absolute_seconds: int
    provider_timeout_seconds: int
    max_pending_transactions: int
    max_sessions: int

    @property
    def secure_cookies(self) -> bool:
        """Secure cookies always under HTTPS; plain HTTP is accepted only for the loopback development profile."""
        return urlsplit(self.app_origin).scheme == "https" or urlsplit(self.redirect_uri).scheme == "https"

    @property
    def backend_origin(self) -> str:
        return _origin(self.redirect_uri, "TRUSTLENS_OIDC_REDIRECT_URI")

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None):
        env = dict(os.environ if environment is None else environment)
        required = ("TRUSTLENS_OIDC_ISSUER", "TRUSTLENS_OIDC_CLIENT_ID", "TRUSTLENS_OIDC_CLIENT_SECRET")
        if not all(env.get(k) for k in required):
            raise AuthConfigurationError("Set TRUSTLENS_OIDC_ISSUER, TRUSTLENS_OIDC_CLIENT_ID and TRUSTLENS_OIDC_CLIENT_SECRET outside Git")
        issuer = env["TRUSTLENS_OIDC_ISSUER"].rstrip("/")
        redirect_uri = env.get("TRUSTLENS_OIDC_REDIRECT_URI", f"http://{LOOPBACK_HOST}:8000/auth/callback")
        app_origin = env.get("TRUSTLENS_APP_ORIGIN", f"http://{LOOPBACK_HOST}:5173").rstrip("/")
        post_logout = env.get("TRUSTLENS_OIDC_POST_LOGOUT_REDIRECT_URI", app_origin + "/")
        _origin(issuer, "TRUSTLENS_OIDC_ISSUER")
        if _origin(app_origin, "TRUSTLENS_APP_ORIGIN") != app_origin:
            raise AuthConfigurationError("TRUSTLENS_APP_ORIGIN must be an origin (scheme, host and port only)")
        _origin(redirect_uri, "TRUSTLENS_OIDC_REDIRECT_URI")
        _origin(post_logout, "TRUSTLENS_OIDC_POST_LOGOUT_REDIRECT_URI")
        if urlsplit(redirect_uri).path != "/auth/callback":
            raise AuthConfigurationError("TRUSTLENS_OIDC_REDIRECT_URI must end at the registered /auth/callback route")
        if "localhost" in (issuer + redirect_uri + app_origin + post_logout).lower():
            raise AuthConfigurationError(f"Use {LOOPBACK_HOST} consistently; do not mix localhost into browser URLs")
        numbers = {}
        for key, default in DEFAULTS.items():
            try:
                value = int(env.get(key, default))
            except ValueError:
                raise AuthConfigurationError(f"{key} must be an integer") from None
            low, high = LIMITS[key]
            if not low <= value <= high:
                raise AuthConfigurationError(f"{key} must be between {low} and {high}")
            numbers[key] = value
        if numbers["TRUSTLENS_SESSION_IDLE_SECONDS"] > numbers["TRUSTLENS_SESSION_ABSOLUTE_SECONDS"]:
            raise AuthConfigurationError("Session idle timeout cannot exceed the absolute session lifetime")
        return cls(issuer=issuer, client_id=env["TRUSTLENS_OIDC_CLIENT_ID"], client_secret=env["TRUSTLENS_OIDC_CLIENT_SECRET"],
                   redirect_uri=redirect_uri, app_origin=app_origin, post_logout_redirect_uri=post_logout,
                   transaction_seconds=numbers["TRUSTLENS_OIDC_TRANSACTION_SECONDS"],
                   session_idle_seconds=numbers["TRUSTLENS_SESSION_IDLE_SECONDS"],
                   session_absolute_seconds=numbers["TRUSTLENS_SESSION_ABSOLUTE_SECONDS"],
                   provider_timeout_seconds=numbers["TRUSTLENS_PROVIDER_TIMEOUT_SECONDS"],
                   max_pending_transactions=numbers["TRUSTLENS_MAX_PENDING_TRANSACTIONS"],
                   max_sessions=numbers["TRUSTLENS_MAX_SESSIONS"])


def load_environment_files(environment: Mapping[str, str] | None = None) -> dict:
    """Process variables, then files named by TRUSTLENS_OIDC_ENV_FILE / TRUSTLENS_APP_DB_ENV_FILE (never override).

    In disposable test mode every named file passes the shared guard first: permanent configuration is refused before
    any existence check or read (fail closed: authentication stays disabled)."""
    env = dict(os.environ if environment is None else environment)
    for variable in ("TRUSTLENS_OIDC_ENV_FILE", "TRUSTLENS_APP_DB_ENV_FILE"):
        name = env.get(variable)
        if not name:
            continue
        try:
            path = guard_env_file(name, env)
        except PermanentConfigurationRefused:
            raise AuthConfigurationError(f"{variable} names permanent configuration, refused in disposable test mode") from None
        if not path.is_file():
            raise AuthConfigurationError(f"{variable} names a file that does not exist")
        for key, value in dotenv_values(path).items():
            if value is not None:
                env.setdefault(key, value)
    return env
