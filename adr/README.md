# Architecture Decision Records

| Field | Value |
|---|---|
| Document ID | ADR-INDEX |
| Version | 2.6 |
| Status | Active |
| Owner role | Chief Architect |
| Last updated | 2026-09-06 |

Per `MP §20`, every major architectural choice is captured as a numbered ADR stating: the
decision, constraints, viable alternatives, comparison criteria, selected option, justification,
consequences, risks, **reversal cost** and validation plan.

Programme-level scope, process and evidence decisions live in the
[Decision Log](../docs/00-program/decision-log.md) instead.

**Status values:** `Proposed` · `Accepted` · `Superseded by ADR-nnnn` · `Deprecated`.

---

## Accepted

| ID | Title | Status | Date | Reversal cost |
|---|---|---|---|---|
| [ADR-0001](ADR-0001-adopt-technical-baseline.md) | Adopt the supplied technical baseline | Accepted | 2026-07-31 | Medium |
| [ADR-0002](ADR-0002-defer-python-intelligence-service.md) | Defer the Python intelligence service to the AI phase | Accepted | 2026-07-31 | Very low |
| [ADR-0003](ADR-0003-rule-representation-format.md) | Rule representation — JSON Schema plus a cross-file linter | Accepted | 2026-08-15 | Low |
| [ADR-0004](ADR-0004-knowledge-storage-architecture.md) | Knowledge storage — Git source of truth + immutable hashed runtime bundle | Accepted | 2026-08-29 | Low |
| [ADR-0005](ADR-0005-rule-execution-model.md) | Rule execution model — three-valued (Kleene) interpreter over the immutable bundle | Accepted | 2026-08-29 | Low |
| [ADR-0006](ADR-0006-risk-and-confidence-aggregation.md) | Risk and confidence aggregation — categorical, decomposable, non-probabilistic (implements CONF-001) | Accepted | 2026-08-29 | Low–Medium |
| [ADR-0007](ADR-0007-ai-authority-and-model-strategy.md) | AI authority boundary and provider-neutral model strategy | Accepted | 2026-09-05 | High |
| [ADR-0008](ADR-0008-python-runtime-service-topology.md) | Python runtime and service topology — modular monolith with in-process reasoning kernel | Accepted | 2026-09-06 | Medium |
| [ADR-0009](ADR-0009-identity-authentication-authorization.md) | Identity, authentication and authorisation | Accepted | 2026-09-06 | Medium |
| [ADR-0010](ADR-0010-evidence-storage-tamper-evidence.md) | Evidence storage and tamper-evidence mechanism | Accepted | 2026-09-06 | Medium |
| [ADR-0013](ADR-0013-rule-set-publication-version-distribution.md) | Rule-set publication and version distribution mechanism | Accepted | 2026-09-06 | Low–Medium |
| [ADR-0014](ADR-0014-language-and-script-strategy.md) | Language and script strategy — MVP English-only, schemas extensible (OI-04 → option A) | Accepted | 2026-08-29 | Low |
| [ADR-0015](ADR-0015-evidence-hierarchy-and-official-alternate-provenance.md) | Evidence hierarchy and official-alternate provenance | Accepted | 2026-08-28 | Low |
| [ADR-0016](ADR-0016-deployment-resilience-runtime-topology.md) | Deployment, resilience and runtime topology | Accepted | 2026-09-06 | Medium |
| [ADR-0017](ADR-0017-observability-operational-readiness.md) | Observability and operational readiness | Accepted | 2026-09-06 | Low–Medium |

### Current backend/runtime topology

**ADR-0008 is the current authority.** It supersedes only the Java core-backend and mandatory separate Python
intelligence-service topology provisions of ADR-0001 and ADR-0002. ADR-0001 and ADR-0002 remain historical
Accepted records for their original rationale and non-conflicting provisions; their complete decisions are not
marked Superseded.

## Planned

These decisions are known to be required but are deliberately **not** made yet — each needs
analysis that belongs to a later phase. Recording them now prevents them being made implicitly.

| ID | Decision needed | Phase | Depends on |
|---|---|---|---|
| ADR-0011 | Database migration tooling | 6 | DATA-001 |
| ADR-0012 | Threat-intelligence adapter architecture and provider selection | 6 | INT-001 |

**Numbering note.** ADR-0004 and ADR-0014 were issued and Accepted at the Phase-2 close (WP8);
**ADR-0005 and ADR-0006 are now issued and Accepted at the Phase-3 design gate** (DET-001); **ADR-0007 was
issued and Accepted at the Phase-4 AI design gate** (AI-001 / GATE-010). **ADR-0008 was issued and Accepted at
P5-WP2 following independent review**; **ADR-0010 was issued and Accepted at P5-WP3 following independent review**;
**ADR-0009 was issued and Accepted at P5-WP4 following independent review** (identity/authentication/authorisation);
**ADR-0016 was issued and Accepted at P5-WP5 following independent review** (deployment/resilience/runtime topology);
**ADR-0017 was issued and Accepted at P5-WP6 following independent review** (observability/operational readiness);
**ADR-0013 was issued and Accepted at P5-WP7 following independent Phase-5 closure review** (rule-set publication/version distribution);
ADR-0011 and ADR-0012 remain **reserved/planned** for the Phase-6 topics above. ADR-0015 was issued ahead of them because the
RESEARCH-006 manual retrieval reconciliation forced an evidence-model decision (the evidence hierarchy)
that could not wait for those later phases.

## Template

```markdown
# ADR-nnnn — <Title>

| Status | Proposed / Accepted / Superseded |
| Date | YYYY-MM-DD |
| Owner role | <role> |
| Related | <IDs> |

## Context and constraints
## Decision
## Alternatives considered
| Option | Pros | Cons | Verdict |
## Justification
## Consequences
## Risks
## Reversal cost
## Validation plan
```
