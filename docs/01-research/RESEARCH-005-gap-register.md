# RESEARCH-005 — Research Gap Register

| Field | Value |
|---|---|
| Document ID | RESEARCH-005 |
| Version | 1.2 |
| Status | **Approved** (v1.1) · **Reconciled** at v1.2 after RESEARCH-006. The register stays **live**: gaps close in later phases. |
| Owner role | Threat Intelligence Lead |
| Dependencies | RESEARCH-001…004, [RESEARCH-006](RESEARCH-006-manual-retrieval-reconciliation.md) |
| Feeds | KB-001, DET-001, PLAN-001 |
| Last updated | 2026-08-28 |

---

## 1. Purpose

`MP §8` requires a register that **separates unsupported assumptions from supported facts**. This
is the artifact that keeps TrustLens honest: anything not evidenced appears here rather than
being quietly absorbed into the knowledge base.

**Severity:** 🔴 blocks or materially weakens MVP · 🟠 limits coverage · 🟡 future work.

---

## 2. Source access gaps

| ID | Gap | Severity | Impact | Path to closure |
|---|---|---|---|---|
| **G-01** | **I4C entirely unreachable.** All 5 cited URLs failed (connection reset / no response), including the advisories index carrying 13 citation markers. | 🔴 | **7 rules unsupported.** I4C is ranked the highest-priority source by the research package. The single largest evidence gap in the programme. | Manual retrieval from a browser on an Indian network; official contact; or a mirror. Rules stay `DRAFT` until then. |
| **G-02** | **NPCI unreachable.** Both URLs HTTP 403 via two methods. | 🟠 | Underpins the three highest-scored starter rules. **Substantially mitigated** — CERT-In SRC-021 independently establishes the receive-vs-pay boundary. | Manual retrieval; or accept CERT-In as the primary anchor. |
| **G-03** | **PIB unreachable** (both URLs 403), including the ₹11,158 crore / 32.80 lakh headline statistic. | 🟠 | Statistic **must not be repeated as fact**. Executive-impersonation rule unsupported. | Manual retrieval. |
| **G-04** | **HDFC link rot.** `hdfcbank.com` → `hdfc.bank.in`; cited content not located at destination. | 🟠 | 3 rules unsupported, 2 more partial. Compounded by HDFC being a commercial source, not an authority. | Locate current pages; **prefer replacing with official-source equivalents** rather than re-citing a bank. |
| **G-05** | Europol report download incomplete; text unextractable. | 🟡 | Background AI-threat context only. | Re-attempt; low priority. |
| **G-06** | SEBI press release PR 27/2025 body not retrievable — only title and date confirmed. | 🟡 | Deepfake investment rule held at `PARTIAL`. | Re-attempt retrieval. |

**Structural finding.** The failures are not random: `i4c.mha.gov.in`, `pib.gov.in` and
`npci.org.in` systematically block automated retrieval, while `cert-in.org.in`, `niti.gov.in` and
`rbi.org.in` permit it. **This is a durable operating condition.** Any future advisory-ingestion
pipeline must assume a human-in-the-loop retrieval step for a subset of official sources — it
cannot be fully automated. This belongs in INT-001 and OPS-001.

### 2a. Manual retrieval reconciliation status (2026-08-28)

The manual retrieval pass ([RESEARCH-006](RESEARCH-006-manual-retrieval-reconciliation.md), executed
via a human-in-the-loop browser session exactly as the structural finding predicted) changed the
status of most source-access gaps. This validated the human-in-the-loop closure path itself.

| Gap | New status | What changed |
|---|---|---|
| **G-01** (I4C) | 🟠 **partially closed** | 3 of the 4 rule-bearing I4C sources now carry official evidence: SRC-013, SRC-019, SRC-024 via the I4C **CyberDost** channel (OFFICIAL_ALTERNATE); SRC-015 via the PIB-2023 + I4C-2025 replacement pair (OFFICIAL_REPLACEMENT). **SRC-002 (advisories index) remains unavailable and stays open** — an index is not claim evidence. |
| **G-02** (NPCI) | 🟢 **closed** | SRC-005 (BHIM-UPI Guidelines p.77) and SRC-018 (Fraud Awareness p.2) retrieved as exact primary. |
| **G-03** (PIB) | 🟢 **closed** | SRC-001 (CFCFRMS statistic) and SRC-022 (Boss-Scam release) retrieved as exact primary. The ₹11,158 cr / 32.80 lakh statistic is now citable **with its manual-retrieval provenance** (MR-EVID-001). |
| **G-04** (HDFC) | 🟠 **partially addressed** | Current pages captured: SRC-008 (Beware of Fraud) and SRC-026 (Security Threat Detected). Both are `INDUSTRY`, so they corroborate and cap at PARTIAL; SRC-026 supports `TL-MAL-003`. `TL-PAY-004` and `TL-IMP-001` claims are **not** present in the replacement — they stay unsupported. |
| **G-06** (SEBI PR 27/2025 body) | 🟠 **partially closed** | Body retrieved (MR-EVID-005): celebrity/public-figure impersonation, fake testimonials and unreasonable-return promises verified. The **deepfake-specific** mechanism is **not present** and folds into G-16. |
| **G-05** (Europol) | 🟡 **open — low impact** | SRC-011 still unavailable; background context only; must not block Phase 2. |

