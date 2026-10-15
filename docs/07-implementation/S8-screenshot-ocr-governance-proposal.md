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
| Independent review | Draft PR #53: Codex REQUEST_CHANGES at `45573e7` (MEDIUM-1); requester reports that the re-review at `70ce39d` resolved MEDIUM-1 as a document issue: ACCEPTABLE_FOR_OWNER_REVIEW, no new findings. The Knowledge/Detection disposition remains **OPEN**; see §3. |

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

All nine technical/governance decision packages remain **PROPOSED**. D1–D5 now carry a concrete technical package (2026-10-15) for owner review; no owner has signed it. Sponsor/Product scope direction has been recorded for the PNG-only local-test intent in D1 and the default-OFF backend-first scope in D5; it does **not** close the independent reviews or authorize coding.

### D1–D5 technical decision package — evidence status

This package (2026-10-15, corrected after the Codex D1–D5 review) makes D1–D5 implementable for **synthetic-local** OCR. Nothing in it is approved: each decision still needs the named owner's sign-off. The table separates what the builder verified from what is only proposed. "Verified" means observed directly on 2026-10-15 and is limited exactly to the scope stated.

| ID | Verified fact (scope of verification) | Source |
| --- | --- | --- |
| E1 | Tag `5.5.2` resolves to commit `6e1d56a847e697de07b38619356550e5cf4e8633`. GitHub shows the tag signature as *Verified* (Stefan Weil, key `E08C21D5677450AD`), released "December 26" (the year is not displayed; the local Homebrew 5.5.2 files are dated 2025-12-26). The signature was **not** checked locally with GPG. | GitHub release page |
| E2 | Tag `5.5.3` resolves to commit `db0ec62f81b0737fbbe184d8fea40af5738f8eef`, also shown as *Verified*, released "July 24" (consistent with Alpine edge `5.5.3-r0` dated 2026-07-27). Its notes list memory-safety fixes in `.traineddata` deserialization and integer-overflow fixes in LSTM Convolve/Reconfig deserialization. | GitHub release page; Alpine package index |
| E3 | SHA-256 of the GitHub tag archives as downloaded: `5.5.2.tar.gz` = `6235ea0dae45ea137f59c09320406f5888383741924d98855bd2ce0d16b54f21` (single source). `5.5.3.tar.gz` = `9218e62793116d42a9f6d14cd9348518b27f382096eea3d0f2d1a24616bb5884`, which equals the checksum published by the Homebrew formula (two independent sources). GitHub-generated archives are not guaranteed byte-stable, so the commit hash, not the archive digest, is the primary pin. | Builder download; `brew info` metadata |
| E4 | Leptonica `1.87.0` release asset `leptonica-1.87.0.tar.gz` (released 2025-12-24): SHA-256 `c73363397f96eb1295602bf44d708a994ad42046c791bf03ea0505d829bdb6a7` (single source). Its licence is a BSD 2-clause-style text (`leptonica-license.txt`). | Builder download |
| E5 | In `tesseract-ocr/tessdata_fast`, `eng.traineddata` was changed only by commit `923915d4ced2a7235221788285785a29c4a42d4a` (2017-09-14). The file at that commit is 4,113,088 bytes with SHA-256 `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`, byte-identical to the local Homebrew `eng.traineddata`. The repository is Apache-2.0; `LICENSE` was added in commit `27cfc71a8874cce2483679eea010e391bb38c2ae` (2019-06-13). | Builder download; GitHub history |
| E6 | Tesseract 5.5.2 `src/api/baseapi.cpp`, read from the downloaded 5.5.2 archive. (a) With input `stdin`/`-`, bytes whose format `findFileFormatBuffer` does not recognise are processed **as a newline-separated file list**. Each line is passed to Leptonica `pixRead()` as a **local path**. This fallback is not conditional on any build option. (b) The libcurl download branch (`#ifdef HAVE_LIBCURL`) applies when the **input filename argument** contains `://`, not to stdin bytes or to file-list lines. (c) A `stream_filelist` parameter exists. (d) CMake options at 5.5.2, with their defaults: `DISABLE_CURL` ("Disable build with libcurl (if available)") OFF, `DISABLE_ARCHIVE` OFF, `DISABLE_TIFF` OFF, `GRAPHICS_DISABLED` OFF, `BUILD_TRAINING_TOOLS` ON, `OPENMP_BUILD` OFF, `DISABLED_LEGACY_ENGINE` OFF. | Upstream source at the tag |
| E7 | The local Homebrew `tesseract` 5.5.2 links `libcurl`, `libarchive` and Leptonica 1.87.0 (built with GIF/JPEG/PNG/TIFF/WebP/OpenJPEG). Homebrew's current formula is 5.5.3. | `otool -L`, `tesseract --version`, `brew info` |
| E8 | **Repositories examined (only these):** Debian (`packages.debian.org`): `tesseract-ocr` bookworm 5.3.0-2, trixie 5.5.0-1+b1, forky/sid 5.5.0-1.1; trixie `libleptonica6` 1.84.1-4 (depends on libpng, libjpeg-turbo, libtiff, libwebp, giflib, openjpeg, zlib). Alpine (`pkgs.alpinelinux.org`, edge/aarch64 only): `tesseract-ocr 5.5.3-r0` (2026-07-27). Fedora (`packages.fedoraproject.org`): the Fedora 44 package page lists **`tesseract-5.5.2-1.fc44`** (changelog 2025-12-27, "Update to 5.5.2"), while the package index lists `5.5.3-2` for Fedora 43/44/45/Rawhide. Whether this is a release vs updates repository difference was not resolved (Koji/Bodhi refused automated access). The Fedora build options and Leptonica linkage were **not** examined. No other distribution was examined. | Distribution package sites |
| E9 | Docker CLI 29.7.2 is installed. The daemon was **not running** during this review. The active context `desktop-linux` uses `~/.docker/run/docker.sock`, owned by the developer account with mode `srwxr-xr-x`, so any process of that account can control the daemon. No daemon security-option, cgroup, file-sharing or networking evidence was obtainable. | `docker version`, `docker context ls`, `ls -l` |
| E10 | Leptonica 1.87.0 `src/readfile.c` dispatches BMP, PNM and SPIX readers (`pixReadStreamBmp`/`Pnm`/`Spix`, `pixReadMem*`) alongside PNG, JPEG, TIFF, GIF, JP2, WebP, PS and LPDF. `bmpio.c` and `spixio.c` have no external-library guard, and `pnmio.c` is guarded only by `USE_PNMIO` (`environ.h`). These readers therefore remain compiled whatever the `ENABLE_*` format options are. | Upstream source in the downloaded archive |
| E11 | Repository constraints of the approved S2 profile: `serve.py` fixes the listener to `127.0.0.1:8000`. `config.py` allows plain HTTP only for host `127.0.0.1` (issuer, redirect, origins). `oidc.py` requires the discovered `issuer` to equal the configured issuer exactly, with endpoints on that origin. `admission.py` buckets by whether the TCP peer is loopback. `content_store.py` requires the KEK and evidence directory to be owned by the process UID with no group/other permission bits. | Repository code at `70ce39d` |

