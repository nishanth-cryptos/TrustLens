# RESEARCH-006 — Manual Retrieval and Evidence Reconciliation

**Status:** Proposed for repository review  
**Version:** 1.0  
**Review date:** 2026-08-28  
**Input manifest:** `knowledge/sources/verification-manifest.json` v1.1  
**Scope:** Phase-1 sources that were `RETRIEVAL_FAILED`, plus SRC-023 (`PRIMARY_CITED_UNVERIFIED`) because its body was manually captured.

## Executive result

The manual retrieval pass materially improves Phase-1 evidence coverage without rewriting history.

The original manifest reported 13 `RETRIEVAL_FAILED` sources. This package preserves those original statuses and records a separate manual outcome. Four of the failed sources were retrieved as the exact issuing-body source and their claims were located. Three blocked rule concepts now have strong official alternate/replacement evidence sufficient for source rebinding. Three failed sources remain only partially supported, one current canonical HDFC page was captured but has no `claim_under_test`/`blocks_rules` in the manifest, and two source-level gaps remain unavailable.

The most important rule-level result is:

- `TL-PAY-002` — exact NPCI primary evidence is now available.
- `TL-AUTH-003` — exact PIB/MHA primary evidence is now available.
- `TL-JOB-003` — can be rebound to a two-source official evidence pair (PIB/MHA 2023 + I4C/NCTAU 2025).
- `TL-MAL-002` — the exact concept is supported by the official CyberDost/I4C channel, but governance must explicitly permit official-channel evidence.
- `TL-CRYP-001` — the exact concept is supported by the official CyberDost/I4C channel, subject to the same governance decision.
- `TL-TEL-001` — remains partial because the captured official CyberDost post supports call-forwarding/code abuse but not the courier/delivery pretext.
- `TL-MAL-001` — remains partial because CERT-In supports untrusted/non-store app installation, but not the iOS configuration-profile mechanism.

This package does **not** authorize automatic rule publication. Existing rule-schema, negative-indicator, seed-case and validator gates must still pass.

## Source reconciliation

| Source | Manual outcome | Key result |
|---|---|---|
| SRC-001 | EXACT_PRIMARY_VERIFIED | CFCFRMS statistic and 1930 are directly verified in PIB PRID 2287674, p.1. |
| SRC-002 | STILL_UNAVAILABLE | I4C advisory index remains unavailable; index pages must not be used as claim evidence. |
| SRC-005 | EXACT_PRIMARY_VERIFIED | NPCI BHIM safety checkpoints on p.77 directly verify the UPI-PIN claim. |
| SRC-008 | OFFICIAL_REPLACEMENT_PARTIAL | Current HDFC fraud snapshot covers several fraud families, but cannot automatically replace the old SIM-swap citation for all five dependent rules. |
| SRC-011 | STILL_UNAVAILABLE_LOW_IMPACT | Europol background report remains unavailable; do not block Phase 2 on it. |
| SRC-013 | OFFICIAL_ALTERNATE_PARTIAL | CyberDost supports call-forwarding/code abuse, but not the delivery/courier pretext. |
| SRC-015 | OFFICIAL_REPLACEMENT_COMPOSITE_VERIFIED | PIB 2023 + I4C 2025 together support the task-job deposit/frozen-or-denied-withdrawal/additional-payment chain. |
| SRC-018 | EXACT_PRIMARY_VERIFIED | NPCI Fraud Awareness p.2 directly supports the QR+UPI-PIN receive-vs-pay rule. |
| SRC-019 | OFFICIAL_ALTERNATE_VERIFIED | Official CyberDost/I4C post supports Android Accessibility-permission abuse and APK/link/fake-app delivery. |
| SRC-022 | EXACT_PRIMARY_VERIFIED | PIB/MHA boss-scam release directly supports urgent executive-payment instructions. |
| SRC-024 | OFFICIAL_ALTERNATE_VERIFIED | Official CyberDost/I4C post closely matches the Trust Wallet fake-verification/wallet-connect chain. |
| SRC-025 | OFFICIAL_REPLACEMENT_PARTIAL | CERT-In supports trusted-store/untrusted-link app-install logic, but not the iOS configuration-profile branch. |
| SRC-026 | CURRENT_CANONICAL_RETRIEVED | Current HDFC page supports the screen-sharing/remote-app concept; the manifest has no rule mapping for this source. |
| SRC-023 | PRIMARY_BODY_RETRIEVED_PARTIAL_CLAIM | SEBI verifies celebrity/public-figure impersonation and fake returns; no deepfake-specific statement is present in the captured release. |

