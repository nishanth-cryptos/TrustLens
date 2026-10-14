"""CLI-first operator interaction for local knowledge activation (DEC-011). Never runs automatically.

    python -m trustlens_backend.knowledge_cli install-bundle --gate PASS     # after run_all.py passed (make knowledge-bundle)
    python -m trustlens_backend.knowledge_cli activate --digest <exact sha256> --governance-change-ref <REF>

install-bundle builds the bundle with the existing publisher (knowledge/publish/build_bundle.py). It installs it only
when its exact content digest is approved in this deployment's committed release record
(apps/backend/knowledge_releases/<deployment>.json), so arbitrary working-tree content can never become authoritative.
It is stored content-addressed at <TRUSTLENS_KNOWLEDGE_ROOT>/<digest>/ and never overwritten.

activate is an ordinary HTTP client of the accepted activateKnowledgeBundle operation:
- it signs in through the normal OIDC code flow as a user agent. The password is read with getpass and never stored,
  echoed or logged. The identity provider is the configured OIDC issuer, never one named by a redirect, and every
  redirect hop is validated before it is requested (see sign_in). Local synthetic profile only; this is not
  production operator authentication;
- it reads the current state as the precondition, then shows the exact digest and the current active digest;
- it requires the operator to type the digest's first 12 characters to confirm;
- it sends the request with the session's CSRF token, the app Origin and a fresh Idempotency-Key, prints the outcome,
  and signs out.
It never connects to the database. The server enforces ADMINISTRATOR authorization, the release approval, pre-activation
validation and the governed audit event; the CLI cannot bypass any of them.
"""
import argparse
import getpass
import html
import json
import os
import secrets
import shutil
import sys
import uuid
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

from .knowledge_seam import DEFAULT_DEPLOYMENT_REF, DEFAULT_KNOWLEDGE_ROOT, BundleRejected, KnowledgeVerifier, NotEligible, release_entry

DEFAULT_BACKEND = "http://127.0.0.1:8000"
DEFAULT_APP_ORIGIN = "http://127.0.0.1:5173"
MAX_REDIRECTS = 8


class CliError(Exception):
    """A refusal with a safe, content-free message."""


# ---------------------------------------------------------------- install-bundle
class _Runtime:
    def __init__(self, deployment_ref, release_dir=None):
        self.deployment_ref, self.knowledge_release_dir = deployment_ref, release_dir


def install_bundle(root: Path, deployment_ref: str, gate: str, release_dir=None, builder=None) -> str:
    if gate != "PASS":
        raise CliError("refusing to install a bundle whose publication gate did not pass (run run_all.py first)")
    from knowledge.publish.build_bundle import build
    builder = builder or build
    root = Path(root).expanduser()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    staging = root / f".staging-{secrets.token_hex(8)}"
    try:
        manifest = builder(staging, gate=gate)
        digest = manifest["content_digest"]
        try:
            release_entry(_Runtime(deployment_ref, release_dir), digest)
        except NotEligible as refused:
            raise CliError(f"built bundle {digest[:12]}… is not approved for {deployment_ref} ({refused.reason})") from None
        target = root / digest
        if target.exists():
            KnowledgeVerifier(root).verify(digest)              # already installed: it must still verify
            return digest
        staging.rename(target)
        try:
            KnowledgeVerifier(root).verify(digest)
        except BundleRejected as rejected:
            shutil.rmtree(target)
            raise CliError(f"installed bundle failed verification ({rejected.reason})") from None
        return digest
    finally:
        if staging.exists():
            shutil.rmtree(staging)


# ---------------------------------------------------------------- sign-in as a user agent
class _LoginForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms, self._current = [], None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self._current = {"action": a.get("action", ""), "inputs": {}, "password": False}
            self.forms.append(self._current)
        elif tag == "input" and self._current is not None and a.get("name"):
            if a.get("type") == "password":
                self._current["password"] = True
            elif a.get("type") == "hidden":
                self._current["inputs"][a["name"]] = a.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self._current = None