**Not verified, only proposed:**
- any container image or image digest (none was built or run);
- any isolation, file-sharing, networking, resource-limit, timing or memory behaviour;
- vulnerability status, reproducibility, and local GPG verification of the tag signatures;
- the Fedora package's build options;
- every numeric bound in D2 under the real engine.

### D1 — PNG media profile (G1)

**Proposal:** a separate S8 synthetic-local opt-in profile (D5) accepts exactly one media type, `image/png`, with `artifact_kind=IMAGE`. The default S2 text-only profile is unchanged and still refuses images (`415`).

**Admitted variant (all must hold):**
- 8-byte PNG signature at offset 0.
- Exactly one `IHDR` as the first chunk, data length 13:
  - width and height 1–4,096, width × height ≤ 8,000,000 (D2), computed overflow-safe;
  - bit depth 8 and colour type 2 (RGB) or 6 (RGBA);
  - compression 0, filter 0, interlace 0 (no Adam7).
- One or more `IDAT` chunks, all **contiguous**, then exactly one `IEND` with length 0 as the last chunk.
- **No bytes after `IEND`.**
- Every chunk length is ≤ 2³¹−1 and within the remaining bytes. Every chunk type is four ASCII letters. **Every CRC-32 is verified.**
- Proposed ancillary allowlist: uncompressed `sRGB`, `gAMA`, `cHRM` and `pHYs`, each at most once and before the first `IDAT`.
- Everything else is refused:
  - `PLTE`, `tRNS`, `bKGD`, `sBIT`, `hIST`, `sPLT`, `tIME`, `tEXt`, `zTXt`, `iTXt`, `iCCP` and `eXIf`;
  - any unknown critical or ancillary chunk;
  - APNG chunks (`acTL`, `fcTL`, `fdAT`).
- **In the isolated worker only:** the concatenated `IDAT` data must form exactly one zlib/deflate stream with no preset dictionary, a valid header check and Adler-32, and nothing after the stream ends. It must inflate to **exactly** `height × (1 + width × channels)` bytes, and every scanline filter byte must be 0–4.

**Consequence of the allowlist:** it refuses most real device screenshots, which commonly carry `iCCP`, `eXIf` or text chunks. That is acceptable for the synthetic-local scope, because test PNGs are generated without them. Widening it is a later profile revision.

**Validation is split at the decompression boundary.** Nothing outside the isolated worker inflates, decodes or touches scanlines or pixels.

| Tier | Where | What is checked | What is never done here |
| --- | --- | --- | --- |
| **Tier 1 — bounded structural preflight** | FastAPI at `putEvidenceContent` and again at `finalizeEvidence`; the launcher again before dispatch (D3) | Total length ≤ 2 MiB (body already bounded); signature; chunk framing and lengths; CRC-32 over each chunk's raw type and data; approved chunk types, order and counts; `IHDR` field values and dimension/pixel arithmetic; no trailing bytes. A single linear pass over ≤ 2 MiB. | zlib header parsing, inflation, Adler-32, scanline or filter-byte inspection, any image decoding |
| **Tier 2 — isolated validation** | Inside the unprivileged OCR worker container (D3), at OCR time (D8: `createEvaluations`), before Tesseract runs | Tier 1 repeated; the zlib stream rules and the exact-size, bounded, streaming inflate above; scanline filter bytes; inflated data counted and discarded. Only if every check passes does the worker hand the **same bytes** to Tesseract (D3 worker command). | Passing anything that failed validation to Tesseract; storing inflated data |

**Sequence and error semantics (proposed):**
- **Tier 2 runs after finalization, not before** (option i). Evidence intake therefore never depends on Docker or the worker.
  - **Tier-1 failures are synchronous upload errors with existing semantics.** At create or PUT: `413 PAYLOAD_TOO_LARGE` (`SIZE_EXCEEDED`) for size, `415 UNSUPPORTED_MEDIA_TYPE` (`MEDIA_INVALID`) for media or structure, and the existing `LENGTH_MISMATCH` / `DIGEST_MISMATCH` handling. A failed `finalizeEvidence` re-check prevents FINALIZED under the existing finalize integrity semantics (`INTEGRITY_FAILED`, `500 INTEGRITY_FAILURE`), not `415` (D7). No API or OpenAPI change is needed.
  - **Tier-2 failures, OCR failures and timeouts happen after FINALIZED.** The evidence stays FINALIZED and unchanged. The failure surfaces only through D7 evaluation/dependency semantics, never as a retroactive `415`, never as a change of evidence state, and never as a safety result.
  - `verified_media_type = image/png` therefore means "passed Tier-1 structural verification", **not** "decodable". This must be documented wherever the field is explained.
- **Alternative for the owner (option ii):** a validation-only worker run before FINALIZED. It couples evidence intake to Docker availability and needs an accepted mapping for a validation failure after a successful PUT, so it is not proposed.

**Original-byte preservation:**
- The server SHA-256 covers the exact submitted bytes (`TL_EVIDENCE_BYTES_V1`) and stays authoritative. The bytes are stored encrypted and unmodified, with no re-encoding, stripping or normalisation.
- The launcher and worker receive a copy of those bytes, with the SHA-256 checked at each hop (D3), and never write back.
- `getEvidenceContent` returns the original unchanged as an attachment with `nosniff`. The OCR text derivative carries no image metadata. Filename and extension are never authority.

