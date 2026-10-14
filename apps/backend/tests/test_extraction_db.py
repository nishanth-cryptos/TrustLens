"""S4 live path against a DISPOSABLE PostgreSQL: finalized evidence -> authorized, audited, digest-verified read ->
deterministic governed inputs, pinned to the exact bundle activated through the accepted API. Synthetic data only."""
import dataclasses
import hashlib
import json
import os
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from db_harness import DISPOSABLE, DbHarness
from knowledge.publish.build_bundle import build
from trustlens_backend.content_store import LocalEncryptedContentStore
from trustlens_backend.extraction import ExtractionRefused, ExtractionUnavailable, extract_finalized_evidence
from trustlens_backend.knowledge_seam import KnowledgeVerifier

ROOT = Path(__file__).resolve().parents[3]
APPROVED = json.loads((ROOT / "apps/backend/knowledge_releases/local-development.json").read_text())["approved_bundles"][0]
TEXT = "text/plain; charset=utf-8"
LIVE = "SYNTHETIC TEST: Example Bank: unusual activity. Share the OTP you just received with our officer now.".encode()


@unittest.skipUnless(DISPOSABLE, "needs an explicitly disposable PostgreSQL")
class ExtractionFromEvidenceTests(DbHarness, unittest.TestCase):
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
        self.store_root = root
        self.evidence_store = LocalEncryptedContentStore(root, kek)
        self.knowledge_verifier = KnowledgeVerifier(self.store)
        self.knowledge_release_dir = work
        self.deployment_ref = f"test-{uuid.uuid4().hex[:12]}"
        self.owner_sql("INSERT INTO trustlens.knowledge_deployment_state (knowledge_deployment_state_id, deployment_ref,"
                       " operational_state, state_changed_at) VALUES (gen_random_uuid(), %s, 'NO_ACTIVE_BUNDLE', now())",
                       (self.deployment_ref,))

    # ---- helpers
    def owner_sql(self, sql, args=()):
        import psycopg
        with psycopg.connect(**self._owner_settings().connection_parameters(), autocommit=True) as c, c.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall() if cur.description else None

    def activate_exact_bundle(self):
        """The approved digest, activated through the accepted ADMINISTRATOR API (DEC-011, DEC-012 local exception)."""
        record = {"release_record_schema_version": "1.0", "deployment_ref": self.deployment_ref,
                  "profile": "SINGLE_MACHINE_SYNTHETIC_DEVELOPMENT",
                  "authenticity_policy": {"decision": "DEC-012", "outcome": "NOT_REQUIRED_BY_POLICY", "scope": "test"},
                  "approved_bundles": [{"release_record_ref": "TL-KREL-TEST-0001", "content_digest": self.digest,
                                        "bundle_version": "1.0.0", "manifest_schema_version": "1.1.0"}]}
        (self.knowledge_release_dir / f"{self.deployment_ref}.json").write_text(json.dumps(record))
        subject, _ = self.provision(roles=("ADMINISTRATOR",))
        r = self.client_for(subject).post("/api/v1/knowledge/deployment/activate",
                                          json={"content_digest": self.digest, "governance_change_ref": "DEC-011:S4-TEST",
                                                "expected_active_content_digest": None},
                                          headers={"Idempotency-Key": self.new_key()})
        self.assertEqual(r.status_code, 202, r.text)

    def owner_upload(self, data=LIVE, input_type="SMS", relationship="RECEIVED", finalize=True):
        subject, pid = self.provision()
        client = self.client_for(subject)
        case_id = self.create_case(client).json()["case_id"]
        body = {"declared_input_type": input_type, **({"relationship_to_content": relationship} if relationship else {})}
        submission_id = self.create_submission(client, case_id, body=body).json()["submission_id"]
        evidence_id = client.post(f"/api/v1/submissions/{submission_id}/evidence", headers={"Idempotency-Key": self.new_key()},
                                  json={"artifact_kind": "TEXT_BODY", "declared_media_type": TEXT,
                                        "declared_byte_length": len(data)}).json()["evidence_id"]
        self.assertEqual(client.put(f"/api/v1/evidence/{evidence_id}/content", content=data,
                                    headers={"Content-Type": TEXT}).status_code, 200)
        if finalize:
            self.assertEqual(client.post(f"/api/v1/evidence/{evidence_id}/finalize", json={},
                                         headers={"Idempotency-Key": self.new_key()}).status_code, 202)
        runtime = client.app.state.auth
        return runtime, runtime.principals.get_active(pid), case_id, evidence_id

    def accesses(self, case_id):
        return [r for r in self.audit_rows(case_id) if r[0] in ("EVIDENCE_ACCESSED", "INTEGRITY_FAILURE", "AUTHORIZATION_DENIED")]

    # ---- the live path
    def test_finalized_bytes_become_pinned_governed_inputs_with_an_audited_read(self):
        self.assertEqual(self.digest, APPROVED["content_digest"])                       # the exact approved bundle
        self.activate_exact_bundle()
        runtime, principal, case_id, evidence_id = self.owner_upload()
        g = extract_finalized_evidence(runtime, principal, evidence_id, correlation_id=str(uuid.uuid4()))
        self.assertEqual((g.input_support_status, g.positive_signals()),
                         ("SUPPORTED", ("AUTHORITY_IMPERSONATION_BANK", "CREDENTIAL_REQUEST_OTP")))
        self.assertEqual(g.knowledge_content_digest, APPROVED["content_digest"])
        self.assertEqual(g.input_id, f"TL-INPUT:{evidence_id}")
        self.assertEqual(dict(g.source), {"evidence_id": evidence_id, "submission_id": g.source["submission_id"],
                                          "content_sha256": hashlib.sha256(LIVE).hexdigest(), "byte_length": len(LIVE)})
        content = g.envelope["content"]
        self.assertEqual(content["raw_text"].encode(), LIVE)                             # the submitted bytes, not a fixture
        self.assertEqual((g.envelope["input_type"], g.envelope["provenance"]["received_via"], g.envelope["provenance"]["synthetic"],
                          g.envelope["user_supplied_context"]["relationship_to_content"]), ("SMS", "USER_SUBMISSION", True, "RECEIVED"))
        self.assertTrue(all(o["source_input_id"] == g.input_id for o in g.observations))
        rows = self.accesses(case_id)
        self.assertEqual([(r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows],
                         [("EVIDENCE_ACCESSED", "SUCCEEDED", principal.principal_reference_id, "EVIDENCE_ITEM", evidence_id,
                           {"stage": "DETERMINISTIC_EXTRACTION"})])
        again = extract_finalized_evidence(runtime, principal, evidence_id, correlation_id=str(uuid.uuid4()))
        self.assertEqual(json.dumps(again.engine_inputs(), sort_keys=True), json.dumps(g.engine_inputs(), sort_keys=True))
        self.assertEqual(len(self.accesses(case_id)), 2)                                 # every read is audited
        self.verify_chain()

    def test_narrative_and_unsupported_submissions_stay_explicit(self):
        self.activate_exact_bundle()
        runtime, principal, _, evidence_id = self.owner_upload(
            b"SYNTHETIC TEST: The caller told me to install AnyDesk and share the OTP. Is this a scam?", "USER_NARRATIVE",
            "REPORTING_ON_BEHALF")
        g = extract_finalized_evidence(runtime, principal, evidence_id, correlation_id=str(uuid.uuid4()))
        self.assertEqual((g.positive_signals(), g.negative_signals()), ((), ("REPORTED_SCAM_NARRATIVE",)))
        runtime, principal, _, evidence_id = self.owner_upload("SYNTHETIC: अपना OTP शेयर करें".encode())
        g = extract_finalized_evidence(runtime, principal, evidence_id, correlation_id=str(uuid.uuid4()))
        self.assertEqual((g.input_support_status, g.indicator_observations), ("UNSUPPORTED", ()))

    # ---- authorization and state
    def test_resource_authorization_is_preserved_and_masked(self):
        self.activate_exact_bundle()
        runtime, principal, case_id, evidence_id = self.owner_upload()
        _, stranger, _, _ = self.owner_upload()
        for who, item in ((stranger, evidence_id), (principal, str(uuid.uuid4())), (principal, "not-a-uuid")):
            with self.subTest(item=item[:8]), self.assertRaisesRegex(ExtractionRefused, "NOT_FOUND"):
                extract_finalized_evidence(runtime, who, item, correlation_id=str(uuid.uuid4()))
        with self.assertRaisesRegex(ExtractionRefused, "FORBIDDEN"):
            extract_finalized_evidence(runtime, dataclasses.replace(principal, roles=("KNOWLEDGE_EDITOR",)), evidence_id,
                                       correlation_id=str(uuid.uuid4()))
        rows = self.accesses(case_id)
        self.assertEqual([(r[0], r[5]["reason"]) for r in rows],
                         [("AUTHORIZATION_DENIED", "ROLE_OWNERSHIP_OR_CONTENT_PERMISSION_REQUIRED")])  # no content was read
        runtime, principal, _, pending = self.owner_upload(finalize=False)
        with self.assertRaisesRegex(ExtractionRefused, "EVIDENCE_NOT_FINALIZED"):
            extract_finalized_evidence(runtime, principal, pending, correlation_id=str(uuid.uuid4()))

    def test_unavailable_knowledge_store_or_integrity_is_explicit_never_benign(self):
        runtime, principal, case_id, evidence_id = self.owner_upload()
        with self.assertRaisesRegex(ExtractionUnavailable, "NO_ACTIVE_BUNDLE"):          # nothing activated yet
            extract_finalized_evidence(runtime, principal, evidence_id, correlation_id=str(uuid.uuid4()))
        self.activate_exact_bundle()
        unconfigured = dataclasses.replace(runtime, knowledge_verifier=None)
        with self.assertRaisesRegex(ExtractionUnavailable, "KNOWLEDGE_STORE_UNCONFIGURED"):
            extract_finalized_evidence(unconfigured, principal, evidence_id, correlation_id=str(uuid.uuid4()))
        no_store = dataclasses.replace(runtime, evidence_store=None, evidence_store_paths=None)
        with self.assertRaisesRegex(ExtractionUnavailable, "CONTENT_STORE_UNAVAILABLE"):
            extract_finalized_evidence(no_store, principal, evidence_id, correlation_id=str(uuid.uuid4()))
        self.assertEqual(self.accesses(case_id), [])
        locator = self.owner_sql("SELECT ecs_locator FROM trustlens.evidence_item WHERE evidence_item_id = %s", (evidence_id,))[0][0]
        path = self.store_root / f"{locator}.tle"
        path.write_bytes(path.read_bytes().replace(b'"ct":"', b'"ct":"AAAA', 1))
        with self.assertRaisesRegex(ExtractionUnavailable, "INTEGRITY_FAILURE"):
            extract_finalized_evidence(runtime, principal, evidence_id, correlation_id=str(uuid.uuid4()))
        self.assertEqual([(r[0], r[1], r[5]) for r in self.accesses(case_id)],
                         [("INTEGRITY_FAILURE", "FAILED", {"stage": "EXTRACTION_READ"})])
        self.verify_chain()


if __name__ == "__main__":
    unittest.main()
