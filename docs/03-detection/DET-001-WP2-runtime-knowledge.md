# DET-001 / P3-WP2 — Published Bundle Loader & Runtime Knowledge Indexes

| Field | Value |
|---|---|
| Document ID | DET-001-WP2 |
| Version | 1.0 |
| Status | **P3-WP2 complete — runtime loader + RuntimeKnowledge frozen** |
| Owner role | Detection Architect |
| Dependencies | [ADR-0004](../../adr/ADR-0004-knowledge-storage-architecture.md), [DET-001](DET-001-deterministic-detection-engine.md), [ADR-0005](../../adr/ADR-0005-rule-execution-model.md), [ADR-0006](../../adr/ADR-0006-risk-and-confidence-aggregation.md), [DET-001-WP1](DET-001-WP1-runtime-contracts.md), KB-001 §8, KB-002 |
| Feeds | P3-WP3 (rule evaluator) — consumes `RuntimeKnowledge` |
| Last updated | 2026-08-29 |

> **Scope.** P3-WP2 builds the deterministic runtime layer that turns a **published knowledge bundle**
> (ADR-0004) into an immutable, indexed, read-only `RuntimeKnowledge` object — or fails closed. It
> **verifies, loads, cross-checks and indexes** governed knowledge. It makes **no fraud decision**: no
> rule evaluation, suppression, scoring, classification or explanation (those are P3-WP3+). DET-001 /
> ADR-0004 / ADR-0005 / ADR-0006 remain authoritative for meaning.

## 1. Package layout

```
knowledge/runtime/
  __init__.py           # public API re-export (import target)
  errors.py             # typed fail-closed loader error hierarchy
  dimensions.py         # shared taxonomy dimension key→axis contract (also used by validate_taxonomy.py)
  indexes.py            # pure index construction + shape/duplicate + reference-integrity checks
  runtime_knowledge.py  # immutable RuntimeKnowledge model (deep-frozen)
  loader.py             # load_bundle(): the ordered, all-or-nothing pipeline
knowledge/validation/
  validate_runtime_loader.py   # 12th canonical gate check + 37-case adversarial suite
```

A proper importable package (relative intra-imports), consumed the normal way with the repo root on
the path — **`from knowledge.runtime import load_bundle`** — so a broken package import cannot be masked
by a `sys.path` hack. No new architectural layer (ADR-0004 unchanged).

## 2. Bundle lifecycle (where WP2 sits)

```
AUTHOR → REVIEW → CI (run_all.py) → APPROVE → PUBLISH (build_bundle.py: immutable, hashed bundle)
       → DEPLOY (ship bundle dir) → ACTIVATE  ◀── P3-WP2 load_bundle() lives here ──▶ EVALUATE (P3-WP3+)
```

WP2 consumes the artefact that `knowledge/publish/build_bundle.py` produces and
`knowledge/publish/validate_bundle.py` proves reproducible. The bundle is **385 KB across 38 files +
`bundle-manifest.json`**: all 26 encoded rules, the indicator registry / families / negative-indicator
library, taxonomy + dimensions, the rule schema + 4 extraction schemas, and evidence **metadata**
(verification manifest + evidence records). Raw PDFs, corpora, coverage matrix and validators are
excluded by construction (ADR-0004 §5.2).

## 3. Loader stages — ordered and fail-closed (STEP 3/4)

`load_bundle` runs a strict pipeline. A failure at any stage raises a **typed** `BundleLoadError` and
**no partial `RuntimeKnowledge` is ever returned** (requirement A):

