# Internship Daily Work Log — TrustLens

| | |
|---|---|
| **Name** | *&lt;Name&gt;* · *&lt;Reg No&gt;* · *&lt;Branch&gt;* |
| **Organisation / Guide** | *&lt;Organisation&gt;* · *&lt;Guide / Faculty&gt;* |
| **Project** | TrustLens — a scam detection and reporting platform |
| **My role** | Requirements, research and system design (documentation phase) |
| **Period** | 31 July 2026 – 24 August 2026 (10 working days) |

## About the project

TrustLens checks suspicious messages — SMS, email, WhatsApp text, links and screenshots — and
tells the user whether it looks like a scam. It explains *why* it thinks so, saves the message as
proof, and creates a report the user can take to the police or a bank. It does not file any
complaint on its own.

My internship covered the planning and design part of this project, not the coding. I worked on
research, the rules the system uses to spot scams, the diagrams, and the main requirements
document (the SRS).

---

## Day 1 — 31 July 2026
### Studying the project and setting it up

**What I did.** I read through the project files and the plan I was given, and checked what was
already there versus what the plan assumed. I wrote this up as a baseline report. I also set up
three files to keep track of things as the project went on: a decision log, a risk register and a
glossary. Then I wrote two short documents (called ADRs) explaining two decisions — which tools
and versions we would use, and why we would build the AI part later instead of now.

**Files I made.** Baseline report, ADR-0001, ADR-0002, decision log, risk register, glossary.

**What I learned.** A project plan often says more than the code actually has. It helps to check
first and write down the difference. I also learned why it's useful to write down *why* a decision
was made, not just what was decided.

---

## Day 2 — 31 July 2026 (continued)
### Making the first scam list and sample data

**What I did.** I made the first list of scam types in JSON format so a program can read it, and
a small set of sample scam messages to test it against. I kept this list as a data file instead of
putting it inside the code, so a new scam type can be added later without changing any code.

**Files I made.** `scam-taxonomy.json`, `seed-corpus-v1.json`.

**What I learned.** A list written for a person and a list written for a program are different. A
program needs fixed IDs and a version number, or things get mixed up later.

---

## Day 3 — 14 August 2026
### Writing the project charter

**What I did.** I wrote the project charter — the main document that says what the project will
and won't do, what the limits are, and how the phases are split. I also made two more tracking
files: one for things we are assuming but haven't checked, and one for places where the documents
I was given contradicted each other. I also wrote down six basic rules the whole project follows,
such as: the rule engine decides, not the AI; every answer must be traceable back to its proof;
and don't call a phase finished if it isn't.

**Files I made.** Project charter, assumption register, conflict register.

**What I learned.** When two documents say different things, it's better to write the conflict
down with a number than to just pick one quietly. Otherwise the same argument comes back later.

---

## Day 4 — 14 August 2026 (continued)
### Researching official sources

**What I did.** I collected the official Indian sources the scam detection would be based on and
graded each one on how reliable it was. I found **26 sources**, of which only **11 could actually
be verified**, and I noted **6 places where sources disagreed**. I expanded the scam list into
**10 categories and 41 sub-categories**, and pulled **10 verified advisories** into a proper
format that rules could be written from.

**Files I made.** RESEARCH-001 (source list), RESEARCH-002 (scam categories), RESEARCH-003
(advisories).

**What I learned.** A source being "official" doesn't mean you can actually find and read it. Some
sources I was told existed couldn't be opened at all. Writing that down honestly was better than
pretending I had read them.

---

## Day 5 — 14 August 2026 (continued)
### Checking the research and closing Phase 1

**What I did.** I made a table grading **30 possible scam-detection rules** against the verified
sources. Only **18 had enough proof to actually be used**. The other problems went into a gap
list — **22 open items**. The biggest one: the research gave us no "this is safe" signals at all,
only "this is suspicious" ones, which is a problem for avoiding false alarms. I then wrote the
Phase 1 review and marked it **PARTIAL** instead of complete, because it genuinely wasn't
finished. I also wrote a small Python script that checks the written documents and the JSON data
files still match each other — **35 out of 35 checks pass**.

