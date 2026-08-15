# TrustLens

An Indian, explainable, multilingual digital-scam detection, evidence-preservation and
assisted-reporting platform.

TrustLens analyses suspicious SMS, email, WhatsApp text, URLs and screenshots; detects scam
patterns using versioned, source-traceable rules; explains the decision in terms a person can
verify; preserves evidence with integrity metadata; and generates a structured report bundle
that a user or analyst can take to the appropriate authority.

**TrustLens does not file reports on anyone's behalf, and its output is not an official
determination.** It assists reporting and investigation.

---

## Status

| | |
|---|---|
| Programme phase | Phase 0 ✅ · Phase 1 ✅ (`PARTIAL`, [GATE-001](docs/00-program/GATE-001-phase-1-assessment.md)) · **Phase 2 — Knowledge Engineering, next** |
| Knowledge base | 26 sources graded, **11 verified** · 10 categories / 41 subcategories · 30 starter rules graded, **18 evidenced and implementable** · 22 open research gaps |
| Implementation | Not started — specifications only |
| Detection quality | **Unmeasured.** No labelled corpus exists yet; no accuracy claim is made. |

## Governing documents

The programme is executed against two supplied inputs, plus artifacts generated from them:

| ID | Artifact | Location |
|---|---|---|
| PROGRAM-001 | Program Charter | [docs/00-program/PROGRAM-001-program-charter.md](docs/00-program/PROGRAM-001-program-charter.md) |
| BASELINE-001 | Repository Assessment | [docs/00-program/BASELINE-001-repository-assessment.md](docs/00-program/BASELINE-001-repository-assessment.md) |
| GATE-001 | Phase 1 Gate Assessment | [docs/00-program/GATE-001-phase-1-assessment.md](docs/00-program/GATE-001-phase-1-assessment.md) |
| — | Assumption Register | [docs/00-program/assumption-register.md](docs/00-program/assumption-register.md) |
| — | Risk Register | [docs/00-program/risk-register.md](docs/00-program/risk-register.md) |
| — | Conflict Register | [docs/00-program/conflict-register.md](docs/00-program/conflict-register.md) |
| — | Decision Log | [docs/00-program/decision-log.md](docs/00-program/decision-log.md) |
| — | Glossary | [docs/00-program/glossary.md](docs/00-program/glossary.md) |
| — | Roadmap | [docs/00-program/roadmap.md](docs/00-program/roadmap.md) |
| — | ADR index | [adr/README.md](adr/README.md) |

## Knowledge artifacts (Phase 1)

| Artifact | Location |
|---|---|
| Source inventory — 26 sources graded, 6 discrepancies | [docs/01-research/RESEARCH-001-source-inventory.md](docs/01-research/RESEARCH-001-source-inventory.md) |
| Scam taxonomy — 10 categories, 41 subcategories | [docs/01-research/RESEARCH-002-scam-taxonomy.md](docs/01-research/RESEARCH-002-scam-taxonomy.md) |
| Advisory extraction — 10 verified advisories | [docs/01-research/RESEARCH-003-advisory-extraction.md](docs/01-research/RESEARCH-003-advisory-extraction.md) |
| Evidence matrix — 30 rules graded | [docs/01-research/RESEARCH-004-evidence-matrix.md](docs/01-research/RESEARCH-004-evidence-matrix.md) |
| Gap register — 22 open gaps | [docs/01-research/RESEARCH-005-gap-register.md](docs/01-research/RESEARCH-005-gap-register.md) |
| Machine-readable: sources · taxonomy · seed corpus | [knowledge/](knowledge/) |

Check that the documents and the machine-readable files still agree:

```bash
python3 knowledge/validation/phase1_consistency_check.py   # 35/35 checks passed
```

## Rules (Phase 2, in progress)

Rules are versioned JSON data validated by a real schema — never engine code ([ADR-0003](adr/ADR-0003-rule-representation-format.md)).

```bash
python3 -m venv .venv && .venv/bin/pip install jsonschema
.venv/bin/python knowledge/validation/validate_rules.py    # 30/30 checks passed
```

The validator loads every rule in [knowledge/rules/](knowledge/rules/) against
[rule.schema.json](knowledge/schemas/rule.schema.json), then applies cross-file lint the schema
cannot express — indicator resolution, evidence-class diversity, trigger/suppressor polarity, and
agreement with the Phase 1 source grades. It then runs a negative corpus of **23 deliberately
malformed rules that must all be rejected**, each declaring which layer should catch it.

## Repository layout

```
docs/00-program      charter, scope, glossary, registers, roadmap
docs/01-research     official-source research, evidence matrix, research gaps
docs/02-knowledge    ontology, taxonomy, rule model, knowledge graph, governance
docs/03-detection    detection pipeline, scoring, explainability, false-positive strategy
docs/04-ai           AI architecture, model boundaries, evaluation, safeguards
docs/05-architecture system context, containers, components, deployment, security
docs/06-data-api     data model, schemas, migrations, API and event contracts
docs/07-implementation epics, iterations, acceptance criteria, DoD, release plan
docs/08-testing      test strategy, datasets, evaluation protocol, quality reports
docs/09-operations   deployment, observability, backup, recovery, runbooks
knowledge/           taxonomies, rules, source mappings, seed data, validation
adr/                 numbered Architecture Decision Records
apps/                implementation modules
```

## Core engineering principles

1. **The rule engine decides.** AI assists interpretation and extraction; it never silently
   overrides deterministic evidence.
2. **Evidence first.** Every conclusion traces to normalised input → extracted entities →
   indicators → matched rules → score contributions → source references.
3. **Uncertainty is shown, not hidden.** Ambiguous or weakly-supported cases route to review
   rather than being presented as certain.
4. **Risk and confidence are separate quantities.** They are never collapsed into one number.
5. **Configuration over hardcoding.** A new scam type is added through data, not engine code.
6. **No fake completion.** A phase is not complete while acceptance criteria, tests,
   documentation or traceability are absent.

## Prerequisites

| Tool | Required | Status on this machine |
|---|---|---|
| Java | 21+ | ✅ 21.0.11 |
| Maven | 3.9+ | ✅ 3.9.11 |
| Node | 20+ | ✅ 26.0.0 |
| Docker + Compose | required for Phase 9 | ❌ **not installed** |
| PostgreSQL | 16 (via Docker) | ❌ **not installed** |

Docker and PostgreSQL block implementation (Phase 9) but not the specification phases.
See [RSK-006](docs/00-program/risk-register.md).