**Approval:** Security and Backend (format, two-tier threat model, option i vs ii); Sponsor/Product (scope, already directed).

### D2 — Resource and admission limits (G2 / T09)

Evaluation of the existing candidate bounds. All values are **local-test proposals**, not approved OPS-001 settings. Each must be measured under the real pinned worker before switch-on (§4).

| Bound | Proposed final local value | Assessment and rationale |
| --- | --- | --- |
| Original PNG upload | 2 MiB (2,097,152 bytes) | Sound; Tier-1 work is linear in it. Applies only to `IMAGE` under the opt-in profile; the 64 KiB text bound is unchanged. A small body with a huge decoded size is handled inside the worker by Tier 2's exact-size inflate bound (D1), not by this limit. |
| Width / height | 1–4,096 each | Sound. A refusal is `415` (Tier 1). |
| Total pixels | ≤ 8,000,000 | Sound, and the binding constraint: 4,096 × 4,096 is refused by Tier 1 even though each dimension passes. |
| Decoded image | ≤ 32 MiB (33,554,432 bytes) | **Rewording required.** Tesseract/Leptonica expose no decode-budget control, so "enforce within isolated decoder" is not achievable as stated. Proposed instead: it is guaranteed arithmetically by Tier 1's `IHDR` checks. At 8,000,000 px × 4 bytes (Leptonica holds RGB/RGBA as 32 bpp) = 32,000,000 bytes, and the scanline bytes are at most 32,004,096. Tier 2 enforces the actual inflate size inside the worker; the container memory cap is the backstop. **Consistent.** |
| OCR deadline | 10 s per attempt | Not unsafe; expiry is an explicit failure. It may be **unworkable** for large, dense 8 MP images on 1 CPU, and is untested. Proposed definition: one end-to-end deadline measured by the launcher from container start to exit, covering Tier 2 and OCR, with kill/cleanup outside it but bounded. Measure on synthetic images at the maximum size before switch-on. If 10 s is not met, OCR stays OFF or a revised profile is approved; the bound is not quietly raised. |
| Worker CPU / memory / PIDs | 1 CPU / 256 MiB / 32 PIDs | Plausible but **unmeasured**: the 32 MB 32-bpp image plus grayscale/binary copies, the ~4 MB `eng` model and the validator must fit, and any `tmpfs` is charged to the same cgroup. Require `--memory-swap` equal to `--memory` (no swap). An OOM kill is an explicit failure. 32 PIDs suffices for a single-threaded build (`OPENMP_BUILD` OFF, E6). |
| Concurrency | One OCR job per local instance | Sound. A second request gets `BUSY` from the launcher (no queue). The public mapping uses existing D7 dependency-unavailable semantics, to be verified by the API owner. |
| OCR text output | ≤ 64 KiB UTF-8 | Sound, and consistent with the S4 extractor's 64 KiB text bound. The launcher reads at most 64 KiB + 1 byte, then kills the job as an explicit failure. stderr is drained under the same cap, discarded and never returned. |
| Images per submission | One | Sound. A second `IMAGE` intent is refused under existing semantics. Consistent with D9; mixed text-plus-screenshot remains BLOCKED (D7). |
| Automatic OCR retries | Zero | Sound. |

No bound is contradictory once "decoded image" is guaranteed arithmetically and enforced inside the worker. The two at-risk bounds are the **10 s deadline** and the **256 MiB memory** cap, and only measurement can settle them. Any further value the design needs (tmpfs size, `nofile` ulimit, IPC margin, cleanup bound) must be measured and recorded in the profile before switch-on. None is chosen here.

**Approval:** Sponsor, Backend/Operations and Security; Product for any future UI copy.

### D3 — Docker isolation and trusted launcher (G3)

**Finding (E9):** on this macOS / Docker Desktop setup, the Docker socket belongs to the developer account. A FastAPI process run as that account (the S2 `make backend-run` default) can control the daemon. **No same-account arrangement meets D3**, so OCR stays OFF until an approved deployment below is demonstrated.

**Common to every option:**
- The backend never has a Docker socket, a `DOCKER_HOST`, Docker contexts or management credentials.
- The launcher and the worker never get the evidence key, the evidence directory, database credentials or the OIDC client secret.
- The worker gets only the bytes of one request.

**Privileged trusted components and residual risk.** The **Docker daemon**, and **every holder of Docker management access**, are *privileged trusted components*:
- the launcher (with the socket mounted in B2, or as the socket owner in B1/D3-A);
- the developer account itself (E9).

Docker management access is equivalent to root on the Docker VM and to control over every container it runs, including the backend container. A holder can:
- start a new container with any host mount, including the paths that hold the S2 KEK, evidence directory and configuration files;
- `exec` into or inspect the running backend container (its environment, mounted files and memory);
- replace, stop or reconfigure the backend, launcher and worker containers, images and networks;
- read container filesystems.

Keeping secrets out of the launcher's own mounts **limits accidental exposure, but is not a boundary** against a compromised launcher or daemon.

**Compromise impact:** loss of confidentiality and integrity of evidence plaintext (through the KEK and evidence directory), of database and OIDC credentials, of audit and operational records reachable with those credentials, and of OCR results.

Controls that **reduce but do not remove** this risk:
- the launcher exposes only the fixed operation, with no generic Docker passthrough;
- small stdlib-only code, no network listener, content-free logs;
- the pinned image ID;
- Tier-1 input checks and peer authentication.

**Explicit, recorded Security acceptance of this residual risk** (reviewer, version reviewed, conditions) is required before switch-on. Without it, D3 stays OPEN and OCR stays OFF.

#### D3-B — containerised backend (preferred candidate)

