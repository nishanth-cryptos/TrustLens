"""TrustLens Phase 3 P3-WP2 — typed, deterministic bundle-loader errors.

The loader NEVER lets an arbitrary low-level exception (KeyError, JSONDecodeError, OSError, a
jsonschema ValidationError) escape as its public failure mode. Every failure is mapped to one of a
small, explicit hierarchy so callers and tests can distinguish *category* (isinstance) and *exact
cause* (`.code`) without string-matching a traceback.

Categories (requirement B):
  * ManifestError            — bundle/manifest format or schema failure
  * IntegrityError           — integrity / hash / missing-member failure (UnsafePathError is a subtype)
  * CompatibilityError       — unsupported bundle / component version
  * MemberSchemaError        — a member did not parse or failed its JSON Schema
  * ReferenceIntegrityError  — a governed cross-reference required by evaluation did not resolve
  * BundleNotFoundError      — the bundle directory / manifest is absent

`ReferenceIntegrityError` is named to avoid shadowing the built-in `ReferenceError`.

These are LOADING errors. They are deliberately distinct from a DET-001 *fraud* decision: a fatal
load is the engine's problem to map to a DET-001 `input_support_status = ERROR` later (P3-WP3+),
never something the loader itself expresses as a benign/no-scam outcome.
"""

from __future__ import annotations

from typing import Any


class BundleLoadError(Exception):
    """Base class for every fail-closed loader error. Carries a stable `.code` and optional `.detail`."""

    code: str = "BUNDLE_LOAD_ERROR"
    category: str = "load"

    def __init__(self, message: str, *, code: str | None = None, detail: Any = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.detail = detail if detail is not None else {}

    def __str__(self) -> str:  # deterministic, greppable
        return f"[{self.code}] {self.message}"


class BundleNotFoundError(BundleLoadError):
    """The bundle directory or its bundle-manifest.json does not exist."""

    code = "BUNDLE_NOT_FOUND"
    category = "not_found"


class ManifestError(BundleLoadError):
    """The manifest could not be parsed or failed bundle-manifest.schema.json."""

    code = "MANIFEST_INVALID"
    category = "manifest"


class IntegrityError(BundleLoadError):
    """A member is missing, or a SHA-256 / byte-count / content-digest check failed."""

    code = "INTEGRITY_ERROR"
    category = "integrity"


class UnsafePathError(IntegrityError):
    """A manifest member path is unsafe (absolute, traversal, duplicate, or escapes the bundle root)."""

    code = "UNSAFE_PATH"
    category = "integrity"


class CompatibilityError(BundleLoadError):
    """A manifest/bundle/component version is outside the engine's declared exact-token allowlist."""

    code = "VERSION_INCOMPATIBLE"
    category = "compatibility"


class MemberSchemaError(BundleLoadError):
    """A bundle member did not parse as JSON, or a rule/schema member failed JSON Schema validation."""

    code = "MEMBER_SCHEMA_INVALID"
    category = "member"


class ReferenceIntegrityError(BundleLoadError):
    """A governed cross-reference required by runtime evaluation did not resolve (would be a dead rule)."""

    code = "REFERENCE_INVALID"
    category = "reference"


class DuplicateIdError(BundleLoadError):
    """Two governed records share a semantic id — the knowledge is ambiguous and must not silently
    overwrite. Detected before index construction (rules, indicators, negatives, families, sources,
    evidence, overrides, taxonomy nodes, dimension terms)."""

    code = "DUPLICATE_ID"
    category = "duplicate"


# Exact code tokens the loader can raise, exported for tests/introspection.
ERROR_CODES = (
    "BUNDLE_NOT_FOUND",
    "MANIFEST_PARSE_ERROR",
    "MANIFEST_SCHEMA_INVALID",
    "COMPONENT_MISSING",
    "COMPONENT_HASH_MISMATCH",
    "COMPONENT_BYTE_COUNT_MISMATCH",
    "COMPONENT_UNREADABLE",
    "DIGEST_MISMATCH",
    "UNSAFE_PATH",
    "UNEXPECTED_MEMBER",
    "COUNTS_MISMATCH",
    "SCHEMA_INCOMPATIBLE",
    "VERSION_INCOMPATIBLE",
    "EMBEDDED_VERSION_MISMATCH",
    "MEMBER_PARSE_ERROR",
    "MEMBER_SCHEMA_INVALID",
    "MEMBER_SHAPE_INVALID",
    "DUPLICATE_ID",
    "REFERENCE_INVALID",
)
