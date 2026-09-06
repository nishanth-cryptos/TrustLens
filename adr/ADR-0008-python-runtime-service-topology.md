# ADR-0008 — Python runtime and service topology: modular monolith with in-process reasoning kernel

| Field | Value |
|---|---|
| Status | **Accepted** — independent P5-WP2 review APPROVE; GATE-013 still requires remote CI and merge |
| Date | 2026-09-06 |
| Owner role | Chief Architect |
| Phase | Phase 5 — P5-WP2 runtime and service topology |
| Related | [ARCH-001](../docs/05-architecture/ARCH-001-enterprise-architecture.md), [ARCH-002](../docs/05-architecture/ARCH-002-python-runtime-service-topology.md), [GATE-013](../docs/00-program/GATE-013-phase-5-runtime-topology.md), [ADR-0001](ADR-0001-adopt-technical-baseline.md), [ADR-0002](ADR-0002-defer-python-intelligence-service.md), [ADR-0004](ADR-0004-knowledge-storage-architecture.md), [ADR-0005](ADR-0005-rule-execution-model.md), [ADR-0006](ADR-0006-risk-and-confidence-aggregation.md), [ADR-0007](ADR-0007-ai-authority-and-model-strategy.md), [DET-001](../docs/03-detection/DET-001-deterministic-detection-engine.md), [AI-001](../docs/04-ai/AI-001-ai-intelligence-layer.md) |
| Supersession effect | Supersedes only the conflicting physical backend/runtime-topology provisions of ADR-0001 and ADR-0002; preserves their historical record and unaffected decisions |
| Reversal cost | **Medium** for topology; rewriting or duplicating the reasoning kernel in another language remains High and requires separate approval |

## Context and constraints

ARCH-001 selects Python for TrustLens server-side application, orchestration, and reasoning capabilities and
requires P5-WP2 to choose the physical runtime/service topology. The repository now contains an authoritative
Python Phase-3 deterministic engine (`ENGINE_VERSION = 1.0.0`) and Python Phase-4 AI validation, governance,
replay, and optional integration. The canonical offline suite validates these implementations. No Java backend
or equivalent Java implementation of the reasoning semantics exists.

The implemented composition points already support an in-process topology:

- `evaluate_detection_from_governed(...)` accepts governed observations plus trusted evaluation context and
  returns the authoritative `DetectionResult`;
- `evaluate_with_optional_ai(...)` gates optional extraction, validates and governs accepted proposals, pins
  replay material, then invokes the unchanged Phase-3 boundary directly; and
- the reasoning runtime does not depend on the AI layer, a web framework, persistence, a queue, a cloud SDK,
  provider SDKs, or presentation code.

The programme has one engineer plus AI assistance. No measured scaling, availability, regulatory, ownership,
resource, or release-cadence requirement currently demands a separate reasoning deployment. A remote boundary
would add serialization, version negotiation, latency, partial failure, retry, observability, deployment, and
distributed coordination around semantics that are already proven in-process. The governing principle remains
the simplest architecture that satisfies current requirements, without treating future growth as fact.

This ADR selects topology only. It does not select a web framework, persistence product, object store, broker,
cloud/deployment platform, live AI provider, API endpoint contract, or frontend implementation.

## Decision

Adopt a **Python modular monolith with the authoritative Phase-3/Phase-4 reasoning capabilities in-process** as
the initial production backend architecture.

1. TrustLens has **one backend deployable/process boundary initially**: the current backend modules are not
   separated by an internal process or network boundary. “Modular monolith” does not require one replica, one
   machine, or one OS process forever; P5-WP5 will decide deployment and scaling mechanics.
2. Application/orchestration, evidence/normalization, governed evaluation, the reasoning kernel, optional AI
   integration, audit/replay, persistence adapters, external adapters, security/access, and reporting handoff
   remain explicit internal modules with inward-facing contracts.
