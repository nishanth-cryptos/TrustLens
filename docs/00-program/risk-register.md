# Risk Register

| Field | Value |
|---|---|
| Document ID | REG-RISK |
| Version | 1.0 |
| Status | Active |
| Owner role | Technical Program Director / Principal Security Engineer |
| Last updated | 2026-07-31 |

Scoring: Likelihood (L) and Impact (I) each `1–5`; Score = L × I.
🔴 ≥ 15 · 🟠 8–14 · 🟡 4–7 · 🟢 ≤ 3.

---

## Programme and delivery risks

| ID | Risk | L | I | Score | Mitigation | Owner |
|---|---|---|---|---|---|---|
| **RSK-005** | **Scope exceeds capacity.** ~20 artifacts, four runtimes and a PRR against one engineer. Failure mode is not slow delivery but *pressure to declare completion without evidence* — explicitly forbidden by `MP §3`. | 4 | 5 | 🔴 **20** | Sponsor chose full depth knowingly ([DEC-001](decision-log.md)). Managed by honest gate reporting: forecast shortfalls **before** the gate, never mark `PASS` without evidence, keep artifacts small and dependency-ordered. | Program Director |
| RSK-016 | **Bus factor of one.** All programme context sits with one engineer plus session memory. | 3 | 4 | 🟠 12 | Everything durable is written to versioned artifacts, not held in conversation. Registers and ADRs are the recovery mechanism. | Program Director |
| RSK-006 | **Docker and PostgreSQL absent.** Blocks Phase 9 implementation and Testcontainers integration tests. | 5 | 3 | 🔴 **15** | Specification phases 0–8 proceed unimpeded. Sponsor admin install required before Phase 9 ([OI-02](PROGRAM-001-program-charter.md#11-open-issues)). Raise again as Phase 8 completes. | Sponsor / DevSecOps |
| RSK-007 | **Bleeding-edge runtimes.** Node 26 and Python 3.14 may outpace library support (OCR, ML, tooling). | 3 | 3 | 🟡 9 | Pin versions in CI. Prefer mature libraries. Python is deferred anyway ([DEC-002](decision-log.md)), buying time. | DevSecOps |

## Evidence and knowledge risks

| ID | Risk | L | I | Score | Mitigation | Owner |
|---|---|---|---|---|---|---|
| **RSK-003** | **No labelled corpus exists, and none is obtainable.** Precision, recall, calibration and false-positive rate cannot be measured. Any accuracy claim would violate `MP §17`/`§21`. | 5 | 4 | 🔴 **20** | Accept and disclose. Synthetic corpus proves *determinism and regression only*. PROGRAM-001 §7.2 states this; PRR-001 will report it as an unclosable gap. Never publish an accuracy figure. | QA Lead |
| **RSK-001** | **Primary source verification fails.** Government advisory PDFs are inconsistently fetchable — the research package says so itself (`RP p.13`). | 4 | 3 | 🟠 **12** | Attempt all ~26 URLs; log every outcome. Failures become `INDEX_ONLY`/`PRIMARY_CITED_UNVERIFIED` grades and RESEARCH-005 gap entries, not blockers. Snapshot and hash whatever *is* retrieved. | Threat Intelligence Lead |
| RSK-013 | **Link rot / advisory churn.** Cited documents move, change or disappear, breaking traceability after the fact. | 4 | 3 | 🟠 12 | Snapshot content hash and retrieval date at verification time. Rules carry `last_reviewed` and `review_due` dates. Periodic re-verification is an OPS-001 runbook. | Threat Intelligence Lead |
| RSK-004 | **Multilingual gap.** Product claims multilingual; knowledge base is 100% English ([CONF-004](conflict-register.md)). | 5 | 3 | 🔴 **15** | Make the limitation explicit rather than silent (NFR-009). Make language/script a first-class rule-schema dimension so cue sets are additive. Sponsor decision pending on OI-04. | Chief Architect |
| RSK-015 | **OCR quality for Indian scripts** is unproven; screenshots are a primary submission modality. | 4 | 3 | 🟠 12 | Deferred to Post-MVP. Evidence-quality scoring must reflect OCR confidence so poor extraction lowers confidence rather than silently corrupting findings. | ML/AI Architect |

## Detection quality risks

| ID | Risk | L | I | Score | Mitigation | Owner |
|---|---|---|---|---|---|---|
| **RSK-002** | **False positives from literal keyword rules.** Flagging a bank's own anti-fraud SMS would actively harm users by training them to ignore warnings ([CONF-002](conflict-register.md)). | 4 | 5 | 🔴 **20** | Three-layer architecture: unscored indicators → composite rules → negative indicators and suppression. Schema lint rejects single-weak-indicator rules. Benign regression corpus authored **first**. | Chief Architect / QA Lead |
| RSK-014 | **Users treat output as an official determination** or as legal advice, and act on it in a legal context. | 3 | 4 | 🟠 12 | Prominent, non-dismissable disclaimer (FR-055). UX reviewed for dark patterns. Separate risk from confidence so uncertainty is visible (`MP §14`). | UX / Program Director |
| RSK-009 | **False negatives on novel scams.** A deterministic rule engine cannot detect a pattern nobody has encoded. | 4 | 4 | 🟠 16 | Never present "no finding" as "safe" — return `INSUFFICIENT_EVIDENCE` with guidance (FR-035). Weak-signal clustering for analyst review is Future scope. | Chief Architect |

## Security and privacy risks

| ID | Risk | L | I | Score | Mitigation | Owner |
|---|---|---|---|---|---|---|
| RSK-008 | **Prompt injection via submitted content.** Every input is by definition attacker-authored; scam text reaching an AI component is a direct injection vector. | 4 | 4 | 🟠 16 | Structural isolation of content from instructions; strict output schemas; AI never authoritative (CON-003); AI behind feature flags. Designed in AI-001, threat-modelled in ARCH-001. | Principal Security Engineer |
| RSK-010 | **Sensitive data exposure.** Submissions routinely contain live OTPs, account numbers and VPAs ([ASM-017](assumption-register.md)); leakage via logs, errors or reports is a real path. | 4 | 5 | 🔴 **20** | Treat all content as sensitive from ingest. Redaction before logging; no raw evidence in logs or error responses (NFR-007, `MP §21`); encryption at rest; automated leak scanning in CI. | Principal Security Engineer |
| RSK-011 | **Evidence integrity failure.** If chain of custody is weak, the report bundle is worthless for its actual purpose. | 3 | 5 | 🟠 15 | Hash on ingest, immutable evidence records, tamper-evident audit log, reproducibility test (FR-053) as a hard acceptance criterion. | Data Architect |
| RSK-012 | **Rule poisoning.** A malicious or careless rule change silently degrades detection or suppresses true positives. | 2 | 5 | 🟠 10 | Governed lifecycle with separated author/approver roles (FR-023), schema validation, regression suite on every publish, versioned rollback (FR-026), full audit. Human approval mandatory for AI-suggested rules (FR-075). | Knowledge Approver |
| RSK-017 | **Malicious upload.** Screenshot ingestion is an attack surface — malformed images, embedded payloads, decompression bombs. | 3 | 4 | 🟠 12 | File-type verification beyond extension, size and dimension limits, processing isolation, no dynamic execution of submitted content (`MP §16`). Post-MVP alongside FR-004. | Principal Security Engineer |
| RSK-018 | **External provider dependency.** Threat-intelligence adapters introduce availability, quota and terms-of-use exposure. | 3 | 2 | 🟡 6 | Architecture functions without any single provider (FR-071). Circuit breakers, caching, graceful degradation. Provider disagreement handled explicitly in INT-001. | Chief Architect |

---

## Top risks by score

| Rank | ID | Risk | Score |
|---|---|---|---|
| =1 | RSK-005 | Scope exceeds capacity | 🔴 20 |
| =1 | RSK-003 | No labelled corpus — accuracy unprovable | 🔴 20 |
| =1 | RSK-002 | False positives from literal keyword rules | 🔴 20 |
| =1 | RSK-010 | Sensitive data exposure | 🔴 20 |
| 5 | RSK-009 | False negatives on novel scams | 🟠 16 |
| =5 | RSK-008 | Prompt injection via submitted content | 🟠 16 |

Three of the top four are **inherent to the problem domain** rather than to this programme's
execution, and are managed by disclosure and design rather than eliminated. RSK-002 is the one
squarely within our control, and it drives the core detection architecture.

## Change history

| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-07-31 | Register opened with 18 risks identified during Phase 0. | Technical Program Director |
