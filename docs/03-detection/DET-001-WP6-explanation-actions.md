# DET-001 P3-WP6 — Deterministic explanation + governed recommended actions

| Field | Value |
|---|---|
| Work package | P3-WP6 |
| Status | **Implemented** — explanation + governed actions only (no WP7/WP8 assembly) |
| Owner role | Detection Architect |
| Authority | [DET-001](DET-001-deterministic-detection-engine.md) §§13–17, [ADR-0006](../../adr/ADR-0006-risk-and-confidence-aggregation.md) |
| Consumes | The P3-WP5 `DecisionResult` + the immutable `RuntimeKnowledge` (+ optional validated normalized observations) |
| Produces | An `ExplanationResult` (`explanation` + `recommended_actions`); full result assembly is WP7/WP8 |
| Runtime | `knowledge/runtime/explanation.py` |
| Governed policy | `knowledge/detection/action-policy-v1.json` (`action-policy.schema.json`), bundled + pinned |
| Gate | Canonical quality-gate **check #16** (`knowledge/validation/validate_wp6_explanation.py`) |
| Last updated | 2026-09-04 |

> **Scope.** WP6 **explains** the WP5 decision; it never reconsiders it. It changes no `input_support_status`,
> `classification`, `governing_rule_id`, `decision_severity`, `matched_evidence_strength`, `risk_level`,
> `detection_confidence`, `corroboration`, rule state, suppression, or override activation. **No LLM**, no
> generative wording, no external request.

---

## 1. Boundary

`build_explanation(decision, *, rk, observations=None) -> ExplanationResult`. Minimum inputs: the WP5
`DecisionResult` + `RuntimeKnowledge`. The validated normalized observations are needed **only** to resolve
`observation_ref → span`; absent ⇒ spans are omitted (optional presentation data). `indicator_observations`
are not consumed. WP6 emits two WP6-owned blocks — `explanation` and `recommended_actions` — that populate
most of `detection-result.schema.json`; timestamps, provenance-bundle assembly, persistence and the API
envelope are **WP7/WP8**.

**`build_explanation` is a TRUST BOUNDARY, and PUBLISHED-only.** A `DecisionResult` is a plain dataclass a
caller can hand-construct, so being an instance is not proof of trustworthiness. Before rendering anything,
`_validate_explanation_input` re-validates the decision against authoritative `RuntimeKnowledge` and the WP5
invariants in **one** place (see §6): every `rule_results` entry is re-checked against the promoted
`rule-evaluation-result` schema **and** the WP5 semantic-invariant matrix (reusing the WP5 validators),
classification is cross-checked against the decision axes, governing/contributing rules must resolve and be
**PUBLISHED** (`rk.published_rule`, DET-001 §5), active overrides must resolve and be backed by a rule result,
and echoed `source_references` must match the **governed** rule's authoritative evidence. A live scam
finding/action may come only from a PUBLISHED rule. On-promotion golden cases (`live_publishable:false`, e.g. a
governing rule not yet PUBLISHED) are **not** live-executable: the public API refuses them, and a **private**
`_build_explanation(..., live=False)` renders the designed on-promotion behaviour for the golden
specification/tests only — there is **no** `allow_unpublished` production escape hatch and **no** case-id bypass
(design-expected-on-promotion ≠ currently-executable-live).

## 2. Explanation — field → deterministic source

| Field | Source |
|---|---|
| `summary`, `what_was_detected`, `why` | classification-specific templates over governed facts (including governing `rule.name`); caller-constructible WP5 `corroboration` is not trusted or used, and WP6 does not recompute it |
| `detection_confidence_reason` *(required)* | templated from the WP5 confidence band + governed rule-result reasons (verdict, override, degraded cap); no caller-supplied corroboration count |
| `matched_indicators` | `decision.matched_positive_indicators` (sorted) |
| `rules_fired` | `decision.matched_rules` (eligible unsuppressed MATCHED; sorted) |
| `overrides_applied` | `decision.active_overrides` → `rk.override().blocks_suppression_categories` |
| `suppression_considered` | `rule_results[].suppression` → `APPLIED`/`BLOCKED_BY_OVERRIDE`/`RECORDED_CONTEXT_ONLY` |
| `evidence_basis` | the **governed** rule's authoritative `evidence.source_references` (via `rk.published_rule`, mapped identically to the runtime echo) for each eligible-MATCHED rule — **exact** stored quotes; deduped and totally ordered by **full canonical identity** over all emitted fields (not `source_id` alone). The caller's echoed `source_references` must be an exact canonical set match (no missing, extra, changed, or duplicate entry; reordering is immaterial) and are never trusted as the source of facts. Non-MATCHED states do not carry or require this match-source echo. |
| `supporting_observations` | eligible-MATCHED `live_positive_provenance` refs → `{observation_ref, span?}` (no `redacted_quote`) |
| `verification_steps` | eligible/relevant rules' governed `explanation.verification_steps`, governing-first, exact-dedup, copied unchanged |
| `remaining_unknowns`, `limitations` | `decision.unknowns` / `ambiguities` + degraded + PARTIAL cap + G-09 |

