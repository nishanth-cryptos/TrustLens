# S8 Screenshot/OCR — Governance Decision Proposal (D1–D9)

| Field | Value |
| --- | --- |
| Status | **SPONSOR SCOPE DIRECTION RECORDED — TECHNICAL APPROVALS PENDING; S8 IMPLEMENTATION BLOCKED** |
| Programme | TrustLens, Phase 9, Slice 8 (S8) |
| Baseline | `main` at `0f82ea631af24753f4c71bafe29d0ac61e96ccd2` (read on 2026-10-15) |
| Scope | Synthetic local-development profile only; backend/API first; default OFF |
| Decision owners | Sponsor/Product; Security/DevSecOps; Backend/Operations; Data; Knowledge/Detection |
| Sponsor scope decision | **User-declared approval received 2026-10-15** for synthetic-local, backend-first, default-OFF S8 scope; not an independently authenticated GitHub reviewer sign-off. See §3. |
| Implementation authority | **None granted by this proposal.** No runtime, migration, API, UX or policy change is approved here. |
| Independent review | Draft PR #53 at `45573e78b58764947e94630eddd60b8e17d41bac`: Codex **REQUEST_CHANGES** (0/0/1/0/0). MEDIUM-1 (confidence compatibility) is **OPEN**; see §3. |

## 1. Authority and non-negotiable boundaries

This is a reviewable **proposal with a recorded user-declared Sponsor/Product scope direction**, not an independent technical approval or implementation authorization. It responds to the S8 readiness STOP report (G1–G6) without changing frozen contracts.

- [PLAN-001 §4](PLAN-001-implementation-blueprint.md) makes S8 dependent on S4–S7, an accepted media profile, a least-privilege worker and bounded resources. An unresolved OCR dependency remains **BLOCKED** for that scope.
- [S2 local profile](S2-local-development-profile.md) currently accepts `text/plain; charset=utf-8` only (64 KiB) and **no images**. That profile must remain unchanged.
- [UX-002 §3](../07-ux/UX-002-submission-evidence-intake.md) marks `SCREENSHOT_IMAGE` / `IMAGE` **POST_MVP / offered: no**. No screenshot picker or camera is authorized by this proposal.
- [API-001 §§12–13](../06-contracts/API-001-api-resource-protocol-contract.md) already permits configuration-governed media validation (`413` / `415`) and one evaluation per governed input envelope, including a separate OCR-derived envelope. No case/submission aggregate verdict and no new API operation are proposed.
- [DATA-001 §§5.4–5.7](../06-contracts/DATA-001-data-domain-lifecycle-contract.md) and [DATA-001-WP2](../06-contracts/DATA-001-WP2-postgresql-persistence-contract.md) require original/derivative immutability, exact parent lineage and content outside OPS. [OPS-001 §16](../06-contracts/OPS-001-operational-replay-persistence-contract.md) makes security/correctness limits fail-closed.
- [ARCH-004 §9.1](../05-architecture/ARCH-004-security-trust-threat-model.md), [ARCH-005 §6](../05-architecture/ARCH-005-deployment-resilience-recovery.md) and [ADR-0016](../../adr/ADR-0016-deployment-resilience-runtime-topology.md) require untrusted-media isolation, bounded work and no unrestricted filesystem, network, database, secrets or host privilege.

The original screenshot is never modified, interpreted as an instruction, fetched as a URL, scanned for executable QR actions, or used to change the deterministic detection kernel. OCR output is **untrusted extracted text**, not a safety determination.

## 2. Proposed decisions — owner acceptance required

All nine technical/governance decision packages remain **PROPOSED**. Sponsor/Product scope direction has been recorded for the PNG-only local-test intent in D1 and the default-OFF backend-first scope in D5; it does **not** close the independent reviews or authorize coding.

### D1 — Media profile (G1)

