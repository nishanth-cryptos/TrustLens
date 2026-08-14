# TrustLens Glossary — Controlled Vocabulary

| Field | Value |
|---|---|
| Document ID | GLOSSARY |
| Version | 1.0 |
| Status | Draft |
| Owner role | Chief Architect / Threat Intelligence Lead |
| Dependencies | PROGRAM-001 |
| Last updated | 2026-07-31 |

This glossary is **normative**. Where these terms appear in TrustLens artifacts, code or UI,
they carry exactly the meaning defined here. Terms are deliberately kept distinct where common
usage would conflate them — most importantly *risk*, *confidence*, *severity* and *evidence
quality*, which the programme forbids collapsing into a single number ([CONF-001](conflict-register.md)).

---

## 1. Decision quantities

These four are **independent axes**. A finding can be high-severity and low-confidence; that
combination means "if true this is serious, but we are not sure it is true" — and it must be
presented that way, not averaged into a single percentage.

| Term | Definition | What it is NOT |
|---|---|---|
| **Severity** | How much harm the scam pattern would cause *if the finding is correct*. A property of the **scam class**, largely fixed per rule. Ordinal: `LOW \| MEDIUM \| HIGH \| CRITICAL`. | Not a measure of whether the pattern is present. |
| **Risk** | Computed exposure for *this specific submission*: a function of severity and the strength of matched evidence. Bounded, decomposable, reproducible. | Not a probability. Not "how sure we are". |
| **Confidence** | How much we trust our own analysis of this submission — driven by extraction quality, corroboration across independent indicators, and completeness of context. | Not risk. A confident finding may be low-risk. |
| **Evidence quality** | Reliability of the *inputs* — OCR fidelity, whether text was truncated, whether the sender is known, whether enrichment succeeded. Feeds confidence. | Not the reliability of the rule's source. |
| **Signal strength** | Contribution of a single indicator or rule match to risk, before aggregation and correlation adjustment. | Not the final score. |
| **Trust** | Reliability weight of a knowledge *source* or threat-intelligence provider. A property of the source, not the submission. | Not confidence in the finding. |

## 2. Pipeline and domain terms

| Term | Definition |
|---|---|
| **Submission** | One user act of sending content to TrustLens for analysis. Contains one or more artifacts. |
| **Artifact** | A single piece of submitted content: a text body, a URL, an image, an email source. Immutable once stored. |
| **Normalisation** | Deterministic conversion of an artifact to canonical form (Unicode normalisation, whitespace, case folding for matching, script detection) without discarding the original. |
| **Extraction** | Deriving structured items from normalised content: entities and indicators. |
| **Entity** | A concrete identifiable thing found in content — URL, phone number, UPI VPA, amount, organisation name, app name, account number. |
| **Indicator** | An observed *signal* belonging to one of the indicator families (e.g. `CREDENTIAL_REQUEST`, `SECRECY_DEMAND`). Carries no score on its own. |
| **Negative indicator** | An observed signal that *reduces* risk or suppresses a rule — e.g. "never share this OTP", a verified known sender. |
| **Rule** | A versioned, declarative, source-referenced statement that a named combination of indicators and context constitutes a recognised scam pattern. Stored as validated data, not code. |
| **Rule set** | A versioned collection of rules published together. Evaluations pin the rule-set version so historical cases replay identically. |
| **Evaluation** | One deterministic execution of a rule set against one submission's extracted evidence. |
| **Finding** | A single rule match produced by an evaluation, with its contributing indicators, score contribution and source references. |
| **Decision** | The overall classified outcome of an evaluation across all findings, including the `INSUFFICIENT_EVIDENCE` outcome. |
| **Explanation** | The human-readable and machine-readable account of a decision: what matched, what did not, what reduced risk, why confidence is limited, and how to verify. |
| **Case** | A durable container grouping submissions, evidence, findings, analyst notes and reports for one incident. |
| **Evidence item** | An artifact plus its integrity metadata — hash, capture timestamp, chain-of-custody record. |
| **Report bundle** | A reproducible, exportable package assembled from a case. Assists reporting; is **not** an official determination. |
| **Adjudication** | An analyst's recorded judgement on a finding or case, including agreement, disagreement and rationale. |
| **Provenance** | The recorded origin of any knowledge item: which source, which advisory, retrieved when, verified how. |
| **Replay** | Re-running a historical evaluation with its pinned rule-set version and configuration to reproduce the original result exactly. |