| # | Stage | Failure → error (`.code`) |
|---|---|---|
| 0 | path-safe `bundle-manifest.json` (its own symlink must not escape root) | `UnsafePathError` (`UNSAFE_PATH`) / `BundleNotFoundError` |
| 1 | parse manifest JSON | `ManifestError` (`MANIFEST_PARSE_ERROR`) |
| 2 | manifest ← `bundle-manifest.schema.json` (Draft 2020-12) | `ManifestError` (`MANIFEST_SCHEMA_INVALID`) |
| 3 | member **path safety** — canonical, no `..`, closed projection, no dup | `UnsafePathError` (`UNSAFE_PATH`) / `IntegrityError` (`UNEXPECTED_MEMBER`) |
| 4 | required members present | `IntegrityError` (`COMPONENT_MISSING`) |
| 5 | per-member existence + **SHA-256** + byte count (bytes **retained**) | `IntegrityError` (`COMPONENT_MISSING`/`COMPONENT_UNREADABLE`/`COMPONENT_HASH_MISMATCH`/`COMPONENT_BYTE_COUNT_MISMATCH`) |
| 6 | **content_digest** recomputation | `IntegrityError` (`DIGEST_MISMATCH`) |
| 7 | manifest-token version **compatibility** (exact-token allowlists) | `CompatibilityError` (`SCHEMA_INCOMPATIBLE`/`VERSION_INCOMPATIBLE`) |
| 8 | parse members (from retained bytes) + **member JSON Schema** | `MemberSchemaError` (`MEMBER_PARSE_ERROR`/`MEMBER_SCHEMA_INVALID`) |
| 9 | component **shapes + duplicate ids** | `MemberSchemaError` (`MEMBER_SHAPE_INVALID`) / `DuplicateIdError` (`DUPLICATE_ID`) |
| 10 | **embedded** member versions == manifest claim | `CompatibilityError` (`EMBEDDED_VERSION_MISMATCH`) |
| 11 | manifest **counts** == loaded population | `IntegrityError` (`COUNTS_MISMATCH`) |
| 12 | **cross-reference integrity** (all shipped rules) | `ReferenceIntegrityError` (`REFERENCE_INVALID`) |
| 13 | build immutable indexes → `RuntimeKnowledge` | — (only reached when everything above passed) |

Members are **hashed and then parsed from the same retained bytes** (no re-open), closing a
verify/parse TOCTOU gap. The engine (P3-WP3+) may later map a fatal load to a DET-001
`input_support_status = ERROR`; the loader itself never expresses a benign/no-scam outcome.

## 4. Integrity (STEP 4 / requirement G)

Two independent checks, both required: (1) every manifest member's **SHA-256 and byte count** are
re-hashed from disk and compared; (2) the bundle **`content_digest`** is recomputed as
`SHA-256("\n".join sorted "<path>=<sha256>"))` — byte-identical to `build_bundle.py`. `created_at` and
`commit_sha` are **excluded** from the digest. Any mismatch fails closed; the loader never rebuilds,
repairs or "heals" a supplied bundle.

## 5. Version compatibility (STEP 5 / requirement 2)

The engine declares **exact-token allowlists** (`loader.SUPPORTED_*`). There is **no semver-range
interpretation and no "latest"** — governed values are matched verbatim, preserving non-semver tokens:

| Field | Accepted (this engine build) |
|---|---|
| `manifest_schema_version` | `1.0.0` |
| `bundle_version` | `1.0.0` |
| `rule_schema` | `1.0.0` |
| `taxonomy` | `2.0` |
| `dimensions` | `1.0.0` |
| `indicator_registry` | `0.3.0-interim` |
| `indicator_families` | `1.0.0` |
| `negative_library` | `1.0.0` |
| `evidence_manifest` | `1.2` |
| `evidence_records` | `1.0` |
| `extraction_schemas` | `1.0.0` |

Any unknown/unsupported token fails closed. Widening support is a deliberate, tested engine change.
**`commit_sha` is provenance only** and is never a compatibility signal (requirement F). The DET-001
`result_contract_version` is an **engine-side output contract** and is deliberately **not** a bundle
member and **not** required by the loader (requirement H, consistent with the WP1 assessment).

**The manifest is not trusted blindly.** Each component's `component_versions` claim is verified against
the member's OWN embedded version field (`taxonomy_version`, `registry_version`, `families_version`,
`library_version`, `dimensions_version`, `manifest_version`, evidence-records `version`,
`schema_version`/`envelope_version` consts). A member whose embedded version differs from the manifest
claim fails closed (`EMBEDDED_VERSION_MISMATCH`), so a hand-edited manifest cannot smuggle an
incompatible component past the allowlist.

## 6. `RuntimeKnowledge` — the read-only surface (STEP 2)

Produced only by a fully successful load. **Deeply immutable** (requirement C / STEP 8): every nested
mapping is a `types.MappingProxyType` and every list a `tuple`, so evaluator code cannot mutate governed
knowledge or an index. A bundle update yields a **new instance** — never in-place mutation.

**Metadata:** `bundle_version`, `content_digest`, `commit_sha`, `manifest_schema_version`,
`component_versions`, `counts`, `meta`.