**Proposal:** Introduce a *separate S8 synthetic-local opt-in profile* accepting exactly `image/png`, with `artifact_kind=IMAGE`. Admit a single-frame, non-interlaced, 8-bit RGB or RGBA PNG only. Refuse APNG/multi-frame, unsupported bit depths/color modes, malformed/truncated chunks, CRC errors, trailing content and polyglots. Check declared MIME against actual structural type; file extension is not authority. Preserve original bytes and digest exactly; do not propagate ancillary metadata to the OCR text derivative. Do not enable JPEG, PDF, camera capture or other media.

**Approval:** Sponsor/Product scope direction recorded 2026-10-15 (user-declared; see §3); Security/Backend acceptance of the exact format and parser threat model **PENDING**. The current S2 text-only profile remains the default.

### D2 — Resource and admission limits (G2 / T09)

These are deliberately conservative **candidate local-test values**; they are **not** approved OPS-001 settings or production limits.

| Parameter | Proposed bound | Enforcement / failure |
| --- | --- | --- |
| Original PNG upload | 2 MiB (2,097,152 bytes) | Declared length and streamed body; exceed → `413 PAYLOAD_TOO_LARGE` |
| Width and height | Each 1–4,096 pixels | Header/structural preflight; invalid → `415 UNSUPPORTED_MEDIA_TYPE` |
| Total pixels | At most 8,000,000 | Reject before decoder invocation |
| Decoded image budget | At most 32 MiB (33,554,432 bytes) | Enforce within isolated decoder; fail closed |
| OCR wall-clock | 10 seconds per attempt | Kill worker on deadline; explicit failure |
| Worker CPU / memory / PIDs | 1 CPU / 256 MiB / 32 PIDs | Container-enforced limits; refuse if unavailable |
| OCR concurrency | One running job per local instance | Bounded dispatch, no unbounded queue |
| OCR text output | At most 64 KiB UTF-8 | Bounded read; reject oversized/invalid output |
| Images per submission | One | Reject second image; no silent truncation |
| Retries | Zero automatic OCR retries in S8a | No duplicate or runaway work |

Use overflow-safe checks; never trust declared sizes, metadata, image dimensions or decoder output alone. A smaller operational limit may be chosen after review, but an increase requires an approved profile revision. Limits must be proven under the actual container/runtime; documentation alone is insufficient.

**Approval:** Sponsor, Backend/Operations and Security. Product confirms upload limits/copy for any future UI.

### D3 — Worker isolation (G3)

**Proposal:** One disposable Docker worker container per OCR attempt, using a reviewed **digest-pinned image** and a fixed command, with: `--network none`, `--read-only`, non-root UID/GID, `--cap-drop ALL`, `--security-opt no-new-privileges`, bounded CPU/memory/PIDs, bounded `tmpfs` scratch and a deadline. Pass bounded image bytes on stdin; accept bounded UTF-8 OCR text on stdout. No user-supplied shell arguments, host bind mounts, database access, credentials, secret environment, network access or URL/QR execution.

**Critical launcher boundary:** The web/API process must **not** receive the Docker socket or arbitrary container-launch privileges. A separately trusted launcher must expose only the fixed OCR operation through bounded IPC; its privilege boundary and failure handling require independent Security/DevSecOps review. Host subprocess isolation alone is **not** accepted for S8a. Refuse to enable OCR if these controls cannot be demonstrated on the selected local Docker environment.

**Approval:** Security/DevSecOps and Backend/Operations; test network denial, filesystem denial, no secrets, limits and worker termination.

### D4 — OCR engine and dependency supply chain (G4)

**Proposal:** Evaluate **Tesseract 5.5.2, English (`eng`) only**, as a *candidate*; no installed Homebrew executable is trusted as a runtime dependency. Before selecting it, record the exact OCR binary version, `eng` trained-data digest, container base/image digest, licenses, vulnerability review, SBOM/lock evidence and reproducible build procedure. All real image decoding stays in the isolated worker; the application preflight does not invoke an image-decoder library.

If an approved digest or vulnerability disposition cannot be produced, **D4 remains OPEN and S8 OCR stays OFF**. No multilingual accuracy, production performance or security certification is claimed.