3. The application layer calls the established Python composition points directly. There is **no internal
   HTTP/RPC/network call to the reasoning kernel** in the selected topology.
4. The Phase-3 kernel remains the sole authority for rule interpretation, structural semantics, suppression,
   aggregation, severity, risk, confidence, classification, explanation, recommended actions, and the final
   `DetectionResult`. Application or adapter code may not duplicate, repair, or override those semantics.
5. The local Phase-4 module remains optional and default OFF. It supplies validated governed observations
   upstream of Phase 3. Phase 3 never calls AI, and AI never becomes a verdict service.
6. Infrastructure adapters implement ports defined by application/domain modules. The kernel owns no database
   transaction and depends on no transport, persistence implementation, queue, cloud, or provider SDK.
7. This is the initial production architecture, not a disposable prototype. A module becomes a separately
   deployed service only when documented evidence satisfies at least one meaningful extraction criterion below,
   and a new ADR approves the boundary and its consequences.
8. The frontend remains a separate concern and may retain the React/TypeScript direction recorded historically.

## Alternatives considered

| Option | Description | Verdict |
|---|---|---|
| **A** | Python modular monolith; one initial backend deployable; in-process Phase-3/4 reasoning; strict modules and evidence-based future extraction | **Selected** |
| **B** | Python application/orchestration service plus separately deployed Python reasoning service across a network contract | Rejected for now; no demonstrated isolation/scaling/release need justifies the added semantic and operational boundary |
| **C** | Service-oriented Python backend from inception, with multiple deployables for ingress, evaluation, AI, evidence, audit/replay, or reporting | Rejected; complexity and distributed failure surface exceed current requirements and team capacity |

## Evaluation criteria and detailed comparison

The comparison is qualitative because the repository contains no production workload measurements or numerical
availability/throughput evidence.

| Criterion | Option A — modular monolith | Option B — separate reasoning | Option C — services from inception |
|---|---|---|---|
| Semantic-drift risk | Lowest: established Python objects and contracts are invoked directly | Higher: serialization and remote contract can diverge from in-process semantics | Highest: several contracts can reinterpret or duplicate decision data |
| Preserve Phase-3/4 implementation | Direct reuse with no protocol translation | Reuses code but adds a service wrapper and client | Reuse possible, but orchestration and ownership fragment across boundaries |
| Operational complexity | One backend unit plus external dependencies selected later | At least two backend units, health/failure/version coordination | Multiple units, routing, discovery, rollout, and dependency management |
| Team capacity | Best fit for one engineer | Standing multi-runtime-unit burden without a current driver | Poor fit; operational surface competes with product work |
| Deployment complexity | Lowest current surface; replicas remain possible later | Coordinated application/kernel deployment and compatibility | Independent deployment pipelines and compatibility matrix from inception |
| Debugging complexity | One trace and local call stack across backend modules | Cross-boundary traces, timeouts, client/server diagnostics | Distributed traces and partial failures across several components |
| Network failure modes | None inside authoritative evaluation | Timeout, partition, retry, duplicate request, stale client/server versions | Same as B across multiple edges and longer failure chains |
| Transaction coordination | Application owns local use-case boundary; kernel remains pure | Persistence and remote reasoning success require explicit coordination | Multiple local transactions and compensation/idempotency design |
| Latency | No internal network hop; no benchmark claim | Adds serialization and network scheduling overhead | Adds one or more internal network hops |
| Testability | Existing direct contracts and canonical suite remain primary | Requires contract, compatibility, and network-failure suites in addition | Requires broader integration, end-to-end, and distributed failure testing |
| Security/isolation | Strong module boundaries; smaller exposed network surface | Can isolate kernel process, but creates another authenticated network surface | More isolation options alongside substantially more exposed boundaries |
| Scalability | Replicate backend as a whole; extract on measured divergence | Kernel scales independently | Each component can scale independently, at high coordination cost |
| Independent release need | Shared release matches current ownership and semantic coupling | Supports kernel release independence, which is not currently required | Maximizes release independence without separate owners/cadences |
| Future extraction ability | Ports/modules and extraction criteria preserve a controlled path | Already extracted; future internal decomposition remains possible | Already distributed, making reversal/consolidation costly |
| Provider isolation | External provider stays behind a local adapter and controlled egress boundary | Provider isolation does not require kernel extraction | Provider integration could be isolated, but all services need not be split for it |
| Failure containment | Process-level failures share a backend domain; typed semantic failures remain contained | Kernel resource/process failure can be isolated but becomes remote unavailability | More failure domains, plus more cascading and coordination failures |
| Observability complexity | Correlation and module-level telemetry in one backend boundary | Cross-service correlation, remote-call metrics, and version visibility | Distributed tracing and service-level telemetry across every edge |
| Reversal cost | Medium: modules can be extracted behind preserved contracts when evidence appears | Medium–High to operate or merge back; remote contract becomes compatibility surface | High: many deployments/contracts/data boundaries become organizational facts |

