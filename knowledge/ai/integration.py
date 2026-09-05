"""P4-WP5 optional offline extraction integration with the unchanged Phase-3 API.

AI cannot directly set, override, or bypass decision semantics. Validated AI
observations augment host observations; Phase 3 alone evaluates the result.
Import this module explicitly: importing knowledge.ai alone stays extraction-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from knowledge import runtime

from .governance import (
    AIConfiguration, AIExtractionResult, AIGovernanceError, PreparedAIExtraction,
    _freeze, _json_copy, canonical_digest, canonical_json,
    prepare_ai_extraction, prepare_ai_request,
)
from .provider import AIExtractorProvider, AIProviderError, RawAIExtractionResponse
from .replay import AIReplaySnapshot, pin_replay_snapshot
from .validation import AIExtractionValidationError, validate_ai_extraction


class AIFallbackReason(str, Enum):
    DISABLED = "AI_DISABLED"
    HOST_NOT_EVALUABLE = "AI_HOST_NOT_EVALUABLE"
    PROVIDER_FAILED = "AI_PROVIDER_FAILED"
    RESPONSE_REJECTED = "AI_RESPONSE_REJECTED"
    GOVERNANCE_FAILED = "AI_GOVERNANCE_FAILED"
    MAPPING_FAILED = "AI_MAPPING_FAILED"


@dataclass(frozen=True)
class AIIntegrationPolicy:
    extraction_enabled: bool = False

    def __post_init__(self) -> None:
        if type(self.extraction_enabled) is not bool:
            raise TypeError("extraction_enabled must be a boolean")


class AIIntegrationInputError(ValueError):
    """Host snapshot integrity failure; never converted to optional AI fallback."""

    def __init__(self) -> None:
        super().__init__("Host integration input is not bounded canonical JSON material.")


class AIMappingError(ValueError):
    """Atomic optional mapping failure with fixed, value-free diagnostic."""

    def __init__(self) -> None:
        super().__init__("AI proposals cannot form a compatible governed contribution.")


@dataclass(frozen=True, slots=True, init=False)
class AIIntegrationOutcome:
    """Sealed integration metadata; the runtime result is the sole decision object.

    All identities/digests come from actual consumed material. No public constructor
    accepts an independently claimed digest or a replacement decision field.
    """

    detection_result: runtime.DetectionResult = field(init=False)
    ai_attempted: bool = field(init=False)
    fallback_reason: AIFallbackReason | None = field(init=False)
    governed_artifact: Mapping[str, Any] = field(init=False)
    replay_snapshot: AIReplaySnapshot | None = field(init=False)

    def __new__(cls, *args, **kwargs):
        raise TypeError("AIIntegrationOutcome is created by evaluate_with_optional_ai")

    @property
    def ai_used(self) -> bool:
        return self.replay_snapshot is not None

    @property
    def ai_extraction_result(self) -> AIExtractionResult | None:
        return self.replay_snapshot.extraction_result if self.replay_snapshot is not None else None

    @property
    def governed_artifact_digest(self) -> str:
        return canonical_digest(self.governed_artifact)

    def as_dict(self) -> dict:
        return {
            "detection_result": self.detection_result.as_dict(), "ai_attempted": self.ai_attempted,
            "ai_used": self.ai_used,
            "fallback_reason": self.fallback_reason.value if self.fallback_reason is not None else None,
            "governed_artifact": _json_copy(self.governed_artifact),
            "governed_artifact_digest": self.governed_artifact_digest,
            "ai_extraction_result": self.ai_extraction_result.as_dict() if self.ai_used else None,
            "replay_snapshot": self.replay_snapshot.as_dict() if self.ai_used else None,
        }


def _map_ai(prepared: PreparedAIExtraction, *, run_id: str, baseline: Mapping[str, Any]) -> dict:
    """Map once, retaining every proposal and remapping all supporting references.

    Schema/reference validation uses Phase 3's existing public governed context
    validator on the AI contribution only. It does not evaluate rules. Host/runtime
    errors from the final evaluation are outside the optional-path catch boundary.
    """
    refs = {}
    observations = []
    indicators = []
    try:
        for proposal, capped in zip(prepared.extraction.observations, prepared.observations, strict=True):
            oid = "AI-OBS-" + canonical_digest({"run_id": run_id, "proposal_id": proposal["proposal_id"]})
            refs[proposal["proposal_id"]] = oid
            obs = {key: proposal[key] for key in (
                "observation_type", "source_input_id", "status", "polarity", "attribution", "mood",
            )}
            obs.update(observation_id=oid, offsets={"start": proposal["start"], "end": proposal["end"]},
                       confidence={"level": capped.level}, provenance=prepared.provenance.as_dict())
            if "canonical_value" in proposal:
                obs["canonical_value"] = proposal["canonical_value"]
            observations.append(obs)
        for proposal, capped in zip(prepared.extraction.indicators, prepared.indicators, strict=True):
            ind = {key: proposal[key] for key in ("indicator_id", "polarity", "matched", "input_id")}
            ind.update(observation_refs=[refs[ref] for ref in proposal.get("observation_refs", ())],
                       confidence={"level": capped.level}, extraction_method="LLM",
                       review_required=capped.review_required, provenance=prepared.provenance.as_dict())
            indicators.append(ind)
        # Collision is an atomic mapping refusal, never overwrite or silent deduplication.
        host_ids = {obs.get("observation_id") for obs in baseline["observations"]}
        if host_ids.intersection(refs.values()):
            raise AIMappingError()
        # Phase 3 allows host-only evidence contexts with their own source identity.
        # Such a context cannot be combined with a different current AI input.
        if observations or indicators:
            input_id = prepared.extraction.input_id
            if any(o.get("source_input_id") != input_id for o in baseline["observations"]) or any(
                i.get("input_id") != input_id for i in baseline["indicator_observations"]
            ):
                raise AIMappingError()
        runtime.build_validated_context(indicators, observations)
    except (KeyError, TypeError, ValueError, AttributeError):
        raise AIMappingError() from None
    return {"observations": observations, "indicator_observations": indicators}


def evaluate_with_optional_ai(
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
    policy: AIIntegrationPolicy = AIIntegrationPolicy(),
    provider: AIExtractorProvider | None = None,
    config: AIConfiguration | None = None,
    normalized_content: str | None = None,
    request_id: str | None = None,
    run_id: str | None = None,
) -> AIIntegrationOutcome:
    """Evaluate one host input with optional AI; default is the deterministic path.

    Host data is captured once before any optional call. Only typed provider,
    WP3, WP4 and mapping failures discard AI. Unexpected programming exceptions
    and the authoritative Phase-3 call are never swallowed as successful fallback.
    Successful empty extraction counts as an accepted AI run with zero added data.
    No identifiers, timestamps, support state or language are generated here.
    """
    if type(policy) is not AIIntegrationPolicy:
        raise TypeError("policy must be AIIntegrationPolicy")
    try:
        host = _json_copy({
            "observations": list(observations), "indicator_observations": list(indicator_observations),
            "evaluation_context": {
                "evaluation_id": evaluation_id, "evaluation_timestamp": evaluation_timestamp,
                "input_id": input_id, "language": language, "script": script,
                "input_support_status": input_support_status,
                "whole_evaluation_errors": list(whole_evaluation_errors),
            },
        })
        canonical_json(host)
        baseline = _freeze(host)
    except (AIGovernanceError, TypeError, ValueError):
        raise AIIntegrationInputError() from None

    artifact = baseline
    replay = None
    attempted = False
    reason = None
    context = baseline["evaluation_context"]
    if not policy.extraction_enabled:
        reason = AIFallbackReason.DISABLED
    elif (context["input_support_status"] not in ("SUPPORTED", "PARTIALLY_SUPPORTED")
          or context["whole_evaluation_errors"] or context["language"] != ("en",)
          or context["script"] != ("Latn",)):
        reason = AIFallbackReason.HOST_NOT_EVALUABLE
    else:
        attempted = True
        try:
            request = prepare_ai_request(config, request_id=request_id, input_id=context["input_id"],
                                         normalized_content=normalized_content)
            if provider is None:
                reason = AIFallbackReason.PROVIDER_FAILED
            else:
                raw = provider.extract(request.request)
                if type(raw) is not RawAIExtractionResponse:
                    reason = AIFallbackReason.RESPONSE_REJECTED
                else:
                    validated = validate_ai_extraction(
                        raw, expected_request_id=request.request.request_id,
                        expected_input_id=context["input_id"],
                        normalized_inputs={context["input_id"]: request.request.normalized_content}, rk=rk,
                    )
                    prepared, audit = prepare_ai_extraction(
                        validated, prepared_request=request, run_id=run_id,
                        evaluation_id=context["evaluation_id"],
                    )
                    contribution = _map_ai(prepared, run_id=audit.run_id, baseline=baseline)
                    combined = _freeze({
                        "observations": list(baseline["observations"]) + contribution["observations"],
                        "indicator_observations": list(baseline["indicator_observations"]) + contribution["indicator_observations"],
                        "evaluation_context": baseline["evaluation_context"],
                    })
                    replay = pin_replay_snapshot(
                        audit, governed_artifact=combined, content_digest=rk.content_digest,
                        engine_version=runtime.ENGINE_VERSION, profile=runtime.DEFAULT_PROFILE.profile_id,
                    )
                    artifact = replay.governed_artifact
        except AIProviderError:
            reason = AIFallbackReason.PROVIDER_FAILED
        except AIExtractionValidationError:
            reason = AIFallbackReason.RESPONSE_REJECTED
        except AIGovernanceError:
            reason = AIFallbackReason.GOVERNANCE_FAILED
        except AIMappingError:
            reason = AIFallbackReason.MAPPING_FAILED

    # Single authoritative evaluation, always outside all optional AI error handling.
    consumed = _json_copy(artifact)
    detection = runtime.evaluate_detection_from_governed(
        rk, consumed["indicator_observations"], consumed["observations"], **consumed["evaluation_context"],
    )
    outcome = object.__new__(AIIntegrationOutcome)
    for name, value in (("detection_result", detection), ("ai_attempted", attempted),
                        ("fallback_reason", reason), ("governed_artifact", artifact), ("replay_snapshot", replay)):
        object.__setattr__(outcome, name, value)
    return outcome
