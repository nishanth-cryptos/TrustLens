# DATA-001-WP2 addendum P9-S2-ADD-001: evidence upload intent and idempotency supersession

| Field | Value |
| --- | --- |
| Status | **APPROVED FOLLOWING INDEPENDENT REVIEW — ACTIVATED BY P6-SNAPSHOT-REV-001 — REMOTE CI + MERGE PENDING** ([GATE-033](../00-program/GATE-033-p9-s2-add-001-persistence-revision.md)). Approved in principle by the sponsor on 2026-10-14; the final independent review returned APPROVE with 0 remaining material findings. Not applied to the sponsor's database |
| Status history | 2026-10-14 CANDIDATE (not independently reviewed) → 2026-10-14 approved following independent review (GATE-033) |
| Change class | **Additive, with one governed constraint relaxation** (§2.3), explicitly approved by the independent review. It is not a purely additive change |
| Extends | `contracts/postgresql/schema-v1.json` (DATA-001-WP2 0.2.0), pinned by SHA-256 in the machine addendum; the base is unchanged |
| Machine addendum | [`contracts/postgresql/schema-v1-addendum-p9-s2-add-001.json`](../../contracts/postgresql/schema-v1-addendum-p9-s2-add-001.json): the artifact that becomes authoritative on activation |
| Resulting version | DATA-001-WP2 0.3.0, on activation. The effective 0.3.0 contract is composed from 0.2.0 and the machine addendum and validated against the actual structural schema (`knowledge/validation/validate_phase6_snapshot_revision.py`) |
| Snapshot revision | Accepted forward Phase-6 snapshot revision `P6-SNAPSHOT-REV-001` ([`contracts/phase6/phase6-snapshot-revision-p9-s2-add-001.json`](../../contracts/phase6/phase6-snapshot-revision-p9-s2-add-001.json)); the original Phase-6 closure snapshot stays byte-for-byte unchanged |
| API impact | **None.** API-001, OAS-001, `api-v1.json` and `openapi-v1.json` are unchanged; `client_declared_sha256` stays optional |
| Candidate implementation | Migration `apps/backend/migrations/versions/0004_evidence_intake.py` (not applied to any persistent database) |

## 1. Why an addendum is needed

1. **Evidence before bytes.** API-001 §12 creates the evidence item before any bytes exist, and the server computes
   the authoritative SHA-256 only at PUT. DATA-001-WP2 makes `evidence_item.content_sha256` and `byte_length`
   NOT NULL, and has no column for `display_filename` or `declared_byte_length`.
2. **Idempotency expiry.** OPS-001 §5 says a key reused after `active_until` is a new request. But
   `api_idempotency_record` makes its scope columns write-once, and `uq_api_idempotency_scope` covers the full scope
   with no expiry term. A fresh claim is therefore impossible unless the governed record is deleted, which the
   application role cannot and should not do.

`relationship_to_content` is not part of this addendum. It already lives on `submission` and is persisted there; no
case-level column is added.

## 2. Changes (the machine addendum is exact)

### 2.1 New table `evidence_upload_intent` (additive; OPS, M-OPS, governed deletion only)

- **Identity:** its primary key is the API `evidence_id`.
- **Columns:** it records the server-derived initiating principal, the submission, `artifact_kind`,
  `declared_media_type`, `declared_byte_length`, and optional `display_filename` (untrusted, ≤ 255, never a path),
  `capture_declared_at` and advisory `client_declared_sha256`. It also holds an internal `idempotency_key` shared with
  the `EVIDENCE_INGEST` operation and the later `evidence_item`, plus `intent_state`, `last_rejection_category` and
  `evidence_item_id`.
- **Transition:** `OPEN → MATERIALIZED` only, in the same transaction that inserts the `evidence_item` with the same
  identifier. CHECKs enforce `MATERIALIZED ⇔ evidence_item_id IS NOT NULL` and identical identity.
- **Rejections:** a rejected PUT (length mismatch, digest mismatch, invalid media, oversize) is recorded in
  `last_rejection_category` without changing the state, so the client can resend the exact declared bytes.
- **Byte definition `TL_EVIDENCE_BYTES_V1`:** the exact PUT body bytes, untransformed.
  `evidence_item.byte_definition_version` records it.

### 2.2 Contract tables created by migration 0004

`evidence_item` and `cross_store_operation` are created exactly as in `schema-v1.json`. One transition guard is added
to `cross_store_operation` (§4, attempt fencing); it uses existing columns only.

### 2.3 `api_idempotency_record`: governed constraint relaxation `P9-S2-ADD-001-REL-01`

- Adds a write-once column `superseded_at` (additive).
- **Relaxes** `uq_api_idempotency_scope` from `UNIQUE (principal, operation, target, key digest)` to the same columns
  `WHERE superseded_at IS NULL`. This is a relaxation of an approved constraint and is **not additive**. The independent
  review accepted it explicitly (GATE-033).

A key reused after `active_until`:
1. marks the old record superseded (compare-and-swap, only while `active_until <= now()` and it is not yet superseded);
2. inserts a fresh claim, in the same transaction.

**Preserved invariants**
- At most one governing record per scope at any instant. The partial unique index still serializes concurrent claims
  (`INSERT … ON CONFLICT`, never check-then-insert).
