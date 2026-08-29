"""TrustLens Phase 3 P3-WP2 — the immutable runtime knowledge model.

`RuntimeKnowledge` is the API-neutral, read-only surface the future evaluator (P3-WP3+) consumes. It
is produced ONLY by a fully successful `loader.load_bundle(...)`; there is no public constructor path
that yields a partially populated instance. Once built it is deeply immutable (requirement C / STEP 8):
every nested mapping is a `types.MappingProxyType` and every list is a `tuple`, so evaluator code
cannot accidentally mutate governed knowledge or an index. A bundle update produces a NEW instance —
there is no in-place mutation of an already-active instance (STEP 8/9).

This model holds NO detection logic. It answers "what does the pinned knowledge say" (lookups and
justified reverse indexes); it never decides risk, severity, confidence or classification.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .indexes import INDEX_NAMES


def freeze(obj: Any) -> Any:
    """Recursively convert dicts -> MappingProxyType and lists -> tuple (deep, read-only)."""
    if isinstance(obj, MappingProxyType):
        return obj
    if isinstance(obj, dict):
        return MappingProxyType({k: freeze(v) for k, v in obj.items()})
    if isinstance(obj, (list, tuple)):
        return tuple(freeze(v) for v in obj)
    return obj


@dataclass(frozen=True)
class RuntimeKnowledge:
    """Read-only, reproducible view of one published knowledge bundle."""

    _meta: Mapping[str, Any]
    _indexes: Mapping[str, Mapping[str, Any]]

    # ---- construction (loader-internal; deep-freezes everything) ----
    @classmethod
    def build(cls, meta: dict, indexes: dict) -> "RuntimeKnowledge":
        frozen_indexes = MappingProxyType({name: freeze(indexes[name]) for name in INDEX_NAMES})
        return cls(freeze(meta), frozen_indexes)

    # ---- bundle metadata / provenance ----
    @property
    def bundle_version(self) -> str:
        return self._meta["bundle_version"]

    @property
    def content_digest(self) -> str:
        return self._meta["content_digest"]

    @property
    def commit_sha(self) -> str:
        return self._meta["commit_sha"]

    @property
    def manifest_schema_version(self) -> str:
        return self._meta["manifest_schema_version"]

    @property
    def component_versions(self) -> Mapping[str, str]:
        return self._meta["component_versions"]

    @property
    def counts(self) -> Mapping[str, Any]:
        return self._meta["counts"]

    @property
    def meta(self) -> Mapping[str, Any]:
        return self._meta

    # ---- generic index access (introspection / tests) ----
    def index_names(self) -> tuple[str, ...]:
        return INDEX_NAMES

    def index(self, name: str) -> Mapping[str, Any]:
        if name not in self._indexes:
            raise KeyError(f"unknown index {name!r}; known: {', '.join(INDEX_NAMES)}")
        return self._indexes[name]

    # ---- point lookups (return frozen record or None) ----
    def rule(self, rule_id: str) -> Mapping[str, Any] | None:
        """Any rule by id (published OR not) — for lookup/audit. Not the executable set."""
        return self._indexes["rules_by_id"].get(rule_id)

    def published_rule(self, rule_id: str) -> Mapping[str, Any] | None:
        """A rule only if it is PUBLISHED (executable); otherwise None."""
        return self._indexes["published_rules_by_id"].get(rule_id)

    def indicator(self, indicator_id: str) -> Mapping[str, Any] | None:
        return self._indexes["indicators_by_id"].get(indicator_id)

    def negative_indicator(self, negative_id: str) -> Mapping[str, Any] | None:
        return self._indexes["negative_indicators_by_id"].get(negative_id)

    def family(self, family_id: str) -> Mapping[str, Any] | None:
        return self._indexes["indicator_families_by_id"].get(family_id)

    def taxonomy_node(self, taxonomy_id: str) -> Mapping[str, Any] | None:
        return self._indexes["taxonomy_by_id"].get(taxonomy_id)

    def dimension_term(self, term_id: str) -> Mapping[str, Any] | None:
        return self._indexes["dimensions_by_id"].get(term_id)

    def source(self, source_id: str) -> Mapping[str, Any] | None:
        return self._indexes["sources_by_id"].get(source_id)

    def evidence(self, evidence_id: str) -> Mapping[str, Any] | None:
        return self._indexes["evidence_by_id"].get(evidence_id)

    def override(self, override_id: str) -> Mapping[str, Any] | None:
        return self._indexes["overrides_by_id"].get(override_id)

    # ---- id collections ----
    def rule_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._indexes["rules_by_id"]))

    def published_rule_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._indexes["published_rules_by_id"]))

    def published_rules(self) -> tuple[Mapping[str, Any], ...]:
        idx = self._indexes["published_rules_by_id"]
        return tuple(idx[rid] for rid in sorted(idx))

    # ---- justified reverse lookups (execution-oriented indexes are PUBLISHED-only) ----
    def rules_for_indicator(self, indicator_id: str) -> tuple[str, ...]:
        return self._indexes["rules_by_indicator"].get(indicator_id, ())

    def rules_for_category(self, category_id: str) -> tuple[str, ...]:
        return self._indexes["rules_by_category"].get(category_id, ())

    def negative_indicators_for_rule(self, rule_id: str) -> tuple[str, ...]:
        return self._indexes["negative_indicators_by_rule"].get(rule_id, ())

    def indicators_for_family(self, family_id: str) -> tuple[str, ...]:
        return self._indexes["positive_indicators_by_family"].get(family_id, ())

    def overrides_for_indicator(self, indicator_id: str) -> tuple[str, ...]:
        return self._indexes["overrides_by_indicator"].get(indicator_id, ())

    def overrides_for_target(self, target_id: str) -> tuple[str, ...]:
        return self._indexes["overrides_by_target"].get(target_id, ())
