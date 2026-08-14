# Conflict Register

| Field | Value |
|---|---|
| Document ID | REG-CONFLICT |
| Version | 1.0 |
| Status | Active |
| Owner role | Chief Architect |
| Last updated | 2026-07-31 |

Per `MP §2`: contradictions are never silently reconciled. Each is recorded with its sources,
impact, proposed resolution and whether sponsor approval is required.

**Status values:** `OPEN` · `RESOLVED-PROPOSED` (resolution decided by the programme, reversible)
· `RESOLVED-APPROVED` (sponsor decided) · `CLOSED`.

---

## CONF-001 — Single risk score vs. separated decision quantities

| | |
|---|---|
| **Status** | `RESOLVED-PROPOSED` |
| **Raised** | 2026-07-31, Phase 0 |
| **Sources in conflict** | `RP p.6–12` (30 rules each carrying one "Risk / confidence" value, e.g. `95 / High`, `99 / High`) vs `MP §10`: *"Design and mathematically specify distinct concepts for risk, confidence, severity, evidence quality, signal strength and trust. **Do not collapse all concepts into one arbitrary percentage.**"* |

**The conflict.** The research package hands us a single 0–100 number plus a coarse
High/Medium label per rule. The master prompt explicitly forbids that representation.

**Compounding problem — false precision.** The scores distinguish 95, 96, 97, 98 and 99. There
is no evidentiary basis for one-point granularity; no cited source publishes numeric scores at
all. The research package concedes this itself (`RP p.6`): these are *"implementation-ready
research judgments… **not** official numeric scores published by the agencies themselves."*
Encoding them as-is would manufacture precision the evidence cannot carry — a form of hiding
uncertainty behind a polished number (`MP §21`).

**Impact.** Blocks KB-001 (rule schema field design) and DET-001 (scoring model). If unresolved,
every rule inherits an unjustifiable number that then propagates into user-facing output.

**Proposed resolution.**
1. Do **not** encode the 0–100 values as risk.
2. Map them to the **severity ordinal** `LOW | MEDIUM | HIGH | CRITICAL` using the research's own
   three-tier harm rationale (`RP p.12–13`): credential requests, payment authorisation under
   false pretences, device-linking/remote-control, and law-enforcement extortion are `CRITICAL`;
   deposits, guaranteed returns, fake job and customer-care funnels, wallet connections are
   `HIGH`; uncorroborated urgency, shortened links and authority claims without a payment step
   are `MEDIUM`.
3. Preserve the original numbers in the rule record as `source_severity_hint` — provenance, not
   an operational value.
4. Derive **risk** at evaluation time from severity × matched-evidence strength; derive
   **confidence** independently from extraction quality and corroboration breadth.

**Approval required:** No — this implements `MP §10` as written. Recorded for visibility.

---

## CONF-002 — Starter rules are keyword matchers, contradicting both the master prompt and the research package's own conclusion

| | |
|---|---|
| **Status** | `RESOLVED-PROPOSED` |
| **Raised** | 2026-07-31, Phase 0 |
| **Severity** | **Highest in the register.** Determines whether TrustLens is credible or a demo. |
| **Sources in conflict** | `RP p.6–12` (rules specified as single-trigger keyword lists) vs `MP §1` (*"not a generic keyword classifier"*), `MP §21` (*"Do not hardcode dozens of untraceable keyword rules and call them threat intelligence"*), **and `RP p.13` itself** (*"the engine should not merely search for words like 'OTP' or 'KYC'… One weak indicator such as urgency should not be enough on its own"*) |

**The conflict.** The research package's rule *table* and its own *conclusion* disagree. The
table specifies rules as keyword triggers; the conclusion states detection must be
combinational. Implemented as tabulated, the rules produce catastrophic false positives.

**Worked failure case.** `RBI-OTP-001` triggers on `OTP, one-time password, share code,
verification code` at `95 / High`. That fires on:

> *"Your OTP is 452901. Never share it with anyone. — HDFC Bank"*

