"""TrustLens Phase 4 AI intelligence layer (P4-WP2: provider-neutral offline boundary).

This package hosts the AI *extraction* layer authored under AI-001 / ADR-0007. P4-WP2 establishes ONLY the
vendor-neutral, OFFLINE provider seam and a deterministic ``FakeProvider`` — no live provider, no vendor SDK,
no network, no API key, no tools, no standing service. Provider output is UNTRUSTED transport data; it is not
a governed observation and never enters Phase 3 directly. Deterministic validation + governed mapping (WP3),
provenance/replay/confidence-cap (WP4) and Phase-3 integration + feature flags + deterministic fallback (WP5)
are later work packages.

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

__all__ = [
    "AIExtractorProvider",
    "AIExtractionRequest",
    "RawAIExtractionResponse",
    "AIProviderError",
    "AIProviderUnavailableError",
    "AIProviderTimeoutError",
    "AIProviderExecutionError",
    "FakeProvider",
    "MAX_CONTENT_CHARS",
]
