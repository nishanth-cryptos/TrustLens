"""S3 knowledge seam (no database): exact-digest bundle verification through the existing Phase-3 loader.

Bundles are built with the existing deterministic publisher (knowledge/publish/build_bundle.py) into temporary
directories named by their content digest; negative cases tamper copies of them. Nothing outside the temp tree is touched.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import httpx

from knowledge.publish.build_bundle import build
from trustlens_backend.knowledge_cli import CliError, expected_idp_origin, login_form, sign_in
from trustlens_backend.knowledge_seam import BundleRejected, KnowledgeVerifier


def build_store(root: Path) -> str:
    """Build the governed bundle into <root>/<content_digest>/ and return the digest."""
    staging = root / "staging"
    manifest = build(staging)
    digest = manifest["content_digest"]
    staging.rename(root / digest)
    return digest


class KnowledgeVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.digest = build_store(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def copy_store(self) -> tuple[Path, Path]:
        """A private copy of the store for one destructive test."""
        work = Path(tempfile.mkdtemp(dir=self.tmp.name))
        shutil.copytree(self.root / self.digest, work / self.digest)
        return work, work / self.digest

    def rejected(self, verifier, digest):
        with self.assertRaises(BundleRejected) as caught:
            verifier.verify(digest)
        return caught.exception.reason

    def test_a_published_bundle_verifies_by_its_exact_digest(self):
        knowledge = KnowledgeVerifier(self.root).verify(self.digest)
        self.assertEqual(knowledge.content_digest, self.digest)
        self.assertEqual((knowledge.bundle_version, knowledge.manifest_schema_version), ("1.0.0", "1.1.0"))

    def test_malformed_or_unknown_digests_are_rejected(self):
        verifier = KnowledgeVerifier(self.root)
        for bad in ("latest", "", None, self.digest.upper(), self.digest[:63], "../" + self.digest, self.digest + "/.."):
            with self.subTest(digest=bad):
                self.assertEqual(self.rejected(verifier, bad), "DIGEST_INVALID")
        self.assertEqual(self.rejected(verifier, "0" * 64), "BUNDLE_MISSING")

    def test_a_tampered_member_is_rejected(self):
        work, bundle = self.copy_store()
        rule = next((bundle / "rules").glob("*.json"))
        rule.write_bytes(rule.read_bytes() + b" ")                             # one byte appended
        self.assertEqual(self.rejected(KnowledgeVerifier(work), self.digest), "BUNDLE_TAMPERED")

    def test_a_bundle_stored_under_another_digest_is_rejected(self):
        work, bundle = self.copy_store()
        other = "f" * 64
        bundle.rename(work / other)
        self.assertEqual(self.rejected(KnowledgeVerifier(work), other), "BUNDLE_TAMPERED")   # identity is the digest

    def test_invalid_and_incompatible_manifests_are_rejected(self):
        work, bundle = self.copy_store()
        manifest_path = bundle / "bundle-manifest.json"
        original = json.loads(manifest_path.read_text())
        broken = dict(original)
        del broken["integrity"]
        manifest_path.write_text(json.dumps(broken))
        self.assertEqual(self.rejected(KnowledgeVerifier(work), self.digest), "BUNDLE_INVALID")
        incompatible = json.loads(json.dumps(original))
        incompatible["component_versions"] = {k: "99.0.0" for k in incompatible["component_versions"]}
        manifest_path.write_text(json.dumps(incompatible))
        self.assertIn(self.rejected(KnowledgeVerifier(work), self.digest), {"BUNDLE_INCOMPATIBLE", "BUNDLE_INVALID"})
        manifest_path.unlink()
        self.assertEqual(self.rejected(KnowledgeVerifier(work), self.digest), "BUNDLE_MISSING")

    def test_an_unexpected_or_unlisted_member_is_rejected(self):
        work, bundle = self.copy_store()
        (bundle / "rules" / "extra-rule.json").write_text("{}")
        manifest_path = bundle / "bundle-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["integrity"]["files"].append({"path": "rules/extra-rule.json", "sha256": "0" * 64, "bytes": 2})
        manifest_path.write_text(json.dumps(manifest))
        self.assertIn(self.rejected(KnowledgeVerifier(work), self.digest), {"BUNDLE_TAMPERED", "BUNDLE_INVALID"})

    def test_verified_knowledge_is_immutable_and_unaffected_by_later_disk_changes(self):
        work, bundle = self.copy_store()
        verifier = KnowledgeVerifier(work)
        first = verifier.verify(self.digest)
        rule = next((bundle / "rules").glob("*.json"))
        rule.write_bytes(rule.read_bytes() + b" ")
        self.assertIs(verifier.verify(self.digest), first)                     # the evaluation keeps what was verified
        self.assertEqual(self.rejected(KnowledgeVerifier(work), self.digest), "BUNDLE_TAMPERED")   # a fresh check fails
        with self.assertRaises((TypeError, AttributeError)):
            first.component_versions["rules"] = "tampered"                     # deep-frozen RuntimeKnowledge



BACKEND, APP, IDP = "http://127.0.0.1:8000", "http://127.0.0.1:5173", "http://127.0.0.1:8081"
FORM = ('<html><body><form id="kc-form-login" action="{action}" method="post"><input type="hidden" name="credentialId"'
        ' value=""><input name="username"><input type="password" name="password"></form></body></html>')


class CliSignInTests(unittest.TestCase):
    """The CLI signs in as a user agent through /auth/login and /auth/callback. Review findings 1-2: every hop is checked
    before it is requested, the IdP origin is configured (never taken from a redirect), and credentials, IdP cookies and
    the session cookie each stay with their own origin."""

    def network(self, routes):
        """routes: url-prefix -> response factory. Records (method, url, body, cookie header) for every request."""
        seen = []

        def handler(request):
            seen.append((request.method, str(request.url), request.content, request.headers.get("cookie", "")))
            url = str(request.url)
            for prefix in sorted(routes, key=len, reverse=True):
                if url.startswith(prefix):
                    return routes[prefix](request)
            return httpx.Response(404)
        return httpx.MockTransport(handler), seen

    def normal_routes(self, idp=IDP, **overrides):
        routes = {
            f"{BACKEND}/auth/login": lambda r: httpx.Response(303, headers={"location": f"{idp}/realms/t/auth?state=x",
                                                                            "set-cookie": "tl_auth_tx=tx; Path=/auth"}),
            f"{idp}/realms/t/auth": lambda r: httpx.Response(200, text=FORM.format(action=f"{idp}/realms/t/login-actions/authenticate?s=1"),
                                                             headers={"set-cookie": "KC_IDP=idp-secret; Path=/"}),
            f"{idp}/realms/t/login-actions/authenticate": lambda r: httpx.Response(302, headers={
                "location": f"{BACKEND}/auth/callback?code=c&state=x"}),
            f"{BACKEND}/auth/callback": lambda r: httpx.Response(303, headers={"location": f"{APP}/", "set-cookie": "tl_session=s; Path=/"}),
        }
        routes.update(overrides)
        return routes

    def attempt(self, routes, idp_origin=IDP):
        transport, seen = self.network(routes)
        backend = httpx.Client(base_url=BACKEND, transport=transport)
        idp = httpx.Client(transport=transport)
        self.addCleanup(backend.close)
        self.addCleanup(idp.close)
        error = None
        try:
            sign_in(backend, "operator", "synthetic-password", APP, idp_origin, idp=idp)
        except CliError as caught:
            error = caught
        return error, seen, backend

    def assert_no_leaks(self, seen):
        for method, url, body, cookies in seen:
            if url.startswith(BACKEND):
                self.assertNotIn("KC_IDP", cookies, url)                                   # IdP cookie never reaches the backend
                self.assertNotIn(b"synthetic-password", body, url)                         # password never reaches the backend
            else:
                self.assertNotIn("tl_session", cookies, url)
                self.assertNotIn("tl_auth_tx", cookies, url)

    def posts(self, seen):
        return [s for s in seen if s[0] == "POST"]

    def test_the_login_form_is_parsed_without_inventing_fields(self):
        action, fields = login_form(FORM.format(action="http://idp.test/x?a=1&amp;b=2"))
        self.assertEqual((action, fields), ("http://idp.test/x?a=1&b=2", {"credentialId": ""}))
        with self.assertRaises(CliError):
            login_form("<form action='x'><input name='a'></form>")                         # no password field

    def test_a_normal_sign_in_completes_through_the_accepted_callback(self):
        error, seen, backend = self.attempt(self.normal_routes())
        self.assertIsNone(error)
        self.assertEqual(backend.cookies.get("tl_session"), "s")
        self.assertEqual([p[1] for p in self.posts(seen)], [f"{IDP}/realms/t/login-actions/authenticate?s=1"])
        self.assertEqual([u for _, u, _, _ in seen if u.startswith(BACKEND)],
                         [f"{BACKEND}/auth/login", f"{BACKEND}/auth/callback?code=c&state=x"])
        self.assert_no_leaks(seen)

    def test_finding_1_idp_to_backend_to_idp_redirects_never_carry_idp_cookies_to_the_backend(self):
        bounce = {f"{IDP}/realms/t/auth": lambda r: httpx.Response(302, headers={"location": f"{BACKEND}/bounce",
                                                                               "set-cookie": "KC_IDP=idp-secret; Path=/"}),
                  f"{BACKEND}/bounce": lambda r: httpx.Response(302, headers={"location": f"{IDP}/realms/t/login"}),
                  f"{IDP}/realms/t/login": lambda r: httpx.Response(200, text=FORM.format(action=f"{IDP}/realms/t/login-actions/authenticate?s=1"))}
        # The exploit is real: an automatically redirecting client on the IdP jar sends the IdP cookie to the backend.
        transport, leaked = self.network(self.normal_routes(**bounce))
        with httpx.Client(transport=transport) as naive:
            naive.get(f"{IDP}/realms/t/auth?state=x", follow_redirects=True)
        self.assertTrue(any(u == f"{BACKEND}/bounce" and "KC_IDP" in c for _, u, _, c in leaked))
        # The fixed CLI refuses the hop before requesting it: the backend sees only /auth/login.
        error, seen, _ = self.attempt(self.normal_routes(**bounce))
        self.assertIsInstance(error, CliError)
        self.assertEqual([u for _, u, _, _ in seen if u.startswith(BACKEND)], [f"{BACKEND}/auth/login"])
        self.assertFalse(self.posts(seen))
        self.assert_no_leaks(seen)

    def test_finding_1_cycles_redirect_limits_downgrades_and_foreign_hops_are_refused(self):
        cases = {
            "cycle": {f"{IDP}/realms/t/auth": lambda r: httpx.Response(302, headers={"location": f"{IDP}/realms/t/auth?state=x"})},
            "too many hops": {f"{IDP}/realms/t/auth": lambda r: httpx.Response(302, headers={
                "location": f"{IDP}/realms/t/auth/next-{len(r.url.path)}?state=x"})},
            "foreign host": {f"{IDP}/realms/t/auth": lambda r: httpx.Response(302, headers={"location": "http://evil.test/login"})},
            "post-login hop to a foreign host": {f"{IDP}/realms/t/login-actions/authenticate": lambda r: httpx.Response(302, headers={
                "location": "http://evil.test/collect"})},
            "post-login hop to another backend path": {f"{IDP}/realms/t/login-actions/authenticate": lambda r: httpx.Response(302, headers={
                "location": f"{BACKEND}/api/v1/me"})},
            "callback reports failure": {f"{BACKEND}/auth/callback": lambda r: httpx.Response(303, headers={
                "location": f"{APP}/?signin=failed"})},
        }
        for name, override in cases.items():
            with self.subTest(case=name):
                error, seen, backend = self.attempt(self.normal_routes(**override))
                self.assertIsInstance(error, CliError)
                self.assertFalse(any("evil.test" in u for _, u, _, _ in seen))             # never requested
                self.assertFalse(any(u.startswith(f"{BACKEND}/api/") for _, u, _, _ in seen))
                self.assertIsNone(backend.cookies.get("tl_session"))                          # no session established
                self.assert_no_leaks(seen)
        https_idp = "https://idp.test"                                                     # scheme downgrade
        downgrade = self.normal_routes(idp=https_idp, **{f"{https_idp}/realms/t/auth": lambda r: httpx.Response(302, headers={
            "location": "http://idp.test/realms/t/login"})})
        error, seen, _ = self.attempt(downgrade, idp_origin=https_idp)
        self.assertIsInstance(error, CliError)
        self.assertFalse(any(u.startswith("http://idp.test") for _, u, _, _ in seen))

    def test_finding_2_a_backend_hosted_login_form_never_receives_the_password(self):
        fake = {f"{BACKEND}/auth/login": lambda r: httpx.Response(303, headers={"location": f"{BACKEND}/fake-login"}),
                f"{BACKEND}/fake-login": lambda r: httpx.Response(200, text=FORM.format(action=f"{BACKEND}/fake-login"))}
        error, seen, _ = self.attempt(self.normal_routes(**fake))                         # configured IdP is :8081
        self.assertIsInstance(error, CliError)
        self.assertFalse(self.posts(seen))
        self.assertNotIn(f"{BACKEND}/fake-login", [u for _, u, _, _ in seen])             # not even fetched
        error, seen, _ = self.attempt(self.normal_routes(**fake), idp_origin=BACKEND)     # backend posing as the IdP
        self.assertIsInstance(error, CliError)
        self.assertEqual(seen, [])                                                         # refused before any request
        for issuer in (f"{BACKEND}/realms/t", f"{APP}/realms/t", "http://idp.example.invalid/realms/t", "ftp://127.0.0.1/x", ""):
            with self.subTest(issuer=issuer), self.assertRaises(CliError):
                expected_idp_origin(issuer, BACKEND, APP)
        self.assertEqual(expected_idp_origin(f"{IDP}/realms/trustlens", BACKEND, APP), IDP)

    def test_finding_2_foreign_or_backend_form_actions_never_receive_the_password(self):
        for action in ("http://evil.test/collect", f"{BACKEND}/auth/callback", "https://127.0.0.1:8081/x", "/../../x"):
            override = {f"{IDP}/realms/t/auth": lambda r, a=action: httpx.Response(200, text=FORM.format(
                action=a if a != "/../../x" else f"{BACKEND}/collect"))}
            with self.subTest(action=action):
                error, seen, _ = self.attempt(self.normal_routes(**override))
                self.assertIsInstance(error, CliError)
                self.assertFalse(self.posts(seen))                                         # credentials never submitted
                self.assert_no_leaks(seen)


if __name__ == "__main__":
    unittest.main()
