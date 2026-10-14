"""Case and submission API against a DISPOSABLE PostgreSQL (migrations 0001-0003 applied). Synthetic data only.

Runs only with TRUSTLENS_TEST_DISPOSABLE_DB=1 plus TRUSTLENS_TEST_APP_DB_ENV_FILE / TRUSTLENS_TEST_MIGRATOR_DB_ENV_FILE;
refuses the persistent development port 55432. Sign-in uses the fake OIDC provider from test_auth (real RSA-signed ID
tokens); principals, roles, grants, cases, submissions, idempotency and audit are the real PostgreSQL implementation.
"""
import importlib.util
import json
import unittest
import uuid

import psycopg
from fastapi.testclient import TestClient

import test_auth as T
from db_harness import CATALOG, DISPOSABLE, ROOT, DbHarness, _settings
from trustlens_backend import cases, idempotency
from trustlens_backend.main import create_app


@unittest.skipUnless(DISPOSABLE, "needs an explicitly disposable PostgreSQL")
class CaseApiTests(DbHarness, unittest.TestCase):
    def test_operations_match_the_catalog(self):
        ops = {o["operation_id"]: o for o in CATALOG["operations"]}
        for op_id, spec in cases.OPERATIONS.items():
            o = ops[op_id]
            self.assertEqual((spec["method"], spec["path"], list(spec["roles"]), spec["resource_authorization"]),
                             (o["method"], o["path"], o["roles"], o["resource_authorization"]), op_id)

    def test_live_schema_matches_the_contract_plus_candidate_addendum(self):
        """Every migrated table equals the effective contract 0.3.0, composed exactly as the snapshot-revision validator
        composes it (schema-v1.json 0.2.0 + candidate addendum P9-S2-ADD-001)."""
        spec = importlib.util.spec_from_file_location("psr", ROOT / "knowledge/validation/validate_phase6_snapshot_revision.py")
        psr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(psr)
        effective = psr.compose(json.loads((ROOT / "contracts/postgresql/schema-v1.json").read_text()),
                                json.loads((ROOT / "contracts/postgresql/schema-v1-addendum-p9-s2-add-001.json").read_text()))
        self.assertEqual(effective["contract_version"], "0.3.0")
        contract = {t["name"]: t for t in effective["tables"]}
        types = {"uuid": "uuid", "text": "text", "timestamptz": "timestamp with time zone", "bigint": "bigint",
                 "integer": "integer", "boolean": "boolean", "jsonb": "jsonb", "text[]": "ARRAY"}
        owner = _settings("TRUSTLENS_TEST_MIGRATOR_DB_ENV_FILE")   # information_schema hides columns the app role cannot read
        with psycopg.connect(**owner.connection_parameters(), autocommit=True) as c, c.cursor() as cur:
            cur.execute("SELECT table_name, column_name, data_type, is_nullable FROM information_schema.columns"
                        " WHERE table_schema = 'trustlens' AND table_name <> 'alembic_version' ORDER BY table_name, ordinal_position")
            live = {}
            for table, column, data_type, nullable in cur.fetchall():
                live.setdefault(table, []).append((column, data_type, nullable == "YES"))
            cur.execute("SELECT indexdef FROM pg_indexes WHERE schemaname = 'trustlens' AND indexname = 'uq_api_idempotency_scope'")
            self.assertIn("WHERE (superseded_at IS NULL)", cur.fetchone()[0])
        self.assertIn("evidence_upload_intent", live)
        self.assertIn("detection_result", live)                    # 0006 (S5) tables are checked against the contract too
        for table, columns in live.items():
            expected = [(col["name"], types[col["type"]], col["nullable"]) for col in contract[table]["columns"]]
            self.assertEqual(columns, expected, table)

    def test_submission_relationship_to_content_is_persisted_on_the_submission(self):
        subject, _ = self.provision()
        client = self.client_for(subject)
        case_id = self.create_case(client).json()["case_id"]
        sub = self.create_submission(client, case_id, body={"declared_input_type": "SMS", "relationship_to_content": "FORWARDED"}).json()
        plain = self.create_submission(client, case_id, body={"declared_input_type": "CHAT_MESSAGE"}).json()
        with self.db() as c, c.cursor() as cur:
            cur.execute("SELECT submission_id::text, relationship_to_content FROM trustlens.submission WHERE case_record_id = %s", (case_id,))
            stored = dict(cur.fetchall())
        self.assertEqual(stored, {sub["submission_id"]: "FORWARDED", plain["submission_id"]: None})
        self.assertEqual(sub["relationship_to_content"], "FORWARDED")
        self.assertNotIn("relationship_to_content", plain)        # optional field omitted, never invented
        with self.db() as c, c.cursor() as cur:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'trustlens' AND table_name = 'case_record'")
            self.assertNotIn("relationship_to_content", [r[0] for r in cur.fetchall()])

    # ---- createCase
    def test_create_case_assigns_server_owner_grant_and_audits_atomically(self):
        subject, pid = self.provision()
        client = self.client_for(subject)
        r = self.create_case(client, body={"relationship_to_content": "RECEIVED"})
        self.assertEqual(r.status_code, 201, r.text)
        body = r.json()
        self.assert_schema(body, "CaseResponse")
        self.assertEqual((body["state"], body["is_synthetic"], body["viewer_access"]),
                         ("OPEN", True, {"relationship": "OWNER", "can_view_evidence_content": True}))
        self.assertEqual(r.headers["etag"], body["etag"])
        self.assertEqual(r.headers["location"], f"/api/v1/cases/{body['case_id']}")
        with self.db() as c, c.cursor() as cur:
            cur.execute("SELECT owner_principal_id::text, mutation_revision FROM trustlens.case_record WHERE case_record_id = %s", (body["case_id"],))
            self.assertEqual(cur.fetchone(), (pid, 1))
            cur.execute("SELECT grant_kind, principal_reference_id::text, permits_evidence_content FROM trustlens.case_access_grant"
                        " WHERE case_record_id = %s", (body["case_id"],))
            self.assertEqual(cur.fetchall(), [("OWNER", pid, True)])
        events = self.audit_rows(body["case_id"])
        self.assertEqual([(e[0], e[1], e[2], e[3], e[4]) for e in events], [("CASE_CREATED", "SUCCEEDED", pid, "CASE", body["case_id"])])
        self.verify_chain()

    def test_owner_cannot_be_supplied_by_the_client(self):
        subject, _ = self.provision()
        client = self.client_for(subject)
        r = self.create_case(client, body={"owner_principal_id": str(uuid.uuid4())})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"]["field_errors"][0], {"field": "owner_principal_id", "code": "UNKNOWN_FIELD",
                                                               "message": "Field is not accepted."})

    def test_idempotent_create_case(self):
        subject, pid = self.provision()
        client = self.client_for(subject)
        key = self.new_key()
        first = self.create_case(client, key=key)
        again = self.create_case(client, key=key)
        self.assertEqual((first.status_code, again.status_code), (201, 201))
        self.assertEqual(first.json()["case_id"], again.json()["case_id"])
        self.assertEqual(len(self.audit_rows(first.json()["case_id"])), 1)        # executed exactly once
        reused = self.create_case(client, key=key, body={"relationship_to_content": "SENT"})
        self.assertEqual((reused.status_code, reused.json()["error"]["code"]), (409, "IDEMPOTENCY_KEY_REUSED"))
        missing = client.post("/api/v1/cases", json={})
        self.assertEqual((missing.status_code, missing.json()["error"]["field_errors"][0]["field"]), (400, "Idempotency-Key"))
        with self.db() as c, c.cursor() as cur:
            cur.execute("SELECT count(*) FROM trustlens.case_record WHERE owner_principal_id = %s", (pid,))
            self.assertEqual(cur.fetchone()[0], 1)
            cur.execute("SELECT count(*) FROM trustlens.api_idempotency_record WHERE idempotency_key_digest = %s", (key,))
            self.assertEqual(cur.fetchone()[0], 0)                                # raw key never stored

    def test_idempotency_in_progress_and_independent_principal_scopes(self):
        subject, pid = self.provision()
        client = self.client_for(subject)
        key = self.new_key()
        with self.db() as c:                     # another executor holds a live claim for the same request
            idempotency.claim(c, pid, "createCase", "/api/v1/cases", key, idempotency.semantic_digest("createCase", "/api/v1/cases", {}))
        r = self.create_case(client, key=key)
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (409, "IDEMPOTENCY_IN_PROGRESS"))
        other_subject, _ = self.provision()
        self.assertEqual(self.create_case(self.client_for(other_subject), key=key).status_code, 201)   # separate scope

    # ---- isolation and roles
    def test_cross_user_isolation_is_masked_and_denials_are_audited(self):
        owner_subject, _ = self.provision()
        owner = self.client_for(owner_subject)
        case_id = self.create_case(owner).json()["case_id"]
        intruder_subject, intruder_pid = self.provision()
        intruder = self.client_for(intruder_subject)
        self.assertEqual(intruder.get(f"/api/v1/cases/{case_id}").status_code, 404)
        self.assertEqual(intruder.get(f"/api/v1/cases/{case_id}/submissions").status_code, 404)
        r = self.create_submission(intruder, case_id)
        self.assertEqual(r.status_code, 404)
        self.assertNotIn(case_id, [c["case_id"] for c in intruder.get("/api/v1/cases").json()["items"]])
        denial = self.audit_rows(case_id)[-1]
        self.assertEqual((denial[0], denial[1], denial[2], denial[5]["reason"]),
                         ("AUTHORIZATION_DENIED", "DENIED", intruder_pid, "NO_CASE_ACCESS"))
        self.assertEqual(intruder.get(f"/api/v1/cases/{uuid.uuid4()}").status_code, 404)  # same answer as non-existent

    def test_assigned_analyst_sees_metadata_but_cannot_submit_or_read_content(self):
        owner_subject, owner_pid = self.provision()
        owner = self.client_for(owner_subject)
        case_id = self.create_case(owner).json()["case_id"]
        analyst_subject, analyst_pid = self.provision(roles=("ANALYST",))
        with self.db() as c, c.cursor() as cur:
            cur.execute("INSERT INTO trustlens.case_access_grant (case_access_grant_id, case_record_id, principal_reference_id,"
                        " grant_kind, permits_case_metadata, permits_evidence_content, granted_by_principal_id, grant_reason_ref,"
                        " effective_from) VALUES (%s, %s, %s, 'ASSIGNED_ANALYST', true, false, %s, 'TEST-ASSIGNMENT', now())",
                        (str(uuid.uuid4()), case_id, analyst_pid, owner_pid))
        analyst = self.client_for(analyst_subject)
        view = analyst.get(f"/api/v1/cases/{case_id}").json()
        self.assertEqual(view["viewer_access"], {"relationship": "ASSIGNED_ANALYST", "can_view_evidence_content": False})
        r = self.create_submission(analyst, case_id)
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (403, "FORBIDDEN"))
        self.assertEqual(self.audit_rows(case_id)[-1][5]["reason"], "ROLE_OR_OWNERSHIP_REQUIRED")
        self.assertEqual(self.create_case(analyst).status_code, 403)              # ANALYST cannot create cases

    def test_grant_rules_are_enforced_by_the_database(self):
        owner_subject, owner_pid = self.provision()
        case_id = self.create_case(self.client_for(owner_subject)).json()["case_id"]
        _, user_pid = self.provision()
        for kind in ("OWNER", "ASSIGNED_ANALYST"):           # non-owner OWNER grant; non-analyst ASSIGNED_ANALYST grant
            with self.db() as c, c.cursor() as cur, self.assertRaises(psycopg.Error):
                cur.execute("INSERT INTO trustlens.case_access_grant (case_access_grant_id, case_record_id, principal_reference_id,"
                            " grant_kind, permits_case_metadata, permits_evidence_content, granted_by_principal_id, grant_reason_ref,"
                            " effective_from) VALUES (%s, %s, %s, %s, true, false, %s, 'TEST', now())",
                            (str(uuid.uuid4()), case_id, user_pid, kind, owner_pid))
        with self.db() as c, c.cursor() as cur:
            for sql in ("UPDATE trustlens.case_record SET owner_principal_id = %s WHERE case_record_id = %s",
                        "DELETE FROM trustlens.case_record WHERE case_record_id = %s AND %s IS NOT NULL",
                        "DELETE FROM trustlens.case_access_grant WHERE case_record_id = %s AND %s IS NOT NULL"):
                with self.assertRaises(psycopg.Error):
                    cur.execute(sql, (user_pid, case_id) if "owner_principal_id" in sql else (case_id, case_id))
            cur.execute("UPDATE trustlens.case_record SET mutation_revision = 99 WHERE case_record_id = %s RETURNING mutation_revision", (case_id,))
            self.assertEqual(cur.fetchone()[0], 2)           # server-advanced by exactly one; supplied value ignored

    # ---- submissions
    def test_create_get_and_list_submissions(self):
        subject, _ = self.provision()
        client = self.client_for(subject)
        case_id = self.create_case(client).json()["case_id"]
        key = self.new_key()
        r = self.create_submission(client, case_id, key=key, body={"declared_input_type": "SMS", "relationship_to_content": "RECEIVED"})
        self.assertEqual(r.status_code, 201, r.text)
        sub = r.json()
        self.assert_schema(sub, "SubmissionResponse")
        self.assertEqual((sub["case_id"], sub["declared_input_type"], sub["state"], sub["is_synthetic"]), (case_id, "SMS", "RECEIVING", True))
        self.assertEqual(self.create_submission(client, case_id, key=key, body={"declared_input_type": "SMS", "relationship_to_content": "RECEIVED"}).json()["submission_id"],
                         sub["submission_id"])
        self.assertEqual(client.get(f"/api/v1/submissions/{sub['submission_id']}").json(), sub)
        listed = client.get(f"/api/v1/cases/{case_id}/submissions").json()
        self.assertEqual([s["submission_id"] for s in listed["items"]], [sub["submission_id"]])
        self.assert_schema(listed, "SubmissionListResponse")

    def test_submission_metadata_is_strict_and_never_carries_message_text(self):
        subject, _ = self.provision()
        client = self.client_for(subject)
        case_id = self.create_case(client).json()["case_id"]
        secret_text = "Your parcel is held, pay 2 GBP at http://example.invalid/synthetic"
        for body in ({"declared_input_type": "SMS", "message": secret_text}, {"declared_input_type": "NOT_A_TYPE"}, {}):
            r = self.create_submission(client, case_id, body=body)
            self.assertEqual(r.status_code, 400)
            self.assertNotIn(secret_text, r.text)
            self.assertNotIn("NOT_A_TYPE", r.text)
        r = client.post(f"/api/v1/cases/{case_id}/submissions", content=b"declared_input_type=SMS",
                        headers={"Idempotency-Key": self.new_key(), "Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(r.status_code, 400)
        big = client.post(f"/api/v1/cases/{case_id}/submissions", content=b"{" + b" " * (128 * 1024) + b"}",
                          headers={"Idempotency-Key": self.new_key(), "Content-Type": "application/json"})
        self.assertEqual(big.status_code, 400)

    def test_closed_case_refuses_submissions_and_replays_the_refusal(self):
        subject, _ = self.provision()
        client = self.client_for(subject)
        case_id = self.create_case(client).json()["case_id"]
        with self.db() as c, c.cursor() as cur:
            cur.execute("UPDATE trustlens.case_record SET lifecycle_state = 'CLOSED', closed_at = now() WHERE case_record_id = %s", (case_id,))
        key = self.new_key()
        for _ in range(2):
            r = self.create_submission(client, case_id, key=key)
            self.assertEqual((r.status_code, r.json()["error"]["code"]), (409, "STATE_CONFLICT"))

    def test_csrf_and_origin_still_protect_api_writes(self):
        subject, _ = self.provision()
        client = self.client_for(subject)
        token = client.headers.pop("X-CSRF-Token")
        self.assertEqual(self.create_case(client).status_code, 403)
        client.headers["X-CSRF-Token"] = token
        client.headers["Origin"] = "http://127.0.0.1:6666"
        self.assertEqual(self.create_case(client).status_code, 403)

    def test_unauthenticated_requests_are_refused(self):
        with TestClient(create_app(None, configure_from_environment=False), base_url=T.BACKEND) as anonymous:
            self.assertEqual(anonymous.get("/api/v1/cases").status_code, 503)    # unconfigured runtime fails closed
        subject, _ = self.provision()
        client = self.client_for(subject)
        client.cookies.clear()
        self.assertEqual(client.get("/api/v1/cases").status_code, 401)

    # ---- pagination and persistence
    def test_cursor_pagination_and_parameter_validation(self):
        subject, _ = self.provision()
        client = self.client_for(subject)
        ids = [self.create_case(client).json()["case_id"] for _ in range(3)]
        first = client.get("/api/v1/cases", params={"limit": 2}).json()
        self.assertEqual(len(first["items"]), 2)
        second = client.get("/api/v1/cases", params={"limit": 2, "cursor": first["page"]["next_cursor"]}).json()
        seen = [c["case_id"] for c in first["items"] + second["items"]]
        self.assertEqual(sorted(seen), sorted(ids))
        self.assertNotIn("next_cursor", second["page"])
        for params in ({"limit": 0}, {"limit": 101}, {"cursor": "not-a-cursor"}, {"state": "MAYBE"}, {"unknown": "x"},
                       {"created_from": "yesterday"}):
            self.assertEqual(client.get("/api/v1/cases", params=params).status_code, 400, params)
        self.assertEqual(client.get("/api/v1/cases", params={"relationship": "ASSIGNED_ANALYST"}).json()["items"], [])

    def test_records_persist_for_a_new_backend_instance_and_session(self):
        subject, _ = self.provision()
        case_id = self.create_case(self.client_for(subject)).json()["case_id"]
        fresh = self.client_for(subject)          # new app, new in-memory session store: only PostgreSQL carries over
        self.assertEqual(fresh.get(f"/api/v1/cases/{case_id}").status_code, 200)
        self.verify_chain()


if __name__ == "__main__":
    unittest.main()