**Approval:** Security/Supply Chain, Backend and Sponsor.

### D5 — Scope and UX (G5)

**Proposal:** S8a is **backend/API only**, for explicitly enabled synthetic-local testing. A feature flag is **OFF by default**; the existing S2 profile and production-like/default startup reject images as before. The browser continues to follow frozen UX-002 (`SCREENSHOT_IMAGE` not offered). Synthetic tests may exercise the existing evidence and evaluation API operations under the opt-in profile. No camera, screenshot picker, preview, new UX wording or frontend workflow is added.

A later user-facing S8b requires a separately approved additive UX revision and Product/Sponsor scope decision; do not silently edit frozen Phase-7 contracts.

**Approval:** Sponsor/Product S8a scope direction recorded 2026-10-15 (user-declared; see §3); independent Security sign-off **PENDING**. S8b remains out of scope and would require a new Product/Sponsor and UX owner decision.

### D6 — OCR lineage, type and uncertainty

**Proposal:** Store original evidence as `artifact_kind=IMAGE`; store an immutable `OCR_TEXT` derivative with exactly one original parent, transformation identity/version and its own digest. The server assigns the derived envelope `input_type=SCREENSHOT_DERIVED_TEXT` and attachment role `SCREENSHOT`, with a new `input_id`.

`declared_input_type` is a **submission** field (`SubmissionCreateRequest`); evidence items carry only `artifact_kind`. The derived envelope's `input_type` is never taken from the submission declaration. Which `declared_input_type` a screenshot-bearing submission declares is a D9 decision.

**Proposed extraction-confidence input (not a detection-confidence policy):** Until Knowledge/Detection approve a calibrated mapping, observations in the **OCR-derived envelope only** would carry extraction `confidence` **LOW**, never promoted to MEDIUM/HIGH from unverified engine confidence. This is observation-level extraction confidence (`observation.schema.json` / `indicator-observation.schema.json`). It is not `detection_confidence`, which the kernel computes. With the pinned `extraction_confidence_gate` MEDIUM, the existing evaluator treats a LOW occurrence as UNKNOWN, never FALSE.
- It does not cap, set or clamp any `detection_confidence`, and it does not set `degraded`.
- It never applies to the text envelope.
- It is not a confidence policy for mixed inputs (D7).

Unreadable/ambiguous text is UNKNOWN or explicitly unsupported, never FALSE; an empty OCR result is not evidence of safety. Preserve extraction limitations and provenance. No new kernel rule, vocabulary or decision axis.

**Approval:** Knowledge/Detection owner for the mapping, **before** any OCR-derived envelope code is implemented (§4); Data/Backend for exact lineage and envelope semantics. Any stronger confidence thresholds need separate review.

### D7 — Failure and response behavior

**Proposal:** Keep accepted HTTP and evaluation contracts; do not invent a public OCR endpoint or a normative OCR error code.

- Malformed/unsupported PNG → `415 UNSUPPORTED_MEDIA_TYPE`; oversize → `413 PAYLOAD_TOO_LARGE`; neither reaches the decoder.
- Screenshot-only, OCR unavailable *before acceptance*: fail the affected operation with the existing dependency-unavailable semantics if applicable; create no fake completed result. If work has already been accepted, record a categorical failed/whole-evaluation error with support `ERROR` and no `NO_SCAM_PATTERN` result.
- Text plus screenshot, OCR fails: **BLOCKED** — see *Mixed-input OCR failure* below. No behavior is proposed for this path until the Knowledge/Detection disposition exists.
- OCR timeout, worker crash, malformed output or lineage integrity failure: explicit failure and audit-safe metadata; never success, `NO_SCAM_PATTERN`, `CLEAN` or a safety claim.

The API owner must verify the precise pre-acceptance dependency error and asynchronous state mapping against accepted error enums **before coding**. Do not add `OCR_UNAVAILABLE` as a normative public code without governance.

#### Mixed-input OCR failure — BLOCKED pending Knowledge/Detection disposition (MEDIUM-1)