| Element | Design |
| --- | --- |
| Backend container | Unprivileged: non-root, `--cap-drop ALL`, `no-new-privileges`, read-only root. **No** Docker socket, `DOCKER_HOST`, `~/.docker` mount or Docker CLI in the image. Explicit `--user <UID>:<GID>` equal to the **existing** owner of the S2 KEK and evidence directory, so `content_store.py`'s owner-UID and mode checks (E11) run **unchanged**. If the mounts don't present that owner and mode, the backend fails closed as today; no check is relaxed. |
| Narrow approved mounts (backend only) | The S2 evidence directory (read-write) and the KEK **file** (read-only), each at a fixed container path. Also read-only, file-level, only the S2 configuration files the backend already reads (database runtime and OIDC client settings). No home directory, no whole `~/.config`, no other host path. **No ownership, mode or location change to any existing S2 persistent asset.** |
| Startup checks (backend) | Refuse to start the S8 profile unless all of these hold: the effective UID/GID equals the configured mapping; the KEK and evidence directory pass the existing checks; no Docker socket path exists, `DOCKER_HOST` is unset, and no Docker endpoint is reachable; the launcher channel authenticates (below). |
| Launcher | A separately trusted program with one fixed operation (`OCR_PNG_ENG_V1`) and Docker access, and no other privilege: stdlib-only, content-free logs, no evidence key, evidence directory, database credentials or network listener. **B2 (preferred candidate, not yet a complete security boundary):** the launcher runs in its own container with the Docker socket mounted, sharing with the backend container only a named volume that holds one Unix socket. Within the Linux VM, peers are authenticated by `SO_PEERCRED`. For later launcher review: hardening of the B2 launcher container itself (read-only root filesystem, minimal Linux capabilities, a dedicated non-root identity where socket access allows, `no-new-privileges`). These are defence in depth only and **do not remove its Docker management authority**. B2 counts as a boundary only after all of the following are validated: (a) the launcher accepts only the backend's mapped UID, and that UID is unique to the backend; (b) the backend verifies by `SO_PEERCRED` that the endpoint is the launcher's UID, because the engine identity in a response is not authentication; (c) the volume and socket are owned by the launcher UID with modes that stop any other container or UID from binding, unlinking or replacing the endpoint, and only the backend and launcher containers mount that volume; and (d) the backend cannot replace the endpoint (no write permission on the socket directory). **B1 (alternative):** the launcher runs on the host as the socket owner. This needs evidence that a host Unix socket is usable from a container across Docker Desktop's file-sharing layer. Otherwise it would need a loopback TCP channel with a new authentication credential, which needs its own approval. |
| Protocol (one request per connection) | **Request:** a 4-byte big-endian header length (≤ 1 KiB), then a UTF-8 JSON header `{"v":1,"op":"OCR_PNG_ENG_V1","request_id":<uuid>,"byte_length":n,"sha256":<64-hex>}`, then exactly `n` bytes (`n` ≤ 2 MiB). **Response:** a header `{"v":1,"request_id","status":OK\|REFUSED\|BUSY\|TIMEOUT\|FAILED\|UNAVAILABLE,"category":<fixed enum>,"engine":{"image_id","tesseract_version","eng_sha256","config_sha256"},"text_length","text_sha256"}`, plus the text bytes only when `OK`. Read and write deadlines apply on both sides. Any unknown field, oversized frame, digest or length mismatch, or unexpected op is `REFUSED`. |
| Fixed operation | The launcher re-checks the length and SHA-256 and runs **Tier 1 only** (no inflation, no decoding). It confirms the local image ID equals the pinned ID, then starts the worker. The backend accepts a result only if `engine` equals the pinned identity and `text_sha256`, length and strict UTF-8 all verify. |
| Worker container | `docker run --rm -i --pull never --name tl-ocr-<request_id> --label trustlens.ocr.worker=v1 --network none --read-only --user 65534:65534 --cap-drop ALL --security-opt no-new-privileges=true --cpus 1 --memory 256m --memory-swap 256m --pids-limit 32 --ipc none --log-driver none --ulimit core=0 <image@pinned-id>`. Notes: no `-t`, no `-e` beyond fixed non-secret values, no `-v`/`--mount`, no `--privileged`, and the default seccomp profile is kept. `--log-driver none` keeps OCR text (C4) out of Docker's log store. Add `tmpfs` (`noexec,nosuid,nodev`, measured size) only if shown to be needed. |
| Worker command (fixed invocation) | The entrypoint is baked into the image. **First, the Tier-2 validator** reads stdin bounded to 2 MiB and runs all D1 worker checks. Only on success does it pass the same bytes through a pipe to `tesseract stdin stdout --oem 1 -l eng`, with a fixed page-segmentation mode and DPI and a fixed read-only `TESSDATA_PREFIX`. **Nothing user-controlled reaches the engine:** no filename, path, URL, shell, argument, `-c` option (including `stream_filelist`), config file or environment value. The full argv, environment and model digest form `config_sha256`. Because only Tier-2-validated PNG bytes reach Tesseract's stdin, E6's file-list fallback is never triggered by a valid request. The fallback itself **still exists in the binary**, and if reached it could only read paths inside the read-only, network-less worker filesystem. |
| Timeout and cleanup | Deadline per D2. On expiry: `docker kill tl-ocr-<request_id>`, then `docker rm -f tl-ocr-<request_id>` (exact names, never globs or `pkill`). At launcher start, and after any failure, leftover containers are found by the exact label and removed by exact name. Until cleanup is confirmed the launcher answers `UNAVAILABLE`. |
| Fail-closed | Launcher absent or unhealthy; peer mismatch; Docker daemon unavailable; image ID mismatch; missing expected `docker info` security options or cgroup controls; or any limit not applicable. Each gives `UNAVAILABLE`. OCR is never attempted by the backend itself. The backend maps it to D7 dependency-unavailable semantics, with no text-only substitution. |

**D3-B feasibility: not demonstrated, and it cannot preserve the approved S2 profile unchanged.** The repository constraints in E11 conflict with running the backend in a container:

