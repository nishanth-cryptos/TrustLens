// Evaluation and result client (accepted API v1 operations only: createEvaluations, getEvaluation, listCaseEvaluations,
// getDetectionResult) and the UX-003 result presentation rules. Every label, meaning, instruction and announcement below is
// the exact governed text from contracts/ux/ux-result-v1.json. The client never derives an axis, a score, a percentage or a
// verdict: it renders only a successful, validated response for the evaluation and view it asked for, and withholds anything
// incomplete, contradictory or for another view. NO_SCAM_PATTERN is never presented as safe.
import { ApiFailure, Fetch, MESSAGES, Result, create, get, randomKey } from "./cases";

export const MAX_STATUS_POLLS = 10;              // approved T09 value: status polling is bounded
export type ApiState = "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";
export type EvaluationView = {
  evaluation_id: string; case_id: string; submission_id: string; origin: string; predecessor_evaluation_id: string | null;
  state: ApiState; result_availability: string; requested_at: string; completed_at: string | null;
  failure: { failure_class: string; reason: string; retry_guidance: string } | null;
  ai_usage: { requested: boolean; enabled_by_policy: boolean; used: boolean; fallback_reason: string | null };
  provenance: { engine_version: string; result_contract_version: string; bundle_content_digest: string; bundle_version: string;
                evaluation_profile_id: string; evaluation_timestamp: string } | null;
};
export type RuleReference = { rule_id: string; rule_version: string; source_references?: string[] };
export type ResultView = {
  evaluation_id: string; result_contract_version: string; result_digest: string; view: "STANDARD" | "DETAILED";
  input_support_status: string; language: string[]; script: string[]; classification: string; decision_severity: string;
  matched_evidence_strength: string; risk_level: string; detection_confidence: string; degraded: boolean;
  governing_rule?: RuleReference | null; matched_rules: RuleReference[]; explanation: { summary: string; evidence_basis?: string[] };
  recommended_actions: { action_code: string }[]; limitations: string[]; unknowns: string[]; ambiguities: string[];
  rule_results?: unknown[];
  provenance: { engine_version: string; result_contract_version: string; bundle_content_digest: string; bundle_version: string;
                evaluation_profile_id: string; evaluation_timestamp: string };
  not_an_official_determination: boolean; absence_of_finding_notice?: string | null;
};

