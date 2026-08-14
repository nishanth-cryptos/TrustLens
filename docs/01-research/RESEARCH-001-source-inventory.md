# RESEARCH-001 — Official Source Inventory

| Field | Value |
|---|---|
| Document ID | RESEARCH-001 |
| Version | 1.1 |
| Status | **Approved** — closed at the Phase 1 gate, [GATE-001](../00-program/GATE-001-phase-1-assessment.md) |
| Owner role | Threat Intelligence Lead |
| Dependencies | PROGRAM-001, BASELINE-001, [DEC-003](../00-program/decision-log.md) |
| Feeds | RESEARCH-002…005, KB-001 |
| Machine-readable companion | [`knowledge/sources/verification-manifest.json`](../../knowledge/sources/verification-manifest.json) |
| Assumptions | [ASM-016](../00-program/assumption-register.md) (source reachability) |
| Last updated | 2026-08-14 |

---

## 1. Method

Per [DEC-003](../00-program/decision-log.md), every source cited by the Phase One Research
Foundation was subjected to a retrieval attempt before any of its claims were encoded. A source
reaches `PRIMARY_VERIFIED` **only** when the issuing body's own document was retrieved *and* the
specific claim was located within it. Titles and dates alone are not sufficient.

Tracking parameters (`utm_source=chatgpt.com`) were stripped from all URLs. Retrieved documents
were hashed (SHA-256) and the hash recorded, so future link rot can be distinguished from
content change.

**Retrieval was attempted twice** where the first method failed — once via the standard fetch
path and once via direct HTTPS request with a browser user-agent. Several government sources
that blocked the first method succeeded on the second, which is why NITI Aayog and the RBI FAME
booklet appear as verified.

## 2. Headline result

| Grade | Count | Share |
|---|---|---|
| `PRIMARY_VERIFIED` | 11 | 42% |
| `PRIMARY_CITED_UNVERIFIED` | 1 | 4% |
| `INDEX_ONLY` | 1 | 4% |
| `RETRIEVAL_FAILED` | 13 | 50% |
| **Total** | **26** | |

**Slightly under half the cited source base could be verified.** This is a materially better
outcome than the research package's own warning implied, and it is concentrated in the right
places — the highest-severity rules (digital arrest) and the core payment boundary are both now
backed by located, quoted primary text.

## 3. Verified sources

Full quotations are recorded in the [verification manifest](../../knowledge/sources/verification-manifest.json).

| ID | Issuing body | Authority | Document | Published | Supports |
|---|---|---|---|---|---|
| **SRC-021** | CERT-In | Government | *Preventing Online scams* (CIAD-2024-0050) | 2024-10-24 | QR sender verification · **receive-vs-pay boundary** · urgent-transfer verification · never pay for job offers |
| **SRC-012** | NITI Aayog | Government | *Digital Arrest: The Modern-Day Cyber Scam* | 2025-04 | Digital arrest modus operandi · coercion · isolation from family/lawyers |
| **SRC-017** | CERT-In | Government | *WhatsApp Account takeover campaign (GhostPairing)* (CIAD-2025-0055) | 2025-12-19 | Fake preview bait · deceptive verification · device linking |
| **SRC-014** | CERT-In | Government | *Cyber Security Awareness Booklet* (NCSAM 2023) | 2023-10 | Social-media fraud · bots · fake profiles |
| **SRC-004** | RBI | Regulator | *Reserve Bank sensitises members of public on safe use of digital transactions* | 2020-06-22 | Institutions never ask password/PIN/OTP/CVV · public Wi-Fi caution |
| **SRC-020** | RBI | Regulator | *FAME* financial awareness booklet | 2024 | "120% returns assured! Zero risk!" as a fraud cue · regulated entities only |
| **SRC-006** | SEBI | Regulator | *Caution to Investor* | — | Guaranteed returns · unregistered advisers illegal · advisers must not handle client funds |
| **SRC-007** | DoT / Sanchar Saathi | Government | *Chakshu* fraud reporting | — | Reporting categories: bank/wallet/SIM/gas/electricity/KYC, government impersonation |
| **SRC-017** ↑ | | | | | |
| **SRC-009** | CISA (US) | Foreign official | *Malware, Phishing, and Ransomware* | — | Phishing definition |
| **SRC-010** | Google | Industry | *Safety Charter for India's AI-led Transformation* | 2025-06-18 | Play Protect blocked ~6 crore high-risk install attempts (pilot from Oct 2024) |
| **SRC-016** | Meta | Industry | *Meta Launches New Anti-Scam Tools* | 2026-03-11 | WhatsApp device-linking via QR or linking code |

**SRC-023** (SEBI, *Caution to Investors on Stock Market Scams through Social Media Platforms*,
PR 27/2025, 2025-05-21) is graded `PRIMARY_CITED_UNVERIFIED` — the document demonstrably exists
with the cited title and date, but its body was not retrievable, so the deepfake claim it is
cited for remains unconfirmed.

## 4. Discrepancies found

The verification pass exists to catch exactly these. **Six** were found.

