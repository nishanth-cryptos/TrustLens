"""TrustLens Phase 3 P3-WP3 — the evaluator input boundary: the governed observation context.

The rule evaluator consumes *indicator observations* plus the *normalized observations* they reference,
never raw text. Occurrence structural semantics (negation / reported / quoted / hypothetical / mood) are
authored ONCE, on the governed `observation.schema.json` contract, and reach the evaluator through the
`indicator-observation.schema.json` `observation_refs` link:

    indicator_observation.observation_refs → normalized observation(s) → status / polarity / attribution / mood

There is exactly ONE authoritative source for occurrence semantics (P3WP3-010). Directional negation is
**occurrence-scoped** (P3WP3-R3-017): observation.schema.json §polarity and the governed extraction fixture
XF-02 show a NEGATED credential occurrence projects to `NEGATED_CREDENTIAL_REQUEST` *with `observation_refs`
to that negated occurrence* and MUST NOT project to a live positive — it does not neutralise a *separate*
live occurrence input-globally. WP3 realises structural negation via eligibility below. The separate governed
negative-library `SUPPRESS_INDICATOR` effect is likewise occurrence-associated through these refs: it can
neutralise only a positive occurrence sharing a ref; explicit disjoint refs do not interact and missing
association remains UNKNOWN.

**Production validation authority (P3WP3-R3-016).** The production evaluator OWNS validation. Callers pass
governed *data* (indicator-observation + normalized-observation dicts) to the evaluator's `*_from_governed`
APIs; the evaluator validates it here via `build_validated_context(...)`, which JSON-Schema-validates both
contracts, enforces cross-object invariants, and returns a **deep-frozen** internal context. The context
type is INTERNAL — it is never a production caller contract, so no external/test object can masquerade as
"validated". The structural verdict is a **module free function** (not a context method), so no subclass
polymorphism can alter it on the production path.

SECURITY SCOPE: these guarantees prevent validation bypass through the *supported* APIs. They do NOT (and
are not intended to) defend against arbitrary in-process reflection / monkeypatching / private-memory
mutation of frozen objects — that is out of scope.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator

MATCHED_STATES = ("OBSERVED", "NOT_OBSERVED", "UNKNOWN", "AMBIGUOUS", "NOT_APPLICABLE")
OBSERVATION_STATUSES = MATCHED_STATES
CONFIDENCE_LEVELS = ("HIGH", "MEDIUM", "LOW")
POLARITIES = ("POSITIVE", "NEGATIVE")   # registry class carried by an indicator observation

STRUCTURAL_POLARITIES = ("AFFIRMED", "NEGATED")
ATTRIBUTIONS = ("FIRST_PARTY", "REPORTED", "QUOTED", "HYPOTHETICAL")
MOODS = ("DIRECTIVE", "DESCRIPTIVE", "INTERROGATIVE")
_NONLIVE_ATTRIBUTIONS = frozenset({"REPORTED", "QUOTED", "HYPOTHETICAL"})

# Structural verdict for one occurrence / one backing observation.
LIVE = "LIVE"
NON_LIVE = "NON_LIVE"
UNRESOLVED = "UNRESOLVED"

_ROOT = Path(__file__).resolve().parents[2]
_INDICATOR_OBS_SCHEMA = _ROOT / "knowledge" / "schemas" / "indicator-observation.schema.json"
_OBSERVATION_SCHEMA = _ROOT / "knowledge" / "schemas" / "observation.schema.json"


@lru_cache(maxsize=1)
def _input_validators() -> tuple[Draft202012Validator, Draft202012Validator]:
    io_schema = json.loads(_INDICATOR_OBS_SCHEMA.read_text(encoding="utf-8"))
    obs_schema = json.loads(_OBSERVATION_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(io_schema)
    Draft202012Validator.check_schema(obs_schema)
    return Draft202012Validator(io_schema), Draft202012Validator(obs_schema)


def _require_valid(validator: Draft202012Validator, instance: Any, kind: str) -> None:
    errs = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errs:
        e = errs[0]
        raise ValueError(f"{kind} fails {validator.schema.get('title', 'schema')}: "
                         f"{e.message} at /{'/'.join(map(str, e.path))}")


def _canonical_json_snapshot(value: Any, *, path: str) -> Any:
    """Recursively capture caller-owned governed data into plain JSON containers exactly once.

    Validation, invariant checking and decoding must all consume this snapshot, never the original Mapping
    or sequence (P3WP3-R3-020). This closes the validation/decoding TOCTOU where a stateful Mapping could
    expose one value to ``dict(raw)`` during schema validation and another to the later decoder. Nested
    mappings are snapshotted too; an outer ``dict(...)`` alone is deliberately insufficient.
    """
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path}: JSON object key must be a string, got {type(key).__name__}")
            out[key] = _canonical_json_snapshot(item, path=f"{path}/{key}")
        return out
    if isinstance(value, (list, tuple)):
        return [_canonical_json_snapshot(item, path=f"{path}/{i}") for i, item in enumerate(value)]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path}: non-finite number is not valid JSON")
        return value
    raise ValueError(f"{path}: value of type {type(value).__name__} is not JSON-compatible")


# ================================================================ typed projections

@dataclass(frozen=True)
class IndicatorObservation:
    """One extractor assertion about one indicator occurrence (`indicator-observation.schema.json`). Carries
    only governed IO fields — NEVER an occurrence structural attribute (those live on the referenced
    normalized observation). `polarity` is the REGISTRY class."""

    indicator_id: str
    matched: str
    polarity: str | None = None
    confidence: str | None = None
    observation_refs: tuple[str, ...] = ()
    supporting_spans: tuple[Any, ...] = ()
    extraction_method: str | None = None
    input_id: str | None = None

    def __post_init__(self) -> None:
        if self.matched not in MATCHED_STATES:
            raise ValueError(f"indicator {self.indicator_id!r}: invalid matched state {self.matched!r}")
        if self.confidence is not None and self.confidence not in CONFIDENCE_LEVELS:
            raise ValueError(f"indicator {self.indicator_id!r}: invalid confidence {self.confidence!r}")
        if self.polarity is not None and self.polarity not in POLARITIES:
            raise ValueError(f"indicator {self.indicator_id!r}: invalid polarity {self.polarity!r}")

    @classmethod
    def _decode(cls, d: Mapping[str, Any]) -> "IndicatorObservation":
        iid = d.get("indicator_id") or d.get("id")
        conf = d.get("confidence")
        if isinstance(conf, Mapping):
            conf = conf.get("level")
        return cls(
            indicator_id=iid,
            matched=d["matched"],
            polarity=d.get("polarity") if d.get("polarity") in POLARITIES else None,
            confidence=conf,
            observation_refs=tuple(d.get("observation_refs") or ()),
            supporting_spans=tuple(d.get("supporting_spans") or ()),
            extraction_method=d.get("extraction_method"),
            input_id=d.get("input_id"),
        )


@dataclass(frozen=True)
class Observation:
    """Typed projection of a governed normalized observation (`observation.schema.json`) — only the fields
    the structural-eligibility stage reads, with the schema's own defaults applied."""

    observation_id: str
    status: str
    source_input_id: str | None = None
    polarity: str = "AFFIRMED"
    attribution: str = "FIRST_PARTY"
    mood: str = "DIRECTIVE"
    observation_type: str | None = None

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Observation":
        return cls(
            observation_id=d["observation_id"],
            status=d.get("status", "OBSERVED"),
            source_input_id=d.get("source_input_id"),
            polarity=d.get("polarity", "AFFIRMED"),
            attribution=d.get("attribution", "FIRST_PARTY"),
            mood=d.get("mood", "DIRECTIVE"),
            observation_type=d.get("observation_type"),
        )


