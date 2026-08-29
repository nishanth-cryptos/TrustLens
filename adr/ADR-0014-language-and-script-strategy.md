# ADR-0014 — Language and Script Handling Strategy

| Field | Value |
|---|---|
| Status | **Accepted — Option A: MVP detection scope = English only (`en` / `Latn`)** ([OI-04](../docs/00-program/PROGRAM-001-program-charter.md#11-open-issues) resolved 2026-08-29 by Sponsor; [DEC-008](../docs/00-program/decision-log.md)) |
| Date | 2026-08-29 |
| Owner role | Chief Architect (drafting) · **scope decided by Sponsor** |
| Phase | 2 — Knowledge engineering (WP8) |
| Related | [CONF-004](../docs/00-program/conflict-register.md), [G-08](../docs/01-research/RESEARCH-005-gap-register.md), [ADR-0003](ADR-0003-rule-representation-format.md) (`language_scope`), KB-002, FR-012, NFR-009, [DEC-008](../docs/00-program/decision-log.md) |

> **Decision (2026-08-29).** The Sponsor resolved OI-04 by selecting **Option A — English only** (matching
> the pre-registered CONF-004 resolution (a)): MVP detection is English/Latn; the schemas remain
> language/script-extensible; non-English input is explicitly flagged `UNSUPPORTED`, never silently
> scored. The multilingual claim (`MP §1`) is **roadmapped**, not shipped. This unblocks and Accepts the
> ADR at English-only scope.

---

## 1. Context

`MP §1` markets TrustLens as **multilingual**; `MP §11` names "major Indian-language scenarios". But
**every trigger cue in all 30 starter rules is English** ([G-08](../docs/01-research/RESEARCH-005-gap-register.md),
[CONF-004](../docs/00-program/conflict-register.md)). Two things are already settled and must not be
re-opened:

- **The engineering posture is already language/script-extensible and honest.** Every rule carries a
  `language_scope` (`languages`, `scripts`, `on_unsupported_input: FLAG_UNSUPPORTED` — a *const*, so
  silent degradation is not selectable, NFR-009). The input envelope (KB-002) carries `language`/`script`
  as data and represents transliteration (e.g. `hi-Latn`). Seed case **A-006** proves the system emits an
  explicit `UNSUPPORTED_LANGUAGE` flag on a Hinglish scam rather than a misleading low score.
- **Resolving OI-04 is therefore a DATA change, not a schema migration** — exactly as the roadmap
  intended by reserving these fields from schema v1.0.0.

What is **not** settled is the **product-scope decision**: *which* Indian languages MVP detection
actually supports. That is [OI-04](../docs/00-program/PROGRAM-001-program-charter.md#11-open-issues),
explicitly a **Sponsor** decision.

## 2. The blocking constraint (why it cannot be resolved from the repository)

[G-08](../docs/01-research/RESEARCH-005-gap-register.md) records: **"No verified source supplies
non-English cues, so any added would be `HEURISTIC`."** Under [RESEARCH-004 §7](../docs/01-research/RESEARCH-004-evidence-matrix.md)
and the rule schema, a `HEURISTIC`/`UNSUPPORTED` rule **cannot be PUBLISHED**. So even if the Sponsor
widens language scope, **rule authoring in a new language is blocked until a dedicated research pass
obtains verified non-English official cues.** Choosing a language cannot manufacture the evidence.

This is why the repository cannot honestly close ADR-0014 by itself: the missing input is (a) a Sponsor
scope decision **and** (b), for anything beyond English, an evidence-gathering pass that does not yet
exist. Inventing cues would violate `MP §21` and the programme's evidence discipline.

## 3. The smallest explicit decision required (OI-04)

Which languages are in **MVP detection** scope?

| Option | MVP detection scope | Evidence implication | Consequence |
|---|---|---|---|
| **A ✅ SELECTED** | **English only**; schemas remain language/script-extensible; non-English input is explicitly flagged `UNSUPPORTED` | None needed — matches current verified evidence | Honest today; multilingual claim (MP §1) reframed as *roadmapped*, not shipped. Zero new work. |
| **B** | **English + Hindi** | Requires a research pass for **verified Hindi/Devanagari + Hinglish** official cues before any Hindi rule can publish | Adds a research + authoring workstream; until it lands, Hindi is FLAGGED, not detected |
| **C** | **English + selected Indian languages** | Requires a research pass per added language (Tamil/Telugu/Bengali/…); larger evidence + review burden | Largest scope; same evidence gate per language; longest path |

**Drafting note (not a decision):** the option consistent with *current* verified evidence is **A** —
B and C require evidence the repository does not have. But OI-04 assigns the choice to the Sponsor, and
the marketing claim in `MP §1` is a programme-level commitment only the Sponsor can re-scope.

## 4. What each option changes downstream
- **A:** no change — the MVP ships English detection with explicit unsupported-language flagging; CONF-004
  is resolved as "multilingual = roadmapped", and this ADR is Accepted with scope = English-only.
- **B/C:** opens a research gap (verified non-English cues) that must be closed *before* any non-English
  rule can reach `PUBLISHED`; `language_scope` entries and new cues are then added as **data**, validated
  by the existing gate, with no schema migration.

## 5. Status and next step
**ACCEPTED — Option A (English only).** The Sponsor answered OI-04 on 2026-08-29 (DEC-008). Consequences:
- MVP detection is English/Latn; the engineering (rule `language_scope`, envelope language/script, A-006
  `UNSUPPORTED` flag) already implements this — **no schema or rule change is required.**
- [CONF-004](../docs/00-program/conflict-register.md) is **RESOLVED** via its pre-registered option (a):
  multilingual is roadmapped, not shipped, and is surfaced honestly (NFR-009).
- [G-08](../docs/01-research/RESEARCH-005-gap-register.md) persists as a **future** research gap (verified
  non-English cues) but **no longer blocks** the MVP, because multilingual detection is now out of MVP scope.
- Widening scope later (to Hindi or other Indian languages) remains a **data change** gated by a
  verified-cue research pass — reopen this ADR with a new revision if/when that is commissioned.

## 6. Change history
| Version | Date | Change | Author role |
|---|---|---|---|
| 0.1 | 2026-08-29 | Drafted as Proposed/BLOCKED. Records that the engineering posture is already language-extensible (rule `language_scope`, envelope language/script, A-006 flag) and that OI-04 (which MVP languages) is a Sponsor decision gated additionally by G-08 (no verified non-English cues). Formulates options A/B/C without choosing. | Chief Architect |
| 1.0 | 2026-08-29 | **Accepted** — Sponsor resolved OI-04 as Option A (English-only MVP detection; schemas extensible; non-English flagged UNSUPPORTED). No engineering change required. CONF-004 resolved (option a); G-08 reframed as non-blocking future work. See DEC-008. | Chief Architect |