## Important evidence locators

- `PIB_PRID-2287674_National_Cybercrime_Response.pdf`, p.1 — CFCFRMS saved amount, complaint count and 1930.
- `BHIM_UPI_Guidelines_2026_012a0b1bce.pdf`, p.77 — UPI PIN safety checkpoints.
- `NPCI_Fraud_Awareness.pdf`, pp.2–3 — QR/UPI-PIN receive-vs-pay guidance and remote-access warning.
- `PIB_PRID-2276809_Boss_Scam.pdf`, p.1 — regulator/executive impersonation and payment-transfer instruction.
- `SEBI_PR-27-2025_Social_Media_Stock_Market_Scams.pdf`, p.1 — WhatsApp groups, fake experts, celebrities/public figures, fake testimonials and unreasonable returns.
- `HDFC_Security_Threat_Detected.pdf`, p.1 — AnyDesk/TeamViewer/AirDroid screen-sharing warning.
- `I4C_USSD_Call_Forwarding_CyberDost.pdf`, p.3 — call-forwarding code warning; original TAU_ADV_007 link is referenced.
- `I4C_Android_GOD_Mode_CyberDost.pdf`, p.11 — Accessibility-permission abuse, links/APKs/fake applications.
- `I4C_Trust_Wallet_CyberDost.pdf`, pp.49–50 — P2P contact, WhatsApp/Telegram handoff, fake verification site, wallet connection, permissions and fund transfer.
- `CERTIn_Cyber_Security_Awareness_Booklet.pdf`, pp.6–7 — use trusted/authorized app sources and avoid app installation from messages/social links.
- `PIB_MHA_Task_Based_Part_Time_Job_Fraud_2023.pdf`, p.1 — initial commission, more investment, frozen larger deposit.
- `I4C_Fake_CAPTCHA_Filling_Jobs_2025.pdf`, p.1 — denied withdrawals followed by additional-payment demands.

## Do not silently close these gaps

1. **SRC-002 / I4C index** remains unavailable.
2. **SRC-011 / Europol background report** remains unavailable.
3. **SRC-008 / old HDFC SIM-swap citation** is not fully replaced by the captured HDFC page. Reconcile each dependent rule separately.
4. **TL-TEL-001 courier/delivery pretext** is not verified by the captured CyberDost call-forwarding post.
5. **TL-MAL-001 iOS configuration-profile clause** is not verified by the CERT-In booklet.
6. **SEBI deepfake-specific wording** is not present in PR No. 27/2025; celebrity/public-figure impersonation is present.

## Recommended Phase-2 continuation

1. Merge this package as evidence metadata, not as an overwrite of the original verification manifest.
2. Add a governance decision for whether archived official social-media/CyberDost posts qualify as publishable primary evidence.
3. Rebind `TL-JOB-003`, `TL-MAL-002` and `TL-CRYP-001` only after that source policy is explicit.
4. Keep or narrow `TL-TEL-001` and `TL-MAL-001`.
5. Re-run the Phase-1 consistency validator.
6. Start Phase 2 with the canonical rule JSON Schema, reserving language/script fields.
7. Build the negative-indicator library before broadening rule publication.
8. Run the seed corpus and add benign near-miss tests before changing a rule from draft to published.
