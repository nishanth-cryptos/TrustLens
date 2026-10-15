"""S7 advisory enrichment against a DISPOSABLE PostgreSQL (migration 0008): the internal seam with a FAKE provider and FAKE
DNS (no network), immutable persistence with exact provenance, the analyst-only listEvaluationEnrichments read, and the
separation from the immutable DetectionResult and from replay. Simulated provider assertions only."""
import json
import socket
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import psycopg

from db_harness import CATALOG, DISPOSABLE
from test_egress import GLOBAL, HOST, NOW, POLICY, SECRET, Credentials, FakeResolver
from test_evaluation_db import EvaluationHarness, code
from trustlens_backend import egress, enrichment
from trustlens_backend.egress import Adapter, TransportError, TransportResponse, load_policy

URLS = (b"SYNTHETIC TEST: Your KYC expires today. Open this link http://examplebank-kyc-verify.example and enter your"
        b" credentials to verify. Also see trust-wallet-verify.example")
NO_URL = b"SYNTHETIC TEST: Example Bank: unusual activity. Share the OTP you just received with our officer now."


class EchoProvider:
    """A FICTIONAL provider that echoes the queried indicator with a scripted entry; counts every request."""

    def __init__(self, entry="FOUND", reputation="MALICIOUS", allowlist="NOT_ALLOWLISTED", failure=None, status=200):
        self.entry, self.reputation, self.allowlist, self.failure, self.status, self.calls = entry, reputation, allowlist, failure, status, []

    def connect(self, connection, *, timeout):
        provider = self

        class Channel:
            peer_address = connection.address

            def close(self):
                pass

            def exchange(self, method, target, headers, body, *, remaining, read_timeout, max_wire_bytes):
                return provider.exchange(connection, target)

        return Channel()

    def exchange(self, connection, target):
        self.calls.append((connection, target))
        if self.failure:
            raise TransportError(self.failure)
        value = parse_qs(urlsplit(target).query)["indicator"][0]
        document = {"schema_version": "1.0.0", "provider_ref": "FICTIONAL_FIXTURE_PROVIDER", "indicator": {"type": "URL", "value": value},
                    "observed_at": "2026-10-15T11:59:00Z", "entry": self.entry, "reputation": self.reputation,
                    "allowlist": self.allowlist, "brand_match": "UNKNOWN"}
        return TransportResponse(self.status, {"content-type": "application/json"}, json.dumps(document).encode())