| ID | Discrepancy | Impact |
|---|---|---|
| **D1** | The research package states RBI says institutions never ask for *"password, PIN, OTP, CVV, **or UPI-PIN**"*. The source's actual list (SRC-004) is **"password, PIN, OTP, CVV number"** — **UPI-PIN is not in it.** | The RBI half of the UPI-PIN rule basis is unsupported. NPCI, the other cited half, could not be retrieved. **Mitigated:** CERT-In SRC-021 independently states *"you don't need a UPI PIN or OTP to receive money"*, which supports the receive-context rule but not a general "RBI says never share UPI PIN" claim. |
| **D2** | Deepfake and social-media investment warnings are attributed to the SEBI investor page (SRC-006). They are **not on that page**; they belong to SRC-023. | Misattribution. Re-point the citation. |
| **D3** | Smishing and vishing definitions are attributed to the CISA page (SRC-009). **Not present** on that page. | Misattribution. Channel taxonomy needs a different source or `HEURISTIC` grading. |
| **D4** | Google Safety Charter is dated **June 2025**, not 2026. The 6-crore figure and its pilot framing are accurate. | Date correction only. |
| **D5** | **Link rot confirmed.** The HDFC URL (SRC-008) now redirects `hdfcbank.com → hdfc.bank.in`, and the destination did not carry the cited content. | Five rules rest on this source. Now unverifiable *and* from a commercial body ([CONF-005](../00-program/conflict-register.md)). |
| **D6** | NITI Aayog does not use the word *"secrecy"*. Its wording is *"instructed not to involve family or lawyers"*. | Encode the source's wording, not the paraphrase. |

None of these are fabrications by the research package — they are attribution drift and one
stale link. But four of the six would have silently propagated into user-facing output had the
verification pass been skipped.

## 5. Organisation-level findings

| Organisation | Cited | Retrieved | Assessment |
|---|---|---|---|
| **I4C** | 5 | **0** | 🔴 Entirely unreachable — all five URLs failed (connection reset / no response). I4C is ranked *"Very high"* priority by the research package and underpins roughly **12 of 30** rules. **The single largest evidence gap in the programme.** |
| **NPCI** | 2 | **0** | 🔴 Entirely unreachable (HTTP 403 on both methods). Underpins the three highest-scored rules. **Substance survives** via CERT-In SRC-021. |
| **CERT-In** | 4 | 3 | 🟢 The most reliably verifiable official source. Two specific advisories plus the awareness booklet, all quoted. |
| **RBI** | 2 | 2 | 🟢 Both retrieved, one with discrepancy D1. |
| **SEBI** | 2 | 1 + 1 partial | 🟡 Investor page verified; press release exists but body unretrievable. |
| **PIB** | 2 | **0** | 🔴 Both HTTP 403. Includes the headline ₹11,158 crore statistic. |
| **HDFC Bank** | 2 | **0** | 🔴 Link rot; commercial authority level. |
| Google / Meta | 2 | 2 | 🟢 Both verified with exact quotes. |
| CISA / Europol | 2 | 1 partial | 🟡 Background context only; low impact. |

**The pattern is structural, not random.** Indian government domains (`i4c.mha.gov.in`,
`pib.gov.in`, `npci.org.in`) systematically block automated retrieval, while
`cert-in.org.in`, `niti.gov.in` and `rbi.org.in` permit it. This is a durable operating
condition, not a transient failure, and it must shape how TrustLens ingests advisories in future
([RESEARCH-005](RESEARCH-005-gap-register.md)).

## 6. Claims that must NOT be repeated as fact

Explicitly listed so no downstream artifact reuses them casually:

| Claim | Why not |
|---|---|
| "₹11,158 crore saved across 32.80 lakh complaints by 30 June 2026" | SRC-001 unretrievable. **Unverified statistic — do not cite.** |
| "RBI says institutions never ask for UPI-PIN" | D1 — UPI-PIN is absent from the source's list |
| "I4C has a dedicated 2025 advisory on fake CAPTCHA-filling jobs" | SRC-002 unretrievable; cited only to an index page |
| "I4C's June 2026 Boss Scam advisory" | SRC-022 unretrievable (403) |
| "I4C's 2021 advisory documents the part-time task sequence" | SRC-015 unretrievable |
| Any HDFC-sourced rule basis | D5 — link rot, content not located, commercial authority |

## 7. Evidence-quality scoring input

For the DET-001 source-reliability term, authority level and verification status combine:

| Authority | Verified | Weight |
|---|---|---|
| `OFFICIAL_REGULATOR` / `OFFICIAL_GOVERNMENT` | `PRIMARY_VERIFIED` | 1.00 |
| `OFFICIAL_*` | `PRIMARY_CITED_UNVERIFIED` | 0.70 |
| `OFFICIAL_*` | `RETRIEVAL_FAILED` | 0.50 |
| `FOREIGN_OFFICIAL` | `PRIMARY_VERIFIED` | 0.70 |
| `INDUSTRY` | `PRIMARY_VERIFIED` | 0.60 |
| `INDUSTRY` | `RETRIEVAL_FAILED` | 0.30 |
| any | `INDEX_ONLY` | **0.00 — cannot alone support a rule** |

These weights are **`HEURISTIC`** — no source publishes a reliability scale. They are programme
judgements, are labelled as such, and are calibrated in DET-001 rather than treated as given.

## 8. Change history

| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-07-31 | Initial inventory. 26 sources graded; 11 verified with located quotations; 6 discrepancies identified; I4C and NPCI found entirely unreachable. | Threat Intelligence Lead |
| 1.1 | 2026-08-14 | Approved at the Phase 1 gate ([GATE-001](../00-program/GATE-001-phase-1-assessment.md)). No change to grades or findings. Companion manifest amended to v1.1: verified fraction restated as `PRIMARY_VERIFIED` only (11/26, matching §2), and `claim_under_test` recorded for the seven failed sources that carried none. | Technical Program Director |
