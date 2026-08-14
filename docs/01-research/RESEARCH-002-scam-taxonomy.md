# RESEARCH-002 — Indian Scam Domain Taxonomy

| Field | Value |
|---|---|
| Document ID | RESEARCH-002 |
| Version | 1.1 |
| Status | **Approved** — closed at the Phase 1 gate, [GATE-001](../00-program/GATE-001-phase-1-assessment.md) |
| Owner role | Threat Intelligence Lead |
| Dependencies | RESEARCH-001 |
| Feeds | RESEARCH-003, RESEARCH-004, KB-001 |
| Machine-readable companion | [`knowledge/taxonomies/scam-taxonomy.json`](../../knowledge/taxonomies/scam-taxonomy.json) |
| Last updated | 2026-08-14 |

---

## 1. Purpose and design principles

A versioned, machine-consumable classification of Indian digital scam types. It is **data, not
code** — `MP §9`'s gate requires a new scam type to be addable without touching the engine.

Four principles:

1. **Canonical IDs, not names.** `TAX-03-01` is stable; "digital arrest" is a label that may be
   translated, renamed or superseded.
2. **Evidence grade travels with the term.** Each entry records whether its existence as a
   recognised category is `PRIMARY_VERIFIED`, or rests on an unverifiable citation.
3. **Categories are not mutually exclusive.** A digital-arrest case that ends in a UPI transfer
   is `TAX-03-01` *and* `TAX-01-02`. Detection assigns multiple categories; the taxonomy does not
   force a single bucket.
4. **Extensible beyond India.** Structure carries no India-specific assumption; the *instances*
   are Indian.

## 2. Top-level categories

Ten top-level categories, as supported by `RP p.2`.

| ID | Category | Evidence | Primary support |
|---|---|---|---|
| `TAX-01` | Financial fraud | 🟢 `PRIMARY_VERIFIED` | SRC-021, SRC-004 |
| `TAX-02` | Identity and KYC fraud | 🟢 `PRIMARY_VERIFIED` | SRC-007 (Chakshu categories) |
| `TAX-03` | Government and authority impersonation | 🟢 `PRIMARY_VERIFIED` | SRC-012, SRC-007 |
| `TAX-04` | Telecom and device hijack fraud | 🟡 Partial | SRC-007; I4C USSD advisory unretrievable |
| `TAX-05` | Investment and wealth-building fraud | 🟢 `PRIMARY_VERIFIED` | SRC-006, SRC-020 |
| `TAX-06` | Employment and income scams | 🟢 `PRIMARY_VERIFIED` | SRC-021 ("Never pay for job offers") |
| `TAX-07` | Courier, delivery and utility scams | 🟡 Partial | SRC-007 (gas/electricity); SRC-012 (parcel pretext) |
| `TAX-08` | Social and relationship-enabled scams | 🟢 `PRIMARY_VERIFIED` | SRC-014 (fake profiles, bots) |
| `TAX-09` | Account-takeover scams | 🟢 `PRIMARY_VERIFIED` | SRC-017, SRC-016 |
| `TAX-10` | Malware-enabled scams | 🟡 Partial | SRC-010 (Play Protect); I4C advisories unretrievable |

**Seven of ten categories are verified at top level.** The three partials (`TAX-04`, `TAX-07`,
`TAX-10`) are all cases where the category is *corroborated* by a verified source but its most
specific evidence sits in unretrievable I4C advisories.

## 3. Subcategories

### TAX-01 · Financial fraud
| ID | Subcategory | Evidence | Note |
|---|---|---|---|
| `TAX-01-01` | Banking credential theft | 🟢 | SRC-004: never asked for password/PIN/OTP/CVV |
| `TAX-01-02` | UPI PIN fraud | 🟢 | SRC-021: no UPI PIN needed to *receive* |
| `TAX-01-03` | QR-code payment misuse | 🟢 | SRC-021: verify sender's banking name before QR payment |
| `TAX-01-04` | Fake refund / false-credit | 🔴 | HDFC only (D5) — **needs official corroboration** |
| `TAX-01-05` | Loan-app abuse | 🔴 | No verified source retrieved |
| `TAX-01-06` | Mule account / illegal payment gateway | 🔴 | No verified source retrieved |
| `TAX-01-07` | Card / CVV / OTP fraud | 🟢 | SRC-004 |

### TAX-02 · Identity and KYC fraud
| ID | Subcategory | Evidence | Note |
|---|---|---|---|
| `TAX-02-01` | Fake KYC-update link | 🟡 | SRC-007 lists KYC as a Chakshu reporting category; the "banks never ask via link/call" phrasing is HDFC-only (D5) |
| `TAX-02-02` | KYC verification call | 🟡 | As above; SRC-012 notes KYC as a digital-arrest opening pretext |
| `TAX-02-03` | SIM binding / SIM swap | 🟡 | SRC-007 lists SIM |
| `TAX-02-04` | Customer-care impersonation | 🔴 | HDFC only (D5) |

### TAX-03 · Government and authority impersonation
| ID | Subcategory | Evidence | Note |
|---|---|---|---|
| `TAX-03-01` | **Digital arrest** | 🟢 **Fully verified** | SRC-012 — complete modus operandi quoted |
| `TAX-03-02` | Law-enforcement impersonation | 🟢 | SRC-012: "Fraudsters impersonate law enforcement officials" |
| `TAX-03-03` | Regulator / government-official impersonation | 🟢 | SRC-007: "impersonation as Government official" |
| `TAX-03-04` | Executive impersonation (boss scam) | 🔴 | SRC-022 unretrievable (403) |