**Files I made.** RESEARCH-004 (evidence table), RESEARCH-005 (gap list), Phase 1 review,
`phase1_consistency_check.py`.

**What I learned.** It's better to close a phase as "partly done" and say what's missing than to
tick it off. Also, documents and data drift apart over time, so a script that compares them saves
trouble later.

---

## Day 6 — 15 August 2026
### Designing the rule format and writing the first rules

**What I did.** I decided (and wrote up as ADR-0003) that scam detection rules would be stored as
JSON data files checked against a schema, never written as code. This is what lets someone add a
new scam type without a programmer. I wrote the schema itself, built a list of **70 warning signs**
(each one linked back to the source it came from), and wrote the **first 7 rules** covering fake
authority calls, password stealing, fake KYC, payment scams, fake tech support and telecom scams.

**Files I made.** ADR-0003, `rule.schema.json`, indicator list, 7 rule files.

**What I learned.** A good schema makes it easy to write a correct rule and impossible to write a
broken one. That way a domain expert can add rules without understanding the code.

---

## Day 7 — 15 August 2026 (continued)
### Testing the rules with deliberately broken ones

**What I did.** A schema can't catch everything, so I wrote a second checker script. It checks
things the schema can't — for example, that every warning sign a rule mentions actually exists in
the list, and that a rule matches the reliability grade of its source. Then I wrote **23
deliberately broken rules** that the checker *must* reject, each one saying which check should
catch it. This tests the checker itself, instead of just trusting it. All **30 checks pass**. I
also updated the README and the roadmap.

**Files I made.** `validate_rules.py`, broken-rule test file, README, roadmap.

**What I learned.** This was probably the most useful thing I learned. A checker that has only
ever seen correct input hasn't really been tested. Writing the broken cases found real holes in
both the schema and the checker.

---

## Day 8 — 18–20 August 2026
### Drawing the data flow diagrams

**What I did.** I drew the system as data flow diagrams at three levels of detail.

- **Level 0** shows the outside boundary — one big process, nine outside parties, eighteen data
  flows. I deliberately put the AI service *outside* the boundary, and made the report export come
  out of the system rather than pass between two outsiders, because the user must always start the
  export themselves.
- **Level 1** breaks that one process into eight smaller ones plus six data stores (evidence,
  cases, rules, sources, analysis records, audit log).
- **Level 2** breaks the detection step into five sub-steps. The order matters here — the "this is
  actually safe" checks run *before* scoring, so safe signals can't be overruled afterwards.

I also wrote a script to convert the diagram definitions into a StarUML file.

**Files I made.** DFD level 0, 1 and 2 diagrams, `gen_mdj.py`.

**What I learned.** A diagram isn't just a picture — it can enforce a rule. Putting the AI service
outside the boundary means nobody can later assume it's part of the system.

---

## Day 9 — 23 August 2026
### Writing the SRS (versions 1.0 and 1.1)

**What I did.** I wrote the full Software Requirements Specification following the IEEE 830
standard and the Wiegers template. It covers the purpose and scope, who the users are, the
operating environment and limits, the interfaces, **ten main features** each with numbered
requirements, and the non-functional requirements like speed, safety and security. I then revised
it to version 1.1 after review.

The machine had no PDF library installed, so I wrote my own Markdown-to-PDF converter using only
Python's standard library. It produces a proper title page, contents with page numbers, a running
header, numbered sections and bordered tables.

**Files I made.** SRS v1.0 and v1.1 (Markdown + PDF), `md2pdf.py`.

**What I learned.** Writing to a standard forces every requirement to be numbered and testable —
you can't write vague sentences. I also learned to be honest about what can't be proven: we can't
measure how accurate the scam detection is, because there's no labelled real-world data set to
test against, so I wrote that down instead of claiming a number.

