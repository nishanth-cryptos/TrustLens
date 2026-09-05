# AI-001 WP5 — Optional AI integration with the deterministic engine

| Field | Value |
|---|---|
| Work package | P4-WP5 |
| Status | Builder implementation; awaiting independent review; stop without commit |
| Baseline | P4-WP4 merge `12da3c659ea65ce4120323caed4c62e4f4c810d3` |
| Semantic baseline | `phase3-wp8-v1.0`; Phase-3 files and promoted schemas unchanged |
| Authorities | [AI-001](AI-001-ai-intelligence-layer.md), [WP2](AI-001-WP2-provider-adapter.md), [WP3](AI-001-WP3-response-validation.md), [WP4](AI-001-WP4-containment-provenance.md), [ADR-0007](../../adr/ADR-0007-ai-authority-and-model-strategy.md), [GATE-010](../00-program/GATE-010-phase-4-ai-design.md) |
| Claim boundary | Offline integration/fixture behavior only; G-09 OPEN |

WP5 connects the existing extraction pipeline to the unchanged public
`knowledge.runtime.evaluate_detection_from_governed` endpoint. AI cannot directly set, override, or bypass
decision semantics. Validated AI-derived observations can indirectly change the deterministic result because
the engine receives them as governed input. No second decision engine or decision schema is introduced.

## Public API and default behavior

Import the integration explicitly from `knowledge.ai.integration`. The existing `knowledge.ai` exports and
WP2–WP4 modules are unchanged; importing the extraction package alone does not load the Phase-3 runtime.

```python
from knowledge.ai.integration import AIIntegrationPolicy, evaluate_with_optional_ai

# rk, host_indicator_observations, host_observations and trusted metadata are host-owned.
outcome = evaluate_with_optional_ai(
    rk, host_indicator_observations, host_observations,
    evaluation_id="EVAL-1", evaluation_timestamp="2026-09-05T10:00:00Z", input_id="IN-1",
    language=["en"], script=["Latn"], input_support_status="SUPPORTED",
)
result = outcome.detection_result
```

The frozen `AIIntegrationPolicy` defaults to `extraction_enabled=False` and accepts only a real boolean.
No environment read, mutable global setting, generated ID/timestamp or hidden auto-enable exists.
OFF skips provider extraction, WP3 AI validation, WP4 request/extraction preparation and AI mapping.
It executes the direct deterministic path over the captured host data.

For an enabled offline run, add `policy=AIIntegrationPolicy(extraction_enabled=True)`, a host-configured
`FakeProvider` through the existing provider-neutral seam, host `AIConfiguration`, `normalized_content`,
`request_id` and `run_id`. The integration does not instantiate or select a live provider. Tests use only
Fake/Fixture providers. Credentials, external access, tool definitions and provider SDKs are absent.

## Host snapshot and support-first policy

The function accepts the Phase-3 endpoint's governed observation iterables and explicit metadata:
`evaluation_id`, `evaluation_timestamp`, `input_id`, `language`, `script`, `input_support_status` and
`whole_evaluation_errors`. Observation/error iterables are consumed once. Language/script retain Phase 3's
sequence contract. A strict WP4 canonical copy captures all nested host material before any optional call.
Non-string object keys, non-finite numbers, bytes, sets, opaque objects, cycles and out-of-bound material
raise the fixed `AIIntegrationInputError`. These host errors are outside fallback handling.

The frozen artifact contains exactly three entries:

```text
observations
indicator_observations
evaluation_context
```

`evaluation_context` contains all seven explicit host metadata fields above. This retains the timestamp,
language/script, support and trusted error context required to reproduce the complete evaluation. No context
field is derived from submitted content or response metadata. Mutating caller-owned lists/maps during a
provider call cannot change the captured baseline or trusted metadata.

Enabled AI is bypassed when support is not `SUPPORTED`/`PARTIALLY_SUPPORTED`, when trusted whole-evaluation
errors are present, or when host language/script are not exactly `en`/`Latn`. Metadata is passed unchanged to
Phase 3, which remains responsible for support-first decisions and invalid-host-context rejection. For example,
a whole-evaluation error accompanying a non-ERROR support state still raises the existing runtime error.
AI does not expand language support or turn unsupported evidence into a safe finding.

