"""Local ADMINISTRATOR provisioning (DEC-013, PROPOSED) against a DISPOSABLE PostgreSQL. Synthetic subjects only.

Roles come only from TrustLens role_assignment rows written by this explicit procedure; identity-provider claims never
grant an application role.
"""
import os
import unittest
import uuid
from unittest.mock import patch

import psycopg

import test_auth as T
from db_harness import DISPOSABLE, DbHarness
from trustlens_backend import provisioning
from trustlens_backend.provisioning import ProvisioningRefused, grant_administrator, grant_user, revoke_administrator


@unittest.skipUnless(DISPOSABLE, "needs an explicitly disposable PostgreSQL")
class AdministratorProvisioningTests(DbHarness, unittest.TestCase):
    def run_provisioning(self, fn, subject):
        with psycopg.connect(**self.app_db.connection_parameters()) as c, c.cursor() as cur:   # one transaction, as main()
            return fn(cur, T.ISSUER, subject)

    def roles_of(self, subject):
        with self.db() as c, c.cursor() as cur:
            cur.execute("SELECT r.role, r.revoked_at IS NULL, r.assignment_reason_ref, r.revocation_reason_ref"
                        " FROM trustlens.role_assignment r JOIN trustlens.principal_reference p ON p.principal_reference_id ="
                        " r.principal_reference_id WHERE p.external_subject = %s ORDER BY r.effective_from", (subject,))
            return cur.fetchall()

    def role_events(self, subject):
        with self.db() as c, c.cursor() as cur:
            cur.execute("SELECT e.event_type, e.actor_kind, e.safe_metadata->>'role', e.safe_metadata->>'reason_ref'"
                        " FROM trustlens.audit_event e JOIN trustlens.principal_reference p"
                        " ON p.principal_reference_id::text = e.safe_metadata->>'principal_id' WHERE p.external_subject = %s"
                        " ORDER BY e.chain_sequence", (subject,))
            return cur.fetchall()

    def test_a_separate_account_receives_administrator_only_with_attribution_and_audit(self):
        subject = str(uuid.uuid4())
        self.assertIn("granted to new principal", self.run_provisioning(grant_administrator, subject))
        self.assertEqual(self.roles_of(subject), [("ADMINISTRATOR", True, provisioning.ADMIN_GRANT_REASON, None)])
        self.assertEqual(self.role_events(subject), [("ROLE_ASSIGNED", "WORKLOAD", "ADMINISTRATOR", provisioning.ADMIN_GRANT_REASON)])
        self.assertIn("no change made", self.run_provisioning(grant_administrator, subject))      # idempotent repeat
        self.assertEqual(len(self.role_events(subject)), 1)
        admin = self.client_for(subject)
        self.assertEqual(admin.get("/api/v1/me").json()["roles"], ["ADMINISTRATOR"])
        self.assertEqual(admin.get("/api/v1/knowledge/activations").status_code, 200)           # administrator surface
        self.assertEqual(admin.post("/api/v1/cases", json={}, headers={"Idempotency-Key": self.new_key()}).status_code, 403)
        self.verify_chain()

    def test_an_existing_user_account_is_never_elevated_and_an_admin_account_gains_no_user_role(self):
        user, _ = self.provision()                                                         # an ordinary USER account
        with self.assertRaisesRegex(ProvisioningRefused, "separate account"):
            self.run_provisioning(grant_administrator, user)
        self.assertEqual([r[0] for r in self.roles_of(user) if r[1]], ["USER"])            # unchanged, no audit
        self.assertEqual([e[2] for e in self.role_events(user)], ["USER"])
        admin = str(uuid.uuid4())
        self.run_provisioning(grant_administrator, admin)
        with self.assertRaisesRegex(ProvisioningRefused, "ADMINISTRATOR account"):
            self.run_provisioning(grant_user, admin)
        self.assertEqual([r[0] for r in self.roles_of(admin) if r[1]], ["ADMINISTRATOR"])

    def test_revocation_is_explicit_audited_write_once_and_takes_effect_on_the_next_request(self):
        subject = str(uuid.uuid4())
        self.run_provisioning(grant_administrator, subject)
        admin = self.client_for(subject)
        self.assertEqual(admin.get("/api/v1/me").status_code, 200)
        self.assertIn("revoked", self.run_provisioning(revoke_administrator, subject))
        self.assertEqual(self.roles_of(subject)[-1][1:], (False, provisioning.ADMIN_GRANT_REASON, provisioning.ADMIN_REVOKE_REASON))
        self.assertEqual([e[0] for e in self.role_events(subject)], ["ROLE_ASSIGNED", "ROLE_REVOKED"])
        self.assertEqual(admin.get("/api/v1/me").status_code, 401)                       # roles re-read per request
        self.assertIn("no change made", self.run_provisioning(revoke_administrator, subject))
        self.assertIn("No principal", self.run_provisioning(revoke_administrator, str(uuid.uuid4())))
        self.assertIn("granted to existing", self.run_provisioning(grant_administrator, subject))   # a new, separate grant
        with self.db() as c, c.cursor() as cur, self.assertRaises(psycopg.Error):
            cur.execute("UPDATE trustlens.role_assignment SET revoked_at = NULL WHERE revocation_reason_ref = %s",
                        (provisioning.ADMIN_REVOKE_REASON,))                               # revocation is write-once
        self.verify_chain()

    def test_identity_provider_claims_never_grant_application_roles(self):
        user, _ = self.provision()
        claimed = {"roles": ["ADMINISTRATOR"], "realm_access": {"roles": ["ADMINISTRATOR", "KNOWLEDGE_APPROVER"]},
                   "resource_access": {"trustlens-bff": {"roles": ["ADMINISTRATOR"]}}, "groups": ["/administrators"]}
        client = self.client_for(user, extra_claims=claimed)
        self.assertEqual(client.get("/api/v1/me").json()["roles"], ["USER"])
        r = client.post("/api/v1/knowledge/deployment/activate", json={"content_digest": "a" * 64,
                        "governance_change_ref": "DEC-011"}, headers={"Idempotency-Key": self.new_key()})
        self.assertEqual(r.status_code, 403)

    def test_malformed_subjects_are_refused_before_any_change(self):
        for subject in ("not-a-uuid", "ADMIN", str(uuid.uuid4()).upper(), "", "../x"):
            with self.subTest(subject=subject), self.assertRaises(ProvisioningRefused):
                self.run_provisioning(grant_administrator, subject)
            with self.subTest(subject=subject), self.assertRaises(ProvisioningRefused):
                self.run_provisioning(revoke_administrator, subject)


