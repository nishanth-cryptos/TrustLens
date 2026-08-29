# Software Requirements Specification

## for TrustLens

```title-page
Version 2.0

Prepared by:
*&lt;Name&gt;*  *&lt;Reg No&gt;*
*&lt;Branch&gt;*

*&lt;Course Code and Title&gt;*
*&lt;Assignment&gt;*
Faculty: *&lt;Faculty Name&gt;*

Semester: *&lt;Semester&gt;*  Year: *&lt;Year&gt;*
Date Created: 24 August 2026
```

| | |
|---|---|
| **Document ID** | SRS-001 |
| **Version** | 2.0 |
| **Status** | Draft for review |
| **Prepared by** | *&lt;Name&gt;* · *&lt;Reg No&gt;* · *&lt;Branch&gt;* |
| **Semester / Year** | *&lt;Semester&gt;* / *&lt;Year&gt;* |
| **Organization** | *&lt;Institution&gt;* |
| **Date created** | 24 August 2026 |
| **Template** | IEEE 830-1998 structure, Karl E. Wiegers SRS template (1999) |

> Fill the italic placeholders on the title page before submitting. They are the only
> unresolved fields there.

---

## Table of Contents

Revision History

1. Introduction
   1.1 Purpose · 1.2 Document Conventions · 1.3 Intended Audience and Reading Suggestions ·
   1.4 Product Scope · 1.5 References
2. Overall Description
   2.1 Product Perspective · 2.2 Product Functions · 2.3 User Classes and Characteristics ·
   2.4 Operating Environment · 2.5 Design and Implementation Constraints · 2.6 User Documentation ·
   2.7 Assumptions and Dependencies
3. External Interface Requirements
   3.1 User Interfaces · 3.2 Hardware Interfaces · 3.3 Software Interfaces ·
   3.4 Communications Interfaces
4. System Features
   4.1 Submission and Evidence Preservation · 4.2 Normalisation and Evidence Extraction ·
   4.3 Rule-Based Detection and Scoring · 4.4 Explanation of Findings ·
   4.5 Analyst Review and Adjudication · 4.6 Case Management and Report Bundle ·
   4.7 Knowledge Base Governance · 4.8 Identity, Access and Audit ·
   4.9 Enrichment and AI Assistance · 4.10 Analytics
5. Other Nonfunctional Requirements
   5.1 Performance Requirements · 5.2 Safety Requirements · 5.3 Security Requirements ·
   5.4 Software Quality Attributes · 5.5 Business Rules
6. Other Requirements

Appendix A: Glossary · Appendix B: Analysis Models · Appendix C: To Be Determined List

## Revision History

| Name | Date | Reason For Changes | Version |
|---|---|---|---|
| *&lt;Name&gt;* | 23 August 2026 | First SRS. Requirements taken from the programme charter and rearranged into the IEEE 830 / Wiegers structure. | 1.0 |
| *&lt;Name&gt;* | 24 August 2026 | Rewritten to the department SRS format. Requirements renumbered by section (4.1.3.1 style) instead of REQ-n, nonfunctional requirements moved into ID / Category / Requirement tables, and the charter cross-reference tags removed from the requirement text. Appendix B now carries the ER model, the three data flow diagrams and the use case diagram. No requirement was dropped. | 2.0 |

---

# 1. Introduction

## 1.1 Purpose

TrustLens is a scam-detection and evidence-preservation tool for Indian digital fraud. Someone who
has received a suspicious SMS, WhatsApp message, email or link can submit it and get back a verdict
saying how risky it looks, how sure the system is, and which official advisory the judgement rests
on. It also stores the submitted content with a hash so it can serve as evidence later, and
packages it into a report the person can take to a bank or to the police.

This document covers the whole product, not one module. It describes release 1.0, which is the
text-message path end to end, and it also describes what is planned after that (enrichment
adapters, AI assistance and analytics) so the boundary between now and later is written down rather
than assumed. It says what the software has to do, not how to build it.

## 1.2 Document Conventions

The IEEE 830-1998 structure and the Wiegers template were used. Requirements are numbered by the
section they sit in, so requirement 4.3.3.2 is the second functional requirement of feature 4.3.
**Shall** marks a binding requirement; **should** is a recommendation and never appears inside a
numbered requirement.

Priority is given per feature in its 4.x.1 subsection: **High** means release 1.0 is not finished
without it, **Medium** means we want it but could ship without it, and **Post-MVP** means it is
specified now and built later. Individual Post-MVP requirements inside a High-priority feature are
marked where they appear.

Every requirement came from the programme charter, which came from the project brief. Nothing was
invented while moving requirements into this document. A few rest on our own engineering judgement
rather than an instruction from anyone, and those are called out where they appear.

## 1.3 Intended Audience and Reading Suggestions

Written for the project team and the faculty reviewing it. In a real setting it would also be read
by developers, testers and whoever is paying for the work.

Read it in order. Sections 1 and 2 give the context. Section 3 draws the line between TrustLens and
everything outside it. Section 4 is the part a developer would build from, and Section 5 covers the
qualities the system needs regardless of feature. Appendix C lists what is still undecided and is
worth reading before treating any of this as final.

## 1.4 Product Scope

Digital fraud in India tends to run as a staged funnel: the victim is contacted, given a pretext,
pushed into either trusting or fearing the caller, asked for a credential or a payment, and then
told to keep quiet. The damaging step is almost always performed by the victim, whether that is
entering a UPI PIN, scanning a QR code, installing an APK, or paying a "fine" to somebody claiming
to be a police officer.

There is already a lot of official guidance on this from I4C, CERT-In, RBI, NPCI, SEBI and DoT. The
problem is that it is not in a form software can use. It sits in advisory PDFs and press releases
written for people to read, and it goes out of date. TrustLens is an attempt to close the gap
between that published guidance and a decision somebody can act on when they need it.

What the product should achieve:

1. Give a verdict that keeps **risk** and **confidence** as two separate things and shows the
   evidence for both.
2. Make every finding traceable, from the submitted content through the extracted indicators and
   matched rules to the official source behind the rule.
3. Preserve the submitted evidence with integrity metadata and turn it into a report bundle.
4. Make a decision taken today reproducible months later from the stored evidence and the rule-set
   version that was used.

**Out of scope.** TrustLens does not file reports with any authority automatically, issue an
official determination of fraud, or give legal advice. It does not block, intercept or change any
message, call or payment, and it does not run as a device agent or read device state. It does not
let an AI model make the final decision, does not retrain itself on user feedback without a human
approving the change, and does not try to identify or profile individual offenders.

