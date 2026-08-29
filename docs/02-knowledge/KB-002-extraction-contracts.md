# KB-002 — Extraction Contracts and Indicator Families

| Field | Value |
|---|---|
| Document ID | KB-002 |
| Status | **Approved** — Phase 2, work package 2 |
| Owner role | Chief Architect |
| Dependencies | [KB-001](KB-001-knowledge-governance.md), [ADR-0003](../../adr/ADR-0003-rule-representation-format.md), [RESEARCH-003](../01-research/RESEARCH-003-advisory-extraction.md), [RESEARCH-004](../01-research/RESEARCH-004-evidence-matrix.md), G-07 negative-indicator library, scam taxonomy v2.0 + dimensions-v1 |
| Feeds | DET-001 (Phase 3), AI-001 (Phase 4), DATA-001 / ADR-0004 (storage), ADR-0014 (language) |
| Last updated | 2026-08-29 |

---

## 1. Purpose

KB-002 defines the **stable, versioned contract between raw TrustLens input and the deterministic
detection knowledge layer.** It is the boundary WP2 was asked to fix: the rule engine must never
consume arbitrary model prose — there must be a *typed* seam. KB-002 specifies that seam and the
transformations that reach it. It does **not** build the production extractor (NLP/LLM/OCR/URL
reputation) — that is later-phase implementation work. It defines *what the extractor must emit and
what it may never emit.*

KB-002 is to extraction what [KB-001](KB-001-knowledge-governance.md) is to governance: a **logical**
contract. Physical storage stays [ADR-0004](../../adr/README.md) (unresolved); language/script policy
stays [ADR-0014](../../adr/README.md)/OI-04 (unresolved). Nothing here assumes either.

## 2. The extraction pipeline

```
RAW INPUT
   │   (input-envelope.schema.json)
   ▼
INPUT ENVELOPE ── raw + normalized text, channel, extracted primitives (urls/phones/upi/amounts), privacy
   │   normalisation
   ▼
NORMALIZED OBSERVATIONS ── typed, span-anchored facts with POLARITY, ATTRIBUTION, actor/action/target,
   │                        payment_direction   (observation.schema.json ; url-observation.schema.json)
   │   indicator extraction
   ▼
INDICATOR OBSERVATIONS ── matched indicator_id + confidence + observation_refs   (indicator-observation.schema.json)
   │   projection:  signal_set = { io.indicator_id : io.matched == OBSERVED }
   ▼
RULE ENGINE  (existing rule_runner — UNCHANGED)
   ▼
EXPLAINABLE RESULT
```

The four contracts live in `knowledge/schemas/`; the family map, golden fixtures and coverage matrix
in `knowledge/indicators/` and `knowledge/extraction/`; the cross-file checks in
`knowledge/validation/validate_extraction.py` (the 8th validator).

**Backward-compatibility invariant.** The current `rule_runner` consumes a flat *set* of indicator
IDs (`expected_indicators ∪ expected_negative_indicators`). KB-002 makes that set the **projection**
of the indicator-observation layer: `{ io.indicator_id : io.matched == OBSERVED }`. The extraction
contract is therefore a strict, backward-compatible **superset** of today's hand-declared tags — the
rule engine, rules, taxonomy and negative library are untouched.

## 3. The input envelope (STEP 2)

`input-envelope.schema.json` — the canonical, versioned carrier of a submission. Modalities:
`TEXT · SMS · CHAT_MESSAGE · EMAIL · URL · OCR_TEXT · SCREENSHOT_DERIVED_TEXT · DOCUMENT_TEXT ·
USER_NARRATIVE` (reserved, not all implemented). It preserves, where available: `input_id`,
`input_type`, `source_channel` (a `CH-*` dimension term or `UNKNOWN`), `raw_text`/`normalized_text`,
`language`/`script` (+ detection), `timestamp`, `actor`/`recipient` parties (with `claimed_identity`),
extracted primitives (`urls`, `phone_numbers`, `email_addresses`, `upi_ids`, `payment_handles`,
`amounts`, `codes`), `attachments`, `thread`, `user_supplied_context`, `provenance`, and `privacy`.

- **Data minimisation.** A field being expressible is not licence to populate it. `privacy.redaction`
  records the *class and span* removed, never the value; a `minimization_profile` names the policy.
  Retention/legal basis is OI-05, out of WP2 scope.
