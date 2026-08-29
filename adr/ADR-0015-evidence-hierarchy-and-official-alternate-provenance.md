# ADR-0015 — Evidence hierarchy and official-alternate provenance

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-08-28 |
| **Owner role** | Chief Architect |
| **Related** | [DEC-003](../docs/00-program/decision-log.md), [DEC-006](../docs/00-program/decision-log.md) · [CONF-005](../docs/00-program/conflict-register.md) · [ADR-0003](ADR-0003-rule-representation-format.md) · [RESEARCH-001 §7](../docs/01-research/RESEARCH-001-source-inventory.md), [RESEARCH-006](../docs/01-research/RESEARCH-006-manual-retrieval-reconciliation.md), [GATE-001](../docs/00-program/GATE-001-phase-1-assessment.md) |
| **Phase** | 2 (reconciliation), work package 1 |

## Context and constraints

The Phase-1 automated verification pass ([DEC-003](../docs/00-program/decision-log.md)) recognised
exactly one way for a source to substantiate a claim: the issuing body's **own document** is
retrieved and the specific claim is located inside it (`PRIMARY_VERIFIED`). Everything else was
`RETRIEVAL_FAILED`, `INDEX_ONLY` or `PRIMARY_CITED_UNVERIFIED`. That binary was correct for an
automated pass, but it cannot describe what the manual retrieval pass ([RESEARCH-006](../docs/01-research/RESEARCH-006-manual-retrieval-reconciliation.md))
actually produced:

- **Exact issuing-body documents** finally retrieved by hand (NPCI, PIB, SEBI body) — genuine primary.
- **Official issuing-body channel publications** — the I4C **CyberDost** Telegram channel — carrying
  the exact claim, where the formal advisory PDF is still unreachable (SRC-013, SRC-019, SRC-024).
- **Official replacement documents** from the *same authority family* that substantiate the concept
  when the originally-cited document is dead (PIB-2023 + I4C-2025 for the task-job chain; CERT-In
  booklet for the untrusted-install concept).
- **Commercial/industry replacement pages** (current HDFC pages) — useful, corroborating, but never
  authoritative ([CONF-005](../docs/00-program/conflict-register.md)).

Three constraints bound the decision:

1. **`DEC-003` semantics must not be weakened.** `PRIMARY_VERIFIED` must keep meaning exactly what
   it meant. A channel post is not a formal advisory and must not be laundered into one.
2. **The rule linter's manifest-agreement check ([ADR-0003](ADR-0003-rule-representation-format.md))
   must keep catching over-statement.** A rule may not claim a grade the manifest does not record.
3. **Publication must remain evidence-gated**, not plausibility-gated. New evidence does not
   auto-publish a rule ([RESEARCH-004 §7](../docs/01-research/RESEARCH-004-evidence-matrix.md)).

Without an explicit hierarchy, the manual evidence would either be silently promoted to
`PRIMARY_VERIFIED` (dishonest) or discarded (wasteful). Both are wrong.

## Decision

**Adopt a five-class evidence hierarchy, and permit `OFFICIAL_ALTERNATE` (and `OFFICIAL_REPLACEMENT`)
evidence to support a *published* rule only under named, checkable conditions.** The class is
recorded **additively** alongside — never overwriting — the automated `status`.

### The hierarchy

| Class | Definition | Max rule verdict it can carry alone |
|---|---|---|
| **PRIMARY** | The issuing body's own formal document retrieved (automated or manual) and the specific claim located within it. | `SUPPORTED` |
| **OFFICIAL_ALTERNATE** | A publication on an issuing body's **own official channel/social-media account** (e.g. I4C CyberDost) carrying the exact claim, where the formal document is unavailable. | `PARTIAL` (capped) |
| **OFFICIAL_REPLACEMENT** | A **different official document from the same or an equivalent authority** that substantiates the concept when the originally-cited official document is dead/unreachable. | `SUPPORTED` if the replacement is itself PRIMARY-grade; else `PARTIAL` |
| **INDUSTRY** | A commercial body's page (bank, platform). Corroborates; never authorises ([CONF-005](../docs/00-program/conflict-register.md)). | `PARTIAL` (capped) |
| **SECONDARY** | Third-party reporting, the research package itself, background material. | Cannot alone support a published rule. |

`PRIMARY` and `OFFICIAL_REPLACEMENT` are the only classes that can carry a lone `SUPPORTED` verdict,
and `OFFICIAL_REPLACEMENT` only when the replacement document is itself an issuing-body PRIMARY
document (as PIB-2023 and I4C-2025 are). `OFFICIAL_ALTERNATE` and `INDUSTRY` cap at `PARTIAL` with a
`severity_cap`, because a channel post and a commercial page are each a step below a formal
issuing-body advisory.

### Conditions for OFFICIAL_ALTERNATE to support a *published* rule

All seven must hold and be recorded in the manifest's `manual_retrieval` block and the rule's
`source_references[].manual_retrieval` block:

1. **Official identity** — the account/channel is demonstrably the issuing body's own (URL + handle).
2. **Archived evidence retained** — the snapshot is stored under `knowledge/sources/raw/…`.
3. **Canonical URL and retrieval date recorded.**
4. **SHA-256 recorded** for the archived snapshot.
5. **Exact supporting claim located** — a page/locator, and wording that matches the rule concept.
6. **Rule wording does not exceed the source** — every rule clause is covered by the located claim;
   unsupported clauses are narrowed out, not retained.
