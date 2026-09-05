"""P4-WP4 immutable replay pins. No extraction dependency or executable artifact.

This prepares and verifies replay material only. WP5 must supply the exact
governed artifact consumed by the engine; this layer does not validate its domain
semantics or execute an evaluation. An extraction performed again is a new run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .governance import (
    AIConfiguration,
    AIExtractionResult,
    AIGovernanceError,
    AIProvenanceInvalidError,
    AIReplayIntegrityError,
    _is_sealed_ai_extraction_result,
    _new_ai_extraction_result,
    _digest,
    _freeze,
    _identifier,
    _json_copy,
    canonical_digest,
    canonical_json,
)
from .validation import ValidatedAIExtraction


@dataclass(frozen=True)
class AIReplaySnapshot:
    """Digest pins the entire snapshot, including every correlation/config pin.

    Restoring with altered material and the old snapshot_digest fails during
    construction. Verification never replaces an existing pin with a new digest.
    A digest detects changes relative to a trusted pin; it is not authentication.
    """

    extraction_result: AIExtractionResult
    governed_artifact: Mapping[str, Any]
    content_digest: str
    engine_version: str
    profile: str
    snapshot_digest: str

    def __post_init__(self) -> None:
        try:
            artifact = _json_copy(self.governed_artifact)
            if type(artifact) is not dict:
                raise AIReplayIntegrityError()
            canonical_json(artifact)
            object.__setattr__(self, "governed_artifact", _freeze(artifact))
            self.verify()
        except AIProvenanceInvalidError:
            raise AIReplayIntegrityError() from None

    @property
    def run_id(self) -> str:
        return self.extraction_result.run_id

    @property
    def evaluation_id(self) -> str:
        return self.extraction_result.evaluation_id

    @property
    def config_ref(self) -> str:
        return self.extraction_result.config_ref

    @property
    def governed_artifact_digest(self) -> str:
        """Always computed from the actual immutable replay artifact."""
        return canonical_digest(self.governed_artifact)

    def _material(self) -> dict:
        return {"snapshot_version": "1.0.0", "extraction_result": self.extraction_result.as_dict(),
                "governed_artifact": _json_copy(self.governed_artifact),
                "governed_artifact_digest": self.governed_artifact_digest,
                "content_digest": self.content_digest, "engine_version": self.engine_version,
                "profile": self.profile}

    def verify(self) -> None:
        try:
            if not _is_sealed_ai_extraction_result(self.extraction_result):
                raise AIReplayIntegrityError()
            _digest(self.content_digest)
            _digest(self.snapshot_digest)
            _identifier(self.engine_version)
            _identifier(self.profile)
            _digest(self.governed_artifact_digest)
            if canonical_digest(self.governed_artifact) != self.governed_artifact_digest:
                raise AIReplayIntegrityError()
            if canonical_digest(self._material()) != self.snapshot_digest:
                raise AIReplayIntegrityError()
        except AIProvenanceInvalidError:
            raise AIReplayIntegrityError() from None

    def as_dict(self) -> dict:
        self.verify()
        return {**self._material(), "snapshot_digest": self.snapshot_digest}


def pin_replay_snapshot(result: AIExtractionResult, *, governed_artifact: Mapping[str, Any],
                        content_digest: str, engine_version: str, profile: str) -> AIReplaySnapshot:
    """Initial host pinning only, not a restoration or tamper-repair operation.

    The artifact digest is derived here from the supplied material and belongs to
    the snapshot. The WP4 audit stays unbound and is not replaced or mutated.
    """
    if not _is_sealed_ai_extraction_result(result):
        raise AIProvenanceInvalidError()
    artifact = _json_copy(governed_artifact)
    if type(artifact) is not dict:
        raise AIProvenanceInvalidError()
    artifact_digest = canonical_digest(artifact)
    material = {"snapshot_version": "1.0.0", "extraction_result": result.as_dict(),
                "governed_artifact": artifact, "content_digest": content_digest,
                "governed_artifact_digest": artifact_digest, "engine_version": engine_version,
                "profile": profile}
    return AIReplaySnapshot(result, artifact, content_digest, engine_version, profile,
                            canonical_digest(material))


def prepare_replay(snapshot: AIReplaySnapshot) -> Mapping[str, Any]:
    """Verify all pins and return the exact immutable artifact; no evaluation."""
    if type(snapshot) is not AIReplaySnapshot:
        raise AIReplayIntegrityError()
    snapshot.verify()
    return snapshot.governed_artifact


def restore_replay_snapshot(payload: Mapping[str, Any]) -> AIReplaySnapshot:
    """Restore an as_dict snapshot, retaining and checking its original digest.

    Input is parsed JSON data, not serialized text. Extra fields and unsupported
    versions fail closed. Initial pinning must never be used to restore history.
    """
    try:
        data = _json_copy(payload)
        if type(data) is not dict or set(data) != {
            "snapshot_version", "extraction_result", "governed_artifact", "governed_artifact_digest",
            "content_digest", "engine_version", "profile", "snapshot_digest",
        } or data["snapshot_version"] != "1.0.0":
            raise AIReplayIntegrityError()
        audit_data = data["extraction_result"]
        config = AIConfiguration(**audit_data["config"])
        validated_data = audit_data["validated_extraction"]
        if type(validated_data) is not dict or set(validated_data) != {"input_id", "observations", "indicators"}:
            raise AIReplayIntegrityError()
        validated = ValidatedAIExtraction(
            validated_data["input_id"], validated_data["observations"], validated_data["indicators"],
        )
        audit = _new_ai_extraction_result(
            run_id=audit_data["run_id"], evaluation_id=audit_data["evaluation_id"], config=config,
            validated_extraction=validated,
        )
        if canonical_json(audit.as_dict()) != canonical_json(audit_data):
            raise AIReplayIntegrityError()
        if data["governed_artifact_digest"] != canonical_digest(data["governed_artifact"]):
            raise AIReplayIntegrityError()
        return AIReplaySnapshot(audit, data["governed_artifact"], data["content_digest"],
                                data["engine_version"], data["profile"], data["snapshot_digest"])
    except (AIGovernanceError, KeyError, TypeError):
        raise AIReplayIntegrityError() from None