## Enabled pipeline and governed mapping

1. WP4 `prepare_ai_request` separates host config/pointers from submitted content.
2. The provider-neutral `extract` seam supplies untrusted transport data.
3. WP3 `validate_ai_extraction` checks response/request/input correlation, schema, forbidden fields,
   membership against the same `RuntimeKnowledge`, references and exact grounding.
4. WP4 `prepare_ai_extraction` assigns confidence and creates its sealed provenance audit from actual material.
5. WP5 maps every validated proposal once, validates the AI-only governed contribution through the existing
   public `runtime.build_validated_context` validation boundary, and appends it to the captured baseline.
6. WP4 replay pinning computes digests over the exact immutable combined artifact.
7. One detached JSON copy is passed to the unchanged public Phase-3 evaluation endpoint.

The AI-only preflight applies the existing promoted schema/reference rules, including rejecting an OBSERVED
indicator backed by a NOT_OBSERVED/NOT_APPLICABLE observation. Its returned context is not used to bypass the
public evaluation boundary; Phase 3 validates the final combined governed dictionaries itself. No rule,
suppression, aggregation, explanation or action policy runs during mapping.

| Mapped record | Fields |
|---|---|
| Normalized observation | Deterministic `observation_id`; original type, source ID, status, polarity, attribution, mood; optional canonical value; exact `{start, end}` offsets; WP4 categorical confidence and provenance |
| Indicator observation | Validated indicator ID, polarity, matched state, input ID; remapped supporting refs; WP4 confidence and provenance; `extraction_method=LLM`; WP4 `review_required` fact |

Observation IDs are `AI-OBS-` plus the canonical SHA-256 of `{run_id, proposal_id}`. These are schema-valid
71-character IDs; the same run/proposal produces the same ID, while either identity changing changes its
digest. The model cannot choose the final ID directly. A local explicit proposal-ID-to-governed-ID map rewrites
every indicator reference. The normal collision where a model proposes an existing host ID is harmless because
the model ID is hashed. An actual generated-ID collision with a baseline ID rejects the whole AI contribution;
nothing is overwritten. Incompatible cross-input augmentation likewise rejects the optional contribution.

Mapping uses WP4's levels and reason-derived review fact without recalculating confidence: UNKNOWN/AMBIGUOUS
are LOW, other validated structural states are MEDIUM, and LOW implies review required. No HIGH or numeric
confidence is introduced. Provenance comes from the existing descriptor: `extractor_type=LLM`,
`extractor_id=ai-extraction-adapter`, `extractor_version=1.0.0` and the content-addressed configuration reference.
WP3's transient `evidence_excerpt` is absent and no `raw_span` is invented. Credential masking remains the WP4
policy boundary; WP5 does not transform normalized text or weaken grounding offsets.

Baseline records come first, followed by all AI records in their validated order. No baseline replacement,
semantic merge, silent deduplication or partial AI salvage occurs. Repeated indicator assertions remain
separate occurrences. A successful empty extraction adds zero records and yields the same authoritative
result as the baseline; it carries an accepted-run audit, not a safety inference.

## Atomic fallback and authoritative failures

| Operational reason | Condition |
|---|---|
| `AI_DISABLED` | Default/explicit feature flag OFF; no AI attempt |
| `AI_HOST_NOT_EVALUABLE` | Support/error/language gate bypasses optional extraction; no AI attempt |
| `AI_PROVIDER_FAILED` | Missing provider or typed WP2 transport failure |
| `AI_RESPONSE_REJECTED` | Invalid transport response type or typed WP3 rejection |
| `AI_GOVERNANCE_FAILED` | Typed WP4 request/config/provenance/replay-pinning failure |
| `AI_MAPPING_FAILED` | Atomic AI mapping/schema/reference/collision refusal |

