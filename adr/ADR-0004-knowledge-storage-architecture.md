# ADR-0004 — Knowledge Storage Architecture

| Field | Value |
|---|---|
| Status | **Accepted** |
| Date | 2026-08-29 |
| Owner role | Chief Architect |
| Phase | 2 — Knowledge engineering (WP8) |
| Related | [KB-001](../docs/02-knowledge/KB-001-knowledge-governance.md), [KB-002](../docs/02-knowledge/KB-002-extraction-contracts.md), [ADR-0003](ADR-0003-rule-representation-format.md), [ADR-0015](ADR-0015-evidence-hierarchy-and-official-alternate-provenance.md), [DEC-004](../docs/00-program/decision-log.md), roadmap WP8, [GATE-007](../docs/00-program/GATE-007-phase-2-storage.md) |
| Reversal cost | **Low** — the authoring format does not change; a runtime store can be added later without touching authored knowledge |

---

## 1. Context and constraints

TrustLens knowledge — rules, indicators, negative indicators, taxonomy, dimensions, schemas, and
source/evidence metadata — is **governed** knowledge: every artifact is versioned, source-traceable,
peer/security-reviewed, and machine-validated before it may be published (KB-001). Phase 3 (DET-001)
will need to *load* this knowledge at runtime to evaluate submissions. ADR-0004 decides **where the
knowledge lives and how it flows to runtime** — nothing about the Phase-3 engine itself.

Constraints that bind the decision:

- **Explainability + auditability (MP §8, FR-046).** Every decision must trace input → indicators →
  rule → evidence → source. The store must preserve exact versions and provenance.
- **Determinism + reproducibility (Phase-3 gate).** The same input + same knowledge version must give
  the same result, and one must be able to reconstruct *exactly which knowledge executed*.
- **Rules are data, never code (ADR-0003, FR-020).** The store must not turn rules into engine logic.
- **Human review happens on diffs (KB-001 §5, DEC-004).** Review, approval and publication are
  git-diff-shaped workflows today; a validator, not prose, is the gate.
- **Offline / on-prem (NFR).** After deployment the runtime must need no GitHub, no advisory websites,
  no package registry, no network to evidence sources.
- **Evidence integrity (ADR-0015).** Raw evidence is SHA-256-hashed and its automated grade is
  immutable history; nothing may silently mutate an already-recorded decision.
- **Scale is small.** 26 rules, 92 indicators (63 positive + 29 negative), 11 categories / 42
  subcategories / 50 dimension terms, ~13 MB of archived PDFs. There is no big-data or high-QPS driver.
- **CI already enforces the machine controls (WP7).** Eight validators run on every change via
  `run_all.py` and GitHub Actions.

## 2. Decision

**Option B — Git/JSON as the single authoritative source of truth, plus a generated, immutable,
hash-addressed *published knowledge bundle* for runtime.**

1. **Authoring & governance store = the Git repository.** Authored JSON + Markdown under `knowledge/`
   and `docs/` remain the *only* authoritative definition of every rule, indicator, taxonomy term,
   schema and piece of evidence metadata. Review/approval/publication stay git-diff workflows gated by CI.
2. **Published artifact = an immutable, versioned knowledge bundle.** A deterministic build step
   (`knowledge/publish/build_bundle.py`) assembles the *runtime-necessary* knowledge into a bundle with
   a `bundle-manifest.json` carrying every component version, a SHA-256 per file, and a content digest
   over the whole set. The bundle is a **build artifact**, reproducible from a commit — not re-authored,
   never hand-edited.
3. **Runtime store = in-memory indexed knowledge loaded from a bundle.** The Phase-3 engine loads a
   bundle once, validates its manifest + hashes, and builds in-memory indexes. No database is required
   to *hold knowledge*.
4. **No database is authoritative for knowledge.** If PostgreSQL appears in Phase 3+, it holds
   operational/audit/analytics data (activation records, decision events, usage), and — at most — a
   **materialized, read-only cache** of a bundle (one-way, bundle → DB; never DB → knowledge).