**One limitation worth stating up front.** There is no labelled real-world corpus of Indian scam
messages available to us and we cannot obtain one within this project, so precision, recall and
false-positive rate cannot be measured. No accuracy claim appears anywhere in this document. What
*can* be proven without such a corpus, such as determinism, traceability and schema conformance, is
specified in Section 5.4 with a verification method attached to each.

## 1.5 References

| # | Document | Location |
|---|---|---|
| R1 | Programme charter, the source of every requirement here | `docs/00-program/PROGRAM-001-program-charter.md` |
| R2 | Glossary, assumption, risk and conflict registers | `docs/00-program/` |
| R3 | Source inventory: 26 sources graded, 11 verified | `docs/01-research/RESEARCH-001-source-inventory.md` |
| R4 | Scam taxonomy: 10 categories, 41 subcategories | `docs/01-research/RESEARCH-002-scam-taxonomy.md` |
| R5 | Evidence matrix: 30 starter rules graded | `docs/01-research/RESEARCH-004-evidence-matrix.md` |
| R6 | Research gap register: 22 open gaps | `docs/01-research/RESEARCH-005-gap-register.md` |
| R7 | ADR-0003, rule representation format, and the rule JSON Schema | `adr/`, `knowledge/schemas/rule.schema.json` |
| R8 | IEEE Std 830-1998 and the K. E. Wiegers SRS template (1999) | Structure used for this document |
| R9 | Analysis models: ER, DFD levels 0 to 2, use case | `docs/05-architecture/diagrams/`, reproduced in Appendix B |

---

# 2. Overall Description

## 2.1 Product Perspective

TrustLens is a new, self-contained product. It does not replace anything, it is not part of a
product family, and it does not extend an existing tool. There is no legacy code and no earlier
deployment to work around.

It is not self-sufficient in knowledge, though. Everything it can detect comes from a curated
knowledge base built out of published official guidance, and that guidance reaches the system
through a governed pipeline with a human in it rather than an automatic feed. A TrustLens with an
empty rule set is a working system that detects nothing.

The product boundary is drawn as a level 0 data flow diagram in Appendix B, Figure B-2. TrustLens
exchanges data with nine outside parties: the reporting user, an analyst, an administrator, the
report recipient, the official guidance bodies whose advisories feed the knowledge base, a
knowledge editor, a knowledge approver, and two Post-MVP providers for threat intelligence and AI
assistance. The eighteen flows crossing that boundary are labelled F1 to F18 on the diagram.

Two of those are worth calling out. The report recipient link is outbound only and always
user-initiated, never an automatic submission. The guidance bodies link is inbound only, and
everything arriving on it is graded before it is allowed to affect a rule.

## 2.2 Product Functions

There are eight things the system does. They match the eight processes in the level 1 data flow
diagram in Appendix B, so the two can be checked against each other.

- **Ingest and preserve evidence** — check the submitted artifacts, hash each one, record
  chain-of-custody metadata
- **Normalise and extract** — canonical form, language and script, then entities, indicators and
  negative indicators
- **Evaluate rules and score** — run a pinned rule set and compute risk, confidence, severity and
  evidence quality as four separate numbers
- **Compose explanation** — what matched, what did not and why, what reduced the risk, and which
  official source backs each finding
- **Route and adjudicate** — send uncertain cases to an analyst and record the decision with its
  reasoning
- **Assemble report bundle** — build an exportable package from a case, disclaimer attached
- **Govern the knowledge base** — grade sources, validate and lint draft rules, run review and
  approval, publish and roll back versions
- **Administer, audit and observe** — authentication, role-based access, retention policy, audit
  events

## 2.3 User Classes and Characteristics

Six user classes are expected. The first two decide whether the product succeeds; the rest are
internal operators.

We should be honest that none of these have been validated. No end user, analyst, knowledge editor
or administrator was available to talk to, so all six descriptions are our own inference. This is
the biggest single source of requirement risk in the document.

**Reporting user, general (P1)** is the one that matters most. Salaried, urban, not technical, on a
phone, submitting occasionally and usually in a hurry with about thirty seconds of patience. Sees
only their own data. Wants a fast plain-language verdict and one clear next step, and is failed by
an answer that is hedged into meaninglessness or full of jargon.

**Reporting user, high-harm (P2)** submits rarely and in a crisis. Retired, WhatsApp-first, inclined
to defer to authority, and targeted by coercion scams such as digital arrest. Also sees only their
own data. Needs a calm, unambiguous contradiction of what the scammer told them, and is failed if
the system equivocates or adds to the panic.

**Analyst (P3)** works the queue of uncertain cases daily. A domain expert who can read every case
and adjudicate it. Needs the full score breakdown and needs to see what did *not* match, and is
failed if they cannot tell why the engine concluded what it did.

**Knowledge editor (P4)** turns new advisories into rules, roughly weekly. Can author rules but
cannot publish them. Needs a schema that makes a well-formed rule easy to write and a malformed one
impossible, and is failed if adding a rule means touching engine code.

**Knowledge approver (P5)** gatekeeps publication, also weekly. Can publish, reject and roll back.
Needs a diff, an impact analysis and regression results before approving, and is failed if rules
can reach production unreviewed.

**Administrator (P6)** runs the platform as needed. Has full configuration access but no access to
case content. Needs health signals, rollback and retention controls, and should not have to read
submitted content to do any of it.

Official guidance bodies and report recipients also interact with the product but are not user
classes. The first are consumed one way, the second receive an export without operating the
software.

## 2.4 Operating Environment

Current evergreen browsers on mobile and desktop, mobile first, since the primary user is assumed
to be on a phone. No native mobile app in release 1.0. React with TypeScript in strict mode on the
frontend, Java 21 with Spring Boot 3.x as a modular monolith on the backend, and PostgreSQL 16
behind it. The Python and FastAPI service for AI and advanced extraction is a separate deployable
and is deferred to a later phase. Docker and Docker Compose locally, GitHub Actions for CI. Local
and test environments only for now: no production deployment happens during this project, and the
hosted target has not been decided.

Java 21.0.11, Maven 3.9.11 and Node 26.0.0 are installed on the development machine. Docker and
PostgreSQL are not, which blocks implementation but not the specification work.

## 2.5 Design and Implementation Constraints

