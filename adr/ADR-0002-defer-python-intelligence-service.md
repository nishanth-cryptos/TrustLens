# ADR-0002 — Defer the Python intelligence service to the AI phase

| Field | Value |
|---|---|
| Status | **Accepted** |
| Date | 2026-07-31 |
| Owner role | Chief Architect |
| Related | `MP §4`, `MP §15`, [ADR-0001](ADR-0001-adopt-technical-baseline.md), [DEC-002](../docs/00-program/decision-log.md) |

## Context and constraints

[ADR-0001](ADR-0001-adopt-technical-baseline.md) adopts the `MP §4` baseline, which includes a
Python + FastAPI service for AI/ML and advanced extraction. The question this ADR answers is
**when** that service is built — not whether.

Two facts drive the answer:

1. **`MP §15` sequences AI last.** The mandatory first implementation sequence places
   *"AI-assisted capabilities behind feature flags"* at **step 10 of 11**, explicitly *"after
   deterministic foundations are stable"*. Steps 1–9 — repository hygiene, walking skeleton, rule
   schema and loader, extraction pipeline, scoring engine, evidence and reporting, URL adapters,
   OCR, auth and admin — have no Python dependency.
2. **`MP §11` requires the system to work without it.** The Phase 4 quality gate states *"the
   deterministic system must remain usable when AI components are degraded or unavailable."*
   The deterministic core must therefore be independently complete by construction.

Constraint: one engineer ([ASM-012](../docs/00-program/assumption-register.md)). Every additional
runtime carries a standing cost — a second dependency tree, CI job, container image, health
check, error path and security surface.

## Decision

Do not create the Python FastAPI service until Phase 9, implementation step 10.

The service **remains in the target architecture** and is designed for in Phase 5 (ARCH-001), so
its boundary, contract and failure containment are specified before anything depends on them.
What is deferred is standing up the runtime, not deciding its existence.

Until then, `apps/` contains only the Java core and React frontend.

## Alternatives considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **Defer to implementation step 10** | Matches `MP §15` sequencing exactly; no runtime maintained before it delivers capability; forces genuine AI-optionality rather than assumed | Requires a real service boundary later rather than growing into one | ✅ **Selected** |
| Stand it up in slice 1 as a stub | Boundary exercised from day one; integration surprises surface early | Maintains an empty service through nine slices; a stub proves the wiring, not the isolation; contradicts `MP §15` ordering | ❌ Rejected |
| Build OCR/extraction in Python from the start | Better OCR library ecosystem | OCR is Post-MVP (FR-013); would introduce the runtime for a deferred feature | ❌ Rejected |
| Drop Python entirely; do AI from Java | One fewer runtime permanently | Deviates from `MP §4` on preference alone; weak ML/OCR ecosystem position | ❌ Rejected |

## Justification

Deferral is what the master prompt's own sequencing already prescribes — this ADR records the
reasoning rather than introducing a change.

The stronger argument is architectural. `MP §11`'s gate demands the deterministic system remain
usable when AI is unavailable. Building the deterministic core **first and alone** makes that
property structural rather than aspirational: there is no period during which a hidden dependency
on the AI service can quietly form, because the service does not exist. Standing up a stub early
would have inverted this — it is precisely how such dependencies are acquired accidentally.

## Consequences

**Positive.** One runtime, one CI pipeline and one deployment unit through the deterministic
build-out. AI-optionality is enforced by construction. If the programme runs short of time, the
deterministic system is the part that stands alone — the correct thing to have finished.

**Negative.** The service boundary is exercised for the first time at step 10. Integration
surprises surface later than they would with an early stub.

**Neutral.** Python 3.14.4 is installed but unused for now, which incidentally defers the
[RSK-007](../docs/00-program/risk-register.md) bleeding-edge library concern to a point where
3.14 ecosystem support will have matured.

## Risks

| Risk | Mitigation |
|---|---|
| Late integration surprises at step 10 | ARCH-001 (Phase 5) specifies the service contract, isolation boundary and failure containment in full before any dependency exists. AI-001 (Phase 4) defines the schemas. |
| Java core accidentally absorbs AI-shaped responsibilities | Architecture tests enforce module boundaries from slice 1; ARCH-001 names the intelligence service as a distinct bounded context |
| Deferral drifts into permanent omission | Tracked explicitly as implementation step 10 in PLAN-001 with its own acceptance criteria |

## Reversal cost

**Very low.** The service is purely additive. Reversing means creating it earlier than planned —
no rework, no migration, nothing to unwind.

## Validation plan

1. ARCH-001 (Phase 5) must specify the intelligence-service boundary, contract and degradation
   behaviour **as if the service existed**. If it cannot, the deferral is hiding an unresolved
   design question and this ADR is revisited.
2. At implementation step 9 — before the service is built — the deterministic system must pass
   all its acceptance tests with no AI component present. That is the concrete proof that
   `MP §11`'s gate is satisfied structurally.
