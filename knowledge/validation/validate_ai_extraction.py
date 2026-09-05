"""TrustLens Phase 4 P4-WP3 — offline AI-extraction validation validator.

Proves the strict, atomic, deterministic validation boundary (``knowledge/ai/validation.py``): it accepts a
well-formed, grounded, RuntimeKnowledge-resolved proposal bound to the authoritative current request/input,
and fail-closes on every reviewed defect with the exact typed code from the closed taxonomy. Covers the
independent-review findings directly: complete required observation structure (H1), authoritative request/input
binding (H2), raw-size + nesting-depth containment (H3), deep immutability + detached as_dict (M1), stable
non-overridable error taxonomy (M2), deterministic failure precedence under permutation (M3), and sanitized
diagnostics that never leak raw model values (M4). It calls no Phase-3 code. Fully offline; no network, no API
key, no vendor SDK.

Usage: .venv/bin/python knowledge/validation/validate_ai_extraction.py [--quiet]
Exit 0 only when every assertion passes. NOT wired into run_all (WP7 owns canonical CI).
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path
from types import MappingProxyType

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from knowledge.publish import build_bundle  # noqa: E402
from knowledge.runtime import load_bundle  # noqa: E402
from knowledge.ai import (  # noqa: E402
    AIExtractionValidationError,
    AIGroundingFailedError,
    AISchemaInvalidError,
    MAX_JSON_NESTING_DEPTH,
    MAX_RAW_RESPONSE_BYTES,
    RawAIExtractionResponse,
    ValidatedAIExtraction,
    validate_ai_extraction,
)

REQ_ID = "REQ-1"
INPUT_ID = "IN-1"
NORMALIZED = "Please share the OTP now."
_OTP_START = NORMALIZED.index("OTP")
_OTP_END = _OTP_START + len("OTP")
INPUTS = {INPUT_ID: NORMALIZED, "IN-2": "A different, unrelated submission."}


class Check:
    def __init__(self) -> None:
        self.count = 0
        self.failures: list[str] = []

    def ok(self, condition: bool, message: str) -> None:
        self.count += 1
        if not condition:
            self.failures.append(message)

    def eq(self, got, wanted, message: str) -> None:
        self.ok(got == wanted, f"{message}: got {got!r}, wanted {wanted!r}")

    def raises(self, fn, exc_type, message: str) -> None:
        self.count += 1
        try:
            fn()
            self.failures.append(f"{message}: did not raise")
        except exc_type:
            pass
        except Exception as exc:  # noqa: BLE001
            self.failures.append(f"{message}: raised {type(exc).__name__}, wanted {exc_type.__name__}")

    def raises_code(self, fn, code: str, message: str) -> None:
        self.count += 1
        try:
            fn()
            self.failures.append(f"{message}: did not raise")
        except AIExtractionValidationError as exc:
            if exc.code != code:
                self.failures.append(f"{message}: code {exc.code!r} != {code!r}")
        except Exception as exc:  # noqa: BLE001
            self.failures.append(f"{message}: raised {type(exc).__name__}, wanted AIExtractionValidationError")

    def no_leak(self, fn, sentinel: str, code: str, message: str) -> None:
        """Assert fn() raises the expected typed code, the sentinel appears in NEITHER str(exc) NOR .detail,
        and .detail is <= 256 chars."""
        self.count += 1
        try:
            fn()
            self.failures.append(f"{message}: did not raise")
        except AIExtractionValidationError as exc:
            if exc.code != code:
                self.failures.append(f"{message}: code {exc.code!r} != {code!r}")
            elif sentinel in str(exc) or sentinel in str(exc.detail):
                self.failures.append(f"{message}: sentinel leaked into diagnostic")
            elif len(exc.detail) > 256:
                self.failures.append(f"{message}: detail exceeds 256 chars ({len(exc.detail)})")
        except Exception as exc:  # noqa: BLE001
            self.failures.append(f"{message}: raised {type(exc).__name__}, wanted AIExtractionValidationError")


def _valid_payload() -> dict:
    return {
        "ai_extraction_version": "1.0.0",
        "input_id": INPUT_ID,
        "observations": [{
            "proposal_id": "o1", "observation_type": "AUTHENTICATION_ACTION", "status": "OBSERVED",
            "polarity": "AFFIRMED", "attribution": "FIRST_PARTY", "mood": "DIRECTIVE",
            "source_input_id": INPUT_ID, "start": _OTP_START, "end": _OTP_END, "evidence_excerpt": "OTP",
        }],
        "indicators": [{
            "proposal_id": "i1", "indicator_id": "CREDENTIAL_REQUEST_OTP", "polarity": "POSITIVE",
            "matched": "OBSERVED", "observation_refs": ["o1"], "input_id": INPUT_ID,
        }],
    }


def _raw(payload, request_id: str = REQ_ID) -> RawAIExtractionResponse:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return RawAIExtractionResponse(request_id=request_id, raw_text=text)


class _StubRK:
    """Minimal RuntimeKnowledge-shaped stub for the non-live negative path (no DEPRECATED member exists in the
    real bundle, so a stub is the only offline way to exercise the governed live-status rejection)."""

    def indicator(self, iid):
        return {"id": iid, "polarity": "POSITIVE"} if iid == "CREDENTIAL_REQUEST_OTP" else None

    def negative_indicator(self, iid):
        return {"negative_indicator_id": iid, "status": "DEPRECATED"} if iid == "DEPRECATED_NEG" else None


def run_checks(rk) -> Check:
    c = Check()

    def validate(payload, *, request_id=REQ_ID, expected_request_id=REQ_ID, expected_input_id=INPUT_ID,
                 normalized_inputs=None, use_rk=rk):
        return validate_ai_extraction(
            _raw(payload, request_id=request_id), expected_request_id=expected_request_id,
            expected_input_id=expected_input_id,
            normalized_inputs=INPUTS if normalized_inputs is None else normalized_inputs, rk=use_rk)

    def bad(mutate, code, message):
        p = _valid_payload()
        mutate(p)
        c.raises_code(lambda: validate(p), code, message)

    # ---- good path ----
    out = validate(_valid_payload())
    c.ok(isinstance(out, ValidatedAIExtraction), "well-formed grounded response is accepted")
    c.eq(out.input_id, INPUT_ID, "validated input_id is the authoritative expected input")
    c.ok("evidence_excerpt" not in out.observations[0], "transient evidence_excerpt dropped from validated output")
    c.ok(type(out).__name__ == "ValidatedAIExtraction", "output is proposals, not a governed/decision type")
    empty = {"ai_extraction_version": "1.0.0", "input_id": INPUT_ID, "observations": [], "indicators": []}
    c.eq(len(validate(empty).observations), 0, "zero-item response is a valid (empty) extraction")
    neg = _valid_payload()
    neg["indicators"] = [{"proposal_id": "i1", "indicator_id": "IT_SUPPORT_CONTEXT", "polarity": "NEGATIVE",
                          "matched": "OBSERVED", "observation_refs": ["o1"], "input_id": INPUT_ID}]
    c.eq(len(validate(neg).indicators), 1, "live NEGATIVE-library indicator resolves")

    # ---- H1: complete required observation structure ----
    bad(lambda p: p["observations"][0].pop("polarity"), "AI_SCHEMA_INVALID", "missing polarity rejected")
    bad(lambda p: p["observations"][0].pop("attribution"), "AI_SCHEMA_INVALID", "missing attribution rejected")
    bad(lambda p: p["observations"][0].pop("mood"), "AI_SCHEMA_INVALID", "missing mood rejected")
    c.ok(validate(_valid_payload()).observations[0]["mood"] == "DIRECTIVE", "governed structural values still pass")

    # ---- H2: authoritative request/input binding ----
    c.raises_code(lambda: validate(_valid_payload(), request_id="REQ-OTHER"), "AI_REFERENCE_INVALID",
                  "raw response request_id mismatch rejected")
    # payload names IN-2 (which EXISTS in the map) but expected is IN-1 → AI cannot select another input
    other = _valid_payload()
    other["input_id"] = "IN-2"
    other["observations"][0]["source_input_id"] = "IN-2"
    other["indicators"][0]["input_id"] = "IN-2"
    c.raises_code(lambda: validate(other), "AI_REFERENCE_INVALID",
                  "payload selecting a different (but present) input is rejected")
    bad(lambda p: p["observations"][0].__setitem__("source_input_id", "IN-2"), "AI_REFERENCE_INVALID",
        "observation source_input_id != expected input rejected")
    bad(lambda p: p["indicators"][0].__setitem__("input_id", "IN-2"), "AI_REFERENCE_INVALID",
        "indicator input_id != expected input rejected")
    c.raises_code(lambda: validate(_valid_payload(), expected_input_id="IN-MISSING"), "AI_REFERENCE_INVALID",
                  "expected_input_id absent from authoritative inputs rejected")
    c.ok(isinstance(validate(_valid_payload(), expected_request_id=REQ_ID, expected_input_id=INPUT_ID),
                    ValidatedAIExtraction), "correct authoritative binding passes")

    # ---- H3: raw size limit (BEFORE parse) ----
    oversized = "A" * (MAX_RAW_RESPONSE_BYTES + 10)   # not even valid JSON; size must win before parse
    c.raises_code(lambda: validate(oversized), "AI_RESPONSE_TOO_LARGE", "oversized raw response rejected pre-parse")

    # ---- H3: nesting depth / recursion containment ----
    c.raises_code(lambda: validate("[" * (MAX_JSON_NESTING_DEPTH + 5) + "]" * (MAX_JSON_NESTING_DEPTH + 5)),
                  "AI_RESPONSE_MALFORMED", "excessive nesting depth rejected (typed, not RecursionError)")
    deep = "[" * 6000 + "]" * 6000
    raised_deep = None
    try:
        validate(deep)
    except AIExtractionValidationError as exc:
        raised_deep = exc.code
    except RecursionError:
        raised_deep = "RECURSION_ERROR_ESCAPED"
    c.eq(raised_deep, "AI_RESPONSE_MALFORMED", "very deep JSON is contained (no RecursionError escapes)")

    # ---- strict JSON parse ----
    c.raises_code(lambda: validate(""), "AI_RESPONSE_MALFORMED", "empty payload rejected")
    c.raises_code(lambda: validate("{not valid json"), "AI_RESPONSE_MALFORMED", "invalid JSON rejected")
    c.raises_code(lambda: validate(json.dumps(_valid_payload()) + " trailing"), "AI_RESPONSE_MALFORMED",
                  "trailing junk after JSON rejected")
    c.raises_code(lambda: validate("[]"), "AI_SCHEMA_INVALID", "wrong root type rejected by schema")

    # ---- forbidden decision / confidence fields (recursive) ----
    bad(lambda p: p.__setitem__("classification", "SCAM_PATTERN_DETECTED"), "AI_DECISION_FIELD_REJECTED",
        "top-level decision field rejected")
    bad(lambda p: p["observations"][0].__setitem__("confidence", "HIGH"), "AI_DECISION_FIELD_REJECTED",
        "nested model-confidence field rejected")
    bad(lambda p: p["indicators"][0].__setitem__("fraud_probability", 0.9), "AI_DECISION_FIELD_REJECTED",
        "nested fraud probability rejected")

    # ---- schema / enums / additionalProperties / version / taxonomy closure ----
    bad(lambda p: p["observations"][0].__setitem__("status", "mostly_live"), "AI_SCHEMA_INVALID",
        "unknown status enum rejected")
    bad(lambda p: p["observations"][0].__setitem__("observation_type", "PROBABLY_A_REQUEST"), "AI_SCHEMA_INVALID",
        "unknown observation_type enum rejected")
    bad(lambda p: p["observations"][0].__setitem__("extra_unknown_key", 1), "AI_SCHEMA_INVALID",
        "unknown extra property rejected (additionalProperties:false)")
    bad(lambda p: p.__setitem__("ai_extraction_version", "9.9.9"), "AI_SCHEMA_INVALID", "wrong contract version rejected")
    bad(lambda p: p["indicators"][0].__setitem__("family_ref", "FAM-X"), "AI_SCHEMA_INVALID",
        "AI-authored taxonomy/family reference structurally forbidden (no taxonomy in the contract)")

    # ---- indicator RuntimeKnowledge membership + polarity + non-live ----
    bad(lambda p: p["indicators"][0].__setitem__("indicator_id", "TOTALLY_MADE_UP_IND"), "AI_UNKNOWN_INDICATOR",
        "unknown indicator id rejected")
    bad(lambda p: p["indicators"][0].__setitem__("polarity", "NEGATIVE"), "AI_UNKNOWN_INDICATOR",
        "polarity mismatch (positive id claimed NEGATIVE) rejected")
    dep = _valid_payload()
    dep["indicators"] = [{"proposal_id": "i1", "indicator_id": "DEPRECATED_NEG", "polarity": "NEGATIVE",
                          "matched": "OBSERVED", "observation_refs": ["o1"], "input_id": INPUT_ID}]
    c.raises_code(lambda: validate(dep, use_rk=_StubRK()), "AI_UNKNOWN_INDICATOR",
                  "non-live (DEPRECATED) negative indicator rejected")

    # ---- reference integrity + duplicates ----
    bad(lambda p: p["indicators"][0].__setitem__("observation_refs", ["nope"]), "AI_REFERENCE_INVALID",
        "dangling observation_ref rejected")
    bad(lambda p: p["indicators"][0].__setitem__("observation_refs", []), "AI_REFERENCE_INVALID",
        "OBSERVED indicator with no supporting observation rejected")
    bad(lambda p: p["observations"].append(copy.deepcopy(p["observations"][0])), "AI_REFERENCE_INVALID",
        "duplicate observation proposal_id rejected")

    # ---- grounding (offsets + exact excerpt) ----
    bad(lambda p: p["observations"][0].__setitem__("end", len(NORMALIZED) + 5), "AI_GROUNDING_FAILED",
        "offset end beyond input length rejected")
    bad(lambda p: (p["observations"][0].__setitem__("start", 5), p["observations"][0].__setitem__("end", 5)),
        "AI_GROUNDING_FAILED", "empty span (start >= end) rejected")
    bad(lambda p: p["observations"][0].__setitem__("evidence_excerpt", "XYZ"), "AI_GROUNDING_FAILED",
        "excerpt not matching the source slice rejected")
    bad(lambda p: p["observations"][0].__setitem__("evidence_excerpt", "otp"), "AI_GROUNDING_FAILED",
        "case-different excerpt rejected (exact match only)")

    # ---- M1: deep immutability + detached as_dict + no caller aliasing ----
    def _setitem(m, k, v):
        m[k] = v

    mo = validate(_valid_payload())
    c.ok(isinstance(mo.observations, tuple) and isinstance(mo.indicators, tuple), "collections are tuples")
    c.ok(isinstance(mo.indicators[0]["observation_refs"], tuple), "observation_refs is an immutable tuple")
    c.raises(lambda: _setitem(mo.observations[0], "start", 0), TypeError, "observation map is read-only")
    c.raises(lambda: _setitem(mo.indicators[0], "matched", "X"), TypeError, "indicator map is read-only")
    d = mo.as_dict()
    d["observations"][0]["start"] = 999
    d["indicators"][0]["observation_refs"].append("HACK")
    d2 = mo.as_dict()
    c.ok(d2["observations"][0]["start"] != 999 and "HACK" not in d2["indicators"][0]["observation_refs"],
         "as_dict returns detached copies (mutating the result never mutates the original)")
    src = _valid_payload()
    aliased = validate(src)
    src["observations"][0]["start"] = 999
    c.ok(aliased.observations[0]["start"] != 999, "validated output does not alias the caller payload")

    # ---- M2: stable, non-overridable error taxonomy ----
    c.eq(AIGroundingFailedError("x").code, "AI_GROUNDING_FAILED", "grounding error code fixed")
    c.eq(AISchemaInvalidError("x").code, "AI_SCHEMA_INVALID", "schema error code fixed")
    c.raises(lambda: AISchemaInvalidError("x", code="BOGUS"), TypeError, "constructor cannot override code")
    err = AIGroundingFailedError("x")
    c.raises(lambda: setattr(err, "code", "BOGUS"), AttributeError, ".code is read-only")

    # ---- M3: deterministic failure precedence under array permutation ----
    def _dup_and_bad_grounding(order):
        p = _valid_payload()
        good = p["observations"][0]
        dupe = copy.deepcopy(good)                       # duplicate proposal_id "o1"
        badg = copy.deepcopy(good)
        badg["proposal_id"] = "o2"
        badg["evidence_excerpt"] = "WRONG"               # grounding failure on a distinct item
        p["observations"] = [good, dupe, badg] if order == "A" else [badg, dupe, good]
        p["indicators"][0]["observation_refs"] = ["o1"]
        return p

    codes = []
    for order in ("A", "B"):
        try:
            validate(_dup_and_bad_grounding(order))
        except AIExtractionValidationError as exc:
            codes.append(exc.code)
    c.eq(codes, ["AI_REFERENCE_INVALID", "AI_REFERENCE_INVALID"],
         "duplicate+grounding failure resolves to the SAME code regardless of item order (precedence)")

    # ---- M4: schema-error diagnostics never leak a raw model value ----
    sentinel = "OTP-938271-SECRET"
    leak = _valid_payload()
    leak["observations"][0]["status"] = sentinel        # schema-invalid enum value carrying a secret sentinel
    raised = None
    try:
        validate(leak)
    except AISchemaInvalidError as exc:
        raised = exc
    c.ok(raised is not None and sentinel not in str(raised) and sentinel not in str(raised.detail),
         "schema-invalid raw model value is not echoed in the sanitized diagnostic")

    # ---- FINAL M1: malformed Unicode (lone surrogate) fails typed; no UnicodeEncodeError escapes ----
    c.raises_code(lambda: validate("\ud800" + json.dumps(_valid_payload())), "AI_RESPONSE_MALFORMED",
                  "lone high surrogate rejected typed (no UnicodeEncodeError escapes)")
    c.raises_code(lambda: validate("\udfff"), "AI_RESPONSE_MALFORMED", "lone low surrogate rejected typed")
    c.raises_code(lambda: validate("A" * (MAX_RAW_RESPONSE_BYTES + 1)), "AI_RESPONSE_TOO_LARGE",
                  "ASCII byte-limit still enforced")
    c.raises_code(lambda: validate("€" * (MAX_RAW_RESPONSE_BYTES // 3 + 1)), "AI_RESPONSE_TOO_LARGE",
                  "multibyte UTF-8 byte-limit enforced on byte count")

    # ---- FINAL M2: no public error detail echoes a model-controlled value (sentinel across every path) ----
    SENT = "LEAK-SECRET-938271"          # id-pattern-safe
    SENT_IND = "LEAK_SECRET_938271"      # indicator_id-pattern-safe (uppercase/underscore)

    def _obs_pair(pid):
        base = _valid_payload()["observations"][0]
        a, b = copy.deepcopy(base), copy.deepcopy(base)
        a["proposal_id"] = b["proposal_id"] = pid
        return [a, b]

    dup_obs = _valid_payload()
    dup_obs["observations"] = _obs_pair(SENT)
    dup_obs["indicators"][0]["observation_refs"] = [SENT]
    c.no_leak(lambda: validate(dup_obs), SENT, "AI_REFERENCE_INVALID", "duplicate observation proposal_id sentinel")

    dup_ind = _valid_payload()
    dup_ind["indicators"] = [copy.deepcopy(dup_ind["indicators"][0]), copy.deepcopy(dup_ind["indicators"][0])]
    dup_ind["indicators"][0]["proposal_id"] = dup_ind["indicators"][1]["proposal_id"] = SENT
    c.no_leak(lambda: validate(dup_ind), SENT, "AI_REFERENCE_INVALID", "duplicate indicator proposal_id sentinel")

    def _mut(field_path, value):
        p = _valid_payload()
        obj = p
        for key in field_path[:-1]:
            obj = obj[key]
        obj[field_path[-1]] = value
        return p

    c.no_leak(lambda: validate(_mut(["indicators", 0, "indicator_id"], SENT_IND)), SENT_IND,
              "AI_UNKNOWN_INDICATOR", "unknown indicator_id sentinel")
    c.no_leak(lambda: validate(_mut(["observations", 0, "source_input_id"], SENT)), SENT,
              "AI_REFERENCE_INVALID", "wrong source_input_id sentinel")
    c.no_leak(lambda: validate(_mut(["indicators", 0, "input_id"], SENT)), SENT,
              "AI_REFERENCE_INVALID", "wrong indicator input_id sentinel")
    c.no_leak(lambda: validate(_mut(["indicators", 0, "observation_refs"], [SENT])), SENT,
              "AI_REFERENCE_INVALID", "dangling observation_ref sentinel")
    c.no_leak(lambda: validate(_mut(["observations", 0, "evidence_excerpt"], SENT)), SENT,
              "AI_GROUNDING_FAILED", "grounding excerpt sentinel")
    c.no_leak(lambda: validate(_mut(["observations", 0, "status"], SENT)), SENT,
              "AI_SCHEMA_INVALID", "schema-invalid value sentinel")

    # ---- FINAL M2: .detail length invariant (off-by-one fixed) ----
    c.eq(len(AISchemaInvalidError("x" * 255).detail), 255, "detail 255 preserved")
    c.eq(len(AISchemaInvalidError("x" * 256).detail), 256, "detail 256 preserved")
    c.ok(len(AISchemaInvalidError("x" * 257).detail) <= 256, "detail 257 capped to <=256")
    c.ok(len(AISchemaInvalidError("x" * 100_000).detail) <= 256, "very long detail capped to <=256")

    # ---- atomicity: one bad item among valid → entire response rejected ----
    atomic = _valid_payload()
    atomic["observations"].append({
        "proposal_id": "o2", "observation_type": "THREAT", "status": "OBSERVED", "polarity": "AFFIRMED",
        "attribution": "FIRST_PARTY", "mood": "DIRECTIVE", "source_input_id": INPUT_ID,
        "start": 0, "end": 6, "evidence_excerpt": "Please"})
    atomic["indicators"].append({"proposal_id": "i2", "indicator_id": "TOTALLY_MADE_UP_IND", "polarity": "POSITIVE",
                                 "matched": "OBSERVED", "observation_refs": ["o2"], "input_id": INPUT_ID})
    raised = None
    try:
        validate(atomic)
    except AIExtractionValidationError as exc:
        raised = exc
    c.ok(raised is not None and raised.code == "AI_UNKNOWN_INDICATOR",
         "one invalid item rejects the entire response (atomic, no partial acceptance)")

    return c


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P4-WP3 offline AI-extraction validation validator")
    parser.add_argument("--quiet", action="store_true", help="suppress the summary line")
    args = parser.parse_args(argv)

    try:
        with tempfile.TemporaryDirectory(prefix="wp3-ai-extraction-") as tmp:
            bundle_dir = Path(tmp) / "bundle"
            build_bundle.build(bundle_dir)
            rk = load_bundle(bundle_dir)
            checks = run_checks(rk)
    except Exception as exc:  # noqa: BLE001
        print(f"P4-WP3 AI EXTRACTION: ERROR — {type(exc).__name__}: {exc}")
        return 2

    passed = checks.count - len(checks.failures)
    if not args.quiet:
        print(f"{passed}/{checks.count} extraction-validation assertions passed.")
    if checks.failures:
        print(f"P4-WP3 AI EXTRACTION: FAIL — {len(checks.failures)} assertion(s) failed")
        for f in checks.failures:
            print(f"  - {f}")
        return 1
    print("P4-WP3 AI EXTRACTION: PASS — strict, atomic, deterministic validation of untrusted AI responses with "
          "authoritative request/input binding, raw-size + nesting-depth containment, complete structural "
          "requirements, RuntimeKnowledge membership, exact grounding, deep immutability, a closed non-overridable "
          "error taxonomy, deterministic precedence and sanitized diagnostics. Not governed; G-09 OPEN.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