**Point lookups** (frozen record or `None`): `rule(id)` (any rule, audit), `published_rule(id)`
(executable-only), `indicator(id)`, `negative_indicator(id)`, `family(id)`, `taxonomy_node(id)`,
`dimension_term(id)`, `source(id)`, `evidence(id)`, `override(id)`.

**Collections:** `rule_ids()`, `published_rule_ids()`, `published_rules()`.

**Reverse lookups:** `rules_for_indicator(id)`, `rules_for_category(id)`,
`negative_indicators_for_rule(id)`, `indicators_for_family(id)`, `overrides_for_indicator(id)`,
`overrides_for_target(id)`.

**Introspection:** `index_names()`, `index(name)`.

## 7. Indexes (STEP 11 / requirement I)

16 indexes, each justified by a runtime-evaluation need identified in the STEP 1 assessment. Every
reverse-index value is a **sorted tuple** so iteration order can never become decision semantics.

| Index | Shape | Scope | Size |
|---|---|---|---|
| `rules_by_id` | id → rule | all rules (audit superset) | 26 |
| `published_rules_by_id` | id → rule | **PUBLISHED only** | 18 |
| `indicators_by_id` | id → positive indicator | registry | 63 |
| `negative_indicators_by_id` | id → negative indicator | library | 29 |
| `indicator_families_by_id` | id → family | families | 28 |
| `positive_indicators_by_family` | family → (indicator ids) | families | 28 |
| `taxonomy_by_id` | id → category/subcategory node | taxonomy | 53 |
| `dimensions_by_id` | term id → term | dimensions | 50 |
| `sources_by_id` | id → source metadata | manifest | 26 |
| `evidence_by_id` | id → evidence record | records | 13 |
| `overrides_by_id` | id → hard-risk override | library | 6 |
| `rules_by_indicator` | **positive** indicator → (published rule ids) | **PUBLISHED** | 44 |
| `rules_by_category` | TAX category → (published rule ids) | **PUBLISHED** | 8 |
| `negative_indicators_by_rule` | published rule → (**ACTIVE** negative ids) | **PUBLISHED** | 18 |
| `overrides_by_indicator` | indicator → (override ids) | overrides | 24 |
| `overrides_by_target` | TAX category / rule id → (override ids) | overrides | 5 |

`rules_by_indicator` is keyed on a rule's **positive trigger** operands (`logic.require`) only — a
SUPPRESSION rule's negative operands are excluded so a negative id never appears as a positive trigger
(polarity discipline, validate_rules L2). `rules_by_category` derives a rule's categories from
`taxonomy_refs` (`TAX-01-03 → TAX-01`); it is a **parent-category** grouping (a subcategory id returns
`()`, while exact node lookup is `taxonomy_node(id)`; negative/override family scope is category-level,
matching that grouping — §Taxonomy semantics below). `negative_indicators_by_rule` applies a negative
when its `applicable_rule_families` is `"*"` or intersects the rule's categories **and** the negative is
`status == ACTIVE` (a DEPRECATED negative is not live knowledge — the analogue of the PUBLISHED-only
rule boundary; it remains available via `negative_indicator(id)` for audit). **`rules_by_channel` is
intentionally omitted** — rules carry no channel attribute; it will be added in a separate, tested
change if and when an evaluator demonstrates the need.

**Taxonomy scope contract (authoritative, resolved 2026-08-29).** The governing question was whether
suppression/override family scope is **category-only** or also **subcategory**. Decision: **category-only
(`TAX-NN`)**. Authority: (a) every governed negative `applicable_rule_families` and override
`applies_to_families` value is a category (`TAX-NN`) — no subcategory scope exists in the knowledge; (b)
a rule's category membership is a rollup from `taxonomy_refs`, and runtime suppression/override matching
is category-level, so a subcategory-scoped negative could never be acted on consistently. The prior
disagreement — `validate_negative_library.py` accepted category **or** subcategory scope — was a genuine
governance inconsistency and has been **tightened to category-only** (see §16 remediation; this expands
the WP2 diff to one authoring validator, reported explicitly). All current governed knowledge still
passes. Runtime `validate_references` enforces the same category-only rule, so authoring and runtime now
agree.

Concretely: `taxonomy_by_id` (via `taxonomy_node`) is an **exact** node lookup over one id namespace
holding both categories (`TAX-NN`) and subcategories (`TAX-NN-MM`), duplicate-guarded.
`rules_by_category` / `rules_for_category` is a **parent-category** rollup (a rule tagged `TAX-01-03` is
grouped under `TAX-01`; a subcategory id passed to `rules_for_category` returns `()` by design — use
`taxonomy_node` for exact subcategory data). This is consistent with `validate_taxonomy.py`.

