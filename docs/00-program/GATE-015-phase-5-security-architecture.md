# GATE-015 — Phase 5 security architecture and threat-model checkpoint

| Field | Value |
|---|---|
| Document ID | GATE-015 |
| Version | 1.0 |
| Status | **DECISION CANDIDATE** — independent review APPROVED; pending remote CI and merge; not Phase-5 closure |
| Phase assessed | Phase 5 — P5-WP4 identity, authorisation, secrets, keys, egress and STRIDE security architecture |
| Owner role | Chief Architect / Principal Security Engineer |
| Baseline | P5-WP3 merge `12c6c9eb4736537d489ff64bc874ca42e7535c51` |
| Primary deliverables | [ADR-0009](../../adr/ADR-0009-identity-authentication-authorization.md) (Accepted following independent review); [ARCH-004](../05-architecture/ARCH-004-security-trust-threat-model.md) (Decision Candidate) |
| Governing authority | ARCH-001 `INV-01`…`INV-15`, ADR-0004/0007/0008/0010, DET-001 and AI-001 |
| Related risks | RSK-008, RSK-010, RSK-011, RSK-012, RSK-017, RSK-018 |
| Last updated | 2026-09-06 |

## 1. Checkpoint purpose

GATE-015 records the P5-WP4 security-architecture candidate: standards-based external/pluggable OIDC identity with
TrustLens-owned role-and-resource authorisation, service/workload identities, secrets and encryption-key
boundaries, audit-signing trust, controlled external egress and SSRF boundary, malicious-upload handling, safe
logging/error handling, and a full architecture-level STRIDE threat model with a control matrix and residual-risk
statement. It does **not** close Phase 5, accept ADR-0009, authorise implementation, choose a security product, or
perform the independent review.

## 2. Decision criteria

| # | Criterion | Candidate evidence | State |
|---:|---|---|---|
| 1 | ADR-0009 is Accepted following independent review | ADR-0009 metadata; ADR index Accepted section | APPROVED — INDEPENDENT REVIEW |
| 2 | ARCH-004 exists as the authoritative P5-WP4 security/threat-model artifact | ARCH-004 metadata | AUTHORED |
| 3 | Authentication vs. authorisation separation is explicit | ADR-0009 §Decision(2), §Authentication/§Authorization; ARCH-004 §3, §5 | AUTHORED |
| 4 | Standards-based, provider-neutral OIDC identity; no vendor selected; TrustLens stores no passwords | ADR-0009 §Decision(1), Alternatives; ARCH-004 §5.1 | AUTHORED |
| 5 | RBAC + resource-level authorisation with deny-by-default | ADR-0009 §Authorization, §Resource authorization | AUTHORED |
| 6 | Separation of duties (author≠approver) enforced architecturally | ADR-0009 §Separation of duties; ARCH-004 T7/E4 | AUTHORED |
| 7 | Administrator/evidence privilege separation (NFR-14) | ADR-0009 §Human roles, §Privileged access; ARCH-004 I2/E5 | AUTHORED |
| 8 | Service/workload identities defined; no human-credential reuse; least privilege | ADR-0009 §Service identities; ARCH-004 §5.1, S3/E6 | AUTHORED |
| 9 | Secrets-management boundary defined; no secrets in Git/DB rows/logs; env-var precision | ARCH-004 §6 | AUTHORED |
| 10 | Encryption key-purpose separation + envelope-encryption principle + key-management principles | ARCH-004 §7.1–7.3 | AUTHORED |
| 11 | Audit-checkpoint-signing trust; signer separated from app write credentials; app cannot export private key | ARCH-004 §7.5 | AUTHORED |
| 12 | Controlled external egress deny-by-default; AI provider egress bounded; provider failure preserves Phase 4 | ARCH-004 §8.1–8.3 | AUTHORED |
| 13 | SSRF / user-URL boundary addressed | ARCH-004 §8.4 | AUTHORED |
| 14 | Malicious-upload boundary; safe logging; safe error handling | ARCH-004 §9 | AUTHORED |
| 15 | Full STRIDE (S/T/R/I/D/E) across TrustLens boundaries and assets | ARCH-004 §11 (47 threats: 5 S / 8 T / 5 R / 10 I / 9 D / 10 E) | AUTHORED |
| 16 | Security control matrix mapping controls to requirements/threats | ARCH-004 §12 | AUTHORED |
| 17 | Residual risk and load-bearing trust assumptions documented; zero risk not claimed | ARCH-004 §13, §14 | AUTHORED |
| 18 | Phase-3/Phase-4 authority, semantics and `ENGINE_VERSION` frozen | Builder freeze verification | PASS — LOCAL BUILDER |
| 19 | No security runtime implementation, IdP, middleware, secret/key material, or infrastructure added | Builder change-surface verification | PASS — LOCAL BUILDER |
| 20 | Canonical gate and CI self-test remain green | Required local validation below | PASS — LOCAL BUILDER |
| 21 | No security-certification / compliance / admissibility / non-repudiation / production-readiness claim; G-09 OPEN | ADR-0009; ARCH-004 §1, §17; this gate §4 | AUTHORED |

`AUTHORED` means the builder supplied reviewable design evidence. It is not independent approval or acceptance.

