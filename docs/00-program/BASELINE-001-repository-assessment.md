# BASELINE-001 — Repository and Input Assessment

| Field | Value |
|---|---|
| Document ID | BASELINE-001 |
| Version | 1.0 |
| Status | **Draft — awaiting review** |
| Owner role | Chief Architect |
| Dependencies | PROGRAM-001 |
| Feeds | RESEARCH-001…005, KB-001, PLAN-001 |
| Assumptions | ASM-001, ASM-006, ASM-010, ASM-011 |
| Decisions | DEC-001…DEC-005 |
| Open issues | OI-02 (Docker), OI-06 (deployment target) |
| Last updated | 2026-07-31 |

---

## 1. Executive summary

**TrustLens is greenfield.** The working directory was empty at assessment time. There is no
prior code, no kickoff package, no memory-bank, no schemas, no tests and no design artifacts.

The Master Execution Prompt (`MP §2`) instructs a recursive inspection of an existing repository
and prior artifacts. **No such repository exists.** This assessment therefore records a
starting position rather than evaluating an inheritance, and the practical consequence is that
every requirement in PROGRAM-001 is *derived* rather than *elicited or inherited*.

The one substantive input is the Phase One Research Foundation, which is materially useful but
is a **secondary synthesis with partly weak citations** (§3). Phase 1 must verify before
encoding.

## 2. Repository inventory

### 2.1 State at assessment (2026-07-31, pre-initialisation)

| Path | Contents |
|---|---|
| `/Users/dineshkumarmohandoss/Desktop/Nish/Internship/software` | **Empty.** No files, no `.git`. |

A search of `~/Desktop` found no TrustLens artifacts anywhere. Sibling directories (`insurance`,
`loan_approval`, `volunteer`) are unrelated projects and were not inspected.

### 2.2 Current-state architecture

**None.** There is no running system, no deployed component, no data store, no interface, no
build and no pipeline. There is consequently no legacy behaviour to preserve, no migration
burden and no compatibility constraint — the one genuine advantage of this starting position.

### 2.3 State after Phase 0 initialisation