**Provenance hard rule.** WP6 asserts an official fact **only** through `evidence_basis` (exact stored
`source_references` quotes). It never re-asserts `rule.explanation.plain`/`technical` as official facts
(some governed `plain` text over-states its stored quote). Classification templates: `NO_SCAM_PATTERN` says
*"No governed scam pattern was established from the evidence evaluated."* — never "safe"/"legitimate";
`INSUFFICIENT_EVIDENCE`, `UNSUPPORTED`, `ERROR` never imply benign. **PII:** no governed redactor exists, so
WP6 emits **no `redacted_quote`** and never copies `raw_span` — `supporting_observations` carry only a ref
(+ optional `span` offsets).

## 3. Recommended actions — governed policy only

Actions come **only** from the governed `action-policy-v1.json` (bundled, hashed into `content_digest`,
pinned as `component_versions.action_policy`, exposed via `RuntimeKnowledge.action_policy_entries()`). WP6
never hardcodes a mapping, never infers an action from a rule name, and never parses verification-step prose.
Trigger types: `OVERRIDE`, `RULE`, `TAXONOMY`, `NEGATIVE_INDICATOR`, `RULE_VERIFICATION_POLICY`,
`SYSTEM_CLASSIFICATION`, `SYSTEM_SUPPORT_STATUS`; `basis` ∈ `DET_001`/`RULE_VERIFICATION_POLICY`/
`GOVERNED_SOURCE`/`PROGRAM_POLICY`/`SYSTEM_STATE` (never `GOLDEN_CASE_EXPECTATION`).

**Applicability.** `OVERRIDE`/`RULE`/`TAXONOMY` fire only for `SCAM_PATTERN_DETECTED`/`SUSPECTED` and only
from **eligible unsuppressed MATCHED** decision rules (a `SUPPRESSED` or sparse `INDETERMINATE` rule never
leaks a scam action). `NEGATIVE_INDICATOR` fires whenever its governed negative is authoritatively matched —
**without changing classification** (GDC-03). `RULE_VERIFICATION_POLICY → VERIFY_INDEPENDENTLY` from an
eligible MATCHED rule with `verification_steps`, or from a **decision-relevant unresolved INDETERMINATE**
rule (ambiguities/unknowns) with `verification_steps` when the classification is `INSUFFICIENT_EVIDENCE`.
`SYSTEM_*` are keyed by authoritative support status / classification.

**Dedup / determinism.** The same `action_code` from multiple triggers → **one** `RecommendedAction` with
unioned `reason_rule_ids`/`reason_indicator_ids`/`reason_override_ids`/`evidence_refs` (each sorted),
emitted in a **fixed action-code order**. **No `priority`.** **No free-form action code.** Action codes are
instructions only — `REPORT_CYBERCRIME`/`CONTACT_*` never carry a phone/URL/`1930`/portal.

**System-state traceability.** `SEEK_HUMAN_REVIEW`, `RESUBMIT_IN_SUPPORTED_LANGUAGE` carry **no** reason ids
(no fabricated rule/indicator/override id) — traced by `input_support_status`/`classification` + the governed
policy entry + the pinned `action_policy` version + `bundle_content_digest`.

## 4. Governed policy content (v1.0.0)