| ID | Constraint |
|---|---|
| 2.5.1 | No automatic submission of legal or regulatory reports, to any authority, by any route. |
| 2.5.2 | No accuracy claim unless it comes from a reproducible evaluation on a described dataset, and no fabricated advisories, citations, statistics or datasets. Synthetic examples shall be labelled synthetic. |
| 2.5.3 | The rule engine is the decision authority. AI output is advisory and never authoritative. |
| 2.5.4 | Java 21 with Spring Boot on the backend, React with TypeScript on the frontend. The Python service is deferred. Delivery capacity is one engineer plus AI assistance. |
| 2.5.5 | Docker and PostgreSQL are missing from the development machine, so implementation is blocked until they are installed. |
| 2.5.6 | Rules are versioned JSON data validated by a published JSON Schema and a cross-file linter, never engine code. Adding a new scam type means writing one JSON file. |
| 2.5.7 | Rule identifiers are neutral (`TL-<domain>-<nnn>`). Source attribution is carried as data, not embedded in the key. |
| 2.5.8 | No rule may fire on a single indicator, and no rule may fire on weak indicators alone. Enforced at load time, not by convention. Severity is an ordinal from `LOW` to `CRITICAL`; numeric risk or confidence values are not stored on a rule. |
| 2.5.9 | Three starter rules need evidence TrustLens cannot observe (device network state, user journey, live payment flow). They stay marked `DEFERRED` and are not published. |

## 2.6 User Documentation

Shipping with the software: in-product help and first-run guidance, a guide to reading a verdict
(what risk against confidence means, and what `INSUFFICIENT_EVIDENCE` means), a README inside every
report bundle covering the contents, the hash verification steps and the disclaimer, an analyst
adjudication guide, a rule authoring guide with a worked example per rule shape and a catalogue of
lint errors, an approval and rollback runbook, an operations runbook, and an API reference
generated from the OpenAPI document. Online material in HTML, anything meant to leave the system
with a user in PDF.

## 2.7 Assumptions and Dependencies

Assumptions we are working under:

- No end user, analyst or official-body stakeholder is available, so every persona and journey in
  this document is our own inference. This one is load-bearing and we have low confidence in it.
- The deployment is single tenant, release 1.0 is English first (the architecture is multilingual,
  the content is not), and no real user data is processed during the project. All examples are
  synthetic and labelled.
- Users submit content after the fact, usually on a phone, rather than during a live attack, so the
  latency budget is seconds rather than milliseconds.
- Submitted content routinely contains live sensitive data such as OTPs, account numbers and VPAs,
  and has to be treated as sensitive from the moment it arrives, before anything is classified.
- There is no budget for paid threat-intelligence providers, so those adapters target free tiers or
  are stubbed.
- TrustLens holds no regulatory registration, official status or relationship with any body whose
  guidance it cites.
- Default evidence retention is 90 days. That is a placeholder, not a policy decision. India's
  Digital Personal Data Protection Act 2023 is *likely* to apply, but this has not been legally
  verified and no compliance claim is being made here.
- During development, rule authoring and approval are done by the same person. The separation of
  duties is built and tested even though it is not enforced organisationally.

Things the project depends on:

- **Official-source retrieval is partly manual.** We tested this rather than assuming it:
  `i4c.mha.gov.in`, `pib.gov.in` and `npci.org.in` block automated retrieval, while
  `cert-in.org.in`, `niti.gov.in` and `rbi.org.in` allow it. Any advisory-ingestion feature
  therefore has to assume a human retrieval step, and full automation is not achievable.
- **Knowledge base completeness.** 26 sources graded and 11 verified, 30 starter rules graded of
  which 18 are both evidenced and implementable. Detection coverage at release is limited by the
  evidence available, not by what the engine can do.
- **The negative-indicator library does not exist yet.** The research package gives us 12 positive
  indicator families and zero suppressive signals. Without negative indicators the false-positive
  problem cannot be solved, so this is the highest-priority piece of outstanding knowledge work.
- **No labelled corpus**, which is why Section 5.4 is limited to provable attributes.
- **Docker and PostgreSQL** are not installed, which blocks implementation entirely.
- **Third-party providers and an OCR engine** are needed for the Post-MVP features. The core path
  has to finish with any one of them unavailable, and we have no guidance yet on OCR quality for
  Indian scripts.

---

# 3. External Interface Requirements

## 3.1 User Interfaces

One responsive web application, mobile first, with navigation that changes by role. There is no
separate installable client in release 1.0.

Nine screens. **Submit**, **Verdict**, **Evidence detail** and **Correction** are the reporting
user's path: paste or upload content with optional sender and channel context, read the outcome
with risk and confidence shown separately, expand into the indicators found and the rules matched
and not matched, and amend a misextracted entity to re-run the evaluation. **Case** groups one
incident and exports its bundle. **Review queue** gives the analyst the uncertain cases with the
full score breakdown and the adjudication controls. **Rule authoring** and **Approval** are the
knowledge editor's and approver's screens, the second carrying the diff, impact analysis and
regression results. **Administration** holds configuration, thresholds, retention, feature flags
and health.

Rules that apply to every screen:

- WCAG 2.2 AA on all release 1.0 journeys, checked by automated and manual audit.
- Risk and confidence are never merged into one number, one bar or one colour anywhere.
- The plain-language explanation is the default view and the technical breakdown is one action
  away, never what P1 or P2 land on. Every verdict view carries the "not an official determination"
  disclaimer without the user having to click anything to see it.
- Supported languages are stated in the interface and unsupported input is flagged rather than
  quietly returning a weak result. Error messages say what went wrong and what to do next, and
  never include raw submitted content, secrets or internal identifiers.

Layout, interaction and visual design are out of scope for this document and belong in a separate
UI specification.

## 3.2 Hardware Interfaces

None. TrustLens is a browser-delivered web application with no direct hardware dependency. It does
not talk to device sensors, SIM or telephony hardware, card readers or any physical peripheral.
Camera and file access for screenshot upload go through standard browser APIs, so the software has
no knowledge of the underlying device.

This is deliberate rather than an omission. Device-agent behaviour is explicitly out of scope, and
constraint 2.5.13 records the three rules that consequently cannot be implemented.

## 3.3 Software Interfaces

| # | Component | Purpose |
|---|---|---|
| 3.3.1 | PostgreSQL 16 | Primary datastore for evidence, cases, findings, pinned analyses and audit events. Reached through a connection pool over TLS. |
| 3.3.2 | Rule JSON Schema, version 1.0 | The single authority on rule structure. The Java loader validates rule documents against the schema file itself, not a reimplementation of it. |
| 3.3.3 | Cross-file rule linter | Enforces the constraints a single-document schema cannot express, checking a rule against the indicator registry, the taxonomy and the verification manifest. Returns a verdict naming the layer that caught the problem. Runs in CI before any rule can be published. |
| 3.3.4 | Source verification manifest | Maps source identifiers to a verification status and grade. A rule cannot claim a grade the manifest contradicts. |
| 3.3.5 | OCR engine *(Post-MVP)* | Extracts text from image artifacts with a per-block confidence value that feeds evidence quality. Engine not yet selected. |
| 3.3.6 | URL / threat-intelligence providers *(Post-MVP)* | Take a URL or domain and return a reputation verdict, labelled non-authoritative. Several providers behind one provider-agnostic adapter. |
| 3.3.7 | AI assist provider *(Post-MVP)* | Takes an isolated content prompt and returns schema-constrained JSON. Extraction help and draft rule suggestions, advisory only. |
| 3.3.8 | Identity provider | Takes credentials or a federated assertion and returns an authenticated principal with roles. Not yet selected. |

