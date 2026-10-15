"""Loopback backend: internal probes, the browser authentication boundary and GET /api/v1/me.

Startup never connects to the database or the identity provider and never creates a schema. Missing or unsafe
authentication configuration disables sign-in (fail closed); it is never replaced by a development bypass. In the served
application only, the S5 evaluation recovery loop starts after startup in a background thread and connects then.
"""
import sys
from uuid import uuid4

import psycopg

from fastapi import FastAPI, Request

from .admission import Admission, admission_middleware
from .audit import AuditUnavailable, PostgresAuditSink
from .auth import AuthRuntime, csrf_middleware, install
from .cases import install as install_cases
from .evaluation import install as install_evaluation, start_recovery
from .history import install as install_history
from .enrichment import install as install_enrichment
from .evidence import get_store, install as install_evidence
from .capabilities import evidence_schema_active
from .knowledge_seam import evaluation_readiness, install as install_knowledge, verifier_from_environment
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
                       principals=principals, audit=audit, database=database,
                       evidence_store_paths=(env.get("TRUSTLENS_EVIDENCE_DIR", "~/.local/share/trustlens/evidence-dev"),
                                             env.get("TRUSTLENS_EVIDENCE_KEK_FILE", "~/.config/trustlens/evidence-kek-v1.key")),
                       knowledge_verifier=verifier_from_environment(env),
                       deployment_ref=env.get("TRUSTLENS_DEPLOYMENT_REF", "local-development"), evaluation_recovery=True)


def create_app(runtime: AuthRuntime | None = None, configure_from_environment: bool = True) -> FastAPI:
    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    if runtime is None and configure_from_environment:
        try:
            runtime = runtime_from_environment()
        except AuthConfigurationError as error:
            print(f"Authentication disabled (fail closed): {error}", file=sys.stderr)   # messages carry no values
    app.state.auth = runtime
    app.state.admission = Admission()

    app.middleware("http")(csrf_middleware)
    app.middleware("http")(admission_middleware)        # outside CSRF: refuse floods before any further work

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
        # Accepted internal probe: HTTP 200 + categorical status only (ARCH-005 §8). OK requires the required
        # persistence (S2 schema), the protected evidence store and a verified, eligible, active knowledge bundle.
        # Every failure is NOT_READY; reasons are never exposed here.
        return {"status": "OK" if probe_ready(app.state.auth) else "NOT_READY"}

    install(app)
    install_cases(app)
    install_evidence(app)
    install_knowledge(app)
    install_evaluation(app)
    install_history(app)
    install_enrichment(app)

    @app.on_event("startup")
    def recover_evaluations():
        # S5 durability: fence expired executions and resume undispatched ones after a restart (served app only).
        if runtime is not None and runtime.evaluation_recovery and runtime.database is not None:
            app.state.evaluation_recovery = start_recovery(runtime)
    return app


def probe_ready(runtime) -> bool:
    if runtime is None or runtime.database is None:
        return False
    try:
        with psycopg.connect(**runtime.database.connection_parameters(), autocommit=True) as connection:
            connection.execute("SET statement_timeout = '5s'")
            with connection.cursor() as cur:
                if not evidence_schema_active(connection) or get_store(runtime) is None:
                    return False
                return evaluation_readiness(cur, runtime.knowledge_verifier, runtime.deployment_ref).ready
    except (psycopg.Error, OSError, DatabaseConfigurationError):
        return False


app = create_app()