**Dimension axis integrity (resolved 2026-08-29).** A taxonomy subcategory's `dimensions` map is
validated **per axis**, not against a flattened global term set: a term is legal only under its own
axis, so `technical_mechanism: ["FO-01"]` is **rejected** even though `FO-01` exists in the
`fraud_objective` axis, and an **unknown axis key** is rejected even if its term exists elsewhere. The
map keys differ from the registry axis names (e.g. key `typical_channels` → axis `channel`); that
`key → axis` mapping is the **single source of truth** in `knowledge/runtime/dimensions.py`, imported by
**both** the runtime loader and the authoring `validate_taxonomy.py` so they cannot silently diverge.
Scope note: **family `applicable_dimensions` is intentionally validated against the global term set**
(not axis-scoped), mirroring its governing authoring validator `validate_extraction.py` — WP2 does not
tighten a runtime-consumed dimension map beyond the contract its governing validator defines.

## 8. Published-rule boundary (STEP 6 / requirement D)

ADR-0005 fixes live evaluation to **PUBLISHED** rules. The bundle ships all 26 encoded rules (8 are
`DRAFT`/`PEER_REVIEW`/`APPROVED`); the loader filters `lifecycle.status == "PUBLISHED"` into the
**executable** set. Non-published rules are reachable **only** via `rule(id)` / `rules_by_id` for audit
— never through `published_rules_by_id`, `rules_by_indicator`, `rules_by_category` or
`negative_indicators_by_rule`. The gate test asserts a known non-published rule (e.g. `TL-MAL-003`)
never leaks into any executable index.

## 9. Cross-reference integrity (STEP 7 / requirement E)

At load time the loader resolves the governed references (and the governed polarity / status / ownership
contracts) that runtime evaluation and suppression depend on; any violation **fails the load** (no silent
drop). Enforced relationships:

- **rule → indicator** (`require` operands + `suppressed_by`) · **rule → `taxonomy_refs`** ·
  **rule → `source_id`** · **rule → `manual_retrieval.evidence_ids`**
- **rule polarity:** a `COMPOSITE` trigger operand may not be a negative indicator; a `SUPPRESSION`
  trigger operand may not be a positive indicator (validate_rules L2)
- **rule → manual-evidence ownership:** a cited `evidence_id` must be owned by (`manifest_source_id` ==)
  the `source_id` that cites it — mere existence is not enough (validate_rules L10)
- **PUBLISHED rule → suppressor status:** a PUBLISHED rule may not depend on a `DEPRECATED` negative
  (validate_rules L1b)
- **family →** `indicator_outputs` · `negative_interactions` · `hard_risk_overrides` ·
  `applicable_dimensions` term ids (global term set, per `validate_extraction.py`)
- **taxonomy subcategory → `dimensions`** — **axis-scoped**: unknown axis key, valid term under the wrong
  axis, and nonexistent term are all rejected (shared `knowledge/runtime/dimensions.py`)
- **negative →** `applicable_rule_families` (TAX **category**) · `source_basis` · `suppresses_indicators`
  (positive indicators)
- **override →** condition indicators (positive) · `applies_to_families` (TAX **category**) ·
  `applies_to_rules` · `blocks_suppression_categories` (library suppression-category vocabulary)
- **evidence → `manifest_source_id`** and **source → `manual_retrieval.evidence_ids`**

**Trust-boundary decision (remediation).** Rule-originated references are validated on **all shipped
rules**, not only the PUBLISHED subset. Rationale: authoring (`validate_rules.py`) validates every rule
regardless of `lifecycle.status`, so a compliant bundle can never legitimately ship a rule (draft or
published) with a dangling reference; the loader mirrors that boundary as fail-closed defence-in-depth,
and a draft that is later flipped to PUBLISHED cannot introduce a latent dead reference. `PUBLISHED`
remains a **separate executability filter** (§8). The self-test confirms the loader independently
catches injected dangling indicator/taxonomy/source/manual-evidence references, including in a
non-published rule.

## 10. Immutability, activation & rollback (STEP 8/9/10)