The rule set, indicator registry and scam taxonomy are shared between the knowledge-governance side
and the detection side. They are shared as immutable versioned snapshots rather than a mutable
store both sides write to, so that publishing a new version cannot retroactively change an analysis
that has already finished.

## 3.4 Communications Interfaces

HTTPS only, TLS 1.3, versioned REST over JSON described by an OpenAPI document from which the
published reference is generated. Asynchronous messaging only where the workload justifies it.
JSON payloads, UTF-8 throughout, with the original byte sequence of submitted content kept
unmodified alongside the normalised form. Every request carries a correlation identifier that is
propagated through logs and audit events.

Report export is an authenticated, access-controlled download. There is no outbound transmission of
a report to any authority by any protocol, and that is enforced by the capability not existing
rather than by a configuration flag. TrustLens sends no SMS and no scam-related notification
traffic; transactional email, if added, is limited to account and access functions. Outbound
enrichment calls (Post-MVP) go over HTTPS with a per-provider timeout and a circuit breaker, and a
provider failure degrades the result rather than failing the submission. Public endpoints are
rate-limited.

---

# 4. System Features

Ten features. Each one states its priority, the stimulus and response pairs that exercise it, and
its numbered functional requirements.

## 4.1 Submission and Evidence Preservation

### 4.1.1 Description and Priority

Takes content from a reporting user, checks it, and preserves each item with integrity metadata
before any analysis runs. Preservation happens first on purpose, so the integrity of the evidence
does not depend on what the analysis later concludes. High priority.

### 4.1.2 Stimulus/Response Sequences

**S1** User pastes SMS or chat text and submits — System accepts the artifact, hashes it, records the capture time and chain-of-custody metadata, creates a submission and starts the analysis.

**S2** User uploads a screenshot that is too large or of an unsupported type — System rejects the upload before processing it, states the limit and the accepted types, and keeps the rest of the submission.

### 4.1.3 Functional Requirements

4.1.3.1: The system shall accept free-text submission of SMS, WhatsApp or other chat message
bodies.

4.1.3.2: The system shall accept URL submission.

4.1.3.3: The system shall accept email content including headers.

4.1.3.4: The system shall accept screenshot and image upload. *(Post-MVP)*

4.1.3.5: The system shall group multiple artifacts into a single submission and a single case.

4.1.3.6: The system shall validate media type, size and structure before processing, and reject
unsafe uploads without processing them. *(Post-MVP)*

4.1.3.7: The system shall accept optional user-supplied context consisting of sender, channel and
description.

4.1.3.8: The system shall compute and store a cryptographic hash of every evidence item on ingest,
together with its chain-of-custody metadata.

4.1.3.9: The system shall keep the original submitted content unmodified alongside any normalised
form derived from it.

## 4.2 Normalisation and Evidence Extraction

### 4.2.1 Description and Priority

Turns preserved artifacts into canonical form and derives what detection works on: entities,
indicators and negative indicators. Extraction aims for high recall and attaches no score to
anything, because an observation is not yet a finding. High priority.

### 4.2.2 Stimulus/Response Sequences

**S1** An artifact enters extraction — System normalises it deterministically, identifies the language and script, and extracts entities and indicators.

**S2** Content contains "Your OTP is 452901. Never share it with anyone." — System extracts both the OTP mention and the self-protective warning, the second as a negative indicator, so the message is not treated as a credential request.

### 4.2.3 Functional Requirements

4.2.3.1: The system shall normalise content to a canonical form deterministically, so that the same
input always produces the same canonical output.

4.2.3.2: The system shall identify the language and script of submitted content.

4.2.3.3: The system shall handle code-mixed and transliterated Indian-language input. *(Post-MVP)*

4.2.3.4: The system shall extract text from screenshots by OCR, recording a per-block confidence
value that contributes to evidence quality. *(Post-MVP)*

4.2.3.5: The system shall extract entities of at least these types: URL, phone number, UPI VPA,
monetary amount, organisation name, application name and account reference.

4.2.3.6: The system shall extract indicators across the defined indicator families, and no
extracted indicator shall carry a score.

4.2.3.7: The system shall detect negative indicators that suppress a rule or reduce risk.

4.2.3.8: The system shall let a user correct an extraction error and re-evaluate the submission,
keeping both the original and the corrected extraction.

## 4.3 Rule-Based Detection and Scoring

### 4.3.1 Description and Priority

The core of the product. Takes the extracted evidence, runs a pinned versioned rule set over it,
and produces risk, confidence, severity and evidence quality as four separate values. Rules are
composite by construction, so no single indicator on its own ever produces a finding.

High priority, and the highest-risk feature in the product. Both of its failure modes damage trust:
missing a real attack, and flagging a bank's own anti-fraud message as a scam.

### 4.3.2 Stimulus/Response Sequences

**S1** A suppression rule's condition is met — System suppresses the affected finding and records the suppression as an explicit outcome rather than as an absence.

**S2** Evidence is too thin to conclude anything — System returns `INSUFFICIENT_EVIDENCE` instead of a low-risk verdict.

### 4.3.3 Functional Requirements

4.3.3.1: The system shall evaluate rules deterministically against the extracted evidence.

4.3.3.2: The system shall support composite rules that require combinations of indicators spanning
at least two distinct evidence classes.

4.3.3.3: The system shall support suppression rules, exceptions and exclusions.

4.3.3.4: The system shall compute risk, confidence, severity and evidence quality as separate
quantities and shall never combine them into a single value, in the pipeline or in the interface.

4.3.3.5: The system shall handle correlated signals without double counting their contribution.
*(Post-MVP)*

4.3.3.6: The system shall return an explicit `INSUFFICIENT_EVIDENCE` outcome when the evidence does
not support a conclusion.

4.3.3.7: The system shall route evaluations past a configured uncertainty threshold to human
review.

4.3.3.8: The system shall pin the rule-set version to every evaluation.

4.3.3.9: The system shall replay a historical evaluation and reproduce its result exactly.

4.3.3.10: The system shall resolve conflicts between competing positive and negative indicators by
a defined and recorded precedence.

4.3.3.11: The system shall fail safe on a malformed rule, an evaluation timeout or partial
evidence, emitting no finding that depends on the incomplete evaluation.