class AdministratorProvisioningCliTests(unittest.TestCase):
    """main(): explicit confirmation and the loopback synthetic profile are checked before any connection."""

    ENV = {"TRUSTLENS_OIDC_ISSUER": "http://127.0.0.1:8081/realms/trustlens", "TRUSTLENS_OIDC_CLIENT_ID": "trustlens-bff",
           "TRUSTLENS_OIDC_CLIENT_SECRET": "synthetic-not-a-secret", "POSTGRES_DB": "trustlens_dev",
           "POSTGRES_USER": "tl_app_runtime", "POSTGRES_PASSWORD": "synthetic", "TRUSTLENS_DB_HOST": "127.0.0.1",
           "TRUSTLENS_DB_PORT": "55491", "TRUSTLENS_TEST_DISPOSABLE_DB": ""}

    def run_main(self, argv, env=None):
        with patch.object(provisioning, "load_environment_files", return_value={**self.ENV, **(env or {})}), \
                patch.dict(os.environ, {"TRUSTLENS_TEST_DISPOSABLE_DB": ""}), \
                patch.object(provisioning.psycopg, "connect", side_effect=psycopg.OperationalError("not connected")) as connect, \
                patch("sys.stderr"):
            try:
                code = provisioning.main(argv)
            except SystemExit as exit_:
                code = exit_.code
        return code, connect.called

    def test_confirmation_and_exact_subject_are_required(self):
        subject = str(uuid.uuid4())
        for argv in (["grant-administrator", "--subject", subject],
                     ["grant-administrator", "--subject", subject, "--confirm"],
                     ["grant-administrator", "--subject", subject, "--confirm-subject", str(uuid.uuid4()), "--confirm"],
                     ["revoke-administrator", "--subject", subject, "--confirm"],
                     ["grant-administrator", "--subject", "not-a-uuid", "--confirm-subject", "not-a-uuid", "--confirm"]):
            with self.subTest(argv=argv[1:]):
                code, connected = self.run_main(argv)
                self.assertEqual(code, 2)
                self.assertFalse(connected)

    def test_only_the_loopback_profile_may_provision_an_administrator(self):
        subject = str(uuid.uuid4())
        argv = ["grant-administrator", "--subject", subject, "--confirm-subject", subject, "--confirm"]
        for env in ({"TRUSTLENS_OIDC_ISSUER": "https://idp.example.invalid/realms/trustlens"},
                    {"TRUSTLENS_OIDC_REDIRECT_URI": "https://app.example.invalid/auth/callback"},
                    {"TRUSTLENS_APP_ORIGIN": "https://app.example.invalid",
                     "TRUSTLENS_OIDC_POST_LOGOUT_REDIRECT_URI": "https://app.example.invalid/"},
                    {"TRUSTLENS_DB_HOST": "10.0.0.5"}):
            with self.subTest(env=env):
                code, connected = self.run_main(argv, env)
                self.assertEqual(code, 2)
                self.assertFalse(connected)
        with patch.object(provisioning, "SYNTHETIC_ONLY_PROFILE", False):
            code, connected = self.run_main(argv)
        self.assertEqual((code, connected), (2, False))
        code, connected = self.run_main(argv)                                              # loopback: proceeds to connect
        self.assertTrue(connected)


if __name__ == "__main__":
    unittest.main()