5. **Graph database: NOT JUSTIFIED** (see §5.11).
6. **Raw evidence stays in Git now**, referenced by a migration-safe hash-addressed model, with a
   documented path to Git LFS / object storage if repository growth ever warrants it (§5.12).

This is the STEP-5 candidate architecture, adopted after testing it against the requirements below.

## 3. The four stores (they are deliberately different things)

| Store | What it is | Where | Authoritative? |
|---|---|---|---|
| **Authoring / governance** | Human-authored, reviewed knowledge | Git repo (`knowledge/`, `docs/`) | **Yes — the single source of truth** |
| **Published artifact** | Immutable, versioned, hashed runtime bundle | build output (`build/…`, or a release asset / tag) | No — a faithful, verifiable projection of a commit |
| **Runtime** | In-memory indexes loaded from a bundle | process memory (Phase 3) | No — reconstructable from the bundle |
| **Audit / history** | Immutable record of what was published/activated and what decided each case | Git history + tags now; an append-only event log in Phase 3+ | Yes for *history*, never re-writing knowledge meaning |

## 4. Alternatives considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **A. Git/JSON only, at authoring *and* runtime** (engine reads the working tree directly) | Simplest; no build step; fully offline | No immutable published unit; runtime coupled to repo layout; "which knowledge ran" answered only by a commit SHA, with dev/test files and 13 MB of PDFs dragged along; no integrity boundary | **Rejected** — cannot cleanly answer reproducibility/integrity, ships test data to runtime |
| **B. Git/JSON source of truth + generated immutable runtime bundle** | Keeps Git authority + diff review; deterministic, hashed, versioned published unit; lean offline runtime; clean dev/test vs runtime split; DB optional later | Adds a build + manifest step (small) | **SELECTED** |
| **C. Git source of truth + relational runtime DB** | SQL query/admin convenience | Sync risk (two representations of the same truth); migration burden; runtime now needs a DB even at trivial scale; offline/on-prem heavier; explainability crosses a DB boundary | **Rejected for MVP** — no query need justifies it; revisitable if scale/admin demands it |
| **D. Relational DB authoritative for knowledge** | Central admin UI writes; row-level history | Governed knowledge leaves Git → loses diff review, CI-as-gate, and evidence-first traceability; violates ADR-0003 "rules are data" review model; migrations become the change process | **Rejected** — inverts the governance model KB-001 depends on |
| **E. Git + relational + graph** | Rich relationship queries | Everything in C/D plus a third store to keep in sync; no query actually needs a graph at this scale | **Rejected** — sophistication without a requirement |

## 5. Design detail

### 5.1 Source-of-truth model (STEP 2)
Git is authoritative for rule/indicator/negative-indicator/taxonomy/schema/evidence-metadata/governance
artifacts. A database does **not** become authoritative merely because Phase 3 needs runtime access —
runtime access is served by the bundle, which is a projection of Git. Authoring, published artifact,
runtime and audit are four distinct things (§3) and are not forced to be the same store.

### 5.2 Published knowledge bundle (STEP 6)
Logical contents (runtime-necessary only):
```
bundle-manifest.json          # versions, per-file sha256, content digest, commit, gate result
rules/TL-*.json               # all encoded rules (engine filters to lifecycle.status == PUBLISHED)
indicators/                   # indicator-registry, indicator-families, negative-indicator-library
taxonomy/                     # scam-taxonomy, dimensions
schemas/                      # rule.schema + the 4 extraction contracts (load-time validation)
sources/                      # verification-manifest + evidence-records  (METADATA references only)
```
**Excluded from the runtime bundle:** raw PDFs (archival, not needed to decide), seed/suppression/
reconciliation corpora and invalid-rule fixtures (test), the extraction-coverage matrix (analysis),
and the validators (tooling). The runtime engine needs source/evidence *metadata and references*, not
whole source documents.