# ================================================================ structural verdict (module FREE functions)
# Free functions — NOT methods — so no context subclass can alter the production structural verdict (R3-016).

def observation_verdict(o: Observation) -> str:
    """Structural verdict of ONE backing observation (P3WP3-013). LIVE requires status OBSERVED and a live
    first-party directive; UNKNOWN/AMBIGUOUS → UNRESOLVED; NOT_OBSERVED/NOT_APPLICABLE and any negated/
    reported/quoted/hypothetical or purely-descriptive OBSERVED → NON_LIVE."""
    if o.status in ("UNKNOWN", "AMBIGUOUS"):
        return UNRESOLVED
    if o.status in ("NOT_OBSERVED", "NOT_APPLICABLE"):
        return NON_LIVE
    if o.polarity == "NEGATED" or o.attribution in _NONLIVE_ATTRIBUTIONS:
        return NON_LIVE
    if o.polarity == "AFFIRMED" and o.attribution == "FIRST_PARTY" and o.mood != "DESCRIPTIVE":
        return LIVE
    return NON_LIVE


def structural_verdict(observations_by_id: Mapping[str, Observation], io: IndicatorObservation) -> str:
    """LIVE / NON_LIVE / UNRESOLVED for one occurrence, from its backing normalized observation(s) resolved
    via `observation_refs`, using CONSERVATIVE AGREEMENT across multiple refs (P3WP3-015): all LIVE → LIVE;
    all NON_LIVE → NON_LIVE; any mixture, or any UNRESOLVED, → UNRESOLVED. No resolvable ref → UNRESOLVED.
    Order-independent."""
    refs = io.observation_refs
    if not refs:
        return UNRESOLVED
    resolved = [observations_by_id[r] for r in refs if r in observations_by_id]
    if len(resolved) != len(refs):
        return UNRESOLVED
    verdicts = {observation_verdict(o) for o in resolved}
    if verdicts == {LIVE}:
        return LIVE
    if verdicts == {NON_LIVE}:
        return NON_LIVE
    return UNRESOLVED


# ================================================================ the (internal) evaluation context