**Durable-truth guard.** No original `RETRIEVAL_FAILED` status was overwritten. Replacement and
alternate documents keep their own durable evidence IDs and are attached to the original failed
source through the manifest's additive `manual_retrieval` layer (DEC-006, ADR-0015). An unavailable
original PDF is never recorded as retrieved because a replacement exists.

## 3. Knowledge gaps

| ID | Gap | Severity | Impact | Path to closure |
|---|---|---|---|---|
| **G-07** | **No negative indicators exist anywhere in the research package.** It supplies 12 positive indicator families and zero suppressive signals. | 🔴 | [CONF-002](../00-program/conflict-register.md)'s architecture *requires* negative indicators. Without them, the false-positive problem is unsolvable. | **Author them in Phase 2 as `HEURISTIC`**, derived from the inverse of verified guidance (e.g. SRC-004's "banks never ask" implies a message *telling you not to share* is protective, not threatening). Validate against the benign corpus. |
| **G-08** | **Zero non-English content.** Every trigger cue in all 30 rules is English; no Devanagari, Tamil, Telugu or transliterated Hinglish. | 🔴 | Product claims multilingual; knowledge base cannot deliver it ([CONF-004](../00-program/conflict-register.md)). | Sponsor decision on [OI-04](../00-program/PROGRAM-001-program-charter.md#11-open-issues). No verified source supplies non-English cues, so any added would be `HEURISTIC`. |
| **G-09** | **No labelled real-world corpus**, and none obtainable. | 🔴 | Precision, recall and calibration **cannot be measured** ([RSK-003](../00-program/risk-register.md)). | **Unclosable within this programme.** Synthetic corpus supports determinism and regression only. Must be disclosed in every quality claim. |
| **G-10** | **Sextortion is missing from the research taxonomy** despite appearing in Chakshu's official reporting categories (SRC-007 ✅). | 🟠 | A nationally-recognised fraud category is absent from our taxonomy. | Add as `TAX-11` in Phase 2, or consciously scope out — it carries distinct victim-harm and safeguarding considerations that may warrant separate handling. |
| **G-11** | Three rules require evidence TrustLens cannot observe ([CONF-003](../00-program/conflict-register.md)): device network state, user journey, live payment flow. | 🟠 | Coverage 30 → 27; 2 further rules only partially detectable. | Encode as `DEFERRED` with `blocked_by: INPUT_MODALITY`. Revisit only if a device-side component is ever in scope. |
| **G-12** | Categories with **zero sources**: loan-app abuse (`TAX-01-05`), mule accounts / illegal payment gateways (`TAX-01-06`). | 🟠 | Named in the research prose but carry no citation at all. | Dedicated research pass; RBI is the likely authority. |
| **G-13** | Smishing / vishing channel taxonomy is **unsourced** — not present on the cited CISA page (D3). | 🟡 | Channel taxonomy is currently an engineering construct. | Reclassify `HEURISTIC`, or source from CISA's actual social-engineering page. |
| **G-14** | **Source freshness varies widely** — RBI SRC-004 is from 2020, CERT-In SRC-014 from 2023, while Meta SRC-016 is from 2026. | 🟡 | A 2020 advisory may not reflect current scam mechanics; rules built on it need earlier review dates. | Set `review_due` per source age in the rule schema. |
| **G-15** | No guidance retrieved on **OCR quality for Indian scripts**, though screenshots are a primary submission modality. | 🟠 | Evidence-quality scoring for OCR output is unspecified ([RSK-015](../00-program/risk-register.md)). | Empirical evaluation in Phase 4/9; not a research gap that sources can close. |

## 4. Gaps the research package identified in itself

Carried forward and confirmed (`RP p.13`):

| ID | Gap | Severity | Status |
|---|---|---|---|
| **G-16** | Multilingual deepfake detection cues · **and the deepfake-specific mechanism generally** | 🟡 | Confirmed open. Now also the home for the SEBI deepfake gap: SRC-023's body verifies celebrity impersonation but **contains no deepfake-specific statement** (2026-08-28). `TL-INV-003` is narrowed to celebrity/social-media impersonation; the deepfake mechanism has no verified official basis. Compounds G-08. |
| **G-17** | Structured rules for synthetic-voice extortion | 🟡 | Confirmed open. Relevant to the digital-arrest video-call vector (ADV-001). |
| **G-18** | Cross-platform identity correlation | 🟡 | Confirmed open. Out of MVP scope. |
| **G-19** | Consumer-visible mule-account detection logic | 🟠 | Confirmed open; overlaps G-12. |
| **G-20** | Aadhaar / PAN-specific scam wording in rule-friendly form | 🟠 | Confirmed open. Notable given identity fraud is `TAX-02`. |
| **G-21** | Advisory PDFs not consistently fetchable | 🔴 | **Confirmed empirically and worse than stated** — not intermittent, but systematic per-domain blocking (G-01…G-03). |
| **G-22** | Second focused research pass needed for UIDAI, Income Tax, IRDAI | 🟡 | Open; none of these bodies is cited at all in the current source base. |

## 5. Explicit separation of fact from assumption

Required by `MP §8`. The programme's position, stated plainly:

### Supported facts — verified primary quotations exist
- Banks and payment operators never ask for password, PIN, OTP or CVV *(SRC-004)*
- A UPI PIN or OTP is **not** needed to receive money *(SRC-021)*
- Payee banking name should be verified before QR payment *(SRC-021)*
- Urgent transfer requests should be verified by direct call *(SRC-021)*
- Payment should never be required for a job offer *(SRC-021)*
- Digital arrest uses law-enforcement impersonation, arrest/account-freeze/passport threats, fake documents and doctored videos, isolation from family and lawyers, and demands a "fine" or "security deposit" *(SRC-012)*
- WhatsApp accounts can be fully taken over via deceptive device linking, without passwords or SIM swap *(SRC-017, corroborated SRC-016)*
- Guaranteed high returns are a fraud cue; unregistered investment advice is illegal in India *(SRC-006, SRC-020)*
- Fake profiles and bots are used to induce online payments *(SRC-014)*
- Chakshu's official fraud-communication categories include bank/wallet/SIM/gas/electricity/KYC, government-official impersonation and sextortion *(SRC-007)*

### Unsupported assumptions — currently carry no verified basis
- RBI says institutions never ask for **UPI-PIN** *(contradicted — D1; still stands)*
- ~~The ₹11,158 crore / 32.80 lakh CFCFRMS statistic~~ → **now verified** (MR-EVID-001, PIB PRID 2287674); cite only with its manual-retrieval provenance
- ~~All I4C-attributed rule bases~~ → **partially resolved (2026-08-28):** boss scam (SRC-022), task apps (SRC-015 replacement), wallet verification (SRC-024), accessibility abuse (SRC-019) and USSD call-forwarding (SRC-013) now carry official evidence. **Still unsupported:** CAPTCHA jobs and matrimonial pivot (both SRC-002 index, still unavailable)
- HDFC-attributed rule bases: **screen sharing now PARTIAL** (SRC-026, INDUSTRY); **false credit and customer-care sourcing remain unsupported** (claim absent from the replacement)
- Any specific numeric risk score *(no source publishes one — [CONF-001](../00-program/conflict-register.md))*
- Any claim about TrustLens detection accuracy *(no corpus — G-09)*
- **The deepfake-specific investment mechanism** *(no verified official basis — G-16)*

## 6. Prioritised closure plan

| Priority | Gaps | Action | Owner |
|---|---|---|---|
| 1 | G-07 | Author negative-indicator library in Phase 2, validated against the benign corpus | Chief Architect |
| 2 | G-01, G-03, G-04 | Manual retrieval of I4C, PIB and current HDFC-equivalent official sources | Sponsor + TI Lead |
| 3 | G-08 | Sponsor decision on OI-04 language scope | Sponsor |
| 4 | G-10, G-12 | Taxonomy completion — sextortion, loan apps, mule accounts | TI Lead |
| 5 | G-09 | Permanent disclosure in TEST-001 and PRR-001 | QA Lead |
| — | G-16…G-22 | Backlog for a second research pass | TI Lead |

## 7. Change history

| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-07-31 | Register opened with 22 gaps: 6 source-access, 9 knowledge, 7 carried forward. Fact/assumption separation stated explicitly. | Threat Intelligence Lead |
| 1.1 | 2026-08-14 | Approved at the Phase 1 gate ([GATE-001](../00-program/GATE-001-phase-1-assessment.md)). All 22 gaps remain **open** — approval covers the register's completeness, not gap closure. G-01, G-03 and G-04 now carry an explicit per-source work list in the [verification manifest](../../knowledge/sources/verification-manifest.json) (`claim_under_test`, `blocks_rules`). G-07 is the highest-priority Phase 2 work package. | Technical Program Director |
| 1.2 | 2026-08-28 | Reconciled with RESEARCH-006 (§2a). **G-02 and G-03 closed; G-01, G-04, G-06 partially closed; G-05 open (low impact).** SRC-002 and SRC-011 stay open. Deepfake-specific gap folded into G-16. Original failed statuses preserved (durable-truth guard). | Threat Intelligence Lead |
