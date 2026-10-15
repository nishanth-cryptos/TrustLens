"""Evidence intake (candidate addendum P9-S2-ADD-001, migration 0004) and idempotency expiry against a DISPOSABLE
PostgreSQL and a temporary encrypted content store. Synthetic data only."""
import hashlib
import os
import tempfile
import threading
import time
import unittest
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import psycopg

from db_harness import CATALOG, DISPOSABLE, DbHarness
from trustlens_backend import evidence, idempotency
from trustlens_backend.content_store import ContentStoreUnavailable, LocalEncryptedContentStore

SMS = "SYNTHETIC TEST: Your parcel is held. Pay 1.99 GBP at http://example.invalid/pay é中\n".encode("utf-8")
TEXT = "text/plain; charset=utf-8"


@unittest.skipUnless(DISPOSABLE, "needs an explicitly disposable PostgreSQL")
class EvidenceApiTests(DbHarness, unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root, kek = Path(tmp.name) / "evidence", Path(tmp.name) / "kek.key"
        root.mkdir(mode=0o700)
        kek.write_bytes(os.urandom(32))
        kek.chmod(0o600)
        self.store_paths = (root, kek)
        self.evidence_store = LocalEncryptedContentStore(root, kek)

    # ---- helpers
    def owner_with_submission(self):
        subject, pid = self.provision()
        client = self.client_for(subject)
        case_id = self.create_case(client).json()["case_id"]
        submission_id = self.create_submission(client, case_id).json()["submission_id"]
        return client, case_id, submission_id, pid

    def initiate(self, client, submission_id, data=SMS, key=None, **overrides):
        body = {"artifact_kind": "TEXT_BODY", "declared_media_type": TEXT, "declared_byte_length": len(data), **overrides}
        return client.post(f"/api/v1/submissions/{submission_id}/evidence", json={k: v for k, v in body.items() if v is not None},
                           headers={"Idempotency-Key": key or self.new_key()})

    def put(self, client, evidence_id, data=SMS, media=TEXT):
        return client.put(f"/api/v1/evidence/{evidence_id}/content", content=data, headers={"Content-Type": media})

    def finalize(self, client, evidence_id, key=None):
        return client.post(f"/api/v1/evidence/{evidence_id}/finalize", json={}, headers={"Idempotency-Key": key or self.new_key()})

    def full_upload(self, client, submission_id, data=SMS):
        evidence_id = self.initiate(client, submission_id, data).json()["evidence_id"]
        self.assertEqual(self.put(client, evidence_id, data).status_code, 200)
        self.assertEqual(self.finalize(client, evidence_id).status_code, 202)
        return evidence_id

    def item(self, evidence_id):
        with self.db() as c, c.cursor() as cur:
            cur.execute("SELECT e.content_state, e.ecs_locator, i.intent_state, i.last_rejection_category, o.state, o.attempt_count"
                        " FROM trustlens.evidence_upload_intent i LEFT JOIN trustlens.evidence_item e ON e.evidence_item_id = i.evidence_upload_intent_id"
                        " LEFT JOIN trustlens.cross_store_operation o ON o.idempotency_key = i.idempotency_key"
                        " WHERE i.evidence_upload_intent_id = %s", (evidence_id,))
            return cur.fetchone()

    # ---- contract parity
    def test_operations_match_the_catalog(self):
        ops = {o["operation_id"]: o for o in CATALOG["operations"]}
        for op_id, spec in evidence.OPERATIONS.items():
            o = ops[op_id]
            self.assertEqual((spec["method"], spec["path"], list(spec["roles"]), spec["resource_authorization"]),
                             (o["method"], o["path"], o["roles"], o["resource_authorization"]), op_id)
        mapping = next(v for k, v in CATALOG["vocabularies"].items() if k == "api_upload_state")["maps_from"]["mapping"]
        self.assertEqual(evidence.UPLOAD_STATE, mapping)

    # ---- the full journey
    def test_three_step_upload_preserves_exact_bytes_encrypted_and_audited(self):
        client, case_id, submission_id, pid = self.owner_with_submission()
        r = self.initiate(client, submission_id, display_filename="screenshot of sms.txt")
        self.assertEqual(r.status_code, 201, r.text)
        view = r.json()
        self.assert_schema(view, "EvidenceMetadataResponse")
        self.assertEqual((view["upload_state"], view["content_sha256"], view["byte_length"], view["display_filename"]),
                         ("AWAITING_CONTENT", None, None, "screenshot of sms.txt"))
        evidence_id = view["evidence_id"]
        r = self.put(client, evidence_id)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json()["upload_state"], r.json()["content_sha256"], r.json()["byte_length"]),
                         ("PROCESSING", hashlib.sha256(SMS).hexdigest(), len(SMS)))
        r = self.finalize(client, evidence_id)
        self.assertEqual(r.status_code, 202, r.text)
        final = r.json()
        self.assertEqual((final["upload_state"], final["verified_media_type"]), ("FINALIZED", TEXT))
        self.assertIsNotNone(final["finalized_at"])
        self.assertNotIn("ecs_locator", final)
        self.assertEqual(final["content_link"], f"/api/v1/evidence/{evidence_id}/content")   # S6 getEvidenceContent
        self.assertEqual(client.get(f"/api/v1/evidence/{evidence_id}").json(), final)
        listed = client.get(f"/api/v1/submissions/{submission_id}/evidence").json()
        self.assertEqual([e["evidence_id"] for e in listed["items"]], [evidence_id])
        state, locator, intent_state, _, op_state, attempts = self.item(evidence_id)
        self.assertEqual((state, intent_state, op_state, attempts), ("FINALIZED", "MATERIALIZED", "FINALIZED", 1))
        raw = (self.store_paths[0] / f"{locator}.tle").read_bytes()
        self.assertNotIn(b"parcel", raw)                                   # encrypted at rest
        self.assertEqual(self.evidence_store.get(locator), SMS)             # exact original bytes
        events = [(e[0], (e[5] or {}).get("stage")) for e in self.audit_rows(case_id)]
        self.assertEqual(events, [("CASE_CREATED", None), ("EVIDENCE_RECEIVED", None), ("EVIDENCE_STORED", "CONTENT_STORED"),
                                  ("EVIDENCE_STORED", "FINALIZED")])
        self.verify_chain()

    def test_records_and_encrypted_content_survive_a_restart(self):
        client, _, submission_id, pid = self.owner_with_submission()
        evidence_id = self.full_upload(client, submission_id)
        subject = self.subject_of(pid)
        self.evidence_store = LocalEncryptedContentStore(*self.store_paths)   # a fresh process: new store instance, same key
        fresh = self.client_for(subject)
        self.assertEqual(fresh.get(f"/api/v1/evidence/{evidence_id}").json()["upload_state"], "FINALIZED")
        self.assertEqual(self.evidence_store.get(self.item(evidence_id)[1]), SMS)

    def subject_of(self, pid):
        with self.db() as c, c.cursor() as cur:
            cur.execute("SELECT external_subject FROM trustlens.principal_reference WHERE principal_reference_id = %s", (pid,))
            return cur.fetchone()[0]

    # ---- declared values, digest and media
    def test_client_digest_is_optional_and_advisory(self):
        client, _, submission_id, _ = self.owner_with_submission()
        good = self.initiate(client, submission_id, client_declared_sha256=hashlib.sha256(SMS).hexdigest()).json()["evidence_id"]
        self.assertEqual(self.put(client, good).status_code, 200)
        wrong = self.initiate(client, submission_id, client_declared_sha256="0" * 64).json()["evidence_id"]
        r = self.put(client, wrong)
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (400, "INVALID_REQUEST"))
        self.assertEqual(self.item(wrong)[2:4], ("OPEN", "DIGEST_MISMATCH"))
        self.assertIsNone(self.item(wrong)[0])                             # no evidence_item, no invented digest

    def test_declared_length_is_enforced_and_retry_with_exact_bytes_succeeds(self):
        client, _, submission_id, _ = self.owner_with_submission()
        evidence_id = self.initiate(client, submission_id).json()["evidence_id"]
        r = self.put(client, evidence_id, SMS + b"!")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.item(evidence_id)[2:4], ("OPEN", "LENGTH_MISMATCH"))
        self.assertEqual(self.put(client, evidence_id).status_code, 200)
        self.assertEqual(self.item(evidence_id)[2:4], ("MATERIALIZED", None))

    def test_identical_re_put_is_a_no_op_and_different_bytes_conflict(self):
        client, case_id, submission_id, _ = self.owner_with_submission()
        evidence_id = self.initiate(client, submission_id).json()["evidence_id"]
        first = self.put(client, evidence_id)
        again = self.put(client, evidence_id)
        self.assertEqual((again.status_code, again.json()), (200, first.json()))
        different = SMS.replace(b"1.99", b"9.99")
        r = self.put(client, evidence_id, different)
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (409, "STATE_CONFLICT"))
        stored = [e for e in self.audit_rows(case_id) if e[0] == "EVIDENCE_STORED"]
        self.assertEqual(len(stored), 1)

    def test_unsupported_media_and_oversized_content_are_refused(self):
        client, _, submission_id, _ = self.owner_with_submission()
        self.assertEqual(self.initiate(client, submission_id, declared_media_type="text/html").status_code, 415)
        self.assertEqual(self.initiate(client, submission_id, artifact_kind="IMAGE", declared_media_type="image/png").status_code, 415)
        self.assertEqual(self.initiate(client, submission_id, declared_byte_length=64 * 1024 + 1).status_code, 413)
        self.assertEqual(self.initiate(client, submission_id, declared_byte_length=0).status_code, 400)
        self.assertEqual(self.initiate(client, submission_id, owner="someone-else").status_code, 400)
        evidence_id = self.initiate(client, submission_id).json()["evidence_id"]
        self.assertEqual(self.put(client, evidence_id, media="text/html").status_code, 415)
        self.assertEqual(self.put(client, evidence_id, b"\xff\xfe not utf-8" + b" " * (len(SMS) - 12)).status_code, 415)
        self.assertEqual(self.item(evidence_id)[3], "MEDIA_INVALID")
        big = self.initiate(client, submission_id, data=b"x" * 1000).json()["evidence_id"]
        self.assertEqual(self.put(client, big, b"x" * (64 * 1024 + 10)).status_code, 413)
        self.assertEqual(self.item(big)[3], "SIZE_EXCEEDED")

    def test_streamed_oversize_bodies_are_bounded_on_the_real_routes(self):
        client, case_id, submission_id, _ = self.owner_with_submission()

        def chunked(size, chunk=16 * 1024):
            def stream():
                sent = 0
                while sent < size:
                    piece = min(chunk, size - sent)
                    sent += piece
                    yield b" " * piece
            return stream()
        big = client.post(f"/api/v1/submissions/{submission_id}/evidence", content=chunked(128 * 1024 + 1),
                          headers={"Content-Type": "application/json", "Idempotency-Key": self.new_key()})
        self.assertEqual((big.status_code, big.json()["error"]["code"]), (413, "PAYLOAD_TOO_LARGE"))   # accepted for this op
        case = client.post("/api/v1/cases", content=chunked(128 * 1024 + 1),
                           headers={"Content-Type": "application/json", "Idempotency-Key": self.new_key()})
        self.assertEqual((case.status_code, case.json()["error"]["code"]), (400, "INVALID_REQUEST"))   # createCase: no 413 in contract
        self.assertEqual(case.json()["error"]["field_errors"][0]["code"], "TOO_LARGE")
        evidence_id = self.initiate(client, submission_id).json()["evidence_id"]
        put = client.put(f"/api/v1/evidence/{evidence_id}/content", content=chunked(64 * 1024 + 1), headers={"Content-Type": TEXT})
        self.assertEqual(put.status_code, 413)
        self.assertEqual(self.item(evidence_id)[3], "SIZE_EXCEEDED")
        with self.db() as c, c.cursor() as cur:
            cur.execute("SELECT count(*) FROM trustlens.case_record WHERE case_record_id <> %s AND owner_principal_id ="
                        " (SELECT owner_principal_id FROM trustlens.case_record WHERE case_record_id = %s)", (case_id, case_id))
            self.assertEqual(cur.fetchone()[0], 0)                                   # the oversized create did nothing

    def test_message_text_never_travels_in_submission_json(self):
        client, case_id, _, _ = self.owner_with_submission()
        r = self.create_submission(client, case_id, body={"declared_input_type": "SMS", "text": SMS.decode()})
        self.assertEqual(r.status_code, 400)
        self.assertNotIn("parcel", r.text)

    # ---- ordering, finalization and failures
    def test_finalize_requires_stored_bytes_and_is_idempotent(self):
        client, _, submission_id, _ = self.owner_with_submission()
        evidence_id = self.initiate(client, submission_id).json()["evidence_id"]
        key = self.new_key()
        early = self.finalize(client, evidence_id, key=key)
        self.assertEqual((early.status_code, early.json()["error"]["code"]), (409, "STATE_CONFLICT"))
        self.assertEqual(self.finalize(client, evidence_id, key=key).status_code, 409)       # replayed refusal
        self.put(client, evidence_id)
        done = self.finalize(client, evidence_id)
        self.assertEqual(done.status_code, 202)
        again = self.finalize(client, evidence_id)
        self.assertEqual((again.status_code, again.json()["upload_state"]), (202, "FINALIZED"))

    def test_corrupted_ciphertext_is_never_finalized(self):
        client, case_id, submission_id, _ = self.owner_with_submission()
        evidence_id = self.initiate(client, submission_id).json()["evidence_id"]
        self.put(client, evidence_id)
        path = self.store_paths[0] / f"{self.item(evidence_id)[1]}.tle"
        path.write_bytes(path.read_bytes().replace(b'"ct":"', b'"ct":"AAAA', 1))
        r = self.finalize(client, evidence_id)
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (500, "INTEGRITY_FAILURE"))
        view = client.get(f"/api/v1/evidence/{evidence_id}").json()
        self.assertEqual((view["upload_state"], view["finalized_at"]), ("REJECTED", None))
        self.assertEqual(self.audit_rows(case_id)[-1][0:2], ("INTEGRITY_FAILURE", "FAILED"))
        self.verify_chain()

    def test_interrupted_content_write_is_retried_then_bounded(self):
        client, _, submission_id, _ = self.owner_with_submission()
        evidence_id = self.initiate(client, submission_id).json()["evidence_id"]
        with patch.object(LocalEncryptedContentStore, "put", side_effect=ContentStoreUnavailable("synthetic outage")):
            r = self.put(client, evidence_id)
        self.assertEqual((r.status_code, r.headers["retry-after"]), (503, "1"))
        self.assertEqual(self.item(evidence_id)[0], "FAILED_RETRYABLE")
        self.assertEqual(client.get(f"/api/v1/evidence/{evidence_id}").json()["upload_state"], "PROCESSING")
        self.assertEqual(self.put(client, evidence_id).status_code, 503)            # backoff not yet elapsed
        time.sleep(1.2)
        self.assertEqual(self.put(client, evidence_id).status_code, 200)           # identical retry resumes the write
        self.assertEqual(self.finalize(client, evidence_id).status_code, 202)

        evidence_id = self.initiate(client, submission_id).json()["evidence_id"]
        with patch.object(LocalEncryptedContentStore, "put", side_effect=ContentStoreUnavailable("synthetic outage")):
            for attempt in range(evidence.MAX_WRITE_ATTEMPTS):
                self.assertEqual(self.put(client, evidence_id).status_code, 503)
                time.sleep(evidence.backoff_seconds(attempt + 1) + 0.2)
        self.assertEqual(self.item(evidence_id)[0], "FAILED_TERMINAL")
        self.assertEqual(client.get(f"/api/v1/evidence/{evidence_id}").json()["upload_state"], "REJECTED")
        self.assertEqual(self.finalize(client, evidence_id).status_code, 409)

    def test_metadata_failure_after_content_write_never_reports_stored(self):
        client, _, submission_id, _ = self.owner_with_submission()
        evidence_id = self.initiate(client, submission_id).json()["evidence_id"]
        original = evidence._audit_evidence

        def fail_once(cur, request, principal, case_id, eid, event_type, stage=None, outcome="SUCCEEDED"):
            if stage == "CONTENT_STORED":
                raise psycopg.OperationalError("synthetic commit failure")
            return original(cur, request, principal, case_id, eid, event_type, stage, outcome)
        with patch.object(evidence, "_audit_evidence", side_effect=fail_once):
            r = self.put(client, evidence_id)
        self.assertEqual(r.status_code, 503)
        self.assertEqual(self.item(evidence_id)[0:2], ("CONTENT_PENDING", None))     # not stored, not finalized
        self.assertEqual(self.finalize(client, evidence_id).status_code, 409)
        self.assertEqual(self.put(client, evidence_id).status_code, 200)           # identical re-PUT completes it
        self.assertEqual(self.finalize(client, evidence_id).status_code, 202)

    def test_missing_key_fails_closed(self):
        client, _, submission_id, _ = self.owner_with_submission()
        evidence_id = self.initiate(client, submission_id).json()["evidence_id"]
        self.evidence_store = None
        subject = self.subject_of(self.item_owner(evidence_id))
        keyless = self.client_for(subject)
        keyless.app.state.auth.evidence_store_paths = (self.store_paths[0], self.store_paths[0] / "missing.key")
        self.assertEqual(self.put(keyless, evidence_id).status_code, 503)
        self.assertEqual(self.initiate(keyless, submission_id).status_code, 503)
        self.assertIsNone(self.item(evidence_id)[0])

    def item_owner(self, evidence_id):
        with self.db() as c, c.cursor() as cur:
            cur.execute("SELECT initiated_by_principal_id::text FROM trustlens.evidence_upload_intent WHERE evidence_upload_intent_id = %s",
                        (evidence_id,))
            return cur.fetchone()[0]

    def test_evidence_is_disabled_on_a_database_without_0004(self):
        client, _, submission_id, _ = self.owner_with_submission()
        with patch.object(evidence, "evidence_schema_active", return_value=False):
            self.assertEqual(self.initiate(client, submission_id).status_code, 503)
            self.assertEqual(client.get(f"/api/v1/submissions/{submission_id}/evidence").status_code, 503)

    # ---- concurrent PUT attempts: durable fencing (review finding 2)
    def gate(self, *outcomes):
        """Replace store.put: call i blocks until released, then fails ('fail') or really stores ('ok')."""
        real, lock = self.evidence_store.put, threading.Lock()
        g = type("Gate", (), {})()
        g.entered = [threading.Event() for _ in outcomes]
        g.release = [threading.Event() for _ in outcomes]
        g.locators, g.calls = [None] * len(outcomes), [0]

        def put(data):
            with lock:
                i = g.calls[0]
                g.calls[0] += 1
            g.entered[i].set()
            self.assertTrue(g.release[i].wait(30), "gate never released")
            if outcomes[i] == "fail":
                raise ContentStoreUnavailable("synthetic delayed failure")
            stored = real(data)
            g.locators[i] = stored.locator
            return stored
        patcher = patch.object(self.evidence_store, "put", side_effect=put)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(lambda: [e.set() for e in g.release])
        return g

    def background_put(self, client, evidence_id, data=SMS):
        box = {}
        thread = threading.Thread(target=lambda: box.setdefault("r", self.put(client, evidence_id, data)))
        thread.start()
        self.addCleanup(thread.join, 30)
        return thread, box

    def second_client(self, pid):
        return self.client_for(self.subject_of(pid))

    def test_stale_failure_cannot_overwrite_a_newer_success(self):
        client, _, submission_id, pid = self.owner_with_submission()
        evidence_id = self.initiate(client, submission_id).json()["evidence_id"]
        g = self.gate("fail", "ok")
        with patch.object(evidence, "WRITE_LEASE", timedelta(seconds=1)):
            old, old_box = self.background_put(client, evidence_id)
            self.assertTrue(g.entered[0].wait(10))
            time.sleep(1.3)                                                 # the first attempt outlives its lease
            g.release[1].set()
            newer = self.put(self.second_client(pid), evidence_id)
            self.assertEqual(newer.status_code, 200, newer.text)
            g.release[0].set()                                              # now the delayed failure arrives
            old.join(30)
        self.assertEqual(old_box["r"].status_code, 200)                     # reports the authoritative stored state
        state, locator, _, _, op_state, attempts = self.item(evidence_id)
        self.assertEqual((state, locator, op_state, attempts), ("CONTENT_STORED", g.locators[1], "CONTENT_STORED", 2))
        self.assertEqual(self.finalize(client, evidence_id).status_code, 202)

    def test_stale_success_cannot_overwrite_a_newer_attempt(self):
        client, _, submission_id, pid = self.owner_with_submission()
        evidence_id = self.initiate(client, submission_id).json()["evidence_id"]
        g = self.gate("ok", "ok")
        with patch.object(evidence, "WRITE_LEASE", timedelta(seconds=1)):
            old, old_box = self.background_put(client, evidence_id)
            self.assertTrue(g.entered[0].wait(10))
            time.sleep(1.3)
            newer, newer_box = self.background_put(self.second_client(pid), evidence_id)
            self.assertTrue(g.entered[1].wait(10))                          # the newer attempt now holds the fence
            g.release[0].set()
            old.join(30)
            stale = old_box["r"]
            self.assertEqual((stale.status_code, stale.json()["error"]["code"]), (503, "DEPENDENCY_UNAVAILABLE"))
            self.assertIn("retry-after", stale.headers)
            self.assertEqual(self.item(evidence_id)[0:2], ("CONTENT_PENDING", None))   # stale success not recorded
            g.release[1].set()
            newer.join(30)
        self.assertEqual(newer_box["r"].status_code, 200)
        state, locator, _, _, _, attempts = self.item(evidence_id)
        self.assertEqual((state, locator, attempts), ("CONTENT_STORED", g.locators[1], 2))
        self.assertNotEqual(g.locators[0], g.locators[1])                   # the stale object is an unreferenced orphan
        self.assertEqual(self.finalize(client, evidence_id).status_code, 202)
        self.assertEqual(self.evidence_store.get(locator), SMS)

    def test_concurrent_identical_put_waits_for_the_live_attempt_then_converges(self):
        client, case_id, submission_id, pid = self.owner_with_submission()
        evidence_id = self.initiate(client, submission_id).json()["evidence_id"]
        g = self.gate("ok")
        first, box = self.background_put(client, evidence_id)
        self.assertTrue(g.entered[0].wait(10))
        other = self.second_client(pid)
        busy = self.put(other, evidence_id)                                  # live lease: not a second writer
        self.assertEqual((busy.status_code, busy.json()["error"]["code"]), (503, "DEPENDENCY_UNAVAILABLE"))
        self.assertGreaterEqual(int(busy.headers["retry-after"]), 1)
        conflict = self.put(other, evidence_id, SMS.replace(b"1.99", b"9.99"))
        self.assertEqual((conflict.status_code, conflict.json()["error"]["code"]), (409, "STATE_CONFLICT"))
        early = self.finalize(other, evidence_id)
        self.assertEqual((early.status_code, early.json()["error"]["code"]), (409, "STATE_CONFLICT"))
        g.release[0].set()
        first.join(30)
        self.assertEqual(box["r"].status_code, 200)
        self.assertEqual(self.put(other, evidence_id).status_code, 200)     # identical retry: no-op on the stored state
        self.assertEqual(self.item(evidence_id)[5], 1)                       # exactly one attempt ever wrote
        self.assertEqual(self.finalize(other, evidence_id).status_code, 202)
        self.assertEqual([e[0] for e in self.audit_rows(case_id)].count("EVIDENCE_STORED"), 2)   # stored once + finalized once

    def test_a_crashed_last_attempt_ends_terminal_after_its_lease(self):
        client, _, submission_id, pid = self.owner_with_submission()
        evidence_id = self.initiate(client, submission_id).json()["evidence_id"]
        g = self.gate("ok")
        with patch.object(evidence, "WRITE_LEASE", timedelta(seconds=1)), patch.object(evidence, "MAX_WRITE_ATTEMPTS", 1):
            crashed, _ = self.background_put(client, evidence_id)          # never reports back while we look
            self.assertTrue(g.entered[0].wait(10))
            time.sleep(1.3)
            r = self.put(self.second_client(pid), evidence_id)
            self.assertEqual(r.status_code, 503)
            self.assertNotIn("retry-after", r.headers)
            self.assertEqual(self.item(evidence_id)[0], "FAILED_TERMINAL")
            g.release[0].set()
            crashed.join(30)
        self.assertEqual(self.item(evidence_id)[0:2], ("FAILED_TERMINAL", None))   # the late success is fenced out
        self.assertEqual(self.finalize(client, evidence_id).status_code, 409)

    def test_the_database_enforces_the_fencing_token(self):
        client, _, submission_id, _ = self.owner_with_submission()
        evidence_id = self.initiate(client, submission_id).json()["evidence_id"]     # operation RECEIVED, not terminal
        where = (" WHERE operation_kind = 'EVIDENCE_INGEST' AND idempotency_key = (SELECT idempotency_key FROM"
                 " trustlens.evidence_upload_intent WHERE evidence_upload_intent_id = %s)")
        with self.db() as c, c.cursor() as cur:
            for value in ("attempt_count - 1", "attempt_count + 2"):
                with self.subTest(value=value), self.assertRaises(psycopg.errors.CheckViolation):
                    with c.transaction():
                        cur.execute("UPDATE trustlens.cross_store_operation SET attempt_count = " + value + where, (evidence_id,))
            with c.transaction():                                       # exactly one step forward is the only change allowed
                cur.execute("UPDATE trustlens.cross_store_operation SET attempt_count = attempt_count + 1" + where, (evidence_id,))
                self.assertEqual(cur.rowcount, 1)

    # ---- access control
    def test_cross_user_and_role_isolation(self):
        client, case_id, submission_id, owner_pid = self.owner_with_submission()
        evidence_id = self.full_upload(client, submission_id)
        intruder_subject, _ = self.provision()
        intruder = self.client_for(intruder_subject)
        for response in (intruder.get(f"/api/v1/evidence/{evidence_id}"), intruder.get(f"/api/v1/submissions/{submission_id}/evidence"),
                         self.put(intruder, evidence_id), self.finalize(intruder, evidence_id), self.initiate(intruder, submission_id)):
            self.assertEqual(response.status_code, 404)
            self.assertNotIn(evidence_id, response.text)
        analyst_subject, analyst_pid = self.provision(roles=("ANALYST",))
        with self.db() as c, c.cursor() as cur:
            cur.execute("INSERT INTO trustlens.case_access_grant (case_access_grant_id, case_record_id, principal_reference_id, grant_kind,"
                        " permits_case_metadata, permits_evidence_content, granted_by_principal_id, grant_reason_ref, effective_from)"
                        " VALUES (%s, %s, %s, 'ASSIGNED_ANALYST', true, false, %s, 'TEST-ASSIGNMENT', now())",
                        (str(uuid.uuid4()), case_id, analyst_pid, owner_pid))
        analyst = self.client_for(analyst_subject)
        self.assertEqual(analyst.get(f"/api/v1/evidence/{evidence_id}").status_code, 200)       # metadata only
        for response in (self.put(analyst, evidence_id), self.finalize(analyst, evidence_id), self.initiate(analyst, submission_id)):
            self.assertEqual(response.status_code, 403)
        token = client.headers.pop("X-CSRF-Token")
        self.assertEqual(self.initiate(client, submission_id).status_code, 403)                  # CSRF still enforced
        client.headers["X-CSRF-Token"] = token
        client.cookies.clear()
        self.assertEqual(client.get(f"/api/v1/evidence/{evidence_id}").status_code, 401)

    # ---- idempotency expiry (OPS-001 §5) with supersession
    def expire(self, client, pid, key):
        """Backdate the governing record for `key` as if its 24 h window had ended (test-only, disposable database)."""
        owner = DbHarness._owner_settings()
        with psycopg.connect(**owner.connection_parameters(), autocommit=True) as c, c.cursor() as cur:
            cur.execute("ALTER TABLE trustlens.api_idempotency_record DISABLE TRIGGER tr_api_idempotency_record_write_once")
            try:
                cur.execute("UPDATE trustlens.api_idempotency_record SET created_at = now() - interval '25 hours',"
                            " active_until = now() - interval '1 hour' WHERE principal_reference_id = %s AND idempotency_key_digest = %s"
                            " AND superseded_at IS NULL", (pid, idempotency.key_digest(key)))
            finally:
                cur.execute("ALTER TABLE trustlens.api_idempotency_record ENABLE TRIGGER tr_api_idempotency_record_write_once")

    def test_reused_key_after_the_window_executes_as_a_new_request(self):
        subject, pid = self.provision()
        client = self.client_for(subject)
        key = self.new_key()
        first = self.create_case(client, key=key).json()["case_id"]
        self.assertEqual(self.create_case(client, key=key).json()["case_id"], first)            # inside the window: replay
        self.expire(client, pid, key)
        fresh = self.create_case(client, key=key, body={"relationship_to_content": "SENT"})        # even a different body
        self.assertEqual(fresh.status_code, 201)
        self.assertNotEqual(fresh.json()["case_id"], first)
        self.assertEqual(self.create_case(client, key=key, body={"relationship_to_content": "SENT"}).json()["case_id"],
                         fresh.json()["case_id"])                                                  # the new record governs
        with self.db() as c, c.cursor() as cur:
            cur.execute("SELECT superseded_at IS NOT NULL, outcome_resource_id::text FROM trustlens.api_idempotency_record"
                        " WHERE principal_reference_id = %s AND idempotency_key_digest = %s ORDER BY created_at", (pid, idempotency.key_digest(key)))
            self.assertEqual(cur.fetchall(), [(True, first), (False, fresh.json()["case_id"])])  # history kept, nothing deleted
            with self.assertRaises(psycopg.Error):
                cur.execute("UPDATE trustlens.api_idempotency_record SET superseded_at = now() WHERE principal_reference_id = %s"
                            " AND superseded_at IS NULL", (pid,))                                 # not expired: refused

    def test_concurrent_reuse_of_an_expired_key_executes_once(self):
        subject, pid = self.provision()
        client = self.client_for(subject)
        key = self.new_key()
        self.create_case(client, key=key)
        self.expire(client, pid, key)
        results = []
        clients = [self.client_for(subject) for _ in range(4)]
        threads = [threading.Thread(target=lambda c=c: results.append(self.create_case(c, key=key))) for c in clients]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        created = {r.json()["case_id"] for r in results if r.status_code == 201}
        self.assertEqual(len(created), 1, [r.status_code for r in results])
        self.assertTrue(all(r.status_code in (201, 409) for r in results))
        with self.db() as c, c.cursor() as cur:
            cur.execute("SELECT count(*) FROM trustlens.case_record WHERE owner_principal_id = %s", (pid,))
            self.assertEqual(cur.fetchone()[0], 2)

    def test_concurrent_identical_requests_inside_the_window_execute_once(self):
        subject, pid = self.provision()
        key = self.new_key()
        clients = [self.client_for(subject) for _ in range(4)]
        results = []
        threads = [threading.Thread(target=lambda c=c: results.append(self.create_case(c, key=key))) for c in clients]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len({r.json()["case_id"] for r in results if r.status_code == 201}), 1)
        self.assertTrue(all(r.status_code == 201 or r.json()["error"]["code"] == "IDEMPOTENCY_IN_PROGRESS" for r in results))

    def test_window_boundary_and_legacy_behaviour(self):
        subject, pid = self.provision()
        client = self.client_for(subject)
        key = self.new_key()
        first = self.create_case(client, key=key).json()["case_id"]
        with self.db() as c:
            replay = idempotency.claim(c, pid, "createCase", "/api/v1/cases", key,
                                       idempotency.semantic_digest("createCase", "/api/v1/cases", {}), supersession=True)
        self.assertEqual((replay.status, replay.resource_id), (201, first))                  # just inside: replay
        self.expire(client, pid, key)
        with self.db() as c, self.assertRaises(idempotency.KeyReused):
            idempotency.claim(c, pid, "createCase", "/api/v1/cases", key,
                              idempotency.semantic_digest("createCase", "/api/v1/cases", {}), supersession=False)  # 0003 schema


if __name__ == "__main__":
    unittest.main()
