# GATE-017 — Phase 5 observability and operations checkpoint

| Field | Value |
|---|---|
| Document ID | GATE-017 |
| Version | 1.0 |
| Status | **DECISION CANDIDATE** — independent review APPROVED; pending remote CI and merge; not Phase-5 closure |
| Phase assessed | Phase 5 — P5-WP6 observability, operability and operational readiness |
| Owner role | Chief Architect / Principal Security Engineer |
| Baseline | P5-WP5 merge `2d348edd8a7c3e3df4059ff62c033d817be80521` |
| Primary deliverables | [ADR-0017](../../adr/ADR-0017-observability-operational-readiness.md) (Accepted following independent review); [ARCH-006](../05-architecture/ARCH-006-observability-operational-readiness.md) (Decision Candidate) |
| Governing authority | ARCH-001 `INV-01`…`INV-15` §15, ARCH-002/003/004/005, ADR-0004/0007/0008/0009/0010/0016, DET-001 and AI-001 |
| Closes | P5-WP5 LOW-WP5-1 (terminal operational signer-failure state) |
| Related risks | RSK-008, RSK-010, RSK-011, RSK-012, RSK-017, RSK-018 |
| Last updated | 2026-09-06 |

## 1. Checkpoint purpose

GATE-017 records the P5-WP6 observability/operational-readiness candidate: vendor-neutral metrics + structured logs
+ traces/correlation, explicit health/dependency states, governed operational alerts, a runbook catalog, SLI/SLO
and RPO/RTO measurement frameworks, and telemetry strictly separated from the governed audit mechanism and from
decision authority. It closes the P5-WP5-owned LOW-WP5-1 finding by adding a terminal operational signer-failure
state. It does **not** close Phase 5, accept ADR-0017, authorise implementation, choose a monitoring product, or
perform the independent review.

## 2. Decision criteria

| # | Criterion | Candidate evidence | State |
|---:|---|---|---|
| 1 | ADR-0017 is Accepted following independent review | ADR-0017 metadata; ADR index Accepted section | APPROVED — INDEPENDENT REVIEW |
| 2 | ARCH-006 present as the detailed WP6 architecture | ARCH-006 metadata | AUTHORED |
| 3 | Vendor-neutral three-signal telemetry architecture; options compared | ADR-0017 §Decision, §Alternatives; ARCH-006 §3 | AUTHORED |
| 4 | Metrics, logs, traces defined | ARCH-006 §3, §6 | AUTHORED |
| 5 | Audit vs telemetry separation explicit | ADR-0017 §Decision(2); ARCH-006 §4, §16 | AUTHORED |
| 6 | No raw evidence/secrets/PII in telemetry | ADR-0017 §Decision(5); ARCH-006 §6.2 | AUTHORED |
| 7 | Metric-cardinality controls defined | ARCH-006 §6.3 | AUTHORED |
| 8 | Correlation model defined | ARCH-006 §6.1 | AUTHORED |
| 9 | Telemetry failure does not alter/block decision authority; non-blocking | ADR-0017 §Decision(4); ARCH-006 §5, §20 | AUTHORED |
| 10 | Health/dependency observability defined; `UNKNOWN` ≠ `HEALTHY` | ARCH-006 §7.2, §7.3 | AUTHORED |
| 11 | Optional AI degradation separated from core outage | ADR-0017 §Decision(8); ARCH-006 §7.3, §10.3, §11.4 | AUTHORED |
| 12 | Operational severity separated from detection severity | ADR-0017 §Decision(7); ARCH-006 §7.1 | AUTHORED |
| 13 | Alert architecture defined (no numeric thresholds) | ARCH-006 §12 | AUTHORED |
| 14 | Runbook architecture + catalog RB-01…RB-15 + safety | ARCH-006 §19 | AUTHORED |
| 15 | Signer terminal-failure state closes LOW-WP5-1 (no unsigned-as-signed; history preserved) | ADR-0017 §Decision(10); ARCH-006 §8 | AUTHORED |
| 16 | Backup/restore observability defined | ARCH-006 §11.1, §11.2, §17 | AUTHORED |
| 17 | Reconciliation observability defined | ARCH-006 §11.3 | AUTHORED |
| 18 | SLI/SLO framework defined; no numeric SLO invented | ARCH-006 §10.1, §10.2 | AUTHORED |
| 19 | RPO/RTO measurement framework defined; values not invented absent sponsor evidence | ARCH-006 §10.4 | AUTHORED |
| 20 | No monitoring vendor selected | ADR-0017 §Decision(1); ARCH-006 §1 | AUTHORED |
| 21 | ADR-0013 not issued/resolved; left for P5-WP7 reconciliation | ADR-0017 §Decision(12); ARCH-006 §22 | AUTHORED |
| 22 | Phase-3/Phase-4 authority, semantics and `ENGINE_VERSION` frozen | Builder freeze verification | PASS — LOCAL BUILDER |
| 23 | No monitoring/telemetry/dashboard/alert/endpoint implementation added | Builder change-surface verification | PASS — LOCAL BUILDER |
| 24 | Canonical gate and CI self-test remain green | Required local validation below | PASS — LOCAL BUILDER |
| 25 | No production-readiness / measured-SLO / efficacy / compliance claim; G-09 OPEN | ADR-0017; ARCH-006 §1, §23; this gate §4 | AUTHORED |

`AUTHORED` means the builder supplied reviewable design evidence. It is not independent approval or acceptance.

## 3. Selected candidate and acknowledged limits

