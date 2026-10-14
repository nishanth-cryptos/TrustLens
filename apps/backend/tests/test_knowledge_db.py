"""S3 governed knowledge seam against a DISPOSABLE PostgreSQL (migration 0005) and temporary bundle stores.

Activation is exercised through the accepted API (`activateKnowledgeBundle`, DEC-011) and the operator CLI. The
readiness tests also use `activate()`, which writes rows as the schema owner to set up states the API must refuse to
create (e.g. a REJECTED record pointed at by the deployment). That helper is TEST-ONLY, never an application path.
"""
import hashlib
import json
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import psycopg
from fastapi.testclient import TestClient

import test_auth as T
from db_harness import CATALOG, DISPOSABLE, DbHarness
from knowledge.publish.build_bundle import build
from knowledge.runtime.loader import _canonical_content_digest
from trustlens_backend import knowledge_cli, knowledge_seam
from trustlens_backend.content_store import LocalEncryptedContentStore
from trustlens_backend.knowledge_seam import KnowledgeVerifier, evaluation_readiness
from trustlens_backend.main import probe_ready

KNOWLEDGE_READERS = ("ANALYST", "KNOWLEDGE_EDITOR", "KNOWLEDGE_APPROVER", "ADMINISTRATOR")


def variant(store: Path, base: str, indent: int) -> str:
    """A distinct, VALID bundle: one member re-serialized with different JSON whitespace, manifest rebuilt."""
    work = store / f"variant-{indent}"
    shutil.copytree(store / base, work)
    manifest = json.loads((work / "bundle-manifest.json").read_text())
    entry = next(f for f in manifest["integrity"]["files"] if f["path"].startswith("rules/"))
    member = work / entry["path"]
    data = json.dumps(json.loads(member.read_text()), indent=indent).encode("utf-8")
    member.write_bytes(data)
    entry.update(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
    manifest["content_digest"] = _canonical_content_digest(manifest["integrity"]["files"])
    (work / "bundle-manifest.json").write_text(json.dumps(manifest, indent=2))
    work.rename(store / manifest["content_digest"])
    return manifest["content_digest"]


@unittest.skipUnless(DISPOSABLE, "needs an explicitly disposable PostgreSQL")
class KnowledgeSeamTests(DbHarness, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.store = Path(cls.tmp.name) / "knowledge"
        staging = cls.store / "staging"
        cls.base = build(staging, gate="PASS")["content_digest"]        # governed publication: the gate passed
        staging.rename(cls.store / cls.base)
        cls.indent = 3

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.deployment_ref = f"test-{uuid.uuid4().hex[:12]}"          # each test owns its deployment state row
        self.knowledge_verifier = KnowledgeVerifier(self.store)
        self.knowledge_release_dir = Path(tempfile.mkdtemp(dir=self.tmp.name))
        self.approved = []
        self.owner("INSERT INTO trustlens.knowledge_deployment_state (knowledge_deployment_state_id, deployment_ref,"
                   " operational_state, state_changed_at) VALUES (gen_random_uuid(), %s, 'NO_ACTIVE_BUNDLE', now())",
                   (self.deployment_ref,))

    # ---- helpers
    def owner(self, sql, args=()):
        with psycopg.connect(**self._owner_settings().connection_parameters(), autocommit=True) as c, c.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall() if cur.description else None

    def fresh_bundle(self) -> str:
        """A valid bundle whose digest this database has never recorded (reruns on the same database stay isolated)."""
        while True:
            type(self).indent += 1
            digest = variant(self.store, self.base, self.indent)
            if not self.owner("SELECT 1 FROM trustlens.knowledge_bundle_reference WHERE content_digest = %s UNION ALL"
                              " SELECT 1 FROM trustlens.audit_event WHERE safe_metadata->>'content_digest' = %s", (digest, digest)):
                return digest

    def reference(self, digest, eligibility="ELIGIBLE", version="1.0.0", manifest_version="1.1.0"):
        self.owner("INSERT INTO trustlens.knowledge_bundle_reference (knowledge_bundle_reference_id, content_digest, bundle_version,"
                   " manifest_schema_version, commit_sha, component_versions, release_record_ref, governance_eligibility,"
                   " eligibility_observed_at, eligibility_source_ref, first_seen_at) VALUES (gen_random_uuid(), %s, %s, %s,"
                   " 'unknown', '{\"rules\": \"1.0.0\"}', NULL, %s, now(), 'TEST-FIXTURE', now())",
                   (digest, version, manifest_version, eligibility))

    def activate(self, digest, lifecycle="ACTIVE", outcome="SUCCEEDED", state="ACTIVE"):
        """TEST-ONLY stand-in for the governed activation operation (not implemented before T07)."""
        _, admin = self.provision(roles=("ADMINISTRATOR",))
        record = str(uuid.uuid4())
        self.owner("INSERT INTO trustlens.knowledge_activation_record (knowledge_activation_record_id, deployment_ref,"
                   " bundle_content_digest, previous_bundle_content_digest, action_kind, lifecycle_state, validation_outcome,"
                   " authenticity_outcome, actor_principal_id, reason_ref, outcome, recorded_at) VALUES (%s, %s, %s, NULL,"
                   " 'ACTIVATION', %s, 'PASSED', 'NOT_REQUIRED_BY_POLICY', %s, 'TEST-FIXTURE', %s, now())",
                   (record, self.deployment_ref, digest, lifecycle, admin, outcome))
        self.owner("UPDATE trustlens.knowledge_deployment_state SET operational_state = %s, active_bundle_content_digest = %s,"
                   " current_activation_record_id = %s, state_changed_at = now() WHERE deployment_ref = %s",
                   (state, digest, record, self.deployment_ref))
        return record

    def readiness(self):
        with self.db() as c, c.cursor() as cur:
            return evaluation_readiness(cur, self.knowledge_verifier, self.deployment_ref)

    def reader(self, role="ANALYST"):
        subject, _ = self.provision(roles=(role,))
        return self.client_for(subject)

    # ---- contract parity
    def test_operations_match_the_catalog(self):
        ops = {o["operation_id"]: o for o in CATALOG["operations"]}
        for op_id, spec in knowledge_seam.OPERATIONS.items():
            o = ops[op_id]
            self.assertEqual((spec["method"], spec["path"], list(spec["roles"]), spec["resource_authorization"]),
                             (o["method"], o["path"], o["roles"], o["resource_authorization"]), op_id)

    # ---- the honest initial state
    def test_a_fresh_deployment_reports_no_active_bundle_and_is_not_ready(self):
        body = self.reader().get("/api/v1/knowledge/active").json()
        self.assert_schema(body, "KnowledgeActiveResponse")
        self.assertEqual((body["deployment_state"], body["active_bundle"]), ("NO_ACTIVE_BUNDLE", None))
        self.assertTrue(body["state_changed_at"].endswith("Z"))
        history = self.reader("KNOWLEDGE_EDITOR").get("/api/v1/knowledge/activations")      # deployment-wide history
        self.assertEqual(history.status_code, 200)
        self.assertEqual(set(history.json()), {"items", "page"})
        self.assertEqual(self.readiness().reason, "NO_ACTIVE_BUNDLE")
        self.deployment_ref = "local-development"                          # the row migration 0005 seeds
        self.assertEqual(self.readiness().reason, "NO_ACTIVE_BUNDLE")

    def test_role_boundaries_follow_the_catalog(self):
        user = self.client_for(self.provision()[0])
        for path in ("/api/v1/knowledge/active", f"/api/v1/knowledge/bundles/{'0' * 64}", "/api/v1/knowledge/activations"):
            self.assertEqual(user.get(path).status_code, 403, path)        # USER holds no knowledge-read role
        self.assertEqual(self.reader("ANALYST").get("/api/v1/knowledge/activations").status_code, 403)
        for role in KNOWLEDGE_READERS:
            self.assertEqual(self.reader(role).get("/api/v1/knowledge/active").status_code, 200, role)
        with TestClient(self.reader().app, base_url=T.BACKEND) as anonymous:
            self.assertEqual(anonymous.get("/api/v1/knowledge/active").status_code, 401)
        admin = self.reader("ADMINISTRATOR")
        for path in ("/api/v1/knowledge/deployment/rollback", f"/api/v1/knowledge/bundles/{'0' * 64}/withdrawal"):
            self.assertIn(admin.post(path, json={}, headers={"Idempotency-Key": self.new_key()}).status_code, (404, 405))

    def test_bundle_lookup_by_exact_digest_only(self):
        digest = self.fresh_bundle()
        self.reference(digest)
        reader = self.reader()
        body = reader.get(f"/api/v1/knowledge/bundles/{digest}").json()
        self.assert_schema(body, "KnowledgeBundleResponse")
        self.assertEqual((body["content_digest"], body["governance_eligibility"]), (digest, "ELIGIBLE"))
        self.assertEqual(reader.get(f"/api/v1/knowledge/bundles/{'e' * 64}").status_code, 404)
        for bad in ("latest", digest.upper(), digest[:40]):
            self.assertEqual(reader.get(f"/api/v1/knowledge/bundles/{bad}").status_code, 400, bad)

    # ---- READY only for an exact, eligible, verified, successfully activated bundle
    def test_an_activated_eligible_verified_bundle_is_ready_and_pinned(self):
        digest = self.fresh_bundle()
        self.reference(digest)
        record = self.activate(digest)
        ready = self.readiness()
        self.assertEqual((ready.ready, ready.reason, ready.content_digest), (True, "READY", digest))
        self.assertEqual(ready.knowledge.content_digest, digest)
        body = self.reader().get("/api/v1/knowledge/active").json()
        self.assertEqual((body["deployment_state"], body["active_bundle"]["content_digest"]), ("ACTIVE", digest))
        history = self.reader("KNOWLEDGE_APPROVER").get("/api/v1/knowledge/activations").json()["items"]
        self.assertIn(record, [h["activation_id"] for h in history])
        self.assert_schema(history[0], "KnowledgeActivationResponse")
        filtered = self.reader("ADMINISTRATOR").get("/api/v1/knowledge/activations?outcome=FAILED").json()["items"]
        self.assertNotIn(record, [h["activation_id"] for h in filtered])

    def test_withdrawal_or_unknown_eligibility_blocks_new_evaluation(self):
        digest = self.fresh_bundle()
        self.reference(digest)
        self.activate(digest)
        self.owner("UPDATE trustlens.knowledge_bundle_reference SET governance_eligibility = 'WITHDRAWN', eligibility_observed_at = now()"
                   " WHERE content_digest = %s", (digest,))
        self.assertEqual(self.readiness().reason, "BUNDLE_WITHDRAWN")    # digest-valid is not enough (ADR-0013 §13)
        self.owner("UPDATE trustlens.knowledge_bundle_reference SET governance_eligibility = 'UNKNOWN' WHERE content_digest = %s", (digest,))
        self.assertEqual(self.readiness().reason, "ELIGIBILITY_UNKNOWN")
        self.owner("UPDATE trustlens.knowledge_deployment_state SET operational_state = 'ACTIVE_BUNDLE_WITHDRAWN' WHERE deployment_ref = %s",
                   (self.deployment_ref,))
        self.assertEqual(self.readiness().reason, "ACTIVE_BUNDLE_WITHDRAWN")
        self.assertEqual(self.reader().get("/api/v1/knowledge/active").json()["deployment_state"], "ACTIVE_BUNDLE_WITHDRAWN")

    def test_missing_tampered_or_mismatched_bundles_block_new_evaluation(self):
        missing = hashlib.sha256(uuid.uuid4().bytes).hexdigest()           # registered, but no bundle on disk
        self.reference(missing)
        self.activate(missing)
        self.assertEqual(self.readiness().reason, "BUNDLE_MISSING")
        tampered = self.fresh_bundle()
        rule = next((self.store / tampered / "rules").glob("*.json"))
        rule.write_bytes(rule.read_bytes() + b" ")
        self.reference(tampered)
        self.activate(tampered)
        self.assertEqual(self.readiness().reason, "BUNDLE_TAMPERED")
        mismatched = self.fresh_bundle()
        self.reference(mismatched, version="9.9.9")
        self.activate(mismatched)
        self.assertEqual(self.readiness().reason, "BUNDLE_REFERENCE_MISMATCH")
        rejected = self.fresh_bundle()
        self.reference(rejected)
        self.activate(rejected, lifecycle="REJECTED", outcome="FAILED")
        self.assertEqual(self.readiness().reason, "ACTIVATION_RECORD_INCONSISTENT")
        self.knowledge_verifier = None
        self.assertEqual(self.readiness().reason, "ACTIVATION_RECORD_INCONSISTENT")

    def test_the_probe_is_ok_only_with_every_required_dependency(self):
        digest = self.fresh_bundle()
        self.approve(digest)
        self.assertEqual(self.activate_api(self.reader("ADMINISTRATOR"), digest).status_code, 202)   # the real operation
        tmp = Path(self.tmp.name) / f"evidence-{uuid.uuid4().hex[:6]}"
        tmp.mkdir(mode=0o700)
        kek = tmp.parent / f"{tmp.name}.key"
        kek.write_bytes(b"k" * 32)
        kek.chmod(0o600)
        runtime = self.reader().app.state.auth
        self.assertFalse(probe_ready(runtime))                            # no evidence store configured
        runtime.evidence_store = LocalEncryptedContentStore(tmp, kek)
        self.assertTrue(probe_ready(runtime))
        runtime.knowledge_verifier = None
        self.assertFalse(probe_ready(runtime))
        runtime.knowledge_verifier, runtime.deployment_ref = self.knowledge_verifier, "local-development"
        self.assertFalse(probe_ready(runtime))                            # that deployment has no active bundle
        with TestClient(self.reader().app, base_url=T.BACKEND) as probe:
            self.assertEqual(probe.get("/health/ready").json(), {"status": "NOT_READY"})

    # ---- recorded identities are preserved; the application cannot write
    def test_recorded_identities_are_immutable_and_the_application_role_is_read_only(self):
        digest = self.fresh_bundle()
        self.reference(digest)
        record = self.activate(digest)
        for sql, args in (("UPDATE trustlens.knowledge_bundle_reference SET content_digest = %s WHERE content_digest = %s", ("b" * 64, digest)),
                          ("UPDATE trustlens.knowledge_bundle_reference SET bundle_version = '2.0.0' WHERE content_digest = %s", (digest,)),
                          ("DELETE FROM trustlens.knowledge_bundle_reference WHERE content_digest = %s", (digest,)),
                          ("UPDATE trustlens.knowledge_activation_record SET outcome = 'FAILED' WHERE knowledge_activation_record_id = %s", (record,)),
                          ("DELETE FROM trustlens.knowledge_activation_record WHERE knowledge_activation_record_id = %s", (record,)),
                          ("DELETE FROM trustlens.knowledge_deployment_state WHERE deployment_ref = %s", (self.deployment_ref,)),
                          ("UPDATE trustlens.knowledge_deployment_state SET deployment_ref = 'other' WHERE deployment_ref = %s", (self.deployment_ref,))):
            with self.subTest(sql=sql[:60]), self.assertRaises(psycopg.errors.RestrictViolation):
                self.owner(sql, args)
        with self.assertRaises(psycopg.errors.CheckViolation):           # never ACTIVE without validation + authenticity
            self.owner("INSERT INTO trustlens.knowledge_activation_record VALUES (gen_random_uuid(), %s, %s, NULL, 'ACTIVATION',"
                       " 'ACTIVE', 'PASSED', 'NOT_PERFORMED', (SELECT actor_principal_id FROM trustlens.knowledge_activation_record"
                       " WHERE knowledge_activation_record_id = %s), 'X', 'SUCCEEDED', now())", (self.deployment_ref, digest, record))
        with self.db() as c, c.cursor() as cur:                           # the application role: activation grants only
            for sql in ("UPDATE trustlens.knowledge_bundle_reference SET governance_eligibility = 'ELIGIBLE'",
                        "DELETE FROM trustlens.knowledge_bundle_reference",
                        "UPDATE trustlens.knowledge_activation_record SET outcome = 'FAILED'",
                        "DELETE FROM trustlens.knowledge_activation_record",
                        "UPDATE trustlens.knowledge_deployment_state SET deployment_ref = 'other'",
                        "DELETE FROM trustlens.knowledge_deployment_state"):
                with self.subTest(sql=sql[:50]), self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute(sql)

    # ---- activateKnowledgeBundle (DEC-011) with the DEC-012 local authenticity exception
    def approve(self, digest, **overrides):
        """Write this test's committed-release-record stand-in approving `digest` for its deployment."""
        entry = {"release_record_ref": f"TL-KREL-TEST-{len(self.approved) + 1:04d}", "content_digest": digest,
                 "bundle_version": "1.0.0", "manifest_schema_version": "1.1.0", **overrides}
        self.approved.append(entry)
        record = {"release_record_schema_version": "1.0", "deployment_ref": self.deployment_ref,
                  "profile": "SINGLE_MACHINE_SYNTHETIC_DEVELOPMENT",
                  "authenticity_policy": {"decision": "DEC-012", "outcome": "NOT_REQUIRED_BY_POLICY", "scope": "test"},
                  "approved_bundles": self.approved}
        (self.knowledge_release_dir / f"{self.deployment_ref}.json").write_text(json.dumps(record))
        return entry

    def activate_api(self, client, digest, expected=None, key=None, ref="DEC-011:S3-TEST", omit_expected=False):
        body = {"content_digest": digest, "governance_change_ref": ref}
        if not omit_expected:
            body["expected_active_content_digest"] = expected
        return client.post("/api/v1/knowledge/deployment/activate", json=body, headers={"Idempotency-Key": key or self.new_key()})

    def deployment(self):
        return self.owner("SELECT operational_state, active_bundle_content_digest FROM trustlens.knowledge_deployment_state"
                          " WHERE deployment_ref = %s", (self.deployment_ref,))[0]

    def knowledge_events(self, digest):
        return self.owner("SELECT event_type, outcome, actor_principal_id::text, target_kind, safe_metadata FROM trustlens.audit_event"
                          " WHERE target_kind = 'KNOWLEDGE_BUNDLE' AND safe_metadata->>'content_digest' = %s ORDER BY chain_sequence",
                          (digest,))

    def test_an_authorized_exact_digest_activation_is_recorded_audited_and_ready(self):
        digest = self.fresh_bundle()
        entry = self.approve(digest)
        subject, admin_id = self.provision(roles=("ADMINISTRATOR",))
        admin = self.client_for(subject)
        key = self.new_key()
        r = self.activate_api(admin, digest, key=key)
        self.assertEqual(r.status_code, 202, r.text)
        view = r.json()
        self.assert_schema(view, "KnowledgeActivationResponse")
        self.assertEqual((view["action_kind"], view["lifecycle_state"], view["outcome"], view["content_digest"],
                          view["previous_content_digest"]), ("ACTIVATION", "ACTIVE", "SUCCEEDED", digest, None))
        self.assertEqual(self.deployment(), ("ACTIVE", digest))
        ready = self.readiness()
        self.assertEqual((ready.ready, ready.content_digest), (True, digest))           # immutable verified instance
        reference = self.owner("SELECT governance_eligibility, release_record_ref, bundle_version, manifest_schema_version"
                               " FROM trustlens.knowledge_bundle_reference WHERE content_digest = %s", (digest,))[0]
        self.assertEqual(reference, ("ELIGIBLE", entry["release_record_ref"], "1.0.0", "1.1.0"))
        record = self.owner("SELECT validation_outcome, authenticity_outcome, actor_principal_id::text, reason_ref"
                            " FROM trustlens.knowledge_activation_record WHERE knowledge_activation_record_id = %s",
                            (view["activation_id"],))[0]
        self.assertEqual(record, ("PASSED", "NOT_REQUIRED_BY_POLICY", admin_id, "DEC-011:S3-TEST"))
        events = self.knowledge_events(digest)
        self.assertEqual([(e[0], e[1], e[2], e[3]) for e in events], [("KNOWLEDGE_ACTIVATED", "SUCCEEDED", admin_id, "KNOWLEDGE_BUNDLE")])
        self.assertEqual((events[0][4]["deployment"], events[0][4]["activation_id"], events[0][4]["authenticity"]),
                         (self.deployment_ref, view["activation_id"], "NOT_REQUIRED_BY_POLICY"))
        self.verify_chain()
        replay = self.activate_api(admin, digest, key=key)
        self.assertEqual((replay.status_code, replay.json()["activation_id"]), (202, view["activation_id"]))   # idempotent
        self.assertEqual(len(self.knowledge_events(digest)), 1)

    def test_the_operator_cli_activates_only_through_the_api_with_confirmation(self):
        digest = self.fresh_bundle()
        self.approve(digest)
        admin = self.reader("ADMINISTRATOR")
        asked = []
        with self.assertRaises(knowledge_cli.CliError):
            knowledge_cli.run_activation(admin, digest, "DEC-011:CLI-TEST", T.APP, lambda e: asked.append(e) or False, say=lambda *_: None)
        self.assertEqual(asked, [digest[:12]])
        self.assertEqual(self.deployment(), ("NO_ACTIVE_BUNDLE", None))                 # not confirmed: nothing changed
        body = knowledge_cli.run_activation(admin, digest, "DEC-011:CLI-TEST", T.APP, lambda e: True, say=lambda *_: None)
        self.assertEqual((body["lifecycle_state"], self.deployment()), ("ACTIVE", ("ACTIVE", digest)))
        with self.assertRaisesRegex(knowledge_cli.CliError, "ADMINISTRATOR"):
            knowledge_cli.run_activation(self.reader("ANALYST"), digest, "DEC-011:CLI-TEST", T.APP, lambda e: True, say=lambda *_: None)

    def test_unauthorized_or_malformed_activation_is_refused_without_change(self):
        digest = self.fresh_bundle()
        self.approve(digest)
        for role in ("USER", "ANALYST", "KNOWLEDGE_EDITOR", "KNOWLEDGE_APPROVER"):
            self.assertEqual(self.activate_api(self.reader(role), digest).status_code, 403, role)
        admin = self.reader("ADMINISTRATOR")
        with TestClient(admin.app, base_url=T.BACKEND, headers={"Origin": T.APP}) as anonymous:
            self.assertIn(self.activate_api(anonymous, digest).status_code, (401, 403))   # no session: refused (CSRF layer first)
        token = admin.headers.pop("X-CSRF-Token")
        self.assertEqual(self.activate_api(admin, digest).status_code, 403)               # CSRF still enforced
        admin.headers["X-CSRF-Token"] = token
        self.assertEqual(admin.post("/api/v1/knowledge/deployment/activate", json={"content_digest": digest,
                                    "governance_change_ref": "X"}).status_code, 400)      # no Idempotency-Key
        for body in ({"content_digest": "latest", "governance_change_ref": "DEC-011"},
                     {"content_digest": digest, "governance_change_ref": "lowercase"},
                     {"content_digest": digest, "governance_change_ref": "DEC-011", "force": True},
                     {"content_digest": digest}):
            with self.subTest(body=body):
                self.assertEqual(admin.post("/api/v1/knowledge/deployment/activate", json=body,
                                            headers={"Idempotency-Key": self.new_key()}).status_code, 400)
        self.assertEqual(self.deployment(), ("NO_ACTIVE_BUNDLE", None))
        self.assertEqual(self.knowledge_events(digest), [])

    def test_ineligible_tampered_or_unapproved_bundles_are_refused_and_audited(self):
        admin = self.reader("ADMINISTRATOR")

        def refused(digest, reason):
            r = self.activate_api(admin, digest)
            self.assertEqual((r.status_code, r.json()["error"]["code"]), (409, "KNOWLEDGE_NOT_ELIGIBLE"), reason)
            self.assertEqual(self.knowledge_events(digest)[-1][0:2], ("KNOWLEDGE_ACTIVATION_REJECTED", "DENIED"))
            self.assertEqual(self.knowledge_events(digest)[-1][4]["reason"], reason)
            self.assertEqual(self.deployment(), ("NO_ACTIVE_BUNDLE", None))
        refused(self.fresh_bundle(), "NO_RELEASE_RECORD")                                # no record for this deployment
        unapproved = self.fresh_bundle()
        self.approve(self.fresh_bundle())
        refused(unapproved, "NOT_APPROVED_FOR_DEPLOYMENT")                                 # digest-valid, not approved
        tampered = self.fresh_bundle()
        self.approve(tampered)
        rule = next((self.store / tampered / "rules").glob("*.json"))
        rule.write_bytes(rule.read_bytes() + b" ")
        refused(tampered, "BUNDLE_TAMPERED")
        missing = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
        self.approve(missing)
        refused(missing, "BUNDLE_MISSING")
        ungoverned = self.fresh_bundle()
        manifest_path = self.store / ungoverned / "bundle-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["gate"] = "NOT_RECORDED"                                                  # not from a passed publication gate
        manifest_path.write_text(json.dumps(manifest))
        self.approve(ungoverned)
        refused(ungoverned, "NOT_GOVERNED_PUBLICATION")
        mismatched = self.fresh_bundle()
        self.approve(mismatched, bundle_version="2.0.0")
        refused(mismatched, "RELEASE_RECORD_MISMATCH")
        withdrawn = self.fresh_bundle()
        self.approve(withdrawn)
        self.reference(withdrawn, eligibility="WITHDRAWN")
        refused(withdrawn, "BUNDLE_WITHDRAWN")                                             # never silently re-qualified
        self.verify_chain()

    def test_a_stale_precondition_is_refused_and_withdrawal_blocks_the_active_bundle(self):
        first, second = self.fresh_bundle(), self.fresh_bundle()
        self.approve(first)
        self.approve(second)
        admin = self.reader("ADMINISTRATOR")
        self.assertEqual(self.activate_api(admin, first, expected=None).status_code, 202)
        stale = self.activate_api(admin, second, expected=None)                           # the operator saw an old state
        self.assertEqual((stale.status_code, stale.json()["error"]["code"]), (412, "PRECONDITION_FAILED"))
        self.assertEqual(self.knowledge_events(second)[-1][4]["reason"], "PRECONDITION_FAILED")
        self.assertEqual(self.deployment(), ("ACTIVE", first))
        moved = self.activate_api(admin, second, expected=first)
        self.assertEqual((moved.status_code, moved.json()["previous_content_digest"]), (202, first))
        self.assertEqual(self.readiness().content_digest, second)
        self.owner("UPDATE trustlens.knowledge_bundle_reference SET governance_eligibility = 'WITHDRAWN', eligibility_observed_at = now()"
                   " WHERE content_digest = %s", (second,))                                 # governance withdraws it
        self.assertEqual(self.readiness().reason, "BUNDLE_WITHDRAWN")
        refused = self.activate_api(admin, second, expected=second)
        self.assertEqual(refused.json()["error"]["code"], "KNOWLEDGE_NOT_ELIGIBLE")
        history = self.owner("SELECT bundle_content_digest FROM trustlens.knowledge_activation_record WHERE deployment_ref = %s"
                             " ORDER BY recorded_at", (self.deployment_ref,))
        self.assertEqual([h[0] for h in history], [first, second])                        # history kept, never rewritten

    def test_install_bundle_publishes_only_an_approved_exact_digest(self):
        root = Path(tempfile.mkdtemp(dir=self.tmp.name)) / "store"
        with self.assertRaisesRegex(knowledge_cli.CliError, "publication gate"):
            knowledge_cli.install_bundle(root, self.deployment_ref, "NOT_RECORDED", release_dir=self.knowledge_release_dir)
        with self.assertRaisesRegex(knowledge_cli.CliError, "not approved"):
            knowledge_cli.install_bundle(root, self.deployment_ref, "PASS", release_dir=self.knowledge_release_dir)
        self.assertEqual([p.name for p in root.iterdir()], [])                            # nothing installed, no staging left
        self.approve(self.base)
        digest = knowledge_cli.install_bundle(root, self.deployment_ref, "PASS", release_dir=self.knowledge_release_dir)
        self.assertEqual(digest, self.base)
        self.assertEqual(KnowledgeVerifier(root).verify(digest).content_digest, digest)
        self.assertEqual(knowledge_cli.install_bundle(root, self.deployment_ref, "PASS", release_dir=self.knowledge_release_dir), digest)

    def test_the_committed_local_release_record_pins_the_governed_bundle(self):
        record = json.loads((knowledge_seam.RELEASE_DIR / "local-development.json").read_text())
        self.assertEqual((record["deployment_ref"], record["profile"], record["authenticity_policy"]["outcome"]),
                         ("local-development", "SINGLE_MACHINE_SYNTHETIC_DEVELOPMENT", "NOT_REQUIRED_BY_POLICY"))
        self.assertEqual([b["content_digest"] for b in record["approved_bundles"]], [self.base])   # = the bundle built from Git

    def test_a_database_without_0005_fails_closed(self):
        with patch.object(knowledge_seam, "schema_active", return_value=False):
            self.assertEqual(self.reader().get("/api/v1/knowledge/active").status_code, 503)
            self.assertEqual(self.readiness().reason, "KNOWLEDGE_SCHEMA_MISSING")


if __name__ == "__main__":
    unittest.main()
