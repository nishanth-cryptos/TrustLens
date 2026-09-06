# ADR-0010 — Evidence storage and tamper-evidence mechanism

| Field | Value |
|---|---|
| Status | **Accepted** — approved by independent P5-WP3 review |
| Date | 2026-09-06 |
| Owner role | Chief Architect |
| Phase | Phase 5 — P5-WP3 persistence, evidence storage and tamper evidence |
| Related | [ARCH-003](../docs/05-architecture/ARCH-003-persistence-evidence-tamper-architecture.md), [GATE-014](../docs/00-program/GATE-014-phase-5-persistence-evidence.md), [ARCH-001](../docs/05-architecture/ARCH-001-enterprise-architecture.md), [ARCH-002](../docs/05-architecture/ARCH-002-python-runtime-service-topology.md), [ADR-0004](ADR-0004-knowledge-storage-architecture.md), [ADR-0007](ADR-0007-ai-authority-and-model-strategy.md), [ADR-0008](ADR-0008-python-runtime-service-topology.md), [ADR-0015](ADR-0015-evidence-hierarchy-and-official-alternate-provenance.md), [DET-001](../docs/03-detection/DET-001-deterministic-detection-engine.md), [AI-001](../docs/04-ai/AI-001-ai-intelligence-layer.md), [RSK-010/011](../docs/00-program/risk-register.md) |
| Reversal cost | **Medium** — contracts and portable content references limit coupling, but moving durable case history and integrity chains requires verified migration |

---

## 1. Context and constraints

TrustLens must retain original submissions while producing normalized and derived material (FR-010), pin the
knowledge used by each evaluation (FR-024), replay historical evaluations exactly (FR-037), and hash every
evidence item while recording custody metadata (FR-050). Cases, reports, secure export, append-only audit,
adjudication, and user export/deletion add relational, privacy, and lifecycle requirements (FR-051…054,
FR-062/063/065). The persistence boundary must also preserve deterministic results (NFR-001), TLS 1.3 and
AES-256 protection (NFR-006), exclusion of raw evidence, PII, and secrets from logs (NFR-007), auditable
history (NFR-010), and configurable retention/deletion (NFR-015).

RSK-010 treats submitted content as sensitive from ingest. RSK-011 requires strong evidence integrity and
reproducibility. OI-05 remains open: neither a retention duration nor a legal basis is decided here.

### 1.1 Two evidence domains must remain distinct

**Official/knowledge evidence** is government or advisory source material governed by ADR-0004 and ADR-0015.
Git, governed metadata, and immutable knowledge bundles remain its authority. **User-submitted case evidence**
is SMS, chat, email, URL, screenshot, user context, or later-supported attachment content submitted to
TrustLens. It is sensitive operational evidence governed by this ADR and **must never be committed to Git**.

PostgreSQL may record which immutable knowledge bundle was activated or consumed. It must never become the
source of truth for rules, indicators, taxonomy, official evidence provenance, or published bundles.

### 1.2 Scope

This ADR chooses logical persistence responsibilities and integrity mechanisms. It does not define SQL,
tables, migrations, ORM models, storage products, cloud resources, deployment, queues, APIs, report
presentation, identity/RBAC, keys, or retention law/policy. ADR-0008's Python modular-monolith topology and
the Phase-3/Phase-4 decision boundaries remain unchanged.

## 2. Decision

Select **Option A**:

1. **PostgreSQL** is the authoritative structured operational store for case, submission, evidence-manifest,
   evaluation, result, provenance, replay/report metadata, audit, workflow, and lifecycle records.
2. A vendor-neutral **`EvidenceContentStore` port** holds protected raw, binary, and other externalized content,
   plus immutable report or replay blobs where appropriate. Content is encrypted, private, digest-verifiable,
   application-authorized, deletable, and recoverable. A public object URL is never evidence authority.
3. **SHA-256** over well-defined bytes, immutable evidence manifests, append-only hash-chained audit events,
   and digest-pinned replay/report manifests provide tamper evidence.
4. Signed or independently anchored audit checkpoints are reserved for later security/deployment design when
   justified. P5-WP4 owns key management and P5-WP5 owns physical placement.

No object-store vendor is selected. PostgreSQL is selected because case/evaluation relationships, referential
integrity, transactions, indexing, structured and JSON provenance, and audit/report queries fit a relational
operational model with manageable small-team complexity. This is a suitability decision, not a measured
performance claim.