Git initialised; the `MP §5` artifact skeleton created (`docs/00-program` … `docs/09-operations`,
`knowledge/`, `adr/`, `apps/`). Documents produced in Phase 0 are listed in [README](../../README.md).
`apps/` remains empty — no implementation has begun, per `MP §23` ("do not start by generating
feature code").

## 3. Input inventory and classification

Per `MP §2`, each supplied artifact is classified.

| # | Input | Classification | Notes |
|---|---|---|---|
| I-01 | TrustLens Master Execution Prompt (20 pp) | **Authoritative** | The governing instruction. Precedence level 2 after the user's live instructions. |
| I-02 | TrustLens Phase One Research Foundation (15 pp) | **Draft / incomplete — secondary** | Substantively valuable; evidentiary weaknesses in §3.2. Precedence level 3. |
| I-03 | TrustLens repository | **Missing** | Empty directory. |
| I-04 | Kickoff package | **Missing** | Referenced by `MP` "How to Use"; never supplied. |
| I-05 | Memory-bank documents | **Missing** | Referenced by `MP §2`; never supplied. |
| I-06 | Requirements documents | **Missing** | Derived into PROGRAM-001 §5 instead. |
| I-07 | Labelled example corpus | **Missing** | Required by `MP §8`; must be authored as synthetic in Phase 1. |
| I-08 | Prior schemas / diagrams / tests / sample data | **Missing** | — |

### 3.1 What the research package genuinely provides

Not to be undersold — this is a strong Phase 1 starting point:

- A 10-category top-level Indian fraud taxonomy with named subcategories (`RP p.2–3`)
- A 12-family threat indicator library organised by cue type, not word lists (`RP p.5–6`)
- **30 normalised starter rules** with detection logic, trigger cues, recommended user action
  and an attributed basis (`RP p.6–12`)
- Four attack-chain relationship maps (`RP p.12`)
- A three-tier severity rationale — critical / high / medium — grounded in likely harm (`RP p.12–13`)
- An explicit statement that detection must be **combinational**, not keyword-based (`RP p.13`)
- Its own gap log, including the admission that source documents need a second archival pass
- **Recency:** cited material runs to June 2026 (NPCI BHIM guidelines, I4C "Boss Scam" advisory),
  so the package is current rather than stale.

Its self-awareness is a point in its favour: it explicitly states that the risk/confidence
numbers are "implementation-ready research judgments… **not** official numeric scores published
by the agencies themselves" (`RP p.6`).

### 3.2 Evidence assessment — why Phase 1 must verify before encoding

| Observation | Detail | Consequence |
|---|---|---|
| Secondary synthesis | Authored via ChatGPT (branding on `RP p.1`); many reference URLs carry `utm_source=chatgpt.com` | Classify `SECONDARY`; strip tracking parameters before recording |
| Citation concentration | **~26 distinct URLs carry 72 footnote markers** | Individual claims are thinly supported relative to the apparent citation density |
| **Index-only citations** | **14 of 72 markers (~19%) resolve to an index or home page.** `i4c.mha.gov.in/advisories.aspx` alone carries 13; `cert-in.org.in` home carries 1 | An index page cannot substantiate a specific claim, and its contents change over time |
| Weakest citations sit on the strongest-weighted source | The research ranks I4C "Very high" priority, yet I4C-derived claims are the most index-dependent | The most relied-upon source is the least verifiable as cited |
| Commercial source treated as authoritative | 5 of 30 rules carry an `HDFC-` prefix; HDFC Bank is a commercial bank, not a regulator | Downgrade to corroborating industry guidance; see [CONF-005](conflict-register.md) |
| Zero verification performed | No cited document has been retrieved and checked | Every source needs a recorded `verification_status` |

**Three rules rest on index-only citations** and are the priority targets for primary retrieval
in Phase 1:

| Rule | Claim | Citation as given |
|---|---|---|
| `I4C-JOB-020` | I4C lists fake-job advisories | `advisories.aspx` index |
| `I4C-CAPTCHA-021` | "I4C has a dedicated **2025 advisory** on fake CAPTCHA-filling jobs" | `advisories.aspx` index |
| `I4C-MATRI-024` | I4C lists matrimonial-platform investment/crypto frauds | `advisories.aspx` index |

By contrast, several rules are cited to specific retrievable documents and should verify cleanly
— `I4C-USSD-013` (USSD advisory PDF), `I4C-CRYPTO-023` (Trust Wallet advisory PDF),
`I4C-ACCESS-027` (Android GOD Mode advisory PDF), `I4C-DARREST-010/011` (NITI Aayog PDF).

## 4. Gap analysis

`MP §7` requires gap analysis across requirements, code, tests, data, security, operations and
documentation. Since the repository is empty, most rows read "everything". Severity reflects
what blocks progress **now**, not eventual importance.

| Dimension | Current state | Gap | Severity |
|---|---|---|---|
| **Requirements** | None supplied | 84 requirements derived in PROGRAM-001; **none validated with a stakeholder** ([ASM-001](assumption-register.md)) | 🔴 High |
| **Research** | Secondary synthesis, unverified | Primary verification pass; 3 rules on index-only citations; no evidence matrix | 🔴 High |
| **Knowledge** | 30 rules exist only as PDF prose | No machine-readable schema, no taxonomy file, no ontology, no negative indicators | 🔴 High |
| **Detection** | Conceptual only | No scoring model; the supplied single-score scheme conflicts with `MP §10` ([CONF-001](conflict-register.md)) | 🔴 High |
| **Code** | None | Entire system | 🟡 Medium — correctly deferred until specs exist |
| **Tests** | None | Entire test pyramid | 🟡 Medium — follows code |
| **Data** | No corpus, no schema, no migrations | Synthetic labelled corpus required; **real corpus unobtainable** ([RSK-003](risk-register.md)) | 🔴 High |
| **Language coverage** | 100% English trigger cues | Product claims multilingual; zero Indian-script or transliterated content ([CONF-004](conflict-register.md)) | 🔴 High |
| **Security** | No threat model, no controls | STRIDE model, RBAC, evidence integrity, upload validation, injection containment | 🟡 Medium — Phase 5 |
| **Operations** | No environment, no CI | **Docker + PostgreSQL absent** ([RSK-006](risk-register.md)); no pipeline, no observability | 🟡 Medium — blocks Phase 9 only |
| **Documentation** | Phase 0 artifacts only | 18 of 20 canonical artifacts outstanding | 🟢 Low — on plan |

## 5. Toolchain assessment

| Tool | Required by `MP §4` | Installed | Verdict |
|---|---|---|---|
| Git | implied | 2.50.1 | ✅ |
| Java | Spring Boot core | 21.0.11 | ✅ Suitable for Spring Boot 3.x |
| Maven | build | 3.9.11 | ✅ |
| Node | React/TypeScript | **26.0.0** | ⚠️ Very new; toolchain support may lag ([RSK-007](risk-register.md)) |
| npm | build | 11.12.1 | ✅ |
| Python | FastAPI intelligence service | **3.14.4** | ⚠️ Very new; ML/OCR library support may lag ([RSK-007](risk-register.md)). Deferred by [DEC-002](decision-log.md) |
| **Docker + Compose** | local development | ❌ **absent** | 🔴 Blocks Phase 9 and Testcontainers-based integration tests |
| **PostgreSQL** | primary datastore | ❌ **absent** | 🔴 Blocks Phase 9 (intended to run via Docker) |
| Gradle | not required | present, version unreported | ➖ Unused; Maven selected |

**Assessment:** the specification phases (0–8) proceed unimpeded. Implementation (Phase 9)
requires a Docker Desktop installation, which needs administrator action from the sponsor. This
is tracked as [OI-02](PROGRAM-001-program-charter.md#11-open-issues) and [RSK-006](risk-register.md).

## 6. Source precedence in force

Per `MP §2`, applied throughout the programme:

1. The user's most recent explicit instruction
2. Approved TrustLens architecture decisions and versioned specifications *(none yet beyond Phase 0)*
3. The supplied Phase 1 research package and its official source references *(classified `SECONDARY` pending verification)*
4. Existing repository behaviour and tests *(none — greenfield)*
5. Earlier drafts and kickoff notes *(none supplied)*
6. Engineering inference, explicitly labelled as assumption

Levels 4 and 5 are empty, so **level 6 carries far more weight than the precedence model
intends**. This is the structural reason Phase 0 cannot report a clean `PASS`.

## 7. Quality-gate status

| Criterion | Status | Evidence |
|---|---|---|
| Repository recursively inspected | ✅ | §2.1 — empty, confirmed by directory listing and search |
| Input inventory produced and classified | ✅ | §3, eight inputs classified |
| Authoritative sources identified | ✅ | §6 precedence, I-01 authoritative |
| Conflicts identified | ✅ | 8 entries, [Conflict Register](conflict-register.md) |
| Missing inputs identified | ✅ | I-03…I-08, five inputs missing |
| Current implementation status established | ✅ | §2.2 — none |
| Gaps visible and severity-rated | ✅ | §4 |

**BASELINE-001 gate: `PASS`.** The assessment itself is complete and evidence-backed. Note that
this is distinct from the Phase 0 gate as a whole, which is `PARTIAL` because PROGRAM-001's
requirement set is unvalidated (see PROGRAM-001 §10).

## 8. Recommendations carried into Phase 1

1. **Verify before encoding.** Attempt retrieval of all ~26 cited URLs; record
   `verification_status` per source; do not promote any claim to `PRIMARY_VERIFIED` without
   locating it in the issuing body's own document. Failed retrievals are logged, not treated as
   blockers ([DEC-003](decision-log.md)).
2. **Prioritise the three index-only rules** listed in §3.2 for primary retrieval, or downgrade
   them explicitly.
3. **Strip `utm_source` tracking parameters** from every URL before recording it.
4. **Snapshot retrieved documents** (hash + retrieval date) — the research package itself warns
   that I4C advisory PDFs are inconsistently fetchable, and link rot is a live risk ([RSK-013](risk-register.md)).
5. **Re-key rule identifiers** from source-branded (`HDFC-…`) to neutral (`TL-<domain>-<n>`),
   carrying sources as data ([CONF-005](conflict-register.md)).
6. **Author the synthetic corpus with benign cases first** — the false-positive examples in
   [CONF-002](conflict-register.md) are the highest-value regression tests the programme has.

## Change history

| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-07-31 | Initial assessment. Greenfield confirmed; 8 inputs classified; research package evidence weaknesses quantified; toolchain gaps identified. | Chief Architect |
