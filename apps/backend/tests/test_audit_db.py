"""Audit chain and atomic role-provisioning tests.

AuditUnitTests always run. AuditDatabaseTests run only against a DISPOSABLE PostgreSQL that the bootstrap SQL and both
migrations have been applied to, named by TRUSTLENS_TEST_DISPOSABLE_DB=1 plus TRUSTLENS_TEST_APP_DB_ENV_FILE and
TRUSTLENS_TEST_MIGRATOR_DB_ENV_FILE. They refuse the persistent development port (55432).
"""
import json
import os
import threading
import unittest
import uuid
from unittest.mock import patch

import psycopg

from trustlens_backend import audit, provisioning
from trustlens_backend.audit import AuditEvent, AuditUnavailable, PostgresAuditSink, event_hash, verify_chain, verify_rows
from trustlens_backend.database import disposable_settings_from_file, install_connect_guard

ISSUER = "http://127.0.0.1:8081/realms/test"


def _event(**extra):
    base = dict(event_type="AUTHENTICATION_SUCCEEDED", outcome="SUCCEEDED", actor_kind="HUMAN",
                target_kind="PRINCIPAL", correlation_id=str(uuid.uuid4()), safe_metadata={"method": "OIDC_AUTHORIZATION_CODE_PKCE"})
    base.update(extra)
    return AuditEvent(**base)