@dataclass(frozen=True)
class EvaluationObservationContext:
    """INTERNAL, deep-frozen governed context. Constructed ONLY by `build_validated_context` (there is no
    public factory, no token, no subclass polymorphism affecting the verdict). It is never a production
    caller contract: production callers pass governed *data* to the evaluator's `*_from_governed` APIs and
    the evaluator builds this internally."""

    indicator_observations: tuple[IndicatorObservation, ...]
    observations_by_id: Mapping[str, Observation]           # MappingProxyType (read-only)
    context_input_id: str | None
    language: str
    script: str
    _by_indicator: Mapping[str, tuple[IndicatorObservation, ...]]   # MappingProxyType (read-only)

    def observations_for(self, indicator_id: str) -> tuple[IndicatorObservation, ...]:
        return self._by_indicator.get(indicator_id, ())

    def present_indicator_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_indicator))

    def __len__(self) -> int:
        return len(self.indicator_observations)


def build_validated_context(
    indicator_observations: Iterable[Mapping[str, Any]],
    observations: Iterable[Mapping[str, Any]],
    *,
    language: str = "en",
    script: str = "Latn",
) -> EvaluationObservationContext:
    """THE governed validation boundary. JSON-Schema-validates every normalized observation and every
    indicator observation, enforces cross-object invariants (single canonical input id / no cross-input —
    P3WP3-014; no dangling ref; no contradictory OBSERVED-vs-non-observed pair — P3WP3-013; no duplicate
    observation id), and returns a DEEP-FROZEN context (dict→MappingProxyType, list→tuple). Raises
    ValueError on any malformed/forbidden/missing/contradictory value. This is the only constructor of a
    validated context; the production evaluator calls it internally."""
    # P3WP3-R3-020: capture ALL caller-owned data before validation. From this point onward the original
    # iterables/mappings are never read again; schemas, invariants and decoders all see the exact same plain
    # JSON snapshot. ``list(...)`` also consumes a generator only once before recursive normalization.
    try:
        ind_snapshot = _canonical_json_snapshot(list(indicator_observations), path="indicator_observations")
        obs_snapshot = _canonical_json_snapshot(list(observations), path="observations")
    except TypeError as e:
        raise ValueError(f"governed observation input must be iterable: {e}") from e

    io_v, obs_v = _input_validators()

    obs_by_id: dict[str, Observation] = {}
    for raw in obs_snapshot:
        if not isinstance(raw, Mapping):
            raise ValueError(f"normalized observation must be an object, got {type(raw).__name__}")
        _require_valid(obs_v, raw, "normalized observation")
        oid = raw["observation_id"]
        if oid in obs_by_id:
            raise ValueError(f"duplicate normalized observation_id {oid!r}")
        obs_by_id[oid] = Observation.from_dict(raw)

    ind: list[IndicatorObservation] = []
    for raw in ind_snapshot:
        if not isinstance(raw, Mapping):
            raise ValueError(f"indicator observation must be an object, got {type(raw).__name__}")
        _require_valid(io_v, raw, "indicator observation")
        ind.append(IndicatorObservation._decode(raw))

    # P3WP3-014: one context == one input.
    all_ids = ({io.input_id for io in ind if io.input_id is not None}
               | {o.source_input_id for o in obs_by_id.values() if o.source_input_id is not None})
    if len(all_ids) > 1:
        raise ValueError(f"cross-input evidence forbidden: multiple input ids {sorted(all_ids)} in one context")
    context_input_id = all_ids.pop() if all_ids else None

    for io in ind:
        for ref in io.observation_refs:
            if ref not in obs_by_id:
                raise ValueError(f"indicator {io.indicator_id!r}: observation_ref {ref!r} does not resolve "
                                 f"to any provided normalized observation (dangling ref rejected)")
            o = obs_by_id[ref]
            if io.input_id is not None and o.source_input_id is not None and o.source_input_id != io.input_id:
                raise ValueError(f"cross-input reference: indicator {io.indicator_id!r} (input {io.input_id!r}) "
                                 f"references observation {ref!r} of input {o.source_input_id!r}")
            # P3WP3-013: a matched=OBSERVED indicator cannot rest on a NOT_OBSERVED/NOT_APPLICABLE backing.
            if io.matched == "OBSERVED" and o.status in ("NOT_OBSERVED", "NOT_APPLICABLE"):
                raise ValueError(f"contradictory governed pair: indicator {io.indicator_id!r} matched=OBSERVED "
                                 f"but backing observation {ref!r} status={o.status!r}")

    by_ind: dict[str, list[IndicatorObservation]] = {}
    for io in ind:
        by_ind.setdefault(io.indicator_id, []).append(io)
    frozen_by_ind = MappingProxyType({k: tuple(v) for k, v in by_ind.items()})
    return EvaluationObservationContext(
        indicator_observations=tuple(ind),
        observations_by_id=MappingProxyType(dict(obs_by_id)),
        context_input_id=context_input_id,
        language=language,
        script=script,
        _by_indicator=frozen_by_ind,
    )
