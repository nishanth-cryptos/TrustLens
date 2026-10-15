"""S6 case history against a DISPOSABLE PostgreSQL (migrations 0006 + 0007): original-evidence download, user corrections
and re-analysis as new evaluations, and exact replay of pinned material. Synthetic messages only."""
import hashlib
import json
import shutil
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import psycopg

from db_harness import CATALOG, DISPOSABLE
from knowledge.publish.build_bundle import build
from test_evaluation_db import OTP, TEXT, EvaluationHarness, code
from test_knowledge_db import variant
from trustlens_backend import evaluation, history
from trustlens_backend.content_store import LocalEncryptedContentStore
from trustlens_backend.knowledge_seam import KnowledgeVerifier

DESCRIPTION = "SYNTHETIC: the sender was not my bank, it was an unknown number"


@unittest.skipUnless(DISPOSABLE, "needs an explicitly disposable PostgreSQL")
class HistoryTests(EvaluationHarness, unittest.TestCase):
    # ---- helpers
    def completed(self, data=OTP):
        self.activate_exact_bundle()
        client, pid = self.owner()
        case_id, submission_id, evaluation_id = self.journey(client, data)
        self.assertEqual(self.status(client, evaluation_id)["state"], "COMPLETED")
        evidence_id = self.app_sql("SELECT evidence_item_id::text FROM trustlens.evidence_item WHERE submission_id = %s",
                                   (submission_id,))[0][0]
        return client, case_id, submission_id, evaluation_id, evidence_id

    def download(self, client, evidence_id):
        return client.get(f"/api/v1/evidence/{evidence_id}/content")

    def correct(self, client, evaluation_id, body=None, key=None):
        return client.post(f"/api/v1/evaluations/{evaluation_id}/corrections",
                           json={"correction_description": DESCRIPTION, "reason_code": "EXTRACTION_ERROR"} if body is None else body,
                           headers={"Idempotency-Key": key or self.new_key()})

    def replay(self, client, evaluation_id, key=None, body=None):
        return client.post(f"/api/v1/evaluations/{evaluation_id}/replays", json=body or {"reason_code": "ANALYST_VERIFICATION"},
                           headers={"Idempotency-Key": key or self.new_key()})

    def admin(self):
        subject, _ = self.provision(roles=("ADMINISTRATOR",))
        return self.client_for(subject)

    def stored_result(self, evaluation_id):
        return self.app_sql("SELECT result_digest, result_canonical_json FROM trustlens.detection_result WHERE evaluation_id = %s",
                            (evaluation_id,))[0]

    def test_operations_match_the_catalog(self):
        ops = {o["operation_id"]: o for o in CATALOG["operations"]}
        for operation_id, spec in history.OPERATIONS.items():
            with self.subTest(operation=operation_id):
                self.assertEqual((spec["method"], spec["path"], list(spec["roles"]), spec["resource_authorization"]),
                                 (ops[operation_id]["method"], ops[operation_id]["path"], ops[operation_id]["roles"],
                                  ops[operation_id]["resource_authorization"]))

    # ---- getEvidenceContent
    def test_original_evidence_downloads_exactly_with_integrity_permissions_and_audit(self):
        client, case_id, _, _, evidence_id = self.completed()
        r = self.download(client, evidence_id)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, OTP)                                                   # the exact submitted bytes
        self.assertEqual(r.headers["content-type"], TEXT)
        self.assertEqual(r.headers["content-disposition"], f'attachment; filename="trustlens-evidence-{evidence_id}.txt"')
        self.assertEqual(r.headers["cache-control"], "no-store")
        self.assertEqual(client.get(f"/api/v1/evidence/{evidence_id}").json()["content_link"], f"/api/v1/evidence/{evidence_id}/content")
        downloads = [e for e in self.audit_rows(case_id) if e[0] == "EVIDENCE_ACCESSED" and e[5] == {"stage": "CONTENT_DOWNLOAD"}]
        self.assertEqual(len(downloads), 1)
        stranger, _ = self.owner()
        subject, _ = self.provision(roles=("KNOWLEDGE_EDITOR",))
        for who in (stranger, self.admin(), self.client_for(subject)):                     # masked: no implicit admin access
            self.assertEqual(self.download(who, evidence_id).status_code, 404)
        analyst, _ = self.assign_analyst(case_id, content=False)
        self.assertEqual(self.download(analyst, evidence_id).status_code, 403)            # case access alone is insufficient
        granted, _ = self.assign_analyst(case_id, content=True)
        self.assertEqual(self.download(granted, evidence_id).content, OTP)
        self.assertEqual(self.download(client, str(uuid.uuid4())).status_code, 404)
        self.assertEqual(client.get(f"/api/v1/evidence/{evidence_id}/content?inline=1").status_code, 400)
        self.verify_chain()

    def test_unfinished_corrupted_or_unavailable_evidence_is_never_sent(self):
        client, case_id, _, _, evidence_id = self.completed()
        _, pending, _ = self.submit(client, OTP, finalize=False)
        pending_id = self.app_sql("SELECT evidence_item_id::text FROM trustlens.evidence_item WHERE submission_id = %s", (pending,))[0][0]
        self.assertEqual(code(self.download(client, pending_id)), "STATE_CONFLICT")
        locator = self.app_sql("SELECT ecs_locator FROM trustlens.evidence_item WHERE evidence_item_id = %s", (evidence_id,))[0][0]
        path = self.evidence_paths[0] / f"{locator}.tle"
        original = path.read_bytes()
        path.write_bytes(original.replace(b'"ct":"', b'"ct":"AAAA', 1))
        r = self.download(client, evidence_id)
        self.assertEqual((r.status_code, code(r)), (500, "INTEGRITY_FAILURE"))
        self.assertNotIn(b"OTP", r.content)
        self.assertIn(("INTEGRITY_FAILURE", "FAILED", {"stage": "CONTENT_DOWNLOAD"}),
                      [(e[0], e[1], e[5]) for e in self.audit_rows(case_id)])
        path.write_bytes(original)
        self.evidence_store = None                                                         # key/store unavailable: fail closed
        no_store = self.client_for(self.app_sql("SELECT p.external_subject FROM trustlens.principal_reference p JOIN trustlens.case_record c"
                                                " ON c.owner_principal_id = p.principal_reference_id WHERE c.case_record_id = %s",
                                                (case_id,))[0][0])
        self.assertEqual(code(self.download(no_store, evidence_id)), "DEPENDENCY_UNAVAILABLE")
        self.verify_chain()

    # ---- corrections and re-analysis
    def test_a_correction_creates_a_linked_new_evaluation_and_never_changes_the_old_one(self):
        client, case_id, submission_id, evaluation_id, _ = self.completed()
        before = self.stored_result(evaluation_id)
        before_body = self.result(client, evaluation_id).json()
        key = self.new_key()
        r = self.correct(client, evaluation_id, key=key)
        self.assertEqual(r.status_code, 202, r.text)
        body = r.json()
        self.assert_schema(body, "CorrectionAcceptedResponse")
        new = body["new_evaluation"]
        self.assertEqual((body["corrected_evaluation_id"], new["origin"], new["predecessor_evaluation_id"]),
                         (evaluation_id, "USER_CORRECTION", evaluation_id))
        self.assertNotEqual(new["evaluation_id"], evaluation_id)
        self.assertEqual(self.status(client, new["evaluation_id"])["state"], "COMPLETED")
        self.assertEqual(self.stored_result(evaluation_id), before)                       # the corrected result is untouched
        self.assertEqual(self.result(client, evaluation_id).json(), before_body)
        replayed = self.correct(client, evaluation_id, key=key).json()                    # idempotent: same correction
        self.assertEqual((replayed["correction_id"], replayed["new_evaluation"]["evaluation_id"]), (body["correction_id"], new["evaluation_id"]))
        self.assertEqual(code(self.correct(client, evaluation_id, body={"correction_description": "other", "reason_code": "EXTRACTION_ERROR"},
                                           key=key)), "IDEMPOTENCY_KEY_REUSED")
        stored = self.app_sql("SELECT corrected_evaluation_id::text, resulting_evaluation_id::text, correction_description"
                              " FROM trustlens.user_correction WHERE user_correction_id = %s", (body["correction_id"],))
        self.assertEqual(stored, [(evaluation_id, new["evaluation_id"], DESCRIPTION)])
        audit = self.audit_rows(case_id)
        self.assertIn(("USER_CORRECTION", "SUCCEEDED", {"reason": "EXTRACTION_ERROR"}), [(e[0], e[1], e[5]) for e in audit])
        self.assertNotIn("unknown number", json.dumps([str(e) for e in audit]))           # the C4 description is never audited
        artifacts = self.app_sql("SELECT count(DISTINCT governed_input_artifact_id) FROM trustlens.governed_input_artifact"
                                 " WHERE evaluation_id IN (%s, %s)", (evaluation_id, new["evaluation_id"]))
        self.assertEqual(artifacts[0][0], 2)                                               # a new governed artifact each
        listed = client.get(f"/api/v1/cases/{case_id}/evaluations?submission_id={submission_id}").json()["items"]
        self.assertEqual([i["evaluation_id"] for i in listed], [new["evaluation_id"], evaluation_id])  # newest first
        with self.db() as c, c.cursor() as cur, self.assertRaises(psycopg.Error):
            cur.execute("UPDATE trustlens.user_correction SET correction_description = 'x' WHERE user_correction_id = %s",
                        (body["correction_id"],))
        self.verify_chain()

    def test_correction_authorization_state_and_validation(self):
        client, case_id, submission_id, evaluation_id, _ = self.completed()
        stranger, _ = self.owner()
        self.assertEqual(self.correct(stranger, evaluation_id).status_code, 404)
        self.assertEqual(self.correct(self.admin(), evaluation_id).status_code, 404)
        analyst, _ = self.assign_analyst(case_id)
        self.assertEqual(self.correct(analyst, evaluation_id).status_code, 403)            # CASE_OWNER, USER only
        for bad in ({"correction_description": DESCRIPTION}, {"reason_code": "EXTRACTION_ERROR"},
                    {"correction_description": " ", "reason_code": "EXTRACTION_ERROR"},
                    {"correction_description": "x" * 2001, "reason_code": "EXTRACTION_ERROR"},
                    {"correction_description": DESCRIPTION, "reason_code": "lower"},
                    {"correction_description": DESCRIPTION, "reason_code": "EXTRACTION_ERROR", "classification": "NO_SCAM_PATTERN"}):
            with self.subTest(body=list(bad)):
                self.assertEqual(code(self.correct(client, evaluation_id, body=bad)), "INVALID_REQUEST")
        with patch.object(evaluation, "dispatch", lambda runtime, ids: None):
            queued = self.analyze(client, submission_id).json()["evaluations"][0]["evaluation_id"]
        self.assertEqual(code(self.correct(client, queued)), "EVALUATION_NOT_COMPLETED")

    def test_re_analysis_creates_a_distinct_evaluation_with_its_own_provenance(self):
        client, case_id, submission_id, evaluation_id, _ = self.completed()
        before = self.stored_result(evaluation_id)
        r = self.analyze(client, submission_id, body={"predecessor_evaluation_id": evaluation_id, "reason_code": "USER_REQUESTED_REANALYSIS"})
        new = r.json()["evaluations"][0]
        self.assertEqual((new["origin"], new["predecessor_evaluation_id"]), ("RE_EVALUATION", evaluation_id))
        old_view, new_view = self.status(client, evaluation_id), self.status(client, new["evaluation_id"])
        self.assertNotEqual(old_view["provenance"]["evaluation_timestamp"], new_view["provenance"]["evaluation_timestamp"])
        self.assertNotEqual(self.result(client, new["evaluation_id"]).json()["result_digest"], before[0])
        self.assertEqual(self.stored_result(evaluation_id), before)
        self.assertEqual({i["evaluation_id"] for i in client.get(f"/api/v1/cases/{case_id}/evaluations?state=COMPLETED").json()["items"]},
                         {evaluation_id, new["evaluation_id"]})

    # ---- exact replay
    def test_an_assigned_analyst_replays_the_pinned_material_exactly(self):
        client, case_id, _, evaluation_id, _ = self.completed()
        analyst, _ = self.assign_analyst(case_id, content=False)                           # replay needs no content permission
        counts = lambda: self.app_sql("SELECT (SELECT count(*) FROM trustlens.evaluation), (SELECT count(*) FROM trustlens.detection_result)")[0]
        before = counts()
        key = self.new_key()
        r = self.replay(analyst, evaluation_id, key=key)
        self.assertEqual(r.status_code, 202, r.text)
        self.assert_schema(r.json(), "ReplayResponse")
        replay_id = r.json()["replay_id"]
        done = analyst.get(f"/api/v1/replays/{replay_id}").json()
        self.assert_schema(done, "ReplayResponse")
        self.assertEqual((done["state"], done["capability"], done["outcome"], done["replayed_result_digest"]),
                         ("COMPLETED", "REPLAY_CAPABLE", "MATCH", self.stored_result(evaluation_id)[0]))
        self.assertEqual(counts(), before)                                                  # never a new evaluation or result
        self.assertEqual(self.replay(analyst, evaluation_id, key=key).json()["replay_id"], replay_id)   # idempotent
        events = [(e[0], e[5]) for e in self.audit_rows(case_id) if e[0] == "REPLAY_EXECUTED"]
        self.assertEqual(events, [("REPLAY_EXECUTED", {"stage": "REQUESTED"}), ("REPLAY_EXECUTED", {"outcome": "MATCH"})])
        self.verify_chain()

    def test_replay_uses_the_pinned_bundle_even_after_a_new_activation(self):
        client, case_id, _, evaluation_id, _ = self.completed()
        newer = variant(self.store, self.digest, 7)                                         # a different, valid bundle
        self.addCleanup(shutil.rmtree, self.store / newer, True)
        admin = self.admin()
        record = json.loads((self.knowledge_release_dir / f"{self.deployment_ref}.json").read_text())
        record["approved_bundles"].append({"release_record_ref": "TL-KREL-TEST-0002", "content_digest": newer,
                                           "bundle_version": "1.0.0", "manifest_schema_version": "1.1.0"})
        (self.knowledge_release_dir / f"{self.deployment_ref}.json").write_text(json.dumps(record))
        r = admin.post("/api/v1/knowledge/deployment/activate", json={"content_digest": newer, "governance_change_ref": "DEC-011:S6-TEST",
                       "expected_active_content_digest": self.digest}, headers={"Idempotency-Key": self.new_key()})
        self.assertIn(r.status_code, (202, 409), r.text)                                   # activated, or refused as already known
        analyst, _ = self.assign_analyst(case_id)
        replay_id = self.replay(analyst, evaluation_id).json()["replay_id"]
        self.assertEqual(analyst.get(f"/api/v1/replays/{replay_id}").json()["outcome"], "MATCH")
        self.assertEqual(self.status(client, evaluation_id)["provenance"]["bundle_content_digest"], self.digest)

    def test_an_administrator_replays_without_case_access_and_sees_no_content(self):
        client, case_id, _, evaluation_id, _ = self.completed()
        admin = self.admin()
        self.assertEqual(admin.get(f"/api/v1/evaluations/{evaluation_id}").status_code, 404)  # no case access
        replay = self.replay(admin, evaluation_id).json()
        done = admin.get(f"/api/v1/replays/{replay['replay_id']}").json()
        self.assertEqual(done["outcome"], "MATCH")
        self.assertEqual(set(done) - {"missing_material_kinds"}, {"replay_id", "evaluation_id", "state", "capability", "outcome",
                                                                  "replayed_result_digest", "requested_at", "completed_at"})
        self.assertNotIn("OTP", json.dumps(done))

    def test_replay_authorization_and_state(self):
        client, case_id, submission_id, evaluation_id, _ = self.completed()
        stranger_analyst, _ = self.provision(roles=("ANALYST",))
        self.assertEqual(self.replay(self.client_for(stranger_analyst), evaluation_id).status_code, 404)
        self.assertEqual(self.replay(client, evaluation_id).status_code, 403)              # the owner (USER) may not replay
        analyst, _ = self.assign_analyst(case_id)
        replay_id = self.replay(analyst, evaluation_id).json()["replay_id"]
        self.assertEqual(client.get(f"/api/v1/replays/{replay_id}").status_code, 403)
        self.assertEqual(self.client_for(stranger_analyst).get(f"/api/v1/replays/{replay_id}").status_code, 404)
        self.assertEqual(code(self.replay(analyst, evaluation_id, body={"reason_code": "X", "bundle": "latest"})), "INVALID_REQUEST")
        self.assertEqual(code(self.replay(analyst, evaluation_id, body={"note": "x"})), "INVALID_REQUEST")
        with patch.object(evaluation, "dispatch", lambda runtime, ids: None):
            queued = self.analyze(client, submission_id).json()["evaluations"][0]["evaluation_id"]
        self.assertEqual(code(self.replay(analyst, queued)), "EVALUATION_NOT_COMPLETED")
        self.assertEqual(self.replay(analyst, str(uuid.uuid4())).status_code, 404)

    def test_missing_or_failed_material_is_an_explicit_unavailable_outcome(self):
        client, case_id, _, evaluation_id, evidence_id = self.completed()
        analyst, _ = self.assign_analyst(case_id)
        runtime = analyst.app.state.auth
        empty = Path(tempfile.mkdtemp(dir=self.tmp.name))
        with patch.object(runtime, "knowledge_verifier", KnowledgeVerifier(empty)):        # the pinned bundle is gone
            replay_id = self.replay(analyst, evaluation_id).json()["replay_id"]
        done = analyst.get(f"/api/v1/replays/{replay_id}").json()
        self.assertEqual((done["capability"], done["outcome"], done["missing_material_kinds"], done["replayed_result_digest"]),
                         ("REPLAY_UNAVAILABLE_BUNDLE_MISSING", "FAILED_BUNDLE_UNAVAILABLE", ["KNOWLEDGE_BUNDLE"], None))
        locator = self.app_sql("SELECT ecs_locator FROM trustlens.evidence_item WHERE evidence_item_id = %s", (evidence_id,))[0][0]
        path = self.evidence_paths[0] / f"{locator}.tle"
        moved = path.with_suffix(".gone")
        path.rename(moved)
        done = analyst.get(f"/api/v1/replays/{self.replay(analyst, evaluation_id).json()['replay_id']}").json()
        self.assertEqual((done["capability"], done["outcome"], done["missing_material_kinds"]),
                         ("REPLAY_UNAVAILABLE_REQUIRED_ARTIFACT_MISSING", "FAILED_MISSING_MATERIAL", ["EVIDENCE_BYTES"]))
        moved.rename(path)
        self.owner_sql("ALTER TABLE trustlens.governed_input_artifact DISABLE TRIGGER tr_governed_input_artifact_immutable")
        try:
            self.owner_sql("UPDATE trustlens.governed_input_artifact SET artifact_canonical_json = replace(artifact_canonical_json,"
                           " 'CREDENTIAL_REQUEST_OTP', 'URGENCY') WHERE evaluation_id = %s", (evaluation_id,))
        finally:
            self.owner_sql("ALTER TABLE trustlens.governed_input_artifact ENABLE TRIGGER tr_governed_input_artifact_immutable")
        done = analyst.get(f"/api/v1/replays/{self.replay(analyst, evaluation_id).json()['replay_id']}").json()
        self.assertEqual((done["capability"], done["outcome"], done["missing_material_kinds"]),
                         ("REPLAY_UNAVAILABLE_INTEGRITY_FAILED", "FAILED_INTEGRITY", ["GOVERNED_INPUT_ARTIFACT"]))
        self.assertEqual(self.result(client, evaluation_id).json()["classification"], "SCAM_PATTERN_DETECTED")  # result unchanged
        self.verify_chain()

    # ---- Codex S6 findings 1 and 2: whole-material commitment, manifest states and the INTEGRITY_FAILURE audit
    def replay_done(self, analyst, evaluation_id):
        return analyst.get(f"/api/v1/replays/{self.replay(analyst, evaluation_id).json()['replay_id']}").json()

    def integrity_events(self, case_id):
        return [e for e in self.audit_rows(case_id) if e[0] == "INTEGRITY_FAILURE" and e[3] == "REPLAY"]

    def test_a_corrupted_whole_material_commitment_is_an_integrity_failure_never_a_match(self):
        client, case_id, _, evaluation_id, _ = self.completed()
        analyst, _ = self.assign_analyst(case_id)
        self.assertEqual(self.replay_done(analyst, evaluation_id)["outcome"], "MATCH")       # the §9 commitment verifies
        self.owner_sql("ALTER TABLE trustlens.evaluation DISABLE TRIGGER tr_evaluation_transition_guard")
        try:
            self.owner_sql("UPDATE trustlens.evaluation SET replay_material_digest = repeat('0', 64) WHERE evaluation_id = %s",
                           (evaluation_id,))
        finally:
            self.owner_sql("ALTER TABLE trustlens.evaluation ENABLE TRIGGER tr_evaluation_transition_guard")
        done = self.replay_done(analyst, evaluation_id)
        self.assertEqual((done["capability"], done["outcome"], done["missing_material_kinds"], done["replayed_result_digest"]),
                         ("REPLAY_UNAVAILABLE_INTEGRITY_FAILED", "FAILED_INTEGRITY", ["EVALUATION_PINS"], None))
        events = self.integrity_events(case_id)
        self.assertEqual([(e[1], e[4], e[5]) for e in events], [("FAILED", done["replay_id"], {"stage": "REPLAY_VERIFICATION"})])
        self.assertEqual(self.result(client, evaluation_id).json()["classification"], "SCAM_PATTERN_DETECTED")
        self.verify_chain()

    def test_a_commitment_covers_the_evidence_and_envelope_digests(self):
        client, case_id, _, evaluation_id, evidence_id = self.completed()
        record = self.app_sql("SELECT replay_material_digest FROM trustlens.evaluation WHERE evaluation_id = %s", (evaluation_id,))[0][0]
        with self.db() as c, c.cursor() as cur:
            committed = evaluation.material_record(cur, evaluation_id, self.stored_result(evaluation_id)[0])
        self.assertEqual(evaluation.material_digest(committed), record)
        self.assertEqual(sorted(committed), sorted(["material_set", "RM-01", "RM-02", "RM-03", "RM-04", "RM-05", "RM-06", "RM-07",
                                                    "RM-08", "RM-09", "RM-10", "RM-11", "RM-13", "RM-14"]))
        self.assertEqual(committed["RM-11"], [{"evidence_item_id": evidence_id, "content_sha256": hashlib.sha256(OTP).hexdigest(),
                                               "byte_length": len(OTP)}])

    def test_integrity_failed_or_quarantined_manifests_are_never_replay_capable(self):
        client, case_id, _, evaluation_id, evidence_id = self.completed()
        analyst, _ = self.assign_analyst(case_id)
        for state in ("INTEGRITY_FAILED", "QUARANTINED"):                                   # the §11 transitions, in order
            with self.subTest(state=state):
                self.app_sql("UPDATE trustlens.evidence_item SET content_state = %s, state_changed_at = now() WHERE evidence_item_id = %s",
                             (state, evidence_id))
                done = self.replay_done(analyst, evaluation_id)
                self.assertEqual((done["capability"], done["outcome"], done["missing_material_kinds"]),
                                 ("REPLAY_UNAVAILABLE_REQUIRED_ARTIFACT_MISSING", "FAILED_MISSING_MATERIAL", ["EVIDENCE_MANIFEST"]))

    def test_corrupted_encrypted_evidence_fails_integrity_with_its_audit_event_atomically(self):
        client, case_id, _, evaluation_id, evidence_id = self.completed()
        analyst, _ = self.assign_analyst(case_id)
        locator = self.app_sql("SELECT ecs_locator FROM trustlens.evidence_item WHERE evidence_item_id = %s", (evidence_id,))[0][0]
        path = self.evidence_paths[0] / f"{locator}.tle"
        path.write_bytes(path.read_bytes().replace(b'"ct":"', b'"ct":"AAAA', 1))
        runtime = analyst.app.state.auth
        real_audit = history.ev._audit

        def failing(cur, event_type, *args, **kwargs):
            if event_type == "INTEGRITY_FAILURE":
                raise history.AuditUnavailable("audit unavailable")
            return real_audit(cur, event_type, *args, **kwargs)

        with patch.object(history.ev, "_audit", failing):                                   # audit write fails: nothing final
            replay_id = self.replay(analyst, evaluation_id).json()["replay_id"]
        pending = analyst.get(f"/api/v1/replays/{replay_id}").json()
        self.assertEqual((pending["state"], pending["outcome"]), ("PENDING", None))
        self.assertEqual(self.integrity_events(case_id), [])
        barrier = threading.Barrier(3)

        def worker():
            barrier.wait()
            history.run_replay(runtime, replay_id)

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        done = analyst.get(f"/api/v1/replays/{replay_id}").json()
        self.assertEqual((done["capability"], done["outcome"], done["missing_material_kinds"]),
                         ("REPLAY_UNAVAILABLE_INTEGRITY_FAILED", "FAILED_INTEGRITY", ["EVIDENCE_BYTES"]))
        self.assertEqual(len(self.integrity_events(case_id)), 1)                           # once, with the one outcome
        self.assertEqual(len([e for e in self.audit_rows(case_id) if e[0] == "REPLAY_EXECUTED" and e[5] == {"outcome": "FAILED_INTEGRITY"}]), 1)
        self.assertNotIn(locator, json.dumps([str(e) for e in self.audit_rows(case_id)]))  # no locator in audit
        self.verify_chain()

    def test_twenty_one_evaluations_page_with_the_cursor_without_duplicates(self):
        self.activate_exact_bundle()
        client, _ = self.owner()
        case_id, submission_id, _ = self.submit(client, OTP)
        with patch.object(evaluation, "dispatch", lambda runtime, ids: None):
            created = [self.analyze(client, submission_id).json()["evaluations"][0]["evaluation_id"] for _ in range(21)]
        base = f"/api/v1/cases/{case_id}/evaluations?submission_id={submission_id}&limit=20"
        first = client.get(base).json()
        second = client.get(base + f"&cursor={first['page']['next_cursor']}").json()
        ids = [i["evaluation_id"] for i in first["items"] + second["items"]]
        self.assertEqual((len(first["items"]), len(second["items"]), second["page"].get("next_cursor")), (20, 1, None))
        self.assertEqual(sorted(ids), sorted(created))
        self.assertEqual(len(set(ids)), 21)
        stamps = [i["requested_at"] for i in first["items"] + second["items"]]
        self.assertEqual(stamps, sorted(stamps, reverse=True))                             # server order kept across pages

    def test_a_crashed_replay_completes_once_after_recovery_and_concurrent_runs_record_once(self):
        client, case_id, _, evaluation_id, _ = self.completed()
        analyst, _ = self.assign_analyst(case_id)
        with patch.object(history, "run_replay", lambda runtime, replay_id: None):          # the process dies after 202
            replay_id = self.replay(analyst, evaluation_id).json()["replay_id"]
        self.assertEqual(analyst.get(f"/api/v1/replays/{replay_id}").json()["state"], "PENDING")
        runtime = analyst.app.state.auth
        barrier = threading.Barrier(3)

        def worker():
            barrier.wait()
            history.run_replay(runtime, replay_id)

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(analyst.get(f"/api/v1/replays/{replay_id}").json()["outcome"], "MATCH")
        outcomes = [e for e in self.audit_rows(case_id) if e[0] == "REPLAY_EXECUTED" and e[5] == {"outcome": "MATCH"}]
        self.assertEqual(len(outcomes), 1)
        with patch.object(history, "run_replay", lambda runtime, replay_id: None):
            pending = self.replay(analyst, evaluation_id).json()["replay_id"]
        self.assertIn(pending, evaluation.recover(runtime)["replays"])                     # restart recovery
        self.assertEqual(analyst.get(f"/api/v1/replays/{pending}").json()["state"], "COMPLETED")
        with self.db() as c, c.cursor() as cur, self.assertRaises(psycopg.Error):
            cur.execute("UPDATE trustlens.replay_execution SET outcome = 'MISMATCH', replay_capability_state = 'REPLAY_CAPABLE',"
                        " completed_at = now() WHERE replay_execution_id = %s", (replay_id,))

    def test_history_survives_a_backend_restart(self):
        client, case_id, _, evaluation_id, evidence_id = self.completed()
        corrected = self.correct(client, evaluation_id).json()["new_evaluation"]["evaluation_id"]
        analyst, _ = self.assign_analyst(case_id)
        replay_id = self.replay(analyst, evaluation_id).json()["replay_id"]
        subject = self.app_sql("SELECT p.external_subject FROM trustlens.principal_reference p JOIN trustlens.case_record c"
                               " ON c.owner_principal_id = p.principal_reference_id WHERE c.case_record_id = %s", (case_id,))[0][0]
        before = (self.result(client, evaluation_id).json(), self.result(client, corrected).json())
        self.evidence_store = LocalEncryptedContentStore(*self.evidence_paths)            # a new process, same stores
        self.knowledge_verifier = KnowledgeVerifier(self.store)
        restarted = self.client_for(subject)
        self.assertEqual((self.result(restarted, evaluation_id).json(), self.result(restarted, corrected).json()), before)
        self.assertEqual(self.download(restarted, evidence_id).content, OTP)
        self.assertEqual(len(restarted.get(f"/api/v1/cases/{case_id}/evaluations").json()["items"]), 2)
        self.assertEqual(analyst.get(f"/api/v1/replays/{replay_id}").json()["outcome"], "MATCH")
        self.verify_chain()


if __name__ == "__main__":
    unittest.main()