## 4.4 Explanation of Findings

### 4.4.1 Description and Priority

Turns an evaluation into something a person can check. The requirement is not that the system
explains *that* it decided, but that it breaks down *why*, including what it rejected and why it is
not more confident. High priority.

### 4.4.2 Stimulus/Response Sequences

**S1** User opens the detail view — System lists matched rules with their contributing indicators, rules considered but not matched with the reason, negative evidence that reduced risk, and the full score breakdown.

**S2** Confidence is limited — System says why, and what extra context would raise it.

### 4.4.3 Functional Requirements

4.4.3.1: The system shall report which rules matched, together with their contributing indicators.

4.4.3.2: The system shall report which rules were considered but did not match, and why.

4.4.3.3: The system shall report negative evidence that reduced the risk.

4.4.3.4: The system shall provide a full score breakdown for each computed component.

4.4.3.5: The system shall state why confidence is limited and what context is missing.

4.4.3.6: The system shall surface the source references behind each matched rule, including each
source's provenance grade.

4.4.3.7: The system shall present a plain-language explanation with an optional technical detail
view.

4.4.3.8: The system shall describe how an analyst can independently verify a conclusion.
*(Post-MVP)*

## 4.5 Analyst Review and Adjudication

### 4.5.1 Description and Priority

Human judgement on the cases the engine is not confident about. Feedback is captured but never
triggers learning: an adjudication changes this case, not the rule set. Medium priority.

### 4.5.2 Stimulus/Response Sequences

**S1** A case goes past the uncertainty threshold — System puts it in the review queue with the full breakdown and what did not match.

**S2** Analyst agrees, disagrees or overrides — System records the adjudication with its reasoning, writes an audit event and updates the case.

### 4.5.3 Functional Requirements

4.5.3.1: The system shall present queued cases to an analyst with the full score breakdown and the
rules that did not match.

4.5.3.2: The system shall support analyst adjudication with a recorded reason, and write an audit
record for every override.

4.5.3.3: The system shall capture user feedback on findings without triggering any automatic change
to rules, thresholds or scoring. *(Post-MVP)*

## 4.6 Case Management and Report Bundle

### 4.6.1 Description and Priority

Groups everything about one incident and produces the artifact the user actually leaves with. The
bundle is only worth something if it is reproducible, so the same case has to produce an identical
bundle later. High priority.

### 4.6.2 Stimulus/Response Sequences

**S1** User requests a report for a case — System assembles the evidence with its hashes, the findings, the explanations, the source citations and the disclaimer into a structured bundle.

**S2** The same bundle is regenerated six weeks later — System reproduces an identical bundle from the stored evidence and the pinned analysis.

### 4.6.3 Functional Requirements

4.6.3.1: The system shall create and manage cases that group submissions, findings and analyst
notes.

4.6.3.2: The system shall generate a structured report bundle conforming to the defined report
contract.

4.6.3.3: The system shall reproduce an identical report bundle from the stored evidence and the
pinned analysis data.

4.6.3.4: The system shall provide report export through an authenticated, access-controlled
channel, and shall not transmit a report to any authority automatically.

4.6.3.5: The system shall carry a prominent disclaimer in every report bundle stating that it is
not an official determination of fraud.

## 4.7 Knowledge Base Governance

### 4.7.1 Description and Priority

How knowledge gets into the product. This is what lets a new scam type be added without touching
engine code, and what stops a rule claiming evidence it does not have. High priority.

### 4.7.2 Stimulus/Response Sequences

**S1** Editor submits a rule that would fire on one weak indicator — System rejects it at load time and names the constraint and the layer that caught it.

**S2** Editor submits a rule citing a source graded `RETRIEVAL_FAILED` — System rejects the claimed provenance grade.

### 4.7.3 Functional Requirements

4.7.3.1: The system shall store rules as versioned, schema-validated data and shall not express
rule logic as engine code.

4.7.3.2: The system shall reject any rule that fails schema validation or cross-file lint at load
time.

4.7.3.3: The system shall maintain a versioned scam taxonomy independently of engine code.

4.7.3.4: The system shall support the rule lifecycle: draft, peer review, security review, approve,
publish, deprecate, retire.

4.7.3.5: The system shall require at least one source reference carrying a provenance grade on
every non-heuristic rule, and shall require any rule without such a source to be labelled
heuristic.

4.7.3.6: The system shall reject a rule whose claimed source grade contradicts the source
verification manifest.

4.7.3.7: The system shall support rollback to a previously published rule-set version without
altering any completed evaluation. *(Post-MVP)*

4.7.3.8: The system shall perform an impact analysis when a rule, taxonomy term or source changes.
*(Post-MVP)*

4.7.3.9: The system shall allow a new scam type to be added through data and configuration alone,
with no change to engine code.

## 4.8 Identity, Access and Audit

### 4.8.1 Description and Priority

Establishes who is allowed to do what, and makes the security- and knowledge-relevant actions
permanently reviewable. High priority.

### 4.8.2 Stimulus/Response Sequences

**S1** An editor tries to publish a rule set — System denies it; publication needs the approver role.

**S2** A security- or knowledge-relevant action happens — System writes an immutable audit event with actor, action, target, timestamp and correlation identifier.

### 4.8.3 Functional Requirements

4.8.3.1: The system shall authenticate users.

4.8.3.2: The system shall enforce role-based access control across the reporting user, analyst,
knowledge editor, knowledge approver and administrator roles.

4.8.3.3: The system shall write immutable audit events for security- and knowledge-relevant
actions.

4.8.3.4: The system shall support data export and deletion requests with audit evidence that they
were fulfilled.

4.8.3.5: The system shall apply the configured retention class to submitted content and shall not
keep it beyond that class.

## 4.9 Enrichment and AI Assistance

### 4.9.1 Description and Priority

Two optional capabilities behind feature flags. Both are advisory: neither may decide an outcome,
and the system has to work fully with both switched off. Post-MVP, so low priority for release 1.0,
but the highest risk in the document, because this is where a model could quietly end up making the
decision if the boundary is not enforced.

### 4.9.2 Stimulus/Response Sequences

**S1** The provider times out or errors — System finishes the analysis without it and records the degradation.

**S2** The model returns output that does not fit the schema — System rejects the output and carries on deterministically.

### 4.9.3 Functional Requirements

4.9.3.1: The system shall integrate URL and threat-intelligence adapters behind a provider-agnostic
interface.

4.9.3.2: The system shall operate fully when any single external provider is unavailable.

4.9.3.3: The system shall gate all AI-assisted capability behind feature flags.

4.9.3.4: The system shall validate AI output against strict schemas and reject anything that does
not conform.

