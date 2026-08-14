# ADR-0001 — Adopt the supplied technical baseline

| Field | Value |
|---|---|
| Status | **Accepted** |
| Date | 2026-07-31 |
| Owner role | Chief Architect |
| Related | `MP §4`, PROGRAM-001 CON-008, [ADR-0002](ADR-0002-defer-python-intelligence-service.md) |
| Supersedes | — |

## Context and constraints

`MP §4` specifies a technical baseline to be used *"unless repository evidence or an approved
decision changes it"*. The repository is empty ([BASELINE-001](../docs/00-program/BASELINE-001-repository-assessment.md) §2),
so there is no repository evidence pointing elsewhere — no legacy code, no existing team
convention, no operational history.

Constraints in force:
- Delivery capacity is one engineer plus AI assistance ([ASM-012](../docs/00-program/assumption-register.md))
- Java 21.0.11, Maven 3.9.11, Node 26.0.0 and Python 3.14.4 are installed
- **Docker and PostgreSQL are not installed** ([RSK-006](../docs/00-program/risk-register.md))
- `MP §20`: prefer the simplest architecture satisfying current requirements; do not introduce
  Kafka, Kubernetes, microservices, graph or vector databases merely to appear advanced

## Decision

Adopt the `MP §4` baseline as the target architecture:

| Concern | Technology |
|---|---|
| Frontend | React + TypeScript (strict) |
| Core backend | Java 21 + Spring Boot 3.x |
| AI / advanced extraction | Python + FastAPI *(deferred — see [ADR-0002](ADR-0002-defer-python-intelligence-service.md))* |
| Primary datastore | PostgreSQL 16 |
| Local environment | Docker + Docker Compose |
| CI/CD | GitHub Actions |
| API style | Versioned REST; asynchronous messaging only where workload or reliability justifies it |
| Documentation | Versioned Markdown with Mermaid diagrams; generated API docs |

Structural shape: **modular monolith** for the core, with a separately deployable Python
intelligence service when it arrives. Criteria justifying any later service extraction are
deferred to ADR-0008 in Phase 5, where the bounded contexts are actually defined.

## Alternatives considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **Adopt `MP §4` baseline** | Instruction-aligned; mature, well-documented ecosystems; Spring Boot's structure suits the domain/application/infrastructure separation `MP §16` requires; strong migration, testing and observability tooling | Java is verbose; four runtimes eventually | ✅ **Selected** |
| Consolidate on Python (FastAPI) end-to-end | One runtime; AI-native; fastest to prototype | Explicit deviation from an authoritative instruction with no evidence to justify it; weaker structural enforcement for a system whose value rests on auditability and determinism | ❌ Rejected |
| Consolidate on Node/TypeScript end-to-end | Single language across stack; strong typing | Same deviation problem; weaker library position for the eventual ML/OCR work | ❌ Rejected |
| Defer the decision to Phase 5 | Maximum information before committing | Blocks all repository scaffolding and CI setup; `MP §4` explicitly supplies a baseline precisely so this is not blocked | ❌ Rejected |

## Justification

Two independent reasons converge on the same answer.

1. **Precedence.** `MP §4` is authoritative and permits deviation only on repository evidence or
   an approved decision. Neither exists. Deviating from an authoritative instruction on
   preference alone would be exactly the silent requirement change `MP §21` prohibits.
2. **Fit.** The baseline suits the problem independently of the instruction. TrustLens's core
   value proposition is determinism, auditability and traceability — not iteration speed on a
   fashionable stack. Spring Boot's opinionated layering, mature migration tooling, and
   first-class transaction and audit support serve that better than a lighter framework would.

The one genuine concern — four runtimes for one engineer — is addressed by
[ADR-0002](ADR-0002-defer-python-intelligence-service.md) rather than by abandoning the baseline.

## Consequences

**Positive.** Instruction-aligned, so no justification debt. Strong structural support for the
architecture and testing requirements of `MP §16`/`§17`. Excellent tooling for migrations
(Flyway/Liquibase), OpenAPI generation and contract testing.

**Negative.** More ceremony than a lighter stack. Two build systems (Maven, npm) from the start,
three once Python arrives. Java verbosity slows early iteration.

**Neutral.** Commits to PostgreSQL as primary store — which does not preclude the graph-vs-relational
knowledge-storage decision deferred to ADR-0004, since PostgreSQL can represent graph structures
adequately at the scale TrustLens needs.

## Risks

| Risk | Mitigation |
|---|---|
| [RSK-006](../docs/00-program/risk-register.md) — Docker and PostgreSQL absent, blocking Phase 9 | Specification phases unaffected; sponsor admin install required before implementation ([OI-02](../docs/00-program/PROGRAM-001-program-charter.md#11-open-issues)) |
| [RSK-007](../docs/00-program/risk-register.md) — Node 26 is very new; tooling may lag | Pin versions in CI; prefer mature libraries; fall back to Node LTS if the ecosystem proves unready |
| Baseline ceremony slows a solo engineer | Modular monolith rather than services; no speculative infrastructure |

## Reversal cost

**Medium.** Reversing before implementation begins (Phase 9) costs only documentation rework.
After implementation, replacing the core runtime is a rewrite. The decision is therefore
effectively locked at the Phase 8 → Phase 9 boundary — which is the right time, since PLAN-001
is the last artifact before code.

## Validation plan

1. Phase 9 slice 1 stands up a Spring Boot skeleton plus React app with a green CI pipeline —
   proving the toolchain works end to end on this machine.
2. Architecture tests (ArchUnit) enforce the domain/application/infrastructure separation from
   slice 1, so the structure is verified continuously rather than assumed.
3. If slice 1 reveals a blocking toolchain problem, this ADR is revisited before further code.