- **Immutability:** a successful load returns a deep-frozen instance; there is no mutating API.
- **Activation:** an orchestrator holds a reference to the *active* `RuntimeKnowledge`. To activate a
  candidate it calls `load_bundle(candidate)`; only on success does it swap the reference (an atomic
  pointer swap). A failed candidate raises and **never touches the currently-active instance**.
- **Rollback:** `load_bundle(previous_bundle_dir)` then swap back. Because each recorded decision pins
  the bundle `content_digest` + component versions (ADR-0004 §5.5), rolling the active bundle back never
  rewrites the meaning of an already-recorded result.
- Deployment **orchestration itself is future work** (ADR-0004 §5.4); WP2 provides only the safe
  runtime abstraction. The suite proves two valid bundles load into two independent instances with
  distinct digests (a **synthetic compatibility fixture**, *not* an N-1 governed/production bundle — no
  historical governed version exists yet).

## 11. Offline & security boundaries (STEP 13/14/15 / requirement F)

- **Offline:** loading reads **only** files under the bundle root, plus the engine's own pinned
  manifest schema. No network, no subprocess, no git, no source-URL or PDF retrieval; `commit_sha`
  triggers no repository lookup. The gate statically asserts the runtime package imports no
  network/subprocess module.
- **Evidence boundary:** only source/evidence **metadata and references** are loaded — never raw PDF
  bytes (they are not in the bundle at all).
- **Path safety:** `bundle-manifest.json` itself and every member path must be relative, **canonical**
  (a non-canonical form like `rules/./x` — a semantic duplicate — is rejected), contain no `..`, sit
  under the allowed runtime prefixes, be unique, and resolve (through any symlink) to within the bundle
  root — else `UnsafePathError`.
- **Exact closed projection (finding 5):** a member must be **either** one of the fixed component paths
  (the 7 knowledge components + `schemas/rule.schema.json` + the 4 extraction schemas) **or** a canonical
  `rules/TL-XXX-NNN.json`. Any other manifested path — an unknown JSON such as `sources/extra.json`, a
  `.pdf`, or a test/dev artefact — is rejected with `UNEXPECTED_MEMBER`, even though it is hash-covered,
  so it can never be hashed into the digest yet silently ignored by `RuntimeKnowledge`. The
  `bundle_version 1.0.0` contract defines no forward-compatible/extension members. The **manifest is the
  authoritative closed membership set** — the loader reads *only* manifested members, so a stray
  unmanifested physical file cannot influence `RuntimeKnowledge`. The manifest **`counts`** the loader can
  independently recompute (files, rules total/published, positive/negative indicators, taxonomy
  categories/subcategories, dimension terms) must equal the loaded population, else `COUNTS_MISMATCH` —
  the manifest cannot under/over-state what was loaded.

## 12. Error model (STEP 16 / requirement B)

A small typed hierarchy under `BundleLoadError`, each carrying a stable `.code`:
`BundleNotFoundError`, `ManifestError`, `IntegrityError` (with `UnsafePathError`), `CompatibilityError`,
`MemberSchemaError`, `ReferenceIntegrityError`, and `DuplicateIdError`. Stable codes:
`BUNDLE_NOT_FOUND`, `MANIFEST_PARSE_ERROR`, `MANIFEST_SCHEMA_INVALID`, `COMPONENT_MISSING`,
`COMPONENT_UNREADABLE`, `COMPONENT_HASH_MISMATCH`, `COMPONENT_BYTE_COUNT_MISMATCH`, `DIGEST_MISMATCH`,
`UNSAFE_PATH`, `UNEXPECTED_MEMBER`, `COUNTS_MISMATCH`, `SCHEMA_INCOMPATIBLE`, `VERSION_INCOMPATIBLE`,
`EMBEDDED_VERSION_MISMATCH`, `MEMBER_PARSE_ERROR`, `MEMBER_SCHEMA_INVALID`, `MEMBER_SHAPE_INVALID`,
`DUPLICATE_ID`, `REFERENCE_INVALID`. Callers/tests distinguish by **category** (`isinstance`) and
**exact cause** (`.code`); **no raw `KeyError` / `JSONDecodeError` / `OSError` / `ValidationError`
escapes** as the public API — malformed non-rule component shapes and member IO failures are mapped to
typed errors. These are **loading** errors, distinct from a DET-001 fraud decision.

## 13. Validation & the 12th gate check (STEP 17/18/19/21/22)

