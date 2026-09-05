"""P4-WP5 offline builder validation. WP7 owns canonical CI integration."""

from __future__ import annotations

import argparse
import ast
import copy
import inspect
import json
import operator
import re
import sys
import tempfile
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from knowledge import runtime  # noqa: E402
from knowledge.ai import (  # noqa: E402
    FakeProvider, RawAIExtractionResponse, canonical_digest, prepare_replay,
    restore_replay_snapshot, AIReplayIntegrityError,
)
from knowledge.ai import integration as integration  # noqa: E402
from knowledge.ai.integration import (  # noqa: E402
    AIIntegrationPolicy, AIIntegrationOutcome, AIIntegrationInputError, AIFallbackReason,
    evaluate_with_optional_ai,
)
from knowledge.publish import build_bundle  # noqa: E402
from knowledge.validation.validate_ai_governance import Check, config, payload  # noqa: E402
from knowledge.validation.validate_wp7_golden_runner import _adapt_fixture, _case_execution_input  # noqa: E402

CONTEXT = dict(evaluation_id="EVAL-1", evaluation_timestamp="2026-09-05T10:00:00Z", input_id="IN-1",
               language=["en"], script=["Latn"], input_support_status="SUPPORTED", whole_evaluation_errors=[])
CONTENT = "Share your OTP."
ON = AIIntegrationPolicy(extraction_enabled=True)
PROVENANCE = {"extractor_id": "wp5-fixture", "extractor_type": "USER_SUPPLIED", "extractor_version": "1.0.0"}


def baseline():
    obs = [{"observation_id": "o1", "observation_type": "CLAIM", "source_input_id": "IN-1",
            "status": "OBSERVED", "polarity": "AFFIRMED", "attribution": "FIRST_PARTY", "mood": "DIRECTIVE",
            "confidence": {"level": "HIGH"}, "provenance": dict(PROVENANCE)}]
    ind = [{"indicator_id": "VERIFICATION_PRETEXT", "polarity": "POSITIVE", "matched": "OBSERVED",
            "input_id": "IN-1", "observation_refs": ["o1"], "confidence": {"level": "HIGH"},
            "provenance": dict(PROVENANCE)}]
    return ind, obs


def fake(data=None):
    data = payload() if data is None else data
    raw = data if isinstance(data, str) else json.dumps(data)
    return FakeProvider().register_response("REQ-1", RawAIExtractionResponse("REQ-1", raw))


class NeverExtract:
    def __init__(self):
        self.calls = 0

    def extract(self, request):
        self.calls += 1
        raise AssertionError("optional path must be bypassed")


