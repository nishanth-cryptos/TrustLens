"""TrustLens Phase 3 runtime knowledge package (P3-WP2).

The runtime layer that loads an ADR-0004 published knowledge bundle into an immutable, indexed,
read-only `RuntimeKnowledge` — or fails closed with a typed error. It contains NO detection logic
(no rule evaluation, suppression, scoring, classification or explanation — those are P3-WP3+).

Public API::

    from knowledge.runtime import load_bundle, RuntimeKnowledge, BundleLoadError
"""

from __future__ import annotations

from .errors import (
    BundleLoadError,
    BundleNotFoundError,
    CompatibilityError,
    DuplicateIdError,
    ERROR_CODES,
    IntegrityError,
    ManifestError,
    MemberSchemaError,
    ReferenceIntegrityError,
    UnsafePathError,
)
from .loader import load_bundle
from .runtime_knowledge import RuntimeKnowledge

__all__ = [
    "load_bundle",
    "RuntimeKnowledge",
    "BundleLoadError",
    "BundleNotFoundError",
    "ManifestError",
    "IntegrityError",
    "UnsafePathError",
    "CompatibilityError",
    "MemberSchemaError",
    "ReferenceIntegrityError",
    "DuplicateIdError",
    "ERROR_CODES",
]