## 3. Data ownership and persistence authority

| Information | Logical authority | Persistence rule |
|---|---|---|
| Cases, submissions, evaluations and lifecycle state | Application/domain modules | PostgreSQL structured records |
| Raw or binary user evidence | Evidence module | Protected bytes in `EvidenceContentStore`; PostgreSQL manifest is the record identity and locator |
| Normalized/derived case content | Evidence/normalization module | Separate identified derivative; content store when externalized, structured metadata in PostgreSQL |
| Governed observations and indicator observations | Orchestration input artifact | Persist the exact governed artifact or a digest-verified reference used by Phase 3 |
| Completed `DetectionResult` | Phase-3 reasoning kernel | Persist exact canonical result plus digest; persistence does not redefine it |
| AI extraction provenance and replay snapshot | Phase-4 governance/integration | Persist exact governed provenance and artifact pins; AI owns no decision field |
| Reports and report manifests | Future reporting module | Immutable/revisioned artifacts and complete input pins; Phase 7 owns presentation format |
| Custody/security/governance events | Audit capability | Append-only PostgreSQL history with hash-chain fields and no raw content |
| Rules, indicators, taxonomy and official evidence meaning | ADR-0004 knowledge governance | Git and immutable bundles only; PostgreSQL records references/activation, never meaning |

## 4. Alternatives considered

| Option | Integrity and transactions | Binary/privacy handling | Query, replay and operations | Migration/reversal | Verdict |
|---|---|---|---|---|---|
| **A. PostgreSQL metadata + encrypted content store + cryptographic tamper evidence** | Relational constraints and local transactions protect structured state; manifests and digests bind the stores | Keeps large/sensitive bytes behind a narrow private port and independent lifecycle controls | Strong case/audit queries, exact pins, and a conventional operational store; cross-store reconciliation is required | Medium: port and portable locators reduce product coupling, but verified migration is still required | **Selected** |
| **B. PostgreSQL for metadata and all raw/blob content** | Simplest atomic metadata/content transaction and referential model | Large/binary content expands database backup, restore, access, and privacy blast radius | Good queries but operational database growth and recovery are coupled to evidence volume | Medium: extracting blobs later requires content migration and reference introduction | Rejected: simpler atomicity does not outweigh content-scale and recovery coupling |
| **C. Filesystem/blob store with metadata files and no operational database** | Weak multi-record transactions, referential integrity, concurrency, and append-only enforcement | Can store binaries privately, but isolation and lifecycle indexing become bespoke | Case, audit, deletion, and report queries plus recovery/reconciliation require custom machinery | Medium–High: later relational migration must reconstruct links and constraints | Rejected: unsuitable for required structured operational relationships and audit queries |
| **D. Document database as primary structured store** | Flexible provenance documents, but cross-document relationships and invariant enforcement need application logic | Handles variable records; large bytes still benefit from externalization | Flexible reads, but relational cases, custody, revision links, and audit reporting are less direct | Medium–High: changing the primary model affects most persistence contracts | Rejected: flexibility does not offset weaker fit for current relational integrity needs |

A graph database adds another authority/synchronization problem without a required graph workload and is not
part of the design.

### 4.1 Criterion-by-criterion comparison