4.9.3.5: The system shall label model-derived observations distinctly from deterministic findings,
in storage, in API responses and in the interface.

4.9.3.6: The system shall require human approval before any AI-suggested rule is published.

4.9.3.7: The system shall degrade to deterministic-only operation when AI assistance is
unavailable, with the core path unaffected.

4.9.3.8: The system shall isolate submitted content from model instructions so that content cannot
alter model behaviour.

## 4.10 Analytics

### 4.10.1 Description and Priority

Operational and knowledge-quality reporting. It reports what the system did. It never makes a claim
about how accurate the system is. Post-MVP, low priority.

### 4.10.2 Stimulus/Response Sequences

**S1** Approver reviews knowledge quality — System reports rule usage, coverage and contribution.

**S2** Analyst reviews adjudication history — System reports adjudicated false positives and negatives by category, scoped to the dataset they were measured on.

### 4.10.3 Functional Requirements

4.10.3.1: The system shall report rule usage, coverage and contribution.

4.10.3.2: The system shall report adjudicated false positives and negatives by category, and shall
state the dataset and its limitations alongside any such figure.

4.10.3.3: The system shall report operational quality including volume, latency and review-queue
depth.

4.10.3.4: The system shall rate-limit public endpoints and protect them against abuse.

---

# 5. Other Nonfunctional Requirements

## 5.1 Performance Requirements

| ID | Category | Requirement |
|---|---|---|
| 5.1.1 | Performance | Analysis of a text-only submission shall complete in under 2 seconds at the 95th percentile. |
| 5.1.2 | Performance | Analysis of a screenshot submission that needs OCR shall complete in under 10 seconds at the 95th percentile. *(Post-MVP)* |
| 5.1.3 | Reliability | Rule-set load and validation shall finish before the system accepts traffic. A rule set that fails validation shall stop startup rather than degrade at runtime. |

The budget is in seconds rather than milliseconds because people submit content after an incident,
not during a live attack. Both numbers are our own estimates rather than the result of a user
study, and would be the first figures to revisit if a real user became available. We have put
numbers on them anyway, because a performance requirement nobody can measure is not a requirement.

## 5.2 Safety Requirements

These are about harm to the user, which for this product means acting on a verdict that is wrong or
that they have misread.

| ID | Category | Requirement |
|---|---|---|
| 5.2.1 | Safety | The system shall not present a verdict in a way that implies an official determination of fraud. |
| 5.2.2 | Safety | The system shall not present recommendations as legal advice. Recommended actions shall be safety actions only. |
| 5.2.3 | Safety | The system shall route ambiguous or weakly supported cases to review, or return `INSUFFICIENT_EVIDENCE`, rather than presenting an uncertain conclusion as a certain one. |
| 5.2.4 | Safety | For coercion scenarios such as digital arrest, the explanation shall plainly contradict what the scammer claimed, and shall not amplify urgency or fear. |
| 5.2.5 | Safety | The system shall not block, intercept or modify any message, call or payment. |
| 5.2.6 | Safety | Where the knowledge base cannot support a conclusion in the submitted language, the system shall say so explicitly rather than returning a weak result that reads as safety. |

## 5.3 Security Requirements

| ID | Category | Requirement |
|---|---|---|
| 5.3.1 | Security | All data shall be encrypted in transit using TLS 1.3 and at rest using AES-256. |
| 5.3.2 | Privacy | Logs shall contain no secrets, no personally identifiable information and no raw submitted evidence. This shall be verified by automated scanning. |
| 5.3.3 | Privacy | Submitted content shall be treated as sensitive from the moment it is ingested, before any classification decision is made about it. |
| 5.3.4 | Auditability | Security- and knowledge-relevant actions shall be recorded immutably, covering 100% of the defined event set. |
| 5.3.5 | Access control | Access to case content shall be restricted by role. The administrator role shall be able to operate the platform without access to submitted content. |
| 5.3.6 | Security | Uploaded files shall be validated and handled so that a malicious upload cannot execute or escape its processing context. |
| 5.3.7 | Security | Submitted content shall never be interpretable as an instruction by any downstream component, including AI-assisted ones. |
| 5.3.8 | Privacy | The system shall not identify or profile individual suspected offenders. |

On privacy: we have not had a lawyer look at whether India's Digital Personal Data Protection Act
2023 applies to TrustLens, and this document makes no compliance claim. The requirements above are
engineering practice, not a legal opinion.

## 5.4 Software Quality Attributes

This section is split into what can be proven and what cannot. Nothing in the first table needs
real-world data. Nothing in the second may be claimed until such data exists.

### 5.4.1 Provable

| ID | Attribute | Requirement | Verified by |
|---|---|---|---|
| 5.4.1.1 | Determinism | Identical evidence, rule-set version and configuration shall produce identical output, on 100% of golden-case replays. | Automated replay suite |
| 5.4.1.2 | Explainability | No finding shall exist without a complete evidence, rule and source trace. | Property test |
| 5.4.1.3 | Extensibility | A new scam type shall be addable with zero engine lines changed. | Integration test |
| 5.4.1.4 | Correctness of knowledge | Every published rule shall pass schema validation and cross-file lint. | CI gate |
| 5.4.1.5 | Traceability | Every non-heuristic published rule shall carry a graded source reference, and every rule without one shall be labelled heuristic. | CI gate |
| 5.4.1.6 | Accessibility | Release 1.0 journeys shall meet WCAG 2.2 AA. | Automated and manual audit |
| 5.4.1.7 | Testability | Automated gates shall exist at unit, schema, property, integration, contract and end-to-end level. | CI |
| 5.4.1.8 | Reproducibility | A clean clone shall build and run without manual intervention. | CI |
| 5.4.1.9 | Observability | All services shall emit structured logs with correlation identifiers, plus metrics and health checks. | Operational review |
| 5.4.1.10 | Maintainability | A new scam type shall be addable by a knowledge editor without a developer being involved. | Integration test |
| 5.4.1.11 | Availability of core path | The core analysis path shall complete when enrichment or AI assistance is unavailable. | Fault-injection test |

### 5.4.2 Not provable within this project

Precision, recall, false-positive rate, false-negative rate, calibration and abstention quality
cannot be claimed. There is no labelled real-world corpus and we cannot get one. A synthetic corpus
is useful for determinism and regression detection and nothing else. Any figure produced against
synthetic data shall be reported with its dataset scope and limitations attached, and shall never
be presented as a general accuracy claim.

## 5.5 Business Rules

