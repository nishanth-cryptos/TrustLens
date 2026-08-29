# RESEARCH-004 — Evidence Matrix

| Field | Value |
|---|---|
| Document ID | RESEARCH-004 |
| Version | 1.2 |
| Status | **Approved** (v1.1) · **Reconciled** at v1.2 after the RESEARCH-006 manual retrieval pass |
| Owner role | Threat Intelligence Lead |
| Dependencies | RESEARCH-001, RESEARCH-002, RESEARCH-003, [RESEARCH-006](RESEARCH-006-manual-retrieval-reconciliation.md), [DEC-006](../00-program/decision-log.md), [ADR-0015](../../adr/ADR-0015-evidence-hierarchy-and-official-alternate-provenance.md) |
| Feeds | KB-001 (rule encoding), DET-001 |
| Last updated | 2026-08-28 |

> **v1.2 reconciliation notice.** The matrix below now shows **post-manual-retrieval** verdicts.
> The original **automated** (v1.1) verdicts — the honest record of what the automated pass alone
> could support — are preserved verbatim in [§9](#9-manual-retrieval-reconciliation-2026-08-28),
> with the old→new transition and the evidence ID behind each change. No verdict was raised except
> where a retained, hashed, human-reviewed piece of official evidence justifies it under
> [ADR-0015](../../adr/ADR-0015-evidence-hierarchy-and-official-alternate-provenance.md).

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
| `TL-PAY-002` | NPCI-QR-004 | "Scan QR to receive money" | `TAX-01-03` | SRC-018 ✅ᴹ · SRC-021 ✅(partial) | **SUPPORTED** | YES |
| `TL-PAY-003` | CERT-QR-005 | Payee identity unverified before QR payment | `TAX-01-03` | **SRC-021 ✅** | **SUPPORTED** | ⚠️ **DEFERRED** |
| `TL-KYC-001` | HDFC-KYC-006 | KYC update demanded via link or call | `TAX-02-01` | SRC-008 ⛔(D5) · SRC-007 ✅(partial) | **PARTIAL** | YES |
| `TL-PAY-004` | HDFC-FALSECR-007 | False credit claim, refund demanded | `TAX-01-04` | SRC-008 ⛔(D5) | **UNSUPPORTED** | YES |
| `TL-CRED-003` | RBI-CARD-008 | Card number / CVV capture | `TAX-01-07` | SRC-004 ✅ | **SUPPORTED** | YES |
| `TL-IMP-001` | HDFC-CARE-009 | Customer-care number sourced from search/ads | `TAX-02-04` | SRC-008 ⛔(D5) | **UNSUPPORTED** | ⚠️ **DEFERRED** |
| `TL-AUTH-001` | I4C-DARREST-010 | Authority impersonation + legal threat + payment demand | `TAX-03-01` | **SRC-012 ✅✅** | **SUPPORTED** | YES |
| `TL-AUTH-002` | I4C-DARREST-011 | Isolation from family or lawyers | `TAX-03-01` | **SRC-012 ✅✅** | **SUPPORTED** | YES |
| `TL-UTIL-001` | HDFC-UTILITY-012 | Utility disconnection threat + urgent payment | `TAX-07-02` | SRC-008 ⛔(D5) · SRC-007 ✅(partial) | **PARTIAL** | YES |
| `TL-TEL-001` | I4C-USSD-013 | Unverified call-forwarding-code request (courier pretext narrowed out) | `TAX-04-01` | SRC-013 🅐(partial) | **PARTIAL** | YES |
| `TL-ATO-001` | I4C-WA-014 | Device-linking request (QR or linking code) | `TAX-09-01` | **SRC-017 ✅ + SRC-016 ✅** | **SUPPORTED** | YES |
| `TL-ATO-002` | CERT-WA-015 | Fake media preview → fake verification page | `TAX-09-02` | **SRC-017 ✅✅** | **SUPPORTED** | YES |
| `TL-AUTH-003` | I4C-BOSS-016 | Executive impersonation + urgent payment order | `TAX-03-04` | SRC-022 ✅ᴹ | **SUPPORTED** | YES |
| `TL-INV-001` | SEBI-RET-017 | Assured/guaranteed return + risk denial | `TAX-05-01` | **SRC-006 ✅ + SRC-020 ✅** | **SUPPORTED** | YES |
| `TL-INV-002` | SEBI-UNREG-018 | Unregistered adviser / handling client funds | `TAX-05-02` | **SRC-006 ✅** | **SUPPORTED** | YES |
| `TL-INV-003` | SEBI-DEEP-019 | Celebrity/public-figure impersonation in social-media investment funnel (deepfake excluded) | `TAX-05-04` | SRC-023 ✅ᴹ(celebrity; deepfake ⛔) | **PARTIAL** | YES |
| `TL-JOB-001` | I4C-JOB-020 | Payment demanded as precondition of a job | `TAX-06-01` | **SRC-021 ✅** | **SUPPORTED** | YES |
| `TL-JOB-002` | I4C-CAPTCHA-021 | CAPTCHA-filling / easy-income task bait | `TAX-06-02` | SRC-002 ⛔ | **UNSUPPORTED** | YES |
| `TL-JOB-003` | I4C-TASK-022 | Task app: deposit → fake earnings → blocked withdrawal → more payment | `TAX-06-03` | SRC-015 🅡 (PIB-2023 + I4C-2025) | **SUPPORTED** | 🟡 PARTIAL |
| `TL-CRYP-001` | I4C-CRYPTO-023 | "Connect wallet to verify assets" | `TAX-05-05` | SRC-024 🅐 | **PARTIAL** | YES |
| `TL-SOC-001` | I4C-MATRI-024 | Matrimonial/romance pivot to investment | `TAX-08-01` | SRC-002 ⛔ | **UNSUPPORTED** | YES |
| `TL-SOC-002` | I4C-SOCIAL-025 | Fake profile of a contact requesting money | `TAX-08-02` | **SRC-014 ✅** | **SUPPORTED** | YES |
| `TL-MAL-001` | I4C-APK-026 | Untrusted/non-store app-install prompt (iOS config-profile excluded) | `TAX-10-01` | SRC-025 🅡 (CERT-In) · SRC-010 ✅(prevalence) | **PARTIAL** | YES |
| `TL-MAL-002` | I4C-ACCESS-027 | Accessibility permission requested out of context | `TAX-10-02` | SRC-019 🅐 | **PARTIAL** | 🟡 PARTIAL |
| `TL-MAL-003` | HDFC-SHARE-028 | Screen-sharing / remote-control app during banking | `TAX-10-03` | SRC-026 🅘 · SRC-018 ✅ᴹ(corrob.) | **PARTIAL** | YES |
| `TL-SOC-003` | CERT-JOB-029 | Urgent transfer request from a claimed relative | `TAX-08-04` | **SRC-021 ✅** | **SUPPORTED** | YES |
| `TL-CTX-001` | RBI-WIFI-030 | Financial activity over public Wi-Fi | — | SRC-004 ✅ | **SUPPORTED** | ⚠️ **DEFERRED** |

✅ verified · 🟡 cited but body unverified · ❌ verified *against* the claim · ⛔ retrieval failed ·
✅ᴹ manually retrieved & verified (PRIMARY, DEC-006) · 🅐 official-alternate channel (caps PARTIAL) ·
🅡 official replacement document · 🅘 industry (caps PARTIAL)

## 3. Result

Counts are **post-reconciliation (v1.2)**. The v1.1 automated counts (14 / 6 / 10) are preserved in
[§9](#9-manual-retrieval-reconciliation-2026-08-28).

| Verdict | Count | Share |
|---|---|---|
| `SUPPORTED` | **17** | 57% |
| `PARTIAL` | **9** | 30% |
| `UNSUPPORTED` | **4** | 13% |

Crossed with implementability:

| | Implementable | Deferred / partial | Total |
|---|---|---|---|
| SUPPORTED | **14** | 3 | 17 |
| PARTIAL | **8** | 1 | 9 |
| UNSUPPORTED | 3 | 1 | 4 |

**22 rules are both evidenced and implementable** (was 18 before the manual retrieval pass). That is
the honest MVP knowledge base — the four rules the manual pass added to the eligible set
(TL-PAY-002, TL-AUTH-003, TL-CRYP-001, TL-MAL-003 by evidence; TL-JOB-003 is evidenced but only
partially implementable) all carry retained, hashed, human-reviewed official evidence.

## 4. What remains unsupported after the manual retrieval pass

The manual pass ([RESEARCH-006](RESEARCH-006-manual-retrieval-reconciliation.md)) closed **6 of the
original 10** `UNSUPPORTED` rules (TL-AUTH-003, TL-JOB-003 → SUPPORTED; TL-TEL-001, TL-CRYP-001,
TL-MAL-002, TL-MAL-003 → PARTIAL). **Four remain unsupported**, for two reasons:

| Cause | Rules | Note |
|---|---|---|
| **I4C index (SRC-002) still unreachable** | `TL-JOB-002`, `TL-SOC-001` (2) | Both were cited only to the I4C advisories *index* (SRC-002), which the manual pass could not retrieve — an index is not claim evidence. The I4C CAPTCHA advisory (MR-EVID-013) is thematically adjacent to `TL-JOB-002` and is a candidate for a future dedicated re-evaluation, but it was retrieved as part of the `TL-JOB-003` composite and is not re-bound here without an explicit review. |
| **HDFC link rot, claim not in the replacement** | `TL-PAY-004`, `TL-IMP-001` (2) | The current HDFC page (SRC-008 replacement) covers identity theft, vishing, smishing, money-mule, phishing and trojans — but **not** false-credit/refund (`TL-PAY-004`) or customer-care-number sourcing (`TL-IMP-001`). No official corroboration located either. |

**Still a retrieval problem, not a knowledge problem.** None of the four was contradicted by evidence.
They stay `DRAFT`/`HEURISTIC`, out of the published set, and promote the moment source access is
obtained.

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
| Deepfake investment tips | **Split (2026-08-28).** SRC-023's body is now retrieved and verifies *celebrity/public-figure impersonation*, fake testimonials and unreasonable-return promises — but **no deepfake-specific statement is present**. `TL-INV-003` is narrowed to the celebrity/social-media-impersonation concept at `PARTIAL`; the deepfake mechanism is **not** verified and stays an open gap ([G-16](RESEARCH-005-gap-register.md)). |
| Any HDFC-derived rule | Cap severity contribution; seek official corroboration; do not present as authoritative. `TL-MAL-003` now carries `PARTIAL` on the current HDFC page (SRC-026, `INDUSTRY`) corroborated by NPCI's remote-access warning — capped, not authoritative. |
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

## 9. Manual retrieval reconciliation (2026-08-28)

The RESEARCH-006 manual retrieval pass changed nine verdicts. The **automated v1.1 verdict** is the
honest record of what the *automated* pass alone could support and is preserved here; the **v1.2
verdict** in the table above is what the retained, hashed, human-reviewed official evidence now
supports under [ADR-0015](../../adr/ADR-0015-evidence-hierarchy-and-official-alternate-provenance.md).

| Rule | v1.1 (automated) | v1.2 (reconciled) | Evidence class | Evidence IDs | Basis |
|---|---|---|---|---|---|
| `TL-PAY-002` | PARTIAL | **SUPPORTED** | PRIMARY | MR-EVID-003 | NPCI Fraud Awareness p.2 — QR+PIN is a payment, not a receipt |
| `TL-AUTH-003` | UNSUPPORTED | **SUPPORTED** | PRIMARY | MR-EVID-004 | PIB/MHA Boss-Scam release p.1 — executive impersonation + urgent transfer |
| `TL-JOB-003` | UNSUPPORTED | **SUPPORTED** | OFFICIAL_REPLACEMENT | MR-EVID-012, MR-EVID-013 | PIB-2023 (commission→more investment→frozen deposit) + I4C-2025 (denied withdrawal→more payment). Original SRC-015 PDF **still unavailable** — rebound, not resurrected |
| `TL-MAL-002` | UNSUPPORTED | **PARTIAL** | OFFICIAL_ALTERNATE | MR-EVID-009 | CyberDost/I4C post — Accessibility-permission abuse, APK/link delivery. Capped |
| `TL-CRYP-001` | UNSUPPORTED | **PARTIAL** | OFFICIAL_ALTERNATE | MR-EVID-010 | CyberDost/I4C post — P2P→off-platform→fake verify→wallet connect→drain. Capped |
| `TL-TEL-001` | UNSUPPORTED | **PARTIAL** | OFFICIAL_ALTERNATE | MR-EVID-008 | CyberDost supports call-forwarding/code abuse **only**; courier/delivery pretext narrowed out (still unsupported) |
| `TL-MAL-001` | PARTIAL | **PARTIAL** | OFFICIAL_REPLACEMENT | MR-EVID-011 | CERT-In booklet supports untrusted/non-store install; iOS configuration-profile clause narrowed out (still unsupported) |
| `TL-MAL-003` | UNSUPPORTED | **PARTIAL** | INDUSTRY | MR-EVID-006 | Current HDFC page names AnyDesk/TeamViewer/AirDroid; NPCI remote-access warning corroborates. Capped |
| `TL-INV-003` | PARTIAL | **PARTIAL** | PRIMARY | MR-EVID-005 | SEBI PR 27/2025 body verifies celebrity/public-figure impersonation; **deepfake mechanism not present** — narrowed |

**Deliberately unchanged.** `TL-JOB-002` and `TL-SOC-001` stay UNSUPPORTED (SRC-002 index still
unavailable); `TL-PAY-004` and `TL-IMP-001` stay UNSUPPORTED (claim absent from the HDFC
replacement). Automated counts (14/6/10) → reconciled counts (17/9/4). The verification manifest's
per-source `manual_retrieval` overlay is the machine-readable companion to this table.

## 8. Change history

| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-07-31 | Initial matrix. All 30 starter rules graded against verified sources; 14 supported, 6 partial, 10 unsupported; 18 both evidenced and implementable. | Threat Intelligence Lead |
| 1.1 | 2026-08-14 | Approved at the Phase 1 gate ([GATE-001](../00-program/GATE-001-phase-1-assessment.md)). Verdict tally and the 18-rule publishable set verified mechanically. §7's publication constraint is now reflected in charter metric SM-11. | Technical Program Director |
| 1.2 | 2026-08-28 | Reconciled with the RESEARCH-006 manual retrieval pass under DEC-006 / ADR-0015. Nine verdicts changed (see §9); counts 14/6/10 → 17/9/4; evidenced-and-implementable 18 → 22. Automated v1.1 verdicts preserved in §9. | Threat Intelligence Lead |