## Justification

Option A fits every current authority and constraint with the fewest new failure modes. The authoritative
implementation and its optional-AI integration are already Python and compose through direct contracts. Keeping
that call in-process avoids inventing a second representation of governed observations and `DetectionResult`,
avoids a retryable network step inside decision production, and preserves the exact canonical regression path.

In-process use is not improper coupling: the dependency is on stable, inward-owned Python contracts, while the
kernel remains transport-, persistence-, framework-, and provider-independent. Module boundaries, forbidden
dependency rules, contract tests, and architecture checks can make this separation enforceable without a
network. A network boundary is a deployment decision, not a prerequisite for modularity.

Option B may become justified if the kernel develops a measured independent scale, isolation, ownership, or SLO
need. None is currently demonstrated. Option C creates still more network, deployment, transaction, security,
and debugging obligations without evidence that those costs buy required behavior. The selected modular
monolith retains service extraction as a governed response to evidence rather than a speculative default.

## Application and kernel responsibility boundary

| Application/orchestration owns | Reasoning kernel owns |
|---|---|
| incoming use-case orchestration and trusted host/evaluation context | immutable `RuntimeKnowledge` interpretation |
| feature-policy selection, including optional AI default-OFF policy | governed observation validation at its public boundary |
| evidence, optional extraction, and evaluation call sequencing | rule evaluation and structural occurrence semantics |
| lifecycle, persistence, and audit coordination | suppression and hard-risk override semantics |
| external response/reporting handoff | aggregation and separate severity/risk/confidence axes |
| operational infrastructure failure handling | classification, deterministic explanation/actions, and authoritative `DetectionResult` |

The application passes governed input and carries the returned result. It cannot recompute a “fallback verdict,”
change a decision field, or convert a kernel/infrastructure failure into `NO_SCAM_PATTERN`.

## Consequences

### Positive

- The proven Python engine and Phase-4 integration are reused without a rewrite or remote translation layer.
- One initial backend deployable matches current team capacity and reduces release, debugging, and operations work.
- Direct invocation preserves current latency characteristics without claiming a measured benchmark.
- The kernel remains independently testable and isolated by contracts even though it shares a deployable.
- Module ports preserve future persistence, provider, worker, and service extraction choices.
- Multiple identical backend replicas remain possible when application state is externalized appropriately.

### Disadvantages and obligations

- A resource leak or process-wide failure can affect more backend responsibilities than with a proven separate
  failure domain.
- Components cannot be deployed or scaled independently until an extraction decision is made.
- Internal boundaries require active enforcement; careless imports can erode them even without a network.
- Whole-backend releases may ship more code than one changed module and require full regression.
- Resource-heavy future OCR or provider work could contend with interactive evaluation if it remains in the
  same runtime without limits or later worker extraction.
