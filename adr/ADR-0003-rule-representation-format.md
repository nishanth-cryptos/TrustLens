# ADR-0003 — Rule representation format

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-08-15 |
| **Owner role** | Chief Architect |
| **Related** | [CONF-001](../docs/00-program/conflict-register.md), [CONF-002](../docs/00-program/conflict-register.md), [CONF-003](../docs/00-program/conflict-register.md), [CONF-005](../docs/00-program/conflict-register.md) · [DEC-004](../docs/00-program/decision-log.md), [DEC-005](../docs/00-program/decision-log.md) · FR-020, FR-021, FR-023, FR-025, FR-028 · [RESEARCH-004 §7](../docs/01-research/RESEARCH-004-evidence-matrix.md) |
| **Phase** | 2, work package 1 |

## Context and constraints

`MP §9`'s gate requires a new scam type to be addable **through data alone**, with no engine code
change. `MP §21` forbids "dozens of untraceable keyword rules" presented as threat intelligence.
FR-021 requires malformed rules to be rejected at load time, not to fail mysteriously at
evaluation.

Four Phase 0 conflicts must be carried into whatever format is chosen, or they are resolved on
paper only:

- **CONF-001** — the research package's 0–100 scores must not become operational risk values.
- **CONF-002** — rules must be combinational; a single keyword must not produce a finding. This
  is the highest-severity entry in the register, because the worked failure case is TrustLens
  flagging a bank's own anti-fraud SMS.
- **CONF-003** — some rules need evidence TrustLens cannot observe and must be retained without
  being live.
- **CONF-005** — identifiers must be neutral; sources are data, not brand names in keys.

Phase 1 adds a fifth constraint: **10 of 30 rules have no verified basis**, and RESEARCH-004 §7
requires that they be retained but kept out of the published set.

## Decision

**Rules are JSON documents validated by a JSON Schema (draft 2020-12), with a second linting
layer for constraints a single-document schema cannot express.**

- `knowledge/schemas/rule.schema.json` — the schema.
- `knowledge/rules/TL-*.json` — one rule per file, filename equal to rule ID.
- `knowledge/validation/validate_rules.py` — schema validation plus lint.
- `knowledge/rules/_fixtures/invalid-rules.json` — the negative corpus.

### The two-layer split

The schema enforces what one document can prove about itself:

| Constraint | Mechanism |
|---|---|
| Severity is an ordinal, never a number | `enum` of `LOW…CRITICAL`; no numeric field exists |
| No risk or confidence stored on a rule | `additionalProperties: false` makes the field unrepresentable |
| Research 0–100 scores quarantined | `provenance.source_severity_hint.operational_use` is `const false` |
| `UNSUPPORTED`/`HEURISTIC` cannot publish | `if/then` on verdict → `status` `not const PUBLISHED` |
| `DEFERRED` cannot publish, and must say why | `if/then` on implementability → `blocked_by` required |
| `PARTIAL` must carry a severity cap | `if/then` on verdict → `severity_cap` required |
| Non-heuristic rules need a graded source | `if/then` → `source_references` `minItems: 1` |
| Neutral IDs | `pattern` `^TL-[A-Z]{3,5}-\d{3}$` |
| No silent language degradation | `on_unsupported_input` is `const FLAG_UNSUPPORTED` |
| No single-indicator rules | `min_evidence_classes` `minimum: 2`; `any_of` `minItems: 2`; `n_of.n` `minimum: 2` |

The linter enforces what requires knowledge held in *other* files:

| Check | Why it cannot be in the schema |
|---|---|
| Every indicator resolves in the registry | Cross-file reference |
| Every satisfying path spans ≥ `min_evidence_classes` | Requires evaluating the condition tree against indicator metadata |
| No rule satisfiable by `WEAK` indicators alone | Same |
| Trigger and suppressor polarity are correct | Requires the registry |
| Source grade matches the verification manifest | Cross-file, and the most important check in the set |
| Verdict does not exceed the Phase 1 evidence matrix | Requires RESEARCH-004 |
| Taxonomy references resolve | Cross-file |

**The `min_evidence_classes` check is the whole of CONF-002 made executable.** It walks every
minimal satisfying set of a rule's condition tree — not just the union of its indicators — because
a rule whose `all_of` spans three classes can still have an `any_of` branch satisfiable by one
weak signal. That branch is a keyword matcher hiding inside a composite rule, and it is precisely
what the register warned about.

**The manifest-agreement check is the mechanism by which evidence quality changes behaviour**
rather than merely being documented. A rule cannot claim `PRIMARY_VERIFIED` for a source the
Phase 1 pass graded `RETRIEVAL_FAILED`, and cannot re-grade its own verdict upward. Without it,
`MP §3`'s evidence-first principle is an aspiration.

