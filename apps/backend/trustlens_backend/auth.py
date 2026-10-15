"""Browser authentication boundary (backend-for-frontend) and the accepted GET /api/v1/me operation.

/auth/* are authentication-integration routes, not API v1 product operations. The browser only ever holds an
opaque, HttpOnly session cookie; ID, access and refresh tokens and the client secret stay in this process.

Audit (ARCH-004 §9.2): sign-in success, sign-in failure and authorization denials are appended to the governed audit
chain with opaque identifiers and categorical reasons only. A session is issued only after its
AUTHENTICATION_SUCCEEDED event is committed; if that append fails, the sign-in fails closed. Failure and denial events
are recorded best-effort, because the request is already refused.
"""
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from .audit import AuditEvent, AuditUnavailable
from .config import MAX_CALLBACK_PARAMETER_LENGTH, AuthSettings
from .oidc import OIDCClient, OIDCError
from .principals import PrincipalStore, PrincipalStoreUnavailable
from .sessions import CapacityExceeded, SessionStore, TransactionStore, tokens_equal

AUTH_BOUNDARY_ROUTES = {"/auth/login", "/auth/callback", "/auth/csrf", "/auth/logout"}
TRANSACTION_COOKIE = "tl_oidc_tx"
CSRF_HEADER = "X-CSRF-Token"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache", "Referrer-Policy": "no-referrer"}
ERRORS = {   # API-001 §31 codes used by this slice (HTTP status, retryability, safe message)
    "UNAUTHENTICATED": (401, "RETRY_WITH_CHANGES", "Sign in to continue."),
    "FORBIDDEN": (403, "NOT_RETRYABLE", "This request is not permitted."),
    "INVALID_REQUEST": (400, "RETRY_WITH_CHANGES", "The request is not valid."),
    "NOT_FOUND": (404, "NOT_RETRYABLE", "Not found."),
    "IDEMPOTENCY_KEY_REUSED": (409, "RETRY_WITH_CHANGES", "This Idempotency-Key was already used for a different request."),
    "IDEMPOTENCY_IN_PROGRESS": (409, "RETRYABLE", "The original request with this Idempotency-Key is still in progress."),
    "STATE_CONFLICT": (409, "NOT_RETRYABLE", "This action is not allowed in the current state."),
    "EVALUATION_NOT_COMPLETED": (409, "RETRYABLE", "The evaluation has not completed; no result is available yet."),
    "REMOVED_UNDER_GOVERNANCE": (410, "NOT_RETRYABLE", "This was removed under governance."),
    "REPLAY_UNAVAILABLE": (409, "NOT_RETRYABLE", "Required pinned material is already known to be removed; replay is unavailable."),
    "PRECONDITION_FAILED": (412, "RETRY_WITH_CHANGES", "The expected state did not match. Refresh and try again."),
    "KNOWLEDGE_NOT_ELIGIBLE": (409, "NOT_RETRYABLE", "That exact knowledge bundle is not eligible for activation here."),
    "PAYLOAD_TOO_LARGE": (413, "RETRY_WITH_CHANGES", "The content exceeds the configured size bound."),
    "UNSUPPORTED_MEDIA_TYPE": (415, "RETRY_WITH_CHANGES", "This media type is not accepted."),
    "RATE_LIMITED": (429, "RETRYABLE", "Too many requests. Please wait and try again."),
    "INTEGRITY_FAILURE": (500, "NOT_RETRYABLE", "Stored content failed integrity verification and is withheld."),
    "DEPENDENCY_UNAVAILABLE": (503, "RETRYABLE", "Sign-in is temporarily unavailable."),
    "INTERNAL_ERROR": (500, "RETRYABLE", "Something went wrong."),
}


class AuditSink(Protocol):
    def record(self, event: AuditEvent) -> None: ...