OVERRIDE: `HR_OTP_DISCLOSURE_REQUEST→DO_NOT_SHARE_CREDENTIALS`; `HR_UPI_PIN_TO_RECEIVE→DO_NOT_ENTER_PIN`;
`HR_BANKING_REMOTE_ACCESS`/`HR_ACCESSIBILITY_REQUEST→DISCONNECT_REMOTE_ACCESS`;
`HR_BANKING_REMOTE_ACCESS→CONTACT_BANK`; `HR_WALLET_CONNECT_UNKNOWN→DO_NOT_CONNECT_WALLET`;
`HR_PAYMENT_UNDER_COERCION→DO_NOT_TRANSFER_MONEY`. RULE: `TL-MAL-003→DO_NOT_INSTALL_APP` (establishes an
app-install/remote request). TAXONOMY: `TAX-01-01/02/07→CONTACT_BANK`; `TAX-01/02/03/05/06/10→REPORT_CYBERCRIME`;
`TAX-03→{CONTACT_OFFICIAL_CHANNEL, PRESERVE_EVIDENCE}`.
NEGATIVE_INDICATOR: `REPORTED_SCAM_NARRATIVE→{REPORT_CYBERCRIME, PRESERVE_EVIDENCE}`. RULE_VERIFICATION_POLICY:
`VERIFY_INDEPENDENTLY`. SYSTEM: `UNSUPPORTED→{RESUBMIT_IN_SUPPORTED_LANGUAGE, SEEK_HUMAN_REVIEW}`,
`ERROR→SEEK_HUMAN_REVIEW`, `INSUFFICIENT_EVIDENCE→SEEK_HUMAN_REVIEW`. `NO_SCAM_PATTERN`: no system action.
`PROCEED_WITH_CAUTION` and `DO_NOT_DIAL_CODE` have **no** governed trigger and are never emitted in the MVP.

