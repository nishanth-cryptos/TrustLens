# S2 local-development profile (T09 subset and evidence key profile)

| Field | Value |
| --- | --- |
| Approved | Sponsor, 2026-10-14, for **local development with synthetic data only** |
| Condition | Bounded **local** admission control is implemented (below); it is per process and not production rate limiting |
| Not claimed | Production values, production key management, complete T09 |

## Bounded parameters

| Parameter (OPS-001) | Value | Where enforced |
| --- | --- | --- |
| Accepted evidence media | `text/plain; charset=utf-8` only, valid UTF-8; no images, PDF, audio, video; URLs never fetched | `evidence.py` |
| Maximum original text evidence | 64 KiB (declared length and streamed body) | `evidence.py` (`MAX_EVIDENCE_BYTES`) |
| Maximum JSON request body | 128 KiB | `cases.py` (`MAX_JSON_BODY`) |
| `IDEMPOTENCY_ACTIVE_WINDOW` | 24 h | `idempotency.py` |
| `IDEMPOTENCY_CLAIM_LEASE` | 30 s | `idempotency.py` |
| Page size | default 20, maximum 100 | `cases.py` |
| Cross-store retries | maximum 3 attempts, backoff 1–30 s (doubling), then `FAILED_TERMINAL` | `evidence.py` |
| Client retries / finalize polling | the same idempotent request ≤ 3 attempts; status polling ≤ 10 attempts | `cases.ts`, `evidence.ts` |
| Data class | every case and submission is marked `is_synthetic = true` by the server | `cases.py` (`SYNTHETIC_ONLY_PROFILE`) |
| Sign-in admission | 10 requests per connection class (loopback / other), refilling 10/min | `admission.py` |
| State-changing API admission | 20 requests per principal (or per connection class without a session), refilling 30/min; `429 RATE_LIMITED` + `Retry-After` | `admission.py` |

**Admission limits.** Buckets are held in memory: they are per process, reset on restart and track at most 10 000
keys.
- **Launcher:** `make backend-run` starts `trustlens_backend.serve`, which pins `proxy_headers` off and trusts no
  forwarder. `X-Forwarded-For`, `X-Real-IP` and `Forwarded` are therefore ignored.
- **Identity before sign-in:** callers are keyed by the class of the real TCP peer (loopback or other), never by a
  request header. Rotated or spoofed forwarding headers cannot create new buckets.

This bounds a local, single-process, loopback-only deployment. It is not distributed rate limiting, and it is not a
configuration for running behind a reverse proxy.

**Disposable tests.** `TRUSTLENS_TEST_DISPOSABLE_DB=1` needs explicit `TRUSTLENS_DB_HOST` and `TRUSTLENS_DB_PORT` on a
loopback address in a test env file outside `~/.config/trustlens`. Port 55432 is always refused. Every refusal
happens before a connection is opened.

**Expiry rule (OPS-001 §5).** After the 24 h window a reused key is a **new request**. With migration
`0004_evidence_intake` (addendum P9-S2-ADD-001, approved in GATE-033) the expired record gets a write-once `superseded_at` by
compare-and-swap, and a fresh claim is inserted in the same transaction. Only key digests are stored, nothing is
deleted, and a partial unique index keeps at most one governing record per scope. On a database still at `0003`, which
cannot represent supersession, an expired key is refused as `IDEMPOTENCY_KEY_REUSED`, and evidence intake stays
disabled (`503`).

## Evidence key profile (approved; wired into evidence intake)

- **Encryption:** AES-256-GCM through the pinned `cryptography` library. Each object gets a fresh random 256-bit data
  key, which is wrapped with AES-256-GCM by a 256-bit key-encryption key (KEK).
- **Integrity binding:** the object locator is bound into the authenticated data, so a moved or swapped object fails.
- **Key reference:** `evidence_item.data_key_version_ref = local-kek-v1`, a reference only and never key material.
- **Locators and writes:** locators are server-generated random hex, never paths. Writes are atomic: exclusive temp
  file, fsync, rename, directory fsync.
- **Fail closed:** a missing, short or group/world-readable KEK, or a non-private directory, means no evidence
  operation can proceed. There is no default, derived or plaintext fallback key.
- **Limitations:**
  - one KEK version, with no rotation or re-wrap tooling;
  - losing the KEK makes all stored evidence unreadable;
  - the KEK sits on the same machine as the ciphertext.
  This is not a production KMS.

**Sponsor-run key provisioning.** This creates a private directory and a 32-byte random key, and prints nothing secret:

```sh
mkdir -p ~/.local/share/trustlens && mkdir -m 700 ~/.local/share/trustlens/evidence-dev
( umask 077; set -C; openssl rand 32 > ~/.config/trustlens/evidence-kek-v1.key )
ls -l ~/.config/trustlens/evidence-kek-v1.key        # expect -rw------- and 32 bytes
```

`set -C` (noclobber) makes the shell refuse to overwrite an existing key ("file exists"), and `mkdir` fails rather than
loosen an existing directory. Never commit, copy into the repository or share the key file. The backend reads
`TRUSTLENS_EVIDENCE_DIR` and `TRUSTLENS_EVIDENCE_KEK_FILE` (defaults: the two paths above). If either is missing or
too permissive, evidence operations answer `503` and nothing is written.
