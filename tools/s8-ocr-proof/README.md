# S8 worker-only OCR proof — disposable artifacts

**Status: PROPOSED — NOT AUTHORIZED TO RUN.** These files implement the worker-only proof plan in
[§4A of the S8 governance proposal](../../docs/07-implementation/S8-screenshot-ocr-governance-proposal.md).

This is **not** TrustLens backend integration, S8 implementation authorization, the S2 containerised-backend addendum,
or OCR activation. No TrustLens feature flag, route, database, migration, evidence store, key or UI is touched.

No Docker image has been built or run for this proof. The immutable base-image digest, dependency pins and
112 offline test results are recorded, but they do not demonstrate real OCR or runtime isolation. The requester,
as the user-declared sole Security approver, conditionally accepted PB-02/PB-08/PB-13 for first construction
against source commit `5d7f880` (see [PR #56](https://github.com/nishanth-cryptos/TrustLens/pull/56) and
[SECURITY-REVIEW-CHECKLIST.md](SECURITY-REVIEW-CHECKLIST.md)). **PB-14 is SATISFIED for the first build only:** the requester acknowledged the N2 pre-start risks and
explicitly authorized manual Docker Desktop startup, read-only preflight, pinned artifact/base acquisition and first
proof-image construction (PR #56 comment `6205866315`). **Actual container restart policies/states have not yet
been observed; N2-ACK.json must still record them after successful preflight, and any unexpected state is a STOP.**
Separate PE-09 authorization and PE-08 vulnerability scan review are required before any worker/OCR run.

**FIRST BUILD ATTEMPT (2026-10-16): failed closed before apt or compilation.** On Docker Desktop 4.90.0,
`RUN --network=none` exposed DOWN kernel tunnel interfaces plus `lo`; the original exact
`ls /sys/class/net == lo` assertion rejected their presence. No non-loopback IPv4 route,
IPv6 route/address or IFF_UP state was found in two separate isolated diagnostic builds.
The Dockerfile now uses a fail-closed interface-UP/routing/address guard. **PB-13 was reopened for
Security re-review and, on 2026-10-21, renewed for the amended source `b62efb1` only** (PR #56 comment
`6318871714`), with PB-14 extended by **one** additional build-only retry. The retry still requires a fresh N2
preflight and N2-ACK.json; BuildKit isolation and the guard's behaviour on live kernel data remain unverified.
No OCR run is authorized.

**BUILD RETRY (2026-10-21): failed closed at runtime stage 5/7** with `untraversable directory under /opt/tl`, after the network guard, compilation and installation had passed. The log does not name the directory. The likely offending path is `/opt/tl/worker`, **inferred** from the BuildKit/fsutil copy implementation (fsutil `copy.Copy` creates a COPY's destination directory with its `--chmod` mode: tonistiigi/fsutil `c1c5bff` `copy/copy.go` L85-89) and from the log (the readability check, which also covers directories, passed); the failed build did not establish it. The proposed correction sets the COPY-created `/opt/tl/worker` and `/opt/tl/probe` to 0555 as root and makes the guards list each offending path and mode. After an independent Codex APPROVE of that correction (committed as `5cd1e40`), **PB-13 was renewed for construction only and PB-14 authorizes exactly ONE further build-only attempt** (PR #56 comment `6320631134`); `check-lock` reports `PRE_BUILD: READY`. That attempt still requires a fresh N2 preflight (protected containers restart=no, exited, no PROBLEM) and a newly written matching N2-ACK.json, and is consumed whether it succeeds or fails. The final nonroot image, the daemon's BuildKit behaviour and any worker/probe execution remain undemonstrated.

**SUCCESSFUL BUILD AND EVIDENCE DISPOSITIONS (2026-10-21):** the authorized attempt of `4c7b0bb` built the runtime image `sha256:482c806e43d935988f548de57539fc9b25afd6293219a5d55468f4e875c1e1e6` and the probe image `sha256:5c02b7b52bcba83f15f537be5544ca679a70a5191d2aca8beb4cdc8803e48799` (build-input fingerprint `af3cf235…c028252`). In PR #56 comment `6322860030` the requester-declared Security owner accepted:
- **F1:** ACCEPT_WITH_LIMITATIONS. The cached install/compile steps are supported by the preserved earlier log (SHA-256 `f4eb93cd089354f3c8d849fd706028412d161be9f33fb491ad86664baf5ba51b`); compilation did not rerun in the final attempt.
- **PE-06:** SATISFIED. Local `FROM` resolution against the exact runtime digest was observed, which does not prove zero registry metadata/auth traffic.
- **F4:** documented. Dockerfile `RUN` steps were network-disabled, but Docker/BuildKit registry metadata and authentication traffic occurred for the digest-pinned base, so the whole build is **not** claimed to be offline.

**PE-05 stays OPEN** pending Python-zlib linkage evidence (one reviewed, container-free image export) and reconciliation of N1's network wording. PE-08, PE-09 and AC-01–AC-07 stay OPEN, and no OCR has run.

**PE-05 SATISFIED for static build-evidence review only (2026-10-22, PR #56 comment `6343908889`).** A never-started disposable container (comment `6325610804`) yielded Python's `zlib.cpython-312-aarch64-linux-gnu.so` (SHA-256 `c0f30510…0f06`), whose `DT_NEEDED` is `libz.so.1`, and `libz.so.1` (SHA-256 `6fe00aca…7d65`, equal to the pinned `zlib1g` payload, `SONAME libz.so.1`). Neither has RPATH/RUNPATH, and the required `ZLIB_1.2.0` version is defined. The evidence script **exited 1**: a `set -x` trace polluted its cleanup comparison after every static check had passed. Container removal was confirmed separately ("No such container"). This is static evidence only: no Python import, loader resolution or OCR has been demonstrated. N1/F4 is reconciled: Dockerfile `RUN` steps were network-disabled, but the Docker build as a whole was not offline. PE-08, PE-09 and AC-01–AC-07 stay OPEN.

## Where things live

| In this branch (reviewable sources) | In `<scratch-root>/<workdir>`, outside the repository (disposable) |
| --- | --- |
| `common/tier1.py`: Tier-1 structural PNG preflight; no decompression, no zlib import | `downloads/`: hash-verified sources (`acquire.py`) |
| `worker/tier2.py`: Tier-2 zlib/scanline validation; **runs only inside the worker image** at run time | `corpus/`: generated synthetic PNGs and `manifest.json` |
| `worker/worker_entry.py`: fixed entrypoint: Tier 1, Tier 2, then fixed Tesseract argv | `context/`: Docker build context assembled by the harness |
| `probe/probe.py`: isolation and measurement probe (probe image only) | `preflight.json`, `N2-ACK.json`, `acquisition.json`, `build.json`, `build-evidence/` |
| `gen_synthetic_png.py`: stdlib synthetic corpus (5x7 bitmap font, `SYNTHETIC TEST` text) | `results.json`: P1–P11 outcomes and measurements |
| `docker/Dockerfile.worker`, `docker/Dockerfile.probe` | |
| `dependencies.lock.json`: pinned candidates and OPEN items | |
| `acquire.py`: the only step that downloads dependencies (Docker/BuildKit also contacts the registry for base-image metadata during `harness.py build`; F4); `harness.py`: operator harness | |
| `pathguard.py`: shared fail-closed output-path containment (F1) | |
| `debclosure.py`: offline `.deb` closure resolver; `packages/closure-manifest.json`: its pinned output (PB-11 option O, approved 2026-10-16) | `downloads/debs/{build,runtime}/<sha256>.deb` |
| `tests/test_offline.py`, `tests/test_codex_findings.py`, `tests/test_f5_build_integrity.py`, `tests/test_context_and_permissions.py`, `tests/test_python_path.py`, `tests/test_debclosure.py`, `tests/fixtures.py`: offline checks and regressions (no Docker, no network) | |

Governance §4A said the proof artifacts would live outside the repository. Here the **sources** are versioned on a
review branch so they can be reviewed, while **every run output** stays under an approved scratch root outside the
repository. A reviewer should confirm this reading.

## Output-path containment (Codex F1)

All three tools take `--scratch-root` and `--workdir` and write, read and remove only through `pathguard.Scratch`.

**Scratch root requirements:**
- an absolute, **canonical** path with no symlinked component anywhere (on macOS, use `/private/var/...` or
  `/private/tmp/...`, not `/var/...` or `/tmp/...`);
- owned by you and not group- or world-writable;
- neither inside nor an ancestor of the repository, `~/.config/trustlens`, `~/.local/share/trustlens`, `~/.docker`,
  or `TRUSTLENS_EVIDENCE_DIR` / `TRUSTLENS_EVIDENCE_KEK_FILE` when they are set.

**Workdir requirements:** a relative name of plain components (no `..`, no absolute path).

**How writes are protected:**
- The root is opened by walking from `/` with `O_NOFOLLOW` at every component.
- Below it, every operation uses held directory descriptors with `O_NOFOLLOW`. A path component swapped for a symlink
  after opening cannot redirect a write.
- Files are written to an `O_EXCL` temporary name and atomically renamed into place.
- Recursive removal never follows symlinks.

**Residual:** the Docker CLI receives path strings (build context, iid file). They are re-verified just before use,
but a process running as the same user could still race them; same-user attackers are outside the threat model.

## Privilege notice

Whoever runs `acquire.py --pull-base` or `harness.py` (preflight, build, run, cleanup) uses the Docker CLI, which
holds **Docker management authority**: root-equivalent on the Docker Desktop VM and over every container it manages.
That operator is a privileged *test operator* (governance D3, privileged trusted components), and the harness is not
a TrustLens component.

The OCR worker holds none of that authority. It runs with:
- no network (`--network none`);
- a read-only root filesystem and no mounts;
- UID/GID 65534 and no capabilities;
- `no-new-privileges` and the default seccomp profile;
- 1 CPU, 256 MiB memory with no swap, and 32 PIDs;
- no Docker logs;
- a 10 s end-to-end deadline and 64 KiB output caps, enforced by the harness.

The harness only ever *reads* existing containers such as `trustlens-postgres-dev` and `trustlens-keycloak-dev`. It
mutates only resources named `tl-s8proof-*` that carry the label `trustlens.s8proof=v1`.

## Offline checks (allowed now)

```sh
apps/backend/.venv/bin/python -m unittest discover -s tools/s8-ocr-proof/tests -v   # 112 previously verified offline tests; no Docker or network
apps/backend/.venv/bin/python tools/s8-ocr-proof/harness.py check-lock              # per-phase OPEN items, exits 1
R="$(python3 -c 'import os,tempfile; print(os.path.realpath(tempfile.mkdtemp()))')"
apps/backend/.venv/bin/python tools/s8-ocr-proof/gen_synthetic_png.py --scratch-root "$R" --workdir corpus-check
```

The offline tests run the validators on *self-generated synthetic* bytes as a development check. They are not the
runtime boundary: at run time Tier 2 executes only inside the isolated worker.

## PRE_BUILD evidence

[PREBUILD-EVIDENCE.md](PREBUILD-EVIDENCE.md) records the verified dependency facts, the candidate (unapproved) base
images, the APT snapshot and `SOURCE_DATE_EPOCH`, the exact acquisition procedures awaiting authorization, the S1–S19
evidence matrix and the first-build authorization checklist. The lock's `candidates` block is informational: no gate
and no fingerprint reads it.

## Lock phases (Codex F5)

`dependencies.lock.json` separates its requirements into three phases. **REVIEW** items are `OPEN` or `SATISFIED`;
`SATISFIED` needs evidence and is set only through a reviewed change, never by a tool. **ARTIFACT** items are always
`PRODUCED_AT_STAGE`: the harness checks the real file in the workdir, so the lock can never claim build or run output.

| Phase | Contents | Gates |
| --- | --- | --- |
| `PRE_BUILD` | PB-01–PB-12 are SATISFIED for the limited synthetic proof (PB-02 signer-key risk accepted; PB-08 Python/zlib conditionally accepted); **SATISFIED: PB-13**, renewed 2026-10-21 for construction only at `5cd1e40` (earlier approvals for `5d7f880` and `b62efb1` are historical); **SATISFIED: PB-14** (exactly one further build-only attempt; fresh N2 preflight and N2-ACK.json required; consumed either way) | `build` |
| `PRE_EXECUTION` | Verified in code: local runtime and probe image IDs equal `build.json` (PE-01/02); build logs (PE-03) and every required build-evidence file (PE-04) present as regular, non-symlinked files matching their recorded size and SHA-256, and the evidence equal to what is baked into the runtime image; the build-input fingerprint equal to the current inputs (PE-07). Reviews: build evidence (PE-05), local `FROM` resolution (PE-06), pinned-runtime-image vulnerability scan and finding disposition **before worker execution** (PE-08), and a **separate requester run authorization** (PE-09) | `run` (together with `PRE_BUILD` and the N2 acknowledgement) |
| `ACCEPTANCE` | Artifacts: rebuild comparison (AC-01), `results.json` (AC-06). Reviews: reproducibility (AC-02), SBOM (AC-03), vulnerability scan (AC-04), licences (AC-05), final review (AC-07) | Nothing; reported as open until produced and reviewed |

### Build record and build-input fingerprint (F5)

`build` writes `build.json` (schema `tl-s8proof-build-record/2`) with:
- the runtime and probe image IDs;
- `{path, bytes, sha256}` for each build log and each build-evidence file;
- `build_input = {fingerprint, manifest}`.

The fingerprint is `SHA-256(canonical JSON(manifest))`. Canonical JSON means sorted keys, `","`/`":"` separators,
ASCII only, and lists in the defined order. The manifest (schema `tl-s8proof-build-input/1`) contains exactly:

| Field | Content |
| --- | --- |
| `platform` | `linux/arm64` |
| `runtime` | target `runtime`, tag, label and exact build arguments (`BASE_IMAGE`, `SOURCE_DATE_EPOCH`, `PYTHON`) |
| `probe` | tag, label, build argument `RUNTIME_IMAGE` |
| `build_context` | The **complete** expected Docker build context, sorted by path: every directory `{path, type: dir, mode: 0700}` and every file `{path, type: file, mode: 0600, size, sha256}`. That is both Dockerfiles, `tier1.py`, `tier2.py`, `worker_entry.py`, `probe.py`, the three pinned sources and the model under `sources/`, the generated `sources/SHA256SUMS` (`<sha256>  <file>` lines sorted by file name), and for each of `debs/build` and `debs/runtime` every closure package as `<sha256>.deb` plus the generated `SHA256SUMS` and `selection.txt` (`<sha256>.deb name version architecture size` lines in manifest order). It is computed from the lock pins and repository files, never read back from the prepared context. |
| `sources` | `{name, file, bytes, sha256}` of each pinned source and the model, sorted by name |
| `base_image` | the pinned reference and the image ID actually acquired (`acquisition.json`) |
| `python` | image path and exact version |
| `apt` | snapshot sources-file SHA-256, the exact build and runtime package pins, and the closure-manifest SHA-256 |
| `source_date_epoch` | the chosen value |

Nothing that cannot change the image is included: no review status or evidence text, approvals, lock notes,
licence notes, acceptance results or rebuild findings. A legitimate post-build approval therefore never invalidates
an unchanged build.

Before `run` (and before `rebuild`), the harness:
- recomputes the manifest from the current repository files, lock and `acquisition.json`;
- checks that the recorded manifest still hashes to the recorded fingerprint;
- re-scans the prepared `context/` on disk (without following symlinks) and requires it to equal the expected context
  exactly: no extra, missing, altered, re-moded, symlinked or special entries.

`build` refuses unless the prepared context equals the expected context, and `rebuild` regenerates a fresh context and
verifies it before building. `run` then additionally confirms the
local image IDs and re-reads the evidence from inside the runtime image. `check-lock` is offline, so it can never
report `PRE_EXECUTION` as passed.

There is no cycle: `build` needs only `PRE_BUILD`, and the reproducibility rebuild is a separate ACCEPTANCE step
(`harness.py rebuild`). `harness.py check-lock [--phase P] [--scratch-root R --workdir W]` prints every phase; with a
workdir it also checks the ARTIFACT items.

## Later, separately authorized proof run (exact commands)

Set `R` to an approved canonical scratch root (for example `R="$(python3 -c 'import os,tempfile; print(os.path.realpath(tempfile.mkdtemp()))')"`),
`W` to a workdir name such as `run1`, and `NAME` to the authorizing person. `S="--scratch-root $R --workdir $W"`.

0. **Authorization.** Security's conditional build-only review and requester PB-14/N2 pre-start acknowledgement are
   recorded on PR #56. Confirm the reviewed proof branch and `PRE_BUILD: READY` before any build. This does NOT waive
   inspection of real restart policies and protected container states once Docker Desktop starts.
1. **N2 preflight, before starting Docker Desktop.** Starting the daemon may automatically restart existing
   persistent containers, including `trustlens-postgres-dev` and `trustlens-keycloak-dev`, according to their restart
   policies. The repository does not record those policies, and they cannot be read while the daemon is stopped.
   Establish them from your own records, or accept that the containers may start, and approve that consequence. Then
   start Docker Desktop yourself; the harness never starts it.
2. **Read-only inventory:** `apps/backend/.venv/bin/python tools/s8-ocr-proof/harness.py preflight $S`.
   This records the daemon facts and every existing container's restart policy and status, and refuses on missing
   cgroup v2 or seccomp. If anything is unexpected, including the state of the existing protected containers,
   or isolation from existing services can't be established, **STOP**.
3. **Acknowledge** by writing `"$R/$W/N2-ACK.json"`. It must record the policies observed in `preflight.json`:
   ```json
   {"operator": "NAME", "date": "YYYY-MM-DD",
    "reviewed_restart_policies": {"trustlens-postgres-dev": "<observed>", "trustlens-keycloak-dev": "<observed>"},
    "accepted_startup_consequences": true}
   ```
4. **Acquire** (the only dependency-download step; F4: `harness.py build` still causes Docker/BuildKit registry metadata/auth traffic for the pinned base):
   `apps/backend/.venv/bin/python tools/s8-ocr-proof/acquire.py $S --authorized-by "$NAME" --pull-base --debs`
   (`--debs` fetches the 109 closure packages, about 97 MB, from `snapshot.debian.org`. They were acquired and verified
   on 2026-10-16 in workdir `proof-20261016` (see `PREBUILD-EVIDENCE.md`), so omit `--debs` there.)
5. **Corpus:** `apps/backend/.venv/bin/python tools/s8-ocr-proof/gen_synthetic_png.py $S`
6. **Build** (requires `PRE_BUILD`; builds the runtime and probe images and extracts the build evidence):
   `apps/backend/.venv/bin/python tools/s8-ocr-proof/harness.py build $S --authorized-by "$NAME"`.
   Then complete the `PRE_EXECUTION` reviews (PE-05, PE-06) through a reviewed lock change.
7. **Run P1–P11 and the measurements** (requires `PRE_BUILD`, the `PRE_EXECUTION` artifacts and reviews, and N2):
   `apps/backend/.venv/bin/python tools/s8-ocr-proof/harness.py run $S --authorized-by "$NAME"`.
   Optional ACCEPTANCE evidence: `harness.py rebuild $S --authorized-by "$NAME"`.
8. **Clean up** proof-owned resources only:
   `apps/backend/.venv/bin/python tools/s8-ocr-proof/harness.py cleanup $S --remove-images`.
   This removes containers named `tl-s8proof-*` with the proof label, and the three proof tags. The base image is
   left for the operator, who removes it by exact reference if wanted. Existing containers are never touched.
9. **Report:** summarise `results.json` into the governance document through a separate reviewed change. Report
   actual values only. P1 is functional, with a character error rate and differences recorded and no accuracy claim.
   The measurements decide whether the D2 values (10 s, 256 MiB) are workable.

## Offline package installation (PB-11 option O)

Every Dockerfile `RUN` instruction is **required to have no network access** (`RUN --network=none`). This does not cover the privileged Docker/BuildKit control plane: resolving the digest-pinned base image produced registry metadata/authentication traffic in the 2026-10-21 build (F4), so the build as a whole is not claimed to be offline. The additional fail-closed N1 guard verifies no enabled non-loopback interfaces, non-loopback IPv4/IPv6 routes or IPv6 addresses; it does not mistake DOWN kernel tunnel devices for usable connectivity. The updated guard was approved for construction (PB-13) and passed in every shell `RUN` step that executed in the 2026-10-21 builds; it is silent on success, so the evidence is each step's successful exit.
- `debclosure.py --index-dir <dir with the verified InRelease and Packages.xz> --output packages/closure-manifest.json`
  re-checks each InRelease against the lock-pinned SHA-256 and each `Packages.xz` against its InRelease entry, then
  resolves the closure of the pinned build and runtime packages: Pre-Depends and Depends, alternatives (an already
  selected package first, then the first real alternative, then a single virtual provider), versioned Provides, `:any`
  / `:native` qualifiers, version constraints, and Conflicts/Breaks inside the closure. Folded (multi-line) fields
  are unfolded before parsing, never discarded. Unresolved or ambiguous dependencies, a pin that is not the
  candidate, conflicting duplicate stanzas, orphaned or blank continuation lines, duplicate or malformed fields,
  empty relationship groups, `|` in Provides/Conflicts/Breaks, malformed or missing metadata, foreign architectures
  and changed indices are all refused. The output is canonical JSON and byte-identical on rerun.
- Nothing is subtracted for the base image: the closure is resolved from an empty installed set, so it also contains
  packages the base already ships (for example `libc6`, `zlib1g`), at the same versions the base SBOM lists. The base
  SBOM is **not** taken as proof of its dpkg state; the build checks that state instead (see below). The one
  assumption is that the base contains the Essential set, because packages need not declare dependencies on
  Essential packages (Debian policy §3.5).
- `acquire.py --debs` fetches each package from its snapshot pool URL and refuses any byte that does not match the
  manifest's size and SHA-256 before writing. `harness.py build` refuses a `downloads/debs/<group>` directory with a
  missing, extra, altered or non-regular file, copies the packages into the context as `<sha256>.deb`, and adds the
  generated `SHA256SUMS` and `selection.txt`. All of it is in the build-context fingerprint (and so in PE-07).
- In each stage the Dockerfile bind-mounts `debs/<group>` read-only, deletes every apt source and list (and asserts
  none remains), then, before installing: requires the directory to hold exactly the files in `selection.txt` plus
  `SHA256SUMS` and `selection.txt`, requires `SHA256SUMS` to list the same files, runs `sha256sum -c --strict`, and
  checks each file is regular, has the exact size, and has the exact control name, version and architecture
  (`dpkg-deb -W`). Only then does it run `apt-get install -y --no-install-recommends --no-remove` with exactly those
  `./<sha256>.deb` paths (no glob, no `--no-download`, which is incompatible with local paths). Afterwards it checks
  every installed version and architecture with `dpkg-query` and requires a clean `dpkg --audit`. There is no
  fallback to the network, no `apt-get update`, no `--allow-downgrades`, and no removal; any gap in the closure fails
  the build.

## Nonroot readability of the images

The worker and probe run as UID 65534, while the host scratch files stay 0600 and directories 0700. The Dockerfiles
therefore never inherit host modes:
- Every `COPY` from the build context names individual files and sets `--chmod=0444` explicitly.
- The runtime stage makes `/opt/tl` read-only (`chmod -R a-w`). A root guard then fails the build if any file under
  `/opt/tl` is not world-readable, or any directory not world-traversable.
- After `USER 65534:65534`, both the worker and probe stages run a `RUN --network=none` check *as UID 65534*. It
  opens every runtime script and the model (worker) or the probe and worker scripts (probe), and fails the build if
  any is unreadable.
- `harness.py` enforces these rules with a static review (`static_dockerfile_review`) offline and again on the
  prepared context before `build`.

Static checks cannot prove that the images start; that needs a later, authorized Docker build and run.

## Execution and cleanup semantics (Codex F2–F4)

- **Cleanup (F2).** Every container is removed by exact name in a `finally` block, and the removal is verified as
  `PRESENT`, `CONFIRMED_ABSENT` or `UNKNOWN`. A failed or ambiguous Docker query is `UNKNOWN`, never absence.
  `removed` is true only for `CONFIRMED_ABSENT`. Any unconfirmed removal marks the run **FAILED** and records the
  uncertainty. Only containers with the proof label *and* the `tl-s8proof-` prefix are touched; no network, volume
  or prune command exists.
- **Deadline (F3).** One absolute monotonic deadline per run is checked while running and again on the completed
  result. An `exit 0` observed after the deadline is `TIMEOUT`, and its output is discarded. Output beyond 64 KiB is
  `OUTPUT_EXCEEDED` even with `exit 0`. Output is kept only for timely, bounded, cleanly ended runs.
- **P11 (F4).** Each of the three runs must be a timely, bounded, non-empty, cleaned-up success before the output
  digests are compared. Identical empty failures fail.

The offline tests prove this decision logic with mocked Docker results. They do **not** prove the real Docker or
runtime controls; only an authorized proof run can.

## Test mapping (§4A)

| Test | Implementation |
| --- | --- |
| P1 | Worker image on `valid-tiny`, `valid-phone` (1170×2532) and `valid-max` (4096×1953). Passes only if real English words are extracted; CER and a unified diff are recorded. |
| P2 / P3 / P4 | Worker image on every `t1-*`, `t2-*` and `np-*` corpus item. Requires the expected exit code and `TLCAT` category, and no `TLSTAGE:ENGINE_STARTED`. |
| P5 | Probe `net`: DNS, public, gateway and `host.docker.internal` attempts all fail; only `lo`; no routes. |
| P6 | Probe `fs` / `identity` / `env`: all writes refused, read-only root, only Docker-managed mounts, UID/GID 65534, zero capabilities, `NoNewPrivs`, seccomp mode 2, minimal environment. |
| P7 | Probe `limits` (`memory.max` = 256 MiB, `memory.swap.max` = 0) and `mem` (OOM-killed). |
| P8 | Probe `cpu` (`cpu.max` = 1 CPU; measured ratio recorded) and `pids` (`pids.max` = 32; fork fails below 32). |
| P9 | Probe `flood-stdout` / `flood-stderr`: cut and killed at 64 KiB + 1 and removed. |
| P10 | Probe `sleep`: killed at the 10 s deadline and removed; `docker logs` yields nothing; no proof containers remain. |
| P11 | Worker on `valid-phone` three times: identical output digests. |
| Measurements | Probe `measure-ocr`, five runs per valid image: container wall-clock, validate+OCR and engine time, cgroup `memory.peak` and `cpu.stat` (probe overhead included and flagged); host facts from `preflight.json`. |
