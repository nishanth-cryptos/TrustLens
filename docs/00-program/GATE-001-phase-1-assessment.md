# GATE-001 — Phase 1 Quality Gate Assessment

| Field | Value |
|---|---|
| Document ID | GATE-001 |
| Version | 1.0 |
| Status | **Approved** |
| Phase assessed | Phase 1 — Official threat research normalisation |
| Owner role | Technical Program Director |
| Dependencies | PROGRAM-001, [roadmap](roadmap.md), RESEARCH-001…005 |
| Gate forecast | `PARTIAL` ([roadmap](roadmap.md#phase-1--official-threat-research-normalisation-)) |
| **Gate result** | **`PARTIAL` — forecast achieved** |
| Approved by | Programme, under [ASM-019](assumption-register.md) (authoring and approval are the same person at team size 1) |
| Last updated | 2026-08-28 (§7 reconciliation addendum) |

---

## 1. Purpose

`MP §7`'s gate condition for research normalisation: *every official-source-derived fact must be
traceable to its issuing body, and missing or contradictory source material must be visible in the
gap register.* This document records whether that condition holds, with evidence, and states
plainly where it does not.

Gate vocabulary is `PASS` · `PARTIAL` · `BLOCKED` ([glossary §5](glossary.md#5-programme-terms)).

## 2. Deliverables

| Deliverable | Location | State |
|---|---|---|
| RESEARCH-001 Source inventory | [docs/01-research/RESEARCH-001-source-inventory.md](../01-research/RESEARCH-001-source-inventory.md) | ✅ Approved |
| RESEARCH-002 Scam taxonomy | [docs/01-research/RESEARCH-002-scam-taxonomy.md](../01-research/RESEARCH-002-scam-taxonomy.md) | ✅ Approved |
| RESEARCH-003 Advisory extraction | [docs/01-research/RESEARCH-003-advisory-extraction.md](../01-research/RESEARCH-003-advisory-extraction.md) | ✅ Approved |
| RESEARCH-004 Evidence matrix | [docs/01-research/RESEARCH-004-evidence-matrix.md](../01-research/RESEARCH-004-evidence-matrix.md) | ✅ Approved |
| RESEARCH-005 Gap register | [docs/01-research/RESEARCH-005-gap-register.md](../01-research/RESEARCH-005-gap-register.md) | ✅ Approved |
| Source verification manifest | [knowledge/sources/verification-manifest.json](../../knowledge/sources/verification-manifest.json) | ✅ v1.1 |
| Machine-readable taxonomy | [knowledge/taxonomies/scam-taxonomy.json](../../knowledge/taxonomies/scam-taxonomy.json) | ✅ v1.0 |
| Seed corpus | [knowledge/seed-data/seed-corpus-v1.json](../../knowledge/seed-data/seed-corpus-v1.json) | ✅ v1.0 |
| Consistency checker | [knowledge/validation/phase1_consistency_check.py](../../knowledge/validation/phase1_consistency_check.py) | ✅ Added at gate |

All seven work items listed in the roadmap's Phase 1 plan were executed, in the mandated order —
including the requirement that **benign cases be authored first** ([CONF-002](conflict-register.md)).

## 3. Evidence

### 3.1 Automated consistency check

`MP §17` and [DEC-004](decision-log.md) require verification by mechanism, not prose review. The
Phase 1 artifacts are now checked by a runnable script rather than by assertion:

```
$ python3 knowledge/validation/phase1_consistency_check.py
35/35 checks passed
```

It verifies that the three machine-readable files agree with each other and with the counts
asserted in the RESEARCH documents: grade tallies, taxonomy nesting and coverage arithmetic, that
every `SRC-*` cited by the taxonomy resolves in the manifest, that every rule ID referenced by the
seed corpus exists in RESEARCH-004, that every `PRIMARY_VERIFIED` source carries located
quotations, and that **no malicious seed case expects an `UNSUPPORTED` or `DEFERRED` rule to
fire** — the check that stops unevidenced knowledge leaking into the test baseline.

This is a consistency checker, not a schema validator. The rule JSON Schema and its validator are
Phase 2 deliverables (ADR-0003).

### 3.2 Two defects found and fixed at the gate

| # | Defect | Fix |
|---|---|---|
| 1 | The manifest reported `verified_fraction: 12/26 (46%)`, silently counting the one `PRIMARY_CITED_UNVERIFIED` source as verified. RESEARCH-001 §2 states 11 (42%). | Restated as `primary_verified_fraction: 11/26 (42%)` with the exclusion made explicit. Manifest → v1.1. |
| 2 | Seven `RETRIEVAL_FAILED` sources recorded neither `claim_under_test` nor a note — the manifest did not say what those documents were meant to prove, which would have made the G-01/G-03 re-retrieval effort guesswork. | `claim_under_test` and `blocks_rules` added to SRC-013, 015, 018, 019, 022, 024, 025. |

Neither is a fabrication; both are traceability defects of exactly the kind the gate exists to catch.

### 3.3 Gate criteria

| Criterion (`MP §7`, `MP §8`) | Status | Evidence |
|---|---|---|
| Every cited source subjected to a retrieval attempt | ✅ | 26 of 26, two methods where the first failed ([RESEARCH-001 §1](../01-research/RESEARCH-001-source-inventory.md)) |
| Every source carries an evidence grade from the controlled vocabulary | ✅ | Manifest; checker verifies grades against [glossary §3](glossary.md#3-evidence-and-provenance-grades) |
| No claim encoded from an unretrieved document | ✅ | RESEARCH-003 extracts only from `PRIMARY_VERIFIED` sources; 10 advisories, all quoted |
| Every detection concept mapped to a source or explicitly classified | ✅ | All 30 starter rules graded `SUPPORTED`/`PARTIAL`/`UNSUPPORTED` ([RESEARCH-004](../01-research/RESEARCH-004-evidence-matrix.md)) |
| Contradictions between package and source made visible | ✅ | 6 discrepancies D1–D6 recorded, not silently corrected |
| Missing research visible in a gap register | ✅ | 22 gaps in [RESEARCH-005](../01-research/RESEARCH-005-gap-register.md), severity-rated, with closure paths |
| Fact separated from assumption explicitly | ✅ | [RESEARCH-005 §5](../01-research/RESEARCH-005-gap-register.md) — 10 supported facts vs 6 unsupported assumptions |
| Synthetic examples labelled synthetic | ✅ | Corpus `provenance: SYNTHETIC`; checker enforces (CON-005) |
| Seed corpus with benign cases authored first | ✅ | 27 cases: 10 benign, 11 malicious, 6 ambiguous |
| **All cited sources retrievable** | ❌ | **13 of 26 failed.** I4C (5/5) and NPCI (2/2) entirely unreachable |
| **Knowledge base covers the claimed language scope** | ❌ | Zero non-English content (G-08); blocked on [OI-04](PROGRAM-001-program-charter.md#11-open-issues) |
| **Negative indicators available** | ❌ | None exist in the research package (G-07); to be authored in Phase 2 as `HEURISTIC` |

## 4. Result — `PARTIAL`

**The forecast was `PARTIAL` and `PARTIAL` is what was achieved.** This is a predicted shortfall,
not a discovered one.

What holds: every fact carried forward is traceable to a retrieved document with located
quotations, every gap is visible and rated, and no unretrievable claim was promoted into the
knowledge base. The verification pass caught six attribution defects — four of which would have
propagated into user-facing output, including *"RBI says institutions never ask for your UPI-PIN"*,
which [SRC-004](../../knowledge/sources/verification-manifest.json) does not say (D1).

What does not: half the cited source base could not be retrieved, and the failure is structural
rather than transient. `i4c.mha.gov.in`, `pib.gov.in` and `npci.org.in` systematically block
automated retrieval while `cert-in.org.in`, `niti.gov.in` and `rbi.org.in` permit it. A clean
`PASS` was never reachable from this environment.

The outcome is better than the research package's own warning implied, and it is concentrated in
the right places: the two highest-severity rules (digital arrest) and the core payment boundary
are both anchored to located primary text. **18 rules are both evidenced and implementable** —
well short of the 30 the research package presents, and considerably more trustworthy.

### 4.1 Consequence carried into Phase 2

| Finding | Binding consequence |
|---|---|
| 10 rules `UNSUPPORTED` | Encode as `DRAFT`/`HEURISTIC`; **must not reach the published rule set** ([RESEARCH-004 §7](../01-research/RESEARCH-004-evidence-matrix.md)) |
| 6 rules `PARTIAL` | May publish with capped severity contribution; require stronger indicator combinations to reach the same risk band |
| 3 rules unobservable | Encode `DEFERRED` with `blocked_by: INPUT_MODALITY` ([CONF-003](conflict-register.md)) |
| G-07 no negative indicators | Highest-priority Phase 2 work package; CONF-002's architecture does not function without it |
| G-08 zero non-English content | Blocked on [OI-04](PROGRAM-001-program-charter.md#11-open-issues); ADR-0014 cannot be written until resolved |
| Retrieval is not automatable | INT-001 and OPS-001 must assume a human-in-the-loop step for a subset of official sources |

### 4.2 Charter amendment arising

[SM-10](PROGRAM-001-program-charter.md#71-provable-now) targeted *"27 of 30 starter rules encoded"*
and was written before the evidence verdicts existed. It conflates two different things.
RESEARCH-004 admits only 18 rules to the published set. The charter is amended at v1.1 to separate
**encoding** (27 of 30, excluding the 3 `DEFERRED`) from **publication** (18 of 30) as SM-10 and
the new SM-11. Both numbers are now honest; neither was reduced to fit.

## 5. Residual risk accepted at this gate

| ID | Risk | Position |
|---|---|---|
| [G-01](../01-research/RESEARCH-005-gap-register.md) | I4C entirely unreachable — 7 rules unsupported | **Accepted, open.** Needs manual retrieval from an Indian network. Rules stay `DRAFT`. |
| [G-09](../01-research/RESEARCH-005-gap-register.md) / [RSK-003](risk-register.md) | No labelled real-world corpus | **Unclosable.** No accuracy claim will be made at any point in the programme. |
| [ASM-016](assumption-register.md) | Source reachability | **Disproved for 13 of 26 sources.** Superseded by the structural finding in RESEARCH-001 §5. |
| [ASM-001](assumption-register.md) | No stakeholder access | Unchanged; inherited by every downstream artifact. |

## 6. Gate decision

**Phase 1 is `PARTIAL` and closed. Phase 2 may proceed**, subject to one condition: the Phase 2
rule schema work that depends on language scope ([ADR-0014](../../adr/README.md)) is blocked until
[OI-04](PROGRAM-001-program-charter.md#11-open-issues) is decided. All other Phase 2 work packages
— rule JSON Schema, indicator families, negative-indicator library, rule encoding, taxonomy
completion — are unblocked.

## 7. Addendum — RESEARCH-006 manual retrieval reconciliation (2026-08-28)

A manual, human-in-the-loop retrieval pass ([RESEARCH-006](../01-research/RESEARCH-006-manual-retrieval-reconciliation.md))
was executed after this gate closed — the exact closure path RESEARCH-001 §5 named for the structural
retrieval block. It does not reopen the gate; it discharges residual risk that the gate accepted.

**Effect on the three failed criteria:**

| Criterion (from §3.3) | Was | Now | Note |
|---|---|---|---|
| All cited sources retrievable | ❌ 13/26 failed | ❌ **materially improved** | NPCI and PIB fully recovered; 3 of 4 rule-bearing I4C sources recovered via official channel/replacement. **SRC-002 (I4C index) and SRC-011 (Europol) still fail** — so the criterion is still not met, but the residual is now 2 low-impact sources, not 13. |
| Knowledge base covers claimed language scope | ❌ zero non-English | ❌ **unchanged** | G-08 still open; blocked on OI-04. Manual retrieval added no non-English cues. |
| Negative indicators available | ❌ none | 🟡 **in progress** | The interim indicator registry now carries a negative-indicator set (G-07); it is *validated* by the Phase-2 rule-runner against the benign corpus, not yet by this gate. |

**Effect on residual risk (§5):**

- **G-01** downgraded from "7 rules unsupported" to "2 rules unsupported (SRC-002 index)". Six blocked
  rules recovered under DEC-006 / ADR-0015.
- **ASM-016** (source reachability) — disproved for automated retrieval, **partially recovered** for
  human-in-the-loop retrieval, exactly as RESEARCH-001 §5 predicted.

**Gate result after reconciliation: remains `PARTIAL`.** Two gate criteria (full source
retrievability, language scope) still genuinely fail, so `PASS` is still not honestly reachable. But
the shortfall is now concentrated in an index page, a background report, and the language decision —
not in half the source base. **Phase 2 continues from `PARTIAL`, which programme policy permits**
([roadmap](roadmap.md): downstream work proceeds from a `PARTIAL` gate; G-01 was never a Phase-2
blocker). The evidence-first discipline held throughout: no automated `RETRIEVAL_FAILED` status was
overwritten, and every upgraded rule carries retained, hashed, human-reviewed provenance.

## 8. Change history

| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-08-14 | Phase 1 gate assessed `PARTIAL`, matching forecast. Two manifest traceability defects found and fixed; consistency checker added as gate evidence; SM-10 charter amendment raised. | Technical Program Director |
| 1.1 | 2026-08-28 | Addendum (§7) — RESEARCH-006 manual retrieval reconciliation discharged residual risk (G-01 6/8 rules recovered, NPCI/PIB fully recovered). Gate **remains `PARTIAL`**: language scope and full source retrievability still fail. Automated statuses preserved; DEC-006 / ADR-0015 govern the added evidence. | Technical Program Director |