- Inside the 24 h window nothing changes: replay, `IDEMPOTENCY_KEY_REUSED` and `IDEMPOTENCY_IN_PROGRESS` behave as in
  P6-WP6.
- A record is superseded at most once, only after its own `active_until`. A superseded record is immutable and never
  governs again.
- Only key digests are stored. There is no cached response, no DELETE grant and no deletion by the request path.
- Completion stays fenced by `claim_token` and atomic with its effect.

**Migration compatibility**
- Every existing 0003 row has `superseded_at` NULL, so it satisfies the partial index exactly as it satisfied the
  full constraint.
- 0004 adds the column, drops the constraint and creates the same-named partial unique index in one migration
  transaction, so there is no window without uniqueness.
- On a 0003 database the application keeps full-scope semantics: an expired key is refused as
  `IDEMPOTENCY_KEY_REUSED`, which is stricter than OPS-001 §5, and evidence intake stays disabled.
- There is no automatic downgrade. Restoring the full constraint is lossless only while nothing is superseded.

## 3. Resolution rules (no ambiguity)

- **Reads:** every `evidence_id` has exactly one intent. `getEvidenceMetadata` and `listEvidence` read the intent and
  left-join the `evidence_item` with the same identifier.
- **`upload_state`:** the `api_upload_state` mapping of `evidence_item.content_state`, or `AWAITING_CONTENT` while
  the intent is `OPEN`.
- **Field sources:** digest, length, verified media type and finalization instant come only from `evidence_item`;
  declared values, `display_filename` and `ingested_at` come only from the intent.
- **PUT:**
  - the first accepted PUT materializes;
  - an identical re-PUT is a no-op on stored content. It answers `503` with `Retry-After` while another attempt holds
    a live lease, and resumes an interrupted write after that;
  - different bytes after content exists return `409 STATE_CONFLICT`.
- **Finalize:** returns `202`. It re-reads, decrypts and verifies digest, length and media, then moves
  `INTEGRITY_VERIFIED → FINALIZED` with the custody audit in one OPS transaction. A failed verification becomes
  `INTEGRITY_FAILED` plus an `INTEGRITY_FAILURE` audit event, never `FINALIZED`. No PostgreSQL transaction covers
  the content store (§19).

## 4. Retry, concurrency, reconciliation and cleanup

- **Attempt fencing:** `cross_store_operation.attempt_count` is the durable fencing token of a content write.
  - Each attempt takes the next number by compare-and-swap, together with a 30 s lease. During `CONTENT_PENDING`,
    `next_attempt_not_before` holds that lease.
  - The encrypted object is written outside any transaction.
  - An attempt records `CONTENT_STORED`, `FAILED_RETRYABLE` or `FAILED_TERMINAL` only with a conditional update
    `WHERE attempt_count = <its number> AND state = 'CONTENT_PENDING'`.
  - A stale attempt (one that outlived its lease and was taken over) therefore changes nothing. A stale failure cannot
    undo a newer success, and a stale success cannot replace a newer attempt's object.
  - The database refuses any `attempt_count` change other than `+1`.
  - A fenced-out attempt reports the authoritative state: `200` if the content is stored, otherwise `503` with
    `Retry-After`.

- **Retries:** a failed content write sets `FAILED_RETRYABLE` with `next_attempt_not_before` (backoff 1–30 s). A
  retry is a re-PUT of identical bytes. After 3 attempts the state becomes `FAILED_TERMINAL` (always through
  `FAILED_RETRYABLE`, as the §11 state machine requires), shown as `REJECTED`.
- **Abandoned intents** stay `OPEN`, and `ix_evidence_upload_intent_open` lists them for reconciliation. There is no
  automatic cleanup period (UX-002#5, OI-05), and no row is deleted outside governed deletion.
- **Orphaned content:** content written whose metadata commit then failed is never adopted silently. The item stays
  `CONTENT_PENDING` until an identical re-PUT completes, which writes a fresh object. The earlier object stays as
  unreferenced ciphertext. Orphan reconciliation (`ORPHAN_RECONCILIATION`) is a later `tl_reconciler` capability.

## 5. Activation

1. **Done:** independent review of this addendum, the machine addendum, relaxation `P9-S2-ADD-001-REL-01`, migration
   0004 and the snapshot revision. The final verdict was APPROVE (GATE-033).
2. **Done in this branch:** snapshot revision `P6-SNAPSHOT-REV-001` is ACCEPTED, with GATE-033 pinned. The original
   Phase-6 snapshot, `schema-v1.json`, the DATA-001-WP2 document and the API/OAS contracts are **not** edited.
3. **Pending:** the sponsor's own pull request, remote CI and merge. The revision becomes repository authority on merge.
4. **Pending, after merge:** the sponsor creates the evidence key, reviews `make migration-sql`, then runs
   `make migrate`.

**Known limitation (carried):** the structural schema only admits additive-revision ids of the form
`P6-WPn-ADD-nnn`. The effective 0.3.0 contract therefore records this revision in its `status` and in the snapshot
revision, not in `additive_revisions`. Widening that pattern would be a separate governed structural-schema change.
