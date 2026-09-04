"""TrustLens Phase 3 P3-WP7 — golden end-to-end replay runner.

Builds and loads one real immutable bundle, adapts the governed golden fixtures without extraction, executes
the closed WP3 -> WP4 -> WP5 -> WP6 composition, and compares every binding golden axis.  PUBLISHED cases use
only public production APIs.  The three lifecycle-preview cases first run the public PUBLISHED lane, then run the
complete PUBLISHED + APPROVED + PEER_REVIEW set through the explicit on-promotion/private-preview paths.

WP7 emits an internal frozen ``GoldenReplayResult`` only.  It does not assemble the promoted detection-result
envelope, create timestamps/evaluation ids, parse input_gloss, use expected values during execution, or perform
network/subprocess/LLM/NLP work.  G-09 remains open; this is deterministic regression evidence, not accuracy.

Usage: .venv/bin/python knowledge/validation/validate_wp7_golden_runner.py [--quiet] [--json]
Exit 0 only when corpus checks, every replay lane, and all in-memory runner self-tests pass.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import tempfile
from dataclasses import FrozenInstanceError, dataclass, fields
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from knowledge.publish import build_bundle  # noqa: E402
from knowledge.runtime import (  # noqa: E402
    EvaluationProfile,
    RuleEvaluator,
    RuleSuppressionExecutor,
    aggregate_decision,
    build_explanation,
    evaluate_decision_from_governed,
    load_bundle,
)
from knowledge.runtime.aggregation import _is_eligible_matched  # noqa: E402
from knowledge.runtime.explanation import (  # noqa: E402
    _authoritative_source_refs,
    _build_explanation,
)

GOLDEN = ROOT / "docs" / "03-detection" / "golden-decision-cases-v1.json"
CORPUS_CONTRACT = {"1.3.1": 15}
PREVIEW_LIFECYCLES = frozenset({"PUBLISHED", "APPROVED", "PEER_REVIEW"})
LIVE_REPLAY = "LIVE_REPLAY"
DESIGN_PREVIEW = "DESIGN_PREVIEW"
_STATUS_FOR = {
    "OBSERVED": "OBSERVED",
    "NOT_OBSERVED": "NOT_OBSERVED",
    "AMBIGUOUS": "AMBIGUOUS",
    "UNKNOWN": "UNKNOWN",
    "NOT_APPLICABLE": "NOT_APPLICABLE",
}
_PROVENANCE = {
    "extractor_id": "wp7-golden-fixture-adapter",
    "extractor_type": "USER_SUPPLIED",
    "extractor_version": "1.0.0",
}
_REQUIRED_EXPECTED = frozenset({
    "input_support_status", "classification", "fired_rules", "rule_states", "active_overrides",
    "severity", "matched_evidence_strength", "risk_level", "detection_confidence", "corroboration_band",
    "unknowns", "ambiguities", "recommended_actions", "live_publishable",
})
_SET_LIKE_EXPECTED = frozenset({
    "fired_rules", "active_overrides", "unknowns", "ambiguities", "blocked_suppressors",
})
_REPORTING_DETAIL = re.compile(r"\b1930\b|https?://|www\.|\+?\d[\d\s().-]{7,}\d")
_NETWORK_OR_PROCESS_IMPORT = re.compile(
    r"^\s*(?:import|from)\s+(?:socket|ssl|http|httplib|urllib|requests|httpx|aiohttp|ftplib|"
    r"telnetlib|smtplib|poplib|imaplib|subprocess)\b", re.MULTILINE,
)


class CorpusError(ValueError):
    """Malformed or unsupported golden corpus contract."""


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze(v) for v in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return value


@dataclass(frozen=True)
class GoldenReplayResult:
    """Internal equality-sensitive WP7 result; deliberately not the WP8 detection-result envelope."""

    case_id: str
    lane: str
    status: str
    decision: Mapping[str, Any]
    explanation: Mapping[str, Any]
    expected: Mapping[str, Any]
    actual: Mapping[str, Any]
    mismatches: tuple[str, ...]
    bundle_version: str
    bundle_content_digest: str
    action_policy_version: str
    assertion_count: int


@dataclass(frozen=True)
class CaseExecutionInput:
    """Only fields authorized to influence execution. Golden expectations and input_gloss cannot enter."""

    case_id: str
    language: Any
    script: Any
    live_publishable: Any
    governed_input: Any
    declared_indicators: Any


@dataclass(frozen=True)
class AdaptedFixture:
    indicator_observations: tuple[Mapping[str, Any], ...]
    normalized_observations: tuple[Mapping[str, Any], ...]
    language: str
    script: str
    support_status: str
    source: str


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

    def raises(self, fn, exc_type: type[BaseException], message: str) -> None:
        self.count += 1
        try:
            fn()
            self.failures.append(f"{message}: did not raise")
        except exc_type:
            pass
        except Exception as exc:  # noqa: BLE001
            self.failures.append(f"{message}: raised {type(exc).__name__}, wanted {exc_type.__name__}")


def _case_execution_input(case: Mapping[str, Any]) -> CaseExecutionInput:
    """Project a corpus case to execution-owned data before any runtime call (anti-self-fulfilment boundary)."""
    return CaseExecutionInput(
        case_id=case.get("id"),
        language=copy.deepcopy(case.get("language")),
        script=copy.deepcopy(case.get("script")),
        live_publishable=case.get("expected", {}).get("live_publishable"),
        governed_input=copy.deepcopy(case.get("governed_input")),
        declared_indicators=copy.deepcopy(case.get("declared_indicators")),
    )


def _derive_support(language: Any, script: Any) -> tuple[str, str, str]:
    """Derive current en/Latn MVP support from fixture metadata, never from expected output."""
    for label, values in (("language", language), ("script", script)):
        if (not isinstance(values, list) or not values
                or not all(isinstance(v, str) and bool(v) for v in values)):
            raise CorpusError(f"missing/malformed {label}: expected a non-empty array of non-empty strings")
    support = "SUPPORTED" if all(v == "en" for v in language) and all(v == "Latn" for v in script) else "UNSUPPORTED"
    return support, language[0], script[0]


def _adapt_fixture(inp: CaseExecutionInput) -> AdaptedFixture:
    """Defensively adapt golden fixture data to the governed WP3 contracts; performs no extraction."""
    support, language, script = _derive_support(inp.language, inp.script)
    if inp.governed_input is not None:
        gi = inp.governed_input
        if not isinstance(gi, Mapping):
            raise CorpusError(f"{inp.case_id}: governed_input must be an object")
        indicator = gi.get("indicator_observations")
        observations = gi.get("normalized_observations")
        if not isinstance(indicator, list) or not isinstance(observations, list):
            raise CorpusError(f"{inp.case_id}: governed_input must contain both governed observation arrays")
        return AdaptedFixture(tuple(copy.deepcopy(indicator)), tuple(copy.deepcopy(observations)),
                              language, script, support, "GOVERNED_INPUT")

    rows = inp.declared_indicators
    if not isinstance(rows, list):
        raise CorpusError(f"{inp.case_id}: declared_indicators must be an array when governed_input is absent")
    indicator_observations: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    for i, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise CorpusError(f"{inp.case_id}: declared_indicators[{i}] must be an object")
        iid = row.get("id") or row.get("indicator_id")
        matched = row.get("matched")
        polarity = row.get("polarity")
        if not isinstance(iid, str) or matched not in _STATUS_FOR or not isinstance(polarity, str):
            raise CorpusError(f"{inp.case_id}: malformed declared_indicators[{i}]")
        reg_polarity = polarity if polarity in ("POSITIVE", "NEGATIVE") else "POSITIVE"
        structural = row.get("structural_polarity") or (
            polarity if polarity in ("AFFIRMED", "NEGATED") else "AFFIRMED")
        refs_value = row.get("observation_refs")
        if refs_value is not None and (not isinstance(refs_value, list)
                                       or not all(isinstance(ref, str) for ref in refs_value)):
            raise CorpusError(f"{inp.case_id}: malformed observation_refs at declared_indicators[{i}]")
        refs = list(refs_value) if refs_value else [f"obs-{i:02d}"]
        for ref in refs:
            if ref in seen_refs:
                continue
            seen_refs.add(ref)
            observations.append({
                "observation_id": ref,
                "observation_type": "CLAIM",
                "source_input_id": f"{inp.case_id}-input",
                "status": _STATUS_FOR[matched],
                "polarity": structural,
                "attribution": row.get("attribution") or "FIRST_PARTY",
                "mood": row.get("mood") or "DIRECTIVE",
                "offsets": {"start": i * 10, "end": i * 10 + 5},
                "provenance": dict(_PROVENANCE),
            })
        projected: dict[str, Any] = {
            "indicator_id": iid,
            "polarity": reg_polarity,
            "matched": matched,
            "input_id": f"{inp.case_id}-input",
            "provenance": dict(_PROVENANCE),
            "observation_refs": refs,
        }
        confidence = row.get("confidence")
        if confidence is not None:
            projected["confidence"] = {"level": confidence}
        indicator_observations.append(projected)
    return AdaptedFixture(tuple(indicator_observations), tuple(observations), language, script, support,
                          "DECLARED_INDICATORS")


def _validate_corpus(corpus: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(corpus, Mapping):
        raise CorpusError("golden corpus must be an object")
    version = corpus.get("cases_version")
    if version not in CORPUS_CONTRACT:
        raise CorpusError(f"unsupported cases_version {version!r}")
    cases = corpus.get("cases")
    if not isinstance(cases, list):
        raise CorpusError("golden corpus cases must be an array")
    wanted = CORPUS_CONTRACT[version]
    if len(cases) != wanted:
        raise CorpusError(f"cases_version {version} requires {wanted} cases, got {len(cases)}")
    seen: set[str] = set()
    out: list[Mapping[str, Any]] = []
    for i, case in enumerate(cases):
        if not isinstance(case, Mapping) or not isinstance(case.get("id"), str):
            raise CorpusError(f"case[{i}] missing string id")
        cid = case["id"]
        if cid in seen:
            raise CorpusError(f"duplicate case id {cid}")
        seen.add(cid)
        expected = case.get("expected")
        if not isinstance(expected, Mapping):
            raise CorpusError(f"{cid}: missing expected object")
        missing = sorted(_REQUIRED_EXPECTED - set(expected))
        if missing:
            raise CorpusError(f"{cid}: missing expected fields {missing}")
        if not isinstance(expected.get("live_publishable"), bool):
            raise CorpusError(f"{cid}: expected.live_publishable must be boolean")
        out.append(copy.deepcopy(case))
    return tuple(out)


def _canon(item: Mapping[str, Any]) -> str:
    return json.dumps(dict(item), sort_keys=True, separators=(",", ":"))


def _projection(decision, explanation_result) -> dict[str, Any]:
    blocked: set[str] = set()
    for result in decision.rule_results:
        suppression = result.get("suppression") or {}
        blocked.update(suppression.get("blocked_suppressors", ()))
        blocked.update(suppression.get("blocked_severity_caps", ()))
    return {
        "input_support_status": decision.input_support_status,
        "classification": decision.classification,
        "fired_rules": list(decision.matched_rules),
        "rule_states": {r["rule_id"]: r["evaluation_state"] for r in decision.rule_results},
        "active_overrides": list(decision.active_overrides),
        "blocked_suppressors": sorted(blocked),
        "severity": decision.decision_severity,
        "matched_evidence_strength": decision.matched_evidence_strength,
        "risk_level": decision.risk_level,
        "detection_confidence": decision.detection_confidence,
        "corroboration_band": decision.corroboration.get("band"),
        "unknowns": list(decision.unknowns),
        "ambiguities": list(decision.ambiguities),
        "recommended_actions": [a["action_code"] for a in explanation_result.recommended_actions],
        "governing_rule_id": decision.governing_rule_id,
    }


def _assert(mismatches: list[str], condition: bool, message: str) -> int:
    if not condition:
        mismatches.append(message)
    return 1


def _compare_golden(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> tuple[list[str], int]:
    mismatches: list[str] = []
    count = 0
    scalar_map = {
        "input_support_status": "input_support_status",
        "classification": "classification",
        "severity": "severity",
        "matched_evidence_strength": "matched_evidence_strength",
        "risk_level": "risk_level",
        "detection_confidence": "detection_confidence",
        "corroboration_band": "corroboration_band",
    }
    for expected_key, actual_key in scalar_map.items():
        count += _assert(mismatches, expected[expected_key] == actual[actual_key],
                         f"{expected_key}: expected {expected[expected_key]!r}, got {actual[actual_key]!r}")
    for key in _SET_LIKE_EXPECTED:
        if key in expected:
            wanted = sorted(set(expected[key]))
            got = sorted(set(actual[key]))
            count += _assert(mismatches, wanted == got, f"{key}: expected {wanted!r}, got {got!r}")
    count += _assert(mismatches, list(expected["recommended_actions"]) == list(actual["recommended_actions"]),
                     f"recommended_actions: expected {expected['recommended_actions']!r}, "
                     f"got {actual['recommended_actions']!r}")
    for rid, state in expected["rule_states"].items():
        count += _assert(mismatches, actual["rule_states"].get(rid) == state,
                         f"rule_states[{rid}]: expected {state!r}, got {actual['rule_states'].get(rid)!r}")
    governing_key = "governing_rule_id" if "governing_rule_id" in expected else (
        "governing_rule" if "governing_rule" in expected else None)
    if governing_key:
        count += _assert(mismatches, expected[governing_key] == actual["governing_rule_id"],
                         f"{governing_key}: expected {expected[governing_key]!r}, "
                         f"got {actual['governing_rule_id']!r}")
    return mismatches, count


def _walk(value: Any, path: str = "result") -> Iterable[tuple[str, Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, f"{path}.{key}")
    elif isinstance(value, list | tuple):
        for i, child in enumerate(value):
            yield from _walk(child, f"{path}[{i}]")


def _explanation_checks(decision, explanation_result, rk, rule_of,
                        raw_spans: Iterable[str]) -> tuple[list[str], int]:
    ex = explanation_result.explanation
    mismatches: list[str] = []
    count = 0
    for key in ("summary", "what_was_detected", "why", "detection_confidence_reason"):
        count += _assert(mismatches, isinstance(ex.get(key), str) and bool(ex[key]),
                         f"explanation.{key} must be a non-empty string")
    count += _assert(mismatches, list(ex.get("rules_fired", ())) == list(decision.matched_rules),
                     "explanation.rules_fired must equal decision.matched_rules")
    count += _assert(mismatches, list(ex.get("matched_indicators", ())) == list(decision.matched_positive_indicators),
                     "explanation.matched_indicators must equal decision.matched_positive_indicators")
    override_ids = [item.get("override_id") for item in ex.get("overrides_applied", ())]
    count += _assert(mismatches, override_ids == list(decision.active_overrides),
                     "explanation.overrides_applied must equal decision.active_overrides")
    count += _assert(mismatches, list(ex.get("remaining_unknowns", ())) == list(decision.unknowns),
                     "explanation.remaining_unknowns must equal decision.unknowns")

    governed_steps = {step for result in decision.rule_results
                      for step in (rule_of(result.get("rule_id")) or {}).get("explanation", {}).get(
                          "verification_steps", ())}
    emitted_steps = list(ex.get("verification_steps", ()))
    count += _assert(mismatches, all(isinstance(step, str) and step in governed_steps for step in emitted_steps),
                     "explanation.verification_steps must be copied from governed rules")

    expected_evidence: dict[str, Mapping[str, Any]] = {}
    for result in decision.rule_results:
        if _is_eligible_matched(result):
            for item in _authoritative_source_refs(rule_of(result.get("rule_id"))):
                expected_evidence[_canon(item)] = item
    emitted_evidence = {_canon(item): item for item in ex.get("evidence_basis", ())}
    count += _assert(mismatches, sorted(emitted_evidence) == sorted(expected_evidence),
                     "explanation.evidence_basis must exactly equal eligible governed source references")

    supporting = list(ex.get("supporting_observations", ()))
    count += _assert(mismatches, all(isinstance(item, Mapping)
                                     and set(item) <= {"observation_ref", "span"} for item in supporting),
                     "supporting_observations may contain only observation_ref and span")
    suppression = list(ex.get("suppression_considered", ()))
    count += _assert(mismatches, all(isinstance(item, Mapping) and item.get("suppressor")
                                     and item.get("outcome") in {
                                         "APPLIED", "BLOCKED_BY_OVERRIDE", "RECORDED_CONTEXT_ONLY"}
                                     for item in suppression),
                     "suppression_considered must contain governed suppressor/outcome records")

    result_dict = explanation_result.as_dict()
    walked = list(_walk(result_dict))
    count += _assert(mismatches, all(not path.endswith((".raw_span", ".redacted_quote"))
                                     for path, _ in walked),
                     "WP6 output must contain neither raw_span nor redacted_quote")
    count += _assert(mismatches, all(not isinstance(value, float) for _, value in walked),
                     "WP6 output must contain no numeric probability")
    rendered = json.dumps(result_dict, sort_keys=True)
    sensitive = [span for span in raw_spans if isinstance(span, str) and len(span) >= 8]
    count += _assert(mismatches, all(span not in rendered for span in sensitive),
                     "governed raw observation spans must not leak into WP6 output")
    generated_text = " ".join(str(ex.get(key, "")) for key in (
        "summary", "what_was_detected", "why", "detection_confidence_reason", "limitations"))
    count += _assert(mismatches, not _REPORTING_DETAIL.search(generated_text),
                     "generated WP6 prose must not invent a reporting URL/phone/procedure")
    if decision.classification in {"NO_SCAM_PATTERN", "UNSUPPORTED", "ERROR"}:
        lower = generated_text.lower()
        count += _assert(mismatches, all(term not in lower for term in ("this is safe", "legitimate", "no risk")),
                         f"{decision.classification} wording must not be falsely reassuring")
    return mismatches, count


def _preview_live_boundary_checks(decision, explanation_result, rk,
                                  preview_only_ids: set[str]) -> tuple[list[str], int]:
    mismatches: list[str] = []
    count = 0
    matched = set(decision.matched_rules)
    fired = set(explanation_result.explanation.get("rules_fired", ()))
    action_rules = {rid for action in explanation_result.recommended_actions
                    for rid in action.get("reason_rule_ids", ())}
    count += _assert(mismatches, not matched & preview_only_ids,
                     f"live decision includes unpublished matched rules {sorted(matched & preview_only_ids)}")
    count += _assert(mismatches, not fired & preview_only_ids,
                     f"live explanation includes unpublished fired rules {sorted(fired & preview_only_ids)}")
    count += _assert(mismatches, not action_rules & preview_only_ids,
                     f"live actions cite unpublished rules {sorted(action_rules & preview_only_ids)}")

    live_sources = {_canon(item) for rid in matched for item in _authoritative_source_refs(rk.published_rule(rid))}
    unpublished_sources = {_canon(item) for rid in preview_only_ids
                           for item in _authoritative_source_refs(rk.rule(rid))}
    exclusive_unpublished = unpublished_sources - live_sources
    emitted = {_canon(item) for item in explanation_result.explanation.get("evidence_basis", ())}
    count += _assert(mismatches, not emitted & exclusive_unpublished,
                     "live evidence_basis contains preview-only governed evidence")
    return mismatches, count


class GoldenRunner:
    def __init__(self, rk) -> None:
        self.rk = rk
        self.preview_rule_ids = tuple(sorted(
            rid for rid in rk.rule_ids()
            if (rk.rule(rid).get("lifecycle") or {}).get("status") in PREVIEW_LIFECYCLES
        ))
        self.preview_only_ids = set(self.preview_rule_ids) - set(rk.published_rule_ids())

    def _live(self, fixture: AdaptedFixture):
        decision = evaluate_decision_from_governed(
            self.rk, fixture.indicator_observations, fixture.normalized_observations,
            input_support_status=fixture.support_status, language=fixture.language, script=fixture.script,
        )
        explanation = build_explanation(decision, rk=self.rk, observations=fixture.normalized_observations)
        return decision, explanation

    def _preview(self, fixture: AdaptedFixture):
        evaluator = RuleEvaluator(self.rk, EvaluationProfile())
        suppressor = RuleSuppressionExecutor(self.rk)
        wp4_results = tuple(suppressor.apply(evaluator.evaluate_on_promotion_from_governed(
            rid, fixture.indicator_observations, fixture.normalized_observations,
            language=fixture.language, script=fixture.script,
        )) for rid in self.preview_rule_ids)
        decision = aggregate_decision(
            wp4_results, input_support_status=fixture.support_status, rk=self.rk,
            language=fixture.language, script=fixture.script,
        )
        explanation = _build_explanation(
            decision, rk=self.rk, observations=fixture.normalized_observations, live=False)
        return decision, explanation

    def _error_result(self, case_id: str, lane: str, expected: Mapping[str, Any], exc: Exception) -> GoldenReplayResult:
        message = f"{type(exc).__name__}: {exc}"
        return GoldenReplayResult(
            case_id=case_id, lane=lane, status="ERROR", decision=_freeze({}), explanation=_freeze({}),
            expected=_freeze(copy.deepcopy(expected)), actual=_freeze({}), mismatches=(message,),
            bundle_version=self.rk.bundle_version, bundle_content_digest=self.rk.content_digest,
            action_policy_version=self.rk.action_policy_version, assertion_count=1,
        )

    def _result(self, inp: CaseExecutionInput, expected: Mapping[str, Any], fixture: AdaptedFixture,
                lane: str) -> GoldenReplayResult:
        try:
            decision, explanation_result = self._live(fixture) if lane == LIVE_REPLAY else self._preview(fixture)
            actual = _projection(decision, explanation_result)
            if lane == DESIGN_PREVIEW or inp.live_publishable:
                mismatches, count = _compare_golden(expected, actual)
            else:
                mismatches, count = [], 0
                count += _assert(mismatches, fixture.support_status == expected["input_support_status"],
                                 f"derived support expected {expected['input_support_status']!r}, "
                                 f"got {fixture.support_status!r}")
                more, n = _preview_live_boundary_checks(
                    decision, explanation_result, self.rk, self.preview_only_ids)
                mismatches.extend(more)
                count += n
            raw_spans = [o.get("raw_span") for o in fixture.normalized_observations if isinstance(o, Mapping)]
            checks, n = _explanation_checks(
                decision, explanation_result, self.rk,
                self.rk.published_rule if lane == LIVE_REPLAY else self.rk.rule,
                raw_spans,
            )
            mismatches.extend(checks)
            count += n
            return GoldenReplayResult(
                case_id=inp.case_id, lane=lane, status="PASS" if not mismatches else "FAIL",
                decision=_freeze(decision.as_decision_dict()), explanation=_freeze(explanation_result.as_dict()),
                expected=_freeze(copy.deepcopy(expected)), actual=_freeze(actual), mismatches=tuple(mismatches),
                bundle_version=self.rk.bundle_version, bundle_content_digest=self.rk.content_digest,
                action_policy_version=self.rk.action_policy_version, assertion_count=count,
            )
        except Exception as exc:  # noqa: BLE001 — stage failures become explicit per-case ERROR records
            return self._error_result(inp.case_id, lane, expected, exc)

    def run_case(self, case: Mapping[str, Any]) -> tuple[GoldenReplayResult, ...]:
        expected = case.get("expected") if isinstance(case.get("expected"), Mapping) else {}
        inp = _case_execution_input(case)
        try:
            fixture = _adapt_fixture(inp)
        except Exception as exc:  # noqa: BLE001
            return (self._error_result(str(inp.case_id), LIVE_REPLAY, expected, exc),)
        if inp.live_publishable:
            return (self._result(inp, expected, fixture, LIVE_REPLAY),)
        live = self._result(inp, expected, fixture, LIVE_REPLAY)
        preview = self._result(inp, expected, fixture, DESIGN_PREVIEW)
        return live, preview

    def run_cases(self, cases: Iterable[Mapping[str, Any]]) -> tuple[GoldenReplayResult, ...]:
        results: list[GoldenReplayResult] = []
        for case in cases:
            results.extend(self.run_case(case))
        return tuple(results)


def _equality_projection(results: Iterable[GoldenReplayResult]) -> Any:
    return tuple((r.case_id, r.lane, r.status, _thaw(r.decision), _thaw(r.explanation),
                  _thaw(r.actual), r.mismatches, r.bundle_version, r.bundle_content_digest,
                  r.action_policy_version) for r in results)


def _reverse_dict_keys(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _reverse_dict_keys(value[key]) for key in reversed(list(value))}
    if isinstance(value, list):
        return [_reverse_dict_keys(v) for v in value]
    return copy.deepcopy(value)


def _self_tests(runner: GoldenRunner, corpus: Mapping[str, Any], cases: tuple[Mapping[str, Any], ...],
                first_results: tuple[GoldenReplayResult, ...], original_golden_bytes: bytes) -> Check:
    c = Check()
    c.eq(runner.rk.manifest_schema_version, "1.1.0", "bundle manifest schema")
    c.ok(runner.rk.has_action_policy(), "bundle has governed action policy")
    c.ok(bool(runner.rk.action_policy_version), "bundle action-policy version present")
    c.eq(tuple(sorted(runner.preview_rule_ids)), runner.preview_rule_ids, "preview rule ids canonical")
    c.ok(all((runner.rk.rule(rid).get("lifecycle") or {}).get("status") in PREVIEW_LIFECYCLES
             for rid in runner.preview_rule_ids), "preview set contains only eligible lifecycle states")
    c.ok(all(rid in runner.preview_rule_ids for rid in runner.rk.published_rule_ids()),
         "preview set includes every PUBLISHED rule")
    c.ok(all((runner.rk.rule(rid).get("lifecycle") or {}).get("status") not in PREVIEW_LIFECYCLES
             for rid in set(runner.rk.rule_ids()) - set(runner.preview_rule_ids)),
         "preview set excludes every non-evaluable lifecycle state")

    c.eq(corpus["cases_version"], "1.3.1", "corpus version pinned")
    c.eq(len(cases), 15, "corpus versioned count")
    c.eq(len({case["id"] for case in cases}), 15, "corpus ids unique")
    c.eq(sum(bool(case["expected"]["live_publishable"]) for case in cases), 12, "12 live-only cases")
    c.eq(sum(not bool(case["expected"]["live_publishable"]) for case in cases), 3, "3 preview cases")
    c.eq(sum(r.lane == LIVE_REPLAY for r in first_results), 15, "all cases get a live lane")
    c.eq(sum(r.lane == DESIGN_PREVIEW for r in first_results), 3, "preview cases get a second lane")
    c.eq({r.case_id for r in first_results}, {case["id"] for case in cases}, "all cases reported")

    second_results = runner.run_cases(cases)
    c.eq(_equality_projection(second_results), _equality_projection(first_results),
         "full replay equality-sensitive projection deterministic")
    c.eq(GOLDEN.read_bytes(), original_golden_bytes, "committed golden object remains byte-identical")

    by_id = {case["id"]: case for case in cases}
    by_lane = {(r.case_id, r.lane): r for r in first_results}
    # Lifecycle dual-lane regression for every preview case (GDC-07/GDC-08/GDC-10). The unpublished binding
    # rule(s) are derived from the case's binding topology (fired_rules OR bound rule_states) via governed
    # lifecycle metadata — never a rule-id prefix and never a case-id lane branch. GDC-08 differs from
    # GDC-07/GDC-10: its unpublished TL-MAL-003 is SUPPRESSED (not fired) in the design, so the excluded rule
    # lives in rule_states, and preview reproduction is asserted structurally (the preview lane reproduces the
    # corrected golden decision, i.e. status PASS with no mismatch).
    for cid in ("GDC-07", "GDC-08", "GDC-10"):
        live = by_lane[(cid, LIVE_REPLAY)]
        preview = by_lane[(cid, DESIGN_PREVIEW)]
        exp = by_id[cid]["expected"]
        topology = set(exp.get("fired_rules", ())) | set(exp.get("rule_states", {}))
        unpublished = sorted(rid for rid in topology
                             if ((runner.rk.rule(rid) or {}).get("lifecycle") or {}).get("status") != "PUBLISHED")
        c.ok(bool(unpublished), f"{cid} binding topology rests on an unpublished rule (a preview case)")
        for rid in unpublished:
            c.ok(rid not in live.actual.get("fired_rules", ()), f"{cid} live excludes unpublished {rid}")
        c.eq(live.status, "PASS", f"{cid} live lane is lifecycle-safe (not compared to the design decision)")
        c.eq(preview.status, "PASS", f"{cid} preview reproduces the corrected golden decision")
        c.eq(list(preview.actual.get("recommended_actions", ())), exp["recommended_actions"],
             f"{cid} preview actions reproduce the golden")

    c.eq(by_lane[("GDC-02", LIVE_REPLAY)].actual.get("classification"), "NO_SCAM_PATTERN", "GDC-02 benign")
    c.eq(by_lane[("GDC-03", LIVE_REPLAY)].actual.get("classification"), "NO_SCAM_PATTERN", "GDC-03 reported")
    c.eq(list(by_lane[("GDC-03", LIVE_REPLAY)].actual.get("recommended_actions", ())),
         ["REPORT_CYBERCRIME", "PRESERVE_EVIDENCE"], "GDC-03 informational actions")
    c.ok("HR_UPI_PIN_TO_RECEIVE" in by_lane[("GDC-04", LIVE_REPLAY)].actual.get("active_overrides", ()),
         "GDC-04 receive-money PIN override")
    c.eq(by_lane[("GDC-05", LIVE_REPLAY)].actual.get("classification"), "NO_SCAM_PATTERN", "GDC-05 merchant payment")
    c.ok(bool(by_lane[("GDC-11", LIVE_REPLAY)].actual.get("ambiguities")), "GDC-11 ambiguity survives")
    c.eq(by_lane[("GDC-12", LIVE_REPLAY)].actual.get("classification"), "UNSUPPORTED", "GDC-12 unsupported")
    c.ok(by_lane[("GDC-12", LIVE_REPLAY)].actual.get("classification") != "NO_SCAM_PATTERN",
         "GDC-12 never benign")
    c.eq(by_lane[("GDC-13", LIVE_REPLAY)].actual.get("classification"), "INSUFFICIENT_EVIDENCE",
         "GDC-13 remains uncertain")

    g15 = by_id["GDC-15"]
    inp15 = _case_execution_input(g15)
    fixture15 = _adapt_fixture(inp15)
    c.eq(list(fixture15.indicator_observations), g15["governed_input"]["indicator_observations"],
         "GDC-15 governed indicator observations pass through unchanged")
    c.eq(list(fixture15.normalized_observations), g15["governed_input"]["normalized_observations"],
         "GDC-15 normalized observations pass through unchanged")
    otp_refs = [tuple(row["observation_refs"]) for row in fixture15.indicator_observations
                if row.get("indicator_id") == "CREDENTIAL_REQUEST_OTP"]
    c.eq(otp_refs, [("g15-otp-neg",), ("g15-otp-live",)], "GDC-15 separate OTP occurrences retained")
    c.eq(by_lane[("GDC-15", LIVE_REPLAY)].actual.get("classification"), "SCAM_PATTERN_DETECTED",
         "GDC-15 classification")
    c.ok("HR_OTP_DISCLOSURE_REQUEST" in by_lane[("GDC-15", LIVE_REPLAY)].actual.get("active_overrides", ()),
         "GDC-15 hard-risk override active")

    reversed_fixture = AdaptedFixture(
        tuple(reversed(fixture15.indicator_observations)), tuple(reversed(fixture15.normalized_observations)),
        fixture15.language, fixture15.script, fixture15.support_status, fixture15.source,
    )
    base_decision, base_explanation = runner._live(fixture15)
    rev_decision, rev_explanation = runner._live(reversed_fixture)
    c.eq((_projection(rev_decision, rev_explanation), rev_explanation.as_dict()),
         (_projection(base_decision, base_explanation), base_explanation.as_dict()),
         "GDC-15 governed observation-array reversal deterministic")
    reordered_case = _reverse_dict_keys(g15)
    reordered_fixture = _adapt_fixture(_case_execution_input(reordered_case))
    key_decision, key_explanation = runner._live(reordered_fixture)
    c.eq((_projection(key_decision, key_explanation), key_explanation.as_dict()),
         (_projection(base_decision, base_explanation), base_explanation.as_dict()),
         "equivalent dictionary-key order deterministic")

    whole_error = {"scope": "WHOLE_EVALUATION", "stage": "OTHER",
                   "code": "WP7_SYNTHETIC_ERROR", "message": "supported whole evaluation refused"}
    error_decision = aggregate_decision([], input_support_status="SUPPORTED", rk=runner.rk,
                                        whole_evaluation_errors=[whole_error])
    error_explanation = build_explanation(error_decision, rk=runner.rk)
    c.eq(error_decision.classification, "ERROR", "synthetic whole error classification")
    c.ok(error_decision.classification != "NO_SCAM_PATTERN", "synthetic whole error never benign")
    c.eq([a["action_code"] for a in error_explanation.recommended_actions], [],
         "synthetic supported whole error emits only governed empty action set")
    c.ok("could not be completed" in error_explanation.explanation["summary"].lower(),
         "synthetic whole error gets governed ERROR wording")

    # Expectations are assertions only: five mutations are detected while actual execution remains identical.
    mutation_case = by_id["GDC-01"]
    baseline_result = runner.run_case(mutation_case)[0]
    mutations = {
        "classification": "NO_SCAM_PATTERN",
        "risk_level": "LOW",
        "fired_rules": [],
        "active_overrides": [],
        "recommended_actions": [],
    }
    for key, value in mutations.items():
        changed = copy.deepcopy(mutation_case)
        changed["expected"][key] = value
        result = runner.run_case(changed)[0]
        c.ok(any(key in mismatch for mismatch in result.mismatches), f"mutated expected {key} is detected")
        c.eq(_thaw(result.actual), _thaw(baseline_result.actual),
             f"mutated expected {key} does not alter execution")

    bad_version = copy.deepcopy(corpus)
    bad_version["cases_version"] = "9.9.9"
    c.raises(lambda: _validate_corpus(bad_version), CorpusError, "unsupported corpus version")
    bad_count = copy.deepcopy(corpus)
    bad_count["cases"].pop()
    c.raises(lambda: _validate_corpus(bad_count), CorpusError, "versioned count mismatch")
    duplicate = copy.deepcopy(corpus)
    duplicate["cases"][1]["id"] = duplicate["cases"][0]["id"]
    c.raises(lambda: _validate_corpus(duplicate), CorpusError, "duplicate case id")
    missing_expected = copy.deepcopy(corpus)
    missing_expected["cases"][0].pop("expected")
    c.raises(lambda: _validate_corpus(missing_expected), CorpusError, "missing expected object")
    missing_axis = copy.deepcopy(corpus)
    missing_axis["cases"][0]["expected"].pop("classification")
    c.raises(lambda: _validate_corpus(missing_axis), CorpusError, "missing binding expected axis")

    malformed = copy.deepcopy(by_id["GDC-01"])
    malformed.pop("language")
    continued = runner.run_cases((malformed, by_id["GDC-02"]))
    c.eq(continued[0].status, "ERROR", "malformed support metadata becomes CASE ERROR")
    c.ok(any(r.case_id == "GDC-02" and r.status != "ERROR" for r in continued),
         "one case error does not hide later cases")
    c.raises(lambda: _derive_support([], ["Latn"]), CorpusError, "empty language metadata rejected")
    c.raises(lambda: _derive_support(["en"], "Latn"), CorpusError, "malformed script metadata rejected")

    c.raises(lambda: setattr(first_results[0], "status", "PASS"), FrozenInstanceError,
             "GoldenReplayResult is frozen")
    c.raises(lambda: dict.__setitem__(first_results[0].decision, "classification", "FORGED"), TypeError,
             "GoldenReplayResult mappings are deeply read-only")
    field_names = {field.name for field in fields(GoldenReplayResult)}
    c.ok(not field_names & {"evaluation_id", "timestamp", "created_at", "persistence", "provenance"},
         "WP7 result contains no WP8 final-envelope fields")
    source = Path(__file__).read_text(encoding="utf-8")
    c.ok(not _NETWORK_OR_PROCESS_IMPORT.search(source), "WP7 validator has no network/subprocess imports")
    c.ok("input_gloss" not in CaseExecutionInput.__annotations__, "WP7 execution projection excludes input_gloss")
    return c


def _result_dict(result: GoldenReplayResult) -> dict[str, Any]:
    return {
        "case_id": result.case_id,
        "lane": result.lane,
        "status": result.status,
        "decision": _thaw(result.decision),
        "explanation": _thaw(result.explanation),
        "expected": _thaw(result.expected),
        "actual": _thaw(result.actual),
        "mismatches": list(result.mismatches),
        "bundle_version": result.bundle_version,
        "bundle_content_digest": result.bundle_content_digest,
        "action_policy_version": result.action_policy_version,
        "assertion_count": result.assertion_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P3-WP7 deterministic golden end-to-end replay")
    parser.add_argument("--quiet", action="store_true", help="suppress per-case PASS output")
    parser.add_argument("--json", action="store_true", help="emit machine-readable replay report")
    args = parser.parse_args(argv)

    original_golden_bytes = GOLDEN.read_bytes()
    try:
        corpus = json.loads(original_golden_bytes)
        cases = _validate_corpus(corpus)
        with tempfile.TemporaryDirectory(prefix="wp7-golden-") as tmp:
            bundle_dir = Path(tmp) / "bundle"
            build_bundle.build(bundle_dir)
            rk = load_bundle(bundle_dir)
            if rk.manifest_schema_version != "1.1.0" or not rk.has_action_policy() or not rk.action_policy_version:
                raise CorpusError("current bundle is not WP6/WP7-capable (manifest 1.1 + action policy required)")
            runner = GoldenRunner(rk)
            results = runner.run_cases(cases)
            self_checks = _self_tests(runner, corpus, cases, results, original_golden_bytes)
    except Exception as exc:  # noqa: BLE001
        if args.json:
            print(json.dumps({"gate": "ERROR", "error": f"{type(exc).__name__}: {exc}"}, indent=2))
        else:
            print(f"P3-WP7 GOLDEN RUNNER: ERROR — {type(exc).__name__}: {exc}")
        return 2

    result_failures = [r for r in results if r.status != "PASS"]
    failed_assertions = sum(len(r.mismatches) for r in results) + len(self_checks.failures)
    assertion_count = sum(r.assertion_count for r in results) + self_checks.count
    passed_assertions = assertion_count - failed_assertions

    if args.json:
        print(json.dumps({
            "gate": "PASS" if not result_failures and not self_checks.failures else "FAIL",
            "cases_version": corpus["cases_version"],
            "cases": len(cases),
            "replay_results": [_result_dict(r) for r in results],
            "self_test_failures": self_checks.failures,
            "assertions": {"passed": passed_assertions, "total": assertion_count},
            "bundle": {"version": rk.bundle_version, "content_digest": rk.content_digest,
                       "action_policy_version": rk.action_policy_version},
        }, indent=2))
    else:
        if not args.quiet:
            print(f"P3-WP7 golden end-to-end replay — corpus {corpus['cases_version']} ({len(cases)} cases), "
                  f"bundle {rk.bundle_version}, action_policy {rk.action_policy_version}")
            for result in results:
                print(f"  {result.case_id:<7} {result.lane:<14} {result.status}")
                for mismatch in result.mismatches:
                    print(f"    - {mismatch}")
        elif result_failures or self_checks.failures:
            for result in result_failures:
                print(f"  {result.case_id} {result.lane} {result.status}: {'; '.join(result.mismatches)}")
        print(f"{passed_assertions}/{assertion_count} assertions passed.")
        if result_failures or self_checks.failures:
            print(f"P3-WP7 GOLDEN RUNNER: FAIL — {len(result_failures)} replay lane(s), "
                  f"{len(self_checks.failures)} runner self-test(s) failed")
            for failure in self_checks.failures:
                print(f"  - SELFTEST: {failure}")
        else:
            print("P3-WP7 GOLDEN RUNNER: PASS — 15 golden cases composed through WP3→WP4→WP5→WP6 "
                  "(12 live-only + 3 dual live/design-preview), exact binding-axis/action comparison, "
                  "structural explanation/provenance checks, deterministic replay, offline and fail-closed.")

    return 1 if result_failures or self_checks.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
