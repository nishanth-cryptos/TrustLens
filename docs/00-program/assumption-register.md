# Assumption Register

| Field | Value |
|---|---|
| Document ID | REG-ASSUMPTION |
| Version | 1.1 |
| Status | Active |
| Owner role | Technical Program Director |
| Last updated | 2026-08-14 |

Per the `MP §7` quality gate: *"No later architecture decision may rely on an unstated
assumption."* Every inference the programme rests on is recorded here. Anything marked
`DERIVED` in PROGRAM-001 traces back to an entry below.

**Confidence:** `HIGH` (safe default, low cost if wrong) · `MEDIUM` (reasonable, would cause
rework) · `LOW` (weakly grounded, could invalidate downstream work).

---

| ID | Assumption | Confidence | If wrong | Validate by |
|---|---|---|---|---|
| **ASM-001** | **No end-user, analyst or official-body stakeholder is available. All personas, journeys and `DERIVED` requirements are engineering inference.** | **LOW** | **Load-bearing.** Requirements may target the wrong users and journeys; PROGRAM-001 §4–5 would need rework. This is the largest single source of requirement risk in the programme. | Sponsor providing access to even one real user or analyst ([OI-01](PROGRAM-001-program-charter.md#11-open-issues)) |
| ASM-002 | Deployment is single-tenant. Multi-tenancy is Future scope, not MVP. | HIGH | Data model needs tenant isolation retrofitted — expensive if late | Sponsor confirmation before DATA-001 |
| ASM-003 | MVP is English-first; the *architecture* is multilingual but the *content* is not. | MEDIUM | Product fails its stated core audience — see [CONF-004](conflict-register.md) | Sponsor decision on OI-04 |
| ASM-004 | No real user data is processed during the programme; all examples are synthetic and labelled as such. | HIGH | Privacy and consent obligations activate immediately | Standing constraint (CON-005) |
| ASM-005 | No budget exists for paid threat-intelligence providers. Adapters target free/keyless tiers or are stubbed. | MEDIUM | INT-001 provider selection changes | Sponsor confirmation before Phase 6 |
| ASM-006 | The research package's 0–100 scores are severity-ordering hints, not calibrated risk values. | HIGH | Scoring model rework — though the package states this itself (`RP p.6`) | Closed by [CONF-001](conflict-register.md) |
| ASM-007 | Target users are Indian consumers, primarily on mobile, submitting content after the fact rather than during a live attack. | MEDIUM | UX and latency budgets change materially | ASM-001 resolution |
| ASM-008 | TrustLens holds no regulatory registration, official status or relationship with any cited body. | HIGH | Would alter legal posture and disclaimer requirements | Standing (NG-02) |
| ASM-009 | No fixed programme end date exists; scope is staged by dependency, not calendar. | MEDIUM | PLAN-001 cannot produce a credible schedule | Sponsor ([OI-03](PROGRAM-001-program-charter.md#11-open-issues)) |
| ASM-010 | Java 21 + Spring Boot 3.x is the core backend runtime. | HIGH | Backend rework | Verified — Java 21.0.11 present |
| ASM-011 | PostgreSQL 16 runs via Docker Compose in local development. | MEDIUM | **Neither is installed** — see [RSK-006](risk-register.md) | Sponsor installs Docker ([OI-02](PROGRAM-001-program-charter.md#11-open-issues)) |
| ASM-012 | Delivery capacity is one engineer plus AI assistance. | HIGH | Sequencing and parallelisation assumptions in PLAN-001 change | Confirmed by sponsor |
| ASM-013 | No production deployment occurs during this programme; environments are local and test only. | MEDIUM | Security, scaling and operational requirements escalate sharply | Sponsor ([OI-06](PROGRAM-001-program-charter.md#11-open-issues)) |
| ASM-014 | Default evidence retention is 90 days, pending a real policy decision. | LOW | Retention, deletion and storage design change | Sponsor + legal ([OI-05](PROGRAM-001-program-charter.md#11-open-issues)) |
| ASM-015 | **Unverified:** India's Digital Personal Data Protection Act 2023 is *likely* to apply to personal data processed by TrustLens. **No legal verification has been performed and no compliance claim is made.** | LOW | Privacy design may be materially incomplete or misdirected | Qualified legal review — *not* engineering inference (`MP §2`: do not invent regulatory obligations) |
| ~~ASM-016~~ | ~~The ~26 cited source URLs remain reachable during Phase 1 verification.~~ **DISPROVED 2026-08-14 ([GATE-001](GATE-001-phase-1-assessment.md)).** 13 of 26 failed. The failure is *structural, not intermittent*: `i4c.mha.gov.in`, `pib.gov.in` and `npci.org.in` block automated retrieval; `cert-in.org.in`, `niti.gov.in` and `rbi.org.in` permit it. **Now a standing operating condition, not an assumption** — any advisory-ingestion pipeline must assume a human-in-the-loop retrieval step (INT-001, OPS-001). | ~~LOW~~ **CLOSED** | Realised: Phase 1 gated `PARTIAL`; 10 rules unsupported; [G-01…G-04](../01-research/RESEARCH-005-gap-register.md) opened | Closed by [RESEARCH-001 §5](../01-research/RESEARCH-001-source-inventory.md) |
| ASM-017 | Submitted content routinely contains live sensitive data — OTPs, account numbers, VPAs, names. It must be treated as sensitive from ingest, before any classification decision. | HIGH | Privacy exposure and log leakage | Standing (NFR-007) |
| ASM-018 | Analysis latency budget is seconds, not milliseconds — users submit after the fact (see ASM-007). | MEDIUM | Architecture may need async/streaming earlier than planned | ASM-001 / ASM-007 resolution |
| ASM-019 | During development, rule authoring and approval are performed by the same person. Separation of duties is modelled in the system but not enforced organisationally. | HIGH | No technical impact; the *workflow* is still built and tested with distinct roles | Standing while team size is 1 |

---

## Load-bearing assumptions

Three entries carry disproportionate weight. If any proves false, downstream rework is
significant:

1. **ASM-001** (no stakeholder access) — invalidates the requirement set's grounding
2. **ASM-015** (DPDP applicability) — unverified legal position affecting privacy architecture
3. ~~**ASM-016** (source reachability)~~ — **resolved, and it broke.** Phase 1 gated `PARTIAL` as a
   direct consequence. Recorded here as evidence that the register is doing its job: the
   assumption was stated in advance, tested, disproved, and its cost accepted openly rather than
   discovered late.

## Change history

| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-07-31 | Register opened with 19 assumptions recorded during Phase 0. | Technical Program Director |
| 1.1 | 2026-08-14 | ASM-016 closed as **disproved** at the Phase 1 gate ([GATE-001](GATE-001-phase-1-assessment.md)) and restated as a standing operating condition. 18 assumptions remain open. | Technical Program Director |
