"""TrustLens Phase 4 P4-WP2 — deterministic, OFFLINE FakeProvider.

A test/reference implementation of ``AIExtractorProvider`` that returns predefined outcomes for configured
``request_id`` keys. It exists so the provider seam can be exercised and later WPs validated **entirely
offline**: no network, no clock, no randomness, no filesystem dependency, no vendor SDK, and — deliberately —
**no caller-supplied executable behaviour** (no key callback, no matcher, no stored exception instance). It
simulates provider *transport* behaviour only: it performs NO parsing, validation, grounding or governed
mapping (WP3), assigns NO confidence (WP4), and produces NO TrustLens decision.

Determinism: for a fixed FakeProvider fixture state and an identical request, ``extract`` produces equivalent
transport behaviour. Lookup is by ``request.request_id`` only. Configured failures are stored as immutable
``_FailureSpec`` snapshots (kind + detail string), and a **fresh** typed exception is minted on each call, so
no mutable exception instance is retained or re-raised. A returned ``RawAIExtractionResponse`` is UNTRUSTED —
it is not trustworthy merely because the fake produced it. WP2 additionally enforces **transport correlation**:
the configured response's ``request_id`` must equal the request's, or the seam fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass

from .provider import (
    AIExtractionRequest,
    AIProviderError,
    AIProviderExecutionError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
    RawAIExtractionResponse,
)

# Canonical WP2 provider-transport failure kinds → their fixed typed exception classes. Arbitrary exception
# classes/instances are NOT accepted as configured outcomes (M4/M5).
_FAILURE_KINDS: dict[str, type[AIProviderError]] = {
    "unavailable": AIProviderUnavailableError,
    "timeout": AIProviderTimeoutError,
    "execution": AIProviderExecutionError,
}


@dataclass(frozen=True)
class _FailureSpec:
    """An immutable snapshot of a configured provider failure — never a stored exception instance (M4)."""

    kind: str
    detail: str = ""


class FakeProvider:
    """Deterministic offline ``AIExtractorProvider`` (see module docstring).

    Register outcomes against a ``request_id`` with :meth:`register_response` or :meth:`register_failure`;
    :meth:`extract` looks the request's ``request_id`` up and either returns the configured response (after a
    transport-correlation check) or raises a freshly-minted typed failure. A key may be registered **once**;
    re-registering the same key raises ``ValueError`` (deterministic, no silent override). An unconfigured key
    fails closed as ``AIProviderUnavailableError``.
    """

    def __init__(self) -> None:
        self._responses: dict[str, RawAIExtractionResponse] = {}
        self._failures: dict[str, _FailureSpec] = {}

    # ---- registration (setup-time; no callbacks, no exception instances) ----

    def _reserve(self, request_id: str) -> None:
        if not isinstance(request_id, str) or not request_id.strip():
            raise ValueError("FakeProvider fixture key must be a non-empty request_id")
        if request_id in self._responses or request_id in self._failures:
            raise ValueError(f"FakeProvider key {request_id!r} is already registered (register a key once)")

    def register_response(self, request_id: str, response: RawAIExtractionResponse) -> "FakeProvider":
        """Configure a raw response for a ``request_id`` (returns self for chaining). The response is a frozen
        ``RawAIExtractionResponse`` whose metadata was already copied at construction, so a later external
        mutation of the caller's source map cannot alter the stored response."""
        self._reserve(request_id)
        if not isinstance(response, RawAIExtractionResponse):
            raise TypeError("FakeProvider response must be a RawAIExtractionResponse")
        self._responses[request_id] = response
        return self

    def register_failure(self, request_id: str, kind: str, detail: str = "") -> "FakeProvider":
        """Configure a canonical provider *transport* failure for a ``request_id`` as an immutable snapshot.
        ``kind`` must be one of ``unavailable`` / ``timeout`` / ``execution``; ``detail`` is an immutable
        string. No exception instance is stored (M4) and no arbitrary exception class is accepted (M5)."""
        self._reserve(request_id)
        if kind not in _FAILURE_KINDS:
            raise ValueError(f"unknown provider failure kind {kind!r}; expected one of {sorted(_FAILURE_KINDS)}")
        if not isinstance(detail, str):
            raise TypeError("FakeProvider failure detail must be a string")
        self._failures[request_id] = _FailureSpec(kind=kind, detail=detail)
        return self

    # ---- extraction (pure over fixed fixture state; deterministic) ----

    def extract(self, request: AIExtractionRequest) -> RawAIExtractionResponse:
        """Return the configured raw response (after a transport-correlation check) or raise a freshly-minted
        typed provider failure. Pure over the fixed fixture state; no network/clock/randomness/hidden mutation
        and no caller-supplied executable path."""
        if not isinstance(request, AIExtractionRequest):
            raise TypeError(f"extract expects an AIExtractionRequest, got {type(request).__name__}")
        key = request.request_id

        if key in self._failures:
            spec = self._failures[key]
            exc_cls = _FAILURE_KINDS[spec.kind]
            raise exc_cls(spec.detail or f"simulated {spec.kind} provider failure")   # FRESH instance each call

        if key not in self._responses:
            raise AIProviderUnavailableError(f"FakeProvider has no configured outcome for request key {key!r}")

        response = self._responses[key]
        # WP2 transport correlation only (WP3 owns JSON/schema/semantic/membership/grounding validation).
        if response.request_id != key:
            raise AIProviderExecutionError(
                f"transport correlation failure: response.request_id {response.request_id!r} "
                f"!= request.request_id {key!r}")
        return response
