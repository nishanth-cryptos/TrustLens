# GATE-013 — Phase 5 Python runtime and service topology checkpoint

| Field | Value |
|---|---|
| Document ID | GATE-013 |
| Version | 1.0 |
| Status | **DECISION CANDIDATE** — independent review APPROVE; awaiting remote CI and merge; not Phase-5 closure |
| Phase assessed | Phase 5 — P5-WP2 Python runtime and service topology |
| Owner role | Chief Architect |
| Baseline | P5-WP1 merge `556d8b6c959409842685c4ff28e48825bba92c59` |
| Primary deliverables | [ADR-0008](../../adr/ADR-0008-python-runtime-service-topology.md) (Accepted); [ARCH-002](../05-architecture/ARCH-002-python-runtime-service-topology.md) (Decision Candidate) |
| Governing authority | [ARCH-001](../05-architecture/ARCH-001-enterprise-architecture.md) `INV-01`…`INV-15` |
| Last updated | 2026-09-06 |

## 1. Checkpoint purpose

GATE-013 records the P5-WP2 decision candidate: an initial Python modular-monolith backend with the proven
Phase-3/Phase-4 reasoning capabilities in-process and evidence-based future service extraction. It is an
architecture checkpoint. ADR-0008 is Accepted following independent review; this gate still does not close
Phase 5, choose infrastructure products, or authorise runtime implementation.

## 2. Decision criteria

| # | Criterion | Candidate evidence | State |
|---|---|---|---|
| 1 | ADR-0008 exists and is Accepted following independent review | ADR-0008 metadata; ADR index Accepted section | APPROVED |
| 2 | ARCH-002 exists as Decision Candidate | ARCH-002 metadata | APPROVED |
| 3 | Three credible Python topology options are compared across required criteria | ADR-0008 alternatives and comparison matrix | AUTHORED |
| 4 | Python modular monolith is selected and justified as the initial production architecture | ADR-0008 Decision/Justification; ARCH-002 §§1–2 | AUTHORED |
| 5 | Authoritative Phase-3/Phase-4 reasoning is selected in-process with no internal network call | ADR-0008 Decision; ARCH-002 §§2, 5 | AUTHORED |
| 6 | Python backend and `INV-15` preservation are explicit | ADR-0008 Context/Decision; ARCH-002 §§1, 13 | AUTHORED |
| 7 | Application/kernel authority and dependency direction prohibit decision duplication | ADR-0008 responsibility boundary; ARCH-002 §§3–6 | AUTHORED |
| 8 | Nine evidence-based service-extraction criteria and non-criteria are explicit | ADR-0008/ARCH-002 extraction sections | AUTHORED |
| 9 | Future kernel extraction requires full semantic equivalence and fail-closed networking | ADR-0008/ARCH-002 kernel safeguards | AUTHORED |
| 10 | Process/replica/worker growth remains possible without a platform choice | ARCH-002 §8 | AUTHORED |
| 11 | Historical ADR-0001/0002 topology is reconciled without rewriting history | ADR-0008 Historical ADR reconciliation | AUTHORED |
| 12 | No framework, data product, broker, cloud/deployment platform, or live provider is selected | ADR-0008 scope; ARCH-002 §§1, 16 | AUTHORED |
| 13 | No runtime/service/API/UI implementation is added | Builder change-surface verification | PASS — LOCAL BUILDER |
| 14 | Phase-3/Phase-4 files and semantics remain frozen; engine stays 1.0.0 | Builder freeze/regression verification | PASS — LOCAL BUILDER |
| 15 | Canonical gate and self-test remain green | Local validation below | PASS — LOCAL BUILDER |
| 16 | G-09 remains OPEN with no efficacy or production-readiness claim | ADR-0008/ARCH-002 claim boundary; this gate §5 | AUTHORED |

`AUTHORED` means the builder supplied reviewable evidence. It is not independent approval or acceptance.

## 3. Selected decision and acknowledged costs

The selected candidate has one initial Python backend deployable with direct in-process kernel invocation,
strict internal modules, inward-defined infrastructure ports, and no separate reasoning service. This minimizes
semantic translation, network failure, deployment, transaction, testing, debugging, and observability overhead
for current requirements and one-engineer capacity.

Accepted disadvantages are a shared process failure/resource domain, whole-backend release boundary, and no
independent module scaling until an evidence-backed extraction is approved. These costs are explicit; modular
boundaries and extraction criteria preserve a controlled path when current evidence changes.

## 4. Deferred decisions

- P5-WP3: persistence/data architecture, tamper evidence, retention/deletion, transaction design, ADR-0010.
- P5-WP4: identity/access architecture, full STRIDE, provider egress/security, ADR-0009.
- P5-WP5: physical deployment/scaling, replicas/workers, resilience, and sync/async mechanics.
- P5-WP6: observability, operational service objectives, alerts, and runbooks.
- Phase 6: API and integration contracts, retry/idempotency protocol details.
- Reserved ADR-0013: governed knowledge publication and distribution.

No deferred package may duplicate or override the Phase-3 decision authority.

## 5. Programme and claim status

| Item | Status |
|---|---|
| Phase 1 | PARTIAL |
| Phase 2 | PASS |
| Phase 3 | CLOSED at `phase3-wp8-v1.0`; `ENGINE_VERSION = 1.0.0` |
| Phase 4 | FORMALLY CLOSED at merged GATE-011; bounded offline reference/scaffold |
| Phase 5 | P5-WP2 DECISION CANDIDATE; not complete |
| Phase 6 | NOT STARTED |
| Phase 7/UI | NOT STARTED |
| G-09 | OPEN |

No accuracy, precision, recall, false-positive/negative rate, real-world scam-detection effectiveness, or
production-readiness claim is made. Architecture suitability does not establish efficacy.

## 6. Required local builder validation

| Check | Required result | Candidate state |
|---|---|---|
| `knowledge/validation/run_all.py` | PASS — 23/23 | PASS — LOCAL BUILDER |
| `knowledge/validation/run_all.py --json` | `gate=PASS`, `validators_run=23`, `validators_failed=0` | PASS — LOCAL BUILDER |
| `knowledge/validation/ci_selftest.py` | PASS — 7/7 defects caught | PASS — LOCAL BUILDER |
| Phase-3/Phase-4 freeze and `ENGINE_VERSION` | zero diff; `1.0.0` | PASS — LOCAL BUILDER |
| Markdown whitespace and `git diff --check` | clean | PASS — LOCAL BUILDER |

These local results do not replace independent review or remote CI.

## 7. Finalisation conditions

GATE-013 may be finalised only after:

1. a separate independent review returns **APPROVE** — **SATISFIED**;
2. ADR-0008 is approved for acceptance — **SATISFIED**;
3. the canonical local gate and self-test pass — **SATISFIED LOCALLY**;
4. remote CI passes where triggered — **PENDING**; and
5. the approved changes merge to `main` — **PENDING**.

ADR-0008 is Accepted and ARCH-002 remains a Decision Candidate pending the remaining gate conditions. This
checkpoint remains a Decision Candidate. Phase-5 closure remains P5-WP7 work. Do not begin P5-WP3 under this
candidate.
