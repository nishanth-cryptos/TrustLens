# RESEARCH-004 — Evidence Matrix

| Field | Value |
|---|---|
| Document ID | RESEARCH-004 |
| Version | 1.1 |
| Status | **Approved** — closed at the Phase 1 gate, [GATE-001](../00-program/GATE-001-phase-1-assessment.md) |
| Owner role | Threat Intelligence Lead |
| Dependencies | RESEARCH-001, RESEARCH-002, RESEARCH-003 |
| Feeds | KB-001 (rule encoding), DET-001 |
| Last updated | 2026-08-14 |

---

## 1. Purpose

`MP §8` requires every proposed detection concept to map to one or more official references, or
be **explicitly classified as heuristic, experimental or unsupported**. This matrix does that for
all 30 starter rules from the research package, judged against the RESEARCH-001 verification pass
rather than against the research package's own attribution.

Rules are re-keyed to neutral TrustLens identifiers per [DEC-005](../00-program/decision-log.md),
with the research-package identifier retained as `legacy_id`.

**Verdicts.** `SUPPORTED` — a verified primary source substantiates the concept · `PARTIAL` —
partially substantiated, or substantiated only by a corroborating/industry source ·
`UNSUPPORTED` — cited source could not be retrieved; no verified basis exists.

**Implementability** is independent of evidence, and reflects [CONF-003](../00-program/conflict-register.md):
`YES` · `DEFERRED` (needs evidence TrustLens cannot observe) · `PARTIAL`.

---

## 2. The matrix