## Alternatives considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **JSON + JSON Schema + linter** | Mature tooling in both Python and Java (ADR-0001); machine-validatable; diffable in review; schema is itself versioned data | Cross-file constraints need a second layer; JSON is verbose for humans | **Selected** |
| YAML + JSON Schema | Friendlier authoring, comments allowed | Type coercion surprises (`no` → `false`); indentation-sensitive; a knowledge editor's slip becomes a semantic change | Rejected — a format that can silently change meaning is wrong for rules whose whole purpose is verifiability |
| A rule DSL | Expressive, compact | Requires a parser, a grammar, and tooling nobody else has; violates `MP §9`'s data-not-code gate; one engineer ([ASM-012](../docs/00-program/assumption-register.md)) cannot maintain a language | Rejected |
| Rules in a database, authored via UI | Lifecycle and approval built in | Not diffable, not reviewable in version control, no clean bootstrap; a database migration becomes the audit trail | Rejected for authoring; DATA-001 may still store a *published copy* for serving |
| Drools / a general rules engine | Battle-tested evaluation | Brings a full production-rules language and its evaluation semantics; determinism (NFR-001) becomes something we inherit rather than specify; enormous surface for a 27-rule set | Rejected |

## Consequences

- A new scam type is added by writing one JSON file and running the validator. FR-028 and `MP §9`'s
  gate are satisfiable, and will be proven by test in WP4.
- Every rule carries its own explanation. A rule that cannot explain itself fails validation,
  which makes FR-046 structural rather than a downstream UI concern.
- **`REDUCE` suppression rules cannot validate yet**, because `reduce_by` is deliberately
  undefined until DET-001 specifies the reduction mathematics. This is intended: it prevents
  magnitudes being invented ahead of the model that gives them meaning. `SUPPRESS` works today.
- The linter must run in CI before any rule reaches a published set (WP7).
- The Java loader in Phase 9 must validate against the same schema file, not a reimplementation.

## Risks

| Risk | Mitigation |
|---|---|
| The two-layer split drifts — a check migrates between layers unnoticed | Every negative fixture declares `expect_rejected_by`; a check caught by the wrong layer fails the build |
| Schema becomes a bottleneck as rules grow more expressive | `rule_version` and `schema_version` are separate; a schema change is an ADR amendment, not a silent edit |
| Indicator registry is interim (v0, derived from the seed corpus) | Superseded by WP2's indicator families and WP3's negative-indicator library; the registry file names its own successor |
| JSON verbosity discourages careful authoring | Reference rules exist for every shape, so authoring starts from a working example rather than the schema |

## Reversal cost

**Low.** The rules are data. Changing serialisation format is a mechanical transform of ~30 files
plus a rewrite of the loader. What would be expensive to reverse is the *content model* — the
separation of severity from risk, evidence verdict from implementability, and trigger from
suppressor — but that content model is inherited from the conflict register and is not
format-specific.

## Validation plan

Satisfied at authoring time, not deferred:

1. **7 reference rules** covering every shape — `SUPPORTED`+`PUBLISHED`, `PARTIAL`+capped,
   `UNSUPPORTED`+`DRAFT`, `SUPPORTED`+`DEFERRED`, and a `SUPPRESSION` rule.
2. **23 negative fixtures**, each breaking exactly one constraint, each declaring which layer must
   reject it. All 23 are rejected, by the expected layer.
3. `30/30 checks passed`, reproducible via
   `.venv/bin/python knowledge/validation/validate_rules.py`.

**The validator found two real defects in the reference rules during authoring**, which is the
evidence that it does something:

- `TL-PAY-001` accepted `RECEIVE_FRAMING + QR_SCAN_REQUEST` — a single evidence class. Inspection
  showed the rule was also reaching past its own quotation: SRC-021's wording here concerns a UPI
  PIN or OTP, not QR codes. The trigger was narrowed to match the source.
- `TL-TEL-001` was satisfiable by three weak indicators. Its actual discriminator — being asked to
  dial a code — **had no positive indicator in the registry at all**, only the benign guard
  `NO_CODE_DIAL_REQUEST`. The seed corpus contains no malicious USSD case because the rule is
  `UNSUPPORTED`, so the positive was never needed. A guard existed with nothing to guard against.

Outstanding for WP4: prove FR-028 by adding a new scam type through data alone, with zero engine
lines changed, as an automated test.

## Amendment — 2026-08-28 (manual-retrieval provenance)

Following the RESEARCH-006 manual retrieval reconciliation and [DEC-006](../docs/00-program/decision-log.md) /
[ADR-0015](ADR-0015-evidence-hierarchy-and-official-alternate-provenance.md), the two-layer model is
extended, not changed:

- **Schema.** `sourceReference` gains an optional additive `manual_retrieval` object. The automated
  `verification_status` field is unchanged and still records the Phase-1 automated grade — so the
  original manifest-agreement check (a rule may not overstate `verification_status`) is untouched.
- **Linter, two new cross-file checks.** **L10** validates every `manual_retrieval` block against
  `evidence-records.json` and the manifest's per-source overlay (evidence IDs resolve, SHA-256
  recorded, evidence class agrees, claim wording does not exceed the source, review recorded when
  published). **L11** enforces the ADR-0015 class caps: a rule may not publish on a failed source
  with no manual evidence, and `OFFICIAL_ALTERNATE`/`INDUSTRY` evidence caps a rule at `PARTIAL`.
- **Negative corpus** grows from 23 to 25: `published-on-failed-source-without-manual-evidence` and
  `official-alternate-claiming-supported`, both LINT-caught.

The layer split is preserved: schema shape stays in the schema, cross-file evidence knowledge stays
in the linter.