| ID | Rule |
|---|---|
| 5.5.1 | The rule engine decides. AI assists interpretation and extraction; it never overrides deterministic evidence and is never the final authority. |
| 5.5.2 | Risk and confidence are separate quantities and are never collapsed into one number, anywhere. |
| 5.5.3 | A new scam type is added through data, not code. |
| 5.5.4 | No rule fires on a single indicator. Every published rule needs a combination spanning at least two distinct evidence classes. |
| 5.5.5 | Publication takes two roles. An editor may author and submit; only an approver may publish, reject or roll back. During development one person may hold both roles, but the system enforces the separation regardless. |
| 5.5.6 | A rule may not claim evidence it does not have. A rule whose source grade contradicts the verification manifest cannot be published, and an unsupported or heuristic rule cannot enter the published set at all. |
| 5.5.7 | TrustLens files nothing on anyone's behalf. Report bundles leave only through a user-initiated, access-controlled export. |
| 5.5.8 | Feedback never auto-trains. No user or analyst action changes a rule, a threshold or a score without human adjudication and the approval workflow. |
| 5.5.9 | Uncertainty is shown, not hidden. `INSUFFICIENT_EVIDENCE` is a first-class outcome, not a failure state, and synthetic content is always labelled synthetic. |
| 5.5.10 | Administrators operate the platform; they do not read cases. Platform administration does not carry access to submitted content. |

---

# 6. Other Requirements

**Database.** Evidence, cases, findings, pinned analyses and audit events shall be stored so that an
evaluation's inputs and rule-set version stay retrievable for replay for the full retention period,
audit events are append-only, and deletion under the retention policy or at a user's request
removes the submitted content while leaving audit evidence that the deletion happened.

**Internationalisation.** All user-facing text shall be externalised for translation from the first
release, and language and script shall be first-class fields in the rule schema rather than
something retrofitted later, even though release 1.0 ships English content only. The system shall
state which languages it supports and flag unsupported input. Which Indian languages make it into
release 1.0 has not been decided.

**Legal.** TrustLens holds no regulatory registration, official status or relationship with any body
whose guidance it cites. Every report bundle and every verdict view shall carry the "not an official
determination" disclaimer. No statement in the product shall assert a regulatory obligation that
has not been checked against a primary source.

**Reuse.** The rule schema, indicator registry, scam taxonomy and source verification manifest are
portable data artifacts, independent of the engine that reads them, so a future device-side or
partner component could reuse them without reimplementation.

**Deliberately not in this document**, following IEEE 830: project cost, delivery schedule and
staffing; design solutions such as module partitioning and data-structure choice; and product
assurance procedures such as QA and configuration management. Those belong in the roadmap, the
architecture decision records and the test strategy.

---

# Appendix A: Glossary

The terms below are normative. Where they appear in TrustLens code, artifacts or interface, they
mean exactly this. The four decision quantities are kept separate on purpose, because the whole
design rests on not collapsing them into one number.

## Decision quantities

| Term | Definition | What it is **not** |
|---|---|---|
| **Severity** | How much harm the scam pattern would cause *if the finding is right*. A property of the scam class, mostly fixed per rule. Ordinal: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`. | Not a measure of whether the pattern is actually present. |
| **Risk** | Computed exposure for *this particular submission*. A function of severity and the strength of the matched evidence. Bounded, decomposable, reproducible. | Not a probability, and not "how sure we are". |
| **Confidence** | How much the system trusts its own analysis of this submission: extraction quality, corroboration across independent indicators, completeness of context. | Not risk. A confident finding can be low risk. |
| **Evidence quality** | How reliable the *inputs* were: OCR fidelity, truncation, known sender, whether enrichment succeeded. Feeds confidence. | Not the reliability of the rule's source. |

## Pipeline and domain terms

| Term | Definition |
|---|---|
| **Submission** | One act of sending content for analysis. Contains one or more artifacts. |
| **Artifact** | A single piece of submitted content: a text body, a URL, an image, an email source. Immutable once stored. |
| **Entity** | A concrete identifiable thing found in the content: URL, phone number, UPI VPA, amount, organisation, app name, account reference. |
| **Indicator** | An observed signal belonging to an indicator family, for example `CREDENTIAL_REQUEST` or `SECRECY_DEMAND`. Carries no score. |
| **Negative indicator** | An observed signal that reduces risk or suppresses a rule, for example "never share this OTP". |
| **Rule** | A versioned, declarative, source-referenced statement that a named combination of indicators is a recognised scam pattern. Stored as validated data, not code. |
| **Rule set** | A versioned collection of rules published together. Evaluations pin the version they used. |
| **Evaluation** | One deterministic run of a rule set against one submission's extracted evidence. |
| **Case** | A durable container grouping the submissions, evidence, findings, notes and reports for one incident. |
| **Report bundle** | A reproducible, exportable package assembled from a case. Assists reporting; not an official determination. |

## Evidence and provenance grades

| Grade | Meaning |
|---|---|
| `PRIMARY_VERIFIED` | The issuing body's own document was retrieved and the specific claim was located inside it. |
| `PRIMARY_CITED_UNVERIFIED` | A specific primary document is cited but has not been retrieved and checked. |
| `INDEX_ONLY` | The citation resolves to a listing or index page, not to a document that substantiates the claim. Not sufficient on its own. |
| `SECONDARY` | The claim comes from a synthesis or a commentary about a primary source. |
| `HEURISTIC` | An engineering judgement with no source claim. Has to be labelled as such. |
| `SYNTHETIC` | Example content written for testing. Never presented as a real sample. |

## India-specific terms

| Term | Definition |
|---|---|
| **UPI** | Unified Payments Interface, India's real-time retail payment system, operated by NPCI. |
| **UPI PIN** | The secret that authorises *sending* money over UPI. Receiving money never needs it, which is the basis of several rules. |
| **VPA** | Virtual Payment Address, the `name@bank` identifier used to address UPI payments. |
| **OTP** | One-Time Password. Note the difference between a message *delivering* one and a message *requesting* one. |
| **KYC** | Know Your Customer, regulated identity verification. A frequent scam pretext. |
| **Digital arrest** | A coercion scam that impersonates law enforcement, alleges criminal involvement, demands secrecy and extracts payment under threat of arrest. |
| **USSD** | Telephony short codes such as `*21#`, abused to silently enable call forwarding. |

## Organisations

I4C is the Indian Cybercrime Coordination Centre and NCRP its National Cyber Crime Reporting
Portal, both under the Ministry of Home Affairs. CERT-In is the national computer emergency
response team. RBI, SEBI and DoT are the banking, securities and telecom regulators, and NPCI
operates UPI. Sanchar Saathi and its Chakshu module are DoT's citizen reporting portal. All of
these are official sources. Banks and platform companies are not authorities and count only as
corroborating industry guidance.

---

# Appendix B: Analysis Models