- Scaling the entire backend for one hot module may be less efficient until evidence justifies extraction.

## Transaction and failure principles

- The kernel is a side-effect-controlled computation boundary and owns no persistence transaction.
- Application orchestration controls use-case persistence boundaries through inward-defined ports.
- No distributed transaction is introduced by this decision.
- AI failure follows the established Phase-4 exact deterministic fallback where its typed semantics apply.
- An authoritative Phase-3 `ERROR` remains authoritative and is never caught as optional AI fallback.
- Failure to store, audit, or return a result is an application/infrastructure failure, never evidence of safety.
- Later retries and idempotency controls must preserve evaluation identity and exact decision material; they may
  not fabricate, repair, or alter a `DetectionResult`.

## Service-extraction criteria

A module may be proposed for separate deployment when documented evidence establishes one or more of these nine
drivers. Meeting a driver opens analysis; it does not automatically approve extraction.

1. **Independent scaling profile.** Measured workload requires materially different scaling from the rest of the backend.
2. **Failure isolation.** A component creates demonstrated availability or resource risk that should not share the backend failure domain.
3. **Security/trust isolation.** A process/network boundary materially reduces a documented risk, such as tightly controlled external-provider egress or sensitive processing.
4. **Distinct resource profile.** CPU, accelerator, memory, or long-running workload characteristics materially conflict with interactive backend operation.
5. **Release independence.** A component has a demonstrated deployment cadence or compatibility lifecycle that cannot reasonably share backend releases.
6. **Ownership boundary.** A separate team owns, operates, and is accountable for the component and its service objectives.
7. **Regulatory or data-residency constraint.** A verified obligation mandates a distinct deployment or data-processing boundary.
8. **Availability/SLO isolation.** Validated, different service objectives require independent runtime management.
9. **Technology constraint.** A justified runtime dependency cannot reasonably or safely coexist in the Python backend.

Extraction requires measured or otherwise verifiable evidence, documented contract/data/failure consequences,
and a new approved ADR. It does not require all nine criteria.

The following are not sufficient alone: “microservices are modern,” codebase size, module count, aesthetic
preference, speculative future scale, desire to use another technology, one slow test, or organizational fashion.

## Likely future extraction candidates

These are possibilities, not current requirements:

- a heavy OCR or document-processing worker with a materially different resource/latency profile;
- a live AI/provider-egress worker or service when isolation and controlled egress require it;
- high-volume asynchronous evidence processing supported by measured workload;
- an independent reporting/export worker for long-running generation or destination failures.

The authoritative reasoning kernel is the **last extraction candidate** absent compelling evidence. A remote
decision boundary adds versioning, availability, retry, and semantic-equivalence risk at the most sensitive
point in the system.

## Requirements if the reasoning kernel is ever extracted

Any future kernel-service ADR must require, at minimum:

1. identical governed input contracts and validation behavior;
2. the identical promoted `DetectionResult` contract;
3. exact engine, bundle/content-digest, component, and profile provenance;
4. full semantic-equivalence regression against the in-process implementation;
5. exact golden-case equivalence;
6. Phase-4 optional-integration and fallback equivalence;
7. explicit client/server contract and version negotiation;
8. fail-closed timeout, partition, retry, and incompatible-version behavior;
9. no fallback decision implementation in application/client code; and
10. no duplicated rule, suppression, aggregation, classification, explanation, or action semantics.

These controls preserve ARCH-001 `INV-01`, `INV-11`, and `INV-15` across a future network boundary.

## Historical ADR reconciliation

ADR-0001 was reasonable when issued: the repository contained no implementation evidence, so it adopted the
supplied Java/Spring core, separate deferred Python intelligence service, and modular-monolith baseline. ADR-0002
then deferred creation of that Python service to keep AI optional and avoid an idle runtime. Neither decision was
wrong on its original evidence.

Repository evidence and sponsor direction have since changed materially. ADR-0008 supersedes
these conflicting **physical backend/runtime-topology provisions**:

| Historical provision | ADR-0008 reconciliation |
|---|---|
| Java core backend | Superseded by the Python-only backend direction and this Python modular-monolith topology. Java is no longer planned for the TrustLens server-side runtime. |
| Separately deployed Python intelligence service required in the target topology | Superseded initially; Phase-4 integration remains an internal Python module, while a future external provider stays behind a provider-neutral adapter. |
| AI deferred so the deterministic product works without it | Preserved and strengthened by ADR-0007/AI-001: optional, default OFF, exact deterministic fallback. |
| React/TypeScript frontend direction | Unaffected; frontend remains separate and outside this ADR. |
| Storage, local-environment, delivery, and API-style provisions | Not decided or superseded here; the responsible later Phase-5/Phase-6 decisions must reconcile them. |

ADR-0008 is Accepted following independent review. The index continues to show ADR-0001 and ADR-0002 as
Accepted historical records; only the conflicting provisions listed above cease to be current. This builder WP
does not rewrite those files. Remote CI and merge remain GATE-013 finalisation conditions.

AI authority is unchanged: ADR-0007 and AI-001 remain controlling. The local AI module can propose governed
observations; neither it nor a future provider gains decision authority.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Internal module boundaries erode | Define allowed dependencies, keep inward-owned ports, add architecture/import checks during implementation, and reject reverse dependencies in review. |
| Resource-heavy work harms interactive evaluation | Bound resources and use the extraction criteria to move demonstrated heavy work to a worker/service; P5-WP5 owns the mechanism. |
| Whole-backend failure affects evaluation and orchestration together | Keep typed failures, side effects outside the kernel, health/readiness at the application boundary, and extract only on demonstrated isolation need. |
| Future service extraction changes semantics | Require the kernel-extraction controls above and retain the in-process implementation as the equivalence oracle during migration. |
| Application duplicates decisions for convenience | Permit only direct kernel results; test forbidden decision construction/recalculation outside the kernel. |
| Modular monolith is misread as single-machine/single-replica forever | ARCH-002 distinguishes deployable architecture from replica/process deployment; P5-WP5 owns scaling. |
| Historical ADR status becomes ambiguous | Record exact supersession scope here and leave original ADR text unchanged as history. |

## Reversal cost

**Medium.** Extracting a well-bounded module requires a new deployment, contract, failure model, observability,
security, and data/transaction analysis, but not a rewrite when inward contracts are preserved. Consolidating an
extracted service later would likewise require compatibility and operational migration. Replacing Python or
rewriting/duplicating the authoritative reasoning semantics is a different, High-cost decision constrained by
ARCH-001 `INV-15` and is not authorised by this ADR.

## Acceptance evidence and remaining validation plan

Independent review returned APPROVE with no BLOCKER, HIGH, MEDIUM, or LOW findings. Remaining gate evidence:

1. Preserve the independently approved option comparison, historical reconciliation, disadvantages, extraction
   criteria, and consistency with all ARCH-001 invariants.
2. Verify `evaluate_detection_from_governed(...)` and `evaluate_with_optional_ai(...)` remain unchanged direct
   composition boundaries and `ENGINE_VERSION` remains `1.0.0`.
3. Run the canonical offline gate: `knowledge/validation/run_all.py` must pass 23/23 and its JSON report must
   state `gate=PASS`, `validators_run=23`, and `validators_failed=0`.
4. Run `ci_selftest.py`; all 7 representative defects must be caught.
5. Verify zero Phase-3/Phase-4/runtime/schema/rule/taxonomy diff and no infrastructure/runtime implementation.
6. Confirm remote CI passes where triggered, then merge through the governed process to finalise GATE-013.

Architecture/import enforcement, framework choice, persistence implementation, deployment tests, and service
extraction tests belong to later implementation work. This WP adds no validator solely for documentation.