@dataclass
class AuthRuntime:
    settings: AuthSettings
    oidc: OIDCClient
    transactions: TransactionStore
    sessions: SessionStore
    principals: PrincipalStore
    audit: AuditSink
    database: object | None = None      # DatabaseSettings for the S2 resource store (None: resource API unavailable)
    evidence_store: object | None = None          # EvidenceContentStore (built lazily from evidence_store_paths)
    evidence_store_paths: tuple | None = None     # (content directory, key-encryption key file)
    knowledge_verifier: object | None = None      # KnowledgeVerifier over the content-addressed bundle store (S3)
    deployment_ref: str = "local-development"     # knowledge_deployment_state.deployment_ref of this deployment
    knowledge_release_dir: object | None = None   # committed release records (default: apps/backend/knowledge_releases)
    evaluation_recovery: bool = False             # S5: run crash recovery for evaluations (the served app only)

    @property
    def session_cookie(self) -> str:
        return "__Host-tl_session" if self.settings.secure_cookies else "tl_session"


def api_error(request: Request, code: str, clear_session: AuthRuntime | None = None,
              field_errors: list[dict] | None = None, retry_after: int | None = None) -> JSONResponse:
    status, retryability, message = ERRORS[code]
    body = {"code": code, "message": message, "request_id": request.state.request_id, "retryability": retryability}
    if field_errors:
        body["field_errors"] = field_errors              # field paths and codes only; submitted values never echoed
    headers = dict(NO_STORE)
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    response = JSONResponse({"error": body}, status_code=status, headers=headers)
    if clear_session is not None:
        _clear_cookie(response, clear_session.session_cookie, "/", clear_session.settings.secure_cookies)
    return response


def _set_cookie(response: Response, name: str, value: str, path: str, secure: bool, max_age: int | None = None):
    response.set_cookie(name, value, max_age=max_age, path=path, secure=secure, httponly=True, samesite="lax")


def _clear_cookie(response: Response, name: str, path: str, secure: bool):
    response.delete_cookie(name, path=path, secure=secure, httponly=True, samesite="lax")


def _runtime(request: Request) -> AuthRuntime | None:
    return getattr(request.app.state, "auth", None)


def _audit(runtime: AuthRuntime, request: Request, event_type: str, outcome: str, reason: str | None = None,
           principal_id: str | None = None, operation: str | None = None, required: bool = False) -> bool:
    """Append one security event. Returns False if it could not be recorded; raises only when required=True."""
    metadata = {}
    if event_type.startswith("AUTHENTICATION_"):
        metadata["method"] = "OIDC_AUTHORIZATION_CODE_PKCE"
    if reason:
        metadata["reason"] = reason
    if operation:
        metadata["operation"] = operation
    event = AuditEvent(event_type=event_type, outcome=outcome, actor_kind="HUMAN", actor_principal_id=principal_id,
                       target_kind="PRINCIPAL", target_id=principal_id, correlation_id=request.state.request_id,
                       safe_metadata=metadata or None)
    try:
        runtime.audit.record(event)
        return True
    except AuditUnavailable:
        if required:
            raise
        return False


def trusted_origin(request: Request, runtime: AuthRuntime | None) -> bool:
    """State-changing requests must come from the configured application origin; no Origin means no trust."""
    if runtime is None:
        return False
    origin = request.headers.get("origin")
    site = request.headers.get("sec-fetch-site")
    return origin == runtime.settings.app_origin and site in (None, "same-origin")


def csrf_valid(request: Request, runtime: AuthRuntime) -> bool:
    session = runtime.sessions.get(request.cookies.get(runtime.session_cookie))
    return session is not None and tokens_equal(request.headers.get(CSRF_HEADER), session.csrf_token)


async def csrf_middleware(request: Request, call_next):
    """Origin check for every state-changing request, plus the synchronizer token for every protected one."""
    if request.method in UNSAFE_METHODS:
        runtime = _runtime(request)
        reason = None
        if not trusted_origin(request, runtime):
            reason = "UNTRUSTED_ORIGIN"
        elif (request.url.path.startswith("/api/") or request.url.path == "/auth/logout") and not csrf_valid(request, runtime):
            reason = "CSRF_TOKEN_INVALID"
        if reason:
            if runtime is not None:
                session = runtime.sessions.get(request.cookies.get(runtime.session_cookie))
                _audit(runtime, request, "AUTHORIZATION_DENIED", "DENIED", reason,
                       principal_id=session.principal_reference_id if session else None,
                       operation="LOGOUT" if request.url.path == "/auth/logout" else "STATE_CHANGING_REQUEST")
            return api_error(request, "FORBIDDEN")
    return await call_next(request)


