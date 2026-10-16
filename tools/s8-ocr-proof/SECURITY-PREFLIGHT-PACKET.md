# S8 OCR proof — Security and Docker preflight packet (issue #54)

**Original packet:** prepared 2026-10-16 by the builder as evidence, not an independent Security review.

**Decision update — 2026-10-16:** The requester, declaring sole Security-approver authority, explicitly accepted
PB-02 for the disposable pinned synthetic proof and conditionally accepted PB-08 and PB-13 **for the first build
only**, against source commit `5d7f88035cd25f184572df9969b4411188afd8bc`. See [PR #56](https://github.com/nishanth-cryptos/TrustLens/pull/56)
Security decision comment `6200838093`, `SECURITY-REVIEW-CHECKLIST.md` and `dependencies.lock.json` for exact
limitations and review provenance. These are requester-declared, not externally authenticated sign-offs.
**PRE_BUILD decisions are SATISFIED, including PB-14 first-build-only consent.** The actual Docker restart policy/state N2 check is still NOT PERFORMED. Before any OCR/probe execution, PE-05/PE-06, **new PE-08** (pinned
vulnerability scan and findings disposition) and **new PE-09** (separate requester authorization to run P1-P11)
remain OPEN. **Docker Desktop manual startup, pinned sources/base acquisition and first proof image build are authorized by PB-14** (PR #56 comment `6205866315`), but only after protected-container preflight and verified N2-ACK.json; do not proceed if states are unexpected. OCR worker execution and scanner acquisition remain unauthorized.
The original pre-approval choices below are preserved as an evidence snapshot.

Labels used below:
- **VERIFIED:** checked offline, with the evidence named.
- **RESIDUAL:** a risk that remains even if every check passes.
- **APPROVAL:** a decision only the accountable reviewer or requester can make.
- **UNPROVEN:** a runtime control that only an authorized build or run can show.

## 1. Acquisition evidence audit — PASS

The audit was re-run offline on 2026-10-16 against the manifest, both evidence records, the download log and the
files themselves. There are no findings.
- The closure manifest SHA-256 equals the approved
  `fd8b27ee639d97f11d0eace695cef940c65321588e55dc09da5be620793c536c`, as does the lock pin.
- 109 logical entries (103 build, 6 runtime) map to **103 unique packages**: all 6 runtime packages are also in the
  build set, and each SHA-256 corresponds to exactly one name, version, architecture, size and URL.
- Every entry's bytes, size and SHA-256 equal the manifest. The architectures are `arm64` (100) and `all` (3).
- Every request URL is exactly
  `https://snapshot.debian.org/archive/{debian|debian-security}/20261006T120000Z/<pool Filename>` for the
  package's suite.
- Every final URL is `https://snapshot.debian.org/file/<sha1>/<name>`, and the SHA-1 equals the SHA-1 of the bytes
  received. The URL-decoded name equals the pool file name, and `%2B` (for `+`) is the only encoding used.
- Identity rests on the package's SHA-256 from the signed index, not on the redirect: the redirect is accepted only
  on that host and path form, and the bytes are pinned independently.
- The download log lists exactly the 103 pool files, with 103 requests and 93,413,868 bytes.
- No source archive, model or unrelated file exists anywhere in the scratch root. Every file is a regular file
  with mode 0600 and every directory is 0700. Every recorded evidence hash still matches.

Evidence is in `PREBUILD-EVIDENCE.md` §Offline package acquisition. The earlier PRE_BUILD evidence (tag signature,
signer key, registry manifests, SBOM, provenance, Debian keys) is preserved at
`~/tl-s8proof-scratch/prebuild-evidence-20261015/`; its `SHA256SUMS` is `f6a61e1a…e4d5`.

## 2. Decisions requiring accountable approval

### PB-02 — Tesseract 5.5.3 tag signer

- **VERIFIED**
  - GnuPG reports `VALIDSIG 49236FEA75C95D698EC2B78AE08C21D5677450AD` over annotated tag object `6951ffe1…`, which
    points to commit `db0ec62f81b0737fbbe184d8fea40af5738f8eef`.
  - The key has a uid `sw@weilnetz.de` that matches the tagger.
  - `https://github.com/stweil.gpg` lists key ID `E08C21D5677450AD`, which is the low 64 bits of that fingerprint.
  - The tag tree is identical to the pinned release archive (empty tree diff), and the archive SHA-256 is pinned in
    the lock and corroborated as recorded in `PREBUILD-EVIDENCE.md`.
- **Limitations**
  - The full fingerprint comes only from `keyserver.ubuntu.com`, where anyone can upload a key.
  - GitHub confirms 64 bits, not the fingerprint.
  - keys.openpgp.org returns 404, WKD has no data, and the distribution packaging has no signing key.
  - The digests prove integrity of the bytes, not their authenticity.
- **RESIDUAL:** an attacker controlling both the maintainer's GitHub-published material and the release archive could
  pass every check above. The OCR runs only on synthetic input inside the isolated worker.
- **APPROVAL, choose one:**
  - (a) accept this chain for the disposable synthetic proof;
  - (b) require out-of-band confirmation of the full fingerprint, naming the channel;
  - (c) reject, and the proof stops.

### PB-08 — Python 3.12.15 and zlib inside the worker

- **VERIFIED**
  - Base `python@sha256:16bf2b5c…` (linux/arm64) has `PYTHON_VERSION=3.12.15` at `/usr/local/bin/python3.12`.
    docker-library builds it from the CPython tarball after SHA-256 and GPG checks (key `7169605F…6305`).
  - The base SBOM lists `zlib1g 1:1.3.dfsg+really1.3.1-1+b1`, the same version as the runtime closure.
  - The worker starts as `python -I -S -B worker_entry.py` (isolated mode, no `site`, no bytecode writes).
  - Input is stdin only, at most `tier1.MAX_BYTES`.
  - Tier 1 is pure `struct`/`binascii` parsing.
  - Tier 2 inflates through `zlib.decompressobj` in 64 KiB steps, bounded by `height × (1 + width × channels)`, and
    checks the header, preset dictionary, Adler-32, trailing data and filter bytes. These checks have offline tests.
- **RESIDUAL**
  - A full CPython interpreter, plus zlib's C inflate, is a large trusted base for a validator.
  - A memory-safety bug in zlib or CPython would run inside the worker, where the much larger Tesseract and
    Leptonica surface also runs.
  - **No vulnerability scan has been run.** No tool is installed, and acquiring one needs authorization.
- **UNPROVEN:** that Python's `zlib` module links the image's `libz.so.1` (expected for docker-library builds; not
  shown by build evidence today), and that the D3 isolation flags hold at run time (P5–P10).
- **APPROVAL, choose one:**
  - (a) accept Python 3.12.15 as the worker validator for the disposable proof;
  - (b) accept, on condition of a vulnerability scan of the runtime image before `run`, with the tool selected
    under PB-13;
  - (c) require a different validator, which means a redesign.

### PB-13 — checklist S1–S19

The reviewer records findings in `SECURITY-REVIEW-CHECKLIST.md` against a named commit.

| Item | VERIFIED offline | UNPROVEN at run time | RESIDUAL / APPROVAL |
| --- | --- | --- | --- |
| S1 Operator privilege | Documented (README privilege notice) | — | **APPROVAL:** accept a root-equivalent Docker operator on the VM shared with the dev containers |
| S2 Worker flags | Exact flag tuple, offline test | Enforcement (P5–P10) | — |
| S3 Tier 1 | AST test (no decompression); corpus | — | — |
| S4 Tier 2 bounds | Bomb and corpus tests | That it runs only in the worker | — |
| S5 Fixed invocation | Fixed argv/env tests | P4 | Tesseract file-list fallback and Leptonica BMP/PNM/SPIX readers remain in the binary |
| S6 Python | See PB-08 | — | **APPROVAL** via PB-08 |
| S7 Build network | Every `RUN --network=none`; static reviewer, with mutation regressions | BuildKit honours `--network=none` and the read-only bind mount | — |
| S8 Package closure | Resolver tests; manifest byte-identical; 109 entries verified (§1) | apt installs the exact local paths with no lists; file/checksum/control/`dpkg-query`/`dpkg --audit` checks pass; no base package changes (PE-05) | Essential set assumed present (Policy §3.5). The build closure includes network-capable libraries pulled in by `cmake` (`libcurl4t64`, `libgnutls30t64`, `libssh2-1t64`, `libkrb5-3`, `libldap2`, `libnghttp2-14`, `librtmp1`), in the builder stage only, with no network; the runtime stage installs only its 6 packages |
| S9 N2 | `require_ack` tests | — | See §3 |
| S10 Mutation scope | `assert_proof_resource`; cleanup tests | — | — |
| S11 Data and paths | F1 tests; synthetic corpus | — | Path strings are passed to the Docker CLI |
| S12 Probe image | Static review | Probe build without pull (PE-06) | Measurements include probe overhead |
| S13 Supply chain | Archive, base and closure digests; SBOM and SLSA provenance verified by digest | Build evidence (CMake caches, `ldd`, `tesseract --version`) | **APPROVAL:** Docker Hub attestations are **unsigned** (digest integrity only). **APPROVAL:** select SBOM, vulnerability and licence tooling (AC-03–AC-05); none is installed |
| S14 Lock phases | F5 tests | — | — |
| S15 Cleanup | F2 tests (mocked Docker) | Real cleanup | — |
| S16 Deadline and output | F3/F4 tests | — | — |
| S17 Build record | F5 integrity tests | First real record | — |
| S18 Context binding | Context tests; all 109 packages fingerprinted | — | — |
| S19 Nonroot readability | Static review | UID 65534 build-time read check | — |

Known residual risks the reviewer must accept or reject explicitly:
- the shared Docker Desktop VM;
- the Docker-managed `/etc/hosts`, `/etc/hostname` and `/etc/resolv.conf` mounts;
- linux/arm64 only;
- image-ID reproducibility unproven until two builds match;
- P1 uses a bitmap font, so its character error rate says nothing about real screenshots.

## 3. N2 operator preflight for the first build

**Facts known offline**
- Docker Desktop's `AutoStart` setting is `false` (read from `settings-store.json`, read-only), so it starts only
  when the operator starts it.
- The restart policies of `trustlens-postgres-dev` and `trustlens-keycloak-dev` **cannot be read while the daemon is
  stopped** and are not recorded in the repository. They are UNKNOWN until step 3.

**Startup consequences to acknowledge before starting Docker**
- **Containers may restart on their own.** If a protected container has restart policy `always`, or
  `unless-stopped` and was running when Docker last stopped, it starts automatically:
  - PostgreSQL reopens its persistent volume `trustlens-pg-dev`, running normal crash recovery if the last stop
    was unclean;
  - Keycloak starts;
  - any published ports become reachable again on the host.
- **Shared resources:** the build shares the VM's CPU, memory and disk with them (`cmake --parallel $(nproc)`), so
  the dev services may slow down during the build.
- **What the proof never does:** it does not stop, restart, reconfigure, network with, exec into or attach to the
  protected containers. It runs no `prune`, `volume`, `network` or `system` command. No cleanup or reset is part of
  this procedure.

**Exact commands** (run from the repository root; `NAME` is the authorizing person):

```sh
R="$HOME/tl-s8proof-scratch"; W=proof-20261016; S="--scratch-root $R --workdir $W"
# 1. Requester's written pre-start acknowledgement of the consequences above (issue #54), as part of PB-14.
# 2. The operator starts Docker Desktop manually. The harness never starts it.
apps/backend/.venv/bin/python tools/s8-ocr-proof/harness.py preflight $S        # 3. read-only; writes preflight.json
# 4. Write "$R/$W/N2-ACK.json" with the restart policies observed in step 3 (README step 3 template).
apps/backend/.venv/bin/python tools/s8-ocr-proof/acquire.py $S --authorized-by "$NAME" --pull-base   # 5. NO --debs
apps/backend/.venv/bin/python tools/s8-ocr-proof/gen_synthetic_png.py $S        # 6. synthetic corpus
apps/backend/.venv/bin/python tools/s8-ocr-proof/harness.py build $S --authorized-by "$NAME"        # 7.
```

**STOP conditions**
- Step 3 reports any `PROBLEM`: cgroup v1, no seccomp, or existing `tl-s8proof-*` containers.
- A protected container is in an unexpected state.
- A download in step 5 mismatches its pin.
- `build` refuses for any reason.

None of these is to be worked around.

**Resources touched**

| Where | What |
| --- | --- |
| Network (step 5 only) | `tesseract-5.5.3.tar.gz` (1,916,037 B, GitHub), `leptonica-1.87.0.tar.gz` (14,802,808 B, GitHub), `eng.traineddata` (4,113,088 B, raw.githubusercontent.com); base-image pull `python@sha256:16bf2b5c…` (4 layers, 43,533,362 B compressed) |
| Scratch `~/tl-s8proof-scratch/proof-20261016/` | `preflight.json`, `N2-ACK.json`, `acquisition.json`, `downloads/` (sources plus the existing `debs/`), `corpus/`, `context/`, `runtime-build.log`, `probe-build.log`, `runtime.iid`, `probe.iid`, `build-evidence/`, `build.json` |
| Docker | Base image (pulled by digest); tags `tl-s8proof-runtime:proof` and `tl-s8proof-probe:proof` with label `trustlens.s8proof=v1`; BuildKit cache; one labelled `tl-s8proof-evidence-*` container, created (never started) and removed again during `build` |
| Not touched | The repository working tree; `~/.docker`; `~/.config/trustlens`; `~/.local/share/trustlens`; PostgreSQL, Keycloak and their volumes; keys, credentials and evidence storage |

## 4. Git source-inclusion inventory (nothing staged)

**Safe to commit:** the 25 untracked files under `tools/s8-ocr-proof/`. No `.gitignore` rule matches them. A scan
for private-key blocks and password, secret, token or API-key assignments found nothing, and no absolute home path
appears in them.
- **Docs:** `README.md`, `PREBUILD-EVIDENCE.md`, `SECURITY-REVIEW-CHECKLIST.md`, `SECURITY-PREFLIGHT-PACKET.md`.
- **Lock and closure:** `dependencies.lock.json`, `packages/closure-manifest.json`,
  `candidates/apt-sources.debian-trixie-20261006T120000Z.list` (326 B, text).
- **Code:** `acquire.py`, `debclosure.py`, `harness.py`, `pathguard.py`, `gen_synthetic_png.py`, `common/tier1.py`,
  `worker/tier2.py`, `worker/worker_entry.py`, `probe/probe.py`, `docker/Dockerfile.worker`, `docker/Dockerfile.probe`.
- **Tests:** `tests/fixtures.py`, `tests/test_offline.py`, `tests/test_codex_findings.py`,
  `tests/test_f5_build_integrity.py`, `tests/test_context_and_permissions.py`, `tests/test_python_path.py`,
  `tests/test_debclosure.py`.

**Never commit:**
- everything under `~/tl-s8proof-scratch/`: the 109 `.deb` files, the acquisition and verification records, the
  one-off driver, verifier and log, and the preserved prebuild evidence (keys, keyrings, clone, registry blobs);
- any `downloads/`, `context/`, `corpus/`, `build-evidence/`, `*.iid`, logs or `results.json`;
- session temporary directories, `__pycache__`, keys, credentials and `.env` files.

Before committing, the user confirms the set with
`git status --porcelain --untracked-files=all -- tools/s8-ocr-proof` (expect exactly these 25 paths) and adds them
by explicit path.

## 5. Approval record and mandatory preflight before building

1. **The user** commits the 25 files on `phase9-s8-ocr-proof`. That commit is the one under review.
2. **Security** reviews that commit and records:
   - PB-02 (a/b/c) and PB-08 (a/b/c);
   - PB-13: every S1–S19 finding, the five residual risks, the unsigned attestations, and the SBOM, vulnerability
     and licence tooling.

   The decisions go into the lock through a reviewed change, after which `check-lock` shows only PB-14 open.
3. **The requester granted PB-14** with written acknowledgement of the possible auto-restart and resource consequences (PR #56 comment `6205866315`). **The actual preflight remains unperformed**: operator must manually start Docker Desktop, inspect protected container states/policies and record the observed values in N2-ACK.json before sources/base acquisition or the first build. STOP on unknown/unexpected state. Execution PE-08/PE-09 remain OPEN.

| Decision | Accountable | Decision (a/b/c) | Conditions | Commit reviewed | Date |
| --- | --- | --- | --- | --- | --- |
| PB-02 | Requester-declared sole Security approver | (a) limited ACCEPT | Unauthenticated full signer fingerprint risk accepted only for pinned synthetic worker | `5d7f88035cd25f184572df9969b4411188afd8bc` | 2026-10-16 |
| PB-08 | Requester-declared sole Security approver | (b) CONDITIONAL | Actual Python/zlib linkage under PE-05 and pinned image vulnerability scan PE-08 before run | `5d7f88035cd25f184572df9969b4411188afd8bc` | 2026-10-16 |
| PB-13 | Requester-declared sole Security approver | CONDITIONAL BUILD ONLY | S1–S19 findings, residuals accepted for proof, Syft/Grype selected but not acquired; PE-08 and PE-09 gate run | `5d7f88035cd25f184572df9969b4411188afd8bc` | 2026-10-16 |
| PB-14 + N2 pre-start acknowledgement | Requester | APPROVED FOR BUILD ONLY | Written restart/resource-risk acknowledgement; actual preflight, state/policy inspection and scratch N2-ACK.json still required before acquisition/build. No OCR run or scanner download. PR #56 comment `6205866315`. | `d57596fa8b86d1df34ed5cf0c720796f8f568d61` | 2026-10-16 |
