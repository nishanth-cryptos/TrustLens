# KB-001 — Knowledge Governance and Rule Lifecycle

| Field | Value |
|---|---|
| Document ID | KB-001 |
| Version | 1.0 |
| Status | **Approved** — Phase 2, work package 6 |
| Owner role | Chief Architect |
| Dependencies | RESEARCH-001…006, [ADR-0003](../../adr/ADR-0003-rule-representation-format.md), [ADR-0015](../../adr/ADR-0015-evidence-hierarchy-and-official-alternate-provenance.md), [DEC-003](../00-program/decision-log.md), [DEC-005](../00-program/decision-log.md), [DEC-006](../00-program/decision-log.md) |
| Feeds | DET-001, ARCH-001, DATA-001, OPS-001 |
| Last updated | 2026-08-29 (v1.1 — §11 CI enforcement) |

---

## 1. Purpose

KB-001 defines **how a piece of knowledge becomes an executable, published detection — and how it is
kept honest afterwards.** It is the governance layer over the artifacts Phase 2 built: the source
verification manifest, the scam taxonomy and dimensions, the indicator registry, the negative-indicator
library, and the rule set. It specifies lifecycles, the state machine for each artifact, what each
transition requires, the provenance chain, versioning, and — critically — **which controls are
machine-enforced and which are human-review controls**.

KB-001 defines the **logical** knowledge model only. The **physical** persistence (relational / graph
/ file) is deliberately not chosen here — it is [ADR-0004](../../adr/README.md), which is **unresolved**.
Nothing in KB-001 assumes a storage engine.

## 2. The knowledge pipeline

```
SOURCE ─▶ EVIDENCE ─▶ CLAIM ─▶ INDICATOR ─▶ RULE ─▶ TEST ─▶ REVIEW ─▶ PUBLISH ─▶ MONITOR ─▶ REVISE / DEPRECATE
```

| Stage | Artifact | Where it lives today |
|---|---|---|
| SOURCE | verification manifest entry | `knowledge/sources/verification-manifest.json` |
| EVIDENCE | automated grade + `manual_retrieval` layer; evidence records | manifest + `knowledge/sources/manual-retrieval/evidence-records.json` |
| CLAIM | located quotation / locator | manifest `verified_quotes` / evidence-record `claim` |
| INDICATOR | positive indicator; negative indicator | `indicator-registry-v0.json`; `negative-indicator-library-v1.json` |
| RULE | rule JSON | `knowledge/rules/TL-*.json` |
| TEST | seed corpus + suppression tests | `knowledge/seed-data/*.json` |
| REVIEW | `lifecycle` + `manual_retrieval.review_*` metadata | rule files |
| PUBLISH | `lifecycle.status = PUBLISHED` | rule files |
| MONITOR / REVISE | change_history + review_due | all artifacts |

**Invariant (MP §3, §21):** a claim may never skip a stage. No rule without an indicator; no indicator
without an evidence-graded source or an honest `HEURISTIC` label; no publication without tests and review.

## 3. Artifact lifecycles and state machines

### 3.1 Source lifecycle

Grades (automated, DEC-003): `PRIMARY_VERIFIED` · `PRIMARY_CITED_UNVERIFIED` · `INDEX_ONLY` ·
`RETRIEVAL_FAILED`. The automated grade is **immutable history** — it is never overwritten.
Manual retrieval adds a `manual_retrieval` layer with an ADR-0015 evidence class
(`PRIMARY` · `OFFICIAL_ALTERNATE` · `OFFICIAL_REPLACEMENT` · `INDUSTRY` · `SECONDARY`).

Transitions: `RETRIEVAL_FAILED → (+ manual_retrieval layer)` when a human retrieves the document; the
automated `status` stays. A source is never deleted; if a URL dies, the entry is kept and a
replacement is recorded as a new evidence layer (see §6).

### 3.2 Evidence lifecycle

Evidence is a located claim in a graded source. It carries: locator, quote/claim, retrieval date,
SHA-256, evidence class, review status. Evidence **strengthens** (manual retrieval upgrades a class)
but its history is retained. Evidence is never fabricated from a document that was not read (MP §21).

### 3.3 Indicator lifecycle (positive)

Registry entry: `id`, `evidence_class`, `strength`, optional `source_basis`. Status is implicit
`ACTIVE`; deprecation is by removal-with-successor (the registry names its `superseded_by`).
An indicator must be *extractable in principle* and referenced by ≥1 rule, or it is dead weight.

### 3.4 Negative-indicator lifecycle

