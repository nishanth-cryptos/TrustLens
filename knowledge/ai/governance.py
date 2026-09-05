"""P4-WP4 offline containment, configuration pinning and extraction confidence.

Only the host constructs configuration. Submitted text remains request data; this
module never interprets it as configuration. WP3 validation is a prerequisite to
preparation, not a claim of semantic truth. WP5 owns governed mapping.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field, fields
from types import MappingProxyType
from typing import Any, Mapping

from .provider import AIExtractionRequest
from .validation import AI_EXTRACTION_VERSION, ValidatedAIExtraction

PROMPT_TEMPLATE_ID = "ai-extraction-data-only"
PROMPT_TEMPLATE_VERSION = "1.0.0"
RESPONSE_SCHEMA_ID = "ai-extraction"
AI_ADAPTER_ID = "ai-extraction-adapter"
AI_ADAPTER_VERSION = "1.0.0"
CONFIDENCE_POLICY_VERSION = "1.0.0"
MAX_CANONICAL_BYTES = 4_194_304
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}")
_DIGEST = re.compile(r"[0-9a-f]{64}")


class AIGovernanceError(Exception):
    """Fixed, value-free diagnostics; callers supply neither codes nor details."""

    _CODE = "AI_PROVENANCE_INVALID"
    _DETAIL = "AI provenance material is invalid."

    def __init__(self) -> None:
        super().__init__(f"[{self.code}] {self.detail}")

    @property
    def code(self) -> str:
        return type(self)._CODE

    @property
    def detail(self) -> str:
        return type(self)._DETAIL


class AIPromptPolicyViolationError(AIGovernanceError):
    _CODE = "AI_PROMPT_POLICY_VIOLATION"
    _DETAIL = "Host-controlled extraction configuration or request binding is invalid."


class AIProvenanceInvalidError(AIGovernanceError):
    pass


class AIReplayIntegrityError(AIGovernanceError):
    _CODE = "AI_REPLAY_INTEGRITY_FAILED"
    _DETAIL = "Replay material does not match its pinned integrity identity."


def _identifier(value: Any, error=AIProvenanceInvalidError) -> None:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise error()


def _digest(value: Any) -> None:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise AIProvenanceInvalidError()


def _json_copy(value: Any, depth: int = 0, budget: list[int] | None = None) -> Any:
    """Copy only JSON values (plus frozen array/map equivalents), with finite bounds.

    No string coercion of keys, custom encoders, or opaque objects. Cycles fail at
    the depth limit. Strict UTF-8 checks precede JSON's ASCII escaping.
    """
    if budget is None:
        budget = [100_000]
    budget[0] -= 1
    if depth > 32 or budget[0] < 0:
        raise AIProvenanceInvalidError()
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) is str:
        try:
            if len(value.encode("utf-8")) > MAX_CANONICAL_BYTES:
                raise AIProvenanceInvalidError()
        except UnicodeError:
            raise AIProvenanceInvalidError() from None
        return value
    if type(value) in (dict, MappingProxyType):
        if any(type(k) is not str for k in value):
            raise AIProvenanceInvalidError()
        return {_json_copy(k, depth + 1, budget): _json_copy(v, depth + 1, budget)
                for k, v in value.items()}
    if type(value) in (list, tuple):
        return [_json_copy(v, depth + 1, budget) for v in value]
    raise AIProvenanceInvalidError()


def canonical_json(value: Any) -> str:
    """Sorted keys, compact separators, ASCII escaping, strict JSON, UTF-8 bytes.

    Matches the repository's JSON key/separator convention; digests use its
    lowercase SHA-256 convention. Array order and numeric JSON spelling matter.
    """
    try:
        result = json.dumps(_json_copy(value), sort_keys=True, separators=(",", ":"),
                            ensure_ascii=True, allow_nan=False)
        if len(result.encode("utf-8")) > MAX_CANONICAL_BYTES:
            raise AIProvenanceInvalidError()
        return result
    except (ValueError, TypeError, RecursionError):
        raise AIProvenanceInvalidError() from None


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _freeze(value: Any) -> Any:
    if type(value) is dict:
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if type(value) is list:
        return tuple(_freeze(v) for v in value)
    return value


@dataclass(frozen=True)
class AIConfiguration:
    """Host-only, credential-free configuration; model/provider names are opaque.

    Current prompt/contract/adapter identities are repository-pinned. New versions
    require a governed code/config change. Decoding is a closed numeric vocabulary,
    never a general metadata bag. Nothing here is read from submitted content.
    """

    config_id: str
    provider_adapter_id: str
    provider_adapter_version: str
    model_id: str
    model_version: str
    decoding_parameters: Mapping[str, int | float] = field(default_factory=dict)
    prompt_template_id: str = PROMPT_TEMPLATE_ID
    prompt_template_version: str = PROMPT_TEMPLATE_VERSION
    response_schema_id: str = RESPONSE_SCHEMA_ID
    response_schema_version: str = AI_EXTRACTION_VERSION
    ai_adapter_id: str = AI_ADAPTER_ID
    ai_adapter_version: str = AI_ADAPTER_VERSION

    def __post_init__(self) -> None:
        for name in ("config_id", "provider_adapter_id", "provider_adapter_version", "model_id", "model_version"):
            _identifier(getattr(self, name))
        for name, expected in (
            ("prompt_template_id", PROMPT_TEMPLATE_ID), ("prompt_template_version", PROMPT_TEMPLATE_VERSION),
            ("response_schema_id", RESPONSE_SCHEMA_ID), ("response_schema_version", AI_EXTRACTION_VERSION),
            ("ai_adapter_id", AI_ADAPTER_ID), ("ai_adapter_version", AI_ADAPTER_VERSION),
        ):
            if type(getattr(self, name)) is not str or getattr(self, name) != expected:
                raise AIPromptPolicyViolationError()
        params = _json_copy(self.decoding_parameters)
        if type(params) is not dict:
            raise AIProvenanceInvalidError()
        if set(params) - {"temperature", "top_p", "max_output_tokens", "seed"}:
            raise AIPromptPolicyViolationError()
        for key, value in params.items():
            if type(value) not in (int, float):
                raise AIProvenanceInvalidError()
            if key == "temperature" and not 0 <= value <= 2:
                raise AIProvenanceInvalidError()
            if key == "top_p" and not 0 <= value <= 1:
                raise AIProvenanceInvalidError()
            if key in ("max_output_tokens", "seed") and (
                type(value) is not int or not (1 if key == "max_output_tokens" else 0) <= value <= 2**31 - 1
            ):
                raise AIProvenanceInvalidError()
        object.__setattr__(self, "decoding_parameters", _freeze(params))

    def as_dict(self) -> dict:
        return {f.name: _json_copy(getattr(self, f.name)) for f in fields(self)}

    @property
    def config_ref(self) -> str:
        return "ai-config:sha256:" + canonical_digest(self.as_dict())


@dataclass(frozen=True)
class PreparedAIRequest:
    """Pinned host configuration beside a WP2 content-only request; no capabilities."""

    config: AIConfiguration
    request: AIExtractionRequest

    def __post_init__(self) -> None:
        if type(self.config) is not AIConfiguration or type(self.request) is not AIExtractionRequest:
            raise AIPromptPolicyViolationError()
        _identifier(self.request.request_id, AIPromptPolicyViolationError)
        _identifier(self.request.input_id, AIPromptPolicyViolationError)
        if (self.request.prompt_template_id != self.config.prompt_template_id
                or self.request.response_contract_id != self.config.response_schema_id):
            raise AIPromptPolicyViolationError()


def prepare_ai_request(config: AIConfiguration, *, request_id: str, input_id: str,
                       normalized_content: str) -> PreparedAIRequest:
    if type(config) is not AIConfiguration:
        raise AIPromptPolicyViolationError()
    try:
        request = AIExtractionRequest(request_id, input_id, normalized_content,
                                      config.prompt_template_id, config.response_schema_id)
    except ValueError:
        raise AIPromptPolicyViolationError() from None
    return PreparedAIRequest(config, request)


@dataclass(frozen=True)
class AIProvenanceDescriptor:
    """WP5 may copy this descriptor into existing governed provenance fields."""

    config: AIConfiguration

    def __post_init__(self) -> None:
        if type(self.config) is not AIConfiguration:
            raise AIProvenanceInvalidError()

    @property
    def extractor_type(self) -> str:
        return "LLM"

    @property
    def config_ref(self) -> str:
        return self.config.config_ref

    def as_dict(self) -> dict:
        return {"extractor_id": self.config.ai_adapter_id, "extractor_type": self.extractor_type,
                "extractor_version": self.config.ai_adapter_version, "config_ref": self.config_ref}


@dataclass(frozen=True)
class CappedAIProposal:
    """Collection/index pins identity even when an indicator has no proposal_id.

    The state is copied from a validated proposal. Level/reason are derived
    properties, never constructor arguments or model opinions.
    """

    collection: str
    index: int
    proposal_id: str | None
    state: str

    def __post_init__(self) -> None:
        if type(self.collection) is not str or self.collection not in ("observations", "indicators"):
            raise AIProvenanceInvalidError()
        if type(self.index) is not int or self.index < 0:
            raise AIProvenanceInvalidError()
        if self.proposal_id is not None:
            _identifier(self.proposal_id)
        if self.collection == "observations" and self.proposal_id is None:
            raise AIProvenanceInvalidError()
        if type(self.state) is not str or self.state not in (
            "OBSERVED", "NOT_OBSERVED", "NOT_APPLICABLE", "UNKNOWN", "AMBIGUOUS"
        ):
            raise AIProvenanceInvalidError()

    @property
    def level(self) -> str:
        return "LOW" if self.state in ("UNKNOWN", "AMBIGUOUS") else "MEDIUM"

    @property
    def reason_code(self) -> str:
        if self.state == "UNKNOWN":
            return "GOVERNED_UNKNOWN"
        if self.state == "AMBIGUOUS":
            return "GOVERNED_AMBIGUITY"
        return "COMPLETE_VALIDATED_DETERMINATE"

    @property
    def review_required(self) -> bool:
        return self.level == "LOW"

    def as_dict(self) -> dict:
        return {"collection": self.collection, "index": self.index, "proposal_id": self.proposal_id,
                "state": self.state, "level": self.level, "reason_code": self.reason_code,
                "review_required": self.review_required}


@dataclass(frozen=True)
class PreparedAIExtraction:
    """Owned snapshot of WP3 output with calculated confidence, still proposals.

    The host MUST pass validate_ai_extraction's successful output. Python type
    construction is not a validation certificate; this wrapper does not re-run
    membership or grounding without WP3's authoritative input and knowledge.
    """

    extraction: ValidatedAIExtraction
    provenance: AIProvenanceDescriptor
    observations: tuple[CappedAIProposal, ...] = field(init=False)
    indicators: tuple[CappedAIProposal, ...] = field(init=False)

    def __post_init__(self) -> None:
        if type(self.extraction) is not ValidatedAIExtraction or type(self.provenance) is not AIProvenanceDescriptor:
            raise AIProvenanceInvalidError()
        data = _json_copy(self.extraction.as_dict())
        canonical_json(data)
        _identifier(data["input_id"])
        object.__setattr__(self, "extraction", ValidatedAIExtraction(
            data["input_id"], _freeze(data["observations"]), _freeze(data["indicators"])))
        for collection, state_key in (("observations", "status"), ("indicators", "matched")):
            try:
                capped = tuple(CappedAIProposal(collection, index, item.get("proposal_id"), item[state_key])
                               for index, item in enumerate(data[collection]))
            except (KeyError, AttributeError, TypeError):
                raise AIProvenanceInvalidError() from None
            object.__setattr__(self, collection, capped)

    @property
    def validated_extraction_digest(self) -> str:
        return canonical_digest(self.extraction.as_dict())

    @property
    def confidence_policy_version(self) -> str:
        return CONFIDENCE_POLICY_VERSION

    def as_dict(self) -> dict:
        return {"extraction": self.extraction.as_dict(), "provenance": self.provenance.as_dict(),
                "validated_extraction_digest": self.validated_extraction_digest,
                "confidence_policy_version": self.confidence_policy_version,
                "observations": [p.as_dict() for p in self.observations],
                "indicators": [p.as_dict() for p in self.indicators]}


_AI_RESULT_CONSTRUCTION_GUARD = object()


@dataclass(frozen=True, slots=True, init=False)
class AIExtractionResult:
    """Sealed run-level audit. Provenance digest inputs are not constructor fields.

    The authoritative factory receives and retains an immutable copy of the
    actual validated extraction, from which its digest is always calculated.
    The governed-artifact relationship is not bound in WP4 and remains ``None``.
    The construction guard only seals the supported Python API; provenance comes
    from hashing source material, not from treating the guard as authentication.
    """

    run_id: str = field(init=False)
    evaluation_id: str = field(init=False)
    config: AIConfiguration = field(init=False)
    _validated_extraction: ValidatedAIExtraction = field(init=False, repr=False)
    _construction_guard: object = field(init=False, repr=False, compare=False)

    def __new__(cls, *args, **kwargs):
        raise TypeError("AIExtractionResult is created by prepare_ai_extraction")

    @property
    def validated_extraction_digest(self) -> str:
        return canonical_digest(self._validated_extraction.as_dict())

    @property
    def governed_artifact_digest(self) -> None:
        """WP5-owned binding slot: deliberately and permanently unbound in WP4."""
        return None

    @property
    def confidence_policy_version(self) -> str:
        return CONFIDENCE_POLICY_VERSION

    @property
    def config_ref(self) -> str:
        return self.config.config_ref

    def as_dict(self) -> dict:
        return {"run_id": self.run_id, "evaluation_id": self.evaluation_id,
                "config_ref": self.config_ref, "config": self.config.as_dict(),
                "validated_extraction": self._validated_extraction.as_dict(),
                "validated_extraction_digest": self.validated_extraction_digest,
                "governed_artifact_digest": self.governed_artifact_digest,
                "response_schema_version": self.config.response_schema_version,
                "confidence_policy_version": self.confidence_policy_version}

    @property
    def digest(self) -> str:
        return canonical_digest(self.as_dict())


def _new_ai_extraction_result(*, run_id: str, evaluation_id: str, config: AIConfiguration,
                              validated_extraction: ValidatedAIExtraction) -> AIExtractionResult:
    """Internal construction from actual material; accepts no provenance digest."""
    _identifier(run_id)
    _identifier(evaluation_id)
    if type(config) is not AIConfiguration or type(validated_extraction) is not ValidatedAIExtraction:
        raise AIProvenanceInvalidError()
    data = _json_copy(validated_extraction.as_dict())
    if type(data) is not dict or set(data) != {"input_id", "observations", "indicators"}:
        raise AIProvenanceInvalidError()
    _identifier(data["input_id"])
    if type(data["observations"]) is not list or type(data["indicators"]) is not list:
        raise AIProvenanceInvalidError()
    owned = ValidatedAIExtraction(data["input_id"], _freeze(data["observations"]),
                                  _freeze(data["indicators"]))
    result = object.__new__(AIExtractionResult)
    object.__setattr__(result, "run_id", run_id)
    object.__setattr__(result, "evaluation_id", evaluation_id)
    object.__setattr__(result, "config", config)
    object.__setattr__(result, "_validated_extraction", owned)
    object.__setattr__(result, "_construction_guard", _AI_RESULT_CONSTRUCTION_GUARD)
    return result


def _is_sealed_ai_extraction_result(value: Any) -> bool:
    """Supported-API construction invariant; not a cryptographic authenticity test."""
    if type(value) is not AIExtractionResult:
        return False
    try:
        if value._construction_guard is not _AI_RESULT_CONSTRUCTION_GUARD:
            return False
        _identifier(value.run_id)
        _identifier(value.evaluation_id)
        if type(value.config) is not AIConfiguration or type(value._validated_extraction) is not ValidatedAIExtraction:
            return False
        _digest(value.validated_extraction_digest)
        return value.governed_artifact_digest is None
    except (AIProvenanceInvalidError, AttributeError):
        return False


def prepare_ai_extraction(validated: ValidatedAIExtraction, *, prepared_request: PreparedAIRequest,
                          run_id: str, evaluation_id: str) -> tuple[PreparedAIExtraction, AIExtractionResult]:
    """Bind successful WP3 output to host config/input, calculate caps and audit."""
    if type(prepared_request) is not PreparedAIRequest or type(validated) is not ValidatedAIExtraction:
        raise AIProvenanceInvalidError()
    if validated.input_id != prepared_request.request.input_id:
        raise AIProvenanceInvalidError()
    prepared = PreparedAIExtraction(validated, AIProvenanceDescriptor(prepared_request.config))
    audit = _new_ai_extraction_result(
        run_id=run_id, evaluation_id=evaluation_id, config=prepared_request.config,
        validated_extraction=prepared.extraction,
    )
    return prepared, audit
