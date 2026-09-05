# AI-001 WP2 — Provider-neutral offline AI extraction adapter

| Field | Value |
|---|---|
| Work package | P4-WP2 |
| Status | **Implemented locally — vendor-neutral offline provider seam + deterministic FakeProvider** |
| Authority | [AI-001](AI-001-ai-intelligence-layer.md) §7/§22/§31, [ADR-0007](../../adr/ADR-0007-ai-authority-and-model-strategy.md), [GATE-010](../00-program/GATE-010-phase-4-ai-design.md) |
| Baseline | Phase-3 frozen at `phase3-wp8-v1.0`; unchanged |
| Constraint | No live provider, no vendor SDK, no network, no API key, no tools, no promoted-schema change, no Phase-3 change; G-09 OPEN |

## Scope

WP2 implements **only** the provider-neutral, offline boundary through which later WPs will obtain AI-proposed
extraction data. It does **not** implement the extraction-validation pipeline (WP3), provenance/replay or the
confidence cap (WP4), or Phase-3 integration/feature flags/fallback (WP5).

## Implemented provider abstraction

`knowledge/ai/provider.py`:

- **`AIExtractorProvider`** — a `@runtime_checkable` `typing.Protocol` with a single method
  `extract(request) -> RawAIExtractionResponse`. A `Protocol` was chosen over an ABC as the smallest testable,
  structural seam: an implementation conforms by shape (no inheritance coupling), and `isinstance` conformance
  is checkable in tests. It has **no** decision authority, **no** tool/chat/`execute_prompt` surface, and **no**
  vendor-specific concepts (no `openai_response_id`/`anthropic_message_id`/`gemini_candidate_id`).
- **`AIExtractionRequest`** (frozen) — the bounded, vendor-neutral request: `request_id`, `input_id`,
  `normalized_content` (submitted-input **data**, never an instruction), and opaque `prompt_template_id` /
  `response_contract_id` pointers. It carries **no** Phase-3 decision field. `__post_init__` enforces transport
  hygiene only (non-empty `request_id`/`input_id`, string content, `MAX_CONTENT_CHARS` bound) — not WP3
  semantic validation. The optional identifier pointers are **`None` or a non-empty, non-whitespace string**;
  `""` / `"   "` are rejected, never silently coerced to `None`.
- **`RawAIExtractionResponse`** (frozen) — the **UNTRUSTED** transport output. The name preserves the trust
  boundary (it is *raw*, not `Governed`/`Validated`/`Trusted`). Payload-neutral: `raw_text` is the exact,
  opaque provider output (valid-looking JSON, empty, or malformed — WP3 parses/validates it) plus a small
  read-only vendor-neutral `metadata` map. It carries **no** decision field and **no** confidence/probability/
  score. It must not enter Phase 3.
- Typed transport failures: `AIProviderError` (base) → `AIProviderUnavailableError`
  (`AI_PROVIDER_UNAVAILABLE`), `AIProviderTimeoutError` (`AI_TIMEOUT`), `AIProviderExecutionError`
  (`AI_PROVIDER_EXECUTION_FAILED`). The `.code` is **fixed by the concrete error type** (class-level `_CODE`
  exposed through a read-only `.code` property) and is **not caller-overridable** — the constructor accepts an
  immutable `detail` string only, with no `code=` parameter. A provider failure is **never** translated into a
  TrustLens decision (never `NO_SCAM_PATTERN`/safe). The full AI failure taxonomy (schema/semantic/grounding)
  is deferred to later WPs.

## FakeProvider behavior

`knowledge/ai/fake_provider.py` — a deterministic offline `AIExtractorProvider`. Outcomes are configured
against a `request_id` via `register_response(request_id, response)` or `register_failure(request_id, kind,
detail)`; `extract` looks up **`request.request_id` only** — there is **no caller-supplied key
callback/matcher and no executable configuration path**. **For a fixed FakeProvider fixture state and an
identical request, `extract` produces equivalent transport behaviour.** A configured response is returned only
after a **transport-correlation** check (`response.request_id == request.request_id`, else
`AIProviderExecutionError`; WP2 validates transport correlation only — WP3 owns JSON/schema/semantic/
membership/grounding). Failures are stored as **immutable `_FailureSpec` snapshots** (kind + detail string),
never a stored exception instance; a **fresh** typed exception is minted on each call (same type/code/detail,
different object), so an external alias cannot mutate a later raised failure. A key may be registered **once**
(a duplicate raises `ValueError`); an unconfigured key fails closed as `AIProviderUnavailableError`. No network,
clock, randomness, filesystem, hidden mutation, or vendor SDK. Only the canonical WP2 failure kinds
(`unavailable`/`timeout`/`execution`) are accepted; arbitrary exception classes/instances are not.

## Explicit boundaries (what WP2 is NOT)

- **No live provider / vendor SDK** (no OpenAI/Anthropic/Gemini/Ollama/vLLM), **no HTTP/network**, **no API
  key**, **no environment credential variable**, **no tools**, **no standing service**.
- **No intermediate `ai-extraction.schema.json`** was created: the seam is kept payload-neutral (`raw_text`)
  because strict parsing/validation is WP3; creating the schema now would pre-empt it.
- **No feature-flag infrastructure** (WP5 owns integration/flags); AI is not enabled anywhere by default.
- **No provenance/replay artifact** (`AIExtractionResult`) — WP4 owns it; the response exposes only minimal
  vendor-neutral `metadata`.
- **No Phase-3 change**: `knowledge/runtime/*`, promoted schemas, golden cases, rules, action policy and
  taxonomy are untouched; identical governed observations still yield the identical `DetectionResult`.

## Validation

`knowledge/validation/validate_ai_provider.py` (offline, standalone; **not** wired into `run_all` — WP7 owns
canonical CI): 57 assertions covering Protocol conformance, determinism (fixed fixture state + identical
request), exact success/empty response, untrusted malformed-payload pass-through, typed provider failures +
fail-closed unconfigured key, no decision/confidence/score field, extraction-only method surface (no
chat/tool), request bounds, response immutability, and a static import/token scan proving no
network/vendor/subprocess/credential/eval dependency in `knowledge/ai`. Phase-3 regression (`run_all`) remains
green.

## Independent-review remediation (applied)

- **M1** — optional `prompt_template_id` / `response_contract_id` are `None` or a non-empty, non-whitespace
  string; `""` / `"   "` are rejected (never coerced to `None`).
- **M2** — request/response **transport correlation** is enforced: a response whose `request_id` differs from
  the request's fails closed (`AIProviderExecutionError`); the mismatched raw response is never returned.
- **M3** — the caller-supplied key callback/matcher is **removed**; lookup is `request.request_id` only, so
  FakeProvider contains no caller-supplied executable behaviour.
- **M4** — configured failures are **immutable snapshots**, not stored exception instances; each `extract`
  raises a **fresh** typed exception (same type/code/detail, distinct object); external source-map mutation
  cannot alter a stored response.
- **M5** — provider error `.code` is **fixed by the error type** and **not caller-overridable** (no `code=`
  parameter; `.code` is read-only). Only canonical failure kinds are accepted; every provider failure stays
  within the `AIProviderError` hierarchy.

## Next (P4-WP3)

Deterministic validation of the untrusted response: parse → `ai-extraction` schema → semantic → RuntimeKnowledge
indicator/taxonomy membership → grounding/reference integrity → **atomic fail-closed acceptance** → governed
`Observation`/`IndicatorObservation` mapping. WP2 hands WP3 only untrusted transport output.
