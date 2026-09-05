# Architecture Decision Records

| Field | Value |
|---|---|
| Document ID | ADR-INDEX |
| Version | 1.4 |
| Status | Active |
| Owner role | Chief Architect |
| Last updated | 2026-09-05 |

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
| [ADR-0014](ADR-0014-language-and-script-strategy.md) | Language and script strategy — MVP English-only, schemas extensible (OI-04 → option A) | Accepted | 2026-08-29 | Low |
| [ADR-0015](ADR-0015-evidence-hierarchy-and-official-alternate-provenance.md) | Evidence hierarchy and official-alternate provenance | Accepted | 2026-08-28 | Low |

## Planned

These decisions are known to be required but are deliberately **not** made yet — each needs
analysis that belongs to a later phase. Recording them now prevents them being made implicitly.

| ID | Decision needed | Phase | Depends on |
|---|---|---|---|
| ADR-0008 | Architecture style — modular monolith vs service-oriented, with extraction criteria | 5 | ARCH-001 |
| ADR-0009 | Identity, authentication and authorisation approach | 5 | ARCH-001 |
| ADR-0010 | Evidence storage and tamper-evidence mechanism | 5 | ARCH-001, [RSK-011](../docs/00-program/risk-register.md) |
| ADR-0011 | Database migration tooling | 6 | DATA-001 |
| ADR-0012 | Threat-intelligence adapter architecture and provider selection | 6 | INT-001 |
| ADR-0013 | Rule-set publication and version distribution mechanism | 5 | ARCH-001 |

**Numbering note.** ADR-0004 and ADR-0014 were issued and Accepted at the Phase-2 close (WP8);
**ADR-0005 and ADR-0006 are now issued and Accepted at the Phase-3 design gate** (DET-001); **ADR-0007 was
issued and Accepted at the Phase-4 AI design gate** (AI-001 / GATE-010). ADR-0008…0013 remain
**reserved/planned** for the planned topics above. ADR-0015 was issued ahead of them because the
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