**Input coverage and detection confidence are different axes.**
- **Input coverage:** `input_support_status` (`PARTIALLY_SUPPORTED`) records that a required channel is missing.
- **Detection confidence:** `detection_confidence` is computed by the existing kernel. In `knowledge/runtime/aggregation.py`, `_detection_confidence` does not read `input_support_status`. It depends on the governing rule's evidence verdict, ambiguities, the extraction-confidence inputs of matched indicators, the proven independent-evidence count or active overrides, and context-only suppression. Separately, `degraded=true` caps it at MEDIUM. `PARTIALLY_SUPPORTED` executes rules exactly as `SUPPORTED` does (`_EVALUABLE_SUPPORT` in `result.py` / `explanation.py`).
- **Consequence:** the existing kernel and result contract permit `input_support_status=PARTIALLY_SUPPORTED` with `classification=SCAM_PATTERN_DETECTED`, `detection_confidence=HIGH` and `degraded=false`. Setting `PARTIALLY_SUPPORTED` therefore does **not** cap confidence.
- **DET-001 §3:** its "cap confidence" consequence for `PARTIALLY_SUPPORTED` is not realized by the kernel for that state. This proposal neither resolves nor reinterprets that difference.

**This proposal does not:**
- introduce a confidence policy or threshold;
- set `degraded=true` to obtain a cap;
- clamp, rewrite or post-process a returned `DetectionResult`;
- change Phase-3 semantics.

**Required before implementation:** a **Knowledge/Detection-approved confidence policy and kernel-compatibility disposition** for the text-plus-screenshot OCR-failure path. The disposition must state how DET-001 §3's confidence consequence applies to `PARTIALLY_SUPPORTED`, and through which governed change, if any; or else that the path stays unsupported. It is required **before** the mixed path is implemented, not at profile activation.

**Until that approval exists:**
- the mixed-input failure path is **BLOCKED** and has no implementation;
- the opt-in profile must not substitute a successful text-only evaluation for a text-plus-screenshot submission, or present it as evaluating the whole submission;
- such a submission is refused under existing accepted refusal semantics, verified by the API owner as above, rather than evaluated text-only. No new code, field or status is introduced for this.

The existing text-only pipeline (one `TEXT_BODY` → one envelope → one evaluation, S5) is unchanged.

**Approval:** API/Backend and Knowledge/Detection, with Security reviewing fail-closed cases. The mixed-input disposition is owned by **Knowledge/Detection**.

### D8 — Timing, idempotency, corrections and replay

**Proposal:** Run OCR at `createEvaluations` time, not at `finalizeEvidence`: FINALIZED means the original bytes are durably stored and verified, not that OCR succeeded. Reuse a previously FINALIZED derivative only when the **same evidence item, original digest, OCR engine/image digest, language, transformation identity/version and configuration digest** match; otherwise create a new derivative. Verify encrypted ECS bytes by digest before recording FINALIZED, then record content-free `EVIDENCE_DERIVED` audit metadata. An interrupted cross-store operation is reconciled without duplicate authoritative derivatives.

Historical replay verifies the pinned derivative's parent, state and exact bytes/digest and **never reruns OCR**. Corrections consume the pinned derivative rather than silently re-OCRing under a newer engine. Missing/altered source is an integrity/unavailable outcome, not a replacement.

**Approval:** Data/Backend/Audit; independent review of the minimal `0009` derivative-write grant against existing column-level permissions. Do not apply any migration until reviewed.

### D9 — Submission composition

**Proposal for S8a synthetic-local tests only:**

| Submission | Evidence items | Governed input envelopes on successful OCR | Result behavior |
| --- | --- | --- | --- |
| Existing text-only | One `TEXT_BODY` | One text envelope | Exactly the S5 behavior; no regression |
| Screenshot-only | One `IMAGE` | One OCR-derived envelope with a new `input_id` | One evaluation; OCR failure follows D7 |
| Text plus screenshot | One `TEXT_BODY` + one `IMAGE` | One text envelope + one OCR-derived envelope | **BLOCKED** (D7 mixed-input disposition). If approved: one evaluation **per** envelope; no aggregate verdict |

