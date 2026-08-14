# RESEARCH-003 — Structured Advisory Extraction

| Field | Value |
|---|---|
| Document ID | RESEARCH-003 |
| Version | 1.1 |
| Status | **Approved** — closed at the Phase 1 gate, [GATE-001](../00-program/GATE-001-phase-1-assessment.md) |
| Owner role | Threat Intelligence Lead |
| Dependencies | RESEARCH-001, RESEARCH-002 |
| Feeds | RESEARCH-004, KB-001, DET-001 |
| Last updated | 2026-08-14 |

---

## 1. Scope and method

Normalised extraction from advisories that reached `PRIMARY_VERIFIED` in
[RESEARCH-001](RESEARCH-001-source-inventory.md). **Sources that could not be retrieved are
deliberately absent** — extracting from a document we could not read would be exactly the
fabrication `MP §21` prohibits.

Ten advisory extractions follow, covering the categories that will carry the MVP. Long advisory
text is not reproduced (`MP §8`); only short verbatim quotations sufficient to anchor each claim.

Fields per `MP §8`: scam category · threat type · victim profile · attack vector · communication
channel · indicators · requested action · payment method · severity cues · recommended response
· source linkage.

---

## ADV-001 · Digital arrest

| Field | Value |
|---|---|
| **Source** | SRC-012 — NITI Aayog, *Digital Arrest: The Modern-Day Cyber Scam*, 2025-04 · `PRIMARY_VERIFIED` |
| **Category** | `TAX-03-01`, `TAX-03-02` → escalates to `TAX-01-02` |
| **Threat type** | Extortion through impersonation and coercion |
| **Victim profile** | Explicitly broad — *"high-ranking officials, journalists, security personnel, and even innocent elderly individuals"* |
| **Attack vector** | Inbound call, escalating to video call |
| **Channel** | Voice call, video call; opening pretext may arrive by message |
| **Indicators** | Law-enforcement identity claim · accusation of money laundering, cybercrime or drug trafficking · threat of arrest · threat of account freezing · threat of passport cancellation · fake documents · doctored videos · spoofed phone numbers · instruction not to involve family or lawyers · demand for "fine" or "security deposit" |
| **Requested action** | Immediate payment framed as a fine or refundable security deposit |
| **Payment method** | UPI, crypto and other digital means |
| **Severity cues** | Fear + authority + isolation + immediate payment — the source characterises this as extortion, i.e. direct financial loss with coercion |
| **Opening pretexts** | *"a harmless parcel delivery claim to a demand for KYC verification"* — links `TAX-07-01` and `TAX-02-02` as entry points |
| **Recommended response** | Make no payment; verify independently through official channels; involve family — the source identifies isolation as part of the method |

> **Verbatim:** *"Coercion: Victims are threatened with arrest, freezing of bank accounts, or
> passport cancellation. They are instructed not to involve family or lawyers, and are asked to
> pay a 'security deposit' or 'fine.'"*

**Note (D6):** the source never uses the word *"secrecy"*. Encode `ISOLATION_FROM_FAMILY_OR_LAWYER`,
matching the source's own wording.

---

## ADV-002 · WhatsApp account takeover via device linking (GhostPairing)

| Field | Value |
|---|---|
| **Source** | SRC-017 — CERT-In, CIAD-2025-0055, 2025-12-19 · `PRIMARY_VERIFIED` |
| **Category** | `TAX-09-01`, `TAX-09-02`, `TAX-09-03` |
| **Threat type** | Account takeover without credential theft |
| **Victim profile** | Messaging-app users; propagates through the victim's own contacts |
| **Attack vector** | Message from a trusted contact carrying a link with a fake social-media preview |
| **Channel** | WhatsApp / messaging |
| **Indicators** | Teaser text (*"Hi, check this photo"*) · Facebook-style link preview · fake viewer page · prompt to "verify" · request to link a device · request for phone number followed by a linking code |
| **Requested action** | Complete a "verification" step that actually links the attacker's device |
| **Payment method** | None at this stage — takeover precedes monetisation |
| **Severity cues** | *"take complete control of WhatsApp accounts without needing passwords or SIM swaps"* — full account compromise |
| **Recommended response** | Do not complete device linking; audit linked devices |

> **Verbatim:** *"The message contains a link with a Facebook-style preview. The link leads to a
> fake Facebook viewer that prompts users to 'verify' to see the content."*

**Corroboration:** SRC-016 (Meta, 2026-03-11) independently describes the same mechanism —
*"trick you into scanning a QR code under false pretenses, which would then link the scammer's
device to your account."* Two independent sources, one official and one platform operator.