### 5.3 Runtime model (STEP 9)
The engine loads one bundle, verifies the manifest schema + every file hash + the content digest, then
builds in-memory indexes (rule-by-id, indicator-by-id/family, taxonomy tree + dimension maps). This is
fully offline and on-prem: after the bundle is delivered, no network is required. In-memory is more than
sufficient at this scale and keeps explainability a pure in-process traversal.

### 5.4 Publishing model (STEP 8)
```
AUTHOR ─▶ REVIEW (peer/security) ─▶ CI (run_all.py, 8 validators + bundle integrity) ─▶ APPROVE
       ─▶ PUBLISH (build immutable bundle, tag) ─▶ DEPLOY (ship bundle) ─▶ ACTIVATE (engine loads it)
```
Publication is `lifecycle.status = PUBLISHED` on rules (KB-001) plus a built, hashed bundle. Building is
deterministic: same commit ⇒ same content digest.

### 5.5 Versioning & pinning (STEP 7)
A runtime decision is reproducible because the bundle manifest pins **every** component version, not just
a commit SHA:

| Question | Answered by |
|---|---|
| Which bundle? | `bundle_manifest.bundle_version` + `content_digest` |
| Which commit produced it? | `bundle_manifest.commit_sha` |
| Which rule version ran? | each rule's `rule_version` (+ `schema_version`) inside the bundle |
| Which indicator registry / families? | `component_versions.indicator_registry` / `.indicator_families` |
| Which negative-indicator library? | `component_versions.negative_library` |
| Which taxonomy / dimensions? | `component_versions.taxonomy` / `.dimensions` |
| Which extraction contracts? | `component_versions.extraction_schemas` |
| Which evidence version supported a rule? | `component_versions.evidence_manifest` / `.evidence_records` + the rule's `source_references` |

Commit SHA is recorded but is **not** the only semantic identifier — the manifest's per-component
semantic versions + content digest are what a decision record pins, so the meaning survives repo moves.

### 5.6 Update / rollback model (STEP 8)
Bundles are immutable and content-addressed. Rollback = **activate the previous bundle** (N → N-1); no
knowledge file is mutated, and the audit record of what each earlier decision used is preserved because
that decision pinned bundle N's digest and component versions. No knowledge update silently changes the
meaning of an already-recorded decision (KB-001 §6, change-response playbook).

### 5.7 On-prem / offline (STEP 9)
The bundle is self-contained for deterministic evaluation. Runtime needs no GitHub, no advisory sites,
no package registry, no evidence-source network. The only network step in the whole pipeline is
`pip install` of pinned deps during CI/build — never at runtime.

### 5.8 Integrity & security (STEP 13)
- **Bundle integrity:** SHA-256 per file + a content digest over the sorted `(path, hash)` set in the
  manifest; `validate_bundle.py` recomputes and verifies, and checks the build is deterministic.
- **Evidence integrity:** unchanged — `manual_evidence_check.py` hashes the committed PDFs against
  `evidence-records.json` (ADR-0015).
- **CI protection:** `run_all.py` (now including bundle integrity) is the required gate; **main should be
  a protected branch** with the gate required and the self-test job green (an org/repo setting, recorded
  here as the intended control).
- **Signed releases:** a **reserved path**, not yet built. When bundles are distributed to third-party
  on-prem deployments, sign the manifest (e.g. cosign/minisign) and verify the signature at load. Not
  justified while distribution is internal; the content digest already gives tamper-evidence in-repo.

### 5.9 Database decision (STEP 10)
PostgreSQL is **not needed for knowledge itself** in Phase 3. Legitimate future uses — activation
records, decision/audit events, rule-usage analytics, deployment metadata — are **operational**, not
authoritative knowledge. If a materialized knowledge cache is ever added for admin queries:
- **authoritative = the bundle**, DB = a read-only materialization;
- **sync direction = bundle → DB only** (never DB → knowledge);
- **failure behaviour:** a stale/absent DB never blocks evaluation (the engine holds the bundle in
  memory); the DB is a convenience, not a dependency;
