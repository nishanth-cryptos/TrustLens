"""TrustLens Phase 3 P3-WP8 — engine integration + final DetectionResult contract validator.

Proves the production integration boundary (``knowledge/runtime/result.evaluate_detection_from_governed``)
assembles ONE immutable, JSON-Schema-valid, semantically-valid, fully-provenance-pinned ``DetectionResult``
(detection-result.schema.json, 1.1.0) from the already-complete WP3→WP6 runtime, adding ZERO detection
semantics. It builds ONE real immutable bundle, drives representative governed fixtures through the public API,
and asserts the final envelope, its trust boundaries, provenance pinning, privacy minimisation, determinism and
fail-closed behaviour. It does NOT re-run WP7's 580 decision assertions — WP7 remains authoritative for the 15
golden decisions; WP8 proves the ENVELOPE.

Offline by construction (no network/subprocess imports); builds the bundle in a TemporaryDirectory and reuses
the WP7 governed fixture adapter. G-09 remains open — no accuracy/precision/recall claim.

Usage: .venv/bin/python knowledge/validation/validate_wp8_integration.py [--quiet]
Exit 0 only when every integration assertion passes.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from knowledge.publish import build_bundle  # noqa: E402
from knowledge.runtime import (  # noqa: E402
    ENGINE_VERSION,
    BundleLoadError,
    DetectionResult,
    DetectionResultError,
    ExplanationResult,
    aggregate_decision,
    build_explanation,
    evaluate_decision_from_governed,
    evaluate_detection_from_governed,
    load_bundle,
)
from knowledge.runtime import result as result_mod  # noqa: E402
from knowledge.runtime.engine import ENGINE_VERSION_RE  # noqa: E402
from knowledge.runtime.evaluator import EvaluationProfile  # noqa: E402
from knowledge.validation.validate_wp7_golden_runner import (  # noqa: E402
    _adapt_fixture,
    _case_execution_input,
)

GOLDEN = ROOT / "docs" / "03-detection" / "golden-decision-cases-v1.json"
_TS = "2026-09-05T10:00:00Z"
_PROV = {"extractor_id": "wp8-integration-fixture", "extractor_type": "USER_SUPPLIED", "extractor_version": "1.0.0"}


class Check:
    def __init__(self) -> None:
        self.count = 0
        self.failures: list[str] = []

    def ok(self, condition: bool, message: str) -> None:
        self.count += 1
        if not condition:
            self.failures.append(message)

    def eq(self, got: Any, wanted: Any, message: str) -> None:
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
        except DetectionResultError as exc:
            if exc.code != code:
                self.failures.append(f"{message}: code {exc.code!r} != {code!r}")
        except Exception as exc:  # noqa: BLE001
            self.failures.append(f"{message}: raised {type(exc).__name__}, wanted DetectionResultError")

    def raises_non_wp8(self, fn, message: str) -> None:
        """Assert an UPSTREAM typed failure propagates (not caught-all into a DetectionResult / WP8 error)."""
        self.count += 1
        try:
            fn()
            self.failures.append(f"{message}: did not raise (would be a benign result)")
        except DetectionResultError as exc:
            self.failures.append(f"{message}: wrapped upstream error into WP8 {exc.code}")
        except Exception:  # noqa: BLE001 — an upstream typed failure is the expected fail-closed behaviour
            pass


# ---------------------------------------------------------------- fixtures


def _wp8_inputs(case: Mapping[str, Any]):
    """Governed observations + envelope arrays + derived support for a golden case (reuses the WP7 adapter)."""
    fx = _adapt_fixture(_case_execution_input(case))
    return (list(fx.indicator_observations), list(fx.normalized_observations),
            list(case["language"]), list(case["script"]), fx.support_status)


def _obs(oid: str) -> dict:
    return {"observation_id": oid, "observation_type": "CLAIM", "source_input_id": "SUPP-input",
            "status": "OBSERVED", "polarity": "AFFIRMED", "attribution": "FIRST_PARTY", "mood": "DIRECTIVE",
            "provenance": dict(_PROV)}


def _io(iid: str, ref: str, polarity: str = "POSITIVE") -> dict:
    return {"indicator_id": iid, "polarity": polarity, "matched": "OBSERVED", "confidence": {"level": "HIGH"},
            "observation_refs": [ref], "input_id": "SUPP-input", "provenance": dict(_PROV)}


def _suppressed_fixture() -> tuple[list[dict], list[dict]]:
    """A synthetic governed fixture that legitimately drives the PUBLISHED rule TL-JOB-001 to a live SUPPRESSED
    state: UPFRONT_FEE_DEMAND (PAYMENT_ACTION) + JOB_CONTEXT (PRETEXT) MATCH it, then the SUPPRESS_RULE
    negative indicator EXPLICIT_NO_FEE cancels it (the job family carries no hard-risk override to block it).
    Not a golden case; the golden corpus is unchanged."""
    norm = [_obs("o-fee"), _obs("o-job"), _obs("o-nofee")]
    ind = [_io("UPFRONT_FEE_DEMAND", "o-fee"), _io("JOB_CONTEXT", "o-job"),
           _io("EXPLICIT_NO_FEE", "o-nofee", "NEGATIVE")]
    return ind, norm


def _walk(value: Any, path: str = "result") -> Iterable[tuple[str, Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from _walk(child, f"{path}[{i}]")


# ---------------------------------------------------------------- the suite


def run_checks(rk) -> Check:
    c = Check()
    corpus = json.loads(GOLDEN.read_bytes())
    by_id = {case["id"]: case for case in corpus["cases"]}

    def detect(case_id, *, support=None, **override):
        ind, norm, lang, scr, derived = _wp8_inputs(by_id[case_id])
        kw = dict(evaluation_id=f"EV-{case_id}", evaluation_timestamp=_TS, input_id=f"IN-{case_id}",
                  language=lang, script=scr, input_support_status=support if support is not None else derived)
        kw.update(override)
        return evaluate_detection_from_governed(rk, ind, norm, **kw)

    # ---- 0. runtime-owned engine version is valid SemVer (the WP8-exclusive selftest target) ----
    c.ok(bool(ENGINE_VERSION_RE.match(ENGINE_VERSION)), f"ENGINE_VERSION {ENGINE_VERSION!r} is valid SemVer")

    # ---- 1. representative integration matrix (final envelope is schema+semantically valid by construction) ----
    r01 = detect("GDC-01").as_dict()
    c.eq(r01["result_contract_version"], "1.1.0", "GDC-01 result_contract_version")
    c.eq(r01["classification"], "SCAM_PATTERN_DETECTED", "GDC-01 classification")
    c.eq(r01["risk_level"], "CRITICAL", "GDC-01 risk")
    c.eq(r01["matched_rules"], ["TL-CRED-001"], "GDC-01 matched_rules")
    c.ok("HR_OTP_DISCLOSURE_REQUEST" in r01["active_overrides"], "GDC-01 hard-risk override serialized")
    c.ok("DO_NOT_SHARE_CREDENTIALS" in [a["action_code"] for a in r01["recommended_actions"]], "GDC-01 action")
    c.eq(r01["provenance"]["engine_version"], ENGINE_VERSION, "GDC-01 engine_version pinned")
    c.eq(r01["provenance"]["bundle_content_digest"], rk.content_digest, "GDC-01 bundle digest pinned")
    c.eq(sorted(r01["provenance"]["component_versions"]),
         ["action_policy", "dimensions", "extraction_contracts", "indicator_families", "indicator_registry",
          "negative_library", "rule_schema", "taxonomy"], "GDC-01 component_versions translated exactly")
    c.ok("evidence_manifest" not in r01["provenance"]["component_versions"]
         and "evidence_records" not in r01["provenance"]["component_versions"],
         "GDC-01 result-unsupported component keys dropped")
    c.eq(r01["provenance"]["evaluation_profile"],
         {"profile_id": "mvp-default", "extraction_confidence_gate": "MEDIUM",
          "risk_matrix_id": "risk-matrix-v1", "confidence_policy_id": "confidence-policy-v1"},
         "GDC-01 evaluation_profile is the production DEFAULT_PROFILE")

    r02 = detect("GDC-02").as_dict()
    c.eq(r02["classification"], "NO_SCAM_PATTERN", "GDC-02 benign")
    c.eq(r02["matched_rules"], [], "GDC-02 no fired rules")
    c.eq(r02["decision_severity"], "NONE", "GDC-02 severity NONE")

    r06 = detect("GDC-06").as_dict()
    c.eq(r06["classification"], "SCAM_PATTERN_DETECTED", "GDC-06 multi-rule detected")
    c.ok({"TL-CRED-001", "TL-CRED-003", "TL-KYC-001"} <= set(r06["matched_rules"]), "GDC-06 multi-rule set")

    r11 = detect("GDC-11").as_dict()
    c.eq(r11["classification"], "INSUFFICIENT_EVIDENCE", "GDC-11 insufficient")
    c.ok(bool(r11.get("ambiguities")), "GDC-11 ambiguity survives into the envelope")

    r13 = detect("GDC-13").as_dict()
    c.eq(r13["classification"], "INSUFFICIENT_EVIDENCE", "GDC-13 insufficient")

    r15 = detect("GDC-15").as_dict()
    c.eq(r15["classification"], "SCAM_PATTERN_DETECTED", "GDC-15 detected")
    c.ok("HR_OTP_DISCLOSURE_REQUEST" in r15["active_overrides"], "GDC-15 override active")
    supporting = {s["observation_ref"] for s in r15["explanation"].get("supporting_observations", ())}
    c.ok("g15-otp-live" in supporting, "GDC-15 live OTP occurrence retained in the envelope")

    # ---- 2. support-first: UNSUPPORTED never executes rules, never benign ----
    r12 = detect("GDC-12").as_dict()
    c.eq(r12["classification"], "UNSUPPORTED", "GDC-12 unsupported")
    c.eq(r12["rule_results"], [], "GDC-12 executes no rules")
    c.ok(r12["classification"] != "NO_SCAM_PATTERN", "GDC-12 never benign")
    c.eq(r12["language"], list(by_id["GDC-12"]["language"]), "GDC-12 language array preserved")
    # poison: GDC-01's live-matching observations under a forced UNSUPPORTED status must still not run rules
    ind01, norm01, _, _, _ = _wp8_inputs(by_id["GDC-01"])
    poison = evaluate_detection_from_governed(
        rk, ind01, norm01, evaluation_id="EV-poison", evaluation_timestamp=_TS, input_id="IN-poison",
        language=["hi-Latn"], script=["Latn"], input_support_status="UNSUPPORTED").as_dict()
    c.eq(poison["classification"], "UNSUPPORTED", "poison UNSUPPORTED classification")
    c.eq(poison["rule_results"], [], "poison UNSUPPORTED runs no rules despite live-matching observations")
    # INSUFFICIENT_INFORMATION support routes to INSUFFICIENT_EVIDENCE without running rules
    insuff = evaluate_detection_from_governed(
        rk, ind01, norm01, evaluation_id="EV-ii", evaluation_timestamp=_TS, input_id="IN-ii",
        language=["en"], script=["Latn"], input_support_status="INSUFFICIENT_INFORMATION").as_dict()
    c.eq(insuff["classification"], "INSUFFICIENT_EVIDENCE", "INSUFFICIENT_INFORMATION → INSUFFICIENT_EVIDENCE")
    c.eq(insuff["rule_results"], [], "INSUFFICIENT_INFORMATION runs no rules")

    # ---- 3. production preview exclusion (GDC-08): unpublished TL-MAL-003 cannot enter the final envelope ----
    r08 = detect("GDC-08")
    r08d = r08.as_dict()
    c.ok("TL-MAL-003" not in [x["rule_id"] for x in r08d["rule_results"]], "GDC-08 TL-MAL-003 not in rule_results")
    c.ok("TL-MAL-003" not in r08d["matched_rules"], "GDC-08 TL-MAL-003 not in matched_rules")
    c.ok("TL-MAL-003" not in json.dumps(r08d), "GDC-08 no unpublished rule anywhere in the production envelope")

    # ---- 4. live SUPPRESSED PUBLISHED rule is faithfully serialized ----
    sup_ind, sup_norm = _suppressed_fixture()
    r_sup = evaluate_detection_from_governed(
        rk, sup_ind, sup_norm, evaluation_id="EV-sup", evaluation_timestamp=_TS, input_id="IN-sup",
        language=["en"], script=["Latn"], input_support_status="SUPPORTED").as_dict()
    job = next((x for x in r_sup["rule_results"] if x["rule_id"] == "TL-JOB-001"), None)
    c.ok(job is not None and job["evaluation_state"] == "SUPPRESSED", "TL-JOB-001 serialized as SUPPRESSED")
    c.ok(job is not None and "EXPLICIT_NO_FEE" in job.get("suppression", {}).get("applied_suppressors", ()),
         "SUPPRESSED rule carries its applied_suppressors")
    c.eq(r_sup["classification"], "NO_SCAM_PATTERN", "suppressed benign clear classifies NO_SCAM_PATTERN")

    # ---- 5. rule-result pass-through: WP8 owns NO filtering ----
    dec01 = evaluate_decision_from_governed(rk, ind01, norm01, input_support_status="SUPPORTED",
                                            language="en", script="Latn")
    c.eq([dict(x) for x in r01["rule_results"]], [dict(x) for x in dec01.rule_results],
         "GDC-01 rule_results is the exact DecisionResult.rule_results (no filtering)")

    # ---- 6. limitations mapping (exact WP6 value) ----
    c.ok(r01.get("limitations") == r01["explanation"]["limitations"] and bool(r01.get("limitations")),
         "top-level limitations equals explanation.limitations")

    # ---- 7. determinism with fixed metadata ----
    a = detect("GDC-01").as_dict()
    b = detect("GDC-01").as_dict()
    c.eq(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True), "fixed-metadata result is byte-identical")

    # ---- 8. identity/time invariance ----
    ind1, norm1, lang1, scr1, sup1 = _wp8_inputs(by_id["GDC-01"])
    base = evaluate_detection_from_governed(rk, ind1, norm1, evaluation_id="EV-a", evaluation_timestamp=_TS,
                                            input_id="IN-a", language=lang1, script=scr1,
                                            input_support_status=sup1).as_dict()
    alt = evaluate_detection_from_governed(rk, ind1, norm1, evaluation_id="EV-b",
                                           evaluation_timestamp="2027-01-02T03:04:05Z", input_id="IN-b",
                                           language=lang1, script=scr1, input_support_status=sup1).as_dict()
    for k in ("classification", "decision_severity", "risk_level", "detection_confidence",
              "matched_evidence_strength", "rule_results", "explanation", "recommended_actions", "provenance",
              "corroboration_summary", "active_overrides"):
        c.eq(alt.get(k), base.get(k), f"changing evaluation_id/timestamp leaves {k} unchanged")
    c.ok(alt["evaluation_id"] != base["evaluation_id"]
         and alt["evaluation_timestamp"] != base["evaluation_timestamp"], "only identity/time differ")

    # ---- 9. privacy: no raw content / redacted_quote / numeric probability / span leakage ----
    for cid, doc in (("GDC-01", r01), ("GDC-15", r15)):
        walked = list(_walk(doc))
        c.ok(all(not p.endswith((".raw_span", ".redacted_quote")) for p, _ in walked),
             f"{cid} envelope contains no raw_span/redacted_quote")
        c.ok(all(not isinstance(v, float) for _, v in walked), f"{cid} envelope contains no numeric probability")
    raw_spans = [o.get("raw_span") for o in by_id["GDC-15"]["governed_input"]["normalized_observations"]]
    rendered15 = json.dumps(r15)
    c.ok(all(span not in rendered15 for span in raw_spans if isinstance(span, str) and len(span) >= 8),
         "GDC-15 governed raw spans do not leak into the final envelope")

    # ---- 10. immutability ----
    res01 = detect("GDC-01")
    c.raises(lambda: setattr(res01, "_result", {}), FrozenInstanceError, "DetectionResult is frozen")
    c.ok(isinstance(res01._result, MappingProxyType), "DetectionResult mapping is deeply read-only")
    c.raises(lambda: dict.__setitem__(res01._result, "classification", "FORGED"), TypeError,
             "DetectionResult mapping cannot be mutated")
    c.ok(res01.as_dict() is not res01.as_dict(), "as_dict returns a fresh mutable copy")

    # ---- 11. whole-evaluation ERROR (H1): support MUST be ERROR; any other support state fails closed ----
    whole_err = [{"scope": "WHOLE_EVALUATION", "stage": "OTHER", "code": "WP8_SYNTHETIC_ERROR",
                  "message": "trusted whole-evaluation refusal"}]

    def _detect_we(support):
        return evaluate_detection_from_governed(
            rk, ind01, norm01, evaluation_id="EV-err", evaluation_timestamp=_TS, input_id="IN-err",
            language=["en"], script=["Latn"], input_support_status=support, whole_evaluation_errors=whole_err)

    err = _detect_we("ERROR").as_dict()
    c.eq(err["input_support_status"], "ERROR", "ERROR + WHOLE_EVALUATION yields ERROR support")
    c.eq(err["classification"], "ERROR", "ERROR + WHOLE_EVALUATION classifies ERROR")
    c.ok(err["classification"] != "NO_SCAM_PATTERN", "whole-evaluation error never benign")
    c.eq(err["rule_results"], [], "whole-evaluation error executes no rules")
    c.eq(err["provenance"]["bundle_content_digest"], rk.content_digest, "ERROR envelope carries real provenance")
    for support in ("SUPPORTED", "UNSUPPORTED", "PARTIALLY_SUPPORTED", "INSUFFICIENT_INFORMATION"):
        c.raises_code(lambda s=support: _detect_we(s), "INVALID_INPUT_CONTEXT",
                      f"{support} + WHOLE_EVALUATION is an inconsistent context (rejected, no ERROR normalisation)")

    # ---- 12. degraded / single-rule error is serialized faithfully (white-box synthetic WP4 result) ----
    na_rule = {"rule_id": "TL-CRED-001", "rule_version": "1.0.0", "kind": "COMPOSITE",
               "evaluation_state": "NOT_APPLICABLE", "required_combination_result": "UNKNOWN",
               "evaluation_error": {"code": "RULE_EVALUATION_ERROR", "message": "synthetic degrade"}}
    dec_deg = aggregate_decision([na_rule], input_support_status="SUPPORTED", rk=rk)
    expl_deg = build_explanation(dec_deg, rk=rk)
    deg = result_mod.assemble_detection_result(
        rk=rk, decision=dec_deg, explanation_result=expl_deg, evaluation_id="EV-deg",
        evaluation_timestamp=_TS, input_id="IN-deg", language=["en"], script=["Latn"]).as_dict()
    c.eq(deg["degraded"], True, "degraded flag serialized")
    c.ok(any(e.get("scope") == "SINGLE_RULE" for e in deg.get("errors", ())), "SINGLE_RULE error serialized")
    c.ok(deg["classification"] != "NO_SCAM_PATTERN", "degraded never benign")

    # ---- 13. bundle pre-load failure never yields a result / fabricated provenance ----
    with tempfile.TemporaryDirectory(prefix="wp8-badbundle-") as bad:
        c.raises(lambda: load_bundle(Path(bad)), BundleLoadError, "missing bundle fails closed (no result)")

    # ---- 14. malformed governed observations fail closed with an UPSTREAM error (not wrapped/benign) ----
    bad_ind = [{"indicator_id": "CREDENTIAL_REQUEST_OTP"}]   # missing required governed fields
    c.raises_non_wp8(lambda: evaluate_detection_from_governed(
        rk, bad_ind, norm01, evaluation_id="EV-bad", evaluation_timestamp=_TS, input_id="IN-bad",
        language=["en"], script=["Latn"], input_support_status="SUPPORTED"),
        "malformed governed observations propagate an upstream typed failure")

    # ---- 15. invalid identity / input context ----
    good = dict(evaluation_id="EV", evaluation_timestamp=_TS, input_id="IN", language=["en"], script=["Latn"],
                input_support_status="SUPPORTED")

    def _detect_kw(**over):
        kw = dict(good); kw.update(over)
        return evaluate_detection_from_governed(rk, ind01, norm01, **kw)

    c.raises_code(lambda: _detect_kw(evaluation_id=""), "INVALID_IDENTITY", "empty evaluation_id rejected")
    c.raises_code(lambda: _detect_kw(input_id=""), "INVALID_IDENTITY", "empty input_id rejected")
    c.raises_code(lambda: _detect_kw(evaluation_timestamp="not-a-time"), "INVALID_IDENTITY", "bad timestamp rejected")
    # M2: real ISO-8601 calendar-instant validation (not just a shape check)
    c.ok(isinstance(_detect_kw(evaluation_timestamp="2026-09-05T00:30:00Z"), DetectionResult),
         "valid Z timestamp accepted")
    c.ok(isinstance(_detect_kw(evaluation_timestamp="2026-09-05T00:30:00+05:30"), DetectionResult),
         "valid UTC-offset timestamp accepted")
    c.raises_code(lambda: _detect_kw(evaluation_timestamp="2026-99-99T99:99:99Z"), "INVALID_IDENTITY",
                  "calendar-impossible timestamp rejected")
    c.raises_code(lambda: _detect_kw(evaluation_timestamp="2026-02-30T10:00:00Z"), "INVALID_IDENTITY",
                  "impossible day-of-month timestamp rejected")
    c.raises_code(lambda: _detect_kw(evaluation_timestamp="2026-09-05T00:30:00"), "INVALID_IDENTITY",
                  "timezone-naive timestamp rejected")
    c.raises_code(lambda: _detect_kw(language=[]), "INVALID_INPUT_CONTEXT", "empty language rejected")
    c.raises_code(lambda: _detect_kw(language=["en", "hi"]), "INVALID_INPUT_CONTEXT",
                  "multi-valued evaluable language rejected (no silent first-element choice)")
    c.raises_code(lambda: _detect_kw(input_support_status="BOGUS"), "INVALID_INPUT_CONTEXT", "unknown support rejected")

    # ---- 16. caller cannot inject decision / explanation / provenance fields (fixed signature) ----
    c.raises(lambda: _detect_kw(classification="NO_SCAM_PATTERN"), TypeError, "caller cannot inject classification")
    c.raises(lambda: _detect_kw(risk_level="LOW"), TypeError, "caller cannot inject risk_level")
    c.raises(lambda: _detect_kw(recommended_actions=[]), TypeError, "caller cannot inject recommended_actions")
    c.raises(lambda: _detect_kw(engine_version="9.9.9"), TypeError, "caller cannot inject engine_version")
    c.raises(lambda: _detect_kw(provenance={}), TypeError, "caller cannot inject provenance")

    # ---- 17. assembly forgery / corruption is caught by schema + semantic + reconciliation ----
    dec_f = evaluate_decision_from_governed(rk, ind01, norm01, input_support_status="SUPPORTED",
                                            language="en", script="Latn")
    expl_f = build_explanation(dec_f, rk=rk, observations=norm01)

    def _tamper(mutate):
        d = result_mod._assemble_result_dict(
            rk=rk, decision=dec_f, explanation_result=expl_f, evaluation_id="EV", evaluation_timestamp=_TS,
            input_id="IN", language=["en"], script=["Latn"])
        mutate(d)
        return result_mod._validate_and_freeze(d, rk, dec_f, expl_f)

    def _set(d, key, value):
        d[key] = value

    c.raises_code(lambda: _tamper(lambda d: _set(d, "classification", "NO_SCAM_PATTERN")),
                  "RESULT_SEMANTIC_INVALID", "forged classification (fired rule + NO_SCAM_PATTERN) caught")
    c.raises_code(lambda: _tamper(lambda d: d.pop("input_id")), "RESULT_SCHEMA_INVALID",
                  "missing required field caught by schema")
    c.raises_code(lambda: _tamper(lambda d: _set(d, "score", 0.9)), "RESULT_SCHEMA_INVALID",
                  "smuggled probability field caught (additionalProperties:false)")
    c.raises_code(lambda: _tamper(lambda d: _set(d, "classification", "INSUFFICIENT_EVIDENCE")),
                  "RESULT_SEMANTIC_INVALID", "semantic contradiction (fired rules + INSUFFICIENT_EVIDENCE) caught")
    c.raises_code(lambda: _tamper(lambda d: d["provenance"].__setitem__("engine_version", "banana")),
                  "RESULT_SCHEMA_INVALID", "malformed engine_version caught by schema pattern")
    c.raises_code(lambda: _tamper(lambda d: d["provenance"].__setitem__("bundle_version", "9.9.9")),
                  "PROVENANCE_MISMATCH", "forged bundle_version caught by reconciliation")
    c.raises_code(lambda: _tamper(lambda d: d["provenance"]["component_versions"].__setitem__("action_policy", "9.9.9")),
                  "PROVENANCE_MISMATCH", "forged action_policy pin caught by component reconciliation")
    forged_expl = ExplanationResult(explanation=expl_f.explanation,
                                    recommended_actions=expl_f.recommended_actions, action_policy_version="9.9.9")
    c.raises_code(lambda: result_mod.assemble_detection_result(
        rk=rk, decision=dec_f, explanation_result=forged_expl, evaluation_id="EV", evaluation_timestamp=_TS,
        input_id="IN", language=["en"], script=["Latn"]),
        "ACTION_POLICY_MISMATCH", "action-policy pin disagreement across bundle/explanation caught")
    c.raises_code(lambda: _tamper(lambda d: d["provenance"].__setitem__(
        "evaluation_profile", {"profile_id": "evil", "extraction_confidence_gate": "MEDIUM",
                               "risk_matrix_id": "risk-matrix-v1", "confidence_policy_id": "confidence-policy-v1"})),
        "PROFILE_MISMATCH", "forged evaluation_profile caught")
    c.raises_code(lambda: _tamper(lambda d: _set(d, "recommended_actions", list(d["recommended_actions"]) + [
        {"action_code": "DO_NOT_TRANSFER_MONEY"}])), "ASSEMBLY_INCONSISTENCY", "forged extra action caught")

    # ---- 18. M1: a profile whose policy label drifts from the executed WP5 authority fails closed even when the
    #          DecisionResult and the production profile agree with each other (both would carry the wrong label).
    orig_profile = result_mod.DEFAULT_PROFILE

    def _with_drift(drifted):
        result_mod.DEFAULT_PROFILE = drifted
        try:
            detect("GDC-01")
        finally:
            result_mod.DEFAULT_PROFILE = orig_profile

    c.raises_code(lambda: _with_drift(EvaluationProfile(risk_matrix_id="bogus-risk-v2")),
                  "PROFILE_MISMATCH", "risk_matrix_id drift from aggregation.RISK_MATRIX_ID fails closed")
    c.raises_code(lambda: _with_drift(EvaluationProfile(confidence_policy_id="bogus-conf-v2")),
                  "PROFILE_MISMATCH", "confidence_policy_id drift from aggregation.CONFIDENCE_POLICY_ID fails closed")

    return c


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P3-WP8 engine integration + DetectionResult validator")
    parser.add_argument("--quiet", action="store_true", help="suppress the summary line")
    args = parser.parse_args(argv)

    try:
        with tempfile.TemporaryDirectory(prefix="wp8-integration-") as tmp:
            bundle_dir = Path(tmp) / "bundle"
            build_bundle.build(bundle_dir)
            rk = load_bundle(bundle_dir)
            if rk.manifest_schema_version != "1.1.0" or not rk.has_action_policy():
                raise RuntimeError("current bundle is not WP6/WP8-capable (manifest 1.1 + action policy required)")
            checks = run_checks(rk)
    except Exception as exc:  # noqa: BLE001
        print(f"P3-WP8 INTEGRATION: ERROR — {type(exc).__name__}: {exc}")
        return 2

    passed = checks.count - len(checks.failures)
    if not args.quiet:
        print(f"{passed}/{checks.count} integration assertions passed.")
    if checks.failures:
        print(f"P3-WP8 INTEGRATION: FAIL — {len(checks.failures)} assertion(s) failed")
        for f in checks.failures:
            print(f"  - {f}")
        return 1
    print("P3-WP8 INTEGRATION: PASS — production evaluate_detection_from_governed assembles a schema+semantically "
          "valid, fully-provenance-pinned, immutable DetectionResult from WP3→WP6; support-first (no rules for "
          "non-evaluable), PUBLISHED-only preview exclusion, faithful WP5/WP6 serialization, privacy-minimised, "
          "deterministic with identity/time invariance, fail-closed on forgery/corruption. Offline; G-09 open.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