class AuditUnitTests(unittest.TestCase):
    def test_hash_covers_every_field_and_the_previous_hash(self):
        row = {"audit_event_id": str(uuid.uuid4()), "chain_id": "deployment", "chain_sequence": 1, "event_schema_version": "1",
               "event_type": "ROLE_ASSIGNED", "occurred_at": "2026-10-13T10:00:00.000000Z", "recorded_at": "2026-10-13T10:00:00.000001Z",
               "actor_principal_id": None, "actor_kind": "WORKLOAD", "outcome": "SUCCEEDED", "target_kind": "ROLE_ASSIGNMENT",
               "target_id": None, "case_record_id": None, "evaluation_id": None, "evidence_item_id": None,
               "bundle_content_digest": None, "correlation_id": str(uuid.uuid4()), "safe_metadata": {"role": "USER"},
               "previous_event_hash": "0" * 64}
        digest = event_hash(row)
        self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertEqual(event_hash(dict(row)), digest)
        for key, value in (("outcome", "FAILED"), ("safe_metadata", {"role": "ANALYST"}), ("previous_event_hash", "1" * 64),
                           ("chain_sequence", 2), ("occurred_at", "2026-10-13T10:00:00.000002Z")):
            self.assertNotEqual(event_hash(dict(row, **{key: value})), digest, key)

    def test_safe_metadata_allowlist_rejects_identity_and_secrets(self):
        for bad in ({"sub": "b235e407-47cf-499e-987b-d696a9e40c15"}, {"reason": "eyJhbGciOiJSUzI1NiJ9.x.y"},
                    {"reason": "lowercase not categorical"}, {"method": "A" * 65}, {"username": "tl-demo-user"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                audit._validate(_event(safe_metadata=bad))
        with self.assertRaises(ValueError):
            audit._validate(_event(actor_principal_id="not-a-uuid"))
        with self.assertRaises(ValueError):
            audit._validate(_event(event_type="CASE_CREATED"))          # not enabled for this slice's schema version
        audit._validate(_event())


def _chain(length):
    rows, previous = [], "0" * 64
    for n in range(1, length + 1):
        row = {"audit_event_id": str(uuid.uuid4()), "chain_id": "deployment", "chain_sequence": n, "event_schema_version": "1",
               "event_type": "AUTHENTICATION_SUCCEEDED", "occurred_at": "2026-10-13T10:00:00.000000Z",
               "recorded_at": "2026-10-13T10:00:00.000000Z", "actor_principal_id": None, "actor_kind": "HUMAN",
               "outcome": "SUCCEEDED", "target_kind": "PRINCIPAL", "target_id": None, "case_record_id": None,
               "evaluation_id": None, "evidence_item_id": None, "bundle_content_digest": None,
               "correlation_id": str(uuid.uuid4()), "safe_metadata": None, "previous_event_hash": previous}
        row["event_hash"] = event_hash(row)
        rows.append(row)
        previous = row["event_hash"]
    return rows, (length, previous)


class VerifySnapshotUnitTests(unittest.TestCase):
    """Round-1 review finding 3: real corruption must still fail when verification sees one consistent snapshot."""

    def test_intact_chain_verifies(self):
        rows, head = _chain(4)
        self.assertEqual(verify_rows(rows, head), 4)
        self.assertEqual(verify_rows([], (0, "0" * 64)), 0)

    def test_tampering_is_detected(self):
        rows, head = _chain(4)
        cases = {
            "edited field": lambda r: r[2].update(outcome="FAILED"),
            "forged hash": lambda r: r[1].update(event_hash="f" * 64),
            "broken link": lambda r: r[3].update(previous_event_hash="e" * 64),
            "sequence gap": lambda r: r.pop(1),
            "reordered": lambda r: r.reverse(),
            "bad genesis": lambda r: r[0].update(previous_event_hash="1" * 64),
        }
        for name, tamper in cases.items():
            with self.subTest(name=name):
                copy_rows = [dict(r) for r in rows]
                tamper(copy_rows)
                with self.assertRaises(ValueError):
                    verify_rows(copy_rows, head)
        with self.assertRaises(ValueError):
            verify_rows(rows, (3, head[1]))                 # head behind the events
        with self.assertRaises(ValueError):
            verify_rows(rows[:3], head)                     # events missing behind the head


def _settings(variable):
    return disposable_settings_from_file(os.environ.get(variable, ""))     # same fail-closed guard as db_harness


@unittest.skipUnless(os.environ.get("TRUSTLENS_TEST_DISPOSABLE_DB") == "1", "needs an explicitly disposable PostgreSQL")
class AuditDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = _settings("TRUSTLENS_TEST_APP_DB_ENV_FILE")
        cls.migrator = _settings("TRUSTLENS_TEST_MIGRATOR_DB_ENV_FILE")
        install_connect_guard()
        assert cls.app.user == "tl_app_runtime" and cls.migrator.user == "tl_schema_migrator"

    def connect(self, settings=None, autocommit=False):
        return psycopg.connect(**(settings or self.app).connection_parameters(), autocommit=autocommit)

    def verify(self):
        with self.connect() as c:
            try:
                with c.cursor() as cur:
                    return verify_chain(cur)
            finally:
                c.rollback()

    def rows(self):
        with self.connect(autocommit=True) as c, c.cursor() as cur:
            return audit.stored_rows(cur)

    def refused(self, sql, settings=None, params=None):
        with self.connect(settings) as c, c.cursor() as cur:
            with self.assertRaises(psycopg.Error):
                cur.execute(sql, params)

    def test_consecutive_appends_form_a_verifiable_chain_from_genesis(self):
        before = self.verify()
        sink = PostgresAuditSink(self.app)
        for _ in range(3):
            sink.record(_event())
        self.assertEqual(self.verify(), before + 3)
        rows = self.rows()
        self.assertEqual(rows[0]["previous_event_hash"], "0" * 64)
        self.assertTrue(all(b["previous_event_hash"] == a["event_hash"] for a, b in zip(rows, rows[1:])))

    def test_append_committed_during_verification_does_not_cause_false_corruption(self):
        before = self.verify()
        sink, original = PostgresAuditSink(self.app), audit.stored_rows

        def rows_then_concurrent_append(cursor, chain_id=audit.CHAIN_ID):
            rows = original(cursor, chain_id)
            sink.record(_event())          # another session appends and COMMITS between the two reads
            return rows
        with patch.object(audit, "stored_rows", side_effect=rows_then_concurrent_append):
            self.assertEqual(self.verify(), before)          # one snapshot: rows and head agree
        self.assertEqual(self.verify(), before + 1)          # a new snapshot sees the committed append

    def test_verification_refuses_autocommit_multi_snapshot_reads(self):
        with self.connect(autocommit=True) as c, c.cursor() as cur:
            with self.assertRaises(RuntimeError):
                verify_chain(cur)

    def test_concurrent_appends_are_serialized_gap_free(self):
        before = self.verify()
        sink, errors = PostgresAuditSink(self.app), []

        def worker():
            try:
                for _ in range(5):
                    sink.record(_event())
            except Exception as error:   # surfaced below
                errors.append(error)
        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(self.verify(), before + 40)
        self.assertEqual([r["chain_sequence"] for r in self.rows()], list(range(1, before + 41)))

    def test_history_is_immutable_for_every_role(self):
        PostgresAuditSink(self.app).record(_event())
        for settings in (self.app, self.migrator):
            self.refused("UPDATE trustlens.audit_event SET outcome = 'FAILED'", settings)
            self.refused("DELETE FROM trustlens.audit_event", settings)
            self.refused("TRUNCATE trustlens.audit_event", settings)
        self.refused("DELETE FROM trustlens.audit_chain_head", self.migrator)
        self.verify()

    def test_unauthorized_or_forged_writes_are_refused(self):
        PostgresAuditSink(self.app).record(_event())
        self.refused("UPDATE trustlens.audit_chain_head SET last_chain_sequence = last_chain_sequence + 5")
        self.refused("UPDATE trustlens.audit_chain_head SET chain_id = 'other'")
        self.refused("INSERT INTO trustlens.audit_chain_head VALUES (gen_random_uuid(), 'rogue', 0, repeat('0', 64), now())")
        forged = (str(uuid.uuid4()), "deployment", 999, "1", "ROLE_ASSIGNED", "WORKLOAD", "SUCCEEDED", "ROLE_ASSIGNMENT",
                  str(uuid.uuid4()), "a" * 64, "b" * 64)
        self.refused("INSERT INTO trustlens.audit_event (audit_event_id, chain_id, chain_sequence, event_schema_version, event_type,"
                     " occurred_at, recorded_at, actor_kind, outcome, target_kind, correlation_id, previous_event_hash, event_hash)"
                     " VALUES (%s, %s, %s, %s, %s, now(), now(), %s, %s, %s, %s, %s, %s)", params=forged)
        self.refused("CREATE TABLE trustlens.shadow_log (x int)")
        self.verify()

    def test_role_grant_and_audit_commit_atomically(self):
        subject = str(uuid.uuid4())
        before = self.verify()
        with patch.object(provisioning, "append", side_effect=AuditUnavailable("synthetic audit failure")):
            with self.assertRaises(AuditUnavailable), self.connect() as c, c.cursor() as cur:
                provisioning.grant_user(cur, ISSUER, subject)
        with self.connect(autocommit=True) as c, c.cursor() as cur:
            cur.execute("SELECT count(*) FROM trustlens.principal_reference WHERE external_subject = %s", (subject,))
            self.assertEqual(cur.fetchone()[0], 0)             # rolled back: no unaudited privilege change
        self.assertEqual(self.verify(), before)

        with self.connect() as c, c.cursor() as cur:
            message = provisioning.grant_user(cur, ISSUER, subject)
        last = self.rows()[-1]
        self.assertIn("USER role granted", message)
        self.assertEqual((last["event_type"], last["actor_kind"], last["outcome"], last["target_kind"]),
                         ("ROLE_ASSIGNED", "WORKLOAD", "SUCCEEDED", "ROLE_ASSIGNMENT"))
        self.assertEqual(last["safe_metadata"]["role"], "USER")
        with self.connect() as c, c.cursor() as cur:
            provisioning.revoke_user(cur, ISSUER, subject)
        last = self.rows()[-1]
        self.assertEqual(last["event_type"], "ROLE_REVOKED")
        self.assertEqual(self.verify(), before + 2)
        dump = json.dumps(self.rows(), default=str)
        for sensitive in (subject, ISSUER, "tl-demo-user"):
            self.assertNotIn(sensitive, dump)


if __name__ == "__main__":
    unittest.main()