| Criterion | A. PostgreSQL + content store | B. PostgreSQL including blobs | C. Files/content + metadata files | D. Document database |
|---|---|---|---|---|
| Integrity | Relational constraints plus digest-bound manifests | Strong database constraints for all records/bytes | Requires bespoke reference validation | Document validation helps locally; cross-document invariants remain application-owned |
| Transaction semantics | Strong local metadata transactions; explicit cross-store state/reconciliation | Single-store transactions are simplest | Weak multi-record atomicity without custom coordination | Document transactions vary by product/model; relationship updates remain less natural |
| Auditability | Append-only queryable events and chain fields fit structured records | Same audit strength, but audit recovery shares blob scale | Append-only enforcement and investigation tooling must be built | Event documents work, but custody joins and revision traversal need application discipline |
| Large/binary evidence | Purpose-built external content boundary | Database size, backup and recovery couple to evidence volume | Natural byte storage | Usually still benefits from external blob storage |
| Privacy/isolation | Narrow private content port and per-record authorization/lifecycle | Larger database privilege and backup blast radius | Isolation depends on filesystem/object conventions | Flexible documents can accidentally mix content/metadata without strict contracts |
| Backup/restore | Coordinated two-store backup with mandatory cross-reference/digest verification | One logical system, but potentially large and slow blob-inclusive recovery | Custom snapshot consistency and metadata reconstruction | Product-specific consistent backup plus external bytes if used |
| Queryability | Strong relational case, audit, deletion and report queries; JSON where justified | Same | Bespoke indexing/search required | Strong document retrieval; relational/custody queries are less direct |
| Operational complexity | Two stores and reconciliation, balanced by conventional relational core and portable port | One store to operate, with heavier growth/recovery coupling | Superficially simple, then custom consistency/indexing operations | One primary product, but team must operate and govern a less suitable relationship model |
| Replayability | Exact structured pins plus immutable artifact bytes | Exact pins/bytes can be transactional | Possible, but completeness/reference enforcement is custom | Possible with strict immutable documents and external pin discipline |
| Future scale | Metadata and byte capacity can scale independently when evidence justifies it | Structured and binary scale together | Byte scale is easy; metadata concurrency/query scale is weak | Horizontal document scale may help later, without current evidence for that cost |
| Migration/reversal | Medium; port limits content-product coupling, structured history still requires verified migration | Medium; later blob extraction is a substantial migration | Medium–High; relationships/constraints must be reconstructed | Medium–High; primary record model and query paths change |

## 5. Evidence identity and chain of custody

Every evidence record conceptually carries `evidence_id`, case/submission association, `content_sha256`, byte
length, declared media type, verified/normalized media type where applicable, ingest timestamp, governed
source/channel metadata, actor/component provenance, retention-class reference, protected storage locator,
and lifecycle state. Exact Phase-6 contracts may refine names and structure.

The digest identifies exact bytes; `evidence_id` identifies a TrustLens evidence record. SHA-256 is not a
public user-facing identifier. TrustLens does not globally deduplicate user evidence by digest: equal bytes in
two user or case contexts retain isolated records. Any future physical deduplication requires security/privacy
review and must preserve authorization, retention, and deletion isolation.

The ingest custody sequence is:

1. receive content and validate bounded input;
2. calculate SHA-256 over the precisely defined original bytes;
3. write the bytes to protected staging/final content storage;
4. read or otherwise verify the durable bytes against the digest;
5. transactionally finalize the immutable evidence manifest and lifecycle state in PostgreSQL;
6. append the custody event; and
7. reconcile controlled staged/orphan content after partial failure.

An idempotent operation token and explicit lifecycle state prevent duplicate retries. No record may claim
`VERIFIED` content that was not durably written and verified. The design does not assume distributed ACID.

Original evidence is never silently overwritten. Normalized text, OCR, redacted presentation, and other
derivatives receive their own identity and digest, `derived_from_evidence_id`, transformation identity/version,
creation time, and actor/component provenance. FR-010 therefore retains the original and makes each transform
independently verifiable.

## 6. Immutability and revisions

Once finalized, original digest/identity metadata, completed evaluations, `DetectionResult`, associated AI
provenance, replay artifacts, report manifest/bundle identities, and audit events are immutable or append-only.
Corrected extraction, analyst adjudication, user correction, regenerated evaluation, and report changes create
linked revisions. They never rewrite the meaning of a historical decision. Workflow, processing, and
retention/deletion workflow state may be mutable, with material transitions audited.

If the reasoning kernel computes a result but required persistence fails, the application reports a persistence
failure and does not claim durable case/report completion. It does not mutate result semantics or rerun the
engine to manufacture another result. An idempotent retry may persist the exact result artifact.

## 7. DetectionResult, Phase-4 provenance and replay

The completed authoritative Phase-3 `DetectionResult` is stored in its emitted canonical form with an integrity
digest. Persistence pins its evaluation and input identities, engine version, profile, knowledge-bundle version
and content digest, classification, emitted severity/risk/confidence fields, rule results, explanations/actions,
component provenance, and result digest. These are persistence concerns, not a redefinition of the Phase-3
contract. The stored artifact can be retrieved without recomputation and compared byte/canonical-value-wise
with replay.

When optional Phase-4 extraction was attempted or used, the record preserves the governed `config_ref`, AI
extraction result/audit identity, validated-extraction digest, exact governed consumed-artifact digest,
provider-neutral run/request identifiers already governed by AI-001, extraction confidence/review-required
metadata, and fallback state. It contains no model-owned decision fields and invents no numeric confidence.