This is a **bank's own anti-fraud message**. TrustLens would flag legitimate security
infrastructure as a critical scam. The same failure recurs across `HDFC-KYC-006` (banks do
legitimately reference KYC), `SEBI-RET-017`, `I4C-JOB-020` and `CERT-JOB-029`.

The discriminating feature is **directionality and intent** — does the message *request* the
secret, or *deliver* it with a warning? That is not expressible as keyword presence.

**Impact.** Determines the core architecture of KB-001 and DET-001. Also determines user trust:
a tool that flags a bank's own OTP message teaches users to ignore it, causing net harm.

**Proposed resolution.** A three-layer separation, which the research package's conclusion
already supports:

1. **Indicator extractors** — high-recall, cheap, *carry no score*. `OTP_MENTIONED` is an
   observation, not a finding.
2. **Composite rules** — require combinations across distinct evidence classes. The research's
   own attack chains (`RP p.12`) supply the template: *pretext + pressure + identity claim +
   payment action + device behaviour*. A rule firing on one weak indicator alone is a schema
   violation, enforced by lint.
3. **Negative indicators and suppression** — `SELF_PROTECTIVE_WARNING` ("never share this",
   "we will never ask"), known-sender context, and legitimate-workflow recognition actively
   reduce risk or suppress a rule (FR-016, FR-032, FR-038).

**Consequence for Phase 1.** The benign corpus must be authored **first** and must include the
legitimate-OTP case above. These are the programme's highest-value regression tests.

**Approval required:** No — this implements `MP §1/§21` and `RP p.13`. Recorded because it
materially reinterprets the supplied rule table.

---

## CONF-003 — Rules requiring evidence TrustLens cannot observe

| | |
|---|---|
| **Status** | `RESOLVED-PROPOSED` |
| **Raised** | 2026-07-31, Phase 0 |
| **Sources in conflict** | `RP p.7, p.11–12` (rules requiring device or live-transaction context) vs `MP §1` (TrustLens analyses *submitted artifacts*) and NG-05 (not a device agent) |

**The conflict.** TrustLens ingests SMS/chat text, email, URLs and screenshots submitted after
the fact. It does not run on the device, does not observe network state, and is not inside the
payment flow. Some starter rules assume evidence from those positions.

| Rule | Requires | Verdict |
|---|---|---|
| `RBI-WIFI-030` | Live network context during a banking session | ❌ **Not implementable** |
| `HDFC-CARE-009` | Knowledge of how the user obtained a phone number | ❌ **Not implementable as specified** |
| `CERT-QR-005` | Live merchant/payee identity resolution in a payment flow | ❌ **Not implementable as specified** |
| `I4C-ACCESS-027` | Device permission state | ⚠️ **Partial** — detectable when *requested in a message* |
| `I4C-TASK-022` | Multi-step app behaviour over time | ⚠️ **Partial** — detectable from conversation narrative |

**Impact.** Rule coverage drops from 30 to **27 implementable**, of which 2 are partial. SM-10
in PROGRAM-001 is set accordingly. Attempting these anyway would mean shipping rules that can
never fire — dead knowledge presented as coverage.

> **Phase 1 update (2026-08-14).** Implementability is only one of the two filters. The
> [evidence matrix](../01-research/RESEARCH-004-evidence-matrix.md) applied the second — evidential
> support — and **18** of the 27 survive both. The charter now separates the two counts as SM-10
> (encoded, 27) and SM-11 (published, 18); see [GATE-001](GATE-001-phase-1-assessment.md) §4.2.
> Note that `CERT-QR-005`/`TL-PAY-003` and `RBI-WIFI-030`/`TL-CTX-001` are *well-evidenced but
> unobservable* — the two filters are genuinely independent.

**Proposed resolution.** Record all five in the Phase 1 research-gap register (RESEARCH-005)
with explicit reason codes. Encode the three unimplementable rules as `status: DEFERRED` in the
knowledge base with a `blocked_by: INPUT_MODALITY` field, so the knowledge is retained and
becomes live if TrustLens ever gains a device-side component. Reframe the two partials to
operate on *described* behaviour rather than *observed* state, and note the narrowing explicitly.

**Approval required:** No. Recorded as a scope reduction against the supplied rule set.

