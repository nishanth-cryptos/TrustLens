# GATE-012 — Phase 5 enterprise architecture design checkpoint

| Field | Value |
|---|---|
| Document ID | GATE-012 |
| Version | 1.0 |
| Status | **DESIGN CANDIDATE** — awaiting independent review; not Phase-5 closure |
| Phase assessed | Phase 5 — P5-WP1 enterprise architecture authority and system context |
| Owner role | Chief Architect |
| Baseline | `main` Phase-4 closure merge `a41b010954db45c61dbadb2c63d6c8333ea359d7` |
| Current backend direction | **Python-only server-side application and reasoning capabilities** — sponsor-directed; physical topology deferred |
| Primary deliverable | [ARCH-001](../05-architecture/ARCH-001-enterprise-architecture.md) |
| Dependencies | PROGRAM-001, merged GATE-011 Phase-4 closure, DET-001, AI-001, ADR-0001/0002/0004/0005/0006/0007/0014/0015 |
| Last updated | 2026-09-06 |

## 1. Gate purpose

GATE-012 is the design checkpoint for the first Phase-5 work package. It establishes a reviewable logical
architecture candidate that later Phase-5 packages can use for topology, persistence, security, deployment,
and operations decisions. It does not close Phase 5, approve a runtime topology, or authorise implementation.

## 2. Candidate criteria

| # | Criterion | Builder evidence | Candidate state |
|---|---|---|---|
| 1 | ARCH-001 exists with Phase-5 metadata and related authorities | ARCH-001 metadata and acceptance section | AUTHORED |
| 2 | System purpose and explicit claim boundary are defined | ARCH-001 §§1, 16, 19 | AUTHORED |
| 3 | Inside-system responsibilities and outside actors/systems are defined | ARCH-001 §2 | AUTHORED |
| 4 | Technology-neutral system-context and logical-flow diagrams are present | ARCH-001 §§3–4 | AUTHORED |
| 5 | Phase-3/Phase-4 authority map is explicit | ARCH-001 §5 | AUTHORED |
| 6 | Immutable architecture invariants are explicit | ARCH-001 §6 (`INV-01`…`INV-15`) | AUTHORED |
| 7 | Logical layers and inward dependency rules are defined without implying services | ARCH-001 §7 | AUTHORED |
| 8 | Existing Python kernel is placed as an asset without semantic redesign | ARCH-001 §8 | AUTHORED |
| 9 | AI, knowledge, logical data, trust, and security boundaries are defined | ARCH-001 §§9–13 | AUTHORED |
| 10 | Fast/heavy workload shapes and ASRs are recorded without a processing product choice | ARCH-001 §§14–15 | AUTHORED |
| 11 | Physical process/service/deployment choices and implementation are excluded | ARCH-001 §16 | AUTHORED |
| 12 | Historical Java/Python decisions and the current sponsor-directed Python backend direction are explicitly recorded | ARCH-001 §§1.1, 17 | AUTHORED |
| 13 | ADR-0008 remains deferred to WP2 for Python topology; no physical topology option is selected | ARCH-001 §17 | AUTHORED |
| 14 | Future ADR and Phase-5 work-package maps are present | ARCH-001 §18 | AUTHORED |
| 15 | Phase-3/Phase-4 implementation and promoted knowledge/schema semantics remain frozen | Change-surface and regression checks required below | AWAITING FINALISATION |
| 16 | G-09 remains OPEN and no efficacy/production-readiness claim is made | ARCH-001 §§1, 19; this gate §4 | AUTHORED |

`AUTHORED` records builder completion of the stated content. It is not independent approval or gate PASS.

## 3. Current backend direction and deferred decisions

Python is the selected backend/runtime direction for TrustLens application, orchestration, and reasoning
capabilities based on repository evidence and explicit sponsor direction. The frontend remains separate and may
use React/TypeScript under the historical baseline. No Java server-side runtime is planned unless a compelling
future requirement and approved ADR justify it.

ADR-0001 and ADR-0002 remain historical Accepted decisions and are unchanged by this WP. Their formal
reconciliation or supersession is deferred to P5-WP2 / ADR-0008. ADR-0008 now decides Python architecture style
and physical process/service topology—not the backend language. Candidate analysis includes an in-process Python
modular monolith, separate Python application/reasoning deployables, and a modular Python backend with explicit
future extraction criteria.

- P5-WP2 / reserved ADR-0008: Python architecture style and runtime/service topology; formal ADR-0001/0002 reconciliation.
- P5-WP3 / reserved ADR-0010: evidence storage, retention, deletion, integrity, and tamper evidence.
- P5-WP4 / reserved ADR-0009: identity, authentication, authorisation, and full STRIDE analysis.
- P5-WP3 or a later governed Phase-5 package / reserved ADR-0013: knowledge publication and distribution.
- P5-WP5: deployment, resilience, scaling, and synchronous/asynchronous processing choices.
- P5-WP6: operational observability, alerts, runbooks, and justified numerical service objectives.

No Python framework, database, object store, message broker, cloud/deployment vendor, identity provider, API
contract, frontend implementation, live AI provider, or process boundary is selected at this checkpoint.

## 4. Programme and claim status

| Item | Status |
|---|---|
| Phase 1 | PARTIAL |
| Phase 2 | PASS |
| Phase 3 | CLOSED at `phase3-wp8-v1.0`; `ENGINE_VERSION = 1.0.0` |
| Phase 4 | FORMALLY CLOSED at merged GATE-011; bounded offline AI reference/scaffold only |
| Phase 5 | STARTING — P5-WP1 design candidate; not complete |
| Phase 6 | NOT STARTED |
| Phase 7/UI | NOT STARTED |
| G-09 | OPEN |

No accuracy, precision, recall, false-positive/negative rate, real-world detection effectiveness, guaranteed
identification, or production-readiness claim is made. The Phase-4 AI capability remains optional, default OFF,
offline/provider-neutral at the proven baseline, and outside decision authority.

## 5. Required finalisation evidence

Before GATE-012 may be finalised:

1. a separate independent review returns **APPROVE**;
2. the canonical local `knowledge/validation/run_all.py` gate returns **PASS** with 23/23 checks;
3. `ci_selftest.py` catches all 7 representative defects;
4. remote CI returns **PASS** where the change triggers it; and
5. the approved change merges to `main`.

The builder may record local validation in the stop report, but this candidate does not self-approve and does
not claim remote CI. Phase-5 closure requires the later integrated P5-WP7 gate.

## 6. Change boundary for review

Expected change surface is limited to ARCH-001, this GATE-012 candidate, and the existing CI workflow path list
needed to trigger canonical validation for `docs/05-architecture/**`. Phase-3 runtime, Phase-4 AI, promoted
schemas, rules, taxonomies, canonical validators, prior ADRs, and prior design documents must remain unchanged.

## 7. Candidate recommendation

If the required local regressions pass and the change boundary remains clean, submit P5-WP1 for independent
review. Do not create ADR-0008 or begin P5-WP2 under this checkpoint.