Four models are given here: the entity relationship model, the data flow diagrams at levels 0, 1
and 2, and the use case diagram. Together they cover the data the system stores, how that data
moves through it, and what each actor can ask it to do.

The DFD notation is DeMarco and Yourdon: an oval is a process, a rectangle is an external entity
and a cylinder is a data store. Level 0 contains no data store, by convention. Source files for all
of these live in `docs/05-architecture/diagrams/`.

## B.1 ER Diagram

```image
figures/er-model.png
Figure B-1 — TrustLens entity relationship model
```

The data model is built around four groups. **Submission and evidence**: `USER`, `CASE`,
`ARTIFACT`, `COMMUNICATION_CHANNEL`, `PLATFORM` and `EXTRACTED_ENTITY` hold what was submitted and
what was pulled out of it. **Knowledge**: `RULE`, `RULE_SET`, `INDICATOR`, `SCAM`, `ORGANISATION`
and `PAYMENT_METHOD` hold the versioned detection knowledge. **Analysis**: `ANALYSIS_RESULT` and
`THREAT_INTEL_CHECK` hold what a single evaluation concluded and what any external lookup returned.
**Output and governance**: `EVIDENCE_VAULT_ITEM`, `REPORT_BUNDLE`, `AUDIT_LOG` and `FEEDBACK` hold
the preserved evidence, the exportable package, the append-only audit trail and the user feedback
that never auto-trains anything.

The relationship that matters most for requirement 4.3.3.8 is `ANALYSIS_RESULT` to `RULE_SET`: an
analysis stores the rule-set version it used, which is what makes a replay months later reproduce
the same answer.

## B.2 Data Flow Diagrams

```image
figures/dfd-level0.png
Figure B-2 — Level 0 context diagram. One process, nine external entities, eighteen flows.
```

The level 0 diagram fixes the product boundary. Flow F9, the report export, leaves process 0.0
rather than passing between two external entities. That is both a rule of the notation and an
accurate statement of the constraint in Section 2.5.1: the export is user-initiated and
access-controlled, never an automatic submission. The AI assist provider sits outside the boundary,
with schema-checked drafts coming back inward, which puts constraint 2.5.3 into the structure of
the diagram rather than only in prose.

```image
figures/dfd-level1.png
Figure B-3 — Level 1 data flow diagram. Eight processes, six data stores.
```

Level 1 explodes process 0.0 into the eight processes listed in Section 2.2, plus six data stores:
`D1` Evidence Store, `D2` Case Store, `D3` Rule-Set Store, `D4` Source Register, `D5` Analysis
Record and `D6` Audit Log. Every flow at level 0 reappears here.

| Process | Level 0 flows it inherits |
|---|---|
| `1.0` Ingest and preserve evidence | F1 |
| `2.0` Normalise and extract | F2, F17 |
| `3.0` Evaluate rules and score | F15, F16 |
| `4.0` Compose explanation | F3 |
| `5.0` Route and adjudicate | F5, F6 |
| `6.0` Assemble report bundle | F4, F9 |
| `7.0` Govern knowledge base | F10, F11, F12, F13, F14, F18 |
| `8.0` Administer, audit and observe | F7, F8 |

```image
figures/dfd-level2.png
Figure B-4 — Level 2 data flow diagram, process 3.0 exploded into five sub-processes.
```

Level 2 breaks process 3.0 into `3.1` load and pin the rule set, `3.2` match composite rules, `3.3`
apply suppressors and resolve conflicts, `3.4` score risk and confidence separately, and `3.5`
decide the outcome and route it. The ordering is itself a requirement: 3.3 runs before 3.4, so
negative evidence cannot be out-voted after the scoring has already happened. Process `3.5` writes
the pinned analysis record that makes requirements 4.3.3.9 and 4.6.3.3 possible.

## B.3 Use Case Diagram

```image
figures/use-case.png
Figure B-5 — TrustLens use case diagram
```

The use case diagram shows how the four actors interact with the system. The **User** authenticates
and submits suspicious content as message text, a URL or a screenshot. Analysis pulls in several
mandatory steps through `<<include>>` relationships: extracting entities, checking threat
intelligence, applying the detection rules and computing a risk score, all before a verdict is
shown. The user can then view the matched indicators, preserve the evidence, generate a report
bundle as PDF or JSON, manage the case, and submit feedback.

Optional behaviour is drawn with `<<extend>>`: escalating a case to an analyst, and submitting
feedback after viewing a verdict. The **Security Analyst** reviews flagged cases and adjudicates
findings. The **Administrator** manages the detection rule lifecycle by creating, approving and
publishing rule sets. The **Threat Intelligence Provider** is an external actor that supplies the
reputation data the detection process can draw on.

Two things are deliberately absent from this diagram, and both are constraints rather than
oversights. There is no "submit report to authority" use case, because the product never does that
(Section 2.5.1). And there is no actor that can publish a rule without going through approval,
because publication needs the approver role (business rule 5.5.5).

---

# Appendix C: To Be Determined List

These are the things that are genuinely still open. Nothing in this list is quietly treated as
settled elsewhere in the document.

| ID | Item | What it blocks |
|---|---|---|
| C.1 | No end user, analyst or knowledge editor has validated any persona or journey. | Confidence in Section 2.3 and much of Section 4 |
| C.2 | Data retention period and legal basis are undecided, and DPDP applicability is unverified. | 4.8.3.4, 4.8.3.5, 5.3.3, Section 6 |
| C.3 | Docker and PostgreSQL are not installed on the development machine. | All implementation |
| C.4 | Which Indian languages are in release 1.0 scope. Currently English only, and no verified source gives us non-English cues. | 4.2.3.3, 5.2.6, Section 6 |
| C.5 | Deployment target unknown, local only or hosted. | Section 2.4 and the operational requirements |
| C.6 | OCR engine not selected, and there is no guidance on OCR quality for Indian scripts. | 4.2.3.4, 5.1.2 |
| C.7 | The negative-indicator library does not exist yet. The research package gave us zero suppressive signals. | 4.2.3.7, 4.3.3.3, and therefore the whole false-positive strategy |
| C.8 | The reduction maths for `REDUCE`-type suppression rules is undefined. Only `SUPPRESS` is currently expressible. | 4.3.3.3, 4.3.3.10 |
| C.9 | Seven I4C-attributed rule bases and three commercial-source rule bases could not be retrieved, so the rules resting on them stay unpublished. | Detection coverage at release |
| C.10 | No labelled real-world corpus exists, so accuracy is unmeasurable. This one cannot be closed within this project and is recorded so it is not quietly forgotten. | Section 5.4.2 and any accuracy claim |
| C.11 | The project has no end date, so no requirement in this document is time-boxed. | Release planning |

---

*End of SRS-001 v2.1.*