Library entry (WP3): `status` `ACTIVE`/`DEPRECATED`, `category`, `suppression_effect`
(`SUPPRESS_RULE` · `SUPPRESS_INDICATOR` · `CAP_SEVERITY` · `CONTEXT_ONLY`), `applicable_rule_families`,
`false_negative_risk`, overrides. A `DEPRECATED` negative may not be referenced by any rule
(`validate_rules.py` L1b). Numeric reduction magnitudes are **out of scope** here — deferred to DET-001.

### 3.5 Rule lifecycle

Statuses (schema, ADR-0003 — **unchanged**): `DRAFT → PEER_REVIEW → SECURITY_REVIEW → APPROVED →
PUBLISHED`, and terminal `DEPRECATED` / `RETIRED`. "Superseded" is expressed by the `supersedes`
field on the replacement plus `DEPRECATED` on the old rule (not a separate status).

```
DRAFT ─▶ PEER_REVIEW ─▶ SECURITY_REVIEW ─▶ APPROVED ─▶ PUBLISHED
                                                │           │
                                                └────────────┴─▶ DEPRECATED ─▶ RETIRED
```

Only `PUBLISHED` rules are evaluated against live submissions (FR-023). `APPROVED` and `PEER_REVIEW`
rules are encoded knowledge that is not yet live (e.g. impl PARTIAL, or awaiting sign-off).

### 3.6 Taxonomy lifecycle

Terms carry `status` (`ACTIVE`/`DEPRECATED`), `version`, `evidence` (automated) and `evidence_maturity`
(current). IDs are permanent (RESEARCH-002 §5.4); deprecation sets a flag and never reuses an ID. A
category may be `detection_status: DEFERRED_SAFEGUARDING` (TAX-11) — recognised but carrying no rule.

### 3.7 Test lifecycle

All test cases are `SYNTHETIC` (CON-005) and may never be used to claim precision/recall (G-09).
Benign cases are authored first (CONF-002). Categories: benign, malicious, ambiguous, adversarial,
suppression. A test is retained; changing an expectation is a `change_history` event.

## 4. Transition requirements — what it takes to advance a rule

| Transition | Requirements | Enforced by |
|---|---|---|
| → `DRAFT` | valid schema; neutral ID; taxonomy refs resolve; ≥1 graded source (unless HEURISTIC) | 🤖 `validate_rules.py` (schema + L1/L5/L6) |
| → `PEER_REVIEW` | above + combination discipline (`min_evidence_classes ≥ 2` on every path); polarity correct | 🤖 `validate_rules.py` (L2/L3/L4) |
| → `SECURITY_REVIEW` | above + abuse/over-suppression review; hard-risk overrides considered | 👤 human (security) + 🤖 `rule_runner.py` override tests |
| → `APPROVED` | above + `approved_by_role`; verdict ≤ Phase-1 matrix; provenance not overstated | 🤖 L7/L11 + 👤 approver |
| → `PUBLISHED` | **the full checklist in §5** | 🤖 five validators + 👤 named reviewer |
| → `DEPRECATED` | `deprecation_reason`; successor recorded if replaced | 🤖 schema + 👤 |
| → `RETIRED` | `deprecation_reason`; removed from the evaluated set | 👤 |

## 5. PUBLISHED checklist (machine vs human)

A rule may be `PUBLISHED` only when **all** hold. Each is marked 🤖 machine-enforced or 👤 human-review.

| # | Requirement | Control |
|---|---|---|
| 1 | Valid against the rule JSON Schema | 🤖 `validate_rules.py` (schema) |
| 2 | Source & evidence traceable to the manifest / evidence records | 🤖 L6/L10 + `rule_runner.py` traceability |
| 3 | Acceptable evidence strength; ADR-0015 caps respected (OFFICIAL_ALTERNATE/INDUSTRY ⇒ PARTIAL) | 🤖 L11 |
| 4 | Taxonomy references valid, not deprecated, publishable maturity | 🤖 `validate_taxonomy.py` |
| 5 | Positive indicators resolve; combination spans ≥2 evidence classes | 🤖 L1/L3/L4 |
| 6 | Negative indicators / suppressors resolve, not deprecated | 🤖 L1b + `validate_negative_library.py` |
| 7 | Required combinations valid (no single-signal path, no weak-only path) | 🤖 L3/L4 |
| 8 | ≥1 malicious test case fires the rule | 🤖 `rule_runner.py` (coverage) |
| 9 | ≥1 benign near-miss does not fire it | 🤖 `rule_runner.py` |
| 10 | Ambiguous / adversarial test where applicable | 🤖 `rule_runner.py` (suppression suite) + 👤 judgement on applicability |
| 11 | Runner executes the rule cleanly | 🤖 `rule_runner.py` |
| 12 | Human-review metadata present (`approved_by_role`; `manual_retrieval.review_status = REVIEWED` where manual) | 🤖 schema/L10 + 👤 identity of reviewer |
| 13 | No unresolved hard validator failure across the five validators | 🤖 CI |
| 14 | Evidence-first judgement: the concept is genuinely supported, not merely plausible | 👤 **human — not automatable** |

