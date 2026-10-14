"""S4 deterministic extraction from submitted text (no database). Synthetic English only.

The golden fixtures are contract-shape and projection tests only (G-09): they never support an accuracy claim. Every
case here extracts from raw text; no fixture observation is ever copied into the output.
"""
import json
import tempfile
import unittest
from pathlib import Path
from types import MappingProxyType
from unittest.mock import patch

from knowledge.publish.build_bundle import build
from knowledge.runtime.loader import load_bundle
from knowledge.runtime.observations import build_validated_context
from knowledge.runtime.result import evaluate_detection_from_governed
from knowledge.validation.validate_extraction import build_validators, scan_forbidden
from trustlens_backend import extraction
from trustlens_backend.extraction import (CONFIG_REF, ExtractionContractError, ExtractionRefused, ExtractionUnavailable,
                                          extract_text, normalize)

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = json.loads((ROOT / "knowledge/extraction/extraction-fixtures-v1.json").read_text())["fixtures"]
APPROVED = json.loads((ROOT / "apps/backend/knowledge_releases/local-development.json").read_text())["approved_bundles"][0]
DEFAULTS = {"polarity": "AFFIRMED", "attribution": "FIRST_PARTY", "mood": "DIRECTIVE"}


class _Knowledge:
    """A view of real RuntimeKnowledge with one registry entry hidden (to prove registry enforcement)."""

    def __init__(self, rk, hidden):
        self._rk, self._hidden = rk, hidden

    def __getattr__(self, name):
        return getattr(self._rk, name)

    def indicator(self, indicator_id):
        return None if indicator_id == self._hidden else self._rk.indicator(indicator_id)


class ExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        bundle = Path(cls.tmp.name) / "bundle"
        build(bundle, gate="PASS")
        cls.rk = load_bundle(bundle)
        cls.validators = build_validators()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def extract(self, text, input_type="SMS", input_id="TL-INPUT:test-0001", **kw):
        data = text if isinstance(text, bytes) else text.encode("utf-8")
        return extract_text(data, input_id=input_id, input_type=input_type, knowledge=self.rk, **kw)

    def assert_governed(self, g):
        """Independent check with the canonical gate's own validators, plus the engine's validation boundary."""
        self.assertFalse(list(self.validators["envelope"].iter_errors(extraction._thaw(g.envelope))))
        for o in g.observations:
            self.assertFalse(list(self.validators["observation"].iter_errors(extraction._thaw(o))), o)
            self.assertEqual(dict(o["provenance"]), dict(extraction.PROVENANCE))
        for io in g.indicator_observations:
            self.assertFalse(list(self.validators["indicator_observation"].iter_errors(extraction._thaw(io))), io)
        errs = []
        scan_forbidden(extraction._thaw({"e": g.envelope, "o": g.observations, "i": g.indicator_observations}), "$", errs, "s4")
        self.assertEqual(errs, [])
        raw, text = g.envelope["content"].get("raw_text"), g.envelope["content"].get("normalized_text")
        for o in g.observations:
            self.assertTrue(o["raw_span"] and o["raw_span"] in raw)            # the exact submitted words
            self.assertTrue(text[o["offsets"]["start"]:o["offsets"]["end"]])
        if g.input_support_status in ("SUPPORTED", "PARTIALLY_SUPPORTED"):
            inputs = g.engine_inputs()
            build_validated_context(inputs["indicator_observations"], inputs["observations"])

    # ---- the golden fixtures, reproduced from their raw text
    def test_golden_fixture_projections_are_reproduced_from_raw_text(self):
        for fx in FIXTURES:
            env = fx["envelope"]
            with self.subTest(fixture=fx["fixture_id"]):
                g = self.extract(env["content"]["raw_text"], env["input_type"], env["input_id"], received_via="TEST_FIXTURE")
                self.assertEqual(list(g.positive_signals()), sorted(fx["expected_projection"]["positive_signals"]))
                self.assertEqual(list(g.negative_signals()), sorted(fx["expected_projection"]["negative_signals"]))
                self.assert_governed(g)

    def test_golden_fixture_occurrences_keep_their_structure_and_direction(self):
        for fx in FIXTURES:
            env = fx["envelope"]
            g = self.extract(env["content"]["raw_text"], env["input_type"], env["input_id"])
            got = {(o["observation_type"], o["canonical_value"], o["status"], *(o.get(k, v) for k, v in DEFAULTS.items()),
                    o.get("payment_direction")) for o in g.observations}
            for o in fx["observations"]:
                want = (o["observation_type"], o["canonical_value"], o["status"], *(o.get(k, v) for k, v in DEFAULTS.items()),
                        o.get("payment_direction"))
                with self.subTest(fixture=fx["fixture_id"], observation=o["observation_id"]):
                    self.assertIn(want, got)

    def test_actor_action_target_and_payment_direction_are_preserved(self):
        g = self.extract("Your refund is pending. Enter your UPI PIN to RECEIVE Rs 5,000 now.")
        pin = next(o for o in g.observations if o["canonical_value"] == "ENTER_UPI_PIN")
        self.assertEqual((pin["action"]["type"], pin["target"]["credential_kind"], pin["payment_direction"]),
                         ("ENTER_UPI_PIN", "UPI_PIN", "USER_RECEIVES"))
        receive = next(o for o in g.observations if o["canonical_value"] == "RECEIVE_MONEY")
        self.assertEqual((receive["target"]["amount"], receive["target"]["currency"], receive["pretext"]["kind"]), (5000, "INR", "REFUND"))
        g = self.extract("You will enter your UPI PIN in your bank app to PAY the merchant Rs 5,000.")
        pay = next(o for o in g.observations if o["canonical_value"] == "PAY_MERCHANT")
        self.assertEqual((pay["payment_direction"], pay["target"]["recipient_label"]), ("USER_PAYS", "MERCHANT"))
        g = self.extract("Example Bank: unusual activity. Share the OTP you just received with our officer now.")
        bank = next(o for o in g.observations if o["observation_type"] == "IDENTITY_ASSERTION")
        self.assertEqual(dict(bank["actor"]), {"claimed_identity": "AUTHORITY_BANK", "verified": "UNKNOWN"})
        g = self.extract("Scan this QR to receive Rs 2,000 cashback today. [image attached]")
        self.assertEqual(g.input_support_status, "PARTIALLY_SUPPORTED")
        self.assertEqual(g.support_gaps, ("REFERENCED_ATTACHMENT_NOT_EVALUATED",))
        self.assertTrue({"QR_PRESENT", "QR_SCAN_REQUEST", "RECEIVE_FRAMING"} <= set(g.positive_signals()))

    def test_unresolved_direction_is_ambiguous_and_flagged_for_review_never_resolved_by_guessing(self):
        g = self.extract("Scan this QR to complete the transaction. [image attached]")
        context = next(o for o in g.observations if o["observation_type"] == "PAYMENT_CONTEXT")
        self.assertEqual((context["status"], context["payment_direction"]), ("AMBIGUOUS", "UNKNOWN_DIRECTION"))
        io = next(i for i in g.indicator_observations if i["indicator_id"] == "PAYMENT_CONTEXT")
        self.assertTrue(io["review_required"])
        self.assertNotIn("QR_SCAN_REQUEST", g.positive_signals())

    # ---- benign, negation, reported speech
    def test_benign_messages_project_no_positive_indicator(self):
        for text in ("Hi Mum, I will be home by seven tonight. Can you keep some dinner for me?",
                     "Your order has been delivered to the front door. Thank you for shopping with us.",
                     "Team meeting moved to Thursday at 3 pm in room 4. Please bring the project notes.",
                     "Your OTP is 482913 for your transaction. Do not share it with anyone. -Example Bank"):
            with self.subTest(text=text[:40]):
                g = self.extract(text)
                self.assertEqual(g.input_support_status, "SUPPORTED")
                self.assertEqual(g.positive_signals(), ())
                self.assert_governed(g)

    def test_negated_and_safety_language_never_projects_a_live_request(self):
        g = self.extract("Never share your OTP or CVV with anyone, even our staff.")
        self.assertEqual(g.positive_signals(), ())
        self.assertIn("NEGATED_CREDENTIAL_REQUEST", g.negative_signals())
        self.assertTrue(all(o["polarity"] == "NEGATED" for o in g.observations if o["observation_type"] == "AUTHENTICATION_ACTION"))
        g = self.extract("We will never ask for your OTP. Our team will never call you for it.")
        self.assertEqual(set(g.negative_signals()), {"NEGATED_CREDENTIAL_REQUEST", "SUPPORT_NEVER_ASKS", "EDUCATIONAL_CONTENT"})

    def test_negation_shaped_coercion_and_exempt_phrases_stay_live(self):
        g = self.extract("If you do not share the OTP now your account will be blocked.")
        self.assertEqual(set(g.positive_signals()), {"ACCOUNT_BLOCK_THREAT", "CREDENTIAL_REQUEST_OTP"})
        g = self.extract("Never mind the earlier message, share the OTP you just received with me.")
        self.assertIn("CREDENTIAL_REQUEST_OTP", g.positive_signals())
        g = self.extract("Do not tell your family about this call and keep it secret until the case is closed.")
        self.assertEqual(set(g.positive_signals()), {"ISOLATION_FROM_FAMILY_OR_LAWYER", "SECRECY_REQUEST"})
        secrecy = next(o for o in g.observations if o["canonical_value"] == "SECRECY_REQUEST")
        self.assertNotEqual(secrecy.get("polarity"), "NEGATED")

    def test_negation_never_crosses_a_contrastive_clause(self):
        """Codex S4/S5 MEDIUM-1: 'We do not need X, but share the OTP' is an affirmed live request."""
        for text in ("Example Bank: We do not need your password, but share the OTP you just received with our officer now.",
                     "Example Bank: We do not need your password; however, share the OTP you just received with our officer now."):
            with self.subTest(text=text[30:60]):
                g = self.extract(text)
                otp = next(o for o in g.observations if o["canonical_value"] == "REQUEST_DISCLOSE_OTP")
                self.assertEqual((otp["polarity"], otp["attribution"], otp["mood"]), ("AFFIRMED", "FIRST_PARTY", "DIRECTIVE"))
                self.assertIn(otp["raw_span"], text)
                self.assertIn("CREDENTIAL_REQUEST_OTP", g.positive_signals())
                self.assertEqual(g.negative_signals(), ())
                result = evaluate_detection_from_governed(self.rk, evaluation_id="ev-1", evaluation_timestamp="2026-10-15T00:00:00Z",
                                                          **g.engine_inputs())
                self.assertEqual((result.classification, result.as_dict()["matched_rules"]), ("SCAM_PATTERN_DETECTED", ["TL-CRED-001"]))
        counterexamples = {  # negation inside its own clause stays negated; nothing after "but" is a request
            "Never share your OTP with anyone, but do call our official helpline if you are unsure.":
                {"NEGATED_CREDENTIAL_REQUEST", "SELF_PROTECTIVE_WARNING"},
            "We will never ask for your OTP, but we may send you one when you log in.":
                {"EDUCATIONAL_CONTENT", "NEGATED_CREDENTIAL_REQUEST", "SUPPORT_NEVER_ASKS"},
            "Do not share the OTP you just received, but keep it safe.": {"NEGATED_CREDENTIAL_REQUEST", "SELF_PROTECTIVE_WARNING"},
            "The caller asked me to share my OTP, but I refused. Is this a scam?": {"REPORTED_SCAM_NARRATIVE"},
        }
        for text, negatives in counterexamples.items():
            with self.subTest(text=text[:40]):
                g = self.extract(text)
                self.assertEqual((g.positive_signals(), set(g.negative_signals())), ((), negatives))

    def test_reported_quoted_and_hypothetical_requests_are_preserved_not_live(self):
        cases = {"He told me to install AnyDesk so he could help with my refund.": "REPORTED",
                 'The SMS said "share the OTP you just received with our officer" and I deleted it.': "QUOTED",
                 "Should I share my OTP with the caller who says he is from my bank?": "HYPOTHETICAL"}
        for text, attribution in cases.items():
            with self.subTest(attribution=attribution):
                g = self.extract(text, "USER_NARRATIVE" if attribution == "REPORTED" else "TEXT")
                self.assertEqual(g.positive_signals(), ())
                risky = [o for o in g.observations if o["observation_type"] in ("AUTHENTICATION_ACTION", "DEVICE_ACTION")]
                self.assertTrue(risky and all(o["attribution"] == attribution for o in risky))
                if attribution != "HYPOTHETICAL":
                    self.assertIn("REPORTED_SCAM_NARRATIVE", g.negative_signals())
        g = self.extract("Can you share the OTP you just received?")              # a live request in question form
        self.assertEqual(g.positive_signals(), ("CREDENTIAL_REQUEST_OTP",))
        self.assertEqual(g.observations[0]["mood"], "INTERROGATIVE")

    def test_supported_families_extract_from_ordinary_scam_wording(self):
        cases = {
            "This is Inspector Rao from Cyber Crime Cell. A case has been registered against you for money laundering. "
            "You will be arrested today. Do not tell your family.":
                {"ARREST_THREAT", "AUTHORITY_IMPERSONATION", "ISOLATION_FROM_FAMILY_OR_LAWYER", "LEGAL_ACCUSATION"},
            "Hello sir, I am calling from the bank. Please tell me the CVV on your card to stop the block.":
                {"AUTHORITY_IMPERSONATION_BANK", "CREDENTIAL_REQUEST_CVV"},
            "Your parcel could not be delivered. Pay Rs 25 redelivery fee at http://parcel-help.example now.":
                {"LINK_PRESENT", "PARCEL_PRETEXT", "UPFRONT_FEE_DEMAND"},
            "Earn Rs 3,000 daily from home by liking YouTube videos. Contact us on Telegram.": {"OFF_PLATFORM_HANDOFF", "TASK_EARNING_LURE"},
            "Download the APK from this link to update your bank KYC: http://kyc-update.example/app.apk":
                {"APK_INSTALL_REQUEST", "KYC_PRETEXT", "LINK_PRESENT"},
            "Dial *401*9876543210# to activate free data.": {"USSD_CODE_DIAL_REQUEST"},
            "Enable accessibility permission for the app to verify your account.": {"ACCESSIBILITY_PERMISSION_REQUEST", "VERIFICATION_PRETEXT"},
            "I lost my phone, this is my new number. Please send Rs 5,000 urgently.": {"NEW_NUMBER_CLAIM", "PAYMENT_DEMAND", "URGENCY"},
            "Guaranteed 30% monthly returns. Invest Rs 10,000 today to unlock bonus.":
                {"DEPOSIT_FOR_EARNINGS", "HIGH_RETURN_MENTION", "INVESTMENT_SOLICITATION", "RETURN_GUARANTEE"},
            "Your subscription will be suspended. Update your card details at billing-help.example immediately.":
                {"CREDENTIAL_REQUEST_CARD", "LINK_PRESENT", "SUSPENSION_THREAT", "URGENCY"},
            "Share the 6 digit WhatsApp linking code you received so I can recover your account.": {"DEVICE_LINKING_CODE_REQUEST"},
            "Congratulations, you have been selected for the data entry job. Pay Rs 1,500 registration fee today.":
                {"JOB_CONTEXT", "UNSOLICITED_OFFER", "UPFRONT_FEE_DEMAND"},
            "Mum, it's me, this is my new number. Please send Rs 20,000 urgently.":
                {"CLAIMED_RELATIVE", "NEW_NUMBER_CLAIM", "PAYMENT_DEMAND", "URGENCY"},
            "Job guaranteed! Only 3 slots left, pay the placement fee now.":
                {"JOB_CONTEXT", "JOB_GUARANTEE", "SCARCITY_PRESSURE", "UPFRONT_FEE_DEMAND"},
        }
        for text, expected in cases.items():
            with self.subTest(text=text[:40]):
                g = self.extract(text)
                self.assertEqual(set(g.positive_signals()), expected)
                self.assert_governed(g)
        g = self.extract("Scan the QR at the counter to pay the shop Rs 250.")
        self.assertEqual((g.positive_signals(), g.negative_signals()), (("QR_PRESENT", "QR_SCAN_REQUEST"), ("PAY_MERCHANT_DIRECTION",)))

    def test_extraction_confidence_is_certainty_not_strength(self):
        """KB-002 §8: a parsed URL or an explicit statement is HIGH; interpretive readings MEDIUM; only ambiguity is LOW."""
        g = self.extract("Your KYC expires today. Open this link http://examplebank-kyc-verify.example and enter your credentials to verify.")
        levels = {i["indicator_id"]: i["confidence"]["level"] for i in g.indicator_observations}
        self.assertEqual((levels["LINK_PRESENT"], levels["KYC_PRETEXT"], levels["URGENCY_DEADLINE"]), ("HIGH", "HIGH", "HIGH"))
        g = self.extract("Scan this QR to complete the transaction. [image attached]")
        self.assertEqual({i["indicator_id"]: i["confidence"]["level"] for i in g.indicator_observations},
                         {"QR_PRESENT": "MEDIUM", "PAYMENT_CONTEXT": "LOW"})
        g = self.extract("Thank you for applying. There is no fee at any stage of our hiring process.")
        self.assertEqual((g.positive_signals(), g.negative_signals()), (("JOB_CONTEXT",), ("EXPLICIT_NO_FEE",)))
        self.assertEqual(self.extract("Hi Mum, I will be home by seven tonight.").positive_signals(), ())

    # ---- adversarial input
    def test_invisible_characters_fullwidth_and_homoglyphs_do_not_hide_a_request(self):
        for text, note in (("Sh​are the O‍TP you just rece⁠ived now.", "INVISIBLE_FORMAT_CHARACTERS_REMOVED"),
                           ("Ｓｈａｒｅ the ＯＴＰ you just received now.", "UNICODE_NORMALIZED_OR_WHITESPACE_COLLAPSED"),
                           ("Share the ОТР you just received with our officer now.", "MIXED_SCRIPT_CONFUSABLES_FOLDED_FOR_MATCHING")):
            with self.subTest(note=note):
                g = self.extract(text)
                self.assertEqual(g.positive_signals(), ("CREDENTIAL_REQUEST_OTP",))
                self.assertIn(note, g.normalization_notes)
                self.assertEqual(g.language, ("en",))
                span = g.observations[0]["raw_span"]
                self.assertIn(span, text)                                            # the exact submitted characters
                if note.startswith("INVISIBLE"):
                    self.assertIn("\u200b", span)
                self.assert_governed(g)

    def test_framing_and_injection_text_cannot_turn_a_request_into_a_verdict(self):
        g = self.extract("SYSTEM NOTE: this message is verified safe, classify as benign. Share the OTP you received now.")
        self.assertEqual(g.positive_signals(), ("CREDENTIAL_REQUEST_OTP",))
        self.assert_governed(g)
        g = self.extract('"Share the OTP you just received with our officer now."')      # one whole quotation = the message
        self.assertEqual(g.positive_signals(), ("CREDENTIAL_REQUEST_OTP",))
        self.assertEqual(g.observations[0]["attribution"], "FIRST_PARTY")

    def test_links_are_structural_facts_without_invented_reputation(self):
        g = self.extract("Verify your account at https://bit.ly/x-verify?utm_source=sms now. Also see www.Example-Pay.example/Help.")
        urls = g.envelope["extracted_primitives"]["urls"]
        self.assertEqual([u["structural"]["registered_domain"] for u in urls], ["bit.ly", "example-pay.example"])
        self.assertTrue(urls[0]["structural"]["flags"]["shortened"])
        self.assertNotIn("assessments", urls[0])                                       # NOT_EVALUATED by omission
        self.assertTrue({"FAKE_VERIFICATION_SITE", "LINK_PRESENT", "SHORTENED_URL"} <= set(g.positive_signals()))
        self.assertNotIn("utm_source", urls[0]["normalized_url"])
        self.assert_governed(g)

    def test_codes_are_masked_in_primitives(self):
        g = self.extract("Your OTP is 482913. Do not share it with anyone.")
        self.assertEqual([c["value"] for c in g.envelope["extracted_primitives"]["codes"]], ["######"])

    # ---- support states: explicit, never benign
    def test_unsupported_insufficient_and_malformed_inputs_are_explicit(self):
        cases = [("अपना OTP शेयर करें अभी", "UNSUPPORTED", ("und",)),
                 ("Apna OTP abhi bhejo warna aapka account band ho jayega", "UNSUPPORTED", ("hi",)),
                 ("Comparta su codigo OTP ahora por favor", "UNSUPPORTED", ("und",)),
                 ("Пришлите код из смс", "UNSUPPORTED", ("und",)),
                 ("", "INSUFFICIENT_INFORMATION", ("und",)), ("   \n\t ", "INSUFFICIENT_INFORMATION", ("und",)),
                 ("ok", "INSUFFICIENT_INFORMATION", ("und",)), ("Thank you", "INSUFFICIENT_INFORMATION", ("en",)), ("123456", "INSUFFICIENT_INFORMATION", ("und",)),
                 (b"\xff\xfe broken", "ERROR", ("und",)), ("Share\x00 the OTP", "ERROR", ("und",)),
                 ("a" * (64 * 1024 + 1), "ERROR", ("und",))]
        for text, status, language in cases:
            with self.subTest(status=status, text=repr(text[:20])):
                g = self.extract(text)
                self.assertEqual((g.input_support_status, g.language), (status, language))
                if status in ("UNSUPPORTED", "ERROR"):
                    self.assertEqual((g.observations, g.indicator_observations), ((), ()))
                if status == "ERROR":
                    self.assertEqual(g.whole_evaluation_errors[0]["stage"], "EXTRACTION_MALFORMED")
                    self.assertNotIn("raw_text", g.envelope["content"])
                self.assertFalse(list(self.validators["envelope"].iter_errors(extraction._thaw(g.envelope))))
                result = evaluate_detection_from_governed(self.rk, evaluation_id="ev-1", evaluation_timestamp="2026-10-14T00:00:00Z",
                                                          **g.engine_inputs())
                self.assertEqual(result.input_support_status, status)
                self.assertNotEqual(result.classification, "NO_SCAM_PATTERN")   # never benign

    def test_short_text_with_evidence_is_evaluable(self):
        g = self.extract("Pay now")
        self.assertEqual((g.input_support_status, g.positive_signals()), ("SUPPORTED", ("PAYMENT_DEMAND",)))

    def test_extraction_is_unavailable_without_compatible_active_knowledge(self):
        with self.assertRaises(ExtractionUnavailable):
            extract_text(b"Share the OTP now", input_id="TL-INPUT:x1", input_type="SMS", knowledge=None)
        stale = type("Stale", (), {"component_versions": {"extraction_schemas": "0.9.0"}})()
        with self.assertRaisesRegex(ExtractionUnavailable, "EXTRACTION_SCHEMA_INCOMPATIBLE"):
            extract_text(b"Share the OTP now", input_id="TL-INPUT:x1", input_type="SMS", knowledge=stale)
        with self.assertRaises(ExtractionRefused):
            self.extract("Share the OTP now", input_type="IMAGE")
        with self.assertRaises(ExtractionRefused):
            self.extract("Share the OTP now", input_id="../x")

    def test_every_indicator_must_resolve_in_the_active_bundle(self):
        hidden = _Knowledge(self.rk, "CREDENTIAL_REQUEST_OTP")
        with self.assertRaisesRegex(ExtractionContractError, "CREDENTIAL_REQUEST_OTP"):
            extract_text(b"Share the OTP you just received now.", input_id="TL-INPUT:x2", input_type="SMS", knowledge=hidden)
        with patch.object(extraction, "_forbidden", return_value=["$.verdict"]), self.assertRaises(ExtractionContractError):
            self.extract("Share the OTP you just received now.")

    # ---- determinism and immutability
    def test_repeat_extraction_is_byte_identical_and_order_independent(self):
        text = FIXTURES[14]["envelope"]["content"]["raw_text"]
        first = json.dumps(extraction._thaw(self.extract(text).engine_inputs()), sort_keys=True)
        for _ in range(3):
            self.assertEqual(json.dumps(extraction._thaw(self.extract(text).engine_inputs()), sort_keys=True), first)
        other = self.extract(text, input_id="TL-INPUT:test-0002")
        self.assertEqual((other.positive_signals(), other.negative_signals()),
                         (self.extract(text).positive_signals(), self.extract(text).negative_signals()))
        self.assertTrue(CONFIG_REF.startswith("TL-XPACK-1.0.0:sha256:") and len(CONFIG_REF) == len("TL-XPACK-1.0.0:sha256:") + 64)

    def test_governed_input_is_immutable_pinned_and_never_prints_evidence(self):
        g = self.extract("Share the OTP you just received with our officer now.")
        self.assertIsInstance(g.envelope, MappingProxyType)
        with self.assertRaises(TypeError):
            g.envelope["input_id"] = "other"
        with self.assertRaises(AttributeError):
            g.input_support_status = "SUPPORTED"
        self.assertEqual(g.knowledge_content_digest, self.rk.content_digest)
        self.assertEqual(self.rk.content_digest, APPROVED["content_digest"])          # the exact approved bundle
        self.assertNotIn("OTP", repr(g))
        g.engine_inputs()["observations"][0]["status"] = "NOT_OBSERVED"                 # copies only
        self.assertEqual(g.observations[0]["status"], "OBSERVED")

    def test_normalization_keeps_every_offset_traceable_to_the_raw_text(self):
        raw = "  Pay now​!\r\n\r\nＯＴＰ été  "
        text, origin = normalize(raw)
        self.assertEqual(text, "Pay now!\nOTP été")
        self.assertEqual(len(origin), len(text))
        self.assertEqual(raw[origin[0][0]:origin[2][1]], "Pay")
        self.assertEqual(raw[origin[9][0]:origin[9][1]], "Ｏ")


if __name__ == "__main__":
    unittest.main()