- **Language extensibility (do not resolve OI-04).** `language`/`script` are carried as data and MUST
  NOT be assumed English-only; the *rule* layer flags unsupported input. Resolving ADR-0014 stays a
  data change, not a schema migration.
- **`normalized_text` is the offset frame** for every observation span, so the chain input → span →
  observation stays traceable.

## 4. The normalized observation model (STEP 3)

`observation.schema.json` — a typed derived fact standing strictly between raw input and indicators.
Types: `ENTITY · ACTION · CLAIM · REQUEST · THREAT · PROMISE · IDENTITY_ASSERTION · PAYMENT_CONTEXT ·
DEVICE_ACTION · LINK_ACTION · AUTHENTICATION_ACTION · TEMPORAL_PRESSURE · RELATIONSHIP_CONTEXT`.

Each observation carries the equivalent of: `observation_id`, `observation_type`, `canonical_value`,
`raw_span`, `normalized_value`, optional `offsets`, `confidence`, `source_input_id`, extractor
provenance, `language`/`script`, and `status`. **An observation carries no indicator, no rule
reference and no verdict** — downstream layers add those. The original span always remains traceable
(via `raw_span` even when exact `offsets` are unavailable), so no rule depends on an opaque confidence
score alone.

### 4.1 Negation and reported speech (STEP 6 — critical)

The contract distinguishes the three cases WP2 named, structurally rather than by substring lists:

| Utterance | `polarity` | `attribution` | `mood` | Projects to |
|---|---|---|---|---|
| "Share your OTP." | AFFIRMED | FIRST_PARTY | DIRECTIVE | **live** `CREDENTIAL_REQUEST_OTP` |
| "Never share your OTP." | NEGATED | FIRST_PARTY | DIRECTIVE | `NEGATED_CREDENTIAL_REQUEST` (no positive) |
| "The scammer asked me to share my OTP." | AFFIRMED | REPORTED | DESCRIPTIVE | `REPORTED_SCAM_NARRATIVE` (no positive) |
| "Fraudsters may ask for your OTP." | — | HYPOTHETICAL | DESCRIPTIVE | `EDUCATIONAL_CONTENT` (no positive) |

**Only a `FIRST_PARTY` + `AFFIRMED` + `DIRECTIVE` observation projects to a LIVE positive indicator.**
This gives the G-07 suppression layer exactly the information it needs to make deterministic decisions
— it is why an official awareness post (B-013) emits *no* live positive rather than emitting one and
relying on `EDUCATIONAL_CONTENT` to "undo" it, and why the decoy (S-I) still fires because its live
directive is `FIRST_PARTY`/`AFFIRMED`. No fragile exclusion list is used.

### 4.2 Actor / action / target frame (STEP 7)

`REQUEST`/`ACTION`/`PAYMENT_CONTEXT` observations carry a frame — **who** is asking (`actor.claimed_identity`,
`actor.verified` default UNKNOWN), **what** (`action.type` keyed to a `UA-*`/`TM-*` term), **to/for what**
(`target.amount`/`currency`/`recipient_label`/`credential_kind`/`instrument`), under **which pretext**
(`pretext.kind`) and with **which pressure** (`pressure.kind`/`threat_of` keyed to `SE-*`). So
*"RBI officer says transfer ₹50,000 now to avoid account freeze"* is representable as
`actor=AUTHORITY_LAW_ENFORCEMENT · action=MAKE_PAYMENT · target.amount=50000 · pretext=ACCOUNT_SECURITY
· pressure=THREAT(ACCOUNT_BLOCK)`. This lets DET-001 later reason over combinations, not keywords.

### 4.3 Payment direction (STEP 8)