7. **Human review recorded** — `review_status: REVIEWED`, with a named review role.

The same conditions 2–7 are required for `OFFICIAL_REPLACEMENT` and `INDUSTRY` to back a published
rule; condition 1 is generalised to "the replacement source's authority and canonical location are
recorded".

### How it is represented without weakening automated semantics

- The manifest `status` field stays the **automated** grade. It is never edited by this ADR.
- A `manual_retrieval` object is added per source carrying `evidence_class`, `manual_retrieval_status`,
  durable `evidence_ids`, canonical URL, retrieval date, SHA-256 and `review_status`.
- A rule's `source_references[]` entry keeps `verification_status` equal to the automated manifest
  grade (so the ADR-0003 over-statement check still fires) and carries an optional
  `manual_retrieval` sub-object naming the evidence class and durable evidence IDs it relies on.
- The linter gains two checks (see [ADR-0003](ADR-0003-rule-representation-format.md) amendment):
  a rule that reaches `SUPPORTED`/`PARTIAL` on a source whose automated grade was **not**
  `PRIMARY_VERIFIED` must carry a valid `manual_retrieval` block resolving to a real evidence record;
  and an `OFFICIAL_ALTERNATE`-backed rule may not exceed `PARTIAL`.

## Alternatives considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **Five-class hierarchy, additive manual layer** | Honest; preserves `DEC-003`; keeps the over-statement check; lets real evidence count | Two more linter checks; more provenance to author | **Selected** |
| Promote channel posts to `PRIMARY_VERIFIED` | Simple; rules publish immediately | Destroys the meaning of `PRIMARY_VERIFIED`; a Telegram post becomes indistinguishable from a formal advisory | Rejected — dishonest |
| Ignore non-PDF evidence entirely | Purist | Discards genuine official evidence; leaves 5 sound rules unsupported forever | Rejected — wasteful and not required by any principle |
| One flat "verified/unverified" bit | Minimal | Cannot express that a channel post is weaker than an advisory; forces either over- or under-claiming | Rejected |

## Justification

The hierarchy is the smallest change that lets manual evidence count **for exactly what it is worth
and no more**. It keeps `PRIMARY_VERIFIED` meaning what `DEC-003` said, records the weaker classes
honestly, and makes the strength difference operational: `OFFICIAL_ALTERNATE` and `INDUSTRY` cap at
`PARTIAL`, so their rules carry a `severity_cap` and need stronger indicator combinations to reach the
same risk band — the same mechanism RESEARCH-004 §7 already uses for partial evidence. The seven
conditions are the auditable form of "we actually checked", not a rubber stamp.

## Consequences

- TL-MAL-002 and TL-CRYP-001 may be **encoded and evidenced** on official-channel evidence, but only
  at `PARTIAL` (capped), and only with the seven conditions recorded.
- TL-PAY-002, TL-AUTH-003 reach `SUPPORTED` on manual PRIMARY evidence; TL-JOB-003 on
  OFFICIAL_REPLACEMENT PRIMARY documents.
- INDUSTRY-only rules (TL-MAL-003 via HDFC) cap at `PARTIAL`.
- The DET-001 source-reliability weighting (Phase 3) gains a natural input: evidence class becomes a
  term in the weight, refining [RESEARCH-001 §7](../docs/01-research/RESEARCH-001-source-inventory.md).
- The Java loader (Phase 9) must understand the `manual_retrieval` block and the class cap.

## Risks

| Risk | Mitigation |
|---|---|
| "Official channel" is asserted, not proven | Condition 1 requires the handle/URL; the archived snapshot and SHA-256 make it falsifiable |
| A channel post is edited/deleted after archiving | SHA-256 + retained snapshot make later drift detectable (same rationale as DEC-003 hashing) |
| Class caps are bypassed by citing a second weak source | The linter caps verdict from evidence class and from RESEARCH-004; two PARTIAL sources do not make a SUPPORTED rule |
| Hierarchy drifts from the schema enum | The class vocabulary lives in the schema and this ADR; a change is an ADR amendment, not a silent edit |

## Reversal cost

**Low.** The classes are data on the manifest and rule files; the caps are two linter checks. Removing
the hierarchy means deleting the `manual_retrieval` blocks and reverting five rules to `DRAFT` — a
mechanical change. What is expensive to reverse is *dishonesty*, which this ADR exists to prevent.

## Validation plan

1. Manifest carries `manual_retrieval.evidence_class` on all 14 re-reviewed sources; automated
   `status` unchanged — proven by `manual_evidence_check.py` and `phase1_consistency_check.py`.
2. The rule linter rejects a rule that reaches `SUPPORTED`/`PARTIAL` on a failed source **without** a
   valid manual block (new negative fixture), and rejects an `OFFICIAL_ALTERNATE`-backed rule that
   claims `SUPPORTED` (new negative fixture).
3. Every published rule relying on manual evidence carries the seven conditions — checked by the
   linter and reviewable in the rule file.