// ---- governed presentation text (UX-003, EXACT_GOVERNED_TEXT)
export const SECTION_TITLES = {
  A: "What TrustLens concluded", B: "Input support and language", C: "Severity, evidence strength, risk band and confidence",
  D: "Why", E: "Governing and matched rules", F: "Sources and provenance", H: "Unknowns, ambiguities, limitations and degraded evaluation",
  I: "Recommended next steps", J: "How this result was produced", K: "Interpretation notice",
};
export const CLASSIFICATIONS: Record<string, { label: string; meaning: string }> = {
  NO_SCAM_PATTERN: { label: "No governed scam pattern established",
    meaning: "No governed scam pattern was established from the evidence evaluated. This is not a determination that the content is safe or legitimate." },
  INSUFFICIENT_EVIDENCE: { label: "Insufficient evidence to conclude",
    meaning: "TrustLens could not reach a conclusion from the evidence evaluated. This is not a determination that the content is safe." },
  SCAM_PATTERN_SUSPECTED: { label: "Scam pattern suspected",
    meaning: "A governed scam pattern matched with low detection confidence; the uncertainty shown with this result remains." },
  SCAM_PATTERN_DETECTED: { label: "Scam pattern detected",
    meaning: "A governed scam pattern matched the evidence evaluated. This is not a legal finding, an official determination or proof of guilt." },
  UNSUPPORTED: { label: "Not evaluated: unsupported input",
    meaning: "The input is outside the supported detection scope and was not evaluated. This is not a determination that the content is safe." },
  ERROR: { label: "Evaluation error: no conclusion",
    meaning: "The evaluation stopped without reaching a conclusion. This is not a determination that the content is safe." },
};
export const INPUT_SUPPORT: Record<string, { label: string; meaning: string }> = {
  SUPPORTED: { label: "Supported input", meaning: "The input was within the supported detection scope and was evaluated." },
  PARTIALLY_SUPPORTED: { label: "Partially supported input",
    meaning: "Part of the input could not be used; only the available evidence was evaluated and the gap is listed with this result." },
  UNSUPPORTED: { label: "Unsupported input", meaning: "The input is outside the supported detection scope and was not evaluated." },
  INSUFFICIENT_INFORMATION: { label: "Insufficient information",
    meaning: "The input was supported but too little could be observed to evaluate any governed pattern." },
  ERROR: { label: "Evaluation error", meaning: "The input could not be evaluated safely; no conclusion was reached." },
};
export const AXES: { field: "decision_severity" | "matched_evidence_strength" | "risk_level" | "detection_confidence"; label: string; question: string;
                     values: string[] }[] = [
  { field: "decision_severity", label: "Severity if genuine", question: "If the pattern is genuine, how harmful would it be?",
    values: ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"] },
  { field: "matched_evidence_strength", label: "Matched evidence strength (feeds the risk band)",
    question: "How strong is the evidence that actually matched?", values: ["NONE", "WEAK", "MODERATE", "STRONG"] },
  { field: "risk_level", label: "Risk level (band)", question: "What is the exposure band for this submission?",
    values: ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"] },
  { field: "detection_confidence", label: "Detection confidence (not a probability)",
    question: "How much does TrustLens trust its own analysis of this submission?", values: ["NOT_APPLICABLE", "LOW", "MEDIUM", "HIGH"] },
];
export const ACTIONS: Record<string, string> = {
  DO_NOT_SHARE_CREDENTIALS: "Do not share passwords, one-time codes, PINs or other credentials in response to this message.",
  DO_NOT_ENTER_PIN: "Do not enter a payment or card PIN in response to this message.",
  DO_NOT_TRANSFER_MONEY: "Do not transfer money in response to this message.",
  DO_NOT_INSTALL_APP: "Do not install an app or grant device access requested by this message.",
  DO_NOT_CONNECT_WALLET: "Do not connect a crypto wallet as requested by this message.",
  DO_NOT_DIAL_CODE: "Do not dial a code requested by this message.",
  DISCONNECT_REMOTE_ACCESS: "End any remote-access or screen-sharing session started at this message's request.",
  VERIFY_INDEPENDENTLY: "Verify the claim independently through a channel you already trust, not one supplied in this message.",
  CONTACT_BANK: "Contact your bank through a channel you already trust.",
  CONTACT_OFFICIAL_CHANNEL: "Contact the organisation concerned through an official channel you find independently.",
  REPORT_CYBERCRIME: "Consider reporting this to the appropriate cybercrime reporting authority.",
  PRESERVE_EVIDENCE: "Keep the original message and related records.",
  PROCEED_WITH_CAUTION: "Proceed with caution.",
  SEEK_HUMAN_REVIEW: "Seek review of this result by a person.",
  RESUBMIT_IN_SUPPORTED_LANGUAGE: "This input was not evaluated; resubmit it in a supported language where possible.",
};
export const ACTION_REASON = "Recommended by the governed action policy in the knowledge bundle identified in this result's provenance.";
export const DEGRADED_MEANING = "One or more rules could not be evaluated, so detection confidence is limited; this is not a determination that the content is safe.";
export const EMPTY_LIST = "None listed in this result.";
export const NOT_PROVIDED = "Not provided in this response.";
export const AI_STATEMENT = "AI may indirectly affect the deterministic result only through validated governed observations; it cannot directly set, override or bypass the deterministic decision.";

export type Presentation = "READY" | "ACTION_PENDING" | "ACTION_FAILED" | "REMOVED_UNDER_GOVERNANCE" | "AUTHENTICATION_REQUIRED"
  | "ACCESS_DENIED" | "NOT_FOUND_OR_NOT_VISIBLE" | "INTEGRITY_ERROR" | "SERVER_ERROR" | "TEMPORARILY_UNAVAILABLE" | "RATE_LIMITED"
  | "RESULT_STATUS_UNRESOLVED" | "RESULT_UNRENDERABLE" | "RESULT_VIEW_NOT_AUTHORIZED" | "RESULT_RESPONSE_UNCONFIRMED";
export const ANNOUNCEMENTS: Record<Presentation, string> = {
  READY: "Result available: {classification_label}.",
  ACTION_PENDING: "The evaluation has not finished; no result is available yet.",
  ACTION_FAILED: "The evaluation or request did not produce a result.",
  REMOVED_UNDER_GOVERNANCE: "This result was removed under governance and cannot be shown.",
  AUTHENTICATION_REQUIRED: "Sign-in is required before a result can be shown.",
  ACCESS_DENIED: "This result is not available with your access.",
  NOT_FOUND_OR_NOT_VISIBLE: "No result can be shown here.",
  INTEGRITY_ERROR: "The result could not be verified and is not shown.",
  SERVER_ERROR: "The result could not be loaded.",
  TEMPORARILY_UNAVAILABLE: "The result is temporarily unavailable.",
  RATE_LIMITED: "Too many requests; the result was not loaded.",
  RESULT_STATUS_UNRESOLVED: "The result status could not be confirmed; no result is shown.",
  RESULT_UNRENDERABLE: "The response was incomplete or inconsistent; no result is shown.",
  RESULT_VIEW_NOT_AUTHORIZED: "The response did not match the view available to you; no result is shown.",
  RESULT_RESPONSE_UNCONFIRMED: "No confirmed result was received; no result is shown.",
};
const ERROR_STATES: Record<string, Presentation> = {
  UNAUTHENTICATED: "AUTHENTICATION_REQUIRED", FORBIDDEN: "ACCESS_DENIED", NOT_FOUND: "NOT_FOUND_OR_NOT_VISIBLE",
  EVALUATION_NOT_COMPLETED: "ACTION_PENDING", REMOVED_UNDER_GOVERNANCE: "REMOVED_UNDER_GOVERNANCE", INTEGRITY_FAILURE: "INTEGRITY_ERROR",
  INTERNAL_ERROR: "SERVER_ERROR", DEPENDENCY_UNAVAILABLE: "TEMPORARILY_UNAVAILABLE", RATE_LIMITED: "RATE_LIMITED",
};
export const FAILURE_REASONS: Record<string, string> = {
  KNOWLEDGE_UNAVAILABLE: "Governed knowledge was not available for this evaluation.",
  INPUT_NOT_EVALUABLE: "The input could not be evaluated.",
  INTEGRITY_FAILURE: "An integrity check failed, so no result was kept.",
  INFRASTRUCTURE_FAILURE: "The evaluation was interrupted before its result was durably kept.",
};
export const STATE_LABELS: Record<ApiState, string> = {
  QUEUED: "Analysis requested", RUNNING: "Analysis running", COMPLETED: "Analysis finished", FAILED: "Analysis did not produce a result",
};
export const ANALYZE_MESSAGES: Record<string, string> = {
  ...MESSAGES,
  STATE_CONFLICT: "Analysis needs exactly one stored and verified message text in this submission.",
  DEPENDENCY_UNAVAILABLE: "Analysis is temporarily unavailable (the governed knowledge or storage is not ready). Please try again later.",
  NOT_FOUND: "That submission could not be found.",
};

export const announcement = (state: Presentation, result?: ResultView) =>
  ANNOUNCEMENTS[state].replace("{classification_label}", result ? CLASSIFICATIONS[result.classification]?.label ?? "" : "");

// ---- response validation (UX-003 response_validation / render_authorization)
const REQUIRED = ["evaluation_id", "result_contract_version", "result_digest", "view", "input_support_status", "language", "script",
  "classification", "decision_severity", "matched_evidence_strength", "risk_level", "detection_confidence", "degraded", "matched_rules",
  "explanation", "recommended_actions", "limitations", "unknowns", "ambiguities", "provenance", "not_an_official_determination"];

/** READY only for a complete, self-consistent response for the evaluation and view requested; otherwise a withheld state. */
export function validateResult(body: unknown, evaluationId: string, requestedView: "STANDARD" | "DETAILED"): Presentation {
  if (!body || typeof body !== "object") return "RESULT_UNRENDERABLE";
  const r = body as Record<string, unknown>;
  if (REQUIRED.some((field) => !(field in r) || r[field] === undefined || r[field] === null)) return "RESULT_UNRENDERABLE";
  const result = body as ResultView;
  if (result.evaluation_id !== evaluationId || result.not_an_official_determination !== true) return "RESULT_UNRENDERABLE";
  if (result.view !== requestedView || (requestedView === "STANDARD" && "rule_results" in r)) return "RESULT_VIEW_NOT_AUTHORIZED";
  if (!(result.classification in CLASSIFICATIONS) || !(result.input_support_status in INPUT_SUPPORT)) return "RESULT_UNRENDERABLE";
  if (AXES.some((axis) => !axis.values.includes(result[axis.field]))) return "RESULT_UNRENDERABLE";
  if (!Array.isArray(result.matched_rules) || !Array.isArray(result.recommended_actions) || typeof result.explanation?.summary !== "string")
    return "RESULT_UNRENDERABLE";
  if (result.classification === "NO_SCAM_PATTERN" && !result.absence_of_finding_notice) return "RESULT_UNRENDERABLE";
  return axisContradiction(result) ? "RESULT_UNRENDERABLE" : "READY";
}

// ---- cross-field consistency (UX-003 response_validation: permitted_support_classification, axis_consistency and
// rule_identity, whose authority is DET-001-WP5 and knowledge/runtime/result.py semantic_violations). These tables are
// copied verbatim from contracts/ux/ux-result-v1.json; App.test.mjs pins them to that file. A contradiction withholds
// the result (RESULT_UNRENDERABLE); nothing is repaired, relabelled or re-derived.
export const PERMITTED_SUPPORT_CLASSIFICATION: Record<string, string[]> = {
  SUPPORTED: ["NO_SCAM_PATTERN", "INSUFFICIENT_EVIDENCE", "SCAM_PATTERN_SUSPECTED", "SCAM_PATTERN_DETECTED", "ERROR"],
  PARTIALLY_SUPPORTED: ["NO_SCAM_PATTERN", "INSUFFICIENT_EVIDENCE", "SCAM_PATTERN_SUSPECTED", "SCAM_PATTERN_DETECTED", "ERROR"],
  UNSUPPORTED: ["UNSUPPORTED"],
  INSUFFICIENT_INFORMATION: ["INSUFFICIENT_EVIDENCE"],
  ERROR: ["ERROR"],
};
export const RISK_MATRIX: [string, string, string][] = [   // risk-matrix-v1: [decision_severity, matched_evidence_strength, risk_level]
  ["NONE", "NONE", "NONE"], ["LOW", "WEAK", "LOW"], ["LOW", "MODERATE", "LOW"], ["LOW", "STRONG", "MEDIUM"],
  ["MEDIUM", "WEAK", "LOW"], ["MEDIUM", "MODERATE", "MEDIUM"], ["MEDIUM", "STRONG", "MEDIUM"], ["HIGH", "WEAK", "MEDIUM"],
  ["HIGH", "MODERATE", "HIGH"], ["HIGH", "STRONG", "HIGH"], ["CRITICAL", "WEAK", "HIGH"], ["CRITICAL", "MODERATE", "HIGH"],
  ["CRITICAL", "STRONG", "CRITICAL"],
];
export const FINDING_CLASSIFICATION_BY_CONFIDENCE: Record<string, string> = {
  LOW: "SCAM_PATTERN_SUSPECTED", MEDIUM: "SCAM_PATTERN_DETECTED", HIGH: "SCAM_PATTERN_DETECTED",
};
export const NO_FINDING_AXES = { decision_severity: "NONE", matched_evidence_strength: "NONE", risk_level: "NONE",
                                 detection_confidence: "NOT_APPLICABLE" };
export const DEGRADED_CONFIDENCE_CAP = "MEDIUM";
const RULE_ID = /^TL-[A-Z]{3,5}-\d{3}$/;
const RULE_VERSION = /^\d+\.\d+\.\d+$/;
const CONFIDENCE_ORDER = ["LOW", "MEDIUM", "HIGH"];

function axisContradiction(r: ResultView): boolean {
  if (!(PERMITTED_SUPPORT_CLASSIFICATION[r.input_support_status] ?? []).includes(r.classification)) return true;
  const matrix = RISK_MATRIX.find(([severity, strength]) => severity === r.decision_severity && strength === r.matched_evidence_strength);
  if (!matrix || matrix[2] !== r.risk_level) return true;
  const references = [...r.matched_rules, ...(r.governing_rule ? [r.governing_rule] : [])];
  if (references.some((ref) => !RULE_ID.test(ref?.rule_id ?? "") || !RULE_VERSION.test(ref?.rule_version ?? ""))) return true;
  if (new Set(r.matched_rules.map((ref) => ref.rule_id)).size !== r.matched_rules.length) return true;
  const finding = r.matched_rules.length > 0;                                   // finding_basis: matched_rules NON_EMPTY
  if (finding) {
    if (FINDING_CLASSIFICATION_BY_CONFIDENCE[r.detection_confidence] !== r.classification) return true;
    if (r.decision_severity === "NONE") return true;
    const governing = r.governing_rule;
    if (!governing || !r.matched_rules.some((m) => m.rule_id === governing.rule_id && m.rule_version === governing.rule_version)) return true;
  } else {
    if (Object.values(FINDING_CLASSIFICATION_BY_CONFIDENCE).includes(r.classification)) return true;
    if (Object.entries(NO_FINDING_AXES).some(([axis, value]) => r[axis as keyof typeof NO_FINDING_AXES] !== value)) return true;
    if (r.governing_rule) return true;
  }
  if (r.degraded && CONFIDENCE_ORDER.indexOf(r.detection_confidence) > CONFIDENCE_ORDER.indexOf(DEGRADED_CONFIDENCE_CAP)) return true;
  return false;
}

export const presentationForError = (error: ApiFailure): Presentation => ERROR_STATES[error.code] ?? "RESULT_RESPONSE_UNCONFIRMED";

/** Status gating (UX-003 status_gating): a result is requested only for COMPLETED + AVAILABLE. */
export function presentationForStatus(evaluation: EvaluationView | null): Presentation | "REQUEST_RESULT" {
  if (!evaluation) return "RESULT_STATUS_UNRESOLVED";
  if (evaluation.state === "COMPLETED" && evaluation.result_availability === "AVAILABLE") return "REQUEST_RESULT";
  if (evaluation.state === "COMPLETED" && evaluation.result_availability === "REMOVED_UNDER_GOVERNANCE") return "REMOVED_UNDER_GOVERNANCE";
  if ((evaluation.state === "QUEUED" || evaluation.state === "RUNNING") && evaluation.result_availability === "NOT_YET_AVAILABLE") return "ACTION_PENDING";
  if (evaluation.state === "FAILED" && evaluation.result_availability === "NOT_PRODUCED") return "ACTION_FAILED";
  return "RESULT_STATUS_UNRESOLVED";
}

// ---- API calls
const realSleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export const createEvaluation = (submissionId: string, body: object = {}, fetcher: Fetch = fetch, newKey = randomKey) =>
  create<{ evaluations: EvaluationView[] }>(`/api/v1/submissions/${encodeURIComponent(submissionId)}/evaluations`, body, fetcher, newKey);
export const getEvaluation = (evaluationId: string, fetcher: Fetch = fetch) =>
  get<EvaluationView>(`/api/v1/evaluations/${encodeURIComponent(evaluationId)}`, fetcher);
export const listCaseEvaluations = (caseId: string, fetcher: Fetch = fetch) =>
  get<{ items: EvaluationView[] }>(`/api/v1/cases/${encodeURIComponent(caseId)}/evaluations?limit=50`, fetcher);
export const getResult = (evaluationId: string, view: "STANDARD" | "DETAILED" = "STANDARD", fetcher: Fetch = fetch) =>
  get<ResultView>(`/api/v1/evaluations/${encodeURIComponent(evaluationId)}/result?view=${view}`, fetcher);

/** Poll until terminal or the bounded number of polls is used; never claims completion that was not reported. */
export async function waitForEvaluation(evaluation: EvaluationView, options: { fetcher?: Fetch; sleep?: (ms: number) => Promise<unknown> } = {})
  : Promise<Result<EvaluationView>> {
  const { fetcher = fetch, sleep = realSleep } = options;
  let latest: Result<EvaluationView> = { kind: "ok", value: evaluation };
  for (let poll = 0; latest.kind === "ok" && (latest.value.state === "QUEUED" || latest.value.state === "RUNNING") && poll < MAX_STATUS_POLLS; poll++) {
    await sleep(Math.min(1000 * (poll + 1), 3000));
    latest = await getEvaluation(evaluation.evaluation_id, fetcher);
  }
  return latest;
}
