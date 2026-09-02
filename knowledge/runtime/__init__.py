"""TrustLens Phase 3 runtime knowledge package (P3-WP2 loader through P3-WP5 aggregation).

P3-WP2 loads an ADR-0004 published knowledge bundle into an immutable, indexed, read-only
`RuntimeKnowledge` — or fails closed with a typed error. P3-WP3 adds the deterministic three-valued
(Kleene) rule evaluator that consumes that RuntimeKnowledge plus a submission's indicator observations
and returns per-rule `RuleEvaluationResult`s. P3-WP4 then applies post-match rule suppression and
severity caps. P3-WP5 (`aggregate_decision`) folds the governed per-rule results into ONE decision-level
result — decision severity, matched-evidence strength, risk, detection confidence, corroboration and the
final classification (ADR-0006). Decision explanation prose and recommended actions remain P3-WP6.

Public API::

    from knowledge.runtime import (
        load_bundle, RuntimeKnowledge, BundleLoadError,          # P3-WP2
        RuleEvaluator, evaluate_rule_from_governed, evaluate_rules_from_governed,   # P3-WP3 production
        RuleSuppressionExecutor, evaluate_rule_with_suppression_from_governed,       # P3-WP4 production
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
from .aggregation import (
    RISK_MATRIX,
    AggregationError,
    DecisionResult,
    aggregate_decision,
    evaluate_decision_from_governed,
)
from .loader import load_bundle
from .suppression import (
    RuleSuppressionExecutor,
    SuppressionExecutionError,
    apply_rule_suppression,
    evaluate_rule_with_suppression_from_governed,
    evaluate_rules_with_suppression_from_governed,
)
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
    # P3-WP4 (rule-level suppression / severity orchestration)
    "RuleSuppressionExecutor",
    "SuppressionExecutionError",
    "apply_rule_suppression",
    "evaluate_rule_with_suppression_from_governed",
    "evaluate_rules_with_suppression_from_governed",
    # P3-WP5 (decision aggregation / risk / confidence / classification)
    "aggregate_decision",
    "evaluate_decision_from_governed",
    "DecisionResult",
    "AggregationError",
    "RISK_MATRIX",
]