**`DO_NOT_TRANSFER_MONEY` is governed by exactly one trigger — `HR_PAYMENT_UNDER_COERCION`** (the coercion
override actually establishes a coerced transfer). There is **no** broad `TAX-03`/`TAX-06` → `DO_NOT_TRANSFER_MONEY`
mapping; those unratified mappings were removed. A fraud family that matches `TAX-03`/`TAX-06` yields
`REPORT_CYBERCRIME` (and, for `TAX-03`, `CONTACT_OFFICIAL_CHANNEL`/`PRESERVE_EVIDENCE`) — not transfer-money
advice — unless the coercion override is independently active. **Taxonomy ancestry** is resolved from the
governed taxonomy structure (a category node's `subcategories`), never by lexical prefix; a `TAXONOMY` action's
`reason_rule_ids` are the **matched rule ids** whose direct-or-governed-parent membership activated it — a
`TAX-*` id never appears in `reason_rule_ids`. Policy content is **26 entries**.

## 5. Bundle-provenance amendment (Phase-2, additive)

The action policy is a governed bundle member (`detection/action-policy-v1.json`): built + SHA-256'd +
digest-covered by `build_bundle.py`, member-schema-validated + version-pinned + trigger-reference-resolved
(fail-closed) by `loader.py`, indexed as `action_policy_by_id`, and exposed by `RuntimeKnowledge`.

**Manifest compatibility (`manifest_schema_version`).** Both `1.0.0` and `1.1.0` are supported, with
version-specific semantics:

* **`1.0.0` — historical / pre-WP6.** Carries **no** action policy: no `component_versions.action_policy`
  pin, no `detection/action-policy-v1.json` member, no runtime action-policy index. It loads and services all
  **WP1–WP5** replay/lookups; `rk.has_action_policy()` is `False`, `action_policy_entries()` is empty,
  `action_policy_version` is `None`. Running **WP6 on a 1.0.0 bundle fails closed** with
  `ExplanationError(code="ACTION_POLICY_UNAVAILABLE")` — never a silent empty action list.
* **A HYBRID `1.0.0` is malformed, not historical.** A `1.0.0` manifest that retains **any** WP6
  action-policy state (a pin and/or the member) is **rejected at load** — enforced by the schema (`1.0.0`
  forbids `component_versions.action_policy`) **and** a defence-in-depth loader invariant (a `1.0.0` manifest
  may carry neither the pin nor the member). The pin and the runtime index are additionally required to be
  **exactly co-present** (never "pinned but empty").
* **`1.1.0` — WP6-capable.** **Requires** the action-policy member (present, schema-valid, hash- and
  digest-covered, version-pinned, embedded-version-matched, trigger-references-resolved); `has_action_policy()`
  is `True`. 1.1 validation was not weakened to support 1.0.

The detection-result contract gains a `provenance.component_versions.action_policy` field and
`result_contract_version` is `1.1.0`. Because WP6 consults the governed policy **even to conclude that no
action applies**, **every** `1.1.0` result is action-policy-dependent: the **runtime semantic validator**
(`validate_runtime_contracts.py`) enforces that a `1.1.0` result pins `provenance.component_versions.action_policy`
as a valid semver — whether or not `recommended_actions` is empty. No existing rule/indicator/evidence
semantics change.

## 6. Fail-closed trust boundary & immutability

`_validate_explanation_input` fails closed with a typed `ExplanationError` (stable `.code`) on any impossible
or forged input, in one place, before any rendering:

* **`ACTION_POLICY_UNAVAILABLE`** — the executed `RuntimeKnowledge` pins no governed action policy (pre-WP6 /
  1.0.0 bundle).
* **`RULE_RESULT_INVALID`** — a `rule_results` entry fails the promoted `rule-evaluation-result` schema or the
  WP5 semantic-invariant matrix (illegal state↔truth pairing, `evaluation_error` misplacement, an unresolved
  matched/neutralised/negative indicator or override, malformed `live_positive_provenance`), or a duplicate
  `rule_id`.
* **`CLASSIFICATION_INCONSISTENT`** — the classification contradicts the decision axes (e.g. `NO_SCAM_PATTERN`
  with a MATCHED governing rule; a scam class with no governing rule / NONE axes; `UNSUPPORTED`/`ERROR` not
  backed by the matching support status).
* **`ROLLUP_MISMATCH`** — a producer-owned WP5 rollup (`matched_rules`, positive/negative/suppressed indicators,
  active overrides, ambiguities, unknowns, degraded state, or derived single-rule errors) differs from the exact
  canonical rollup implied by the validated `rule_results`. Tuple order is immaterial; missing, extra, or duplicate
  members fail closed before explanation/action generation.
* **`UNPUBLISHED_RULE`** — on the live path, a governing/contributing rule resolves but is not PUBLISHED.
* **`REFERENCE_INVALID` / `OVERRIDE_UNBACKED`** — a rule id / active override that does not resolve, or a
  decision-level override not backed by any `rule_results` entry.
* **`SOURCE_REFERENCE_MISMATCH`** — an eligible-MATCHED result's complete echoed `source_references` set does
  not exactly match the governed rule's authoritative evidence (missing, extra, or changed metadata/quote).
* **`INVALID_DECISION`** — the input is not a WP5 `DecisionResult`, or an axis value is out of vocabulary.

Optional presentation data (a missing observation offset) is omitted, not fatal. WP6 reads the
`DecisionResult` read-only and asserts the WP5 axes are byte-identical before/after; it never silently repairs
an impossible decision. A malformed/dangling action policy fails the **bundle load** closed (schema-invalid,
duplicate `policy_entry_id`, unknown trigger id, version mismatch, or missing/hybrid member).

## 7. Golden-case action reconciliation (v1.3.0 — decision axes unchanged)

`recommended_actions` were normalized against `phase3-wp5-v1.0` to the governed policy (a golden is a
regression oracle, not policy authority). Membership changes are: **GDC-04 +REPORT_CYBERCRIME**;
**GDC-07 +REPORT_CYBERCRIME** plus canonical reorder; **GDC-10 −DO_NOT_TRANSFER_MONEY** (the unratified broad
`TAX-06` transfer mapping was removed; only `HR_PAYMENT_UNDER_COERCION` governs that action);
**GDC-11 −PROCEED_WITH_CAUTION** with canonical `VERIFY_INDEPENDENTLY`, `SEEK_HUMAN_REVIEW` ordering; and
**GDC-13**, whose old `{PROCEED_WITH_CAUTION, VERIFY_INDEPENDENTLY}` is replaced by
`{SEEK_HUMAN_REVIEW}` because its INDETERMINATE result is sparse/not decision-relevant. Canonical-order-only
changes also apply to **GDC-01, GDC-06, GDC-12, GDC-14, and GDC-15**. No classification, severity, evidence
strength, risk, confidence, governing, or corroboration expectation changed for any case.

## 8. Limitations & next

Decision-level explanation + governed actions only; no full result assembly/provenance (WP7/WP8), no LLM,
no accuracy claim (G-09). `PROCEED_WITH_CAUTION`/`DO_NOT_DIAL_CODE`, `SCAM_PATTERN_SUSPECTED`, and
`GOVERNED_SOURCE`-basis actions are implemented/representable but not exercised by any current live golden
case. **Next = P3-WP7** (golden decision-case + corpus runner). Not started.