@unittest.skipUnless(DISPOSABLE, "needs an explicitly disposable PostgreSQL")
class EnrichmentTests(EvaluationHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        def no_network(*args, **kwargs):
            raise AssertionError("no real network access from the test suite")
        for target in ("socket.getaddrinfo", "socket.create_connection"):
            guard = patch(target, no_network)
            guard.start()
            self.addCleanup(guard.stop)

    def enable(self, runtime, provider, policy_overrides=None, answers=(GLOBAL,), credentials=Credentials()):
        policy = load_policy({**POLICY, **(policy_overrides or {})})
        adapter = Adapter(resolver=FakeResolver({HOST: list(answers)}), transport=provider, credentials=credentials, now=lambda: NOW,
                          sleep=lambda s: None)
        known = runtime.enrichment.policies if runtime.enrichment else {}             # published versions stay resolvable
        runtime.enrichment = enrichment.EnrichmentRuntime(adapter=adapter, policies=dict(known))
        runtime.enrichment.add(policy)                                                  # only this version is ACTIVE
        return policy

    def evaluated(self, data=URLS):
        self.activate_exact_bundle()
        client, _ = self.owner()
        case_id, submission_id, evaluation_id = self.journey(client, data)
        analyst, _ = self.assign_analyst(case_id)
        return client, analyst, case_id, submission_id, evaluation_id

    def rows(self, evaluation_id):
        return self.app_sql("SELECT status, lookup_outcome, reputation_result, allowlist_result, safe_error_category, indicator_type,"
                            " normalized_indicator_ref, provider_policy_ref, provider_policy_version, provider_policy_digest,"
                            " parser_schema_version, response_artifact_digest, responded_at, consumed_in_governed_artifact,"
                            " adapter_version, integration_contract_version, freshness_state, cache_used, provider_response_category,"
                            " raw_provider_content_policy_ref, retained_provider_artifact_ecs_locator"
                            " FROM trustlens.external_enrichment_result WHERE evaluation_id = %s ORDER BY created_at", (evaluation_id,))

    def listing(self, client, evaluation_id, query=""):
        return client.get(f"/api/v1/evaluations/{evaluation_id}/enrichments{query}")

    def test_operation_matches_the_catalog(self):
        o = next(o for o in CATALOG["operations"] if o["operation_id"] == "listEvaluationEnrichments")
        spec = enrichment.OPERATIONS["listEvaluationEnrichments"]
        self.assertEqual((spec["method"], spec["path"], list(spec["roles"]), spec["resource_authorization"]),
                         (o["method"], o["path"], o["roles"], o["resource_authorization"]))

    def test_disabled_by_default_and_no_indicator_means_no_lookup(self):
        client, analyst, _, _, evaluation_id = self.evaluated()
        runtime = analyst.app.state.auth
        self.assertIsNone(runtime.enrichment)
        self.assertEqual(enrichment.enrich_evaluation(runtime, evaluation_id), {"state": "DISABLED", "records": []})
        self.assertEqual(self.rows(evaluation_id), [])
        body = self.listing(analyst, evaluation_id).json()
        self.assertEqual(body["items"], [])                                              # honest: nothing was looked up
        provider = EchoProvider()
        self.enable(runtime, provider)
        _, _, plain = self.journey(client, NO_URL)
        self.assertEqual(enrichment.enrich_evaluation(runtime, plain)["state"], "NO_INDICATORS")
        self.assertEqual(provider.calls, [])

    def test_lookups_persist_exact_provenance_and_never_touch_the_detection_result(self):
        client, analyst, case_id, _, evaluation_id = self.evaluated()
        before = self.app_sql("SELECT r.result_digest, r.result_canonical_json, e.status, e.replay_material_digest FROM trustlens.detection_result r"
                              " JOIN trustlens.evaluation e ON e.evaluation_id = r.evaluation_id WHERE r.evaluation_id = %s", (evaluation_id,))
        result_before = self.result(client, evaluation_id).json()
        provider = EchoProvider("FOUND", "MALICIOUS")
        policy = self.enable(analyst.app.state.auth, provider)
        outcome = enrichment.enrich_evaluation(analyst.app.state.auth, evaluation_id)
        self.assertEqual((outcome["state"], len(outcome["records"])), ("RECORDED", 2))     # two URL indicators, each looked up once
        self.assertTrue(all(call[0].address == GLOBAL and call[0].server_hostname == HOST for call in provider.calls))
        self.assertFalse(any("examplebank" in call[0].server_hostname for call in provider.calls))   # never the submitted host
        for row in self.rows(evaluation_id):
            self.assertEqual(row[:6], ("SUCCEEDED", "FOUND", "MALICIOUS", "NOT_ALLOWLISTED", None, "URL"))
            self.assertEqual(row[7:11], ("TL-PPOL-FIXTURE", "1.0.0", policy.digest, "TL-FIXTURE-PARSER-1.0.0"))
            self.assertRegex(row[6], r"^[0-9a-f]{64}$")
            self.assertRegex(row[11], r"^[0-9a-f]{64}$")
            self.assertEqual(row[12], NOW)
            self.assertEqual(row[13:], (False, egress.ADAPTER_VERSION, "0.1.0", "UNKNOWN", False, "HTTP_2XX",
                                        "NO_RAW_PROVIDER_CONTENT_RETAINED", None))
        after = self.app_sql("SELECT r.result_digest, r.result_canonical_json, e.status, e.replay_material_digest FROM trustlens.detection_result r"
                             " JOIN trustlens.evaluation e ON e.evaluation_id = r.evaluation_id WHERE r.evaluation_id = %s", (evaluation_id,))
        self.assertEqual(after, before)                                                    # classification, risk, confidence unchanged
        self.assertEqual(self.result(client, evaluation_id).json(), result_before)
        events = [(e[0], e[5]) for e in self.audit_rows(case_id) if e[3] in ("EXTERNAL_ENRICHMENT", "PROVIDER_POLICY")]
        self.assertEqual([e[0] for e in events], ["PROVIDER_POLICY_SELECTED", "ENRICHMENT_REQUESTED", "ENRICHMENT_ACCEPTED",
                                                  "ENRICHMENT_REQUESTED", "ENRICHMENT_ACCEPTED"])
        everything = json.dumps([str(r) for r in self.app_sql("SELECT * FROM trustlens.external_enrichment_result")]
                                + [str(e) for e in self.audit_rows(case_id)])
        for forbidden in (SECRET, "examplebank-kyc-verify", "trust-wallet-verify"):
            self.assertNotIn(forbidden, everything)                                         # no credential, no raw indicator
        with self.db() as c, c.cursor() as cur, self.assertRaises(psycopg.Error):
            cur.execute("UPDATE trustlens.external_enrichment_result SET reputation_result = 'CLEAN' WHERE evaluation_id = %s", (evaluation_id,))
        self.verify_chain()

    def test_every_outcome_persists_under_the_accepted_constraints(self):
        client, analyst, case_id, _, evaluation_id = self.evaluated()
        runtime = analyst.app.state.auth
        cases = [(EchoProvider("FOUND", "SUSPICIOUS"), {}, (GLOBAL,), ("SUCCEEDED", "FOUND", "SUSPICIOUS", None)),
                 (EchoProvider("FOUND", "CLEAN", "ALLOWLISTED"), {}, (GLOBAL,), ("SUCCEEDED", "FOUND", "CLEAN", None)),
                 (EchoProvider("FOUND", "UNKNOWN"), {}, (GLOBAL,), ("SUCCEEDED", "FOUND", "UNKNOWN", None)),
                 (EchoProvider("NOT_FOUND", "UNKNOWN", "NOT_EVALUATED"), {}, (GLOBAL,), ("SUCCEEDED", "NOT_FOUND", "UNKNOWN", None)),
                 (EchoProvider(failure="TIMEOUT"), {}, (GLOBAL,), ("TIMED_OUT", "UNAVAILABLE", "NOT_EVALUATED", "TIMEOUT")),
                 (EchoProvider(failure="CONNECTION"), {"retry_safe": False}, (GLOBAL,), ("FAILED", "UNAVAILABLE", "NOT_EVALUATED", "CONNECTION_FAILURE")),
                 (EchoProvider(status=429), {"retry_safe": False}, (GLOBAL,), ("FAILED", "UNAVAILABLE", "NOT_EVALUATED", "RATE_LIMITED")),
                 (EchoProvider(reputation="SAFE"), {}, (GLOBAL,), ("FAILED", "INVALID_RESPONSE", "NOT_EVALUATED", "SCHEMA_INVALID_RESPONSE")),
                 (EchoProvider(), {}, ("169.254.169.254",), ("REJECTED", "POLICY_REJECTED", "NOT_EVALUATED", "DESTINATION_ADDRESS_REJECTION")),
                 (EchoProvider(), {}, (GLOBAL, "10.0.0.1"), ("REJECTED", "POLICY_REJECTED", "NOT_EVALUATED", "DESTINATION_ADDRESS_REJECTION"))]
        for provider, overrides, answers, expected in cases:
            with self.subTest(expected=expected):
                self.enable(runtime, provider, {"provider_policy_version": f"1.0.{len(provider.calls)}", **overrides}, answers)
                records = enrichment.enrich_evaluation(runtime, evaluation_id)["records"]
                stored = self.app_sql("SELECT status, lookup_outcome, reputation_result, safe_error_category FROM trustlens.external_enrichment_result"
                                      " WHERE external_enrichment_result_id = %s", (records[0],))[0]
                self.assertEqual(stored, expected)
        self.enable(runtime, EchoProvider(), credentials=None)                               # credential reference unresolvable
        record = enrichment.enrich_evaluation(runtime, evaluation_id)["records"][0]
        self.assertEqual(self.app_sql("SELECT status, safe_error_category FROM trustlens.external_enrichment_result"
                                      " WHERE external_enrichment_result_id = %s", (record,))[0], ("FAILED", "CREDENTIAL_UNAVAILABLE"))
        kinds = {e[0] for e in self.audit_rows(case_id)}
        self.assertTrue({"EGRESS_DENIED", "CREDENTIAL_REFERENCE_FAILURE", "ENRICHMENT_ACCEPTED"} <= kinds)
        self.verify_chain()

    def test_analysts_read_normalized_advisory_records_only(self):
        client, analyst, case_id, _, evaluation_id = self.evaluated()
        runtime = analyst.app.state.auth
        self.enable(runtime, EchoProvider("FOUND", "CLEAN"))
        enrichment.enrich_evaluation(runtime, evaluation_id)
        self.enable(runtime, EchoProvider(failure="TIMEOUT"), {"provider_policy_version": "1.0.9"})
        enrichment.enrich_evaluation(runtime, evaluation_id)
        r = self.listing(analyst, evaluation_id)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assert_schema(body, "EnrichmentListResponse")
        self.assertEqual(len(body["items"]), 4)
        for item in body["items"]:
            self.assert_schema(item, "EnrichmentView")
            self.assertEqual(set(item), {"enrichment_id", "provider_category", "status", "reputation_result", "observed_at", "advisory"})
            self.assertTrue(item["advisory"])
            self.assertEqual(item["provider_category"], "REPUTATION_LOOKUP")
        self.assertEqual({(i["status"], i["reputation_result"]) for i in body["items"]}, {("SUCCEEDED", "CLEAN"), ("TIMED_OUT", "NOT_EVALUATED")})
        self.assertEqual([i["status"] for i in self.listing(analyst, evaluation_id, "?status=TIMED_OUT").json()["items"]], ["TIMED_OUT"] * 2)
        first = self.listing(analyst, evaluation_id, "?limit=3").json()
        rest = self.listing(analyst, evaluation_id, f"?limit=3&cursor={first['page']['next_cursor']}").json()
        self.assertEqual(len({i["enrichment_id"] for i in first["items"] + rest["items"]}), 4)
        for query in ("?status=CLEAN", "?status=succeeded", "?provider=x", "?limit=0"):
            with self.subTest(query=query):
                self.assertEqual(code(self.listing(analyst, evaluation_id, query)), "INVALID_REQUEST")
        self.assertNotIn(SECRET, r.text)
        for forbidden in ("provider_policy_ref", "ecs_locator", "credential", "raw", "lookup.provider-fixture", "indicator"):
            self.assertNotIn(forbidden, r.text)

    def test_unattributable_history_never_presents_a_provider_assertion(self):
        """Codex S7 finding 5: stored rows stay as they are; only resolvable, matching attribution is presented."""
        client, analyst, case_id, _, evaluation_id = self.evaluated()
        runtime = analyst.app.state.auth
        policy = self.enable(runtime, EchoProvider("FOUND", "CLEAN", "ALLOWLISTED"))
        enrichment.enrich_evaluation(runtime, evaluation_id)
        stored = self.app_sql("SELECT status, reputation_result FROM trustlens.external_enrichment_result WHERE evaluation_id = %s",
                              (evaluation_id,))
        result_before = self.result(client, evaluation_id).json()
        views = lambda: self.listing(analyst, evaluation_id).json()["items"]
        self.assertEqual({(i["provider_category"], i["status"], i["reputation_result"]) for i in views()},
                         {("REPUTATION_LOOKUP", "SUCCEEDED", "CLEAN")})                    # attributed: the provider assertion
        runtime.enrichment.active = ()                                                     # withdrawn for new lookups only
        self.assertEqual({i["reputation_result"] for i in views()}, {"CLEAN"})            # history still resolves exactly
        runtime.enrichment.policies.clear()                                                # pinned policy not in the registry
        self.assertEqual({(i["provider_category"], i["status"], i["reputation_result"]) for i in views()},
                         {("NOT_RESOLVED", "SUCCEEDED", "NOT_EVALUATED")})                 # CLEAN withheld, never asserted
        impostor = load_policy({**POLICY, "provider_policy_version": "9.9.9"})
        runtime.enrichment.policies[policy.digest] = impostor                              # same digest, different identity
        self.assertEqual({(i["provider_category"], i["reputation_result"]) for i in views()}, {("NOT_RESOLVED", "NOT_EVALUATED")})
        runtime.enrichment = None                                                           # no registry at all
        self.assertEqual({(i["provider_category"], i["reputation_result"]) for i in views()}, {("NOT_RESOLVED", "NOT_EVALUATED")})
        self.assertEqual(self.app_sql("SELECT status, reputation_result FROM trustlens.external_enrichment_result WHERE evaluation_id = %s",
                                      (evaluation_id,)), stored)                           # the immutable records are unchanged
        self.assertEqual(self.result(client, evaluation_id).json(), result_before)        # and so is the DetectionResult

    def test_replaced_policy_content_at_the_pinned_digest_never_attributes(self):
        """Codex S7 recheck: a registry entry under the stored digest attributes only if its own content digest IS that digest."""
        client, analyst, case_id, _, evaluation_id = self.evaluated()
        runtime = analyst.app.state.auth
        original = self.enable(runtime, EchoProvider("FOUND", "CLEAN", "ALLOWLISTED"))
        enrichment.enrich_evaluation(runtime, evaluation_id)
        stored = self.app_sql("SELECT status, reputation_result, provider_policy_digest FROM trustlens.external_enrichment_result"
                              " WHERE evaluation_id = %s", (evaluation_id,))
        self.assertEqual({row[2] for row in stored}, {original.digest})
        result_before = self.result(client, evaluation_id).json()
        views = lambda: {(i["provider_category"], i["status"], i["reputation_result"]) for i in self.listing(analyst, evaluation_id).json()["items"]}
        self.assertEqual(views(), {("REPUTATION_LOOKUP", "SUCCEEDED", "CLEAN")})            # exact digest, valid policy: accepted
        for name, replacement in (("changed path_prefix", {**dict(original.document), "path_prefix": "/v1/different"}),
                                  ("disabled replacement", {**dict(original.document), "enabled": False})):
            with self.subTest(case=name):
                replacement = load_policy(replacement)
                self.assertEqual((replacement.provider_ref, replacement.provider_policy_ref, replacement.provider_policy_version),
                                 (original.provider_ref, original.provider_policy_ref, original.provider_policy_version))
                self.assertNotEqual(replacement.digest, original.digest)
                runtime.enrichment.policies[original.digest] = replacement                  # the reproduced substitution
                self.assertEqual(views(), {("NOT_RESOLVED", "SUCCEEDED", "NOT_EVALUATED")})   # no trusted SUCCEEDED/CLEAN
        runtime.enrichment.policies[original.digest] = original
        self.assertEqual(views(), {("REPUTATION_LOOKUP", "SUCCEEDED", "CLEAN")})
        self.assertEqual(self.app_sql("SELECT status, reputation_result, provider_policy_digest FROM trustlens.external_enrichment_result"
                                      " WHERE evaluation_id = %s", (evaluation_id,)), stored)        # historical records unchanged
        self.assertEqual(self.result(client, evaluation_id).json(), result_before)        # and the DetectionResult

    def test_users_administrators_and_unassigned_analysts_get_no_enrichment(self):
        client, analyst, case_id, _, evaluation_id = self.evaluated()
        self.assertEqual(self.listing(client, evaluation_id).status_code, 403)              # the owner: visible, not an analyst
        subject, _ = self.provision(roles=("ANALYST",))
        self.assertEqual(self.listing(self.client_for(subject), evaluation_id).status_code, 404)   # not assigned: masked
        admin_subject, _ = self.provision(roles=("ADMINISTRATOR",))
        self.assertEqual(self.listing(self.client_for(admin_subject), evaluation_id).status_code, 404)
        editor, _ = self.provision(roles=("KNOWLEDGE_EDITOR",))
        self.assertEqual(self.listing(self.client_for(editor), evaluation_id).status_code, 404)
        self.assertEqual(self.listing(analyst, str(uuid.uuid4())).status_code, 404)

    def test_replay_never_refetches_and_re_analysis_creates_new_records(self):
        client, analyst, case_id, submission_id, evaluation_id = self.evaluated()
        runtime = analyst.app.state.auth
        provider = EchoProvider("FOUND", "MALICIOUS")
        self.enable(runtime, provider)
        enrichment.enrich_evaluation(runtime, evaluation_id)
        calls = len(provider.calls)
        replay_id = analyst.post(f"/api/v1/evaluations/{evaluation_id}/replays", json={"reason_code": "ANALYST_VERIFICATION"},
                                 headers={"Idempotency-Key": self.new_key()}).json()["replay_id"]
        self.assertEqual(analyst.get(f"/api/v1/replays/{replay_id}").json()["outcome"], "MATCH")
        self.assertEqual(len(provider.calls), calls)                                          # replay: no provider call
        new = self.analyze(client, submission_id, body={"predecessor_evaluation_id": evaluation_id,
                                                        "reason_code": "USER_REQUESTED_REANALYSIS"}).json()["evaluations"][0]["evaluation_id"]
        self.assertEqual(len(provider.calls), calls)                                          # evaluation never waits on a provider
        enrichment.enrich_evaluation(runtime, new)
        self.assertEqual(len(self.rows(new)), 2)
        self.assertEqual(len(self.rows(evaluation_id)), 2)                                    # history kept, nothing overwritten
        subject = self.app_sql("SELECT p.external_subject FROM trustlens.principal_reference p JOIN trustlens.case_access_grant g"
                               " ON g.principal_reference_id = p.principal_reference_id WHERE g.case_record_id = %s"
                               " AND g.grant_kind = 'ASSIGNED_ANALYST'", (case_id,))[0][0]
        restarted = self.client_for(subject)                                                  # a new process: records survive
        self.assertEqual(len(self.listing(restarted, evaluation_id).json()["items"]), 2)


if __name__ == "__main__":
    unittest.main()


class PolicyAttributionTests(unittest.TestCase):
    """attributed_policy without a database: exact content digest first, then the descriptive identity."""
    def setUp(self):
        self.original = load_policy(POLICY)
        self.config = enrichment.EnrichmentRuntime(adapter=None)
        self.config.add(self.original)
        self.identity = (self.original.provider_ref, self.original.provider_policy_ref, self.original.provider_policy_version)

    def attributed(self, digest, identity=None):
        return enrichment.attributed_policy(self.config, digest, *(identity or self.identity))

    def test_only_the_exact_content_digest_attributes(self):
        self.assertIs(self.attributed(self.original.digest), self.original)
        for change in ({"path_prefix": "/v1/different"}, {"enabled": False}, {"retry_safe": False}):
            with self.subTest(change=change):
                replacement = load_policy({**dict(self.original.document), **change})
                self.config.policies[self.original.digest] = replacement
                self.assertIsNone(self.attributed(self.original.digest))
                self.assertIsNone(self.attributed(replacement.digest))                      # not registered under its own digest
                self.config.policies[self.original.digest] = self.original

    def test_missing_or_incorrect_digests_and_identities_are_rejected(self):
        other = "0" * 64
        for digest in (None, "", "abc", self.original.digest.upper(), self.original.digest + "0", other, 7):
            with self.subTest(digest=digest):
                self.assertIsNone(self.attributed(digest))
        self.config.policies[other] = dict(self.original.document)                          # not a governed ProviderPolicy
        self.assertIsNone(self.attributed(other))
        self.assertIsNone(self.attributed(self.original.digest, ("OTHER", *self.identity[1:])))
        self.assertIsNone(self.attributed(self.original.digest, (*self.identity[:2], "9.9.9")))
        self.assertIsNone(enrichment.attributed_policy(None, self.original.digest, *self.identity))

    def test_an_unverifiable_record_is_presented_without_any_provider_assertion(self):
        row = ("e-1", "SUCCEEDED", "CLEAN", NOW, self.original.digest, NOW, *self.identity)
        self.assertEqual(enrichment._view(row, self.config)["reputation_result"], "CLEAN")
        self.config.policies[self.original.digest] = load_policy({**dict(self.original.document), "path_prefix": "/v1/different"})
        view = enrichment._view(row, self.config)
        self.assertEqual((view["provider_category"], view["status"], view["reputation_result"], view["advisory"]),
                         (enrichment.UNRESOLVED_CATEGORY, "SUCCEEDED", "NOT_EVALUATED", True))
        self.assertEqual(set(view), {"enrichment_id", "provider_category", "status", "reputation_result", "observed_at", "advisory"})
