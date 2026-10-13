"""Loopback backend: internal probes, the browser authentication boundary and GET /api/v1/me.

Startup never connects to the database or the identity provider and never creates a schema. Missing or unsafe
authentication configuration disables sign-in (fail closed); it is never replaced by a development bypass.
"""
import sys
from uuid import uuid4

from fastapi import FastAPI, Request

from .audit import AuditUnavailable, PostgresAuditSink
from .auth import AuthRuntime, csrf_middleware, install
from .config import AuthConfigurationError, AuthSettings, load_environment_files
from .database import DatabaseConfigurationError, DatabaseSettings
from .oidc import OIDCClient
from .principals import PostgresPrincipalStore, PrincipalStoreUnavailable
from .sessions import SessionStore, TransactionStore


def runtime_from_environment(environment=None) -> AuthRuntime:
    env = load_environment_files(environment)
    settings = AuthSettings.from_environment(env)
    try:
        database = DatabaseSettings.from_environment(env)
        principals, audit = PostgresPrincipalStore(database), PostgresAuditSink(database)
    except (DatabaseConfigurationError, PrincipalStoreUnavailable, AuditUnavailable) as error:
        raise AuthConfigurationError(f"Application database: {error}") from None
    return AuthRuntime(settings=settings, oidc=OIDCClient(settings),
                       transactions=TransactionStore(settings.transaction_seconds, settings.max_pending_transactions),
                       sessions=SessionStore(settings.session_idle_seconds, settings.session_absolute_seconds, settings.max_sessions),
                       principals=principals, audit=audit)


def create_app(runtime: AuthRuntime | None = None, configure_from_environment: bool = True) -> FastAPI:
    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    if runtime is None and configure_from_environment:
        try:
            runtime = runtime_from_environment()
        except AuthConfigurationError as error:
            print(f"Authentication disabled (fail closed): {error}", file=sys.stderr)   # messages carry no values
    app.state.auth = runtime

    app.middleware("http")(csrf_middleware)

    @app.middleware("http")
    async def request_identity(request: Request, call_next):
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/health/live")
    def liveness():
        return {"status": "OK"}

    @app.get("/health/ready")
    def readiness():
        # The accepted internal probe has HTTP 200 + categorical status. Protected content/keys, knowledge and the
        # remaining S2 schema are not configured, so the service is still not ready even when sign-in works.
        return {"status": "NOT_READY"}

    install(app)
    return app


app = create_app()