---

## ADV-003 · Preventing online scams — payment, transfer and job guidance

| Field | Value |
|---|---|
| **Source** | SRC-021 — CERT-In, *Preventing Online scams*, CIAD-2024-0050, 2024-10-24 · `PRIMARY_VERIFIED` |
| **Categories** | `TAX-01-02`, `TAX-01-03`, `TAX-06-01`, `TAX-08-04` |

The single highest-value advisory of the verification pass — it substantiates four distinct
detection concepts, including the payment boundary NPCI could not be retrieved to confirm.

| # | Verbatim guidance | Detection concept | Category |
|---|---|---|---|
| 1 | *"Always remember, you don't need a UPI PIN or OTP to receive money."* | **Receive-vs-pay boundary.** A credential prompt framed as necessary to *receive* funds is contradicted by official guidance. | `TAX-01-02` |
| 2 | *"Verify the sender's banking name before making payments using QR codes."* | Payee identity verification before QR payment | `TAX-01-03` |
| 3 | *"Verify requests for urgent money transfers by calling directly your relatives/friends."* | Out-of-band verification for urgent personal transfer requests | `TAX-08-04` |
| 4 | *"Never pay for job offers. Verify job postings and companies before applying or providing personal data."* | Payment demanded as a precondition of employment | `TAX-06-01` |

**Why concept 1 matters most.** It is the rare piece of official guidance that is *bidirectional
and falsifiable*: it does not say "be careful with UPI PIN", it states a categorical rule about
when a PIN is required. That makes it usable as a **high-confidence composite condition** —
receive/refund/credit framing **combined with** a credential prompt — rather than a keyword.

---

## ADV-004 · Social media fraud

| Field | Value |
|---|---|
| **Source** | SRC-014 — CERT-In, *Cyber Security Awareness Booklet* (NCSAM 2023) · `PRIMARY_VERIFIED` |
| **Category** | `TAX-08-02` |
| **Threat type** | Trust abuse through impersonation of a known person |
| **Attack vector** | Cloned or fake profile of someone the victim trusts; automated accounts |
| **Channel** | Social media platforms |
| **Indicators** | Fake profile of the victim or of a contact · bot-driven outreach · payment request arriving through a social channel |
| **Requested action** | Online payment to an attacker-controlled account |
| **Recommended response** | Verify identity out-of-band; report the fake profile |

> **Verbatim:** *"Scammers use 'bots' to trick unsuspecting users into making online payments to
> accounts under their control"* and *"Fraudsters use Fake Profile of the victim"*.

---

## ADV-005 · Safe use of digital transactions

| Field | Value |
|---|---|
| **Source** | SRC-004 — RBI, 2020-06-22 · `PRIMARY_VERIFIED` |
| **Category** | `TAX-01-01`, `TAX-01-07` |
| **Threat type** | Credential harvesting by impersonation of a financial institution |
| **Indicators** | Any request for password, PIN, OTP or CVV attributed to a bank or payment operator · financial activity over public/open/free Wi-Fi |
| **Recommended response** | Never share; use official channels; avoid public Wi-Fi for financial transactions |

> **Verbatim:** *"banks and other payment systems operators never ask for details such as
> password, PIN, OTP, CVV number"*