---

## CONF-004 — "Multilingual" product claim vs. an entirely English knowledge base

| | |
|---|---|
| **Status** | `OPEN` — needs sponsor decision |
| **Raised** | 2026-07-31, Phase 0 |
| **Sources in conflict** | `MP §1` (*"Indian, explainable, **multilingual** digital-scam detection"*), `MP §11` (*"major Indian-language scenarios"*) vs `RP p.5–12` — **every trigger cue in all 30 rules is English** |

**The conflict.** Multilingual support is a headline product claim with no supporting knowledge
behind it. The research package contains zero Devanagari, Tamil, Telugu, Bengali or Marathi
content, and does not address transliterated code-mixing — the register in which a great deal of
Indian scam messaging actually arrives ("OTP bhejo", "PIN daal do", "urgent paisa transfer karo").

**Impact.** A user submitting a Hindi or Hinglish scam message would receive
`INSUFFICIENT_EVIDENCE` — technically honest, but a product that fails its stated core audience.

**Proposed resolution (needs approval).** Make the limitation explicit rather than silent
(NFR-009): the system declares which languages it supports and flags unsupported input, instead
of quietly returning a low score. Then choose a path:

- **(a)** English-only MVP, multilingual architecture proven by making script/language a
  first-class rule-schema dimension, with cue sets added later — *recommended, lowest risk*
- **(b)** Add Hindi + Hinglish cue sets in Phase 1, accepting that these would be **unsourced
  heuristics** (`HEURISTIC` grade), since no cited advisory supplies non-English cues
- **(c)** Drop the multilingual claim from the product vision until it can be substantiated