**Machine-enforced vs human-review split.** Items 1–13 are machine-checkable and run in CI. Item 14,
and the *quality* of the review in 3/10/12, are human controls: a validator can confirm a reviewer role
is recorded and that tests exist, but not that the review was diligent or that the concept is sound.
KB-001 deliberately does **not** try to encode judgement as software (MP §3).

## 6. Change-response playbook

| Event | Response |
|---|---|
| **A source disappears (link rot)** | Keep the manifest entry and its automated grade; record the dead URL; seek an OFFICIAL_REPLACEMENT and add it as a `manual_retrieval` layer. Rules on that source drop to their next-best evidence class; if none, they move toward `DEPRECATED` and out of the published set. |
| **An advisory is superseded** | Add the new source; keep the old (history). Re-point dependent rules; bump the rule `rule_version` (MAJOR if the claim changed). |
| **Evidence changes** | Re-grade the evidence layer (never rewrite the automated grade). If maturity drops below publishable, unpublish (→ `DEPRECATED`/`PEER_REVIEW`) via the human control. |
| **A rule is contradicted by a source** | Record the contradiction (like discrepancies D1–D6); narrow or retire the rule; never silently keep it. |
| **False positive reported** | Add the case as a benign/adversarial test (must_not_match); author or strengthen a negative indicator / override; re-run the suite. Do not weaken a hard-risk override to fix an FP without security review. |
| **False negative reported** | Add a malicious test; check whether a suppressor over-fired (see below) or an indicator/combination is missing; add evidence before publishing any new rule. |
| **A taxonomy term changes** | Deprecate the old ID (never reuse); add the new; migrate rule `taxonomy_refs`; `validate_taxonomy.py` fails any rule left on a deprecated term. |
| **A negative indicator over-suppresses** | Raise its `false_negative_risk`; narrow its `applicable_rule_families`; or add a hard-risk override that blocks it (as HR_BANKING_REMOTE_ACCESS blocks IT_SUPPORT_CONTEXT). Add a test proving the fix. |
| **Emergency disablement** | Flip `lifecycle.status` PUBLISHED → `DEPRECATED` with a `deprecation_reason`; the rule leaves the evaluated set immediately. This is a human control with an audit trail; no code change is required (rules are data, ADR-0003). |

## 7. Provenance model

Every published finding must answer the full chain. KB-001 fixes where each answer lives:

| Question | Answer source |
|---|---|
| Which rule fired? | `rule.id` + `rule_version` |
| Which indicators matched? | `rule_runner` explanation → `matched_positives` |
| Which negative indicators were evaluated / applied? | runner explanation → `negatives_present`, `neutralised`, `cancelled_by`, `blocked_suppressors` |
| Which overrides were applied? | runner explanation → `overrides_active` |
| What evidence supports the rule? | `rule.evidence.source_references[]` (+ `manual_retrieval` layer) |
| What source supports that evidence? | manifest entry (automated grade + `manual_retrieval`, SHA-256, canonical URL, retrieval date) |
| What rule version ran? | `rule_version` |
| What indicator-library version ran? | `negative-indicator-library-v1.json` `library_version` + registry `registry_version` |
| What taxonomy version applied? | `scam-taxonomy.json` `taxonomy_version` + `dimensions_version` |

The **ADR-0015 evidence hierarchy is preserved unchanged**: `PRIMARY` · `OFFICIAL_ALTERNATE` ·
`OFFICIAL_REPLACEMENT` · `INDUSTRY` · `SECONDARY`, with the seven official-alternate publication
conditions (official identity, archived snapshot, canonical URL, retrieval date, SHA-256, exact claim
located, human review). KB-001 does not weaken any of them.

## 8. Versioning policy

Semantic versioning across all knowledge artifacts (rules, taxonomy, dimensions, indicator registry,
negative-indicator library, source/evidence metadata, seed corpus):