**Constraint (D1).** **UPI-PIN does not appear in this source's list.** Any rule asserting *"RBI
says never share your UPI PIN"* is unsupported. The UPI PIN concept is supported instead by
SRC-021 (ADV-003 #1), and only in the receive-context form.

**Age.** 2020. Still current guidance in substance, but six years old — relevant to the review-due
date this source's dependent rules should carry.

---

## ADV-006 · Financial awareness — assured returns as a fraud cue

| Field | Value |
|---|---|
| **Source** | SRC-020 — RBI, *FAME* booklet · `PRIMARY_VERIFIED` |
| **Category** | `TAX-05-01` |
| **Indicators** | Guaranteed or extraordinary return claims · "zero risk" framing · unregulated counterparty |
| **Recommended response** | Deal only with registered or regulated entities |

> **Verbatim:** the booklet presents *"120% returns assured! Zero risk!"* as a fraud cue, and
> advises *"Invest with or deposit only with entities registered with or regulated"*.

**Detection note.** RBI presents an *example of scam wording*, not a threshold. There is no
official basis for any specific percentage cut-off. The detectable concept is the **conjunction
of a return guarantee with a risk denial** — "assured" plus "zero risk" — not a number.

---

## ADV-007 · Investor caution

| Field | Value |
|---|---|
| **Source** | SRC-006 — SEBI, *Caution to Investor* · `PRIMARY_VERIFIED` |
| **Category** | `TAX-05-01`, `TAX-05-02` |
| **Indicators** | Guaranteed high returns · advice from an unregistered adviser · adviser handling client cash, securities or trades · Ponzi markers: unregistered investments, unlicensed sellers, non-transparent disclosure, difficulty receiving payments, overly consistent returns |
| **Recommended response** | Verify SEBI registration; take advice only from registered entities |

> **Verbatim:** *"Be highly suspicious of any guaranteed high return investment opportunity."* ·
> *"It is illegal to act as Investment Adviser without SEBI registration."* · *"Investment
> Advisers have to limit themselves to giving advice and they should not handle cash or securities."*

**Constraint (D2).** Deepfake and social-media promotion claims are **not** on this page. They
belong to SRC-023, whose body could not be retrieved — so the deepfake rule concept remains
`PRIMARY_CITED_UNVERIFIED`.

---

## ADV-008 · Chakshu fraud-communication reporting categories

| Field | Value |
|---|---|
| **Source** | SRC-007 — DoT / Sanchar Saathi · `PRIMARY_VERIFIED` |
| **Category** | Cross-cutting — `TAX-02`, `TAX-03-03`, `TAX-04`, `TAX-07-02` |
| **Value** | An **official enumeration of fraud-communication categories** by the national telecom reporting channel — useful as independent corroboration that these categories are nationally recognised |

> **Verbatim categories:** *"Bank Account / Payment Wallet / SIM / Gas / Electricity / KYC
> update, impersonation as Government official, sextortion etc."*

**Note.** `sextortion` appears in the official category list but is **absent from the research
package's taxonomy entirely**. Recorded as a gap in [RESEARCH-005](RESEARCH-005-gap-register.md).

---

## ADV-009 · Messaging-app device linking (platform)

| Field | Value |
|---|---|
| **Source** | SRC-016 — Meta, 2026-03-11 · `PRIMARY_VERIFIED` · `INDUSTRY` authority |
| **Category** | `TAX-09-01` |
| **Indicators** | Request to share phone number then a device-linking code · request to scan a QR code under a false pretext |
| **Role** | Corroborates ADV-002 from the platform operator's side. Being `INDUSTRY`, it carries lower source weight but raises confidence through **independent agreement** with an official source. |

---

## ADV-010 · High-risk app installation (platform)

| Field | Value |
|---|---|
| **Source** | SRC-010 — Google, 2025-06-18 · `PRIMARY_VERIFIED` · `INDUSTRY` authority |
| **Category** | `TAX-10-01` |
| **Claim** | *"Since our Play Protect pilot rolled out in October 2024 in India, it has blocked nearly 6 crore (60 million) attempts to install high-risk apps"* |
| **Role** | Establishes **prevalence**, not a detection rule. Supports prioritising `TAX-10-01`; contributes no indicator. |

**Care required.** This is a vendor-reported figure about its own product. Cite as prevalence
context only — never as a TrustLens performance benchmark or as evidence any specific message is
malicious.

---

## 2. Cross-advisory patterns

Two structural findings that shape DET-001.

**The staged funnel is confirmed by verified sources.** ADV-001 documents it fully: contact
(parcel/KYC pretext) → escalation (accusation, panic) → legitimacy props (fake documents,
doctored videos, spoofed numbers) → isolation (no family or lawyers) → payment (fine/security
deposit). ADV-002 shows the same shape for takeover: lure → fake preview → fake verification →
device link. **Stage sequence is itself a detectable signal**, not just the individual cues.

**Every verified advisory describes conjunctions, never single keywords.** Not one verified
source says "the word OTP indicates fraud". They say a *bank never asks* for it (ADV-005), or
that you *don't need it to receive money* (ADV-003). Both are statements about **context and
direction**. This is direct primary-source support for the three-layer architecture in
[CONF-002](../00-program/conflict-register.md) — the combinational requirement is now evidenced,
not merely asserted.

## 3. Change history

| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-07-31 | Initial extraction from 10 verified advisories. Unretrievable sources deliberately excluded. | Threat Intelligence Lead |
| 1.1 | 2026-08-14 | Approved at the Phase 1 gate ([GATE-001](../00-program/GATE-001-phase-1-assessment.md)). No content change: every extraction already derives from a `PRIMARY_VERIFIED` source, which is the gate's central traceability condition. | Technical Program Director |