A replay artifact contains or digest-verifiably references the exact governed artifact consumed by Phase 3,
engine version, profile, knowledge-bundle digest/version, evaluation identity, Phase-4 configuration/provenance
when used, and a digest over replay material. Historical replay verifies every pin and uses this exact material.
It must not call an AI provider, substitute latest knowledge, silently repair history, or translate an integrity
failure into `NO_SCAM_PATTERN` or `INSUFFICIENT_EVIDENCE`.

## 8. Report reproducibility and export

The report manifest pins case/evaluation identity, evidence IDs and digests, `DetectionResult` digest, engine
version, knowledge-bundle digest, relevant AI provenance/configuration, report-contract version, future
template/version, and stable generation metadata needed for deterministic reproduction. Phase 7 defines report
format; P5-WP3 guarantees the immutable inputs needed to reproduce it. Reports are revisioned and each revision
has its own manifest/bundle identity and digest.

User-owned evidence, evaluations, results, reports, corrections, and relevant audit metadata remain traversable
through explicit ownership links for an application-authorized export. FR-054/065 do not authorize a direct
storage URL or define an API/export format; those contracts belong to Phase 6/7.

## 9. Audit and tamper evidence

Security, governance, and custody audit is append-only. Candidate classes include `EVIDENCE_RECEIVED`,
`EVIDENCE_STORED`, `EVIDENCE_DERIVED`, `EVALUATION_STARTED`, `EVALUATION_COMPLETED`, `AI_ATTEMPTED`,
`AI_REJECTED_OR_FAILED`, `RESULT_PERSISTED`, `USER_CORRECTION`, `ANALYST_ADJUDICATION`, `REPORT_GENERATED`,
`REPORT_EXPORTED`, `DELETION_REQUESTED`, `CONTENT_DELETED`, `RETENTION_ACTION`, and `INTEGRITY_FAILURE`.
Later contracts own the exact taxonomy.

Each event conceptually records an event ID/type, timestamp, actor/service identity, applicable case,
evaluation and evidence references, correlation ID, non-sensitive structured metadata, previous-event hash,
and event hash. General audit events never contain submitted content.

Conceptually:

```text
event_hash = SHA-256(canonical_event_without_hash + previous_event_hash)
```

The exact canonical encoding and chain partitioning belong to later contracts. Hash chaining is
**tamper-evident**, not tamper-proof: a privileged operator able to replace the entire database and its trusted
root could rewrite a chain. Future signed or independently anchored checkpoints can make undetected wholesale
rewrite harder; P5-WP4/P5-WP5 must decide keys, trust anchor, cadence, and placement. This is not a blockchain
claim and creates no claim of legal admissibility or certified custody.

Evidence bytes/manifests, derivative-parent linkage, `DetectionResult`, replay material, report bundle/manifest,
audit-chain continuity, and knowledge-bundle digests are verified at high-value boundaries such as replay reads,
report generation/export, audit investigation, and restore verification. Exact frequency is operational detail.
Any mismatch is an explicit integrity/application failure and fails closed without altering Phase-3 semantics.

## 10. Retention and deletion

Persistence records configurable retention-class ID, policy/version, retention-basis metadata where governed,
expiry/delete-after only when supplied by future policy, and deletion state. Classes may distinguish case
evidence, derivatives, completed results, audit history, report bundles, and temporary/staged data; this ADR
assigns no durations or legal basis. OI-05 remains open.

Immutability does not authorize permanent sensitive-content retention. An authorized deletion evaluates policy,
enumerates the ownership/dependency graph, removes original and derived sensitive content plus indexes/caches,
verifies absence, and appends proof that the deletion action occurred. Remaining audit/tombstone data is limited
to the minimum non-content evidence permitted by the future policy/legal decision. This ADR does not decide
which metadata must remain. Cryptographic erasure may supplement deletion after key architecture exists, but it
is not the sole mechanism and is not selected here.

## 11. Cross-store consistency, backup and recovery

PostgreSQL and the content store use explicit states, idempotent operations, durable digest verification, and
reconciliation instead of a distributed transaction. Controlled reconciliation detects staged/orphaned objects,
missing objects, incomplete manifests, and digest mismatches; it finalizes only provably complete operations and
otherwise quarantines/fails them with a non-sensitive audit event.