---

## Day 10 — 24 August 2026
### SRS v2.0 / v2.1, diagrams and the figure tools

**What I did.** I rewrote the SRS into the department's format as v2.0 and then v2.1. Requirements
were renumbered by section (like 4.1.3.1) instead of REQ-1, REQ-2, and the non-functional
requirements were put into proper tables. Nothing was lost in the rewrite. I added **Appendix B**
with the ER diagram, the three data flow diagrams and the use case diagram, each with an
explanation. I added **Appendix C** listing **11 things that are genuinely still undecided**, and
what each one blocks.

To get the diagrams into the PDF I wrote three more small tools: one to read and resize PNG
images, one to convert exported diagram PDFs into trimmed images, and one that draws figures
directly using PDF drawing commands. I also produced the DOCX version for submission.

**Files I made.** SRS v2.0 and v2.1 (Markdown, PDF, DOCX), five diagram images, `png.py`,
`prepfigures.py`, `srsfigures.py`.

**What I learned.** Reformatting a document sounds easy but it's risky — a requirement can quietly
disappear while renumbering, so I had to check each one carried over. I also learned how the PDF
format actually works, and how to solve a missing-library problem by writing just what I needed
instead of installing more things.

---

## Extra entry — 27 August 2026
### Sequence diagrams for the three main use cases

*Use this if you need an eleventh day, or swap it in for any day above.*

**What I did.** I drew three sequence diagrams showing the step-by-step order of what happens
inside the system:

- **UC-01** — a user submits a message and gets a verdict.
- **UC-02** — an analyst reviews a flagged case and makes a decision.
- **UC-03** — a knowledge editor writes a rule and a separate approver publishes it.

**Files I made.** Three sequence diagram files.

**What I learned.** These diagrams showed up timing details the other diagrams missed — for
example that permission is checked *before* any case data is loaded, and that the approver is a
genuinely separate person, not just another step for the editor.

---

## Summary of the work

| Area | What was produced |
|---|---|
| Planning documents | Charter, baseline report, phase review, and 5 tracking registers |
| Design decisions | 3 ADRs |
| Research | 26 sources graded (11 verified) · 10 categories / 41 sub-categories · 10 advisories · 30 rules graded, 18 usable · 22 open gaps |
| Rule knowledge base | 70 warning signs, 7 working rules, JSON schema, checker script, 23 broken-rule tests |
| Automated checks | 35/35 consistency checks · 30/30 rule checks |
| Diagrams | ER diagram, 3 data flow diagrams, use case diagram, 3 sequence diagrams |
| Main document | SRS up to v2.1 — 10 features, about 1,070 lines, in Markdown, PDF and Word |
| Tools written | 5 Python tools, all using only the standard library |

## What I learned overall

1. **How to write proper requirements.** Following the IEEE 830 standard taught me to write
   requirements that are numbered, specific and testable, instead of vague descriptions.
2. **Always work from evidence.** Every scam rule traces back to a real source. If the source
   couldn't be verified, the rule stayed unpublished rather than being guessed at.
3. **Be honest about status.** Phase 1 was closed as "partial", accuracy was recorded as
   unmeasured, and 11 items were left openly listed as undecided. Saying what's missing is part of
   the job.
4. **Test with bad input, not just good input.** A checker that has only seen valid data hasn't
   been tested. Writing 23 deliberately broken rules found real problems.
5. **Diagrams can enforce rules.** Where I placed things on the diagram — inside or outside the
   boundary, and in what order — locks in constraints that words alone can be ignored.
6. **Work with what you have.** With no PDF library, no image library and no database installed, I
   wrote five small tools myself rather than adding dependencies.

---

*The italic placeholders above (&lt;Name&gt;, &lt;Reg No&gt;, &lt;Branch&gt;, &lt;Organisation&gt;, &lt;Guide&gt;) are the
only things left to fill in before submitting.*
