# Decision Log

| Field | Value |
|---|---|
| Document ID | REG-DECISION |
| Version | 1.0 |
| Status | Active |
| Owner role | Technical Program Director |
| Last updated | 2026-08-28 |

Programme-level decisions. **Architecture** decisions live as numbered ADRs in
[`adr/`](../../adr/README.md); this log records scope, process and evidence-policy decisions,
and points to the ADR where one exists.

Per `MP §20`, each entry states the decision, constraints, alternatives, justification,
consequences and reversal cost.

---

## DEC-001 — Execute the full programme at specified depth

| | |
|---|---|
| **Date** | 2026-07-31 |
| **Decided by** | Sponsor |
| **Status** | Accepted |
| **Related** | [CONF-008](conflict-register.md), [RSK-005](risk-register.md) |

**Decision.** Deliver all ~20 canonical artifacts at the depth described in the master prompt,
following its phase structure.

**Constraints.** One engineer plus AI assistance ([ASM-012](assumption-register.md)); no fixed
end date ([ASM-009](assumption-register.md)).

**Alternatives considered.**
- *Depth-first MVP* — full rigour on Phases 0–3 plus a working engine; Phases 4–10 lighter.
  Recommended by the programme.
- *Documentation only* — all specs, no implementation. Rejected: nothing would ever be validated
  by running code.

**Justification.** The concern that this scope exceeds a solo delivery capacity was raised
explicitly *before* work began. The sponsor reviewed it and chose full depth. That is the
sponsor's call to make.

**Consequences.** Long programme. Elevated risk of pressure toward unevidenced completion
claims, which `MP §3` forbids — managed by forecasting gate shortfalls in advance rather than
discovering them at the gate. Phase 0 and Phase 1 are already forecast as `PARTIAL`.

**Reversal cost.** Low at any point — scope can be narrowed later without discarding completed
artifacts.

---

## DEC-002 — Java + React first; defer the Python intelligence service

| | |
|---|---|
| **Date** | 2026-07-31 |
| **Decided by** | Sponsor |
| **Status** | Accepted |
| **Related** | [ADR-0002](../../adr/ADR-0002-defer-python-intelligence-service.md), CON-008 |

**Decision.** Build the core on Java 21 + Spring Boot with a React/TypeScript frontend. The
Python FastAPI intelligence service remains in the target architecture but is **not built until
the AI phase**.

**Justification.** The master prompt's own implementation sequence (`MP §15`) places AI-assisted
capability at step 10, behind feature flags, *after* deterministic foundations are stable.
Slices 1–9 therefore have no dependency on the Python service. Standing it up early would add a
second runtime, a second CI pipeline and a network boundary to maintain, for zero delivered
capability.

**Consequences.** Fewer moving parts through the deterministic build-out. This is **sequencing,
not architectural deviation** — the end-state architecture is unchanged.

**Reversal cost.** Very low; the service is additive.

---

## DEC-003 — Verify primary sources before encoding any rule

| | |
|---|---|
| **Date** | 2026-07-31 |
| **Decided by** | Sponsor |
| **Status** | Accepted |
| **Related** | [CONF-006](conflict-register.md), [RSK-001](risk-register.md), [ASM-016](assumption-register.md) |