| TrustLens ID | legacy_id | Concept | Category | Source | Verdict | Impl. |
|---|---|---|---|---|---|---|
| `TL-CRED-001` | RBI-OTP-001 | Claimant requests the user's OTP | `TAX-01-01` | SRC-004 ✅ | **SUPPORTED** | YES |
| `TL-CRED-002` | RBI-UPIPIN-002 | UPI PIN requested outside a payment flow | `TAX-01-02` | SRC-004 ❌(D1) · SRC-005 ⛔ | **PARTIAL** | YES |
| `TL-PAY-001` | NPCI-RECV-003 | Credential prompt framed as needed to *receive* money | `TAX-01-02` | **SRC-021 ✅** | **SUPPORTED** | YES |
| `TL-PAY-002` | NPCI-QR-004 | "Scan QR to receive money" | `TAX-01-03` | SRC-018 ⛔ · SRC-021 ✅(partial) | **PARTIAL** | YES |
| `TL-PAY-003` | CERT-QR-005 | Payee identity unverified before QR payment | `TAX-01-03` | **SRC-021 ✅** | **SUPPORTED** | ⚠️ **DEFERRED** |
| `TL-KYC-001` | HDFC-KYC-006 | KYC update demanded via link or call | `TAX-02-01` | SRC-008 ⛔(D5) · SRC-007 ✅(partial) | **PARTIAL** | YES |
| `TL-PAY-004` | HDFC-FALSECR-007 | False credit claim, refund demanded | `TAX-01-04` | SRC-008 ⛔(D5) | **UNSUPPORTED** | YES |
| `TL-CRED-003` | RBI-CARD-008 | Card number / CVV capture | `TAX-01-07` | SRC-004 ✅ | **SUPPORTED** | YES |
| `TL-IMP-001` | HDFC-CARE-009 | Customer-care number sourced from search/ads | `TAX-02-04` | SRC-008 ⛔(D5) | **UNSUPPORTED** | ⚠️ **DEFERRED** |
| `TL-AUTH-001` | I4C-DARREST-010 | Authority impersonation + legal threat + payment demand | `TAX-03-01` | **SRC-012 ✅✅** | **SUPPORTED** | YES |
| `TL-AUTH-002` | I4C-DARREST-011 | Isolation from family or lawyers | `TAX-03-01` | **SRC-012 ✅✅** | **SUPPORTED** | YES |
| `TL-UTIL-001` | HDFC-UTILITY-012 | Utility disconnection threat + urgent payment | `TAX-07-02` | SRC-008 ⛔(D5) · SRC-007 ✅(partial) | **PARTIAL** | YES |
| `TL-TEL-001` | I4C-USSD-013 | Courier pretext + request to dial a USSD code | `TAX-04-01` | SRC-013 ⛔ | **UNSUPPORTED** | YES |
| `TL-ATO-001` | I4C-WA-014 | Device-linking request (QR or linking code) | `TAX-09-01` | **SRC-017 ✅ + SRC-016 ✅** | **SUPPORTED** | YES |
| `TL-ATO-002` | CERT-WA-015 | Fake media preview → fake verification page | `TAX-09-02` | **SRC-017 ✅✅** | **SUPPORTED** | YES |
| `TL-AUTH-003` | I4C-BOSS-016 | Executive impersonation + urgent payment order | `TAX-03-04` | SRC-022 ⛔ | **UNSUPPORTED** | YES |
| `TL-INV-001` | SEBI-RET-017 | Assured/guaranteed return + risk denial | `TAX-05-01` | **SRC-006 ✅ + SRC-020 ✅** | **SUPPORTED** | YES |
| `TL-INV-002` | SEBI-UNREG-018 | Unregistered adviser / handling client funds | `TAX-05-02` | **SRC-006 ✅** | **SUPPORTED** | YES |
| `TL-INV-003` | SEBI-DEEP-019 | Deepfake or social-media trading tip | `TAX-05-04` | SRC-023 🟡(D2) | **PARTIAL** | YES |
| `TL-JOB-001` | I4C-JOB-020 | Payment demanded as precondition of a job | `TAX-06-01` | **SRC-021 ✅** | **SUPPORTED** | YES |
| `TL-JOB-002` | I4C-CAPTCHA-021 | CAPTCHA-filling / easy-income task bait | `TAX-06-02` | SRC-002 ⛔ | **UNSUPPORTED** | YES |
| `TL-JOB-003` | I4C-TASK-022 | Task app: deposit → fake earnings → blocked withdrawal | `TAX-06-03` | SRC-015 ⛔ | **UNSUPPORTED** | 🟡 PARTIAL |
| `TL-CRYP-001` | I4C-CRYPTO-023 | "Connect wallet to verify assets" | `TAX-05-05` | SRC-024 ⛔ | **UNSUPPORTED** | YES |
| `TL-SOC-001` | I4C-MATRI-024 | Matrimonial/romance pivot to investment | `TAX-08-01` | SRC-002 ⛔ | **UNSUPPORTED** | YES |
| `TL-SOC-002` | I4C-SOCIAL-025 | Fake profile of a contact requesting money | `TAX-08-02` | **SRC-014 ✅** | **SUPPORTED** | YES |
| `TL-MAL-001` | I4C-APK-026 | APK / sideload / profile-install prompt | `TAX-10-01` | SRC-025 ⛔ · SRC-010 ✅(prevalence) | **PARTIAL** | YES |
| `TL-MAL-002` | I4C-ACCESS-027 | Accessibility permission requested out of context | `TAX-10-02` | SRC-019 ⛔ | **UNSUPPORTED** | 🟡 PARTIAL |
| `TL-MAL-003` | HDFC-SHARE-028 | Screen-sharing / remote-control app during banking | `TAX-10-03` | SRC-008 ⛔(D5) | **UNSUPPORTED** | YES |
| `TL-SOC-003` | CERT-JOB-029 | Urgent transfer request from a claimed relative | `TAX-08-04` | **SRC-021 ✅** | **SUPPORTED** | YES |
| `TL-CTX-001` | RBI-WIFI-030 | Financial activity over public Wi-Fi | — | SRC-004 ✅ | **SUPPORTED** | ⚠️ **DEFERRED** |

✅ verified · 🟡 cited but body unverified · ❌ verified *against* the claim · ⛔ retrieval failed

## 3. Result

| Verdict | Count | Share |
|---|---|---|
| `SUPPORTED` | **14** | 47% |
| `PARTIAL` | **6** | 20% |
| `UNSUPPORTED` | **10** | 33% |

