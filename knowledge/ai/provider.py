"""TrustLens Phase 4 P4-WP2 — provider-neutral, OFFLINE AI extraction boundary.

This module defines ONLY the vendor-neutral seam through which TrustLens will (in later WPs) obtain
AI-proposed extraction data — and nothing else. It contains no live provider, no vendor SDK, no HTTP/network
client, no API-key requirement, no tool execution, and no standing service. It authors no governed
``Observation`` / ``IndicatorObservation`` and no ``DetectionResult``.

Trust boundary (AI-001 §4, ADR-0007). A provider maps a bounded ``AIExtractionRequest`` — where the submitted
content is **data, never an instruction** — to a ``RawAIExtractionResponse`` that is **UNTRUSTED transport
output**: it is not parsed, not validated, not grounded, and not governed. Deterministic parsing, schema /
semantic / RuntimeKnowledge-membership / grounding validation and the governed observation mapping are owned
by **P4-WP3**; provenance / replay / confidence-cap by **P4-WP4**; Phase-3 integration + feature flags +
deterministic fallback by **P4-WP5**. WP2 deliberately keeps the payload **neutral** (an opaque ``raw_text``)
so it does not pre-empt the WP3 ``ai-extraction`` contract.

Authority / non-authority. The provider is an *extractor*, not a decision-maker: the interface exposes no
decision field (classification/severity/risk/confidence/actions/rule_results/governing_rule) and no
model-reported confidence or fraud/scam probability/score. A provider-transport failure is a typed
``AIProviderError`` and is **never** translated into a TrustLens decision (never ``NO_SCAM_PATTERN`` / safe).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Protocol, runtime_checkable

# Transport-level containment bound (AI-001 §23). This is request hygiene, NOT the semantic size/field-count
# validation owned by WP3/WP4 — it only stops an unbounded blob crossing the provider seam.
MAX_CONTENT_CHARS = 100_000


# ================================================================ typed provider-transport failures


class AIProviderError(Exception):
    """Base class for a fail-closed AI provider *transport* failure at the WP2 boundary.

    The ``.code`` is **fixed by the concrete error type and is NOT caller-overridable** (M5): each subclass
    declares a class-level ``_CODE`` and ``.code`` is a read-only property returning it. The constructor
    accepts an immutable ``detail`` string only — there is deliberately no ``code=`` parameter, so a caller
    cannot mint a bogus code. This is distinct from a later validation error (WP3/WP4) and from a TrustLens
    decision: a provider failure is the integration's problem to route to governed uncertainty later — it is
    NEVER expressed here as a benign / ``NO_SCAM_PATTERN`` / safe outcome. The complete AI failure taxonomy
    (schema/semantic/grounding/etc.) is owned by later WPs and is deliberately NOT implemented here."""

    _CODE: str = "AI_PROVIDER_ERROR"

    def __init__(self, detail: str = "") -> None:
        self._detail = str(detail)
        super().__init__(f"[{type(self)._CODE}] {self._detail}".rstrip())
        self.message = self._detail

    @property
    def code(self) -> str:
        """The stable, caller-immutable error code, fixed by the concrete error class (read-only)."""
        return type(self)._CODE

    @property
    def detail(self) -> str:
        """The immutable detail string supplied at construction."""
        return self._detail

    def __str__(self) -> str:  # deterministic, greppable
        return f"[{self.code}] {self._detail}".rstrip()


class AIProviderUnavailableError(AIProviderError):
    """The provider could not be reached / has no configured outcome (offline fake: no registered response)."""

    _CODE = "AI_PROVIDER_UNAVAILABLE"


class AIProviderTimeoutError(AIProviderError):
    """The provider did not respond within its bound."""

    _CODE = "AI_TIMEOUT"


class AIProviderExecutionError(AIProviderError):
    """The provider accepted the request but failed to execute it (a transport/execution fault, incl. a
    request/response correlation mismatch), not a validation verdict."""

    _CODE = "AI_PROVIDER_EXECUTION_FAILED"


# ================================================================ bounded, vendor-neutral request


@dataclass(frozen=True)
class AIExtractionRequest:
    """The minimal, bounded, provider-neutral request to an extraction provider.

    It carries only extraction *input* and identity/config *pointers* — never a Phase-3 decision field and
    never a general instruction. ``normalized_content`` is submitted-input DATA, passed for extraction only;
    it is never a prompt the caller lets the model *act on* (there is deliberately no ``execute_prompt`` /
    chat method — AI-001 §23/§24). ``prompt_template_id`` / ``response_contract_id`` are opaque pointers a
    later WP resolves; WP2 neither authors nor validates their content.
    """

    request_id: str
    input_id: str
    normalized_content: str
    prompt_template_id: str | None = None
    response_contract_id: str | None = None

    def __post_init__(self) -> None:
        # transport hygiene only (not WP3 semantic validation): well-typed ids + a content bound.
        for name in ("request_id", "input_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"AIExtractionRequest.{name} must be a non-empty string")
        if not isinstance(self.normalized_content, str):
            raise ValueError("AIExtractionRequest.normalized_content must be a string (submitted input data)")
        if len(self.normalized_content) > MAX_CONTENT_CHARS:
            raise ValueError(
                f"AIExtractionRequest.normalized_content exceeds the transport bound "
                f"({len(self.normalized_content)} > {MAX_CONTENT_CHARS} chars)")
        # Optional identifier pointers: None is valid; a present value MUST be a non-empty, non-whitespace
        # string. "" / "   " are rejected (never silently coerced to None) — M1.
        for name in ("prompt_template_id", "response_contract_id"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(
                    f"AIExtractionRequest.{name} must be None or a non-empty, non-whitespace string")


# ================================================================ UNTRUSTED, payload-neutral response


@dataclass(frozen=True)
class RawAIExtractionResponse:
    """The **UNTRUSTED** provider-transport output.

    This is NOT a governed ``Observation`` / ``IndicatorObservation``, NOT a ``DetectionResult``, and NOT
    validated in any way — it must not be passed into Phase 3. The name preserves the trust boundary: it is
    *raw*. ``raw_text`` is the exact, opaque provider output (which may be valid-looking JSON, empty, or
    malformed — WP3 parses/validates/rejects it). ``metadata`` is a small, vendor-neutral,
    read-only execution-metadata map (no vendor ids, no decision field, no confidence/probability/score). WP2
    intentionally keeps the payload neutral; the ``ai-extraction`` contract is authored in WP3.
    """

    request_id: str
    raw_text: str
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not self.request_id:
            raise ValueError("RawAIExtractionResponse.request_id must be a non-empty string")
        if not isinstance(self.raw_text, str):
            raise ValueError("RawAIExtractionResponse.raw_text must be a string (untrusted, unparsed)")
        md = dict(self.metadata)
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in md.items()):
            raise ValueError("RawAIExtractionResponse.metadata must be a flat string->string map")
        object.__setattr__(self, "metadata", MappingProxyType(md))   # deep read-only


# ================================================================ provider-neutral interface


@runtime_checkable
class AIExtractorProvider(Protocol):
    """The single provider-neutral extraction seam.

    An implementation maps a bounded ``AIExtractionRequest`` (submitted content is DATA, never an instruction)
    to a ``RawAIExtractionResponse`` (UNTRUSTED transport output). The interface deliberately has NO
    decision authority, NO tool-execution capability, NO general chat/``execute_prompt`` method, and NO
    vendor-specific concepts (no ``openai_response_id`` / ``anthropic_message_id`` / ``gemini_candidate_id`` in
    the domain contract — vendor metadata belongs to a future provider implementation's own audit data). A
    transport failure raises an ``AIProviderError`` subtype; it is never a TrustLens decision.
    """

    def extract(self, request: AIExtractionRequest) -> RawAIExtractionResponse:
        ...
