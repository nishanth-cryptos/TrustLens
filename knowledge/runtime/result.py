"""TrustLens Phase 3 P3-WP8 — engine integration + final DetectionResult assembly.

The production-facing deterministic integration boundary that closes Phase 3 (DET-001 pipeline stage 19,
"Result assembly with full version pinning"). It turns governed observation DATA + trusted envelope context
(identity/time, language/script, support status) + an already-loaded immutable ``RuntimeKnowledge`` into ONE
schema-valid, semantically-valid, fully-provenance-pinned, immutable ``DetectionResult`` conforming to the
promoted ``detection-result.schema.json`` (``result_contract_version`` 1.1.0). It adds ZERO scam-detection
semantics: every decision quantity comes from the authoritative WP5 ``DecisionResult`` and every explanation/
action from the authoritative WP6 ``ExplanationResult``; WP8 only orchestrates, maps, pins, validates and
reconciles.

Support-first orchestration (DET-001 §3). Only SUPPORTED / PARTIALLY_SUPPORTED execute rules
(WP3→WP4→WP5 via ``evaluate_decision_from_governed``); UNSUPPORTED / INSUFFICIENT_INFORMATION / ERROR and any
trusted whole-evaluation error route through the authoritative WP5 aggregation boundary over an EMPTY
rule-result set — no rule ever runs — so a skipped evaluation can never be reported as ``NO_SCAM_PATTERN``.

Trust boundaries. Identity/time are envelope-only and never influence any decision quantity. ``engine_version``
is the runtime-owned constant (``engine.ENGINE_VERSION``); a caller cannot override it, the profile, or any
decision/explanation/provenance field. ``whole_evaluation_errors`` are TRUSTED integration diagnostics, not
end-user input. Established upstream typed failures (``BundleLoadError``/``AggregationError``/
``ExplanationError``/``EvaluatorError``) propagate; WP8 never catches-all into a generic result. A bundle that
failed to load never reaches here, so provenance is never fabricated.

This module also OWNS the reusable promoted cross-field semantic invariants (``semantic_violations`` and
helpers), moved here from ``validate_runtime_contracts.py`` (which now imports them) — one authoritative copy,
reusing ``aggregation.RISK_MATRIX`` and the promoted action vocabulary rather than a second policy matrix.
"""

from __future__ import annotations

import datetime
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .aggregation import (
    CONFIDENCE_POLICY_ID,
    RISK_MATRIX,
    RISK_MATRIX_ID,
    DecisionResult,
    aggregate_decision,
    evaluate_decision_from_governed,
)
from .engine import ENGINE_VERSION
from .evaluator import DEFAULT_PROFILE
from .explanation import _ACTION_ORDER, ExplanationResult, build_explanation
from .runtime_knowledge import freeze

_ROOT = Path(__file__).resolve().parents[2]
_DETECTION_SCHEMA_PATH = _ROOT / "knowledge" / "schemas" / "detection" / "detection-result.schema.json"
_RULE_EVAL_SCHEMA_PATH = _ROOT / "knowledge" / "schemas" / "detection" / "rule-evaluation-result.schema.json"

RESULT_CONTRACT_VERSION = "1.1.0"