| # | Conflict with the approved S2 profile | Evidence needed or approval |
| --- | --- | --- |
| 1 | `serve.py` fixes the listener to `127.0.0.1:8000`; inside a container that is unreachable through a published port. The container would bind its own interface, with the host publish restricted to `127.0.0.1:8000`. | Change to a fixed S2 profile parameter: approval needed. |
| 2 | Published-port traffic reaches the backend from the Docker gateway or proxy, not loopback. All browser requests then fall into admission's "other" class. | Security evaluation plus evidence of the actual peer address. |
| 3 | OIDC issuer and redirect must be `http://127.0.0.1:…`, and the discovered issuer must match exactly. Inside the container, `127.0.0.1:8081` is not the Keycloak dev container. | Evidence that the issuer is reachable unchanged (for example host networking on Docker Desktop), or an approved profile revision. The issuer and HTTP checks must not be weakened. |
| 4 | The runtime database is the existing dev container at `127.0.0.1:55432`, with the same reachability issue. Attaching the dev container to a new Docker network would modify a persistent asset. | Reachability evidence without modifying the dev containers, or an approved revision. |
| 5 | The content store's owner-UID/mode checks over Docker Desktop bind mounts (file-sharing ownership presentation) are unverified. | Evidence that the unchanged checks pass with the explicit UID mapping. Otherwise this scope stays BLOCKED. |
| 6 | The launcher channel (B2 named-volume Unix socket with `SO_PEERCRED`, or B1 across the VM boundary) is unverified. | Evidence; a new channel credential needs approval. |

**Minimal approval required to unblock D3-B:** Sponsor plus Security approval of a *containerised-backend addendum* to the S2 local-development profile. It would cover items 1–4 (listener bind and publish, admission peer class, OIDC and database reachability). The content-store, key, issuer and HTTP-origin checks stay **unchanged**, and items 5–6 are demonstrated. Until both exist, **D3-B and synthetic-local OCR remain BLOCKED.**

**Isolation evidence required before switch-on** (on the selected Docker Desktop VM, all with synthetic data):
- the backend container cannot reach Docker management (no socket, no `DOCKER_HOST`, no Docker TCP endpoint);
- the backend's UID mapping and unchanged S2 checks;
- the launcher and worker cannot see the KEK, evidence directory or database/OIDC credentials;
- worker network denial: DNS, TCP and the host gateway;
- worker filesystem: read-only root and no host paths;
- non-root with no capabilities; no secrets;
- memory/OOM, CPU, PID and output caps each triggered;
- deadline kill and cleanup;
- the launcher refusing wrong-UID peers and malformed frames;
- the backend refusing an endpoint not owned by the launcher UID;
- the socket endpoint protected against replacement by the backend or any other container;
- Tier-2 refusals never reaching Tesseract.

#### D3-A — separate host OS account for the backend (conditional alternative)

The backend runs as a separate unprivileged macOS account that cannot connect to the developer account's Docker socket; the launcher runs as the socket owner on a peer-authenticated Unix socket. This would require moving, or re-provisioning for that account, the S2 KEK and evidence directory, which is a change to existing S2 persistent assets. D3-A is therefore **not** an automatic prerequisite. It is available only if Sponsor and Security explicitly approve that S2 key-profile revision. Otherwise it stays unused.

**Approval:** Security/DevSecOps (privilege boundary, **residual-risk acceptance for the privileged Docker components**, D3-B vs D3-A, B1 vs B2) and Backend/Operations. Sponsor plus Security for the S2 profile addendum (D3-B) or key-profile revision (D3-A).

### D4 — Tesseract and supply chain (G4)

**Version decision (owner):**
- **5.5.2:** the originally proposed version, matching the local binary and the Fedora 44 page; E1, E3, E8.
- **5.5.3:** later patch release with memory-safety and overflow fixes in traineddata deserialization; E2, E3 two-source digest.

The builder **recommends 5.5.3** for review. Either way, pin the tag commit, verify the tag signature locally with GPG before building, and record the archive digest.

**Source decision (owner):**
- **Source build (proposed):** full control of build options.
- **Distribution package:** for example Fedora 44's (E8). Its build options and Leptonica linkage are unexamined and would need the same evidence.

**Proposed source build:**
- Multi-stage, for `linux/arm64` on the local Apple-silicon host.
- Builder and runtime base images pinned by digest. System packages from a pinned snapshot repository, so they are reproducible.
- **Leptonica 1.87.0** (E4 digest): `ENABLE_ZLIB=ON`, `ENABLE_PNG=ON`, `ENABLE_GIF/JPEG/TIFF/WEBP/OPENJPEG=OFF`. This removes those *external* decoders from the build. **It does not make the worker PNG-only:** Leptonica's built-in BMP, PNM and SPIX readers remain (E10).
- **Tesseract:** `DISABLE_CURL=ON`, `DISABLE_ARCHIVE=ON`, `DISABLE_TIFF=ON`, `GRAPHICS_DISABLED=ON`, `BUILD_TRAINING_TOOLS=OFF`, `OPENMP_BUILD=OFF`, `DISABLED_LEGACY_ENGINE=ON`.
  - `DISABLE_CURL` is intended to exclude libcurl "if available". Its effect must be **demonstrated for the pinned build** (configuration output and linkage), not assumed.
  - The stdin path doesn't use the curl branch anyway (E6b), and `--network none` remains the enforcing network control.
  - **None of these options removes the file-list fallback (E6a).**
- **Runtime image** contains only: the Tier-2 validator, `tesseract`, `libtesseract`, `libleptonica`, `libpng`, `zlib`, the C/C++ runtime and `eng.traineddata` verified against E5's SHA-256. It runs as non-root, ideally with no shell.

**PNG-only behaviour is enforced by** the Tier-2 validator plus the fixed invocation (D3), **not** by the build. Linkage evidence such as `ldd` records which external libraries are present; it is **not** proof of PNG-only capability.

**Supply-chain evidence required before switch-on:**
1. Recorded commit, tag signature check, archive and asset digests, and base image digests.
2. The built image ID, which is the pin used by `--pull never`.
3. An SBOM (SPDX or CycloneDX) of the runtime image.
4. A vulnerability scan of the SBOM with a written disposition for each finding (scanner selection is a Security decision).
5. Build configuration and linkage records for the options above.
6. A second independent build with the same image ID, using pinned sources, `SOURCE_DATE_EPOCH` and normalised timestamps. If not bit-reproducible, record the residual differences and treat the reviewed image ID as authoritative.
7. A licence inventory from the SBOM.
8. Negative tests in the worker:
   - BMP, PNM, SPIX and other non-PNG inputs, a file-list-shaped input, and a PNG failing Tier 2 are each refused by the validator before Tesseract;
   - no network is reachable.

**Licence obligations:**