def run_checks(rk):
    c = Check()
    ind, obs = baseline()
    cfg = config()
    direct = runtime.evaluate_detection_from_governed
    expected = direct(rk, ind, obs, **CONTEXT).as_dict()

    def run(*, provider=None, indicators=None, observations=None, context=None, **options):
        kwargs = dict(policy=ON, config=cfg, normalized_content=CONTENT, request_id="REQ-1", run_id="RUN-1")
        kwargs.update(options)
        return evaluate_with_optional_ai(rk, ind if indicators is None else indicators,
                                         obs if observations is None else observations,
                                         provider=provider, **(CONTEXT if context is None else context), **kwargs)

    c.eq(AIIntegrationPolicy().extraction_enabled, False, "feature flag default OFF")
    c.raises(lambda: AIIntegrationPolicy(1), TypeError, "feature flag must be an explicit boolean")
    c.raises(lambda: setattr(ON, "extraction_enabled", False), FrozenInstanceError, "feature policy immutable")
    sentinel = NeverExtract()
    with patch.object(integration, "validate_ai_extraction", side_effect=AssertionError("WP3 entered")) as v3, \
            patch.object(integration, "prepare_ai_extraction", side_effect=AssertionError("WP4 entered")) as v4, \
            patch.object(integration, "prepare_ai_request", side_effect=AssertionError("request entered")) as prep:
        off = evaluate_with_optional_ai(rk, ind, obs, provider=sentinel, **CONTEXT)
        c.eq(off.detection_result.as_dict(), expected, "default OFF exact deterministic baseline equality")
        c.eq((v3.call_count, v4.call_count, prep.call_count, sentinel.calls), (0, 0, 0, 0),
             "OFF bypasses provider and all AI validation/preparation")
        corpus = json.loads((ROOT / "docs/03-detection/golden-decision-cases-v1.json").read_text())
        for case in corpus["cases"]:
            fixture = _adapt_fixture(_case_execution_input(case))
            context = dict(CONTEXT, evaluation_id="EV-" + case["id"], input_id="IN-" + case["id"],
                           language=case["language"], script=case["script"], input_support_status=fixture.support_status)
            actual = evaluate_with_optional_ai(rk, fixture.indicator_observations, fixture.normalized_observations,
                                               provider=sentinel, **context)
            reference = direct(rk, fixture.indicator_observations, fixture.normalized_observations, **context)
            c.eq(actual.detection_result.as_dict(), reference.as_dict(), f"{case['id']}: complete OFF result equality")
        c.eq(sentinel.calls, 0, "golden OFF matrix never calls provider")
    c.eq((off.ai_attempted, off.ai_used, off.fallback_reason), (False, False, AIFallbackReason.DISABLED), "OFF metadata")
    c.eq(off.ai_extraction_result, None, "OFF has no fabricated AI audit")

    captured = []
    def capture(knowledge, indicators, observations, **context):
        captured.append(copy.deepcopy(dict(indicator_observations=indicators, observations=observations,
                                           evaluation_context=context)))
        return direct(knowledge, indicators, observations, **context)

    original_ind, original_obs = copy.deepcopy(ind), copy.deepcopy(obs)
    with patch.object(runtime, "evaluate_detection_from_governed", side_effect=capture) as engine, \
            patch.object(integration, "validate_ai_extraction", wraps=integration.validate_ai_extraction) as v3, \
            patch.object(integration, "prepare_ai_extraction", wraps=integration.prepare_ai_extraction) as v4:
        success = run(provider=fake())
        c.eq((engine.call_count, v3.call_count, v4.call_count), (1, 1, 1), "one provider pipeline and one authoritative engine call")
    c.ok(success.ai_attempted and success.ai_used and success.fallback_reason is None, "valid FakeProvider accepted")
    c.eq(success.as_dict()["governed_artifact"], captured[0], "exact pinned combined artifact equals engine arguments")
    c.eq(success.governed_artifact_digest, canonical_digest(captured[0]), "internally computed digest covers consumed data")
    c.eq(success.replay_snapshot.governed_artifact_digest, success.governed_artifact_digest, "replay digest equals consumed digest")
    c.eq(success.detection_result.as_dict(), direct(rk, captured[0]["indicator_observations"],
         captured[0]["observations"], **captured[0]["evaluation_context"]).as_dict(), "Phase3 remains sole result producer")
    c.ok(expected != success.detection_result.as_dict(), "synthetic AI contribution changes deterministic result through governed input")
    c.ok("TL-CRED-001" in success.detection_result.as_dict()["matched_rules"], "synthetic OTP plus host pretext triggers governed rule")
    c.eq((ind, obs), (original_ind, original_obs), "caller baseline data remains unchanged")
    artifact = success.as_dict()["governed_artifact"]
    c.eq(artifact["observations"][:len(obs)], obs, "baseline observations preserved in original order")
    c.eq(artifact["indicator_observations"][:len(ind)], ind, "baseline indicators preserved in original order")
    ai_obs, ai_ind = artifact["observations"][-1], artifact["indicator_observations"][-1]
    c.eq(len(artifact["observations"]), len(obs) + 1, "AI augments, never replaces baseline")
    c.ok(re.fullmatch(r"AI-OBS-[0-9a-f]{64}", ai_obs["observation_id"]) is not None, "deterministic schema-valid AI ID")
    c.ok(ai_obs["observation_id"] != "o1", "model proposal id cannot overwrite same-named host observation")
    c.eq(ai_ind["observation_refs"], [ai_obs["observation_id"]], "indicator proposal refs explicitly remapped")
    c.eq(ai_obs["offsets"], {"start": 11, "end": 14}, "exact WP3 offsets preserved")
    c.ok("raw_span" not in ai_obs and "evidence_excerpt" not in ai_obs, "no transient excerpt persistence or invented raw span")
    for record in (ai_obs, ai_ind):
        c.eq(record["confidence"], {"level": "MEDIUM"}, "exact WP4 determinate confidence, no numeric field")
        c.eq(record["provenance"], {"extractor_id": "ai-extraction-adapter", "extractor_type": "LLM",
                                    "extractor_version": "1.0.0", "config_ref": cfg.config_ref}, "WP4 authoritative provenance reused")
    c.eq(ai_ind["extraction_method"], "LLM", "governed extraction method LLM")
    c.eq(ai_ind["review_required"], False, "determinate state does not require review under WP4")
    c.eq(run(provider=fake()).governed_artifact_digest, success.governed_artifact_digest, "same input/run/config stable artifact")
    changed_run = run(provider=fake(), run_id="RUN-2")
    c.ok(changed_run.governed_artifact["observations"][-1]["observation_id"] != ai_obs["observation_id"], "different run changes AI ID")
    changed = payload()
    changed["observations"][0]["proposal_id"] = "o2"
    changed["indicators"][0]["observation_refs"] = ["o2"]
    changed["observations"][0]["canonical_value"] = "REQUEST_DISCLOSE_OTP"
    changed_result = run(provider=fake(changed))
    c.ok(changed_result.governed_artifact["observations"][-1]["observation_id"] != ai_obs["observation_id"], "different proposal changes AI ID")
    c.eq(changed_result.governed_artifact["observations"][-1]["canonical_value"], "REQUEST_DISCLOSE_OTP", "optional canonical value mapped")
    for state in ("UNKNOWN", "AMBIGUOUS", "NOT_OBSERVED", "NOT_APPLICABLE"):
        out = run(provider=fake(payload(state)))
        c.ok(out.ai_used, f"{state}: valid uncertain/determinate proposal remains accepted")
        for record in (out.governed_artifact["observations"][-1], out.governed_artifact["indicator_observations"][-1]):
            c.eq(record["confidence"]["level"], "LOW" if state in ("UNKNOWN", "AMBIGUOUS") else "MEDIUM", f"{state}: exact WP4 confidence")
        c.eq(out.governed_artifact["indicator_observations"][-1]["review_required"], state in ("UNKNOWN", "AMBIGUOUS"), f"{state}: LOW implies review")
    duplicate = payload()
    duplicate["indicators"].append(copy.deepcopy(duplicate["indicators"][0]))
    out = run(provider=fake(duplicate))
    c.eq(len(out.governed_artifact["indicator_observations"]), len(ind) + 2, "no semantic/silent deduplication")
    empty = run(provider=fake(payload(empty=True)))
    c.ok(empty.ai_used, "valid empty extraction accepted with zero contribution")
    c.eq(empty.detection_result.as_dict(), expected, "empty extraction does not create safety evidence")

    def assert_fallback(out, reason, reference=expected):
        c.eq(out.detection_result.as_dict(), reference, f"{reason.value}: complete deterministic baseline equality")
        c.eq((out.ai_attempted, out.ai_used, out.fallback_reason), (True, False, reason), "closed operational fallback metadata")
        c.eq((out.ai_extraction_result, out.replay_snapshot), (None, None), "discarded AI has no success audit/replay")
        c.eq(out.governed_artifact["evaluation_context"]["input_support_status"], "SUPPORTED", "optional failure preserves host support")
        c.eq(out.as_dict()["governed_artifact"]["evaluation_context"], CONTEXT, "all host metadata/whole errors unchanged")
        c.ok("SECRET" not in json.dumps(out.as_dict()), "provider/response secret not in fallback diagnostics")

    for kind in ("unavailable", "timeout", "execution"):
        assert_fallback(run(provider=FakeProvider().register_failure("REQ-1", kind, "SECRET")), AIFallbackReason.PROVIDER_FAILED)
    assert_fallback(run(provider=None), AIFallbackReason.PROVIDER_FAILED)
    assert_fallback(run(provider=FakeProvider()), AIFallbackReason.PROVIDER_FAILED)
    mutations = ["{SECRET"]
    for path, value in (
        (("observations", 0, "status"), "SECRET"),
        (("indicators", 0, "indicator_id"), "NONEXISTENT_INDICATOR"),
        (("observations", 0, "end"), 999),
        (("indicators", 0, "observation_refs"), ["missing"]),
        (("input_id",), "IN-OTHER"),
    ):
        mutated = payload()
        cursor = mutated
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
        mutations.append(mutated)
    for name in ("classification", "risk_level", "confidence", "input_support_status", "language", "script",
                 "evaluation_id", "evaluation_timestamp", "provenance"):
        mutated = payload()
        mutated[name] = "SECRET"
        mutations.append(mutated)
    for bad in mutations:
        out = run(provider=fake(bad))
        assert_fallback(out, AIFallbackReason.RESPONSE_REJECTED)
        c.eq(out.as_dict()["governed_artifact"]["observations"], obs, "response rejection leaves zero partial AI observations")
        c.eq(out.as_dict()["governed_artifact"]["indicator_observations"], ind, "response rejection leaves zero partial AI indicators")
    assert_fallback(run(provider=fake(), config=None), AIFallbackReason.GOVERNANCE_FAILED)
    assert_fallback(run(provider=fake(), run_id=" "), AIFallbackReason.GOVERNANCE_FAILED)
    contradiction = payload()
    contradiction["observations"][0]["status"] = "NOT_OBSERVED"
    assert_fallback(run(provider=fake(contradiction)), AIFallbackReason.MAPPING_FAILED)
    collided_obs = copy.deepcopy(obs)
    collided_ind = copy.deepcopy(ind)
    collided_obs[0]["observation_id"] = ai_obs["observation_id"]
    collided_ind[0]["observation_refs"] = [ai_obs["observation_id"]]
    collided_reference = direct(rk, collided_ind, collided_obs, **CONTEXT).as_dict()
    assert_fallback(run(provider=fake(), indicators=collided_ind, observations=collided_obs),
                    AIFallbackReason.MAPPING_FAILED, collided_reference)

    for support in ("UNSUPPORTED", "INSUFFICIENT_INFORMATION", "ERROR"):
        ctx = dict(CONTEXT, input_support_status=support)
        if support == "UNSUPPORTED":
            ctx.update(language=["hi"], script=["Deva"])
        if support == "ERROR":
            ctx["whole_evaluation_errors"] = [{"scope": "WHOLE_EVALUATION", "stage": "OTHER",
                "code": "HOST_FAILURE", "message": "trusted host error"}]
        bypass = run(provider=sentinel, context=ctx)
        c.eq(bypass.detection_result.as_dict(), direct(rk, ind, obs, **ctx).as_dict(), f"{support}: exact support-first baseline")
        c.eq((bypass.ai_attempted, bypass.ai_used), (False, False), f"{support}: extraction bypass")
        c.eq(bypass.fallback_reason, AIFallbackReason.HOST_NOT_EVALUABLE, "support bypass controlled reason")
    c.eq(sentinel.calls, 0, "support-first does not call provider")
    bad_context = dict(CONTEXT, evaluation_timestamp="not-a-timestamp")
    c.raises(lambda: run(provider=fake(), context=bad_context), runtime.DetectionResultError, "host identity error propagates")
    bad_context = dict(CONTEXT, whole_evaluation_errors=[{"scope": "WHOLE_EVALUATION", "stage": "OTHER",
        "code": "HOST_FAILURE", "message": "trusted host error"}])
    c.raises(lambda: run(provider=sentinel, context=bad_context), runtime.DetectionResultError,
             "inconsistent host whole-error/support contract propagates")
    with patch.object(runtime, "evaluate_detection_from_governed", side_effect=runtime.DetectionResultError("engine failure")) as engine:
        c.raises(lambda: run(provider=fake()), runtime.DetectionResultError, "Phase3 failure never becomes AI fallback")
        c.eq(engine.call_count, 1, "failed Phase3 call is not retried with fabricated fallback")
    invalid_obs = copy.deepcopy(obs)
    invalid_obs[0]["status"] = "INVALID"
    c.raises(lambda: run(provider=fake(), observations=invalid_obs), ValueError, "malformed baseline propagates Phase3 validation failure")

    # Provider observes only its request. Changing caller aliases cannot alter captured host state.
    mutable_ind, mutable_obs = baseline()
    mutable_ctx = copy.deepcopy(CONTEXT)
    actual_provider = fake()
    class MutatingFixture:
        def extract(self, request):
            mutable_obs[0]["status"] = "NOT_OBSERVED"
            mutable_ind.clear()
            mutable_ctx["language"][:] = ["hi"]
            mutable_ctx["whole_evaluation_errors"].append({"code": "changed"})
            return actual_provider.extract(request)
    isolated = run(provider=MutatingFixture(), indicators=mutable_ind, observations=mutable_obs, context=mutable_ctx)
    c.eq(isolated.as_dict(), success.as_dict(), "baseline and host metadata captured before provider mutation")
    cyclic = []
    cyclic.append(cyclic)
    for bad in ({1: "value"}, {"x": float("nan")}, {"x": float("inf")}, {"x": b"bytes"},
                {"x": {1, 2}}, {"x": object()}, {"x": cyclic}):
        c.raises(lambda value=bad: run(provider=sentinel, observations=[value]), AIIntegrationInputError,
                 "noncanonical host data rejected outside optional fallback")
    c.eq(sentinel.calls, 0, "invalid host snapshot rejected before provider")
    c.raises(lambda: setattr(success, "ai_attempted", False), FrozenInstanceError, "outcome frozen")
    c.raises(lambda: operator.setitem(success.governed_artifact["observations"][0], "status", "UNKNOWN"), TypeError,
             "combined artifact deeply frozen")
    detached = success.as_dict()
    detached["governed_artifact"]["observations"].clear()
    c.eq(success.governed_artifact_digest, canonical_digest(captured[0]), "detached serialization does not alias artifact")
    c.eq(success.ai_extraction_result.governed_artifact_digest, None, "sealed WP4 audit never mutated or rebound")
    c.eq(success.replay_snapshot.content_digest, rk.content_digest, "actual bundle digest pinned")
    c.eq(success.replay_snapshot.engine_version, runtime.ENGINE_VERSION, "actual engine version pinned")
    c.eq(success.replay_snapshot.profile, runtime.DEFAULT_PROFILE.profile_id, "actual runtime profile pinned")
    c.eq(success.replay_snapshot.evaluation_id, CONTEXT["evaluation_id"], "replay evaluation correlated")
    with patch.object(FakeProvider, "extract", side_effect=AssertionError("replay model recall")):
        replayed = prepare_replay(restore_replay_snapshot(success.replay_snapshot.as_dict()))
        replayed_data = json.loads(integration.canonical_json(replayed))
        replay_result = direct(rk, replayed_data["indicator_observations"], replayed_data["observations"],
                               **replayed_data["evaluation_context"])
        c.eq(replay_result.as_dict(), success.detection_result.as_dict(), "historical exact-artifact replay without model call")
    tampered = success.replay_snapshot.as_dict()
    tampered["governed_artifact"]["observations"][-1]["offsets"]["start"] = 0
    c.raises(lambda: restore_replay_snapshot(tampered), AIReplayIntegrityError, "consumed-artifact replay detects tampering")
    c.ok("governed_artifact_digest" not in inspect.signature(evaluate_with_optional_ai).parameters, "no caller digest override")
    c.raises(lambda: AIIntegrationOutcome(governed_artifact_digest="f" * 64), TypeError, "no public outcome digest injection")
    forbidden = {"classification", "risk_level", "decision_severity", "detection_confidence", "recommended_actions",
                 "fraud_probability", "scam_probability"}
    c.ok(not {f.name for f in fields(AIIntegrationOutcome)} & forbidden, "outcome duplicates no decision fields")
    tree = ast.parse((ROOT / "knowledge/ai/integration.py").read_text())
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imports.update(alias.name for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names)
    c.ok(imports <= {"__future__", "dataclasses", "enum", "typing", "knowledge", "governance", "provider", "replay", "validation"},
         "production imports no vendor/network/tools")
    c.ok(not {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)} & forbidden,
         "production authors no decision-owned key")
    return c, expected["classification"], success.detection_result.as_dict()["classification"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="P4-WP5 offline Phase-3 AI integration validator")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    try:
        with tempfile.TemporaryDirectory(prefix="wp5-ai-integration-") as temporary:
            bundle = Path(temporary) / "bundle"
            build_bundle.build(bundle)
            checks, before, after = run_checks(runtime.load_bundle(bundle))
    except Exception as exc:
        print(f"P4-WP5 AI INTEGRATION: ERROR — {type(exc).__name__}: {exc}")
        return 2
    if not args.quiet:
        print(f"{checks.count - len(checks.failures)}/{checks.count} integration assertions passed.")
        print(f"Synthetic governed-input fixture: {before} -> {after}; integration behavior only.")
    if checks.failures:
        for failure in checks.failures:
            print(f"  FAIL: {failure}")
        return 1
    print("P4-WP5 AI INTEGRATION: PASS — offline wiring and exact baseline/replay equivalence only; G-09 OPEN.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