- **version pinning:** the materialization records the `bundle_version` + `content_digest` it reflects;
- **schema ownership:** owned by the operational service, never by the knowledge governance process.

### 5.10 Graph database (STEP 11)
**NOT JUSTIFIED.** The source → evidence → claim → indicator → rule chain is already represented
logically by IDs and references across the JSON, and is traversed in-process for explanation. No
TrustLens query requires graph traversal at MVP scale, and none is foreseen for the MVP. Status:
**NOT JUSTIFIED** now; *optional future* only if a genuinely graph-shaped query (e.g. large-scale
cross-rule impact analysis) ever appears — which would not change the source of truth.

### 5.11 Raw evidence storage (STEP 12)
Archived PDFs (~13 MB, 13 files) stay in Git for now — small enough that Git is adequate, and keeping
them versioned with the metadata preserves one-checkout reproducibility. They are referenced by a
**migration-safe, hash-addressed model already in place**: `evidence-records.json` names each file **and
its SHA-256**. Because references are by content hash, the physical location can move later —
**Git LFS** (if repo growth becomes a problem) or **hash-addressed object storage** — **without
invalidating any existing evidence record or rule**: the durable identity is the hash, not the path.
The current manually-retrieved evidence remains valid under any future physical store.

### 5.12 Admin-UI boundary (STEP 14)
A future admin UI may **view/search/review** rules and evidence and **propose** changes and drive the
publication workflow. This does **not** make a database authoritative: a UI proposal becomes a reviewed
**Git change** (or another governed, CI-gated workflow) before it is knowledge. The UI reads a
materialized cache for convenience and writes *proposals*, never authoritative rules. The boundary:
**authoring authority stays in the governed Git+CI workflow; the UI is a client of it.**

## 6. Consequences

- Git stays the single source of truth; review, CI and evidence-first traceability are preserved.
- Runtime gets a lean, deterministic, offline, hash-verified unit; "which knowledge ran" is fully
  answerable from a decision's pinned bundle manifest.
- A small, machine-checked publishing step is added (manifest schema + builder + integrity validator),
  wired into the existing gate. No authored knowledge changes; no database or graph store is introduced.
- Phase 3 is free to add operational Postgres/audit logging without touching knowledge authority.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Bundle drifts from source | Deterministic build + `validate_bundle.py` in CI (rebuild-and-verify every run) |
| "Just put it in Postgres later" erodes Git authority | ADR fixes DB as materialized/operational only, one-way sync |
| Repo bloat from evidence | Hash-addressed references make a later move to LFS/object storage non-breaking |
| Tamper between publish and load | Content digest now; reserved signed-release path for external distribution |

## 8. Reversal cost
**Low.** The authoring format is unchanged, so reversing to Option A (drop the bundle) or advancing to
Option C (add a runtime DB) are both additive: neither rewrites authored knowledge. The bundle is a
projection, discardable and rebuildable.

## 9. Validation plan
- `knowledge/schemas/bundle-manifest.schema.json` — the manifest contract (Draft 2020-12).
- `knowledge/publish/build_bundle.py` — deterministic builder (offline, no subprocess).
- `knowledge/publish/validate_bundle.py` — integrity validator: manifest schema-valid; every file hash
  matches; content digest reproducible (built twice); all component versions present; runtime bundle
  excludes raw PDFs and test data. Wired as the 9th check in `run_all.py`.
- No deployment infrastructure and no Phase-3 runtime service is built here (out of Phase-2 scope).

## 10. Change history
| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-08-29 | Initial ADR-0004. Option B selected: Git/JSON source of truth + immutable hashed runtime bundle; DB operational-only/materialized; graph not justified; evidence hash-addressed in Git with a migration-safe path; integrity via SHA-256 + reserved signing; admin-UI writes proposals not authority. Manifest schema + builder + integrity validator delivered and wired into CI. | Chief Architect |