### TAX-04 · Telecom and device hijack fraud
| ID | Subcategory | Evidence | Note |
|---|---|---|---|
| `TAX-04-01` | USSD call forwarding | 🔴 | SRC-013 unretrievable |
| `TAX-04-02` | Caller-ID spoofing | 🟡 | SRC-012: "spoofed phone numbers" |
| `TAX-04-03` | SIM misuse | 🟡 | SRC-007 |

### TAX-05 · Investment and wealth-building fraud
| ID | Subcategory | Evidence | Note |
|---|---|---|---|
| `TAX-05-01` | Assured / guaranteed returns | 🟢 **Fully verified** | SRC-006 + SRC-020 ("120% returns assured! Zero risk!") |
| `TAX-05-02` | Unregistered investment adviser | 🟢 | SRC-006: "illegal to act as Investment Adviser without SEBI registration" |
| `TAX-05-03` | Fake trading platform / app | 🟡 | Implied by SRC-006's registered-entities guidance |
| `TAX-05-04` | Deepfake / social-media trading tips | 🟡 | SRC-023 exists but body unverified (D2) |
| `TAX-05-05` | Crypto wallet-verification drain | 🔴 | SRC-024 unretrievable |

### TAX-06 · Employment and income scams
| ID | Subcategory | Evidence | Note |
|---|---|---|---|
| `TAX-06-01` | Fake job / placement fee | 🟢 | SRC-021: "Never pay for job offers" |
| `TAX-06-02` | CAPTCHA-filling work scam | 🔴 | SRC-002 index-only, unretrievable |
| `TAX-06-03` | Part-time task app / Ponzi | 🔴 | SRC-015 unretrievable |
| `TAX-06-04` | Overseas job racket | 🟡 | Covered generically by SRC-021 |

### TAX-07 · Courier, delivery and utility scams
| ID | Subcategory | Evidence | Note |
|---|---|---|---|
| `TAX-07-01` | Fake parcel / customs payment | 🟡 | SRC-012: "harmless parcel delivery claim" as an opening pretext |
| `TAX-07-02` | Utility disconnection threat | 🟡 | SRC-007 lists Gas / Electricity as reporting categories |
| `TAX-07-03` | Delivery-agent impersonation | 🔴 | SRC-013 unretrievable |

### TAX-08 · Social and relationship-enabled scams
| ID | Subcategory | Evidence | Note |
|---|---|---|---|
| `TAX-08-01` | Romance / matrimonial pivot to investment | 🔴 | SRC-002 index-only |
| `TAX-08-02` | Fake profile / trusted-contact abuse | 🟢 | SRC-014: "Fraudsters use Fake Profile of the victim" |
| `TAX-08-03` | Account renting | 🔴 | SRC-002 index-only |
| `TAX-08-04` | Urgent-transfer request from "relative" | 🟢 | SRC-021: verify by calling directly |

### TAX-09 · Account-takeover scams
| ID | Subcategory | Evidence | Note |
|---|---|---|---|
| `TAX-09-01` | **WhatsApp device linking** | 🟢 **Fully verified** | SRC-017 (GhostPairing) + SRC-016 (Meta) |
| `TAX-09-02` | Fake media preview → verification page | 🟢 **Fully verified** | SRC-017 exact wording |
| `TAX-09-03` | Phishing page impersonating a platform | 🟢 | SRC-017: "fake Facebook viewer" |

### TAX-10 · Malware-enabled scams
| ID | Subcategory | Evidence | Note |
|---|---|---|---|
| `TAX-10-01` | APK / sideload distribution | 🟡 | SRC-010 (Play Protect blocks); I4C iOS advisory unretrievable |
| `TAX-10-02` | Accessibility permission abuse | 🔴 | SRC-019 unretrievable |
| `TAX-10-03` | Screen sharing / remote control | 🔴 | HDFC only (D5) |
| `TAX-10-04` | Browser extension abuse | 🔴 | SRC-002 index-only |

## 4. Coverage summary

| Evidence grade | Subcategories | Share |
|---|---|---|
| 🟢 Verified | 15 | 37% |
| 🟡 Partial / corroborated | 11 | 27% |
| 🔴 Unverified | 15 | 37% |
| **Total** | **41** | |

**Structural finding:** verified coverage clusters in **payments, authority impersonation,
investment and account takeover** — which happen to be the highest-severity families. The
unverified tail is concentrated in **malware, telecom and employment**, almost entirely because
I4C is unreachable.

This is a workable position. The MVP can be built on strongly-evidenced categories, with the
unverified tail carried as `DEFERRED` knowledge pending source access.

## 5. Rules for using this taxonomy

1. A rule may only claim a category at 🟢 or 🟡. A 🔴 category may carry rules **explicitly graded
   `HEURISTIC`**, never rules presented as officially supported.
2. Multiple category assignment is expected; scoring must not double-count severity when a case
   maps to several categories ([CONF-001](../00-program/conflict-register.md)).
3. Adding a category requires a source reference and an evidence grade. No ungraded terms.
4. Category IDs are permanent. Deprecation sets a flag; it never reuses an ID.

## 6. Change history

| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-07-31 | Initial taxonomy: 10 categories, 41 subcategories, each evidence-graded against the RESEARCH-001 verification pass. | Threat Intelligence Lead |
| 1.1 | 2026-08-14 | Approved at the Phase 1 gate ([GATE-001](../00-program/GATE-001-phase-1-assessment.md)). Counts and nesting verified mechanically by [`phase1_consistency_check.py`](../../knowledge/validation/phase1_consistency_check.py). Sextortion (`TAX-11`, G-10) remains an open Phase 2 decision. | Technical Program Director |
