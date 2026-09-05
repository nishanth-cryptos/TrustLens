"""TrustLens Phase 4 P4-WP3 — strict, atomic, deterministic AI-extraction validation.

The validation boundary between an UNTRUSTED ``RawAIExtractionResponse`` (WP2 transport output) and
``ValidatedAIExtraction`` — VALIDATED AI extraction *proposals* (still not governed observations, not a
``DetectionResult``, not a decision). Every provider response is treated as hostile external data. The
pipeline is deterministic and offline, calls NO Phase-3 code, and never gives the AI decision authority; WP5
later maps validated proposals to governed observations and runs the Phase-3 engine.

Public failure precedence (deterministic; documented in AI-001-WP3):

    1. strict-UTF-8 validity + raw byte-size limit → AIResponseMalformedError (bad UTF-8) / AIResponseTooLargeError
    2. current-request binding            → AIReferenceInvalidError   (AI_REFERENCE_INVALID)
    3. strict JSON parse + nesting depth  → AIResponseMalformedError  (AI_RESPONSE_MALFORMED)
    4. forbidden decision/confidence scan → AIDecisionFieldRejectedError (AI_DECISION_FIELD_REJECTED)
    5. ai-extraction schema               → AISchemaInvalidError      (AI_SCHEMA_INVALID)
    6. current-input binding              → AIReferenceInvalidError
    7. duplicate proposal ids             → AIReferenceInvalidError
    8. per-item source/input correlation  → AIReferenceInvalidError
    9. indicator RuntimeKnowledge membership/polarity/live status → AIUnknownIndicatorError (AI_UNKNOWN_INDICATOR)
   10. observation-reference integrity    → AIReferenceInvalidError
   11. grounding (offsets + exact excerpt)→ AIGroundingFailedError    (AI_GROUNDING_FAILED)
   12. construct immutable validated output

Global stages inspect the whole relevant collection; within a per-item stage the winner is chosen by the
stable ``proposal_id`` key, so the resulting failure is invariant under array permutation. ATOMIC: any single
invalid item rejects the ENTIRE response (no partial acceptance / salvage / decisive-item / silent drop); a
valid response may contain zero items. Grounding proves ONLY source anchoring / reference + offset integrity /
exact excerpt correspondence — never semantic truth. The transient ``evidence_excerpt`` is dropped from the
validated output (privacy). Diagnostics are sanitized: schema failures echo only the structural path + failing
rule, never a raw model-supplied value.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from .provider import RawAIExtractionResponse

_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _ROOT / "knowledge" / "ai" / "schemas" / "ai-extraction.schema.json"

AI_EXTRACTION_VERSION = "1.0.0"

# ---- containment limits (Python-enforced BEFORE expensive work; aligned with the schema bounds) ----
# The schema caps observations/indicators at 128 items, canonical_value 256, evidence_excerpt 2048, refs 64 —
# a well-formed response stays far below this raw cap; the cap is a hard pre-parse guard against a huge blob.
MAX_RAW_RESPONSE_BYTES = 1_048_576          # 1 MiB, UTF-8
MAX_JSON_NESTING_DEPTH = 16                 # legitimate depth is ~4; far below the interpreter recursion limit
MAX_ERROR_DETAIL_CHARS = 256                # hard bound on public diagnostic length (suffix included)


def _safe_detail(text: str) -> str:
    """Bound a public diagnostic to at most MAX_ERROR_DETAIL_CHARS characters (INCLUDING the ellipsis suffix).

    This is a SECONDARY bound only. WP3 diagnostics are constructed value-free at every call site (repository-
    controlled structural descriptions + safe path/rule metadata), so truncation is never relied on to sanitize
    a hostile value — hostile model values are removed first, and the bound merely caps length defensively."""
    text = str(text)
    if len(text) <= MAX_ERROR_DETAIL_CHARS:
        return text
    suffix = "…"
    return text[: MAX_ERROR_DETAIL_CHARS - len(suffix)] + suffix

# Decision/confidence/score fields the AI response must NEVER carry. Structurally forbidden by the schema's
# additionalProperties:false; this recursive set is defence in depth so a forbidden field ANYWHERE yields the
# precise AI_DECISION_FIELD_REJECTED code rather than a generic schema failure.
_FORBIDDEN_FIELDS = frozenset({
    "classification", "decision_severity", "matched_evidence_strength", "risk_level", "detection_confidence",
    "fraud_probability", "scam_probability", "score", "safety_score", "recommended_actions", "rule_results",
    "governing_rule", "official_evidence_basis", "safe", "legitimate", "fraud_verdict",
    "confidence", "probability", "certainty", "token_probability", "self_score",
    "fraud_confidence", "scam_confidence",
})

# A negative indicator may be emitted only while it is live (governed policy; non-ACTIVE may not).
_NEGATIVE_LIVE_STATUSES = frozenset({"ACTIVE"})


# ================================================================ closed, stable error taxonomy


class AIExtractionValidationError(Exception):
    """Base of the CLOSED WP3 validation-failure taxonomy. ``.code`` is fixed by the concrete subclass
    (class-level ``_CODE`` exposed via a read-only property) and is NOT caller-selectable or mutable — the
    constructor accepts a sanitized ``detail`` string only (no ``code=`` parameter). A validation failure is
    NEVER a TrustLens decision (never NO_SCAM_PATTERN/safe); the caller degrades to deterministic-only /
    governed uncertainty (WP5). Diagnostics are bounded and never echo a raw model-supplied value."""

    _CODE: str = "AI_EXTRACTION_INVALID"

    def __init__(self, detail: str = "") -> None:
        d = _safe_detail(detail)
        self._detail = d
        super().__init__(f"[{type(self)._CODE}] {d}".rstrip())
        self.message = d

    @property
    def code(self) -> str:
        return type(self)._CODE

    @property
    def detail(self) -> str:
        return self._detail

    def __str__(self) -> str:
        return f"[{self.code}] {self._detail}".rstrip()


class AIResponseTooLargeError(AIExtractionValidationError):
    _CODE = "AI_RESPONSE_TOO_LARGE"


class AIResponseMalformedError(AIExtractionValidationError):
    _CODE = "AI_RESPONSE_MALFORMED"


class AISchemaInvalidError(AIExtractionValidationError):
    _CODE = "AI_SCHEMA_INVALID"


class AIDecisionFieldRejectedError(AIExtractionValidationError):
    _CODE = "AI_DECISION_FIELD_REJECTED"


class AIUnknownIndicatorError(AIExtractionValidationError):
    _CODE = "AI_UNKNOWN_INDICATOR"


class AIReferenceInvalidError(AIExtractionValidationError):
    _CODE = "AI_REFERENCE_INVALID"


class AIGroundingFailedError(AIExtractionValidationError):
    _CODE = "AI_GROUNDING_FAILED"


# ================================================================ validated (deeply immutable) output


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _deep_freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(v) for v in value)
    return value


def _deep_thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _deep_thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_deep_thaw(v) for v in value]
    return value


@dataclass(frozen=True)
class ValidatedAIExtraction:
    """VALIDATED AI extraction PROPOSALS — deliberately NOT a governed Observation/IndicatorObservation, NOT a
    DetectionResult, NOT trusted evidence. Deeply read-only: the collections are tuples and every nested map is
    a ``MappingProxyType`` with nested arrays frozen to tuples (e.g. ``observation_refs``). ``as_dict`` returns
    a fully detached, mutable JSON-like copy that cannot alias internal state. The transient
    ``evidence_excerpt`` has been dropped (grounding already verified it)."""

    input_id: str
    observations: tuple[Mapping[str, Any], ...]
    indicators: tuple[Mapping[str, Any], ...]

    def as_dict(self) -> dict:
        return {
            "input_id": self.input_id,
            "observations": [_deep_thaw(o) for o in self.observations],
            "indicators": [_deep_thaw(i) for i in self.indicators],
        }


# ================================================================ helpers


@lru_cache(maxsize=1)
def _schema_validator() -> Draft202012Validator:
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _fail(exc_cls: type[AIExtractionValidationError], detail: str) -> None:
    raise exc_cls(detail)


def _check_depth(root: Any) -> None:
    """Iterative (non-recursive) nesting-depth guard — deterministic, never a RecursionError."""
    stack = [(root, 1)]
    while stack:
        node, depth = stack.pop()
        if depth > MAX_JSON_NESTING_DEPTH:
            _fail(AIResponseMalformedError, f"JSON nesting depth exceeds limit {MAX_JSON_NESTING_DEPTH}")
        if isinstance(node, Mapping):
            for v in node.values():
                stack.append((v, depth + 1))
        elif isinstance(node, list):
            for v in node:
                stack.append((v, depth + 1))


def _scan_forbidden(root: Any) -> None:
    """Iterative recursive-free forbidden-field scan (defence in depth; depth already bounded)."""
    stack = [root]
    while stack:
        node = stack.pop()
        if isinstance(node, Mapping):
            for k, v in node.items():
                if k in _FORBIDDEN_FIELDS:
                    # k belongs to the CLOSED repository-owned deny-list, but keep the detail value-free/uniform.
                    _fail(AIDecisionFieldRejectedError, "forbidden decision-owned field detected")
                stack.append(v)
        elif isinstance(node, list):
            stack.extend(node)


# ================================================================ public API


def validate_ai_extraction(
    raw: RawAIExtractionResponse,
    *,
    expected_request_id: str,
    expected_input_id: str,
    normalized_inputs: Mapping[str, str],
    rk,
) -> ValidatedAIExtraction:
    """Validate ONE untrusted ``RawAIExtractionResponse`` into ``ValidatedAIExtraction`` or fail closed.

    Authoritative current-context binding (H2): ``expected_request_id`` / ``expected_input_id`` are supplied by
    the caller and are the ONLY input this validation is about — the AI payload can never select a different
    submission merely by naming another key present in ``normalized_inputs``. ``normalized_inputs`` maps
    ``input_id`` → the authoritative normalized submitted text used for grounding (single-current-input MVP;
    ``expected_input_id`` must be present). ``rk`` is the SAME authoritative ``RuntimeKnowledge`` Phase 3 uses
    (no divergent indicator copy). Any single defect raises a typed ``AIExtractionValidationError`` from the
    closed taxonomy (atomic rejection); nothing is partially accepted.
    """
    if not isinstance(raw, RawAIExtractionResponse):
        raise TypeError(f"validate_ai_extraction expects a RawAIExtractionResponse, got {type(raw).__name__}")
    if not isinstance(normalized_inputs, Mapping):
        raise TypeError("normalized_inputs must be a mapping of input_id -> normalized text")
    if not (isinstance(expected_request_id, str) and expected_request_id):
        raise TypeError("expected_request_id must be a non-empty string")
    if not (isinstance(expected_input_id, str) and expected_input_id):
        raise TypeError("expected_input_id must be a non-empty string")

    text = raw.raw_text

    # ---- 1. raw payload must be strict-UTF-8 representable; byte-size limit (BEFORE parse) ----
    if not isinstance(text, str):
        _fail(AIResponseMalformedError, "provider payload is not a string")
    try:
        raw_bytes = text.encode("utf-8")   # STRICT; a lone surrogate raises UnicodeEncodeError (never escapes)
    except UnicodeEncodeError:
        raise AIResponseMalformedError("provider payload is not valid UTF-8") from None
    if len(raw_bytes) > MAX_RAW_RESPONSE_BYTES:
        _fail(AIResponseTooLargeError, "raw response exceeds the maximum size")

    # ---- 2. current-request binding (authoritative; AI cannot rebind the request) ----
    if raw.request_id != expected_request_id:
        _fail(AIReferenceInvalidError, "request correlation failed")

    # ---- 3. strict JSON parse + nesting-depth guard (RecursionError contained, never escapes) ----
    if text.strip() == "":
        _fail(AIResponseMalformedError, "empty provider payload")
    try:
        data = json.loads(text)   # rejects invalid JSON, trailing junk / extra data, concatenated values
    except RecursionError:
        raise AIResponseMalformedError("provider payload nesting is too deep to parse") from None
    except ValueError:            # json.JSONDecodeError is a ValueError; do not echo the library message
        raise AIResponseMalformedError("provider payload is not valid JSON") from None
    _check_depth(data)

    # ---- 4. forbidden decision/confidence field scan (precise code; schema also forbids structurally) ----
    _scan_forbidden(data)

    # ---- 5. ai-extraction schema (root object, version const, enums, bounds, additionalProperties:false) ----
    #         Diagnostics are sanitized: only the structural path + failing rule, never a raw model value (M4).
    errs = sorted(_schema_validator().iter_errors(data), key=lambda e: list(e.absolute_path))
    if errs:
        e = errs[0]
        path = "/".join(str(p) for p in e.absolute_path) or "<root>"
        _fail(AISchemaInvalidError, f"schema validation failed at /{path} (rule: {e.validator})")

    # ---- 6. current-input binding (payload input_id must be the expected submission; AI cannot rebind) ----
    if expected_input_id not in normalized_inputs or not isinstance(normalized_inputs.get(expected_input_id), str):
        _fail(AIReferenceInvalidError, "expected_input_id does not resolve to authoritative submitted input")
    if data["input_id"] != expected_input_id:
        _fail(AIReferenceInvalidError, "payload input_id does not match the expected current input")
    normalized = normalized_inputs[expected_input_id]
    n = len(normalized)

    observations = data["observations"]
    indicators = data["indicators"]

    # ---- 7. duplicate proposal ids (global; deterministic winner = lexically-first duplicate) ----
    obs_ids = [o["proposal_id"] for o in observations]
    if len(set(obs_ids)) != len(obs_ids):
        _fail(AIReferenceInvalidError, "duplicate observation proposal identifier")
    ind_pids = [i["proposal_id"] for i in indicators if "proposal_id" in i]
    if len(set(ind_pids)) != len(ind_pids):
        _fail(AIReferenceInvalidError, "duplicate indicator proposal identifier")

    # ---- 8. per-item source/input correlation (bound to expected_input_id; sorted for determinism) ----
    for obs in sorted(observations, key=lambda o: o["proposal_id"]):
        if obs["source_input_id"] != expected_input_id:
            _fail(AIReferenceInvalidError, "observation source-input correlation failed")
    for ind in sorted(indicators, key=lambda i: (i.get("proposal_id", ""), i["indicator_id"])):
        if ind["input_id"] != expected_input_id:
            _fail(AIReferenceInvalidError, "indicator input correlation failed")

    # ---- 9. indicator RuntimeKnowledge membership / polarity / live status (sorted for determinism) ----
    for ind in sorted(indicators, key=lambda i: (i["indicator_id"], i.get("proposal_id", ""))):
        iid = ind["indicator_id"]
        if ind["polarity"] == "POSITIVE":
            record = rk.indicator(iid)
            if record is None:
                _fail(AIUnknownIndicatorError, "indicator membership validation failed (POSITIVE registry)")
            if record.get("polarity") not in (None, "POSITIVE"):
                _fail(AIUnknownIndicatorError, "indicator polarity does not match the governed registry")
        else:  # NEGATIVE
            record = rk.negative_indicator(iid)
            if record is None:
                _fail(AIUnknownIndicatorError, "indicator membership validation failed (NEGATIVE library)")
            status = record.get("status")
            if status is not None and status not in _NEGATIVE_LIVE_STATUSES:
                _fail(AIUnknownIndicatorError, "negative indicator is not live and may not be emitted")

    # ---- 10. observation-reference integrity (refs resolve within THIS response; OBSERVED needs support) ----
    obs_id_set = set(obs_ids)
    for ind in sorted(indicators, key=lambda i: (i["indicator_id"], i.get("proposal_id", ""))):
        refs = ind.get("observation_refs", [])
        for ref in sorted(refs):
            if ref not in obs_id_set:
                _fail(AIReferenceInvalidError, "observation reference does not resolve")
        if ind["matched"] == "OBSERVED" and not refs:
            _fail(AIReferenceInvalidError, "OBSERVED indicator has no supporting observation reference")

    # ---- 11. grounding: offsets in range + exact excerpt↔slice (sorted for determinism) ----
    for obs in sorted(observations, key=lambda o: o["proposal_id"]):
        start, end = obs["start"], obs["end"]
        if not (0 <= start < end <= n):
            _fail(AIGroundingFailedError, "grounding offset range invalid")
        excerpt = obs.get("evidence_excerpt")
        if excerpt is not None and normalized[start:end] != excerpt:
            _fail(AIGroundingFailedError, "grounding excerpt does not match the source slice")

    # ---- 12. accept: build the deeply read-only validated proposals (transient excerpt dropped) ----
    validated_obs = tuple(
        _deep_freeze({k: v for k, v in o.items() if k != "evidence_excerpt"}) for o in observations)
    validated_ind = tuple(_deep_freeze(i) for i in indicators)
    return ValidatedAIExtraction(input_id=expected_input_id, observations=validated_obs, indicators=validated_ind)