def _back_to_app(runtime: AuthRuntime, outcome: str | None) -> RedirectResponse:
    target = runtime.settings.app_origin + "/" + (("?" + urlencode({"signin": outcome})) if outcome else "")
    return RedirectResponse(target, status_code=303, headers=NO_STORE)


def login(request: Request):
    runtime = _runtime(request)
    if runtime is None:
        return Response("Sign-in is unavailable.", status_code=503, media_type="text/plain", headers=NO_STORE)
    try:
        tx, binding = runtime.transactions.begin()
        location = runtime.oidc.authorization_url(tx)
    except (CapacityExceeded, OIDCError):
        return _back_to_app(runtime, "unavailable")
    response = RedirectResponse(location, status_code=303, headers=NO_STORE)
    _set_cookie(response, TRANSACTION_COOKIE, binding, "/auth", runtime.settings.secure_cookies, runtime.settings.transaction_seconds)
    return response


def _callback_parameters(request: Request) -> dict | None:
    items = request.query_params.multi_items()
    keys = [k for k, _ in items]
    allowed = set(MAX_CALLBACK_PARAMETER_LENGTH) | {"error_description", "error_uri"}
    if len(keys) != len(set(keys)) or not set(keys) <= allowed:
        return None
    params = dict(items)
    if any(len(params.get(k, "")) > limit for k, limit in MAX_CALLBACK_PARAMETER_LENGTH.items()):
        return None
    return params


def callback(request: Request):
    runtime = _runtime(request)
    if runtime is None:
        return Response("Sign-in is unavailable.", status_code=503, media_type="text/plain", headers=NO_STORE)
    params = _callback_parameters(request)
    previous_session = request.cookies.get(runtime.session_cookie)
    tx = None
    if params is not None and params.get("state"):
        tx = runtime.transactions.consume(params["state"], request.cookies.get(TRANSACTION_COOKIE))
    if tx is None:
        # Not a callback for a sign-in this browser started (missing, forged, replayed, expired or unbound state, or a
        # malformed request). Reject it without touching the current session or cookies, so an unsolicited cross-site
        # navigation can neither log the user out nor disturb a sign-in in progress (round-1 review finding 1).
        _audit(runtime, request, "AUTHENTICATION_FAILED", "FAILED",
               "CALLBACK_INVALID" if params is None or not params.get("state") else "STATE_INVALID")
        return _back_to_app(runtime, "failed")
    # From here the callback is bound to this browser's own sign-in: the established policy applies (a failed or denied
    # sign-in also ends any earlier session; a successful one rotates it).
    outcome, reason = "failed", None
    if "error" in params:
        reason = "PROVIDER_ERROR_RESPONSE"
    elif not params.get("code"):
        reason = "CODE_MISSING"
    else:
        try:
            if params.get("iss", runtime.settings.issuer) != runtime.settings.issuer or \
                    (runtime.oidc.metadata().get("authorization_response_iss_parameter_supported") and "iss" not in params):
                raise OIDCError("ISSUER_MISMATCH")      # RFC 9207 mix-up defence
            tokens = runtime.oidc.exchange_code(params["code"], tx.code_verifier)
            claims = runtime.oidc.validate_id_token(tokens["id_token"], tx.nonce)
            principal = runtime.principals.find_active(claims["iss"], claims["sub"])
            if principal is None:
                outcome, reason = "denied", None
                runtime.sessions.invalidate(previous_session)
                _audit(runtime, request, "AUTHORIZATION_DENIED", "DENIED", "PRINCIPAL_NOT_PROVISIONED", operation="SIGN_IN")
            else:
                refresh = tokens.get("refresh_token") if isinstance(tokens.get("refresh_token"), str) else None
                session_id = runtime.sessions.create(principal.principal_reference_id, tokens["id_token"], refresh,
                                                     replaces=previous_session)
                try:
                    _audit(runtime, request, "AUTHENTICATION_SUCCEEDED", "SUCCEEDED",
                           principal_id=principal.principal_reference_id, required=True)
                except AuditUnavailable:
                    runtime.sessions.invalidate(session_id)       # no unaudited session ever reaches the browser
                    raise
                response = _back_to_app(runtime, None)
                _set_cookie(response, runtime.session_cookie, session_id, "/", runtime.settings.secure_cookies)
                _clear_cookie(response, TRANSACTION_COOKIE, "/auth", runtime.settings.secure_cookies)
                return response
        except OIDCError as error:
            outcome = "unavailable" if error.category == "PROVIDER_UNAVAILABLE" else "failed"
            reason = error.category
        except (PrincipalStoreUnavailable, CapacityExceeded):
            outcome, reason = "unavailable", "DEPENDENCY_UNAVAILABLE"
        except AuditUnavailable:
            outcome, reason = "unavailable", None
    runtime.sessions.invalidate(previous_session)   # a failed or denied sign-in never leaves an earlier session behind
    if reason:
        _audit(runtime, request, "AUTHENTICATION_FAILED", "FAILED", reason)
    response = _back_to_app(runtime, outcome)
    _clear_cookie(response, runtime.session_cookie, "/", runtime.settings.secure_cookies)
    _clear_cookie(response, TRANSACTION_COOKIE, "/auth", runtime.settings.secure_cookies)
    return response