def login_form(page: str) -> tuple[str, dict]:
    parser = _LoginForm()
    parser.feed(page)
    forms = [f for f in parser.forms if f["password"]]
    if len(forms) != 1 or not forms[0]["action"]:
        raise CliError("the identity provider did not present a single password sign-in form")
    return html.unescape(forms[0]["action"]), forms[0]["inputs"]


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def expected_idp_origin(issuer: str, backend: str, app_origin: str) -> str:
    """The identity-provider origin from trusted, validated configuration (the OIDC issuer), never from a redirect.
    It must be HTTPS or loopback HTTP and must not be the TrustLens backend or app origin, even on loopback."""
    parts = urlsplit(issuer or "")
    if not parts.hostname or not (parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in ("127.0.0.1", "::1"))):
        raise CliError("the configured identity provider must use HTTPS or the loopback development profile")
    origin = _origin(issuer)
    if origin in (_origin(backend), _origin(app_origin)):
        raise CliError("the configured identity provider origin is the TrustLens backend or app; refusing")
    return origin


def _next_hop(response, base_url: str) -> str | None:
    if response.status_code in (301, 302, 303, 307, 308):
        location = response.headers.get("location")
        if not location:
            raise CliError("the identity provider sent a redirect without a destination")
        return urljoin(base_url, location)
    return None


def sign_in(client: httpx.Client, username: str, password: str, app_origin: str, idp_origin: str,
            idp: httpx.Client | None = None) -> None:
    """Authorization-code sign-in through the backend's own /auth/login and /auth/callback (no new route, no bypass).

    The backend keeps the PKCE verifier, client secret and tokens; the CLI only ever holds the session cookie.
    Constraints (local synthetic profile only; not production operator authentication):
    - idp_origin comes from validated configuration (expected_idp_origin), never from the login redirect;
    - no redirect is followed automatically; every next hop is validated BEFORE it is requested. IdP hops must stay on
      exactly idp_origin (same scheme: no downgrade); cycles and more than MAX_REDIRECTS hops are refused;
    - the password is posted only to a form whose action is on idp_origin;
    - the backend is contacted only for /auth/login and, once, for its accepted /auth/callback, with its own cookie jar,
      and that callback must redirect to the app origin. IdP cookies never travel to the backend and vice versa."""
    backend = _origin(str(client.base_url))
    if idp_origin in (backend, _origin(app_origin)):
        raise CliError("the identity provider origin is the TrustLens backend or app; refusing")
    start = client.get("/auth/login", follow_redirects=False)
    login_url = _next_hop(start, str(start.url)) if start.status_code == 303 else None
    if login_url is None:
        raise CliError("sign-in is unavailable on the backend")
    own_idp = idp is None
    idp = idp or httpx.Client(trust_env=False, timeout=15)
    visited: set[str] = set()

    def idp_get(url: str):
        if _origin(url) != idp_origin:                       # checked before any request is sent
            raise CliError("sign-in redirected away from the configured identity provider")
        if url in visited or len(visited) >= MAX_REDIRECTS:
            raise CliError("sign-in redirect loop or too many redirects")
        visited.add(url)
        return idp.get(url, follow_redirects=False)
    try:
        page = idp_get(login_url)
        while (hop := _next_hop(page, str(page.url))) is not None:
            page = idp_get(hop)                              # IdP-internal hops only, before credentials
        if page.status_code != 200:
            raise CliError("unexpected identity provider response")
        action, fields = login_form(page.text)
        action = urljoin(str(page.url), action)
        if _origin(action) != idp_origin:
            raise CliError("the sign-in form points outside the configured identity provider")
        response = idp.post(action, data={**fields, "username": username, "password": password}, follow_redirects=False)
        while True:
            target = _next_hop(response, str(response.url))
            if target is None:
                raise CliError("sign-in was not accepted")
            if _origin(target) == idp_origin:
                response = idp_get(target)
                continue
            parts = urlsplit(target)
            if _origin(target) != backend or parts.path != "/auth/callback":
                raise CliError("sign-in did not return to the backend's registered callback")
            callback = client.get(target, follow_redirects=False)   # the one constrained backend step
            done = _next_hop(callback, str(callback.url)) if callback.status_code == 303 else None
            if done is None or done.rstrip("/") != app_origin.rstrip("/"):
                raise CliError("sign-in did not complete (refused or failed)")
            return
    finally:
        if own_idp:
            idp.close()                                      # IdP cookies are discarded with this client


# ---------------------------------------------------------------- activation through the accepted API
def _unsafe_headers(client, app_origin, extra=None):
    token = client.get("/auth/csrf")
    if token.status_code != 200:
        raise CliError("could not obtain a CSRF token for this session")
    return {"Origin": app_origin, "X-CSRF-Token": token.json()["csrf_token"], **(extra or {})}