| Component | Licence |
| --- | --- |
| Tesseract | Apache-2.0 (`LICENSE`; the archive has no `NOTICE`) |
| tessdata_fast | Apache-2.0 |
| Leptonica | BSD 2-clause-style: retain the copyright and disclaimer in binary redistributions |
| libpng | PNG Reference Library licence |
| zlib | zlib licence |
| glibc | LGPL-2.1+ |
| libstdc++ / libgcc | GPL-3.0 with the GCC Runtime Library Exception |
| Other base packages, and any distro package | Per the SBOM |

S8a never pushes or distributes the image, which limits most redistribution obligations. If it is ever distributed, notices and LGPL/GPL source obligations apply and need review.

If any evidence item is missing, **D4 remains OPEN and OCR stays OFF.** No accuracy, multilingual, performance or certification claim is made.

**Approval:** Security/Supply Chain, Backend and Sponsor.

### D5 — Scope and activation (G5)

**Unchanged scope:** synthetic-local only, backend/API only, PNG only, English (`eng`) only, OCR **default OFF**. There is no browser picker, camera, preview or UI copy (UX-002 frozen), no production or non-loopback activation, and no change to S1–S7 or the S2 text-only default. S8b (UI) still needs its own Product/UX decision.

**Proposed future opt-in:** a single explicit setting selects the S8 profile, for example `TRUSTLENS_S8_OCR_PROFILE=SYNTHETIC_LOCAL_V1`; any other value or absence means OFF.

At startup the backend accepts the setting only if:
- the synthetic-only profile is active;
- the listener is reachable only through `127.0.0.1` on the host, per the approved D3 deployment;
- migration `0009` (D8) is present;
- the D3 backend startup checks pass;
- the launcher answers a health probe on the authenticated channel with the pinned engine identity.

Any failure leaves OCR OFF and keeps images refused (`415`). Turning the setting off restores the S2 behaviour exactly. Already-recorded evidence, derivatives and evaluations stay immutable and replayable.

**Approval:** Sponsor/Product (scope, already directed) and Security for the activation guard. Implementation authorization stays with §4.

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

- **Upload-time Tier-1 refusal (D1).** `415 UNSUPPORTED_MEDIA_TYPE` (`MEDIA_INVALID`) applies only when the bounded Tier-1 structural PNG checks reject the content during upload, at `createEvidenceUpload` (declared type) or `putEvidenceContent` (bytes). Oversize is `413 PAYLOAD_TOO_LARGE` (`SIZE_EXCEEDED`). Neither reaches any decoder. If the `finalizeEvidence` re-check fails for bytes that passed at PUT, that follows the existing finalize integrity semantics (`INTEGRITY_FAILED`, `500 INTEGRITY_FAILURE`), not `415`.
- **Deferred Tier-2 failure (D1).** A structurally valid, FINALIZED PNG that later fails decompression, scanline validation or decoding in the isolated worker is **never** a retroactive `415`, and never changes the evidence state. It uses the approved evaluation-failure handling in this section: explicit failure, no `NO_SCAM_PATTERN`, `CLEAN` or safety claim. The exact mapping is subject to the API-owner verification below.
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
| D1 | SPONSOR SCOPE DIRECTION RECORDED; TECHNICAL PACKAGE READY FOR OWNER REVIEW | PNG-only synthetic-local intent accepted by requester on 2026-10-15; Security/Backend and formal attestation pending |
| D2 | PROPOSED — TECHNICAL PACKAGE READY FOR OWNER REVIEW | PENDING |
| D3 | PROPOSED — TECHNICAL PACKAGE READY FOR OWNER REVIEW | PENDING |
| D4 | PROPOSED — TECHNICAL PACKAGE READY FOR OWNER REVIEW | PENDING |
| D5 | SPONSOR SCOPE DIRECTION RECORDED; TECHNICAL PACKAGE READY FOR OWNER REVIEW | Backend-first, synthetic-local, default OFF, no UI accepted by requester on 2026-10-15; Security and formal attestation pending |
| D6 | PROPOSED | PENDING — Knowledge/Detection extraction-confidence mapping required before OCR-envelope implementation |
| D7 | PROPOSED; mixed-input OCR-failure path **BLOCKED** | PENDING — Knowledge/Detection confidence policy and kernel-compatibility disposition required before implementation (MEDIUM-1) |
| D8 | PROPOSED | PENDING |
| D9 | PROPOSED; text-plus-screenshot row **BLOCKED** | PENDING — submission `declared_input_type` for screenshot-bearing submissions OPEN (API/Data) |

### Independent review findings

| Finding | Review provenance | Owner | Status |
| --- | --- | --- | --- |
| MEDIUM-1 — Confidence compatibility. The kernel permits `PARTIALLY_SUPPORTED` + `SCAM_PATTERN_DETECTED` + `detection_confidence=HIGH` + `degraded=false`, so the earlier D7 wording ("cap confidence") was incorrect. | Codex independent review of Draft PR #53 at `45573e78b58764947e94630eddd60b8e17d41bac`: REQUEST_CHANGES, BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 0 / INFO 0, recorded as a GitHub PR comment (as reported by the requester; the comment was not independently retrieved by the builder). | **Knowledge/Detection**: confidence policy and kernel-compatibility disposition. Builder: document correction only. | **Document issue RESOLVED** at `70ce39d` per Codex re-review (ACCEPTABLE_FOR_OWNER_REVIEW, no new findings; as reported by the requester). **Substantive disposition OPEN** until Knowledge/Detection approve it. |
| D1–D5 technical package review: REQUEST_CHANGES, 0 BLOCKER / 0 HIGH / 2 MEDIUM / 1 LOW, covering the PNG decompression boundary, the Tesseract input-capability claims and the package-availability scope, plus a request to evaluate D3-B as the preferred deployment. | Codex independent review of the uncommitted D1–D5 changes on `70ce39d` (as reported by the requester). | Builder: document correction. Owners: Security/Backend (D1, D3, D4), Sponsor (S2 addendum). | **RESOLVED** per Codex re-review (as reported by the requester). Corrected: two-tier validation (no inflation outside the worker); E6/E10 re-scoped and D4 claims corrected; E8 scoped to the repositories examined, with Fedora 44 acknowledged; D3-B evaluated as preferred but BLOCKED, D3-A conditional. |
| D1–D5 re-review: MEDIUM, the Docker launcher's effective authority was understated; LOW, D7 described every malformed PNG as an upload-time `415`. | Codex independent re-review of the uncommitted D1–D5 corrections on `70ce39d` (as reported by the requester). | Builder: document correction. Security: residual-risk acceptance for the privileged Docker components. | **OPEN** pending re-review. Corrected in this revision: D3 classifies the daemon and launcher as privileged trusted components, with compromise impact and required Security acceptance, and B2 is not a complete boundary until socket authentication, ownership and endpoint protection are validated. D7 limits `415` to upload-time Tier-1 refusals; Tier-2 failures use evaluation-failure handling, and the finalize re-check uses existing integrity semantics. §4A adds the worker-only proof plan. |

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