**Mixed composition is not activatable in S8a while D7's mixed-input disposition is open.** OCR failure cannot be known before the attempt. Until Knowledge/Detection approve that disposition, a text-plus-screenshot submission under the opt-in profile is refused as D7 describes. It is never evaluated text-only as if the whole submission had been evaluated. Screenshot-only and text-only rows are unaffected.

No URL/email/image mixture beyond these combinations is activated in S8a. Existing URL and enrichment paths remain unchanged and never fetch content from an image. Any input-count or lifecycle changes require API/Data owner sign-off before implementation.

Evidence items carry `artifact_kind` (`TEXT_BODY`, `IMAGE`); `declared_input_type` belongs to the submission. The `declared_input_type` a screenshot-only or mixed submission declares is **OPEN** for the API/Data owner. The OCR-derived envelope's `input_type` (`SCREENSHOT_DERIVED_TEXT`, D6) is server-assigned and is not taken from that declaration.

**Approval:** Product/Sponsor and API/Data/Backend; Knowledge/Detection for the mixed text-plus-screenshot row (D7).

## 3. Readiness gates and open blockers

| Gap | What closes it | Accountable approval |
| --- | --- | --- |
| G1 — Media profile | D1 and D5 signed; S8 opt-in profile documented; default S2 remains text-only | Sponsor/Product + Security |
| G2 — Resource limits | D2 signed; limits enforced and adversarially tested | Sponsor + Backend/Operations + Security |
| G3 — Isolation | D3 signed; trusted launcher and actual container isolation demonstrated | Security/DevSecOps |
| G4 — Engine | D4 pinned version/image/trained-data digests and supply-chain review | Security + Backend + Sponsor |
| G5 — Post-MVP activation | User-declared synthetic-local scope approval recorded; verify accountable sponsor attestation before gate closure; S8b UI separately deferred | Sponsor/Product (attestation pending) |
| G6 — Derivative writes | Reviewed, least-privilege migration `0009`, only after D8 approval | Data + Security |

**Decision ledger (unfilled by design):**

| Decision | Current state | Owner decision / evidence reference |
| --- | --- | --- |
| D1 | SPONSOR SCOPE DIRECTION RECORDED; TECHNICAL OPEN | PNG-only synthetic-local intent accepted by requester on 2026-10-15; Security/Backend and formal attestation pending |
| D2 | PROPOSED | PENDING |
| D3 | PROPOSED | PENDING |
| D4 | PROPOSED | PENDING |
| D5 | SPONSOR SCOPE DIRECTION RECORDED; TECHNICAL OPEN | Backend-first, synthetic-local, default OFF, no UI accepted by requester on 2026-10-15; Security and formal attestation pending |
| D6 | PROPOSED | PENDING — Knowledge/Detection extraction-confidence mapping required before OCR-envelope implementation |
| D7 | PROPOSED; mixed-input OCR-failure path **BLOCKED** | PENDING — Knowledge/Detection confidence policy and kernel-compatibility disposition required before implementation (MEDIUM-1) |
| D8 | PROPOSED | PENDING |
| D9 | PROPOSED; text-plus-screenshot row **BLOCKED** | PENDING — submission `declared_input_type` for screenshot-bearing submissions OPEN (API/Data) |

### Independent review findings

| Finding | Review provenance | Owner | Status |
| --- | --- | --- | --- |
| MEDIUM-1 — Confidence compatibility. The kernel permits `PARTIALLY_SUPPORTED` + `SCAM_PATTERN_DETECTED` + `detection_confidence=HIGH` + `degraded=false`, so the earlier D7 wording ("cap confidence") was incorrect. | Codex independent review of Draft PR #53 at `45573e78b58764947e94630eddd60b8e17d41bac`: REQUEST_CHANGES, BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 0 / INFO 0, recorded as a GitHub PR comment (as reported by the requester; the comment was not independently retrieved by the builder). | **Knowledge/Detection**: confidence policy and kernel-compatibility disposition. Builder: document correction only. | **OPEN.** D6, D7, D9 and §4 corrected in this revision, pending targeted re-review. The substantive disposition remains open until Knowledge/Detection approve it. |

