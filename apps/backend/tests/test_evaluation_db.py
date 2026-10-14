"""S5 end-to-end governed evaluation against a DISPOSABLE PostgreSQL (migration 0006), a temporary encrypted evidence
store and the exact approved knowledge bundle activated through the accepted API. Synthetic messages only.

Every classification asserted here is what the existing Phase-3 kernel returns for the raw message text through S4
extraction; nothing is fixture-backed or hardcoded on the result path. No accuracy claim is made (G-09).
"""
import dataclasses
import hashlib
import json
import os
import shutil
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import psycopg

from db_harness import CATALOG, DISPOSABLE, DbHarness
from knowledge.ai.governance import canonical_json
from knowledge.publish.build_bundle import build
from trustlens_backend import evaluation
from trustlens_backend.content_store import LocalEncryptedContentStore
from trustlens_backend.knowledge_seam import KnowledgeVerifier

ROOT = Path(__file__).resolve().parents[3]
APPROVED = json.loads((ROOT / "apps/backend/knowledge_releases/local-development.json").read_text())["approved_bundles"][0]
TEXT = "text/plain; charset=utf-8"
OTP = b"SYNTHETIC TEST: Example Bank: unusual activity. Share the OTP you just received with our officer now."
# (raw message, expected support status, expected classification, expected governing rule or None)
MATRIX = {
    "otp_request": (OTP, "SUPPORTED", "SCAM_PATTERN_DETECTED", "TL-CRED-001"),
    "upi_pin_to_receive": (b"SYNTHETIC TEST: Your refund is pending. Enter your UPI PIN to RECEIVE Rs 5,000 now.",
                           "SUPPORTED", "SCAM_PATTERN_DETECTED", None),
    "advance_fee_job": (b"SYNTHETIC TEST: Congratulations, you have been selected for the data entry job. Pay Rs 1,500 "
                        b"registration fee today to receive your offer letter.", "SUPPORTED", "SCAM_PATTERN_DETECTED", "TL-JOB-001"),
    "utility_disconnection": (b"SYNTHETIC TEST: Your electricity connection will be disconnected tonight. Pay now to avoid "
                              b"disconnection.", "SUPPORTED", "SCAM_PATTERN_DETECTED", "TL-UTIL-001"),
    "benign": (b"SYNTHETIC TEST: Hi Mum, I will be home by seven tonight. Can you keep some dinner for me?",
               "SUPPORTED", "INSUFFICIENT_EVIDENCE", None),
    "negated_otp_notice": (b"SYNTHETIC TEST: Your OTP is 482913 for your transaction. Never share it with anyone. -Example Bank",
                           "SUPPORTED", "INSUFFICIENT_EVIDENCE", None),
    "reported_scam": (b"SYNTHETIC TEST: The scammer asked me to share my OTP. Is this a fraud?",
                      "SUPPORTED", "INSUFFICIENT_EVIDENCE", None),
    "quoted_scam": (b'SYNTHETIC TEST: My uncle got this: "guaranteed 200% returns, connect your wallet now". Is it a scam?',
                    "SUPPORTED", "INSUFFICIENT_EVIDENCE", None),
    "ambiguous_payment_direction": (b"SYNTHETIC TEST: Scan this QR to complete the transaction. [image attached]",
                                    "PARTIALLY_SUPPORTED", "INSUFFICIENT_EVIDENCE", None),
    "unsupported_language": ("SYNTHETIC: अपना OTP शेयर करें अभी".encode(),
                             "UNSUPPORTED", "UNSUPPORTED", None),
    "insufficient": (b"ok thanks", "INSUFFICIENT_INFORMATION", "INSUFFICIENT_EVIDENCE", None),
    "malformed_control_characters": (b"SYNTHETIC TEST: Share the OTP\x00\x07 now", "ERROR", "ERROR", None),
}


def code(response):
    return response.json()["error"]["code"]


