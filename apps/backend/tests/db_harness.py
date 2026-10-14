"""Shared harness for DISPOSABLE-PostgreSQL API tests (never the persistent development database on port 55432)."""
import json
import os
import time
import unittest
import uuid
from pathlib import Path

import httpx
import psycopg
from fastapi.testclient import TestClient

import test_auth as T
from trustlens_backend import audit, provisioning
from trustlens_backend.admission import Admission, BucketProfile
from trustlens_backend.audit import PostgresAuditSink
from trustlens_backend.auth import AuthRuntime
from trustlens_backend.database import disposable_settings_from_file, install_connect_guard
from trustlens_backend.main import create_app
from trustlens_backend.oidc import OIDCClient
from trustlens_backend.principals import PostgresPrincipalStore
from trustlens_backend.sessions import SessionStore, TransactionStore

ROOT = Path(__file__).resolve().parents[3]
CATALOG = json.loads((ROOT / "contracts/api/api-v1.json").read_text())
DISPOSABLE = os.environ.get("TRUSTLENS_TEST_DISPOSABLE_DB") == "1"
GENEROUS = BucketProfile(capacity=10_000, refill_per_second=10_000)   # functional tests are not admission tests


if DISPOSABLE:
    install_connect_guard()        # every psycopg/SQLAlchemy connection in this process is checked before it opens


def _settings(variable):
    """Disposable settings from the named env file; fails closed (before any connection) on a missing, misnamed,
    malformed or persistent endpoint, or on the sponsor's permanent credential directory."""
    return disposable_settings_from_file(os.environ.get(variable, ""))


class DbHarness:
    evidence_store = None          # set by evidence tests to a temporary LocalEncryptedContentStore
    knowledge_verifier = None      # set by knowledge tests to a KnowledgeVerifier over a temporary bundle store
    knowledge_release_dir = None   # set by knowledge tests to a temporary release-record directory
    deployment_ref = "local-development"

    @classmethod
    def setUpClass(cls):
        cls.app_db = _settings("TRUSTLENS_TEST_APP_DB_ENV_FILE")      # raises, never skips, on an unsafe endpoint
        if cls.app_db.user != "tl_app_runtime":
            raise AssertionError("disposable API tests run only as tl_app_runtime")

    @staticmethod
    def _owner_settings():
        settings = _settings("TRUSTLENS_TEST_MIGRATOR_DB_ENV_FILE")
        if settings.user != "tl_schema_migrator":
            raise AssertionError("owner-level test helpers run only as tl_schema_migrator")
        return settings

    def db(self):
        return psycopg.connect(**self.app_db.connection_parameters(), autocommit=True)

    def provision(self, roles=("USER",)):
        subject = str(uuid.uuid4())
        with psycopg.connect(**self.app_db.connection_parameters()) as c, c.cursor() as cur:
            provisioning.grant_user(cur, T.ISSUER, subject)
            cur.execute("SELECT principal_reference_id::text FROM trustlens.principal_reference WHERE external_subject = %s", (subject,))
            pid = cur.fetchone()[0]
            if "USER" not in roles:
                provisioning.revoke_user(cur, T.ISSUER, subject)
            for role in (r for r in roles if r != "USER"):        # ANALYST, KNOWLEDGE_EDITOR, KNOWLEDGE_APPROVER, ADMINISTRATOR
                cur.execute("SELECT principal_reference_id::text FROM trustlens.principal_reference WHERE external_issuer = %s",
                            (provisioning.PROVISIONER_ISSUER,))
                cur.execute("INSERT INTO trustlens.role_assignment (role_assignment_id, principal_reference_id, role,"
                            " assigned_by_principal_id, assignment_reason_ref, effective_from)"
                            " VALUES (%s, %s, %s, %s, %s, now())",
                            (str(uuid.uuid4()), pid, role, cur.fetchone()[0], f"TEST-{role}"))
        return subject, pid

    def client_for(self, subject, extra_claims=None):
        """A browser signed in as `subject` through the full OIDC callback (fake provider, real stores)."""
        clock, wall = T.Clock(), T.Clock()
        wall.now = time.time()
        provider = T.FakeProvider(wall)
        s = T.settings()
        runtime = AuthRuntime(settings=s, oidc=OIDCClient(s, httpx.Client(transport=httpx.MockTransport(provider.handler)), clock=wall),
                              transactions=TransactionStore(300, 100, clock=clock), sessions=SessionStore(1800, 28800, 100, clock=clock),
                              principals=PostgresPrincipalStore(self.app_db), audit=PostgresAuditSink(self.app_db), database=self.app_db,
                              evidence_store=self.evidence_store, knowledge_verifier=self.knowledge_verifier,
                              deployment_ref=self.deployment_ref, knowledge_release_dir=self.knowledge_release_dir)
        app = create_app(runtime)
        app.state.admission = Admission(GENEROUS, GENEROUS)
        client = TestClient(app, base_url=T.BACKEND)
        client.__enter__()
        self.addCleanup(client.__exit__, None, None, None)
        login = client.get("/auth/login", follow_redirects=False)
        provider.claims_override = {"sub": subject, **(extra_claims or {})}
        code, query = provider.authorize(login.headers["location"])
        r = client.get("/auth/callback", params={"code": code, "state": query["state"][0], "iss": T.ISSUER}, follow_redirects=False)
        self.assertEqual(r.headers["location"], T.APP + "/", "sign-in failed")
        client.headers["Origin"] = T.APP
        client.headers["X-CSRF-Token"] = client.get("/auth/csrf").json()["csrf_token"]
        return client

    def new_key(self):
        return "test-" + uuid.uuid4().hex

    def create_case(self, client, key=None, body=None):
        return client.post("/api/v1/cases", json={} if body is None else body, headers={"Idempotency-Key": key or self.new_key()})

    def create_submission(self, client, case_id, key=None, body=None):
        return client.post(f"/api/v1/cases/{case_id}/submissions", json={"declared_input_type": "SMS"} if body is None else body,
                           headers={"Idempotency-Key": key or self.new_key()})

    def audit_rows(self, case_id):
        with self.db() as c, c.cursor() as cur:
            cur.execute("SELECT event_type, outcome, actor_principal_id::text, target_kind, target_id::text, safe_metadata"
                        " FROM trustlens.audit_event WHERE case_record_id = %s ORDER BY chain_sequence", (case_id,))
            return cur.fetchall()

    def verify_chain(self):
        with psycopg.connect(**self.app_db.connection_parameters()) as c:
            try:
                with c.cursor() as cur:
                    return audit.verify_chain(cur)
            finally:
                c.rollback()

    def assert_schema(self, body, schema):
        fields = {f["name"]: f for f in CATALOG["schemas"][schema]["fields"]}
        self.assertTrue(set(body) <= set(fields), set(body) - set(fields))
        self.assertTrue({n for n, f in fields.items() if f["required"]} <= set(body))

    # ---- contract parity