| Bump | Meaning | Examples |
|---|---|---|
| **PATCH** | No change to interpretation | spelling, metadata, a clarified description, a new example |
| **MINOR** | Backwards-compatible addition | a new indicator, a new taxonomy term, a new test case, a new source with no rule change |
| **MAJOR** | Semantic change to interpretation or contract | a rule's logic/severity changes; a taxonomy term's meaning changes; a suppression effect changes; an evidence grade is downgraded in a way that unpublishes a rule |

Notes: `schema_version` is a **const** per schema revision (an ADR amendment, not a silent bump).
`rule_version` moves independently of `schema_version` (ADR-0003). A MAJOR change to a published rule
requires re-review (§5). This adapts the repository's existing version fields; it does not replace them.

## 9. Machine-enforced vs human-review controls (summary)

**Machine-enforced (CI, five validators):** schema validity; ID neutrality/uniqueness; indicator &
taxonomy & source & evidence resolution; no deprecated references; combination discipline; polarity;
verdict ≤ Phase-1 matrix; ADR-0015 caps; manifest status preservation (durable-truth guard); test
coverage (malicious fires, benign does not); override behaviour; traceability; version syntax.

**Human-review controls (not automatable):** soundness of a concept (§5 item 14); diligence of peer /
security / approval review; whether an official-channel identity is genuinely official; safeguarding
decisions (e.g. TAX-11); whether to weaken a hard-risk override; emergency disablement authorisation.

KB-001's position: **encode what is objectively checkable; leave judgement to a named human with an
audit trail.** Over-encoding governance as software creates false assurance.

## 10. Storage boundary

The above is a **logical** model. Physical persistence — whether sources/evidence/rules/taxonomy live
in files (as now), a relational schema, a graph, or a hybrid, and how a published rule-set version is
distributed — is **[ADR-0004](../../adr/README.md) (knowledge storage), which is unresolved.** KB-001
must not be read as choosing one. Where DATA-001 or ADR-0004 later fix persistence, they inherit this
logical model and its lifecycles.

## 11. Continuous enforcement — the CI quality gate (WP7)

The machine-enforced controls in §5 and §9 are wired into a **continuous quality gate** so they run
on every relevant change rather than on request. The gate is one canonical command,
`knowledge/validation/run_all.py`, which runs the complete validation suite (the eight validators) in
dependency order; the GitHub Actions workflow
[`knowledge-validation.yml`](../../.github/workflows/knowledge-validation.yml) runs that same command
on pull requests and pushes to `main` that touch knowledge, governance/research/knowledge docs, ADRs,
the dependency file, or the workflow itself. Full description: [GATE-006](../00-program/GATE-006-phase-2-ci-quality-gates.md).

**Merge-eligibility rule.** A change **cannot become merge-eligible while the mandatory machine-enforced
TrustLens validation suite fails.** A red gate means an evidence, taxonomy, indicator, rule,
suppression, extraction-contract or governance regression is present and must be fixed before merge.
The gate runs **offline** against the committed evidence bundle (a preflight refuses to run if any
validator imports a network module), so a green result is a statement about the repository's durable
truth, not about a live source.

**CI does not replace human review.** The gate enforces exactly the objectively checkable controls
(§9, machine column); it makes **no** judgement about the controls §9 reserves for a named human, all
of which remain mandatory:

- evidence **interpretation** and whether a concept is genuinely supported (§5 item 14);
- whether an **official-channel identity** is genuinely official (ADR-0015);
- **safeguarding** decisions (e.g. TAX-11 sextortion detection deferral);
- **semantic rule review** — peer/security/approval diligence;
- whether to **weaken a hard-risk override**;
- **publication approval** — the transition to `PUBLISHED`.

A green gate is **necessary but not sufficient** for merge or publication: it certifies the machine
controls hold, and the human controls are then applied on top. Over-encoding governance as software
would create false assurance (§9); the gate is deliberately scoped to what is objectively decidable.

## 12. Change history

| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-08-28 | Initial KB-001. Pipeline, seven artifact lifecycles, rule state machine reconciled with ADR-0003, PUBLISHED checklist with machine/human split, change-response playbook, provenance model (preserving ADR-0015), versioning policy, storage boundary deferred to ADR-0004. | Chief Architect |
| 1.1 | 2026-08-29 | Added §11 continuous enforcement: the WP7 CI quality gate (`run_all.py` + `knowledge-validation.yml`) makes a change merge-ineligible while the machine-enforced suite fails, without replacing the §9 human controls. | Chief Architect |
