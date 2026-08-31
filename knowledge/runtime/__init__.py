"""TrustLens Phase 3 runtime knowledge package (P3-WP2 loader + P3-WP3 rule evaluator).

P3-WP2 loads an ADR-0004 published knowledge bundle into an immutable, indexed, read-only
`RuntimeKnowledge` — or fails closed with a typed error. P3-WP3 adds the deterministic three-valued
(Kleene) rule evaluator that consumes that RuntimeKnowledge plus a submission's indicator observations
and returns per-rule `RuleEvaluationResult`s. The evaluator produces PER-RULE results ONLY: no
aggregation, risk, severity, classification or explanation prose (those are P3-WP4+).

Public API::

    from knowledge.runtime import (
        load_bundle, RuntimeKnowledge, BundleLoadError,          # P3-WP2
        RuleEvaluator, evaluate_rule_from_governed, evaluate_rules_from_governed,   # P3-WP3 production
        IndicatorObservation, Observation, EvaluationProfile,
        build_validated_context, EvaluationObservationContext,    # governed input boundary (internal ctx)
    )

The production evaluation APIs receive governed observation DATA (indicator-observation +
normalized-observation dicts) and own validation internally (P3WP3-R3-016); no caller-built context is
accepted. `evaluate_on_promotion_from_governed` / `evaluate_candidate_rule_from_governed` are the
non-production (design/validation) entry points.
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
from .evaluator import (
    DEFAULT_PROFILE,
    EvaluationProfile,
    EvaluatorError,
    RuleEvaluator,
    evaluate_rule_from_governed,
    evaluate_rules_from_governed,
)
from .loader import load_bundle
from .observations import (
    EvaluationObservationContext,
    IndicatorObservation,
    Observation,
    build_validated_context,
    structural_verdict,
)
from .runtime_knowledge import RuntimeKnowledge

__all__ = [
    # P3-WP2
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
    # P3-WP3
    "RuleEvaluator",
    "evaluate_rule_from_governed",
    "evaluate_rules_from_governed",
    "IndicatorObservation",
    "Observation",
    "EvaluationObservationContext",
    "build_validated_context",
    "structural_verdict",
    "EvaluationProfile",
    "DEFAULT_PROFILE",
    "EvaluatorError",
]