## 3. Evidence and provenance grades

Applied to every source in RESEARCH-001 and every rule in the knowledge base.

| Grade | Meaning |
|---|---|
| `PRIMARY_VERIFIED` | The issuing body's own document was retrieved and the specific claim was located within it. |
| `PRIMARY_CITED_UNVERIFIED` | A specific primary document is cited but has not been retrieved and checked. |
| `INDEX_ONLY` | The citation resolves to a listing or index page, not to a document substantiating the claim. **Insufficient on its own.** |
| `SECONDARY` | The claim comes from a synthesis or commentary about a primary source. |
| `HEURISTIC` | An engineering judgement with no source claim. Must be labelled as such in the rule. |
| `SYNTHETIC` | Example content authored for testing. **Never** presented as a real-world sample. |

## 4. India-specific domain terms

| Term | Definition |
|---|---|
| **UPI** | Unified Payments Interface — India's real-time retail payment system, operated by NPCI. |
| **UPI PIN** | The secret that authorises *sending* money via UPI. Receiving money never requires it — a boundary that underpins several detection rules. |
| **VPA** | Virtual Payment Address, the `name@bank` identifier used to address UPI payments. |
| **OTP** | One-Time Password. Note the critical distinction between a message *delivering* an OTP and one *requesting* it — see [CONF-002](conflict-register.md). |
| **KYC** | Know Your Customer — regulated identity verification. A frequent scam pretext. |
| **Digital arrest** | A coercion scam in which offenders impersonate law enforcement, allege criminal involvement, impose secrecy, and extract payment under threat of arrest. |
| **Smishing / Vishing** | Phishing conducted over SMS / voice call respectively. |
| **USSD** | Telephony short codes (e.g. `*21#`); abused to silently enable call forwarding. |
| **APK / sideloading** | Installing Android apps outside the official store — a malware delivery vector. |

### Organisations referenced by the knowledge base

| Abbrev. | Body | Authority level |
|---|---|---|
| **I4C** | Indian Cybercrime Coordination Centre, Ministry of Home Affairs | Official (government) |
| **NCRP** | National Cyber Crime Reporting Portal | Official (government) |
| **CERT-In** | Indian Computer Emergency Response Team | Official (government) |
| **RBI** | Reserve Bank of India | Official (regulator) |
| **NPCI** | National Payments Corporation of India | Official (payment system operator) |
| **SEBI** | Securities and Exchange Board of India | Official (regulator) |
| **DoT** | Department of Telecommunications | Official (government) |
| **Sanchar Saathi / Chakshu** | DoT citizen portal for reporting suspected fraud communication | Official (government) |
| **NITI Aayog** | Government of India policy think tank | Official (government, advisory) |
| **CISA** | US Cybersecurity and Infrastructure Security Agency | Official (foreign government) |
| **Europol** | EU law enforcement agency | Official (foreign, intergovernmental) |
| **HDFC Bank, Google, Meta, Microsoft** | Commercial organisations | **Not authorities.** Corroborating industry guidance only — see [CONF-005](conflict-register.md). |

## 5. Programme terms

| Term | Definition |
|---|---|
| **Quality gate** | A named, evidence-checked condition that must hold before a phase counts as approved input to the next. Reported as `PASS`, `PARTIAL` or `BLOCKED`. |
| **Vertical slice** | A demonstrable increment cutting through every layer, leaving the repository in a working state. |
| **Master prompt (MP)** | The supplied *TrustLens Master Execution Prompt*, the programme's authoritative instruction. Cited as `MP §n`. |
| **Research package (RP)** | The supplied *TrustLens Phase One Research Foundation*. Cited as `RP p.n`. Classified `SECONDARY` — see [BASELINE-001](BASELINE-001-repository-assessment.md). |

---

## Change history

| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-07-31 | Initial controlled vocabulary established during Phase 0. | Chief Architect |