The candidate adopts vendor-neutral metrics + structured logs + traces/correlation with explicit health/dependency
states, governed operational alerts and a runbook catalog. Operational telemetry is strictly separated from the
governed ADR-0010 audit and from decision authority: it never sets/overrides/reinterprets/blocks/reconstructs a
`DetectionResult`, excludes raw evidence/secrets/PII, uses bounded metric labels, and degrades to
`OBSERVABILITY_DEGRADED` on outage without a Phase-3 dependency. Optional AI observability is separated from core
health/SLO; operational severity is a distinct namespace. The signer model gains a `CHECKPOINT_TERMINAL_FAILURE`
state (closing LOW-WP5-1) that never auto-signs, never fabricates a signature, and preserves history. SLI/SLO and
RPO/RTO **frameworks** and ownership are defined without inventing numeric targets.

Acknowledged limits: numeric SLO/RPO/RTO targets, alert thresholds, max pending-checkpoint age, restore-test
frequency and telemetry retention durations remain NOT YET SPECIFIED pending sponsor/operational evidence; the
observability product, exporters, dashboards and alert rules are Phase-6 implementation. Reserved ADR-0013 remains
Planned and is reconciled by P5-WP7. Retention/legal basis remain OI-05.

### 3.1 Independent review outcome (acceptance-time)

Independent P5-WP6 review returned **APPROVE** — BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 1 / INFO 3. ADR-0017 is
**Accepted following independent review**; ARCH-006 and GATE-017 remain Decision Candidates pending remote CI and
merge. The findings are recorded non-blocking follow-ups; no observability semantics were redesigned:

| Finding | Summary | Disposition |
|---|---|---|
| LOW-1 | ARCH-006 §2 traceability row for NFR-016 abuse/overload cited §14.4 (Clock/time) instead of §14.2 (Abuse/overload) | **Corrected** — cross-reference §14.4 → §14.2; no semantic change |
| INFO-1 | `OPTIONAL_AI_DEGRADED` maps to RB-13 (provider/egress) | Acceptable; optional P5-WP7 / Phase-6 refinement only |
| INFO-2 | ARCH-006 governing-authority list omits ADR-0008 that ADR-0017 includes | No semantic defect; not reopened |
| INFO-3 | Cross-reference verification otherwise clean | No action |

Prior closed/deferred items are preserved: **WP5 LOW-1 CLOSED** (`CHECKPOINT_TERMINAL_FAILURE`); **WP4 LOW-2
CLOSED** (pending/signed signer distinction); **WP4 LOW-4 CLOSED** (restore authorisation + restored-data integrity
verification); **WP4 LOW-3 still deferred** to Phase 6 / ADR-0012 (DNS-rebinding / resolve-time SSRF TOCTOU); and
**reserved ADR-0013 remains Planned**, to be reconciled by P5-WP7 before Phase-5 closure. This is acceptance-time
governance bookkeeping only.

## 4. Programme and claim status

| Item | Status |
|---|---|
| Phase 1 | PARTIAL |
| Phase 2 | PASS |
| Phase 3 | CLOSED at `phase3-wp8-v1.0`; `ENGINE_VERSION = 1.0.0` |
| Phase 4 | FORMALLY CLOSED at merged GATE-011; bounded optional offline reference/scaffold |
| Phase 5 | P5-WP6 DECISION CANDIDATE; not complete |
| Phase 6 | NOT STARTED |
| Phase 7 / UI | NOT STARTED |
| G-09 | OPEN |

No production-readiness, measured/five-nines availability, zero-downtime, achieved RPO/RTO, DR/security/compliance
certification, evidentiary admissibility, tamper-proof-logging, or real-world detection-effectiveness (accuracy/
precision/recall/false-positive/negative) claim is made. Aggregate classification counts are descriptive
operational distributions only.

## 5. Required local builder validation

| Check | Required result | Candidate state |
|---|---|---|
| `knowledge/validation/run_all.py` | PASS — 23/23 | PASS — LOCAL BUILDER |
| `knowledge/validation/run_all.py --json` | `gate=PASS`, `validators_run=23`, `validators_failed=0` | PASS — LOCAL BUILDER |
| `knowledge/validation/ci_selftest.py` | PASS — 7/7 defects caught | PASS — LOCAL BUILDER |
| Phase-3/Phase-4 freeze and `ENGINE_VERSION` | zero diff; `1.0.0` | PASS — LOCAL BUILDER |
| Markdown whitespace and `git diff --check` | clean | PASS — LOCAL BUILDER |

Local builder results are recorded here after execution. They do not replace independent review or remote CI.

## 6. Finalisation conditions

GATE-017 may be finalised only after:

1. a separate independent review returns **APPROVE**;
2. ADR-0017 is independently approved before any Accepted status;
3. canonical local validation and CI self-test pass;
4. remote CI passes where triggered; and
5. the approved changes merge to `main`.

Phase-5 closure remains later integrated gate work (P5-WP7, which must also reconcile reserved ADR-0013). P5-WP7
must not start under this builder checkpoint.

## 7. Change boundary

The candidate change surface is limited to new ADR-0017, ARCH-006, GATE-017, and the ADR index update. ADR-0004/
0007/0008/0009/0010/0016, ARCH-001/002/003/004/005, GATE-012/013/014/015/016, the risk register, runtime/AI code,
promoted schemas/rules/taxonomies, detection/AI design documents, canonical validators, workflow, monitoring
implementation, and UI remain unchanged.

## 8. Candidate recommendation

Independent review APPROVED the P5-WP6 observability/operational-readiness candidate and ADR-0017; acceptance
bookkeeping is complete (ADR-0017 Accepted; ADR index updated; LOW-1 cross-reference corrected; INFO items
non-blocking). The WP5-owned LOW-WP5-1 finding remains closed. Continue with required remote CI and merge
finalisation. Do not commit yet, and do not begin P5-WP7 in this step (P5-WP7 also reconciles reserved ADR-0013).