def run_activation(client: httpx.Client, digest: str, governance_change_ref: str, app_origin: str, confirm, say=print) -> dict:
    me = client.get("/api/v1/me")
    if me.status_code != 200:
        raise CliError("not signed in")
    if "ADMINISTRATOR" not in me.json().get("roles", []):
        raise CliError("this account does not hold the ADMINISTRATOR role; activation would be refused")
    active = client.get("/api/v1/knowledge/active")
    if active.status_code != 200:
        raise CliError(f"could not read the current knowledge state (HTTP {active.status_code})")
    state = active.json()
    current = (state.get("active_bundle") or {}).get("content_digest")
    say(f"Deployment state: {state['deployment_state']}; currently active: {current or 'none'}")
    say(f"Requested exact bundle: {digest}")
    if not confirm(digest[:12]):
        raise CliError("not confirmed; nothing was changed")
    response = client.post("/api/v1/knowledge/deployment/activate",
                           json={"content_digest": digest, "expected_active_content_digest": current,
                                 "governance_change_ref": governance_change_ref},
                           headers=_unsafe_headers(client, app_origin, {"Idempotency-Key": f"kcli-{uuid.uuid4().hex}"}))
    body = response.json()
    if response.status_code != 202:
        raise CliError(f"activation refused: {body.get('error', {}).get('code', response.status_code)}")
    say(f"Activation {body['activation_id']}: {body['lifecycle_state']} / {body['outcome']} at {body['recorded_at']}")
    return body


def sign_out(client: httpx.Client, app_origin: str) -> None:
    try:
        client.post("/auth/logout", headers=_unsafe_headers(client, app_origin))
    except (CliError, httpx.HTTPError):
        pass


def _configured_issuer() -> str:
    """The issuer from the backend's own validated OIDC configuration (shared guarded loader; nothing else is kept)."""
    from .config import AuthConfigurationError, AuthSettings, load_environment_files
    try:
        return AuthSettings.from_environment(load_environment_files()).issuer
    except AuthConfigurationError:
        raise CliError("set --issuer or the backend OIDC configuration (TRUSTLENS_OIDC_ENV_FILE)") from None


def _typed_confirmation(expected: str) -> bool:
    return input(f"Type the first 12 characters of the digest ({expected}) to activate it: ").strip() == expected


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="TrustLens local knowledge operator CLI (DEC-011)")
    sub = parser.add_subparsers(dest="command", required=True)
    inst = sub.add_parser("install-bundle", help="publish and install the approved exact bundle")
    inst.add_argument("--gate", required=True, choices=["PASS"])
    act = sub.add_parser("activate", help="activate an exact approved bundle through the API")
    act.add_argument("--digest", required=True)
    act.add_argument("--governance-change-ref", required=True)
    act.add_argument("--backend", default=os.environ.get("TRUSTLENS_BACKEND_URL", DEFAULT_BACKEND))
    act.add_argument("--app-origin", default=os.environ.get("TRUSTLENS_APP_ORIGIN", DEFAULT_APP_ORIGIN))
    act.add_argument("--issuer", help="OIDC issuer; default: the validated TRUSTLENS_OIDC_ISSUER of the backend configuration")
    args = parser.parse_args(argv)
    deployment = os.environ.get("TRUSTLENS_DEPLOYMENT_REF", DEFAULT_DEPLOYMENT_REF)
    try:
        if args.command == "install-bundle":
            digest = install_bundle(Path(os.environ.get("TRUSTLENS_KNOWLEDGE_ROOT", DEFAULT_KNOWLEDGE_ROOT)), deployment, args.gate)
            print(f"Installed and verified exact bundle {digest} for {deployment}.")
            return 0
        if urlsplit(args.backend).hostname not in ("127.0.0.1", "::1"):
            raise CliError("the local operator CLI talks only to a loopback backend")
        issuer = args.issuer or _configured_issuer()
        idp_origin = expected_idp_origin(issuer, args.backend, args.app_origin)
        username = input("Username: ").strip()
        password = getpass.getpass("Password: ")
        with httpx.Client(base_url=args.backend, trust_env=False, timeout=15) as client:
            try:
                try:
                    sign_in(client, username, password, args.app_origin, idp_origin)
                finally:
                    password = None  # drop the only reference as soon as sign-in ends
                run_activation(client, args.digest, args.governance_change_ref, args.app_origin, _typed_confirmation)
            finally:
                sign_out(client, args.app_origin)
        return 0
    except CliError as error:
        print(f"Refused: {error}", file=sys.stderr)
        return 2
    except (httpx.HTTPError, json.JSONDecodeError):
        print("Refused: the backend or identity provider could not be reached.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