`payment_direction ∈ { USER_PAYS, USER_RECEIVES, UNKNOWN_DIRECTION }`, default `UNKNOWN_DIRECTION`.
**Direction is never inferred from the presence of currency or UPI terminology.** When the text does
not settle it, the value is `UNKNOWN_DIRECTION` and `status` SHOULD be `AMBIGUOUS`. `USER_RECEIVES` +
a PIN/OTP prompt is the receive-fraud contradiction (RESEARCH-003 ADV-003 #1, → `RECEIVE_FRAMING`);
`USER_PAYS` to a named merchant is legitimate outbound (→ `PAY_MERCHANT_DIRECTION`). Fixtures XF-04 /
XF-05 / XF-13 exercise all three.

## 5. The indicator observation contract (STEP 5)

`indicator-observation.schema.json` — the typed boundary the rule engine consumes. Fields:
`indicator_id`, `indicator_version`, `polarity`, `matched`, `confidence`, `observation_refs`,
`supporting_spans`, `input_id`, `language`/`script`, `extraction_method`, `family_ref`,
`review_required`, and extractor `provenance`.

**An extractor emits indicator observations; it MUST NOT declare a scam, risk, severity or verdict.**
The schema forbids it structurally (`additionalProperties:false`, no such field) and
`validate_extraction.py` additionally rejects any of `verdict/risk/risk_score/severity/is_scam/
decision/label/classification/…` by name (defence in depth), while still permitting `confidence.score`
as *extraction* confidence. Final risk determination belongs to the rule/detection layer (CONF-001).

## 6. Indicator families (STEP 4)

`indicator-families-v1.json` — **28 families** that reorganise the **63 positive indicators** into
reusable, mechanism-level groups (the file the registry names in `superseded_by`). Each family
declares: `family_id`, `name`, `description`, `parent_evidence_class`, `observation_inputs`,
`indicator_outputs`, `applicable_dimensions`, `negative_interactions`, `hard_risk_overrides`,
`language_considerations`, `confidence_requirements`, `known_ambiguities`, `examples`,
`counterexamples`, `version`, `status`.

- **Partition invariant.** The union of `indicator_outputs` equals the positive-indicator set, with no
  indicator in two families — enforced by `validate_extraction.py`. Families **add an organising
  layer**; they do not change indicator IDs, polarity, evidence class or strength (the registry stays
  the source of truth). Negatives remain governed by the G-07 library; families only *reference* the
  negatives they interact with.
- **Granularity.** `parent_evidence_class` preserves the clean 8-class canonical grouping while the
  families give finer mechanism-level splits (e.g. `FAM-REMOTE-ACCESS`, `FAM-ACCESSIBILITY-PERMISSION`,
  `FAM-CALL-FORWARDING`, `FAM-WALLET-CONNECTION` are distinct, each mapping to its own hard-risk
  override).

## 7. URL / domain observation contract (STEP 9)

`url-observation.schema.json` — structural URL facts a parser can derive (`scheme`, `hostname`,
`registered_domain`, `path`, flags `shortened/obfuscated/punycode/ip_literal`) plus `claimed_brand`.
The judgement fields — `domain_matches_claimed_brand`, `allowlist_result`, `reputation_result` — are
**reserved** and default to `UNKNOWN` / `NOT_EVALUATED`. **No reputation is invented:** absence of a
reputation service is `NOT_EVALUATED`, never `CLEAN` and never `MALICIOUS`. `validate_extraction.py`
rejects any WP2 artefact that sets a committed assessment. Consequently `LOOKALIKE_DOMAIN` /
`FAKE_VERIFICATION_SITE` are today heuristic/structural only; reliable detection needs the Phase-6
intelligence adapter (ADR-0012), recorded in the coverage matrix as `URL_BRAND_REPUTATION`.

## 8. Confidence model (STEP 10)

Extraction confidence — "how sure are we the text requests an OTP" — is **separate** from rule
confidence — "how strong is the evidence this is fraud". It is **categorical by default**
(`level ∈ HIGH/MEDIUM/LOW`) with an **optional advisory numeric** `score ∈ [0,1]` (`method` records
which). The numeric is explicitly **not** a fraud probability and is never aggregated into a finding;
probabilistic risk scoring is deferred to DET-001/CONF-001. The rule engine currently uses *presence*
(`matched == OBSERVED`), not the number.

## 9. Extractor provenance (STEP 11)

Every derived object records how it was produced: `extractor_id`, `extractor_type`, `extractor_version`,
`config_ref`. Reserved types: `DETERMINISTIC_PATTERN · PARSER · NER_MODEL · CLASSIFIER · LLM · VISION ·
OCR · USER_SUPPLIED · SYSTEM_METADATA` (+ `COMPOSED` for indicator observations derived from multiple
observations). This is **provenance vocabulary, not permission to implement all of them now.** The
chain input → exact span → observation → indicator → rule → evidence → result is fully expressible.

## 10. UNKNOWN / AMBIGUOUS handling (STEP 12)

Observations and indicator observations share `status ∈ { OBSERVED, NOT_OBSERVED, UNKNOWN, AMBIGUOUS,
NOT_APPLICABLE }`. **Missing evidence is UNKNOWN, never benign; ambiguity stays ambiguity.** Only
`OBSERVED` enters the rule engine's signal set. `NOT_OBSERVED` records an affirmative absence (useful
for negative context and explanation); `AMBIGUOUS` (e.g. unresolved payment direction) may set
`review_required`.