@unittest.skipUnless(DISPOSABLE, "needs an explicitly disposable PostgreSQL")
class EvaluationJourneyTests(DbHarness, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.store = Path(cls.tmp.name) / "knowledge"
        staging = cls.store / "staging"
        cls.digest = build(staging, gate="PASS")["content_digest"]
        staging.rename(cls.store / cls.digest)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        work = Path(tempfile.mkdtemp(dir=self.tmp.name))
        self.addCleanup(shutil.rmtree, work, True)
        root, kek = work / "evidence", work / "kek.key"
        root.mkdir(mode=0o700)
        kek.write_bytes(os.urandom(32))
        kek.chmod(0o600)
        self.evidence_paths = (root, kek)
        self.evidence_store = LocalEncryptedContentStore(root, kek)
        self.knowledge_verifier = KnowledgeVerifier(self.store)
        self.knowledge_release_dir = work
        self.deployment_ref = f"test-{uuid.uuid4().hex[:12]}"
        self.owner_sql("INSERT INTO trustlens.knowledge_deployment_state (knowledge_deployment_state_id, deployment_ref,"
                       " operational_state, state_changed_at) VALUES (gen_random_uuid(), %s, 'NO_ACTIVE_BUNDLE', now())",
                       (self.deployment_ref,))

    # ---- helpers
    def owner_sql(self, sql, args=()):
        with psycopg.connect(**self._owner_settings().connection_parameters(), autocommit=True) as c, c.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall() if cur.description else None

    def app_sql(self, sql, args=()):
        with self.db() as c, c.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall() if cur.description else None

    def activate_exact_bundle(self):
        record = {"release_record_schema_version": "1.0", "deployment_ref": self.deployment_ref,
                  "profile": "SINGLE_MACHINE_SYNTHETIC_DEVELOPMENT",
                  "authenticity_policy": {"decision": "DEC-012", "outcome": "NOT_REQUIRED_BY_POLICY", "scope": "test"},
                  "approved_bundles": [{"release_record_ref": "TL-KREL-TEST-0001", "content_digest": self.digest,
                                        "bundle_version": "1.0.0", "manifest_schema_version": "1.1.0"}]}
        (self.knowledge_release_dir / f"{self.deployment_ref}.json").write_text(json.dumps(record))
        subject, _ = self.provision(roles=("ADMINISTRATOR",))
        admin = self.client_for(subject)
        r = admin.post("/api/v1/knowledge/deployment/activate", json={"content_digest": self.digest, "governance_change_ref": "DEC-011:S5-TEST",
                       "expected_active_content_digest": None}, headers={"Idempotency-Key": self.new_key()})
        self.assertEqual(r.status_code, 202, r.text)
        return admin

    def owner(self):
        subject, pid = self.provision()
        return self.client_for(subject), pid

    def submit(self, client, data, finalize=True, input_type="SMS"):
        case_id = self.create_case(client).json()["case_id"]
        submission_id = self.create_submission(client, case_id, body={"declared_input_type": input_type,
                                                                       "relationship_to_content": "RECEIVED"}).json()["submission_id"]
        evidence_id = client.post(f"/api/v1/submissions/{submission_id}/evidence", headers={"Idempotency-Key": self.new_key()},
                                  json={"artifact_kind": "TEXT_BODY", "declared_media_type": TEXT,
                                        "declared_byte_length": len(data)}).json()["evidence_id"]
        self.assertEqual(client.put(f"/api/v1/evidence/{evidence_id}/content", content=data, headers={"Content-Type": TEXT}).status_code, 200)
        if finalize:
            self.assertEqual(client.post(f"/api/v1/evidence/{evidence_id}/finalize", json={},
                                         headers={"Idempotency-Key": self.new_key()}).status_code, 202)
        return case_id, submission_id, evidence_id

    def analyze(self, client, submission_id, body=None, key=None):
        return client.post(f"/api/v1/submissions/{submission_id}/evaluations", json=body or {},
                           headers={"Idempotency-Key": key or self.new_key()})

    def journey(self, client, data):
        case_id, submission_id, _ = self.submit(client, data)
        r = self.analyze(client, submission_id)
        self.assertEqual(r.status_code, 202, r.text)
        evaluation_id = r.json()["evaluations"][0]["evaluation_id"]
        return case_id, submission_id, evaluation_id

    def status(self, client, evaluation_id):
        r = client.get(f"/api/v1/evaluations/{evaluation_id}")
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def result(self, client, evaluation_id, view=None):
        return client.get(f"/api/v1/evaluations/{evaluation_id}/result" + (f"?view={view}" if view else ""))

    def runtime_of(self, client):
        return client.app.state.auth

    # ---- contract parity
    def test_operations_match_the_catalog(self):
        ops = {o["operation_id"]: o for o in CATALOG["operations"]}
        for operation_id, spec in evaluation.OPERATIONS.items():
            with self.subTest(operation=operation_id):
                self.assertEqual((spec["method"], spec["path"], list(spec["roles"]), spec["resource_authorization"]),
                                 (ops[operation_id]["method"], ops[operation_id]["path"], ops[operation_id]["roles"],
                                  ops[operation_id]["resource_authorization"]))

    # ---- the browser-equivalent journey
    def test_upload_finalize_analyze_and_read_a_real_pinned_result(self):
        self.activate_exact_bundle()
        client, pid = self.owner()
        case_id, submission_id, evaluation_id = self.journey(client, OTP)
        accepted = self.status(client, evaluation_id)
        self.assert_schema(accepted, "EvaluationResponse")
        self.assertEqual((accepted["state"], accepted["result_availability"], accepted["origin"], accepted["failure"]),
                         ("COMPLETED", "AVAILABLE", "INITIAL", None))
        self.assertEqual(accepted["provenance"]["bundle_content_digest"], APPROVED["content_digest"])
        self.assertEqual(accepted["ai_usage"], {"requested": False, "enabled_by_policy": False, "used": False, "fallback_reason": None})
        r = self.result(client, evaluation_id)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assert_schema(body, "DetectionResultResponse")
        self.assertEqual((body["view"], body["input_support_status"], body["classification"], body["risk_level"],
                          body["detection_confidence"], body["decision_severity"], body["matched_evidence_strength"]),
                         ("STANDARD", "SUPPORTED", "SCAM_PATTERN_DETECTED", "CRITICAL", "HIGH", "CRITICAL", "STRONG"))
        self.assertEqual(body["governing_rule"], {"rule_id": "TL-CRED-001", "rule_version": "1.0.0", "source_references": ["SRC-004"]})
        self.assertEqual([a["action_code"] for a in body["recommended_actions"]],
                         ["DO_NOT_SHARE_CREDENTIALS", "VERIFY_INDEPENDENTLY", "CONTACT_BANK", "REPORT_CYBERCRIME"])
        self.assertTrue(any("Reserve Bank of India (SRC-004)" in s for s in body["explanation"]["evidence_basis"]))
        self.assertNotIn("rule_results", body)                                           # STANDARD never carries it
        self.assertTrue(body["not_an_official_determination"])
        self.assertIsNone(body["absence_of_finding_notice"])
        self.assertEqual(body["provenance"]["bundle_content_digest"], APPROVED["content_digest"])
        for forbidden in ("score", "probability", "matched_positive_indicators", "observations"):
            self.assertNotIn(forbidden, json.dumps(body))
        # persistence: the exact canonical document, its digest and pins equal to the evaluation's
        stored = self.app_sql("SELECT r.result_digest, r.result_canonical_json, r.classification, r.bundle_content_digest,"
                              " e.status, e.bundle_content_digest, e.engine_version, e.input_id, e.replay_material_digest IS NOT NULL,"
                              " e.execution_fence_token = r.execution_fence_token FROM trustlens.detection_result r"
                              " JOIN trustlens.evaluation e ON e.evaluation_id = r.evaluation_id WHERE r.evaluation_id = %s",
                              (evaluation_id,))[0]
        self.assertEqual(stored[0], hashlib.sha256(stored[1].encode()).hexdigest())
        self.assertEqual(stored[0], body["result_digest"])
        self.assertEqual(json.loads(stored[1])["classification"], stored[2])
        self.assertEqual(stored[3:], (APPROVED["content_digest"], "COMPLETED", APPROVED["content_digest"], "1.0.0",
                                      stored[7], True, True))
        artifact = self.app_sql("SELECT a.governed_artifact_digest, a.artifact_canonical_json, s.evidence_item_id::text"
                                " FROM trustlens.governed_input_artifact a JOIN trustlens.input_envelope_source s"
                                " ON s.input_envelope_record_id = a.input_envelope_record_id WHERE a.evaluation_id = %s", (evaluation_id,))
        self.assertEqual(len(artifact), 1)
        self.assertEqual(artifact[0][0], hashlib.sha256(artifact[0][1].encode()).hexdigest())
        governed = json.loads(artifact[0][1])
        self.assertIn("CREDENTIAL_REQUEST_OTP", {i["indicator_id"] for i in governed["indicator_observations"]})
        self.assertEqual(governed["evaluation_context"]["knowledge_content_digest"], APPROVED["content_digest"])
        events = [(e[0], e[1]) for e in self.audit_rows(case_id)]
        for expected in (("EVIDENCE_ACCESSED", "SUCCEEDED"), ("EVALUATION_STARTED", "SUCCEEDED"), ("RESULT_PERSISTED", "SUCCEEDED"),
                         ("EVALUATION_COMPLETED", "SUCCEEDED")):
            self.assertIn(expected, events)
        reads = len([e for e in self.audit_rows(case_id) if e[0] == "EVIDENCE_ACCESSED"])
        again = self.result(client, evaluation_id).json()
        self.assertEqual(again, body)                                                    # the immutable record, re-read
        self.assertEqual(len([e for e in self.audit_rows(case_id) if e[0] == "EVIDENCE_ACCESSED"]), reads + 1)
        listed = client.get(f"/api/v1/cases/{case_id}/evaluations").json()
        self.assertEqual([i["evaluation_id"] for i in listed["items"]], [evaluation_id])
        self.verify_chain()

    def test_real_raw_messages_feed_the_existing_kernel(self):
        self.activate_exact_bundle()
        client, _ = self.owner()
        for name, (data, support, classification, governing) in MATRIX.items():
            with self.subTest(message=name):
                _, _, evaluation_id = self.journey(client, data)
                self.assertEqual(self.status(client, evaluation_id)["state"], "COMPLETED")
                body = self.result(client, evaluation_id).json()
                self.assertEqual((body["input_support_status"], body["classification"]), (support, classification))
                if governing:
                    self.assertEqual(body["governing_rule"]["rule_id"], governing)
                if classification != "SCAM_PATTERN_DETECTED":
                    self.assertIsNone(body["governing_rule"])
                    self.assertEqual(body["risk_level"], "NONE")
                self.assertNotEqual(body["classification"], "NO_SCAM_PATTERN" if support != "SUPPORTED" else "-")
                if support == "UNSUPPORTED":
                    self.assertIn("RESUBMIT_IN_SUPPORTED_LANGUAGE", [a["action_code"] for a in body["recommended_actions"]])

    def test_case_evaluation_list_applies_the_accepted_filters(self):
        self.activate_exact_bundle()
        client, _ = self.owner()
        case_id, completed_sub, completed = self.journey(client, OTP)
        failed_sub = self.create_submission(client, case_id).json()["submission_id"]
        evidence_id = client.post(f"/api/v1/submissions/{failed_sub}/evidence", headers={"Idempotency-Key": self.new_key()},
                                  json={"artifact_kind": "TEXT_BODY", "declared_media_type": TEXT, "declared_byte_length": len(OTP)}).json()["evidence_id"]
        client.put(f"/api/v1/evidence/{evidence_id}/content", content=OTP, headers={"Content-Type": TEXT})
        client.post(f"/api/v1/evidence/{evidence_id}/finalize", json={}, headers={"Idempotency-Key": self.new_key()})
        with patch.object(evaluation, "dispatch", lambda runtime, ids: None):
            queued = self.analyze(client, completed_sub).json()["evaluations"][0]["evaluation_id"]
            failed = self.analyze(client, failed_sub).json()["evaluations"][0]["evaluation_id"]
        evaluation.run_evaluation(dataclasses.replace(self.runtime_of(client), knowledge_verifier=None), failed)
        base = f"/api/v1/cases/{case_id}/evaluations"

        def ids(query):
            r = client.get(base + query)
            self.assertEqual(r.status_code, 200, r.text)
            self.assert_schema(r.json(), "EvaluationListResponse")
            return {i["evaluation_id"] for i in r.json()["items"]}

        self.assertEqual(ids(""), {completed, queued, failed})
        self.assertEqual(ids("?state=COMPLETED"), {completed})
        self.assertEqual(ids("?state=QUEUED"), {queued})
        self.assertEqual(ids("?state=FAILED"), {failed})
        self.assertEqual(ids("?state=RUNNING"), set())
        self.assertEqual(ids("?result_availability=AVAILABLE"), {completed})
        self.assertEqual(ids("?result_availability=NOT_PRODUCED"), {failed})
        self.assertEqual(ids("?result_availability=NOT_YET_AVAILABLE"), {queued})
        self.assertEqual(ids("?result_availability=REMOVED_UNDER_GOVERNANCE"), set())
        self.assertEqual(ids(f"?submission_id={completed_sub}"), {completed, queued})
        self.assertEqual(ids(f"?submission_id={completed_sub}&state=COMPLETED"), {completed})
        self.assertEqual(ids("?requested_from=2000-01-01T00:00:00Z&requested_to=2999-01-01T00:00:00Z"), {completed, queued, failed})
        self.assertEqual(ids("?requested_to=2000-01-01T00:00:00Z"), set())
        self.assertEqual(ids("?state=COMPLETED&limit=1"), {completed})
        for query, field in (("?state=DONE", "state"), ("?state=completed", "state"), ("?result_availability=SAFE", "result_availability"),
                             ("?submission_id=not-a-uuid", "submission_id"), ("?requested_from=yesterday", "requested_from"),
                             ("?requested_to=2026-10-15T00:00:00", "requested_to"), ("?status=COMPLETED", "status"),
                             ("?state=COMPLETED&state=FAILED", "state"), ("?limit=0", "limit")):
            with self.subTest(query=query):
                r = client.get(base + query)
                self.assertEqual((r.status_code, code(r)), (400, "INVALID_REQUEST"))
                self.assertIn(field, [e["field"] for e in r.json()["error"]["field_errors"]])
        stranger, _ = self.owner()
        self.assertEqual(stranger.get(base + "?state=COMPLETED").status_code, 404)        # masked, whatever the filter
        subject, _ = self.provision(roles=("KNOWLEDGE_EDITOR",))
        self.assertEqual(self.client_for(subject).get(base + "?state=COMPLETED").status_code, 404)

    def test_negation_before_a_contrast_does_not_hide_a_live_request(self):
        self.activate_exact_bundle()
        client, _ = self.owner()
        _, _, evaluation_id = self.journey(client, b"SYNTHETIC TEST: Example Bank: We do not need your password, but share the OTP"
                                                   b" you just received with our officer now.")
        body = self.result(client, evaluation_id).json()
        self.assertEqual((body["classification"], body["governing_rule"]["rule_id"]), ("SCAM_PATTERN_DETECTED", "TL-CRED-001"))

    # ---- idempotency, determinism and immutability
    def test_retries_are_idempotent_and_repeats_are_deterministic(self):
        self.activate_exact_bundle()
        client, _ = self.owner()
        _, submission_id, _ = self.submit(client, OTP)
        key = self.new_key()
        first = self.analyze(client, submission_id, key=key)
        replay = self.analyze(client, submission_id, key=key)
        self.assertEqual((first.status_code, replay.status_code), (202, 202))
        evaluation_id = first.json()["evaluations"][0]["evaluation_id"]
        self.assertEqual(replay.json()["evaluations"][0]["evaluation_id"], evaluation_id)
        self.assertEqual(code(self.analyze(client, submission_id, body={"analysis_mode": "DETERMINISTIC"}, key=key)),
                         "IDEMPOTENCY_KEY_REUSED")
        self.assertEqual(self.app_sql("SELECT count(*) FROM trustlens.evaluation WHERE submission_id = %s", (submission_id,))[0][0], 1)
        repeat = self.analyze(client, submission_id).json()["evaluations"][0]["evaluation_id"]  # a new request: new evaluation
        self.assertNotEqual(repeat, evaluation_id)
        docs = [json.loads(self.app_sql("SELECT result_canonical_json FROM trustlens.detection_result WHERE evaluation_id = %s",
                                        (e,))[0][0]) for e in (evaluation_id, repeat)]
        for doc in docs:
            doc.pop("evaluation_id"), doc.pop("evaluation_timestamp")
        self.assertEqual(docs[0], docs[1])                                               # same input, same knowledge, same result
        artifacts = self.app_sql("SELECT DISTINCT governed_artifact_digest FROM trustlens.governed_input_artifact a"
                                 " JOIN trustlens.evaluation e ON e.evaluation_id = a.evaluation_id WHERE e.submission_id = %s",
                                 (submission_id,))
        self.assertEqual(len(artifacts), 1)                                              # one artifact per evaluation, identical
        envelopes = self.app_sql("SELECT count(*) FROM trustlens.input_envelope_record r JOIN trustlens.submission s"
                                 " ON s.submission_id = r.submission_id WHERE s.submission_id = %s", (submission_id,))
        self.assertEqual(envelopes[0][0], 1)                                             # one envelope per input
        with self.db() as c, c.cursor() as cur:
            for sql in ("UPDATE trustlens.detection_result SET classification = 'NO_SCAM_PATTERN' WHERE evaluation_id = %s",
                        "DELETE FROM trustlens.detection_result WHERE evaluation_id = %s",
                        "UPDATE trustlens.evaluation SET status = 'FAILED_INFRASTRUCTURE', failure_category = 'PERSISTENCE_FAILED',"
                        " failed_at = now(), execution_fence_token = NULL WHERE evaluation_id = %s",
                        "UPDATE trustlens.governed_input_artifact SET governed_artifact_digest = repeat('0', 64) WHERE evaluation_id = %s"):
                with self.subTest(sql=sql[:50]), self.assertRaises(psycopg.Error):
                    cur.execute(sql, (evaluation_id,))

    # ---- authorization
    def test_authorization_and_existence_masking_are_preserved(self):
        admin = self.activate_exact_bundle()
        client, _ = self.owner()
        case_id, submission_id, evaluation_id = self.journey(client, OTP)
        stranger, _ = self.owner()
        subject, _ = self.provision(roles=("KNOWLEDGE_EDITOR",))
        editor = self.client_for(subject)
        for who, label in ((stranger, "other user"), (admin, "administrator"), (editor, "knowledge editor")):
            with self.subTest(caller=label):
                self.assertEqual(self.analyze(who, submission_id).status_code, 404)
                self.assertEqual(who.get(f"/api/v1/evaluations/{evaluation_id}").status_code, 404)
                self.assertEqual(self.result(who, evaluation_id).status_code, 404)
                self.assertEqual(who.get(f"/api/v1/cases/{case_id}/evaluations").status_code, 404)
        self.assertEqual(self.result(client, evaluation_id, "DETAILED").status_code, 403)    # owner: STANDARD only
        self.assertEqual(self.result(client, evaluation_id, "EVERYTHING").status_code, 400)
        self.assertEqual(client.get(f"/api/v1/evaluations/{evaluation_id}/result?view=STANDARD&debug=1").status_code, 400)
        self.assertEqual(self.analyze(client, submission_id, body={"classification": "NO_SCAM_PATTERN"}).status_code, 400)
        self.assertEqual(self.analyze(client, submission_id, body={"analysis_mode": "MAGIC"}).status_code, 400)
        no_csrf = client.post(f"/api/v1/submissions/{submission_id}/evaluations", json={},
                              headers={"Idempotency-Key": self.new_key(), "X-CSRF-Token": "wrong"})
        self.assertEqual(no_csrf.status_code, 403)
        self.assertEqual(client.post(f"/api/v1/submissions/{submission_id}/evaluations", json={}).status_code, 400)  # key required
        self.verify_chain()

    # ---- explicit refusals and failures
    def test_unfinalized_evidence_and_unavailable_knowledge_are_explicit(self):
        client, _ = self.owner()
        _, submission_id, _ = self.submit(client, OTP)
        self.assertEqual(code(self.analyze(client, submission_id)), "DEPENDENCY_UNAVAILABLE")   # nothing activated
        self.activate_exact_bundle()
        _, pending, _ = self.submit(client, OTP, finalize=False)
        case_id = self.create_case(client).json()["case_id"]                             # invalid UTF-8 never reaches analysis
        sub = self.create_submission(client, case_id).json()["submission_id"]
        bad = client.post(f"/api/v1/submissions/{sub}/evidence", headers={"Idempotency-Key": self.new_key()},
                          json={"artifact_kind": "TEXT_BODY", "declared_media_type": TEXT, "declared_byte_length": 4}).json()["evidence_id"]
        self.assertEqual(client.put(f"/api/v1/evidence/{bad}/content", content=b"\xff\xfe\xfd\xfc",
                                    headers={"Content-Type": TEXT}).status_code, 415)
        self.assertEqual(code(self.analyze(client, pending)), "STATE_CONFLICT")
        self.assertEqual(self.app_sql("SELECT count(*) FROM trustlens.evaluation WHERE submission_id IN (%s, %s)",
                                      (submission_id, pending))[0][0], 0)

    def test_a_crash_before_dispatch_resumes_after_restart(self):
        self.activate_exact_bundle()
        client, _ = self.owner()
        _, submission_id, _ = self.submit(client, OTP)
        with patch.object(evaluation, "dispatch", lambda runtime, ids: None):              # the process dies after 202
            evaluation_id = self.analyze(client, submission_id).json()["evaluations"][0]["evaluation_id"]
        self.assertEqual(self.status(client, evaluation_id)["state"], "QUEUED")
        self.assertEqual(code(self.result(client, evaluation_id)), "EVALUATION_NOT_COMPLETED")
        restarted, _ = self.owner()                                                      # a new process, same stores
        outcome = evaluation.recover(self.runtime_of(restarted))
        self.assertIn(evaluation_id, outcome["dispatched"])
        self.assertEqual(self.status(client, evaluation_id)["state"], "COMPLETED")
        self.assertEqual(self.result(client, evaluation_id).json()["classification"], "SCAM_PATTERN_DETECTED")

    def test_a_lost_execution_is_fenced_and_a_retry_is_a_new_evaluation(self):
        self.activate_exact_bundle()
        client, _ = self.owner()
        _, submission_id, _ = self.submit(client, OTP)
        with patch.object(evaluation, "dispatch", lambda runtime, ids: None):
            evaluation_id = self.analyze(client, submission_id).json()["evaluations"][0]["evaluation_id"]

        class Crash(Exception):
            pass

        def crash():
            raise Crash()

        with self.assertRaises(Crash):                                                   # dies after RUNNING, before commit
            evaluation.run_evaluation(self.runtime_of(client), evaluation_id, before_completion=crash)
        self.assertEqual(self.status(client, evaluation_id)["state"], "RUNNING")
        self.app_sql("UPDATE trustlens.evaluation SET execution_lease_expires_at = now() - interval '1 second'"
                     " WHERE evaluation_id = %s", (evaluation_id,))
        self.assertIn(evaluation_id, evaluation.recover(self.runtime_of(client))["fenced"])
        failed = self.status(client, evaluation_id)
        self.assertEqual((failed["state"], failed["result_availability"], failed["failure"]),
                         ("FAILED", "NOT_PRODUCED", {"failure_class": "INFRASTRUCTURE", "reason": "INFRASTRUCTURE_FAILURE",
                                                     "retry_guidance": "RETRY_AS_NEW_EVALUATION"}))
        self.assertEqual(code(self.result(client, evaluation_id)), "EVALUATION_NOT_COMPLETED")
        retry = self.analyze(client, submission_id, body={"predecessor_evaluation_id": evaluation_id}).json()["evaluations"][0]
        self.assertEqual((retry["origin"], retry["predecessor_evaluation_id"]), ("RETRY_AFTER_FAILURE", evaluation_id))
        self.assertEqual(self.status(client, retry["evaluation_id"])["state"], "COMPLETED")
        self.assertEqual(self.app_sql("SELECT count(*) FROM trustlens.detection_result WHERE evaluation_id = %s", (evaluation_id,))[0][0], 0)

    def test_a_stale_worker_cannot_commit_after_being_fenced(self):
        self.activate_exact_bundle()
        client, _ = self.owner()
        _, submission_id, _ = self.submit(client, OTP)
        with patch.object(evaluation, "dispatch", lambda runtime, ids: None):
            evaluation_id = self.analyze(client, submission_id).json()["evaluations"][0]["evaluation_id"]
        runtime = self.runtime_of(client)

        def fence_meanwhile():                                                           # the lease expired and was fenced
            self.app_sql("UPDATE trustlens.evaluation SET execution_lease_expires_at = now() - interval '1 second'"
                         " WHERE evaluation_id = %s", (evaluation_id,))
            evaluation.recover(runtime)

        evaluation.run_evaluation(runtime, evaluation_id, before_completion=fence_meanwhile)
        self.assertEqual(self.status(client, evaluation_id)["state"], "FAILED")
        self.assertEqual(self.app_sql("SELECT count(*) FROM trustlens.detection_result WHERE evaluation_id = %s", (evaluation_id,))[0][0], 0)
        token = str(uuid.uuid4())                                                        # the database refuses a forged result
        with self.db() as c, c.cursor() as cur, self.assertRaises(psycopg.Error):
            cur.execute("INSERT INTO trustlens.detection_result SELECT gen_random_uuid(), %s, %s::uuid, r.result_contract_version,"
                        " r.result_digest, r.canonical_json_version, r.storage_mode, r.result_canonical_json, NULL, r.input_support_status,"
                        " r.classification, r.decision_severity, r.matched_evidence_strength, r.risk_level, r.detection_confidence,"
                        " r.degraded, r.engine_version, r.bundle_version, r.bundle_content_digest, r.commit_sha, r.evaluation_profile_id,"
                        " r.extraction_confidence_gate, r.risk_matrix_id, r.confidence_policy_id, r.action_policy_version,"
                        " r.component_versions, r.evaluation_timestamp, r.input_id, r.language, r.script, now(),"
                        " r.retention_policy_reference_id FROM trustlens.detection_result r LIMIT 1", (evaluation_id, token))

    def test_concurrent_workers_produce_exactly_one_result(self):
        self.activate_exact_bundle()
        client, _ = self.owner()
        _, submission_id, _ = self.submit(client, OTP)
        with patch.object(evaluation, "dispatch", lambda runtime, ids: None):
            evaluation_id = self.analyze(client, submission_id).json()["evaluations"][0]["evaluation_id"]
        runtime, barrier = self.runtime_of(client), threading.Barrier(4)

        def worker():
            barrier.wait()
            evaluation.run_evaluation(runtime, evaluation_id)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(self.status(client, evaluation_id)["state"], "COMPLETED")
        self.assertEqual(self.app_sql("SELECT count(*) FROM trustlens.detection_result WHERE evaluation_id = %s", (evaluation_id,))[0][0], 1)
        self.assertEqual(len([e for e in self.app_sql("SELECT event_type FROM trustlens.audit_event WHERE evaluation_id = %s",
                                                       (evaluation_id,)) if e[0] == "EVALUATION_COMPLETED"]), 1)

    def test_missing_knowledge_at_execution_fails_as_a_precondition_never_as_a_result(self):
        self.activate_exact_bundle()
        client, _ = self.owner()
        _, submission_id, _ = self.submit(client, OTP)
        with patch.object(evaluation, "dispatch", lambda runtime, ids: None):
            evaluation_id = self.analyze(client, submission_id).json()["evaluations"][0]["evaluation_id"]
        evaluation.run_evaluation(dataclasses.replace(self.runtime_of(client), knowledge_verifier=None), evaluation_id)
        failed = self.status(client, evaluation_id)
        self.assertEqual((failed["state"], failed["failure"]["failure_class"], failed["failure"]["reason"]),
                         ("FAILED", "PRECONDITION", "KNOWLEDGE_UNAVAILABLE"))
        self.assertIsNone(failed["provenance"])                                          # never pinned, never run

    def test_tampered_artifact_or_result_is_withheld(self):
        self.activate_exact_bundle()
        client, _ = self.owner()
        case_id, _, evaluation_id = self.journey(client, OTP)
        self.owner_sql("ALTER TABLE trustlens.detection_result DISABLE TRIGGER tr_detection_result_immutable")
        try:
            self.owner_sql("UPDATE trustlens.detection_result SET result_canonical_json = replace(result_canonical_json,"
                           " 'SCAM_PATTERN_DETECTED', 'NO_SCAM_PATTERN') WHERE evaluation_id = %s", (evaluation_id,))
        finally:
            self.owner_sql("ALTER TABLE trustlens.detection_result ENABLE TRIGGER tr_detection_result_immutable")
        r = self.result(client, evaluation_id)
        self.assertEqual((r.status_code, code(r)), (500, "INTEGRITY_FAILURE"))
        self.assertIn(("INTEGRITY_FAILURE", "FAILED"), [(e[0], e[1]) for e in self.audit_rows(case_id)])

    def test_durable_result_survives_a_restart(self):
        self.activate_exact_bundle()
        client, pid = self.owner()
        case_id, _, evaluation_id = self.journey(client, OTP)
        before = self.result(client, evaluation_id).json()
        subject = self.app_sql("SELECT external_subject FROM trustlens.principal_reference WHERE principal_reference_id = %s", (pid,))[0][0]
        self.evidence_store = LocalEncryptedContentStore(*self.evidence_paths)        # fresh process, same key and store
        self.knowledge_verifier = KnowledgeVerifier(self.store)
        after = self.client_for(subject)
        self.assertEqual(self.result(after, evaluation_id).json(), before)
        self.assertEqual(after.get(f"/api/v1/cases/{case_id}/evaluations").json()["items"][0]["state"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