Codex is an independent reviewer. Its finding is review evidence, not owner approval of any decision, and it closes no D1–D9 decision or G1–G6 gap.

### Sponsor/Product scope decision — recorded 2026-10-15

**Decision source:** Project conversation, requester-provided direction (not an independently authenticated GitHub review or a verified sponsor identity). The requester explicitly stated: “Proceed with Option A. I approve the proposed synthetic-local, backend-first S8 product scope. Record my sponsor scope decision, keep OCR disabled, and identify any independent technical approvals still needed before implementation.”

**Scope accepted as product direction:** synthetic/local-only tests, PNG screenshot input only for the proposed opt-in profile, English-only OCR evaluation, backend/API first, default OFF, no browser screenshot/camera UI, no production activation, and no change to the S2 text-only default or S1–S7 behavior. This records the requester’s Sponsor/Product **scope assent** to D1/D5; it does **not** approve D1 parser/security specifics, D2 numeric bounds, D3 worker/launcher privileges, D4 engine/image digests, D6 confidence, D7 errors, D8 migration/replay, or D9 exact composition semantics.

**Attestation limit:** No reviewer identity or organizational authority was verified through GitHub. An accountable Sponsor/Product owner must confirm the decision and conditions in the governed review record before G5 is formally CLOSED. OCR must remain OFF, and implementation remains BLOCKED.

No builder-authored check or draft PR counts as independent approval. Approval must identify an accountable reviewer, the exact decision/version, evidence and any conditions. Sponsor assent alone does not substitute for independent Security/Detection review.

## 4. Implementation authorization checklist (not yet met)

Before **any** S8 runtime implementation, confirm D1–D5 approvals, accepted limits and selected isolation/dependency.

Some approvals are required **before the code they govern is written**, not at activation:
- **D6:** the Knowledge/Detection extraction-confidence mapping, before any OCR-derived envelope code.
- **D7 mixed-input:** the Knowledge/Detection confidence policy and kernel-compatibility disposition, before any text-plus-screenshot OCR-failure code. Without it, that path stays BLOCKED and only the refusal described in D7/D9 may be implemented.

Before **activating** the S8 profile, also close the remaining D7–D9 items, verify the migration/grants and all tests. If any dependency remains unresolved, report that scope **BLOCKED** under PLAN-001 rather than marking S8 complete.

After authorization only, the smallest proposed S8a scope is: bounded PNG preflight; disabled-by-default OCR port; isolated worker/launcher; immutable derivative + source lineage + audit; envelope/evaluation composition; replay integrity; minimal grant migration; synthetic tests. Preserve the existing API/OpenAPI, Phase-3 kernel, Phase-7 UX contracts, S1–S7 runtime behavior and prior migration history.

Required proof: malformed PNG, polyglot, decompression bomb, dimension and output bounds; isolation escape attempts, timeout/kill and network denial; encrypted original and derivative digest/parent checks; duplicate/retry idempotency; screenshot-only failures; refusal of mixed text-plus-screenshot submissions while D7's mixed-input path is BLOCKED (no text-only substitution); the text-only pipeline unchanged; zero OCR calls during replay; authorized role behavior; full backend/frontend regression, canonical quality gate, CI and independent review.

## 5. Current STOP status

**SPONSOR SCOPE DIRECTION RECORDED; INDEPENDENT FINDING MEDIUM-1 OPEN (Knowledge/Detection); MIXED-INPUT OCR-FAILURE PATH BLOCKED; READY FOR GOVERNANCE REVIEW ONLY. NOT INDEPENDENTLY APPROVED. NOT READY TO IMPLEMENT S8.** This document is not a new feature flag, not a media-configuration activation, not an accepted security profile, not a migration, and not a claim of tested OCR. It must not be used to assert S8 completion or production readiness.