Crossed with implementability:

| | Implementable | Deferred / partial | Total |
|---|---|---|---|
| SUPPORTED | **12** | 2 | 14 |
| PARTIAL | **6** | 0 | 6 |
| UNSUPPORTED | 7 | 3 | 10 |

**18 rules are both evidenced and implementable.** That is the honest MVP knowledge base — well
short of the 30 the research package presents, and considerably more trustworthy.

## 4. What drives the unsupported third

Every one of the 10 `UNSUPPORTED` rules fails for one of exactly two reasons:

| Cause | Rules | Note |
|---|---|---|
| **I4C unreachable** | `TL-TEL-001`, `TL-AUTH-003`, `TL-JOB-002`, `TL-JOB-003`, `TL-CRYP-001`, `TL-SOC-001`, `TL-MAL-002` (7) | The concepts are very likely sound — I4C is a genuine national authority and these are plausible, widely-reported scams. They are unsupported **as evidence**, not disproven. |
| **HDFC link rot / commercial source** | `TL-PAY-004`, `TL-IMP-001`, `TL-MAL-003` (3) | Cited domain migrated; content not located; and the source was never an authority ([CONF-005](../00-program/conflict-register.md)). |

**This is a retrieval problem, not a knowledge problem.** None of the 10 was contradicted by
evidence — they simply cannot yet be substantiated. They should be encoded as `DRAFT` /
`HEURISTIC` rules, kept out of the published rule set, and promoted the moment source access is
obtained. That preserves the work without overstating it.

## 5. Concepts *newly* supported by verification

The pass did not only subtract. Two concepts are now better-founded than the research package
had them:

1. **The receive-vs-pay boundary** (`TL-PAY-001`) was cited to NPCI, which is unreachable. It is
   now anchored to CERT-In SRC-021's exact wording — *"you don't need a UPI PIN or OTP to receive
   money"*. Arguably a **stronger** basis, since CERT-In is the national CERT and the wording is
   categorical.
2. **Device linking** (`TL-ATO-001`) now has **two independent verified sources** — CERT-In
   (official) and Meta (platform operator) — describing the same mechanism. Independent
   agreement raises confidence beyond what either alone supports.

## 6. Concepts requiring reclassification

| Concept | Action |
|---|---|
| "RBI says never share your UPI PIN" | **Drop.** Not in SRC-004 (D1). Replace with the receive-context form from SRC-021. |
| Smishing / vishing channel taxonomy | Reclassify `HEURISTIC` — not on the cited CISA page (D3). Channel taxonomy is an engineering construct here. |
| Deepfake investment tips | Hold at `PARTIAL` until SRC-023's body is retrieved. |
| Any HDFC-derived rule | Cap severity contribution; seek official corroboration; do not present as authoritative. |
| **Sextortion** | **New category, not in the research package** — appears in Chakshu's official list (ADV-008). Logged in [RESEARCH-005](RESEARCH-005-gap-register.md). |

## 7. Feeding DET-001

Each rule carries a `source_confidence` derived from RESEARCH-001 §7 weights and its verdict
here. Two constraints follow directly:

- A rule whose sources are all `UNSUPPORTED` **must not reach the published rule set**, regardless
  of how plausible it seems.
- `PARTIAL` rules may publish but with a **capped severity contribution**, and must require
  stronger indicator combinations to reach the same risk band as a `SUPPORTED` rule.

That is the mechanism by which evidence quality actually changes behaviour, rather than merely
being documented — which is the whole point of `MP §3`'s evidence-first principle.

## 8. Change history

| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-07-31 | Initial matrix. All 30 starter rules graded against verified sources; 14 supported, 6 partial, 10 unsupported; 18 both evidenced and implementable. | Threat Intelligence Lead |
| 1.1 | 2026-08-14 | Approved at the Phase 1 gate ([GATE-001](../00-program/GATE-001-phase-1-assessment.md)). Verdict tally and the 18-rule publishable set verified mechanically. §7's publication constraint is now reflected in charter metric SM-11. | Technical Program Director |