def csrf_token(request: Request):
    runtime = _runtime(request)
    if runtime is None:
        return api_error(request, "DEPENDENCY_UNAVAILABLE")
    session = runtime.sessions.get(request.cookies.get(runtime.session_cookie))
    if session is None:
        return api_error(request, "UNAUTHENTICATED", clear_session=runtime)
    return JSONResponse({"csrf_token": session.csrf_token}, headers=NO_STORE)


def logout(request: Request):
    runtime = _runtime(request)      # trusted Origin and CSRF token already enforced by csrf_middleware
    session = runtime.sessions.invalidate(request.cookies.get(runtime.session_cookie))
    ended = runtime.oidc.end_provider_session(session.refresh_token) if session else False
    response = JSONResponse({"status": "SIGNED_OUT", "provider_session": "ENDED" if ended else "NOT_CONFIRMED"}, headers=NO_STORE)
    _clear_cookie(response, runtime.session_cookie, "/", runtime.settings.secure_cookies)
    return response


def current_principal(request: Request, operation: str):
    """(runtime, principal, None) for an authenticated, active principal, or (runtime, None, error response).
    Roles are re-read from trusted state on every request; a revoked or deactivated principal loses its sessions."""
    runtime = _runtime(request)
    if runtime is None:
        return None, None, api_error(request, "DEPENDENCY_UNAVAILABLE")
    session_id = request.cookies.get(runtime.session_cookie)
    session = runtime.sessions.get(session_id)
    if session is None:
        return runtime, None, api_error(request, "UNAUTHENTICATED", clear_session=runtime if session_id else None)
    try:
        principal = runtime.principals.get_active(session.principal_reference_id)
    except PrincipalStoreUnavailable:
        return runtime, None, api_error(request, "DEPENDENCY_UNAVAILABLE")
    if principal is None:            # deactivated or every role revoked since sign-in
        runtime.sessions.invalidate_principal(session.principal_reference_id)
        _audit(runtime, request, "AUTHORIZATION_DENIED", "DENIED", "PRINCIPAL_INACTIVE_OR_NO_ROLE",
               principal_id=session.principal_reference_id, operation=operation)
        return runtime, None, api_error(request, "UNAUTHENTICATED", clear_session=runtime)
    return runtime, principal, None


def get_me(request: Request):
    """API-001 getMe: SELF, all five roles, MeResponse; roles re-read from trusted state on every request."""
    runtime, principal, error = current_principal(request, "GET_ME")
    if error is not None:
        return error
    return JSONResponse({"principal_id": principal.principal_reference_id, "principal_kind": principal.principal_kind,
                         "roles": list(principal.roles), "capabilities": []}, headers=NO_STORE)


def install(app: FastAPI):
    """Register the authentication-boundary routes and getMe directly on the application (a flat, auditable surface)."""
    app.add_api_route("/auth/login", login, methods=["GET"])
    app.add_api_route("/auth/callback", callback, methods=["GET"])
    app.add_api_route("/auth/csrf", csrf_token, methods=["GET"])
    app.add_api_route("/auth/logout", logout, methods=["POST"])
    app.add_api_route("/api/v1/me", get_me, methods=["GET"])