## 3. Selected candidate and acknowledged limits

The candidate delegates human authentication to a standards-based, pluggable OIDC provider (Authorization Code +
PKCE) and retains TrustLens-owned role **and** resource authorisation with deny-by-default, separation of duties,
and administrator/evidence separation (NFR-14). It defines service/workload identities, a `SecretProvider`
boundary, separated encryption-key purposes with envelope-encryption principle, an `AuditCheckpointSigner` trust
enhancement, controlled deny-by-default egress with an SSRF boundary, and malicious-upload/safe-logging handling,
supported by a full STRIDE model.

Acknowledged limits: the architecture depends on a correctly configured, trusted external IdP; the audit chain is
tamper-**evident**, not tamper-**proof** — a privileged whole-history plus signing-anchor rewrite remains
possible; break-glass, workload-identity technology, secret/key products, SSRF-controlled fetch, per-endpoint RBAC
and rate-limit thresholds are deferred to P5-WP5 / Phase 6. Retention duration, legal basis and residual metadata
remain OI-05.

### 3.1 Independent review outcome (acceptance-time)

Independent P5-WP4 review returned **APPROVE** — BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 4 / INFO 2. ADR-0009 is
**Accepted following independent review**; ARCH-004 and GATE-015 remain Decision Candidates pending remote CI and
merge. The four LOW findings are recorded follow-ups and are **not** fixed under this acceptance step (no
architecture redesign, no security code):

| Finding | Summary | Carry-forward target |
|---|---|---|
| LOW-1 | ARCH-004 §16 handoff misattributed Phase-6 data/authorisation contracts to ADR-0011 (which is database migration tooling) | Documentation follow-up — corrected in ARCH-004 §16 to **Phase 6 contracts** (not ADR-0011); no ADR-0011/0012 issued |
| LOW-2 | Signer availability/failure does not explicitly distinguish unsigned/pending from successfully signed checkpoint | **P5-WP5** |
| LOW-3 | SSRF controls do not explicitly name DNS-rebinding / resolve-time TOCTOU validation | **Phase 6 / ADR-0012** |
| LOW-4 | Restore authorisation and restored-evidence integrity re-verification should be explicit | **P5-WP5** |

The 2 INFO items are non-blocking observations carried with the LOW follow-ups. This is acceptance-time
governance bookkeeping only; the security architecture semantics are unchanged.

## 4. Programme and claim status

| Item | Status |
|---|---|
| Phase 1 | PARTIAL |
| Phase 2 | PASS |
| Phase 3 | CLOSED at `phase3-wp8-v1.0`; `ENGINE_VERSION = 1.0.0` |
| Phase 4 | FORMALLY CLOSED at merged GATE-011; bounded optional offline reference/scaffold |
| Phase 5 | P5-WP4 DECISION CANDIDATE; not complete |
| Phase 6 | NOT STARTED |
| Phase 7 / UI | NOT STARTED |
| G-09 | OPEN |

No accuracy, precision, recall, false-positive/negative rate, real-world detection effectiveness, security
certification, penetration-tested, zero-trust, SOC 2 / ISO 27001 / DPDP compliance, evidentiary admissibility,
legal non-repudiation, tamper-proofing, or production-readiness claim is made.

## 5. Required local builder validation

| Check | Required result | Candidate state |
|---|---|---|
| `knowledge/validation/run_all.py` | PASS — 23/23 | PASS — LOCAL BUILDER |
| `knowledge/validation/run_all.py --json` | `gate=PASS`, `validators_run=23`, `validators_failed=0` | PASS — LOCAL BUILDER |
| `knowledge/validation/ci_selftest.py` | PASS — 7/7 defects caught | PASS — LOCAL BUILDER |
| Phase-3/Phase-4 freeze and `ENGINE_VERSION` | zero diff; `1.0.0` | PASS — LOCAL BUILDER |
| Markdown whitespace and `git diff --check` | clean | PASS — LOCAL BUILDER |

Local builder results are recorded here after execution. They do not replace independent review or remote CI.

## 6. Finalisation conditions

GATE-015 may be finalised only after:

1. a separate independent review returns **APPROVE**;
2. ADR-0009 is independently approved before any Accepted status;
3. canonical local validation and CI self-test pass;
4. remote CI passes where triggered; and
5. the approved changes merge to `main`.

Phase-5 closure remains later integrated gate work (P5-WP7). P5-WP5 must not start under this builder checkpoint.

## 7. Change boundary

The candidate change surface is limited to new ADR-0009, ARCH-004, GATE-015, and the ADR index update. ADR-0004/
0007/0008/0010, ARCH-001/002/003, GATE-012/013/014, the risk register, runtime/AI code, promoted schemas/rules/
taxonomies, detection/AI design documents, canonical validators, workflow, security implementation, and UI remain
unchanged.

## 8. Candidate recommendation

Independent review APPROVED the P5-WP4 security-architecture candidate and ADR-0009; acceptance bookkeeping is
complete (ADR-0009 Accepted; ADR index updated; four LOW findings recorded as P5-WP5 / Phase 6 follow-ups).
Continue with required remote CI and merge finalisation. Do not commit yet, and do not begin P5-WP5 in this step.