**Decision.** Phase 1 begins with a source verification pass. Every source in RESEARCH-001
carries a `verification_status` from the [glossary grading scale](glossary.md#3-evidence-and-provenance-grades).
No claim reaches `PRIMARY_VERIFIED` without being located in the issuing body's own document.

**Alternatives considered.**
- *Encode as-is, mark everything unverified* — faster, but Phase 1's gate could only ever report
  `PARTIAL`, and unverified attribution would propagate into user-facing output.
- *Encode only what verifies* — strictest, but would likely cut the rule set well below 27 and
  discard real coverage.

**Justification.** `MP §8`'s gate demands traceability and forbids fabricated citations. The
research package itself recommends exactly this second pass (`RP p.13`).

**Consequences.** Phase 1 takes materially longer. Some retrievals will fail
([ASM-016](assumption-register.md)); failures are logged as gap entries rather than treated as
blockers. Strip `utm_source` parameters and snapshot hashes on retrieval.

**Reversal cost.** N/A — verification, once done, is a durable asset.

---

## DEC-004 — Follow the master prompt's phase order; do not pull the walking skeleton forward

| | |
|---|---|
| **Date** | 2026-07-31 |
| **Decided by** | Sponsor (by implication of DEC-001) |
| **Status** | Accepted — **revisitable** |

**Decision.** Complete specification Phases 0–8 before implementation begins, per `MP §6`.

**Context.** The programme recommended pulling the walking skeleton (submit text → persist → run
one validated rule → return explanation → render) forward to immediately after DET-001, so the
rule schema is proven by working code before a further dozen documents are written against it.
The sponsor selected full specified depth, which implies the prompt's stated ordering.

**Consequences.** UX-001 through PRR-001 are written against a rule schema that has not yet been
executed. If the schema proves unworkable in Phase 9, rework propagates backwards through
several artifacts.

**Mitigation.** KB-001 will ship with a machine-validatable JSON Schema plus worked example
rules that are *validated by an actual schema validator* during Phase 2, rather than only
prose-reviewed. That is not a running engine, but it catches the largest class of schema defect
early.

**Reversal cost.** Low, and it decreases the earlier it is revisited. Flagged for reconsideration
at the Phase 3 → Phase 4 boundary.

---

## DEC-005 — Neutral rule identifiers, sources carried as data

| | |
|---|---|
| **Date** | 2026-07-31 |
| **Decided by** | Programme (engineering decision) |
| **Status** | Accepted — **sponsor confirmation invited, not required** |
| **Related** | [CONF-005](conflict-register.md) |

**Decision.** Rules are identified as `TL-<domain>-<nnn>` (e.g. `TL-KYC-006`), not by
source-branded identifiers (`HDFC-KYC-006`). The research package's identifier is retained as
`legacy_id`. Sources move into a `source_references[]` array carrying issuing body, authority
level, document reference and verification status.

**Justification.** Embedding a commercial brand in a canonical identifier conflates issuing body
with rule ownership, ties the taxonomy to one private company, and breaks when a source is
superseded. `MP §3` requires source mappings to be versioned data, not hardcoded. It also
prevents the subtler error of treating a commercial bank's guidance as carrying regulatory
authority.

**Consequences.** A one-time mapping table from `RP` identifiers to TrustLens identifiers must
be maintained for traceability back to the research package.

**Reversal cost.** Low if done before Phase 2 encoding; high afterwards — which is why it is
decided now.

---

## DEC-006 — Evidence hierarchy admitting official-alternate and replacement provenance

| | |
|---|---|
| **Date** | 2026-08-28 |
| **Decided by** | Programme (evidence-policy decision) |
| **Status** | Accepted |
| **Related** | [ADR-0015](../../adr/ADR-0015-evidence-hierarchy-and-official-alternate-provenance.md), [DEC-003](#dec-003--verify-primary-sources-before-encoding-any-rule), [CONF-005](conflict-register.md), [RESEARCH-006](../01-research/RESEARCH-006-manual-retrieval-reconciliation.md) |

**Decision.** The manual retrieval pass ([RESEARCH-006](../01-research/RESEARCH-006-manual-retrieval-reconciliation.md))
produced evidence that the binary `DEC-003` grading cannot describe. TrustLens adopts a **five-class
evidence hierarchy** — `PRIMARY`, `OFFICIAL_ALTERNATE`, `OFFICIAL_REPLACEMENT`, `INDUSTRY`,
`SECONDARY` — recorded **additively** on the verification manifest without altering any automated
`status`. Architectural mechanism, schema and linter enforcement are specified in
[ADR-0015](../../adr/ADR-0015-evidence-hierarchy-and-official-alternate-provenance.md).

An `OFFICIAL_ALTERNATE` source (an issuing body's own official channel/social-media publication,
e.g. I4C CyberDost) may support a **published** rule only when all seven conditions hold:
official channel identity established; archived evidence retained; canonical URL and retrieval date
recorded; SHA-256 recorded; exact supporting claim located; rule wording does not exceed the source;
human review recorded. `OFFICIAL_ALTERNATE` and `INDUSTRY` evidence cap a rule at `PARTIAL`.

**Alternatives considered.** Promote channel posts to `PRIMARY_VERIFIED` (rejected — destroys the
meaning of `DEC-003`); discard all non-PDF evidence (rejected — wastes genuine official evidence and
needlessly strands five sound rules).

**Justification.** `MP §3`'s evidence-first principle requires that evidence quality change behaviour
rather than merely be documented. A hierarchy with caps does exactly that while keeping
`PRIMARY_VERIFIED` honest.

**Consequences.** TL-PAY-002 / TL-AUTH-003 reach `SUPPORTED` on manual PRIMARY evidence; TL-JOB-003
on `OFFICIAL_REPLACEMENT` PRIMARY documents; TL-MAL-002 / TL-CRYP-001 reach `PARTIAL` (capped) on
`OFFICIAL_ALTERNATE` evidence; TL-MAL-003 reaches `PARTIAL` (capped) on `INDUSTRY` evidence. No rule
auto-publishes; all existing rule-QA gates still apply.

**Reversal cost.** Low — the classes are data and two linter checks.

---

## DEC-007 — Sextortion in the taxonomy; detection deferred for safeguarding

| | |
|---|---|
| **Date** | 2026-08-28 |
| **Decided by** | Programme (scope + evidence-policy decision) |
| **Status** | Accepted |
| **Related** | [RESEARCH-002 §6.3](../01-research/RESEARCH-002-scam-taxonomy.md), [G-10](../01-research/RESEARCH-005-gap-register.md), [KB-001](../02-knowledge/KB-001-knowledge-governance.md) |

**Decision.** Add sextortion to the taxonomy as `TAX-11` (category existence `PRIMARY_VERIFIED` via
SRC-007 / Chakshu), but author **no executable detection rule** in the MVP —
`detection_status: DEFERRED_SAFEGUARDING`.

**Justification.** The source verifies the *category*, not a modus operandi (unlike SRC-012 for digital
arrest). More importantly, a submitted sextortion message is frequently a victim in acute distress; a
fraud score is the wrong response and risks harm. Detection needs a safeguarding/referral design that is
out of MVP scope. Including the category keeps the taxonomy nationally complete without manufacturing
unsafe detection (MP §3, §21).

**Alternatives considered.** Build a sextortion rule now (rejected — unsafe, weak modus-operandi
evidence); scope sextortion out entirely (rejected — it is an official, nationally-recognised category).

**Consequences.** `validate_taxonomy.py` fails any rule authored on `TAX-11`. G-10 moves from open to
"taxonomy resolved, detection deferred". A future increment must design safeguarding-aware handling.

**Reversal cost.** Low — the category is data; a future rule can be added once safeguarding is designed.

---

## DEC-008 — MVP language scope: English only (OI-04 resolved)

| | |
|---|---|
| **Date** | 2026-08-29 |
| **Decided by** | **Sponsor** (OI-04 is an explicit owner decision) |
| **Status** | Accepted |
| **Related** | [OI-04](PROGRAM-001-program-charter.md#11-open-issues), [CONF-004](conflict-register.md), [G-08](../01-research/RESEARCH-005-gap-register.md), [ADR-0014](../../adr/ADR-0014-language-and-script-strategy.md) |

**Decision.** MVP **detection** supports **English (`en` / `Latn`) only** — CONF-004 pre-registered
resolution **(a)**. The knowledge schemas remain language/script-extensible; non-English input is
explicitly flagged `UNSUPPORTED` (NFR-009), never silently scored. The multilingual claim (`MP §1`) is
**roadmapped**, not shipped.

**Justification.** No verified official source supplies non-English cues ([G-08](../01-research/RESEARCH-005-gap-register.md)),
so any non-English rule would be `HEURISTIC` and un-publishable (RESEARCH-004 §7) without a dedicated
research pass. Option A is the only choice consistent with the current evidence and requires **zero**
engineering change — the language-extensible posture (rule `language_scope`, envelope language/script,
seed case A-006's `UNSUPPORTED` flag) already implements it.

**Consequences.** Resolves OI-04 and CONF-004; Accepts ADR-0014 at English-only scope; **unblocks Phase-2
closure**. G-08 persists as **future, non-blocking** research (verified non-English cues). Widening scope
later (Hindi or other Indian languages) is a **data change** gated by a verified-cue research pass.

**Reversal cost.** Low — schemas already carry language/script; adding a language is additive data, not a
migration.

---

## Summary

| ID | Decision | Decided by | Status |
|---|---|---|---|
| DEC-001 | Full programme at specified depth | Sponsor | Accepted |
| DEC-002 | Java + React first; Python deferred | Sponsor | Accepted |
| DEC-003 | Verify primary sources before encoding | Sponsor | Accepted |
| DEC-004 | Follow master prompt phase order | Sponsor (implied) | Accepted — revisitable |
| DEC-005 | Neutral rule identifiers | Programme | Accepted |
| DEC-006 | Evidence hierarchy (official-alternate + replacement) | Programme | Accepted |
| DEC-007 | Sextortion in taxonomy; detection deferred (safeguarding) | Programme | Accepted |
| DEC-008 | MVP language scope English-only (OI-04 resolved); schemas stay extensible | Sponsor | Accepted |

## Change history

| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-07-31 | Log opened with five Phase 0 decisions. | Technical Program Director |
| 1.1 | 2026-08-28 | DEC-006 added — evidence hierarchy admitting official-alternate and replacement provenance, arising from the RESEARCH-006 manual retrieval reconciliation. Points to ADR-0015. | Chief Architect |
| 1.2 | 2026-08-28 | DEC-007 added — sextortion added to the taxonomy (TAX-11) with detection deferred for safeguarding (WP5). | Threat Intelligence Lead |
| 1.3 | 2026-08-29 | DEC-008 added — Sponsor resolved OI-04: MVP language scope is English-only (CONF-004 option a); schemas stay language/script-extensible. Accepts ADR-0014; unblocks Phase-2 closure. | Technical Program Director |