The vocabulary is the closed `AIFallbackReason` enum, never arbitrary exception text. On a typed optional
failure the integration discards every AI record and uses the original frozen baseline. No AI success audit
or replay snapshot is returned for a discarded contribution. `ai_attempted` means the optional pipeline was
entered, which can include a configuration failure before a provider call. These operational reasons do not
mean fraud, benignness or whole-evaluation failure.

The final `evaluate_detection_from_governed` call is outside every optional-path exception handler. Runtime
failure propagates and is never retried or presented as successful AI fallback. Malformed host data and
unexpected provider/programming exceptions also propagate. Optional AI failures never set support to ERROR
or inject a whole-evaluation diagnostic, and never alter language, script or evaluation identity.

## Outcome and exact consumed-artifact replay

The frozen, sealed `AIIntegrationOutcome` contains the authoritative `detection_result`, `ai_attempted`,
closed `fallback_reason`, immutable `governed_artifact` and optional WP4 `replay_snapshot`. Its `ai_used`,
`ai_extraction_result` and canonical `governed_artifact_digest` are derived properties. Its constructor cannot
be used to supply an independent artifact digest. `as_dict()` returns detached copies. No classification,
risk, decision confidence or recommended actions are duplicated as integration-owned fields.

On success, the exact artifact retained by `AIReplaySnapshot` supplies the observation collections and
metadata thawed for the engine call. There is no post-digest remapping, content reconstruction or baseline
re-read. The outcome and snapshot therefore bind the sealed AI run to the actual combined material supplied
to Phase 3. The same artifact includes all deterministic records, accepted AI records and host metadata.
The WP4 `AIExtractionResult` itself is unchanged and its own `governed_artifact_digest` remains `None`;
WP5 establishes the consumed-artifact relationship through this separate integration outcome/snapshot.

Replay pins the run/evaluation/config identities, actual `rk.content_digest`, runtime `ENGINE_VERSION` and
`DEFAULT_PROFILE.profile_id`. The runtime endpoint does not permit a caller-selected profile, so WP5 does
not add one. Given the same pinned bundle and engine version/profile, `prepare_replay`/verified restoration
returns the immutable artifact; a detached copy of its observation arrays and `evaluation_context` can be
passed directly to the Phase-3 endpoint with no provider argument or AI recall. Tampering fails with the
unchanged WP4 typed replay integrity error. Verification is relative to a trusted stored pin, as documented
in WP4; no new authentication claim is made.

## Builder validation and limitations

`knowledge/validation/validate_ai_integration.py` builds/loads the existing bundle in a temporary directory.
It checks all 15 golden fixtures for complete flag-OFF result equality, stage-bypass sentinels, real governed
mapping and reference/collision behavior, exact fallback equality, support-first preservation, host-data
mutation isolation, runtime failure propagation, exact engine-argument/replay equality, immutability and
security boundaries. The synthetic accepted-AI fixture augments a host verification pretext with an AI OTP
request. It changes `INSUFFICIENT_EVIDENCE` to `SCAM_PATTERN_DETECTED` solely by supplying governed data to
the unchanged deterministic engine. This proves wiring only.

Run with the existing repository `.venv/bin/python`:

```text
.venv/bin/python knowledge/validation/validate_ai_integration.py
.venv/bin/python knowledge/validation/validate_ai_governance.py
.venv/bin/python knowledge/validation/validate_ai_extraction.py
.venv/bin/python knowledge/validation/validate_ai_provider.py
.venv/bin/python knowledge/validation/run_all.py
.venv/bin/python -m py_compile knowledge/ai/integration.py knowledge/validation/validate_ai_integration.py
git diff --check
```

Also run a clean-process import smoke, the requested security-name searches and an explicit whitespace check
for untracked files. WP2 automatically adds two static assertions for the new AI module. WP7 retains ownership
of canonical AI CI wiring; `run_all.py` and `ci_selftest.py` are untouched.

There is no live provider, vendor SDK, API key, network/tool access, Phase-3/schema/knowledge change, WP6,
Phase 5 or UI implementation. G-09 remains OPEN. No accuracy, precision, recall, false-positive/negative rate,
AI effectiveness, improved detection rate or production-readiness claim is supported by these fixtures.
Independent review belongs to a separate session. Stop without commit.