**Approval required:** **Yes.** Tracked as [OI-04](PROGRAM-001-program-charter.md#11-open-issues).

---

## CONF-005 — Commercial sources treated as authoritative, and brand names embedded in rule identifiers

| | |
|---|---|
| **Status** | `RESOLVED-PROPOSED` |
| **Raised** | 2026-07-31, Phase 0 |
| **Sources in conflict** | `RP p.7–11` (5 rules prefixed `HDFC-`; `RP p.2` ranks "Official bank fraud pages" as `High` priority) vs `MP §8` (official sources enumerated as CERT-In, RBI, NPCI, I4C/NCRP, MeitY, DoT, Sanchar Saathi — **no commercial banks**) |

**The conflict — two distinct problems.**

1. **Evidence weight.** HDFC Bank is a commercial institution. Its customer-education pages are
   useful corroboration but carry no regulatory authority. `MP §8`'s official-source list does
   not include commercial banks. Rules resting *solely* on HDFC guidance are weaker than their
   presentation suggests. The same applies to Google, Meta and Microsoft (`RP p.2`, ranked
   `Medium`).
2. **Design.** Baking a private company's brand into a canonical rule identifier is wrong
   irrespective of evidence weight: it conflates *issuing body* with *rule ownership*, ties the
   taxonomy to one commercial brand, and breaks if the source is superseded. `MP §3` requires
   sources to be versioned data, not hardcoded.

**Impact.** Affects the rule identifier scheme in KB-001 and source grading in RESEARCH-001.

**Proposed resolution.**
1. Re-key all rules to neutral identifiers: `TL-<domain>-<nnn>` (e.g. `TL-KYC-006`). Retain the
   research-package ID as `legacy_id` for traceability back to `RP`.
2. Carry sources as **data** in a `source_references[]` array, each with issuing body, authority
   level (`OFFICIAL_REGULATOR` / `OFFICIAL_GOVERNMENT` / `INDUSTRY` / `FOREIGN_OFFICIAL`),
   document reference and `verification_status`.
3. Where a rule rests solely on `INDUSTRY` sources, seek an official corroborating source in
   Phase 1; if none is found, cap its severity contribution and mark it accordingly.

**Approval required:** No — engineering decision, low reversal cost. See [DEC-005](decision-log.md).

---

## CONF-006 — Secondary research vs. the requirement for official-source traceability

| | |
|---|---|
| **Status** | `RESOLVED-APPROVED` |
| **Raised** | 2026-07-31, Phase 0 |
| **Sources in conflict** | The supplied research package is a ChatGPT synthesis of primary sources (BASELINE-001 §3.2) vs `MP §8` gate: *"Every official-source-derived fact must be traceable… **No fabricated citations are permitted**"* |

**The conflict.** The package attributes specific claims to official bodies, but 14 of 72
citation markers (~19%) resolve to index or home pages rather than documents, and **no claim has
been verified against a primary source**. Encoding it as-is would present unverified secondary
attribution as official fact.

**Impact.** Gates the entire Phase 1 quality gate.

**Resolution — approved by sponsor 2026-07-31 ([DEC-003](decision-log.md)).** Perform a primary
verification pass before encoding. Every source carries `verification_status` from the
[glossary](glossary.md#3-evidence-and-provenance-grades) grading scale. Claims that verify only
to an index page are graded `INDEX_ONLY` and may not alone support a rule. Retrieval failures
are logged honestly and do not block the phase — they become RESEARCH-005 gap entries.

---

## CONF-007 — The master prompt assumes an existing repository; none exists

| | |
|---|---|
| **Status** | `CLOSED` |
| **Raised** | 2026-07-31, Phase 0 |
| **Sources in conflict** | `MP §2` (*"recursively inspect the complete repository"*), `MP "How to Use"` (references a kickoff package and memory-bank documents) vs an empty working directory |

**Impact.** Precedence levels 4 and 5 (`MP §2`) are empty, so engineering inference — level 6 —
carries far more weight than the model intends. This is the structural reason Phase 0 reports
`PARTIAL` rather than `PASS`.

**Resolution.** Treat the programme as greenfield. BASELINE-001 records the starting position
instead of assessing an inheritance. Every inferred requirement is tagged `DERIVED` and
inherits [ASM-001](assumption-register.md). No further action; recorded for audit.

---

## CONF-008 — Programme scope vs. delivery capacity

| | |
|---|---|
| **Status** | `RESOLVED-APPROVED` |
| **Raised** | 2026-07-31, before Phase 0 work began |
| **Sources in conflict** | `MP` overall (~20 versioned artifacts, four runtimes, full test pyramid, production readiness review) vs one engineer plus AI assistance, on an internship timeline ([ASM-012](assumption-register.md)) |

**The conflict.** The programme as specified is a multi-team, multi-quarter workload. Delivering
all of it at the specified depth carries a real risk of either abandonment or — worse, and
explicitly forbidden by `MP §3` — declaring completion without acceptance criteria, tests or
traceability.

**Resolution — sponsor decided 2026-07-31 ([DEC-001](decision-log.md)).** The concern was raised
before work began; the sponsor reviewed it and chose **full programme at specified depth**. That
is settled and will not be re-litigated.

**Standing mitigation.** Because the risk is capacity rather than direction, it is managed
through honest gate reporting: no phase is marked `PASS` without evidence, and forecast
shortfalls are stated in advance rather than discovered at the gate. Tracked as
[RSK-005](risk-register.md).

---

## Summary

| ID | Conflict | Status | Approval needed |
|---|---|---|---|
| CONF-001 | Single risk score vs separated quantities | `RESOLVED-PROPOSED` | No |
| CONF-002 | Keyword rules vs combinational detection | `RESOLVED-PROPOSED` | No |
| CONF-003 | Rules requiring unobservable evidence | `RESOLVED-PROPOSED` | No |
| **CONF-004** | **Multilingual claim vs English-only knowledge** | **`OPEN`** | **Yes — OI-04** |
| CONF-005 | Commercial sources as authoritative; brand in rule IDs | `RESOLVED-PROPOSED` | No |
| CONF-006 | Secondary research vs official traceability | `RESOLVED-APPROVED` | Done — DEC-003 |
| CONF-007 | Assumed repository does not exist | `CLOSED` | No |
| CONF-008 | Scope vs capacity | `RESOLVED-APPROVED` | Done — DEC-001 |

**One conflict requires a sponsor decision: CONF-004.**

## Change history

| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-07-31 | Register opened with 8 conflicts identified during Phase 0 input analysis. | Chief Architect |