`knowledge/validation/validate_runtime_loader.py` (the **12th canonical gate check**) builds the real
bundle into a temp directory (STEP 19) and runs **48 deterministic cases** — success + every failure
path — asserting the **precise typed error** category/code, plus deterministic reload, the published
boundary, deep nested immutability, positive-trigger polarity (now a hard load failure), deprecated-
suppressor rejection, wrong-source manual-evidence ownership, global positive/negative id collision,
six malformed **nested** shapes, six governed nested-reference closures, **taxonomy dimension axis
integrity** (wrong-axis / unknown-axis / nonexistent-term rejected, correct-axis loads), taxonomy
exact/parent semantics, embedded-version and counts consistency, exact closed membership incl. an unknown
manifested JSON, a manifest symlink escape, a byte-count-only mismatch, a member IO failure, non-published
dangling references, normal package import, and the offline guarantee. Synthetic corruption/compatibility bundles
exist **only in temp storage**; governed knowledge is never modified. Local `run_all.py` and CI run the
identical suite; `ci_selftest.py` confirms the enlarged gate stays non-vacuous (the loader itself also
independently catches the injected authoring defects — defence-in-depth).

## 14. Performance (STEP 12)

385 KB / 38 files loads in **~72 ms** (best of 5, cold) into 16 in-memory indexes. In-memory is
sufficient at this scale (ADR-0004 §5.3); **no PostgreSQL / Redis / Neo4j / caching layer** is
introduced.

## 15. What is NOT done (deferred)

No rule evaluation, Kleene logic, suppression/override execution, aggregation, scoring, classification,
confidence or explanation — all P3-WP3+. No deployment/activation orchestration service. No governed
knowledge **content** was changed (one authoring **validator**, `validate_negative_library.py`, was
tightened to resolve a real governance inconsistency — see §16 round 2, finding 4).

## 16. Remediation — independent adversarial review (Codex)

Two independent read-only review rounds. Findings were fixed within the WP2 boundary (no
evaluation/scoring/suppression/Kleene/classification added), each with a regression test that fails
before the fix.

**Round 1**

| # | Finding | Disposition | Fix |
|---|---|---|---|
| 1 | Embedded component-version not verified | ACCEPTED | Member's own declared version checked against the manifest claim; mismatch → `EMBEDDED_VERSION_MISMATCH` |
| 2 | Raw exceptions could leak | ACCEPTED | Member IO → `COMPONENT_UNREADABLE`; malformed non-rule shape → `MEMBER_SHAPE_INVALID`; all mapped to typed errors |
| 3 | Reference completeness / non-published scope | ACCEPTED | References validated on **all** shipped rules; added rule→`manual_retrieval.evidence_ids`; boundary documented (§9) |
| 4 | Duplicate semantic ids silently overwritten | ACCEPTED | Per-collection duplicate detection → `DuplicateIdError` |
| 5 | Closed bundle membership | ACCEPTED | Canonical-path normalization; closed projection (`UNEXPECTED_MEMBER`); counts cross-check (`COUNTS_MISMATCH`) |
| 6 | Manifest path / TOCTOU | ACCEPTED | Manifest symlink safety; members parsed from the SAME hashed bytes; distinct `COMPONENT_BYTE_COUNT_MISMATCH` |
| 7 | Indicator polarity / deprecated negatives | ACCEPTED | `rules_by_indicator` = positive operands only; `negative_indicators_by_rule` = ACTIVE negatives only |
| 8 | Taxonomy semantics | PARTIALLY ACCEPTED | Documented; resolved fully in round 2 |
| 9 | Package imports | ACCEPTED | `knowledge/runtime/` is a proper package; tests use normal package import |
| 10 | Test coverage | ACCEPTED | Suite 22 → 37 cases |

**Round 2 (final)**

