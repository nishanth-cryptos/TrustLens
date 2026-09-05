"""TrustLens Phase 4 AI intelligence layer (P4-WP2 through P4-WP4, offline).

This package hosts the AI *extraction* layer authored under AI-001 / ADR-0007. P4-WP2 establishes ONLY the
vendor-neutral, OFFLINE provider seam and a deterministic ``FakeProvider`` — no live provider, no vendor SDK,
no network, no API key, no tools, no standing service. Provider output is UNTRUSTED transport data; it is not
a governed observation and never enters Phase 3 directly. WP3 validates proposals; WP4 pins configuration,
assigns capped confidence and verifies replay material. Governed mapping, Phase-3 integration, feature flags
and deterministic fallback remain WP5 work.

Public surface::

    from knowledge.ai import (
        AIExtractorProvider,          # provider-neutral Protocol (extraction seam)
        AIExtractionRequest,          # bounded, decision-field-free request (content is DATA)
        RawAIExtractionResponse,      # UNTRUSTED, payload-neutral transport output
        AIProviderError,              # base transport failure (stable .code)
        AIProviderUnavailableError,
        AIProviderTimeoutError,
        AIProviderExecutionError,
        FakeProvider,                 # deterministic offline provider for tests/reference
        MAX_CONTENT_CHARS,
    )
"""

from __future__ import annotations

from .fake_provider import FakeProvider
from .provider import (
    MAX_CONTENT_CHARS,
    AIExtractionRequest,
    AIExtractorProvider,
    AIProviderError,
    AIProviderExecutionError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
    RawAIExtractionResponse,
)
from .validation import (
    AI_EXTRACTION_VERSION,
    MAX_JSON_NESTING_DEPTH,
    MAX_RAW_RESPONSE_BYTES,
    AIDecisionFieldRejectedError,
    AIExtractionValidationError,
    AIGroundingFailedError,
    AIReferenceInvalidError,
    AIResponseMalformedError,
    AIResponseTooLargeError,
    AISchemaInvalidError,
    AIUnknownIndicatorError,
    ValidatedAIExtraction,
    validate_ai_extraction,
)
from .governance import (
    AI_ADAPTER_ID,
    AI_ADAPTER_VERSION,
    CONFIDENCE_POLICY_VERSION,
    PROMPT_TEMPLATE_ID,
    PROMPT_TEMPLATE_VERSION,
    RESPONSE_SCHEMA_ID,
    AIConfiguration,
    AIExtractionResult,
    AIGovernanceError,
    AIPromptPolicyViolationError,
    AIProvenanceDescriptor,
    AIProvenanceInvalidError,
    AIReplayIntegrityError,
    CappedAIProposal,
    PreparedAIExtraction,
    PreparedAIRequest,
    canonical_digest,
    canonical_json,
    prepare_ai_extraction,
    prepare_ai_request,
)
from .replay import AIReplaySnapshot, pin_replay_snapshot, prepare_replay, restore_replay_snapshot

__all__ = [
    # P4-WP2 provider seam
    "AIExtractorProvider",
    "AIExtractionRequest",
    "RawAIExtractionResponse",
    "AIProviderError",
    "AIProviderUnavailableError",
    "AIProviderTimeoutError",
    "AIProviderExecutionError",
    "FakeProvider",
    "MAX_CONTENT_CHARS",
    # P4-WP3 strict extraction validation
    "validate_ai_extraction",
    "ValidatedAIExtraction",
    "AIExtractionValidationError",
    "AIResponseTooLargeError",
    "AIResponseMalformedError",
    "AISchemaInvalidError",
    "AIDecisionFieldRejectedError",
    "AIUnknownIndicatorError",
    "AIReferenceInvalidError",
    "AIGroundingFailedError",
    "AI_EXTRACTION_VERSION",
    "MAX_RAW_RESPONSE_BYTES",
    "MAX_JSON_NESTING_DEPTH",
    # P4-WP4 containment, provenance, confidence and replay pins
    "AIConfiguration",
    "PreparedAIRequest",
    "prepare_ai_request",
    "PreparedAIExtraction",
    "CappedAIProposal",
    "prepare_ai_extraction",
    "AIProvenanceDescriptor",
    "AIExtractionResult",
    "AIReplaySnapshot",
    "pin_replay_snapshot",
    "restore_replay_snapshot",
    "prepare_replay",
    "AIGovernanceError",
    "AIPromptPolicyViolationError",
    "AIProvenanceInvalidError",
    "AIReplayIntegrityError",
    "canonical_json",
    "canonical_digest",
    "PROMPT_TEMPLATE_ID",
    "PROMPT_TEMPLATE_VERSION",
    "RESPONSE_SCHEMA_ID",
    "AI_ADAPTER_ID",
    "AI_ADAPTER_VERSION",
    "CONFIDENCE_POLICY_VERSION",
]