Backup/restore must jointly preserve relational consistency, evidence objects, content digests, manifest
references, audit chain, replay/report artifacts, and required key references. Recovery is incomplete until
integrity checks validate cross-store references, object and artifact digests, knowledge pins, and audit-chain
continuity. No RPO or RTO is selected.

## 12. Security and privacy

- Treat raw user evidence as restricted/highly sensitive and normalized/derived evidence, observations, and
  reports as sensitive. Operational metadata and content-free audit metadata are internal. Governed
  public/internal knowledge follows ADR-0004/0015; these are architectural labels, not statutory claims.
- Preserve TLS 1.3 in transit and AES-256 at rest. Protect backups to the same sensitivity level.
- Use least privilege and separate credentials/roles, with all evidence access mediated by application
  authorization. P5-WP4 defines identity, RBAC, secrets, and key management.
- Do not store application credentials, encryption keys, provider secrets, or other operational secrets in
  PostgreSQL records or evidence content. P5-WP4 defines their protected mechanism.
- Logs, metrics, traces, errors, and general audit may contain IDs, statuses, durations, correlation IDs, and
  safe categorical error codes. They may not contain raw evidence, message or AI-response bodies, OTP/PIN,
  PAN/account data, secrets, or PII.
- Storage locators are internal references rather than public authority. Export is controlled and audited.

## 13. Consequences

### Positive

- Strong relational integrity and queryability cover cases, revisions, audit, replay, report, and deletion.
- Large/sensitive bytes have a narrow protected boundary and independent lifecycle/backup treatment.
- Exact artifact and version pins preserve deterministic historical replay and report inputs.
- The content-store port avoids premature vendor choice and supports later migration.

### Costs and limitations

- Cross-store writes require state machines, idempotency, reconciliation, and joint recovery testing.
- Two persistence technologies increase operational and backup complexity over one database.
- Digests detect alteration relative to trusted pins but do not authenticate actors or prevent privileged
  wholesale history replacement without a separate checkpoint trust anchor.
- OI-05 blocks final retention/deletion policy. Identity, keys, physical deployment, migration tooling, API
  contracts, and report format remain future work.

## 14. Risks and mitigations

| Risk | Architectural response |
|---|---|
| Sensitive content leaks through logs, locators, exports, or backups (RSK-010) | Private application-mediated access, encryption, safe telemetry, controlled export, least privilege and protected backups |
| Content and manifest diverge after partial failure (RSK-011) | Hash before/after durable write, explicit lifecycle, idempotency, reconciliation and fail-closed verification |
| Privileged rewrite defeats a database-only hash chain | Admit the limit; preserve trusted chain roots and reserve signed/external checkpoints |
| Deletion misses normalized/OCR/redacted/report/cache copies | Explicit derivative and ownership graph, dependency enumeration, deletion verification and audited proof |
| PostgreSQL becomes a second knowledge authority | Store bundle references/activation only; ADR-0004 Git/bundle authority is invariant |
| Replay uses current knowledge or calls AI | Require exact pinned artifact/config/bundle; refuse missing or mismatched history |

## 15. Reversal cost

Reversal cost is **Medium**. The conceptual `EvidenceContentStore` port, immutable portable artifacts, and
digest-based references support swapping the physical content product. Moving PostgreSQL structured history to
another database is more expensive because referential, revision, lifecycle, and audit-chain constraints must
be migrated and verified. Combining content into PostgreSQL or separating additional stores requires an ADR,
dual-read/verification planning, and proof that every historical digest and ownership link survives.

## 16. Validation plan

Before acceptance:

1. an independent reviewer validates requirements traceability, alternative comparison, data authority,
   integrity limits, deletion/replay behavior, and deferred boundaries;
2. ARCH-003 and GATE-014 remain consistent with this proposal;
3. canonical validation returns 23/23 PASS and CI self-test catches 7/7 representative defects;
4. the Phase-3/Phase-4/runtime/schema/rule/taxonomy freeze has zero diff and `ENGINE_VERSION` remains `1.0.0`;
5. remote CI passes where triggered; and
6. approved changes merge to `main`.

This proposal makes no accuracy, precision, recall, false-positive/negative rate, evidentiary admissibility,
legal chain-of-custody certification, real-world detection-effectiveness, or production-readiness claim. G-09
remains OPEN.