| # | Finding | Disposition | Fix |
|---|---|---|---|
| 1 | Nested malformed-component containment | ACCEPTED | `check_shapes_and_duplicates` now validates **every runtime-consumed nested structure** before traversal (`_need_list`/`_need_dict`/`_need_dim_map`) — `subcategories=null`, `indicator_outputs=null`, `applicable_rule_families=null`, `manual_retrieval=string`, `applicable_dimensions=null`, `blocks_suppression_categories={}` etc. → `MEMBER_SHAPE_INVALID`, never a raw `TypeError`/`AttributeError` |
| 2 | Runtime reference/polarity must match governed contract | ACCEPTED | `validate_references` extended: family `negative_interactions` / `hard_risk_overrides` / dimension terms; taxonomy subcategory dimension terms; negative `suppresses_indicators`; override `blocks_suppression_categories`; rule **polarity** (no negative in COMPOSITE trigger, no positive in SUPPRESSION trigger); PUBLISHED rule may not reference a **DEPRECATED** suppressor; manual-evidence **ownership** (`manifest_source_id` must equal the citing `source_id`) |
| 3 | Global governed stable-ID uniqueness | ACCEPTED | `check_shapes_and_duplicates` adds a **cross-namespace** uniqueness pass (taxonomy/dimension/indicator/negative/rule share one namespace, per `validate_kb.py`/KB-001) → a positive id equal to a negative id is `DuplicateIdError` before indexing |
| 4 | Resolve taxonomy scope contract (not just document) | ACCEPTED (with authoring change) | Authoritative decision: **category-only** (`TAX-NN`) family scope. `validate_negative_library.py` tightened from category-**or**-subcategory to category-only; runtime `validate_references` enforces the same. All governed knowledge still passes (no data uses subcategory scope). **Expands the diff to one authoring validator — reported.** |
| 5 | Exact manifested projection | ACCEPTED | Membership tightened to an **exact whitelist**: fixed component paths + canonical `rules/TL-XXX-NNN.json`; any other manifested JSON (`sources/extra.json`) → `UNEXPECTED_MEMBER` |
| 6 | Complete adversarial regression coverage | ACCEPTED | Suite 37 → **44 cases** covering every round-2 finding |

**Round 3 (final)**

| Finding | Disposition | Fix |
|---|---|---|
| Taxonomy dimension **axis** integrity not enforced at runtime (terms validated against a flattened global set) | ACCEPTED | Runtime now validates each taxonomy subcategory `dimensions` map **per axis**, rejecting an unknown axis key, a valid term under the wrong axis, and a nonexistent term. The governing `key → axis` mapping was extracted from `validate_taxonomy.py` into a shared pure module `knowledge/runtime/dimensions.py`, imported by **both** the runtime loader and `validate_taxonomy.py` (single source of truth, no divergence). Family `applicable_dimensions` stays global-scoped, matching its governing validator `validate_extraction.py` (scope not expanded beyond governance). Suite 44 → **48 cases** (wrong-axis / unknown-axis / nonexistent-term / correct-axis-loads). |

No finding was rejected across any round.

## 17. Change history

| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-08-29 | P3-WP2: added `knowledge/runtime/` (errors, indexes, runtime_knowledge, loader); fail-closed bundle load with manifest schema + SHA-256 + content-digest integrity, exact-token version compatibility, member schema + cross-reference validation, PUBLISHED-only executable boundary, 16 immutable indexes; `validate_runtime_loader.py` wired as the 12th canonical gate check (22 cases). No detection logic; no governed knowledge changed. | Detection Architect |
| 1.1 | 2026-08-29 | P3-WP2 remediation round 1: embedded component-version verification; typed containment of IO/shape/duplicate failures; reference validation broadened to all shipped rules + manual-retrieval evidence; duplicate-id detection; canonical/closed membership + counts cross-check; manifest symlink safety + TOCTOU-safe parse + distinct byte-count code; positive-only trigger index + ACTIVE-only negatives; proper importable package; suite 22 → 37 cases. No detection logic; no governed knowledge changed. | Detection Architect |
| 1.2 | 2026-08-29 | P3-WP2 remediation round 2: full nested-shape containment (`MEMBER_SHAPE_INVALID`); reference/polarity/ownership/deprecated-suppressor closures matching the governed contract; global cross-namespace stable-id uniqueness (positive/negative collision → `DuplicateIdError`); **taxonomy scope resolved to category-only** — `validate_negative_library.py` tightened accordingly (only authoring file changed, governed data unaffected); exact manifested projection (`UNEXPECTED_MEMBER` for unknown JSON); suite 37 → 44 cases. No detection logic. | Detection Architect |
| 1.3 | 2026-08-29 | P3-WP2 remediation round 3 (final): **taxonomy dimension axis integrity** — subcategory `dimensions` validated per axis (wrong-axis / unknown-axis / nonexistent-term rejected), via new shared single-source `knowledge/runtime/dimensions.py` imported by both the runtime loader and `validate_taxonomy.py`; family `applicable_dimensions` deliberately left global-scoped per `validate_extraction.py`; suite 44 → 48 cases. No detection logic; no governed knowledge content changed. | Detection Architect |