**Synthetic-local OCR switch-ON checklist.** Every item must be true and evidenced; otherwise OCR stays OFF.

1. D1–D5 signed by their named owners, identifying the reviewer, the version reviewed and any conditions. D6, D8 and D9 approved before their code is written. D7's mixed-input disposition approved, or the mixed path still refused.
2. D4 evidence items 1–7 recorded for the exact image ID, and the Tesseract version decision (5.5.2 or 5.5.3) made.
3. The approved D3 deployment in place with its evidence. D3-B is preferred, and needs its S2 containerised-backend addendum; D3-A only if its S2 key-profile revision is separately approved. The backend demonstrably cannot reach Docker management. The launcher and worker cannot reach the evidence key, evidence directory or database/OIDC credentials. S2 persistent assets are unchanged unless an approved revision says otherwise.
4. D3 isolation evidence recorded on the selected Docker Desktop VM, including B2 socket authentication, ownership and endpoint-replacement protection. Security's recorded acceptance of the privileged Docker components' residual risk.
5. D2 bounds measured with the real worker at their maxima, including the 10 s deadline and 256 MiB memory. Every additional value recorded in the profile.
6. D1 tests pass:
   - **Tier 1** (backend and launcher): malformed or truncated framing, CRC failures, trailing data, polyglots, APNG, interlaced and disallowed chunks, dimension and pixel limits, with no inflation performed;
   - **Tier 2** (worker): invalid zlib streams, bad Adler-32, wrong inflate size, decompression bombs, bad filter bytes and non-PNG inputs, each refused before Tesseract.
7. Migration `0009` reviewed and applied only through the governed path. Images still refused with the setting OFF.
8. The full backend/frontend suites, canonical gate and CI green, and independent review complete.
9. A D5 startup guard proven: any failed check leaves OCR OFF.

After authorization only, the smallest proposed S8a scope is: bounded PNG preflight; disabled-by-default OCR port; isolated worker/launcher; immutable derivative + source lineage + audit; envelope/evaluation composition; replay integrity; minimal grant migration; synthetic tests. Preserve the existing API/OpenAPI, Phase-3 kernel, Phase-7 UX contracts, S1–S7 runtime behavior and prior migration history.

Required proof: malformed PNG, polyglot, decompression bomb, dimension and output bounds; isolation escape attempts, timeout/kill and network denial; encrypted original and derivative digest/parent checks; duplicate/retry idempotency; screenshot-only failures; refusal of mixed text-plus-screenshot submissions while D7's mixed-input path is BLOCKED (no text-only substitution); the text-only pipeline unchanged; zero OCR calls during replay; authorized role behavior; full backend/frontend regression, canonical quality gate, CI and independent review.

## 4A. Worker-only OCR proof plan (proposed; separate from S8 authorization)

**What this is:** a disposable, synthetic-local demonstration of the D3 worker container alone. It produces the worker-level evidence that D2 and D4 call for, and measures real performance.

**What it is not:**
- not S8 implementation authorization (§4);
- not the S2 containerised-backend addendum, and not evidence for D3-B's backend, launcher or channel items;
- not a TrustLens feature, and it sets no TrustLens OCR flag.

**Status: PROPOSED — NOT AUTHORIZED TO RUN.** Running it needs a separate, explicit go-ahead from the requester/Sponsor, because it starts Docker and builds an image. Security must first review the Dockerfile, the validator and the harness.

| Aspect | Plan |
| --- | --- |
| Boundary | **No** TrustLens backend, frontend, database, migration, ECS content, evidence key, `~/.config/trustlens`, existing dev containers, credentials or feature flags. No repository application code or deployment file is touched. Proof artifacts live in a disposable directory outside the repository; only a results summary is later added to this document. |
| Dependency | One pinned English OCR build per D4, from the reviewed candidates and under the network rules below. The built image ID is recorded and run with `--pull never`. |
| Worker under test | The exact D3 worker image and argv (Tier-2 validator, then the fixed `tesseract stdin stdout` invocation), launched directly by a disposable harness. The harness and its operator account hold Docker management authority as **test operators**: this is the same privileged-component caveat as D3, so the harness is never part of TrustLens. Isolation probes use a separate probe image derived from the identical runtime image (plus a minimal probe program), run with the identical flag set. The runtime image itself stays probe-free. |
| Synthetic inputs | Generated PNGs only. A stdlib generator (bitmap font plus `zlib`/`struct`, no new dependency) renders known `SYNTHETIC TEST` strings with no real identifiers, so expected text is exact. Sizes: tiny, a typical phone-screenshot size, and the D2 maxima (one dimension at 4,096, and total pixels just under 8,000,000). Invalid inputs are generated by mutating valid ones. |

**Proof dependency candidates — review required; none is approved:**

| Candidate | Current evidence | Status |
| --- | --- | --- |
| Tesseract 5.5.3, commit `db0ec62f81b0737fbbe184d8fea40af5738f8eef` | Tag shown as signed (E2); archive SHA-256 `9218e627…5884` from two sources (E3) | Candidate. Local GPG verification of the tag signature: **OPEN**. |
| `eng.traineddata` (tessdata_fast, commit `923915d4…`) | 4,113,088 bytes, SHA-256 `7d4322bd…70b2` (E5) | Candidate, verified digest. |
| Leptonica 1.87.0 | Release-asset SHA-256 `c7336339…b6a7`, single source (E4) | Candidate. Second source or signature: **OPEN**. |
| Python 3.12 for the Tier-2 validator, **inside the worker only** | None yet | Candidate. Its native `zlib` inflation runs only inside the isolated worker; outside the worker, Tier 1 may compute CRC-32 checksums but never calls a decompressor. Exact patch version, provenance (base-image package or source) and digest: **OPEN**. Adds an interpreter to the worker's attack surface, so it needs Security review. |
| Minimal Linux base image (builder and runtime) | None. No digest has been selected or observed. | Selection with supply-chain evidence (digest, SBOM, scan): **OPEN**. |
| Compiler toolchain, CMake, libpng/zlib development and runtime packages | None | Exact versions, snapshot repository date and digests: **OPEN**. |
| Synthetic generator, Tier-2 validator, probe program and harness | Not written | Authoring and Security review: **OPEN**. |

