"""P4-WP7 Phase-4 closure validator — cross-WP adversarial behaviour over the PUBLIC interfaces.

This does NOT re-run the four WP validators (run_all invokes those separately). It independently
exercises the committed offline adversarial fixture matrix
(``knowledge/ai/fixtures/phase4-adversarial-fixtures-v1.json``) through the single public entry point
``knowledge.ai.integration.evaluate_with_optional_ai`` and proves cross-WP properties that no single
WP validator proves alone: feature-flag default OFF, WP2→WP3→WP4→WP5→Phase-3 wiring, atomic fail-closed
fallback, exact deterministic baseline equivalence, provenance/confidence caps, support-first preservation,
content-as-data containment, exact consumed-artifact replay and fail-closed tampering.

Expectations are LITERAL and authored in the fixture file; they are never recomputed from production code at
load time. The only comparisons made against a live production call are the exact-baseline-equivalence
invariants (a direct Phase-3 call vs. the optional-AI wrapper), where the equivalence itself is the property
under test. Offline: no provider, no network, no subprocess, no vendor SDK, no API key, no tools. G-09 OPEN.

Usage:  python knowledge/validation/validate_ai_phase4_closure.py [--quiet]
Exit 0 only when every closure assertion passes.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import tempfile
from dataclasses import fields, FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from knowledge import runtime  # noqa: E402
from knowledge.ai import (  # noqa: E402
    FakeProvider, RawAIExtractionResponse, restore_replay_snapshot, prepare_replay,
    AIReplayIntegrityError, canonical_digest,
)
from knowledge.ai import integration as integration  # noqa: E402
from knowledge.ai.integration import (  # noqa: E402
    AIIntegrationPolicy, AIIntegrationOutcome, AIIntegrationInputError, AIFallbackReason,
    evaluate_with_optional_ai,
)
from knowledge.publish import build_bundle  # noqa: E402
from knowledge.validation.validate_ai_governance import Check, config  # noqa: E402

FIXTURE_PATH = ROOT / "knowledge/ai/fixtures/phase4-adversarial-fixtures-v1.json"
FALLBACK = {r.value: r for r in AIFallbackReason}
DECISION_FIELDS = {"classification", "risk_level", "decision_severity", "detection_confidence",
                   "recommended_actions", "fraud_probability", "scam_probability"}
REQUIRED_CASE_KEYS = {"case_id", "category", "description", "policy_enabled", "baseline", "provider", "expected"}


class NeverExtract:
    """Provider sentinel: extraction must be bypassed; any call is a hard error."""

    def __init__(self):
        self.calls = 0

    def extract(self, request):
        self.calls += 1
        raise AssertionError("optional AI path must be bypassed")


def load_and_validate_fixture(data=None):
    """Deterministically reject malformed fixture metadata; return the parsed matrix."""
    if data is None:
        data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if data.get("fixture_version") != "1.0.0":
        raise ValueError("fixture_version must be '1.0.0'")
    for key in ("purpose", "claim_boundary", "content"):
        if not isinstance(data.get(key), str) or not data[key]:
            raise ValueError(f"fixture {key} must be a non-empty string")
    if not isinstance(data.get("context"), dict) or not isinstance(data.get("baselines"), dict):
        raise ValueError("fixture context/baselines must be objects")
    if not isinstance(data.get("cases"), list) or not data["cases"]:
        raise ValueError("fixture cases must be a non-empty list")
    seen = set()
    for case in data["cases"]:
        missing = REQUIRED_CASE_KEYS - set(case)
        if missing:
            raise ValueError(f"case {case.get('case_id')!r} missing keys {sorted(missing)}")
        if case["case_id"] in seen:
            raise ValueError(f"duplicate case_id {case['case_id']!r}")
        seen.add(case["case_id"])
        if case["baseline"] not in data["baselines"]:
            raise ValueError(f"case {case['case_id']!r} references unknown baseline {case['baseline']!r}")
        if not isinstance(case["expected"], dict):
            raise ValueError(f"case {case['case_id']!r} expected must be an object")
    return data


def _provider(case):
    kind = case["provider"]
    if kind == "sentinel":
        return NeverExtract()
    if kind == "none":
        return None
    if kind == "empty":
        return FakeProvider()
    if kind.startswith("fail:"):
        return FakeProvider().register_failure("REQ-1", kind.split(":", 1)[1], case.get("provider_secret", "SECRET"))
    raw = json.dumps(case["ai_response"]) if "ai_response" in case else case["ai_response_raw"]
    return FakeProvider().register_response("REQ-1", RawAIExtractionResponse("REQ-1", raw))


def _evaluate(rk, fixture, case, provider):
    base = fixture["baselines"][case["baseline"]]
    ind = copy.deepcopy(base["indicator_observations"])
    obs = copy.deepcopy(base["observations"])
    ctx = dict(fixture["context"], **case.get("context_overrides", {}))
    content = case.get("content_override", fixture["content"])
    outcome = evaluate_with_optional_ai(
        rk, ind, obs, policy=AIIntegrationPolicy(case["policy_enabled"]), config=config(),
        normalized_content=content, request_id="REQ-1", run_id="RUN-1", provider=provider, **ctx)
    return outcome, ind, obs, ctx


def run_case(c, rk, fixture, case):
    cid = case["case_id"]
    exp = case["expected"]
    provider = _provider(case)
    outcome, ind, obs, ctx = _evaluate(rk, fixture, case, provider)
    dr = outcome.detection_result.as_dict()

    c.eq(outcome.ai_attempted, exp["ai_attempted"], f"{cid}: ai_attempted")
    c.eq(outcome.ai_used, exp["ai_used"], f"{cid}: ai_used")
    expected_reason = FALLBACK[exp["fallback_reason"]] if exp["fallback_reason"] else None
    c.eq(outcome.fallback_reason, expected_reason, f"{cid}: closed fallback reason")
    c.eq(dr["classification"], exp["classification"], f"{cid}: literal governed classification")

    if exp.get("provider_called") is False and isinstance(provider, NeverExtract):
        c.eq(provider.calls, 0, f"{cid}: provider never called")
    if exp.get("equals_direct_baseline"):
        direct = runtime.evaluate_detection_from_governed(rk, ind, obs, **ctx).as_dict()
        c.eq(dr, direct, f"{cid}: complete DetectionResult equals direct deterministic baseline")
    if not outcome.ai_used:
        c.eq(outcome.as_dict()["governed_artifact"]["observations"], obs, f"{cid}: zero partial AI observations")
        c.eq(outcome.as_dict()["governed_artifact"]["indicator_observations"], ind, f"{cid}: zero partial AI indicators")
        c.eq((outcome.ai_extraction_result, outcome.replay_snapshot), (None, None), f"{cid}: no success audit/replay for discarded AI")
    if "matched_rule_contains" in exp:
        c.ok(exp["matched_rule_contains"] in dr["matched_rules"], f"{cid}: governed rule {exp['matched_rule_contains']} fired via governed input")
    if "ai_contribution_count" in exp:
        n = exp["ai_contribution_count"]
        c.eq(len(outcome.governed_artifact["observations"]) - len(obs), n, f"{cid}: AI observation contribution count")
        c.eq(len(outcome.governed_artifact["indicator_observations"]) - len(ind), n, f"{cid}: AI indicator contribution count")
    if exp.get("secret_absent_from_outcome"):
        c.ok(case["provider_secret"] not in json.dumps(outcome.as_dict()), f"{cid}: provider secret absent from diagnostics")
    if exp.get("whole_evaluation_errors_unchanged"):
        c.eq(outcome.as_dict()["governed_artifact"]["evaluation_context"]["whole_evaluation_errors"],
             list(ctx["whole_evaluation_errors"]), f"{cid}: host whole_evaluation_errors unchanged")
        c.eq(dr["input_support_status"], ctx["input_support_status"], f"{cid}: host support unchanged")

    aiexp = exp.get("ai_observation")
    if aiexp:
        ai_obs = outcome.governed_artifact["observations"][-1]
        ai_ind = outcome.governed_artifact["indicator_observations"][-1]
        for key in ("status", "polarity", "attribution", "mood"):
            if key in aiexp:
                c.eq(ai_obs[key], aiexp[key], f"{cid}: AI-derived {key} reaches deterministic structure unchanged")
        if "confidence_level" in aiexp:
            c.eq(ai_obs["confidence"], {"level": aiexp["confidence_level"]}, f"{cid}: exact WP4 categorical confidence")
            c.ok(ai_obs["confidence"]["level"] != "HIGH", f"{cid}: LLM-only confidence never HIGH")
            c.ok(not isinstance(ai_obs["confidence"].get("level"), (int, float)), f"{cid}: no numeric confidence")
        if "review_required" in aiexp:
            c.eq(ai_ind["review_required"], aiexp["review_required"], f"{cid}: WP4 review_required fact")
        if aiexp.get("extractor_type") == "LLM":
            c.eq(ai_obs["provenance"]["extractor_type"], "LLM", f"{cid}: provenance extractor_type LLM")
            c.eq(ai_ind["extraction_method"], "LLM", f"{cid}: indicator extraction_method LLM")
            c.eq(ai_obs["provenance"]["config_ref"], config().config_ref, f"{cid}: pinned WP4 config_ref")
            c.ok("evidence_excerpt" not in ai_obs and "raw_span" not in ai_obs, f"{cid}: transient excerpt not persisted; no invented raw_span")
            c.ok(re.fullmatch(r"AI-OBS-[0-9a-f]{64}", ai_obs["observation_id"]) is not None, f"{cid}: deterministic schema-valid AI observation id")
    return outcome


def run_probes(c, rk, fixture, outcomes):
    """Programmatic cross-WP proofs that are awkward or unsafe to express as JSON fixtures."""
    valid = outcomes["B-valid-extraction"]
    base = fixture["baselines"]["pretext"]
    ind0 = copy.deepcopy(base["indicator_observations"])
    obs0 = copy.deepcopy(base["observations"])
    ctx0 = dict(fixture["context"])
    content = fixture["content"]
    on = AIIntegrationPolicy(extraction_enabled=True)

    def valid_provider():
        raw = json.dumps(next(x for x in fixture["cases"] if x["case_id"] == "B-valid-extraction")["ai_response"])
        return FakeProvider().register_response("REQ-1", RawAIExtractionResponse("REQ-1", raw))

    # ---- default feature policy
    c.eq(AIIntegrationPolicy().extraction_enabled, False, "feature flag default OFF")
    c.raises(lambda: setattr(on, "extraction_enabled", False), FrozenInstanceError, "feature policy immutable")

    # ---- no second decision object; DetectionResult authoritative
    c.ok(not {f.name for f in fields(AIIntegrationOutcome)} & DECISION_FIELDS, "outcome authors no decision-owned field")
    c.ok(isinstance(valid.detection_result, runtime.DetectionResult), "DetectionResult is the sole decision object")
    c.raises(lambda: setattr(valid, "ai_attempted", False), FrozenInstanceError, "outcome sealed/frozen")

    # ---- exact consumed-artifact pinning: what is hashed is exactly what Phase 3 consumes
    direct = runtime.evaluate_detection_from_governed
    captured = []

    def capture(knowledge, indicators, observations, **context):
        captured.append(copy.deepcopy({"indicator_observations": indicators, "observations": observations,
                                       "evaluation_context": context}))
        return direct(knowledge, indicators, observations, **context)

    with patch.object(runtime, "evaluate_detection_from_governed", side_effect=capture):
        pinned = evaluate_with_optional_ai(rk, copy.deepcopy(ind0), copy.deepcopy(obs0), policy=on, config=config(),
                                           normalized_content=content, request_id="REQ-1", run_id="RUN-1",
                                           provider=valid_provider(), **ctx0)
    c.eq(pinned.as_dict()["governed_artifact"], captured[0], "exact combined artifact equals Phase-3-consumed material")
    c.eq(pinned.governed_artifact_digest, canonical_digest(captured[0]), "digest computed from exact consumed artifact")
    c.eq(pinned.replay_snapshot.governed_artifact_digest, pinned.governed_artifact_digest, "replay digest equals consumed digest")
    c.eq(pinned.ai_extraction_result.governed_artifact_digest, None, "sealed WP4 audit never mutated")

    # ---- exact historical replay with NO provider/model recall
    replayed = prepare_replay(restore_replay_snapshot(valid.replay_snapshot.as_dict()))
    with patch.object(FakeProvider, "extract", side_effect=AssertionError("replay must not recall a model")):
        data = json.loads(integration.canonical_json(replayed))
        rr = direct(rk, data["indicator_observations"], data["observations"], **data["evaluation_context"])
    c.eq(rr.as_dict(), valid.detection_result.as_dict(), "exact-artifact replay reproduces the result without a model call")
    c.eq(valid.replay_snapshot.content_digest, rk.content_digest, "replay pins actual bundle content digest")
    c.eq(valid.replay_snapshot.engine_version, runtime.ENGINE_VERSION, "replay pins actual engine version")

    # ---- replay tampering fails closed
    tampered = valid.replay_snapshot.as_dict()
    tampered["governed_artifact"]["observations"][-1]["offsets"]["start"] = 0
    c.raises(lambda: restore_replay_snapshot(tampered), AIReplayIntegrityError, "consumed-artifact replay tampering fails closed")

    # ---- Phase-3 runtime failure propagates; it is never presented as successful AI fallback
    bad_ctx = dict(ctx0, evaluation_timestamp="not-a-timestamp")
    c.raises(lambda: evaluate_with_optional_ai(rk, copy.deepcopy(ind0), copy.deepcopy(obs0), policy=on, config=config(),
             normalized_content=content, request_id="REQ-1", run_id="RUN-1", provider=valid_provider(), **bad_ctx),
             runtime.DetectionResultError, "Phase-3 host-identity failure propagates, not AI fallback")
    c.raises(lambda: evaluate_with_optional_ai(rk, copy.deepcopy(ind0), copy.deepcopy(obs0), policy=AIIntegrationPolicy(False),
             config=config(), normalized_content=content, request_id="REQ-1", run_id="RUN-1", provider=None, **bad_ctx),
             runtime.DetectionResultError, "Phase-3 failure propagates even on the deterministic-only path")

    # ---- caller data snapshotted before any provider call (no TOCTOU between hashed and consumed data)
    m_ind = copy.deepcopy(ind0)
    m_obs = copy.deepcopy(obs0)
    m_ctx = copy.deepcopy(ctx0)
    inner = valid_provider()

    class MutatingFixture:
        def extract(self, request):
            m_obs[0]["status"] = "NOT_OBSERVED"
            m_ind.clear()
            m_ctx["language"][:] = ["hi"]
            m_ctx["whole_evaluation_errors"].append({"code": "tampered"})
            return inner.extract(request)

    isolated = evaluate_with_optional_ai(rk, m_ind, m_obs, policy=on, config=config(), normalized_content=content,
                                         request_id="REQ-1", run_id="RUN-1", provider=MutatingFixture(), **m_ctx)
    c.eq(isolated.as_dict(), valid.as_dict(), "baseline and host metadata captured before provider mutation")

    # ---- non-canonical host material is a host-integrity error, never an optional AI fallback (incl. lone surrogate)
    sentinel = NeverExtract()
    cyclic = []
    cyclic.append(cyclic)
    for bad in ({1: "value"}, {"x": float("nan")}, {"x": float("inf")}, {"x": b"bytes"}, {"x": {1, 2}},
                {"x": object()}, {"x": cyclic}, {"x": "\ud800"}):
        c.raises(lambda value=bad: evaluate_with_optional_ai(rk, copy.deepcopy(ind0), [value], policy=on, config=config(),
                 normalized_content=content, request_id="REQ-1", run_id="RUN-1", provider=sentinel, **ctx0),
                 AIIntegrationInputError, "non-canonical host material rejected outside fallback")
    deep = {"leaf": 0}
    for _ in range(80):
        deep = {"nest": deep}
    c.raises(lambda: evaluate_with_optional_ai(rk, copy.deepcopy(ind0), [deep], policy=on, config=config(),
             normalized_content=content, request_id="REQ-1", run_id="RUN-1", provider=sentinel, **ctx0),
             AIIntegrationInputError, "excessively nested host material rejected outside fallback")
    c.eq(sentinel.calls, 0, "invalid host snapshot rejected before any provider call")

    # ---- fixture-metadata validator fails closed on malformed input
    c.raises(lambda: load_and_validate_fixture({"fixture_version": "9.9.9"}), ValueError, "malformed fixture version rejected")
    c.raises(lambda: load_and_validate_fixture(dict(fixture, cases=[])), ValueError, "empty fixture case list rejected")


def run_all_checks(rk):
    c = Check()
    fixture = load_and_validate_fixture()
    c.ok(len(fixture["cases"]) >= 15, "adversarial matrix carries the full cross-WP case family")
    outcomes = {}
    for case in fixture["cases"]:
        outcomes[case["case_id"]] = run_case(c, rk, fixture, case)
    run_probes(c, rk, fixture, outcomes)
    before = outcomes["A-ai-disabled"].detection_result.as_dict()["classification"]
    after = outcomes["B-valid-extraction"].detection_result.as_dict()["classification"]
    return c, len(fixture["cases"]), before, after


def main(argv=None):
    parser = argparse.ArgumentParser(description="P4-WP7 offline Phase-4 cross-WP closure validator")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    try:
        with tempfile.TemporaryDirectory(prefix="wp7-ai-closure-") as temporary:
            bundle = Path(temporary) / "bundle"
            build_bundle.build(bundle)
            checks, n_cases, before, after = run_all_checks(runtime.load_bundle(bundle))
    except Exception as exc:  # noqa: BLE001 — surface any setup/among-checks crash as a gate ERROR
        print(f"P4-WP7 AI CLOSURE: ERROR — {type(exc).__name__}: {exc}")
        return 2
    if not args.quiet:
        print(f"{checks.count - len(checks.failures)}/{checks.count} closure assertions passed over {n_cases} adversarial cases.")
        print(f"Synthetic governed-input fixture: {before} -> {after}; integration/security behavior only.")
    if checks.failures:
        for failure in checks.failures:
            print(f"  FAIL: {failure}")
        return 1
    print("P4-WP7 AI CLOSURE: PASS — offline cross-WP wiring/authority/fallback/replay boundaries only; G-09 OPEN.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