## 11. Rule-extraction coverage matrix (STEP 15)

`rule-extraction-coverage-v1.json` maps every rule file to the extraction contract it needs:
required evidence classes, indicator families, observation types and positive indicators; negative-
context dependencies (explicit `suppressed_by`, family-scoped suppressors, directional neutralisers);
applicable hard-risk overrides; and an **extractability** verdict.

**Scope — 26 matrix entries = 25 starters + TL-SUP-001.** The matrix covers the **25 encoded starter
rules** (`kind = COMPOSITE`) **plus `TL-SUP-001`**, the non-starter SUPPRESSION-infrastructure rule
that consumes negative indicators. That is why the file has **26 entries** while the starter set is 25.

| Verdict | Meaning | All 26 | 25 starters | TL-SUP-001 |
|---|---|---|---|---|
| `CURRENTLY_EXTRACTABLE` | producible from the defined text input contract by a reference extractor | 23 | 22 | 1 |
| `PARTIAL_REQUIRES_FUTURE_EXTRACTOR` | discriminating signal needs a capability beyond the MVP text contract | 2 | 2 | 0 |
| `UNOBSERVABLE` | TrustLens cannot observe what the rule needs (rule is DEFERRED) | 1 | 1 | 0 |

The two partials are **TL-JOB-003** (needs `THREAD_CONTEXT` to observe the deposit→blocked-withdrawal
chain) and **TL-MAL-002** (needs `DEVICE_STATE` to confirm an Accessibility grant vs its text request);
the one unobservable is **TL-PAY-003** (`PAYEE_IDENTITY`, `blocked_by INPUT_MODALITY`); `TL-SUP-001` is
the +1 `CURRENTLY_EXTRACTABLE` beyond the 25 starters. The matrix is **derived** from the rules +
families + library and re-checked by the validator, so it cannot drift.

## 12. What WP2 deliberately does NOT do (STEP 16)

No production LLM prompts, vector DBs, embedding classifiers, full OCR, URL/phone reputation services,
browser/mobile integrations, or NLP pipelines. Those are Phase 9 / later. The reference `DETERMINISTIC_PATTERN`
extractor named in the fixtures is illustrative provenance, not an implementation. **Extraction never
emits a verdict; the rule/detection layer decides risk.** Phase 3 must not begin without approval.

## 13. Machine-enforced vs human-review (KB-001 §9 alignment)

**Machine (validate_extraction.py):** schema validity of all four contracts and every fixture object;
indicator resolution + polarity agreement + no DEPRECATED emission; the family partition; family
dimension/negative/override references; fixture cross-refs and projection equality; the verdict-key
ban; the URL-assessment reservation; coverage-matrix agreement with live rules. **Human:** whether a
proposed observation type or family is *sound*; safeguarding scope (TAX-11 stays out of extraction);
language-policy (ADR-0014) and storage (ADR-0004) decisions.

## 14. Versioning and storage boundary

All WP2 artefacts follow KB-001 §8 semantic versioning (`envelope_version` const per contract
revision; `families_version`/`fixtures_version`/`coverage_version` semver). The contracts are
storage-agnostic (ADR-0004): they are logical shapes, equally serialisable to files (as now), a
relational schema or a graph.

## 15. Change history

| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-08-29 | Initial KB-002. Four contract schemas (envelope, observation, url-observation, indicator-observation); 28 indicator families partitioning the 63 positives; negation/reported-speech, actor/action/target and payment-direction models; confidence and provenance models; UNKNOWN/AMBIGUOUS handling; 15 golden fixtures; 26-entry extraction-coverage matrix (25 starters + TL-SUP-001); the 8th validator. Rule engine, rules, taxonomy and negative library unchanged. | Chief Architect |