**Network rules for the proof (N1):**
1. **Dependency acquisition** is a separately controlled step and the only step with network access. It runs outside the compile and test containers. Every source archive and the trained data are verified against their recorded SHA-256 before use, and anything that doesn't match is rejected.
2. **Base image and packages:** only the digest-pinned base image and reviewed package dependencies from a pinned snapshot are used. No floating tags and no unpinned downloads.
3. **Compilation** uses only the verified local inputs, with no network where the selected build environment supports it (for example `--network none` on the build step). If a step can't run without network, it is **OPEN** until reviewed, never silently allowed. If any build container must have network access, its reachability to existing services (for example ports published on the host loopback, through `host.docker.internal`) must be assessed first. If it can't be shown to be isolated, STOP.
4. **OCR execution** is always `--network none`, without exception. This covers the worker and every probe run.

**Test matrix (each test passes only on observed evidence):**

| # | Test | Pass condition |
| --- | --- | --- |
| P1 | Real PNG-to-text extraction | Evidence that actual English text was extracted from each valid synthetic PNG (non-empty, recognisably the rendered words). Record the character error rate and the exact transcription differences against the known text. Perfect punctuation isn't required and no accuracy threshold is set. A functional check only, with no production-accuracy claim. |
| P2 | Tier-1 malformed structure | Bad signature, framing, CRC, chunk order or type, APNG, interlace, palette or 16-bit, dimension and pixel limits, trailing data and polyglots: each is refused by the validator with a category, and Tesseract never starts. |
| P3 | Tier-2 malformed data | Bad zlib header, preset dictionary, bad Adler-32, short or long inflate, bad filter byte, and a decompression bomb (inflate beyond the `IHDR`-derived size): each is refused, aborting at the bound. |
| P4 | Non-PNG and capability probes | BMP, PNM, SPIX, TIFF, JPEG, GIF, a file-list-shaped text body (local paths) and a URL-shaped line: each is refused before Tesseract (E6, E10). |
| P5 | Network denial | Probe: DNS lookup, TCP to a public address, to the Docker host gateway and `host.docker.internal`: all fail. |
| P6 | Read-only filesystem and identity | Probe: writes to `/`, `/usr` and the tessdata path fail. No host paths are mounted. UID/GID is 65534, effective capabilities are zero, `no_new_privs` is set, and the environment holds only the fixed values. |
| P7 | Memory | Probe allocation beyond 256 MiB is OOM-killed, with no swap use. Peak memory of real OCR runs is recorded from the cgroup (method recorded). |
| P8 | CPU and PIDs | A probe's CPU usage stays within 1 CPU (from cgroup `cpu.stat`). Forking beyond 32 PIDs fails. |
| P9 | Output limits | A probe writing more than 64 KiB to stdout (and to stderr) is cut off and killed by the harness at 64 KiB + 1. No text is kept from that run. |
| P10 | Timeout termination | A run exceeding the 10 s deadline is killed by exact name and removed. No container with the proof label remains afterwards. `docker logs` holds nothing (`--log-driver none`). |
| P11 | Determinism | Repeated runs on the same input give identical output and output digest. |

**Measured performance (report actual values only):** for each input size over repeated runs, record:
- container start-to-exit wall-clock, and OCR-only time;
- cold vs warm container start;
- peak memory and CPU time;
- the host model, Docker Desktop version and VM resources.

These measurements decide whether the D2 values (10 s, 256 MiB) are workable. They are evidence, not a performance or SLA claim.

**Mandatory Docker Desktop startup preflight (N2), before the daemon is started:**
- Starting Docker Desktop may automatically restart existing persistent development containers, including `trustlens-postgres-dev` and `trustlens-keycloak-dev`, according to their restart policies. The repository doesn't record those policies, and they can't be read while the daemon is stopped, so they are **OPEN**.
- The human operator must establish them from their own records, or accept that the containers may start, and must **approve the possible startup consequences** before the proof begins.
- After the daemon starts, the harness may only *read* their state (`docker ps`, `docker inspect`) to record it. It never stops, deletes, restarts, reconfigures, attaches to, networks with or otherwise interacts with them.
- If safe isolation of the proof from existing services can't be established, the proof **STOPS** and does not proceed.

**Cleanup and data handling:**
- Synthetic data only.
- Proof containers are created only with the exact proof label and names, and are removed by exact name. The proof image is removed by exact ID if the reviewer asks.
- `trustlens-postgres-dev`, `trustlens-keycloak-dev` and any other container are never touched.
- Starting or stopping Docker Desktop is the requester's action.
- The results report holds measurements, categories and digests only.

**Exit:** a dated results summary, plus the evidence files listed in D4 items 1–8 for the proof image. The summary can satisfy only the worker-level parts of D2 and D4. D1, D3, D5, D6–D9 and §4 remain separately open.

## 5. Current STOP status

**SPONSOR SCOPE DIRECTION RECORDED; D1–D5 TECHNICAL PACKAGE READY FOR OWNER REVIEW (UNSIGNED); WORKER-ONLY PROOF PLAN (§4A) PROPOSED, NOT AUTHORIZED TO RUN; MEDIUM-1 KNOWLEDGE/DETECTION DISPOSITION OPEN; MIXED-INPUT OCR-FAILURE PATH BLOCKED; READY FOR GOVERNANCE REVIEW ONLY. NOT INDEPENDENTLY APPROVED. NOT READY TO IMPLEMENT S8.** This document is not a new feature flag, not a media-configuration activation, not an accepted security profile, not a migration, and not a claim of tested OCR. It must not be used to assert S8 completion or production readiness.
