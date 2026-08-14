# Architecture Decision Records

| Field | Value |
|---|---|
| Document ID | ADR-INDEX |
| Version | 1.0 |
| Status | Active |
| Owner role | Chief Architect |
| Last updated | 2026-07-31 |

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

## Planned

These decisions are known to be required but are deliberately **not** made yet — each needs
analysis that belongs to a later phase. Recording them now prevents them being made implicitly.

| ID | Decision needed | Phase | Depends on |
|---|---|---|---|
| ADR-0003 | Rule representation format — JSON Schema vs alternative declarative contract | 2 | KB-001 |
| ADR-0004 | Knowledge storage — relational, graph database, or hybrid, with migration path | 2 | KB-001, `MP §9` |
| ADR-0005 | Rule execution model — interpreter design, dependency resolution, determinism guarantees | 3 | DET-001 |
| ADR-0006 | Risk and confidence aggregation mathematics | 3 | DET-001, [CONF-001](../docs/00-program/conflict-register.md) |
| ADR-0007 | AI model strategy — local/open vs managed API vs hybrid | 4 | AI-001, `MP §11` |
| ADR-0008 | Architecture style — modular monolith vs service-oriented, with extraction criteria | 5 | ARCH-001 |
| ADR-0009 | Identity, authentication and authorisation approach | 5 | ARCH-001 |
| ADR-0010 | Evidence storage and tamper-evidence mechanism | 5 | ARCH-001, [RSK-011](../docs/00-program/risk-register.md) |
| ADR-0011 | Database migration tooling | 6 | DATA-001 |
| ADR-0012 | Threat-intelligence adapter architecture and provider selection | 6 | INT-001 |
| ADR-0013 | Rule-set publication and version distribution mechanism | 5 | ARCH-001 |
| ADR-0014 | Language and script handling strategy | 2 | [CONF-004](../docs/00-program/conflict-register.md) resolution |

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
