# S8 OCR proof — PRE_BUILD dependency evidence

**Status (2026-10-15, authorized acquisition pass): PRE_BUILD DOES NOT PASS.** Of PB-01 to PB-14, seven requirements
are satisfied (PB-01, PB-03, PB-04, PB-05, PB-06, PB-07, PB-10) and seven are open (PB-02, PB-08, PB-09, PB-11, PB-12,
PB-13, PB-14). Nothing here is a Security approval, and PB-14 (construction authorization) is not closed. No Docker
operation, image pull or package installation was performed.

**Offline package preparation pass (2026-10-15):** PB-11 option O was implemented (see
[Offline package closure](#offline-package-closure-pb-11-option-o)).

**Authorized offline package acquisition (2026-10-16, issue #54):** the requester approved PB-09, PB-11 (option O)
and PB-12, and the download of the 109 closure entries; see [Recorded requester decisions](#recorded-requester-decisions-for-the-disposable-standalone-proof-only)
and [Offline package acquisition](#offline-package-acquisition-2026-10-16). PRE_BUILD is still **BLOCKED** by PB-02,
PB-08, PB-13 and PB-14. No Docker operation, image pull or package installation was performed.

## Recorded requester decisions (for the disposable standalone proof only)

- Tesseract **5.5.3** → PB-06 SATISFIED.
- Base family **`python:3.12-slim-trixie` on linux/arm64**, "pending exact verified image digest". The digest was
  verified this pass → PB-07 SATISFIED.
- Bounded downloads of public verification materials, signing-key information and package indices.
- 2026-10-16 (issue #54): **PB-09** snapshot `20261006T120000Z` → SATISFIED; **PB-11** option O, verified offline
  package installation → SATISFIED *as a decision*; **PB-12** `SOURCE_DATE_EPOCH=1792074664` → SATISFIED and set in
  `configuration.source_date_epoch`; download of the 109 `.deb` entries of closure manifest
  `fd8b27ee639d97f11d0eace695cef940c65321588e55dc09da5be620793c536c` (acquisition and verification only).

These do not constitute Security approval and do not authorize Docker operations.

**Approved choices versus unproven runtime controls.** The PB-11 decision selects the design; it does not show the
design works. The controls that only a build can show — BuildKit honouring `RUN --network=none` and the read-only bind
mount, apt installing the exact local paths without lists or sources, the in-build file-set, checksum, control-data,
`dpkg-query` and `dpkg --audit` checks passing, and no base package changing — remain **UNPROVEN** and are now part of
PE-05 (Security review of the build evidence).

## Acquisition record

All files are in a private scratch directory (mode 0700) outside the repository and outside every protected TrustLens
path. They were first written to a session-temporary directory, and on 2026-10-16 a verified local copy was
preserved at `~/tl-s8proof-scratch/prebuild-evidence-20261015/`: 1,528 regular files including the blobless
Tesseract clone, 31,382,599 bytes, modes 0600/0700. The copy is listed in its `SHA256SUMS`
(`f6a61e1af20fa707dad05c56dbc8d6593e2fa55c98785bfa34c8514da4cfe4d5`), and the gpg-agent sockets were not copied.
Nothing was installed or executed.

| Artifact | Source URL | Bytes | SHA-256 | Result |
| --- | --- | --- | --- | --- |
| Tag `5.5.3` (object `6951ffe10ce031374bcd04fe400811da1e7e04ad`) | `https://github.com/tesseract-ocr/tesseract.git` (`refs/tags/5.5.3`, depth 1, blobless) | — | — | Annotated tag → commit `db0ec62f81b0737fbbe184d8fea40af5738f8eef` |
| Tag signature / signed payload | extracted from the tag object | 894 / 142 | `e789d18f…ea67` / `e547fcce…6203` | VALIDSIG `49236FEA75C95D698EC2B78AE08C21D5677450AD` |
| Signer key (keyserver) | `https://keyserver.ubuntu.com/pks/lookup?op=get&options=mr&search=0x49236FEA…50AD` | 15,841 | `5cb125ac164bec19b5d7f1090f153f46da83e0ccb70ede624b1150bde2286f4c` | RSA-4096, created 2015-08-05, uids include `sw@weilnetz.de` |
| Maintainer key listing (GitHub) | `https://github.com/stweil.gpg` | 181 | `794c1fbac726858f7a8a4e1328962452d6ef9d99ad8e5782baf24ed55deceaf3` | Names key ID `E08C21D5677450AD` only (not exportable) |
| Image index | `registry-1.docker.io/v2/library/python/manifests/3.12-slim-trixie` | 10,373 | `a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1` | = `Docker-Content-Digest` |
| linux/arm64/v8 manifest | `…/manifests/sha256:16bf2b5c…` | 1,748 | `16bf2b5c59a08523519d3c8589deca849285dee1d62a3653e124c3dba340f15e` | Self-verified |
| Image config | `…/blobs/sha256:ce9a404c…` | 5,677 | `ce9a404c2c0138e747a43e6ea022d2f7e670ed868df35d627a663ba7fb940ea9` | Self-verified; `PYTHON_VERSION=3.12.15` |
| Attestation manifest | `…/manifests/sha256:48bd8447…` | 841 | `48bd844737bd0fb3a7c8d02a11ebc314ae61b77e6358881b3cde6f82b88558aa` | Self-verified |
| SPDX SBOM | `…/blobs/sha256:ba62fc86…` | 2,152,399 | `ba62fc866f1e590f23723352278b883175d1f41a9f459da3afe4fc3edd5aa8a9` | Self-verified; subject = arm64 manifest; 125 packages |
| SLSA v0.2 provenance | `…/blobs/sha256:e5bc9678…` | 24,369 | `e5bc9678f6a8647b1d1bdcaf68ec4f2dff651e59e0caba58f934666b213a39de` | Self-verified; builder `https://github.com/docker-library` |
| docker-library Dockerfile @ `2a3b794c` | `https://raw.githubusercontent.com/docker-library/python/2a3b794c223ab067d122719541cdd54a068732a5/3.12/slim-trixie/Dockerfile` | 4,972 | `db36efba269b9ace6b432e5d842549cd9f345c38bb4f9ae5617d26dde485047e` | `FROM debian:trixie-slim`; CPython SHA-256 and GPG checks; `/usr/local` |
| Debian 12 archive key | `https://ftp-master.debian.org/keys/archive-key-12.asc` | 11,861 | `c2a9a16fde95e037bafd0fa6b7e31f41b4ff1e85851de5558f19a2a2f0e955e2` | Primary `B8B80B5B…47F8` (listed on keys.html), signing subkey `4CB50190…E131` |
| Debian 12 security key | `https://ftp-master.debian.org/keys/archive-key-12-security.asc` | 11,873 | `74f81645b4e3156d1e9a88c8dd9259271b89c7099d64af89a2a6996b592faa1f` | Primary `05AB9034…A8F0` (listed), subkey `B0CAB926…C7A8` |
| Debian 13 archive key | `https://ftp-master.debian.org/keys/archive-key-13.asc` | 11,861 | `6f1d277429dd7ffedcc6f8688a7ad9a458859b1139ffa026d1eeaadcbffb0da7` | `04B54C3C…88BD` (listed; keyserver match) |
| Debian 13 security key | `https://ftp-master.debian.org/keys/archive-key-13-security.asc` | 11,873 | `844c07d242db37f283afab9d5531270a0550841e90f9f1a9c3bd599722b808b7` | `5E04A1E3…68C6` (listed; keyserver match) |
| Debian 13 release key | `https://ftp-master.debian.org/keys/release-13.asc` | 1,384 | `4d097bb93f83d731f475c5b92a0c2fcf108cfce1d4932792fca72d00b48d198b` | `41587F7D…9DE4` (listed; keyserver match) |
| ftp-master key page | `https://ftp-master.debian.org/keys.html` | 10,718 | `b271f4c351a3b54f6a6be9667bb834809d12ee514055b903ccb06839d274e3e0` | Lists the 11–13 fingerprints |
| `trixie` InRelease | `https://snapshot.debian.org/archive/debian/20261006T120000Z/dists/trixie/InRelease` | 140,421 | `0584fba32e13e0ab8285fb16c27adea1ec03a73669c18702821094fd6ca86675` | SHA-1 = snapshot address `aa33cb31…`; VALIDSIG by the 12 archive, 13 archive and 13 release keys |
| `trixie-updates` InRelease | `…/debian/20261006T120000Z/dists/trixie-updates/InRelease` | 47,340 | `056c3b5e561551a5498fbf8c94a91cd6dbd19da16b984e38fdb2cb1938cb0b98` | SHA-1 = `aef0868f…`; VALIDSIG by the 12 and 13 archive keys |
| `trixie-security` InRelease | `https://snapshot.debian.org/archive/debian-security/20261006T120000Z/dists/trixie-security/InRelease` | 43,409 | `1402f5b326f84ad48b7d32e092165d1f6ee192af737c941d70879f3cf9518818` | SHA-1 = `7d6d9da7…`; VALIDSIG by the 12 and 13 security keys |
| `trixie` arm64 `Packages.xz` | `…/dists/trixie/main/binary-arm64/Packages.xz` | 9,614,192 | `be16b37b2f740f066ea93d35d56f04f94d63693e5a3eb421b052bf86fae75bcd` | = signed InRelease entry |
| `trixie-updates` arm64 `Packages.xz` | `…/dists/trixie-updates/main/binary-arm64/Packages.xz` | 4,424 | `fe771d58d4af39dbb94142d6f3ce578d340c6b1364c172d9e87f2287bdc4994b` | = signed InRelease entry |
| `trixie-security` arm64 `Packages.xz` | `…/dists/trixie-security/main/binary-arm64/Packages.xz` | 264,896 | `32bf01dc144870354d1e077338cf0c7d845e327ed58f505f8eb7added0313db4` | = signed InRelease entry |

Signature checks used isolated GnuPG homes inside the scratch directory; the operator's keyring was not touched.

## PRE_BUILD items

| Item | State | Evidence or reason |
| --- | --- | --- |
| PB-01 Tesseract source pin | **CLOSED** | Commit and archive SHA-256 (two sources) plus Alpine SHA-512. This pass adds: the tag's tree is identical to the pinned archive (724 files). |
| PB-02 Tag GPG with independent trust | **OPEN** (Security) | Cryptography verified: VALIDSIG `49236FEA75C95D698EC2B78AE08C21D5677450AD` on the annotated tag for commit `db0ec62f…`, with a uid matching the tagger email. **Trust is not independently established:** the full fingerprint comes only from an unauthenticated keyserver; GitHub confirms only the 64-bit key ID for the maintainer's account; keys.openpgp.org returns 404; WKD for `weilnetz.de` has no data; the Debian and Arch packaging provide no verifiable key. Security must accept or reject this chain, or name a further channel. |
| PB-03 Leptonica pin | **CLOSED** | Unchanged. |
| PB-04 Leptonica second source | **CLOSED** | Homebrew SHA-256 and Alpine SHA-512 (previous pass), preserved. |
| PB-05 Model pin | **CLOSED** | Unchanged. |
| PB-06 Tesseract version | **CLOSED** | Requester decision: 5.5.3. |
| PB-07 Base image | **CLOSED** | Requester-approved family; pinned `docker.io/library/python@sha256:16bf2b5c59a08523519d3c8589deca849285dee1d62a3653e124c3dba340f15e` (linux/arm64/v8) with verified provenance and SBOM. The attestations are registry-hosted and **unsigned**: their integrity rests on digests, and their authenticity on Docker Hub. Flagged for PB-13. |
| PB-08 Exact Python | **OPEN** (Security part) | Verified facts recorded: 3.12.15; `/usr/local/bin/python3.12` per the docker-library Dockerfile (configure default prefix; `PATH=/usr/local/bin:…`); CPython verified upstream by SHA-256 `c2c43219…` and GPG key `7169605F…6305`. The interpreter attack-surface review is Security's. |
| PB-09 apt sources file | **CLOSED** (requester, 2026-10-16) | Snapshot `20261006T120000Z` approved. Content recorded in the lock (`inputs/apt-sources.list`, 326 bytes, `7ee0a89b…5a19`); the three InRelease signatures re-verified on 2026-10-16. Under option O the file is no longer copied into the build context (the image has no apt sources at all); it remains the reviewed record of the snapshot, and its SHA-256 stays in the build-input fingerprint. |
| PB-10 Exact package pins | **CLOSED** | Resolved from the signature-verified arm64 indices, taking the highest version across the three suites. Must be redone if PB-09 changes the snapshot. |
| PB-11 Package-step reachability | **CLOSED as a decision** (requester, 2026-10-16) | Option O approved: no build step has network access; packages come only from the verified closure, now acquired and verified (below). The runtime controls are **unproven** until the first authorized build and are checked under PE-05. |
| PB-12 `SOURCE_DATE_EPOCH` | **CLOSED** (requester, 2026-10-16) | `1792074664` approved and set in `configuration.source_date_epoch`. It equals 2026-10-15T14:31:04Z, the author and committer time of `d7be441` on `origin/phase9-s8-governance-proposal`. |
| PB-13 Security review | **OPEN** | See the S1–S19 matrix below. |
| PB-14 Requester build authorization | **OPEN** | Deliberately not closed. |

## Resolved package pins (snapshot `20261006T120000Z`, linux/arm64)

| Group | Pin | Suite |
| --- | --- | --- |
| build | `g++=4:14.2.0-1` | trixie |
| build | `make=4.4.1-2` | trixie |
| build | `cmake=3.31.6-2` | trixie |
| build | `pkg-config=1.8.1-4` (transitional; depends on `pkgconf (>= 1.8.1-4)`) | trixie |
| build | `libpng-dev=1.6.48-1+deb13u6` | trixie-security |
| build | `zlib1g-dev=1:1.3.dfsg+really1.3.1-1+b1` | trixie |
| runtime | `libpng16-16t64=1.6.48-1+deb13u6` | trixie-security |
| runtime | `zlib1g=1:1.3.dfsg+really1.3.1-1+b1` | trixie (equals the base image SBOM) |
| runtime | `libstdc++6=14.2.0-19` | trixie (equals the base image SBOM) |

Only these top-level packages are pinned by version in `configuration.apt`. Their complete dependency closure, at
exact versions and hashes, is fixed by `packages/closure-manifest.json` (pinned in the lock), which was resolved from
the same signed snapshot.

## Issues requiring owner or Security approval

1. **PB-02 trust anchor (Security):** accept the keyserver plus GitHub key-ID chain, or require another channel. Until
   then, Tesseract authenticity rests on the archive digests (three sources) and the identical tag tree.
2. **Unsigned Docker Hub attestations (Security, PB-07/PB-13):** accept digest-based integrity, or require signed
   provenance.
3. **Python path — fixed, pending targeted review:**
   - `harness.py` now passes `configuration.python.path_in_image` (`/usr/local/bin/python3.12`) as the required
     `--build-arg PYTHON=…`. It is bound into the build-input fingerprint twice: in `runtime.build_args` and in the
     `python` field.
   - `configuration_errors` rejects any path that is not an absolute, plain `…/python3.12`.
   - The worker Dockerfile declares `ARG PYTHON` with **no default**. The build fails unless the argument is set, is an
     absolute `…/python3.12` path, is executable, and reports Python 3.12.
   - The worker and probe use the interpreter only through `/opt/tl/bin/python`, which links to `$PYTHON`. The static
     review enforces this.
   - Offline regressions: `tests/test_python_path.py`.
4. **PB-08 interpreter attack surface (Security).**
5. **PB-09 snapshot approval (owner):** approved 2026-10-16. A changed snapshot would require PB-10 and the closure to be redone.
6. **PB-11 (owner/Security):** option O approved 2026-10-16 (decision only; runtime controls under PE-05). Previously: accept option O, or choose option N and its
   reachability assessment instead.
7. **PB-12 (owner):** `1792074664` approved 2026-10-16.
8. **PB-13 (Security):** S1–S19 review; S1 privileged-operator risk acceptance; selection of SBOM and vulnerability
   tooling (none is installed).

## PB-11 recommendation (owner decision; nothing performed)

The question: may the two package-install build steps have network access, given that a BuildKit `RUN` with default
networking can reach Docker-host services (for example through `host.docker.internal`)?

| | O — verified offline package acquisition (**recommended**) | N — restricted network during package installation |
| --- | --- | --- |
| How | Before the build, resolve the full dependency closure of the pinned build and runtime packages against the **already signature-verified** snapshot indices, net of packages already in the base image (per its SBOM). Download each `.deb` from the same snapshot, check it against its SHA-256 in the verified index, and add it to the build context. In the Dockerfile, the two networked steps become `COPY --chmod=0444` of the `.deb` files plus `RUN --network=none` installation from local files, with the `lo`-only guard. | Keep the two networked steps, but confine their egress to `snapshot.debian.org`. Docker Desktop / BuildKit has no per-build egress allowlist, so this needs extra infrastructure: an internal network plus a filtering proxy, or firewall rules in the Docker VM. |
| Build-time network | **None.** PB-11 is answered by construction: nothing in the build can reach host services. | Present during package installation, including maintainer scripts running as root. Unreachability of host services must be demonstrated. |
| Integrity | Every package byte is verified before it enters the context, and bound into the build-context fingerprint (and so into PE-07). | apt signature and hash checks with the base image's keyring (sound), but the bytes are not in the fingerprint. |
| Reproducibility | Fully offline once acquired; independent of snapshot-service availability at build time. | Depends on the snapshot service being reachable at build time. |
| Cost and risk | New, reviewed code: a closure resolver (Depends, Pre-Depends, alternatives, virtual Provides) with tests; an `acquire.py` extension; Dockerfile and context-manifest changes. The closure size is not yet measured (no figure assumed). An incomplete closure fails the build safely, because there is no network. | Changes Docker networking configuration (not authorized now) and adds privileged infrastructure to secure. Less code, but more runtime evidence needed. |
| Docker evidence still needed | Only that offline installation succeeds (build log). | The egress restriction, and that host-loopback services (for example the dev PostgreSQL and Keycloak ports) are unreachable from the build step. |

**Recommendation: O.** It removes the reachability question instead of mitigating it. It keeps N1's
"compilation and verification without network" property for the whole build. It reuses the indices and keys already
verified this pass, and it needs no change to Docker infrastructure. It requires an authorized acquisition of the
`.deb` closure and a targeted code review before the first build.

## Offline package closure (PB-11 option O)

**Inputs.** The three InRelease files and `main/binary-arm64/Packages.xz` indices of snapshot `20261006T120000Z`,
already signature-verified in the authorized acquisition pass and held in the private scratch directory. Nothing new
was downloaded. `debclosure.py` re-checks each InRelease against the lock-pinned SHA-256 and each `Packages.xz`
against the size and SHA-256 in its InRelease, so the chain is: Debian archive keys → InRelease signature → InRelease
SHA-256 (lock) → `Packages.xz` entry → package stanza (name, version, architecture, `Filename`, `Size`, `SHA256`) →
`.deb` bytes (checked by `acquire.py --debs`, again by `harness.py build`, and again in the image with
`sha256sum -c --strict`).

**Result** (`packages/closure-manifest.json`, 48,685 bytes, SHA-256
`fd8b27ee639d97f11d0eace695cef940c65321588e55dc09da5be620793c536c`, byte-identical on rerun):

| Group | Packages | Bytes | Notes |
| --- | --- | --- | --- |
| build | 103 | 93,413,868 | includes `init-system-helpers` (Essential, but explicitly depended on) |
| runtime | 6 | 3,584,992 | `gcc-14-base`, `libc6=2.41-12+deb13u4`, `libgcc-s1`, `libpng16-16t64=1.6.48-1+deb13u6`, `libstdc++6=14.2.0-19`, `zlib1g` |

All architectures are `arm64` or `all`. Every package that also appears in the base-image SBOM has the identical
version there, so no downgrade or replacement is expected. That is an expectation, not evidence: the SBOM is not
treated as proof of the image's dpkg state.

**Unresolved or assumed (to be confirmed in Docker):**
1. The Essential set is assumed present in the base image (Debian policy §3.5), so it is not resolved further.
2. apt's handling of an install of explicit local `.deb` paths with no package lists and no sources is unverified
   (the earlier `--no-download` form was incompatible with local paths and was removed).
3. BuildKit support for `RUN --network=none` and `--mount=type=bind` (read-only by default) with the default
   Dockerfile frontend (there is no `# syntax=` directive) is unverified.
4. That installing the closure changes no base package version is expected from the SBOM but unverified. Downgrades
   are not permitted (`--allow-downgrades` is absent), so a mismatch fails the build.
5. Maintainer scripts run as root during installation, but with no network.

**Remaining Docker checks** (first authorized build; all from the build log and `build-evidence/`):
- Both install steps run with only `lo` (the in-build guard passes) and with the bind mount read-only.
- `sha256sum -c --strict SHA256SUMS` passes in both stages.
- The pre-install file-set, checksum, size and control-data checks pass; `apt-get install` of the exact local paths
  completes with no attempt to fetch and no removal, and the `selection.txt` version/architecture check
  passes for every package.
- The in-build `dpkg --audit` check passes in both stages.
- The installed versions of the base packages still match the base SBOM (no downgrade or removal); compare
  `dpkg-query -W` in the built image with the SBOM.
- The final runtime image contains no `.deb` files, no apt sources and no package lists.
- An incomplete closure fails the build rather than reaching the network (expected by construction).

## §Security — evidence matrix for S1–S19 (no sign-off)

| Item | Evidence available now | Status |
| --- | --- | --- |
| S1 Privileged test operator | Documented (README privilege notice) | OPEN — Security risk-acceptance decision |
| S2 Worker flags | `test_harness_worker_flags_match_governance_d3` | Static; runtime enforcement REQUIRES DOCKER (P5–P10) |
| S3 Tier 1 no decompression | AST test; every Tier-1 corpus case | Evidenced offline |
| S4 Tier 2 bounds | Tier-2 corpus, bomb bound test | Logic evidenced offline; worker placement REQUIRES DOCKER |
| S5 Fixed invocation | Fixed-argv and refused-input tests; residual E6/E10 capabilities documented | Static; P4 REQUIRES DOCKER |
| S6 Python in worker | Python 3.12.15 with verified provenance | OPEN — Security (PB-08) |
| S7 Build network policy | Dockerfile static tests (`dockerfile_offline_findings`: every `RUN` offline); `acquire.py` tests; pins from verified indices | Frontend behaviour REQUIRES DOCKER |
| S8 Package closure / reachability | `tests/test_debclosure.py` (resolver, index, manifest, acquisition and context checks); no networked step remains | Offline install REQUIRES DOCKER; PB-11 owner decision OPEN |
| S9 N2 / never starts Docker | `require_ack` tests; code review | Evidenced offline |
| S10 Mutation scope | `assert_proof_resource`, cleanup tests | Evidenced offline (mocked Docker) |
| S11 Data and paths | F1 tests | Evidenced offline |
| S12 Probe image | Static review | REQUIRES DOCKER |
| S13 Supply-chain evidence | This document; base-image SBOM and provenance | Build-time evidence REQUIRES DOCKER; scan tooling OPEN |
| S14 Lock phases | F5 lock tests | Evidenced offline |
| S15 Cleanup verification | F2 tests | Evidenced offline (mocked) |
| S16 Deadline and output | F3/F4 tests | Evidenced offline (mocked) |
| S17 Build-record integrity | F5 integrity tests | Evidenced offline |
| S18 Complete context binding | Context tests | Evidenced offline |
| S19 Nonroot readability | Static Dockerfile review | Build-time UID 65534 check REQUIRES DOCKER |

## Offline package acquisition (2026-10-16)

Authorized by the requester (issue #54): acquisition and verification of the 109 `.deb` entries of the approved
closure manifest only. Nothing was installed, extracted to disk or executed, and no Docker operation took place.

**Pre-download checks.** The manifest SHA-256 equals the approved
`fd8b27ee639d97f11d0eace695cef940c65321588e55dc09da5be620793c536c`. The three InRelease files were re-verified with
`gpgv` against a fresh keyring built only from the ftp-master keys (VALIDSIG primaries `B8B80B5B…47F8`,
`04B54C3C…88BD`, `41587F7D…9DE4` for `trixie`/`trixie-updates`; `05AB9034…A8F0`, `5E04A1E3…68C6` for
`trixie-security`), and their SHA-256 values equal the lock pins. `debclosure.py` re-checked every `Packages.xz`
against its InRelease entry and regenerated a byte-identical manifest. All nine requested pins are present at the
exact version and architecture.

**Procedure.** A one-off driver called the reviewed `acquire.acquire_debs` directly. The `acquire.py` CLI was not
used, because it always downloads the source archives first, which this authorization does not cover. The driver
passed a stricter fetcher:
- HTTPS to `snapshot.debian.org` only, no query strings and no other ports.
- Redirects only to `/archive/…` or to snapshot's content-addressed `/file/<sha1>/<pool file name>`, and the
  received bytes must match that SHA-1.
- The URL-decoded final file name must equal the pool file name.
- Reads are bounded to the manifest size plus one byte, with no retries.
- Packages listed in both groups are fetched once.

`acquire_debs` verifies size and SHA-256 before each atomic write through `pathguard.Scratch`.

**Fail-closed stops, both from the driver's own URL rules, not from package mismatches:**
1. The first run refused snapshot's redirect to `/file/<sha1>/…`, writing nothing.
2. The second run refused the `%2B` encoding of `+` in `g++_14.2.0-1_arm64.deb`, after 9 verified writes. Those 9
   files were removed through `pathguard.Scratch.remove_tree`, so the final set comes from one clean run.

Both rules were narrowed as described above, and nothing was substituted.

**Result** (2026-10-15T19:02:04Z–19:05:30Z UTC):

| | Entries | Bytes | Status |
| --- | --- | --- | --- |
| build | 103 | 93,413,868 | 103 VERIFIED |
| runtime | 6 | 3,584,992 | 6 VERIFIED |
| **total** | **109** | **96,998,860** | **109 VERIFIED, 0 failed, 0 missing, 0 unexpected** |

The 6 runtime packages are also in the build closure, so there were 103 HTTP requests (93,413,868 bytes downloaded),
all of them redirected to snapshot's `/file/` store.

The independent verifier (`verify_debs.py`, read-only) checked each entry for:
- the exact file set per group;
- SHA-256 and size;
- control `Package`, `Version` and `Architecture`, read in memory from `control.tar.xz`;
- regular file, mode 0600.

It found every directory 0700 and no symlinks or special files.

**Evidence paths** (private scratch root, mode 0700, outside the repository, `~/.docker` and every TrustLens
configuration, data, key and evidence location):

| Path | SHA-256 |
| --- | --- |
| `~/tl-s8proof-scratch/proof-20261016/downloads/debs/{build,runtime}/<sha256>.deb` | per the manifest |
| `~/tl-s8proof-scratch/proof-20261016/acquisition-debs.json` (per-file URL, final URL, bytes, SHA-256) | `f72ae711dea59bf3167a4a16fde95569932ce6472db7e65ec21e49aac6f0d477` |
| `~/tl-s8proof-scratch/proof-20261016/verification-debs.json` (per-file checks and status) | `15f84011c1cfe2a5c32d256d520a28bde5ba50ecc7c486ab9da881c460ede7c5` |
| `~/tl-s8proof-scratch/acquisition-tools-20261016/acquire_debs_driver.py` | `ba720382ef8174b1f327649f83c963d1e67baac2bd32dec6df2b06d67d76a742` |
| `~/tl-s8proof-scratch/acquisition-tools-20261016/verify_debs.py` | `bbe1b3173d90e9bad7024d74f39433593b0c9a8a9e5801794e913effa839a1c1` |
| `~/tl-s8proof-scratch/acquisition-tools-20261016/acquire-debs.log` | `6d8f239584885bdae4b6ed873be2590a95e9d7bfcd937834790d34dd9643f855` |

The workdir `proof-20261016` is intended for the first build. `harness.py build` re-checks
`downloads/debs/<group>` against the manifest before assembling the context.

## Exact remaining requirements before the first authorized Docker build

1. **Security:**
   - decides PB-02 (Tesseract tag trust anchor) and PB-08 (interpreter attack surface);
   - signs PB-13 (S1–S19, including S1 risk acceptance, the unsigned Docker Hub attestations, and a review of
     `debclosure.py`, the manifest, the offline Dockerfile steps and the Python-path change).
2. **The user** commits the reviewed proof sources and lock (Git).
3. **The requester grants PB-14:**
   - the N2 preflight and acknowledgement;
   - the Docker Desktop start;
   - `acquire.py --pull-base` into the same workdir: the three source archives and model, plus the base image.
     Do **not** pass `--debs`, because the packages are already acquired and verified.
   - the synthetic corpus;
   - `harness.py build`.

   `check-lock` must then report `PRE_BUILD: READY`.
4. **After the build:** PE-01–PE-07, including PE-05, which now carries the unproven PB-11 runtime controls.