_SUPPORT_VALUES = frozenset({"SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "INSUFFICIENT_INFORMATION", "ERROR"})
_EVALUABLE_SUPPORT = frozenset({"SUPPORTED", "PARTIALLY_SUPPORTED"})

def _is_real_iso8601_instant(value: Any) -> bool:
    """A REAL, timezone-aware ISO-8601 calendar instant (M2). Uses the stdlib parser so impossible calendar
    values (month 99, 2026-02-30, hour 99) and naive/offset-less timestamps are rejected — not just a shape
    check. Provenance-only; the engine never reads a clock and never mutates the caller's serialized value."""
    if not isinstance(value, str) or not value:
        return False
    text = value[:-1] + "+00:00" if value.endswith("Z") else value   # normalise a trailing Z for the parser
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


# ================================================================ typed error


class DetectionResultError(Exception):
    """Fail-closed P3-WP8 assembly/integration error. ``.code`` is a stable, greppable token:
    ``INVALID_INPUT_CONTEXT``, ``INVALID_IDENTITY``, ``PROFILE_MISMATCH``, ``PROVENANCE_MISMATCH``,
    ``ACTION_POLICY_MISMATCH``, ``RESULT_SCHEMA_INVALID``, ``RESULT_SEMANTIC_INVALID``,
    ``ASSEMBLY_INCONSISTENCY``. WP8 raises it rather than return an invalid/forged DetectionResult; it never
    wraps or erases an established upstream ``BundleLoadError``/``AggregationError``/``ExplanationError``/
    ``EvaluatorError`` (those propagate)."""

    def __init__(self, message: str, *, code: str = "ASSEMBLY_INCONSISTENCY") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


# ================================================================ promoted semantic invariants (moved here)
#
# Cross-field invariants not expressible in JSON Schema (DET-001 / ADR-0006). Moved VERBATIM from
# validate_runtime_contracts.py so runtime assembly and the CLI contract validator share ONE definition; the
# only change is sourcing RISK_MATRIX from aggregation and the action vocabulary from the promoted
# _ACTION_ORDER (no second divergent policy copy). Operates on a FULL detection-result dict.

_ACTION_VOCAB = frozenset(_ACTION_ORDER)
_PROBABILITY_KEY = re.compile(r"probab|likelihood|percent", re.I)


def matched_rule_ids(result: Mapping[str, Any]) -> list[str]:
    return sorted(r["rule_id"] for r in result.get("rule_results", [])
                  if r.get("evaluation_state") == "MATCHED" and "rule_id" in r)


def probability_keys(obj: Any, path: str = "") -> list[str]:
    """Recursively find any key that looks like a probability/score (defence in depth)."""
    hits: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if _PROBABILITY_KEY.search(k) or k.lower() == "score":
                hits.append(f"{path}/{k}")
            hits += probability_keys(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits += probability_keys(v, f"{path}/{i}")
    return hits


def semantic_violations(r: Mapping[str, Any]) -> list[str]:
    """Cross-field invariants not expressible in JSON Schema (DET-001 / ADR-0006)."""
    v: list[str] = []
    support = r.get("input_support_status")
    cls = r.get("classification")
    sev = r.get("decision_severity")
    strength = r.get("matched_evidence_strength")
    risk = r.get("risk_level")
    conf = r.get("detection_confidence")
    matched = set(r.get("matched_rules", []))
    fired = set(matched_rule_ids(r))

    # matched_rules must equal the MATCHED rule_results
    if matched != fired:
        v.append(f"matched_rules {sorted(matched)} != MATCHED rule_results {sorted(fired)}")

    # risk matrix
    expected_risk = RISK_MATRIX.get(sev, {}).get(strength)
    if expected_risk is None:
        v.append(f"illegal (severity={sev}, strength={strength}) for the risk matrix")
    elif risk != expected_risk:
        v.append(f"risk_level {risk} != RISK_MATRIX[{sev}][{strength}] = {expected_risk}")

    # support/classification consistency; ERROR/UNSUPPORTED must not appear safe
    if support == "UNSUPPORTED" and cls != "UNSUPPORTED":
        v.append("UNSUPPORTED input must have classification UNSUPPORTED (unknown is not safe)")
    if support == "ERROR" and cls != "ERROR":
        v.append("ERROR input must have classification ERROR (a failure must not appear safe)")
    if support == "INSUFFICIENT_INFORMATION" and cls != "INSUFFICIENT_EVIDENCE":
        v.append("INSUFFICIENT_INFORMATION input must classify as INSUFFICIENT_EVIDENCE")

    # fired vs classification/severity/confidence
    if fired:
        if cls not in ("SCAM_PATTERN_DETECTED", "SCAM_PATTERN_SUSPECTED"):
            v.append(f"fired rules present but classification is {cls}")
        if conf == "LOW" and cls != "SCAM_PATTERN_SUSPECTED":
            v.append("LOW detection_confidence with a fired rule must be SCAM_PATTERN_SUSPECTED")
        if conf in ("MEDIUM", "HIGH") and cls != "SCAM_PATTERN_DETECTED":
            v.append(f"{conf} detection_confidence with a fired rule must be SCAM_PATTERN_DETECTED")
        if sev == "NONE":
            v.append("fired rules present but decision_severity is NONE")
    else:
        if cls in ("SCAM_PATTERN_DETECTED", "SCAM_PATTERN_SUSPECTED"):
            v.append(f"no fired rules but classification is {cls}")
        if sev != "NONE" or risk != "NONE" or conf != "NOT_APPLICABLE":
            v.append("no fired rules must yield severity/risk NONE and confidence NOT_APPLICABLE")

    # recommended action vocabulary
    for a in r.get("recommended_actions", []):
        if a.get("action_code") not in _ACTION_VOCAB:
            v.append(f"recommended action {a.get('action_code')} not in the controlled vocabulary")

    # a result_contract_version=1.1.0 result is action-policy-dependent even when recommended_actions == []
    # (WP6 consults the governed policy to conclude that NO action applies), so the governed action_policy
    # version MUST be pinned in provenance and be a valid semver.
    if r.get("result_contract_version") == "1.1.0":
        ap = ((r.get("provenance") or {}).get("component_versions") or {}).get("action_policy")
        if ap is None:
            v.append("result_contract_version 1.1.0 without a provenance.component_versions.action_policy pin")
        elif not re.match(r"^\d+\.\d+\.\d+$", str(ap)):
            v.append(f"malformed provenance.component_versions.action_policy pin {ap!r}")
    return v


# ================================================================ component-version translation (define ONCE)
#
# The manifest component_versions (bundle-manifest.schema.json) and the result contract component_versions
# (detection-result.schema.json, additionalProperties:false) use different key sets. This is the single
# authoritative translation from loaded RuntimeKnowledge to the result contract.

_COMPONENT_KEY_MAP: dict[str, str] = {
    "rule_schema": "rule_schema",
    "indicator_registry": "indicator_registry",
    "indicator_families": "indicator_families",
    "negative_library": "negative_library",
    "taxonomy": "taxonomy",
    "dimensions": "dimensions",
    "extraction_schemas": "extraction_contracts",   # renamed
    "action_policy": "action_policy",               # present only for a WP6 (1.1.0) bundle
}
# manifest keys deliberately NOT in the result contract (the full bundle digest still pins them).
_DROPPED_COMPONENT_KEYS = frozenset({"evidence_manifest", "evidence_records"})
_REQUIRED_SOURCE_KEYS = tuple(k for k in _COMPONENT_KEY_MAP if k != "action_policy")


def _translate_component_versions(bundle_cv: Mapping[str, str]) -> dict[str, str]:
    """Translate a loaded bundle's component_versions to the result-contract shape. Fail closed if a required
    source key is absent (provenance would be incomplete)."""
    out: dict[str, str] = {}
    for src in _REQUIRED_SOURCE_KEYS:
        if src not in bundle_cv:
            raise DetectionResultError(
                f"provenance incomplete: bundle component_versions is missing required key {src!r}",
                code="PROVENANCE_MISMATCH")
        out[_COMPONENT_KEY_MAP[src]] = bundle_cv[src]
    if bundle_cv.get("action_policy"):   # co-present with the WP6 action policy (loader guarantees it)
        out["action_policy"] = bundle_cv["action_policy"]
    return out


def _production_profile_ids() -> dict[str, str]:
    """The evaluation_profile ids of the pinned production DEFAULT_PROFILE (WP8 accepts no caller profile)."""
    p = DEFAULT_PROFILE
    return {"profile_id": p.profile_id, "extraction_confidence_gate": p.extraction_confidence_gate,
            "risk_matrix_id": p.risk_matrix_id, "confidence_policy_id": p.confidence_policy_id}


# ================================================================ immutable final result


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return value


@dataclass(frozen=True)
class DetectionResult:
    """The immutable, promoted final envelope for ONE evaluation (detection-result.schema.json, 1.1.0). The
    canonical mapping is deeply read-only (``runtime_knowledge.freeze`` style); ``as_dict()`` returns a deep
    mutable COPY suitable for JSON serialization. It is NOT a persistence/HTTP/DB object."""

    _result: Mapping[str, Any]

    def as_dict(self) -> dict:
        return _thaw(self._result)

    @property
    def classification(self) -> str:
        return self._result["classification"]

    @property
    def input_support_status(self) -> str:
        return self._result["input_support_status"]

    @property
    def evaluation_id(self) -> str:
        return self._result["evaluation_id"]

    @property
    def provenance(self) -> Mapping[str, Any]:
        return self._result["provenance"]


# ================================================================ schema validator (cached)


@lru_cache(maxsize=1)
def _detection_validator() -> Draft202012Validator:
    det = json.loads(_DETECTION_SCHEMA_PATH.read_text(encoding="utf-8"))
    rev = json.loads(_RULE_EVAL_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(det)
    registry = Registry().with_resources([
        (det["$id"], Resource.from_contents(det)),
        (rev["$id"], Resource.from_contents(rev)),
    ])
    return Draft202012Validator(det, registry=registry)


# ================================================================ provenance + assembly


def _build_provenance(rk, decision: DecisionResult, explanation_result: ExplanationResult) -> dict:
    component_versions = _translate_component_versions(rk.component_versions)
    ap_bundle = rk.action_policy_version
    ap_expl = explanation_result.action_policy_version
    ap_comp = component_versions.get("action_policy")
    if ap_comp is None or not (ap_bundle == ap_expl == ap_comp):
        raise DetectionResultError(
            f"action-policy pin disagreement: bundle={ap_bundle!r}, explanation={ap_expl!r}, "
            f"provenance={ap_comp!r}", code="ACTION_POLICY_MISMATCH")
    return {
        "bundle_version": rk.bundle_version,
        "bundle_content_digest": rk.content_digest,
        "commit_sha": rk.commit_sha,
        "engine_version": ENGINE_VERSION,
        "evaluation_profile": dict(decision.evaluation_profile),
        "component_versions": component_versions,
    }


def _assemble_result_dict(*, rk, decision: DecisionResult, explanation_result: ExplanationResult,
                          evaluation_id: str, evaluation_timestamp: str, input_id: str,
                          language: Iterable[str], script: Iterable[str]) -> dict:
    result: dict[str, Any] = dict(decision.as_decision_dict())   # axes + rollups + rule_results + degraded
    result["result_contract_version"] = RESULT_CONTRACT_VERSION
    result["evaluation_id"] = evaluation_id
    result["evaluation_timestamp"] = evaluation_timestamp
    result["input_id"] = input_id
    result["language"] = list(language)
    result["script"] = list(script)
    result["provenance"] = _build_provenance(rk, decision, explanation_result)
    result["explanation"] = dict(explanation_result.explanation)
    result["recommended_actions"] = [dict(a) for a in explanation_result.recommended_actions]
    limitations = explanation_result.explanation.get("limitations")
    if limitations:                                   # canonical envelope completeness: exact WP6 value
        result["limitations"] = list(limitations)
    return result


def _reconcile(result: Mapping[str, Any], rk, decision: DecisionResult,
               explanation_result: ExplanationResult) -> None:
    """Assembler-specific reconciliation (beyond generic semantic_violations): prove the emitted envelope is a
    faithful, unforged projection of the ACTUAL loaded RuntimeKnowledge + WP5 DecisionResult + WP6
    ExplanationResult. Fails closed."""
    dd = decision.as_decision_dict()
    for axis in ("input_support_status", "classification", "decision_severity", "matched_evidence_strength",
                 "risk_level", "detection_confidence"):
        if result.get(axis) != getattr(decision, axis):
            raise DetectionResultError(f"{axis} does not match DecisionResult", code="ASSEMBLY_INCONSISTENCY")
    if [dict(r) for r in result.get("rule_results", ())] != [dict(r) for r in decision.rule_results]:
        raise DetectionResultError("rule_results is not the exact DecisionResult.rule_results",
                                   code="ASSEMBLY_INCONSISTENCY")
    for key in ("matched_rules", "matched_positive_indicators", "matched_negative_indicators",
                "suppressed_indicators", "active_overrides", "corroboration_summary", "degraded",
                "ambiguities", "unknowns", "errors"):
        if result.get(key) != dd.get(key):
            raise DetectionResultError(f"rollup {key} does not match DecisionResult", code="ASSEMBLY_INCONSISTENCY")
    if result.get("explanation") != dict(explanation_result.explanation):
        raise DetectionResultError("explanation is not the exact ExplanationResult", code="ASSEMBLY_INCONSISTENCY")
    if result.get("recommended_actions") != [dict(a) for a in explanation_result.recommended_actions]:
        raise DetectionResultError("recommended_actions are not the exact ExplanationResult actions",
                                   code="ASSEMBLY_INCONSISTENCY")
    limitations = explanation_result.explanation.get("limitations")
    if limitations and result.get("limitations") != list(limitations):
        raise DetectionResultError("limitations must be the exact WP6 explanation.limitations",
                                   code="ASSEMBLY_INCONSISTENCY")

    prov = result.get("provenance") or {}
    if prov.get("bundle_version") != rk.bundle_version or prov.get("bundle_content_digest") != rk.content_digest \
            or prov.get("commit_sha") != rk.commit_sha:
        raise DetectionResultError("bundle provenance does not match the loaded RuntimeKnowledge",
                                   code="PROVENANCE_MISMATCH")
    if prov.get("engine_version") != ENGINE_VERSION:
        raise DetectionResultError("engine_version does not match the runtime ENGINE_VERSION",
                                   code="PROVENANCE_MISMATCH")
    if prov.get("component_versions") != _translate_component_versions(rk.component_versions):
        raise DetectionResultError("component_versions do not match the translated bundle provenance",
                                   code="PROVENANCE_MISMATCH")
    prof = prov.get("evaluation_profile")
    if prof != dict(decision.evaluation_profile) or prof != _production_profile_ids():
        raise DetectionResultError("evaluation_profile does not match the production DEFAULT_PROFILE / DecisionResult",
                                   code="PROFILE_MISMATCH")
    # M1: the emitted policy ids must describe the ACTUAL executed WP5 policy authority (aggregation constants),
    # not merely agree with each other — otherwise a mislabelled DEFAULT_PROFILE could claim a policy that did
    # not execute. Reconcile the production profile AND the DecisionResult profile against the real authority.
    dprof = dict(decision.evaluation_profile)
    if (DEFAULT_PROFILE.risk_matrix_id != RISK_MATRIX_ID
            or DEFAULT_PROFILE.confidence_policy_id != CONFIDENCE_POLICY_ID
            or prof.get("risk_matrix_id") != RISK_MATRIX_ID
            or prof.get("confidence_policy_id") != CONFIDENCE_POLICY_ID
            or dprof.get("risk_matrix_id") != RISK_MATRIX_ID
            or dprof.get("confidence_policy_id") != CONFIDENCE_POLICY_ID):
        raise DetectionResultError(
            "evaluation_profile policy ids do not match the executed WP5 authority "
            f"(risk_matrix_id must be {RISK_MATRIX_ID!r}, confidence_policy_id must be {CONFIDENCE_POLICY_ID!r})",
            code="PROFILE_MISMATCH")
    ap = (prov.get("component_versions") or {}).get("action_policy")
    if not (ap == rk.action_policy_version == explanation_result.action_policy_version):
        raise DetectionResultError("action-policy pin does not reconcile across bundle/explanation/provenance",
                                   code="ACTION_POLICY_MISMATCH")


def assemble_detection_result(
    *, rk, decision: DecisionResult, explanation_result: ExplanationResult,
    evaluation_id: str, evaluation_timestamp: str, input_id: str,
    language: Iterable[str], script: Iterable[str],
) -> DetectionResult:
    """Assemble + fully validate + reconcile ONE immutable ``DetectionResult`` from an authoritative WP5
    ``DecisionResult`` and WP6 ``ExplanationResult`` plus trusted envelope context. The reusable seam the
    public API (and white-box tests) call; it never runs rules itself."""
    _validate_identity(evaluation_id, evaluation_timestamp, input_id)
    _validate_seq("language", language)
    _validate_seq("script", script)
    result = _assemble_result_dict(
        rk=rk, decision=decision, explanation_result=explanation_result,
        evaluation_id=evaluation_id, evaluation_timestamp=evaluation_timestamp, input_id=input_id,
        language=language, script=script)
    return _validate_and_freeze(result, rk, decision, explanation_result)


def _validate_and_freeze(result: Mapping[str, Any], rk, decision, explanation_result) -> DetectionResult:
    # 1. JSON Schema (with rule-evaluation-result $ref resolved)
    errs = sorted(_detection_validator().iter_errors(result), key=lambda e: list(e.path))
    if errs:
        e = errs[0]
        raise DetectionResultError(
            f"assembled result fails detection-result.schema.json: {e.message} at /{'/'.join(map(str, e.path))}",
            code="RESULT_SCHEMA_INVALID")
    # 2. promoted cross-field semantic invariants + probability-key defence in depth
    problems = semantic_violations(result)
    problems += [f"probability-like field at {hit}" for hit in probability_keys(result)]
    if problems:
        raise DetectionResultError(f"assembled result fails semantic validation: {problems[0]}",
                                   code="RESULT_SEMANTIC_INVALID")
    # 3. assembler-specific reconciliation against the authoritative sources
    _reconcile(result, rk, decision, explanation_result)
    return DetectionResult(freeze(result))


# ================================================================ input-context validation


def _validate_identity(evaluation_id: Any, evaluation_timestamp: Any, input_id: Any) -> None:
    for name, value in (("evaluation_id", evaluation_id), ("input_id", input_id)):
        if not isinstance(value, str) or not value:
            raise DetectionResultError(f"{name} must be a non-empty string", code="INVALID_IDENTITY")
    if not _is_real_iso8601_instant(evaluation_timestamp):
        raise DetectionResultError(
            "evaluation_timestamp must be a real, timezone-aware ISO-8601 calendar instant (offset or Z), "
            f"got {evaluation_timestamp!r}", code="INVALID_IDENTITY")


def _validate_seq(name: str, value: Any) -> None:
    if not isinstance(value, (list, tuple)) or not value or not all(isinstance(v, str) and v for v in value):
        raise DetectionResultError(f"{name} must be a non-empty sequence of non-empty strings",
                                   code="INVALID_INPUT_CONTEXT")


def _single_scalar(language: Iterable[str], script: Iterable[str]) -> tuple[str, str]:
    """One effective language/script scalar for the evaluable runtime. A multi-valued evaluable context cannot
    be represented by the current runtime and fails closed (never silently pick the first element)."""
    lang, scr = list(language), list(script)
    if len(lang) != 1 or len(scr) != 1:
        raise DetectionResultError(
            "an evaluable input requires exactly one language and one script; the current runtime cannot "
            f"represent a multi-valued evaluable context (language={lang!r}, script={scr!r})",
            code="INVALID_INPUT_CONTEXT")
    return lang[0], scr[0]


# ================================================================ public production API


def evaluate_detection_from_governed(
    rk,
    indicator_observations: Iterable[Mapping[str, Any]],
    observations: Iterable[Mapping[str, Any]],
    *,
    evaluation_id: str,
    evaluation_timestamp: str,
    input_id: str,
    language: Iterable[str],
    script: Iterable[str],
    input_support_status: str,
    whole_evaluation_errors: Iterable[Mapping[str, Any]] = (),
) -> DetectionResult:
    """Production convenience: assemble ONE immutable, schema+semantically-valid ``DetectionResult`` from
    governed observation DATA and trusted envelope context.

    Trust model: ``evaluation_id``/``evaluation_timestamp``/``input_id``/``language``/``script``/
    ``input_support_status`` are trusted governed metadata; ``whole_evaluation_errors`` are TRUSTED integration
    diagnostics (never end-user input). The engine version and evaluation profile are runtime-pinned
    (``ENGINE_VERSION`` / ``DEFAULT_PROFILE``) and cannot be supplied by the caller, nor can any
    decision/rollup/explanation/action/provenance field. ``rk`` MUST be an already-loaded bundle — a bundle
    that failed to load never reaches here (no fabricated provenance).

    Support-first (DET-001 §3): only SUPPORTED/PARTIALLY_SUPPORTED execute rules; every other support state
    (and any trusted whole-evaluation error) routes through WP5 over an EMPTY rule set — rules never run.
    """
    _validate_identity(evaluation_id, evaluation_timestamp, input_id)
    _validate_seq("language", language)
    _validate_seq("script", script)
    if input_support_status not in _SUPPORT_VALUES:
        raise DetectionResultError(f"unknown input_support_status {input_support_status!r}",
                                   code="INVALID_INPUT_CONTEXT")

    whole_errors = tuple(whole_evaluation_errors)
    # H1: a WHOLE_EVALUATION diagnostic accompanies input_support_status=ERROR (promoted contract). A trusted
    # whole-evaluation refusal on a non-ERROR governed support state is an INCONSISTENT context — reject it,
    # never silently normalise the authoritative support state to ERROR.
    if whole_errors and input_support_status != "ERROR":
        raise DetectionResultError(
            "whole_evaluation_errors (a trusted WHOLE_EVALUATION diagnostic) require input_support_status=ERROR; "
            f"got {input_support_status!r}", code="INVALID_INPUT_CONTEXT")
    if whole_errors:
        # A trusted whole-evaluation refusal (support already proven ERROR): WP5 classifies ERROR over an empty
        # rule set; rules never run.
        decision = aggregate_decision([], input_support_status="ERROR", rk=rk,
                                      profile=DEFAULT_PROFILE, whole_evaluation_errors=whole_errors)
        expl_observations: Iterable[Mapping[str, Any]] | None = None
    elif input_support_status in _EVALUABLE_SUPPORT:
        lang_scalar, script_scalar = _single_scalar(language, script)
        decision = evaluate_decision_from_governed(
            rk, indicator_observations, observations, input_support_status=input_support_status,
            profile=DEFAULT_PROFILE, language=lang_scalar, script=script_scalar)
        expl_observations = observations
    else:
        # UNSUPPORTED / INSUFFICIENT_INFORMATION / ERROR: no rule execution (DET-001 §3 support-first gate).
        decision = aggregate_decision([], input_support_status=input_support_status, rk=rk,
                                      profile=DEFAULT_PROFILE)
        expl_observations = None

    explanation_result = build_explanation(decision, rk=rk, observations=expl_observations)

    return assemble_detection_result(
        rk=rk, decision=decision, explanation_result=explanation_result,
        evaluation_id=evaluation_id, evaluation_timestamp=evaluation_timestamp, input_id=input_id,
        language=language, script=script)
