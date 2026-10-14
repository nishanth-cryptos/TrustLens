// Evidence intake client: the accepted three-step upload (createEvidenceUpload -> putEvidenceContent ->
// finalizeEvidence), then bounded polling of getEvidenceMetadata. The server computes the authoritative SHA-256; the
// digest sent here is advisory only. Message text goes only in the PUT body as text/plain; charset=utf-8 and is never
// stored in the browser (no localStorage, sessionStorage or IndexedDB). Nothing is analysed or scored.
import { ApiFailure, Fetch, MAX_ATTEMPTS, MESSAGES, RETRYABLE, Result, create, failure, get, randomKey } from "./cases";

export const MAX_EVIDENCE_BYTES = 64 * 1024;      // approved T09 local-development value
export const MAX_POLLS = 10;                     // approved T09 value: finalize status polling is bounded
export const TEXT_MEDIA_TYPE = "text/plain; charset=utf-8";

export type EvidenceView = {
  evidence_id: string; submission_id: string; artifact_kind: string; upload_state: string;
  content_sha256: string | null; byte_length: number | null; declared_media_type: string;
  verified_media_type: string | null; display_filename: string | null; ingested_at: string; finalized_at: string | null;
};
export type Stage = "PREPARING" | "SENDING" | "CHECKING" | "FINALIZED" | "REJECTED" | "STILL_PROCESSING" | "FAILED";

/** Plain-language upload states (UX-002): what is known, never more. */
export const STAGE_LABELS: Record<Stage, string> = {
  PREPARING: "Preparing the upload…",
  SENDING: "Sending the message text…",
  CHECKING: "Checking the stored copy…",
  FINALIZED: "Stored and verified. It has not been analysed.",
  REJECTED: "The message text could not be stored. Nothing was analysed.",
  STILL_PROCESSING: "Still being processed. Reload later to see its status.",
  FAILED: "The upload did not finish.",
};
export const UPLOAD_STATE_LABELS: Record<string, string> = {
  AWAITING_CONTENT: "Waiting for the message text", PROCESSING: "Being stored", FINALIZED: "Stored and verified",
  REJECTED: "Not stored", DELETION_PENDING: "Being deleted", DELETED: "Deleted",
};

export const utf8Bytes = (text: string): Uint8Array<ArrayBuffer> => new TextEncoder().encode(text);

export async function sha256Hex(bytes: Uint8Array<ArrayBuffer>): Promise<string | null> {
  try {
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
  } catch {
    return null;                                  // advisory only: the server's digest is authoritative
  }
}

const unavailable = (): ApiFailure => ({ kind: "error", code: "DEPENDENCY_UNAVAILABLE", message: MESSAGES.DEPENDENCY_UNAVAILABLE });
const realSleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

type Options = { fetcher?: Fetch; newKey?: () => string; sleep?: (ms: number) => Promise<unknown>; onStage?: (stage: Stage) => void };

/** PUT the exact bytes. Re-sending identical bytes is a no-op on the server, so bounded retries are safe. */
async function putContent(evidenceId: string, bytes: Uint8Array<ArrayBuffer>, fetcher: Fetch, sleep: (ms: number) => Promise<unknown>)
  : Promise<Result<EvidenceView>> {
  for (let attempt = 1; ; attempt++) {
    let wait = 1000 * attempt;
    try {
      const csrf = await fetcher("/auth/csrf", { credentials: "same-origin", headers: { Accept: "application/json" } });
      if (!csrf.ok) return failure(csrf);
      const { csrf_token } = (await csrf.json()) as { csrf_token: string };
      const response = await fetcher(`/api/v1/evidence/${encodeURIComponent(evidenceId)}/content`, {
        method: "PUT", credentials: "same-origin", body: bytes,
        headers: { "Content-Type": TEXT_MEDIA_TYPE, Accept: "application/json", "X-CSRF-Token": csrf_token },
      });
      if (response.ok) return { kind: "ok", value: (await response.json()) as EvidenceView };
      const problem = await failure(response);
      if (attempt >= MAX_ATTEMPTS || !RETRYABLE.includes(problem.code)) return problem;
      const retryAfter = Number(response.headers.get("Retry-After"));
      if (Number.isFinite(retryAfter) && retryAfter > 0) wait = Math.min(retryAfter, 30) * 1000;
    } catch {
      if (attempt >= MAX_ATTEMPTS) return unavailable();
    }
    await sleep(wait);
  }
}

/** The whole journey. Returns the last known metadata; never claims more than the server reported. */
/** Honest, step-specific wording once an upload record exists: say what is saved and what is not, never more. */
export const PARTIAL_MESSAGES = {
  CONTENT_NOT_STORED: "The upload was started and its details are saved, but the message text has not been stored yet. "
    + "You can send the same text again for this upload.",
  NOT_VERIFIED: "The message text was received, but it has not been verified yet, so the upload is not finished. "
    + "You can try finishing it again.",
  DIFFERENT_TEXT: "This upload already holds different message text, so nothing was changed. Start a new upload to send other text.",
  MISMATCHED_TEXT: "This text does not match what the upload was started with. Paste exactly the same text, or start a new upload.",
};

const PUT_SPECIFIC: Record<string, string> = {
  STATE_CONFLICT: PARTIAL_MESSAGES.DIFFERENT_TEXT, INVALID_REQUEST: PARTIAL_MESSAGES.MISMATCHED_TEXT,
};

type Outcome = { stage: Stage; evidence?: EvidenceView; error?: ApiFailure };

const partial = (error: ApiFailure, message: string): ApiFailure =>
  // Integrity and permission outcomes keep their own accurate wording; transient and state failures are explained.
  ["INTEGRITY_FAILURE", "FORBIDDEN", "UNAUTHENTICATED", "PAYLOAD_TOO_LARGE", "UNSUPPORTED_MEDIA_TYPE"].includes(error.code)
    ? error : { ...error, message };

/** Steps 2 and 3 for an existing upload (also used to resume one): exact bytes, finalize, bounded polling. */
async function continueUpload(evidence: EvidenceView, bytes: Uint8Array<ArrayBuffer>, options: Options): Promise<Outcome> {
  const { fetcher = fetch, newKey = randomKey, sleep = realSleep, onStage = () => {} } = options;
  const evidenceId = evidence.evidence_id;
  onStage("SENDING");
  const stored = await putContent(evidenceId, bytes, fetcher, sleep);
  if (stored.kind === "error") {
    return { stage: "FAILED", evidence, error: partial(stored, PUT_SPECIFIC[stored.code] ?? PARTIAL_MESSAGES.CONTENT_NOT_STORED) };
  }

  onStage("CHECKING");
  const finalized = await create<EvidenceView>(`/api/v1/evidence/${encodeURIComponent(evidenceId)}/finalize`, {}, fetcher, newKey);
  let view = finalized.kind === "ok" ? finalized.value : stored.value;
  for (let poll = 0; view.upload_state === "PROCESSING" && poll < MAX_POLLS; poll++) {
    await sleep(1000);
    const latest = await getEvidence(evidenceId, fetcher);
    if (latest.kind === "ok") view = latest.value;
  }
  const stage: Stage = view.upload_state === "FINALIZED" ? "FINALIZED" : view.upload_state === "REJECTED" ? "REJECTED"
    : view.upload_state === "PROCESSING" ? "STILL_PROCESSING" : "FAILED";
  if (stage === "FINALIZED" || finalized.kind === "ok") return { stage, evidence: view };
  return { stage, evidence: view, error: partial(finalized, PARTIAL_MESSAGES.NOT_VERIFIED) };
}

function checkSize(bytes: Uint8Array): Outcome | null {
  if (bytes.length === 0) return { stage: "FAILED", error: { kind: "error", code: "INVALID_REQUEST", message: "Paste some text first." } };
  if (bytes.length > MAX_EVIDENCE_BYTES) return { stage: "FAILED", error: { kind: "error", code: "PAYLOAD_TOO_LARGE", message: MESSAGES.PAYLOAD_TOO_LARGE } };
  return null;
}

/** The whole journey. Returns the last known metadata; never claims more than the server reported. */
export async function uploadText(submissionId: string, text: string, options: Options = {}): Promise<Outcome> {
  const { fetcher = fetch, newKey = randomKey, onStage = () => {} } = options;
  const bytes = utf8Bytes(text);
  const invalid = checkSize(bytes);
  if (invalid) return invalid;
  onStage("PREPARING");
  const digest = await sha256Hex(bytes);
  const intent = await create<EvidenceView>(`/api/v1/submissions/${encodeURIComponent(submissionId)}/evidence`, {
    artifact_kind: "TEXT_BODY", declared_media_type: TEXT_MEDIA_TYPE, declared_byte_length: bytes.length,
    ...(digest ? { client_declared_sha256: digest } : {}),
  }, fetcher, newKey);
  if (intent.kind === "error") return { stage: "FAILED", error: intent };
  return continueUpload(intent.value, bytes, options);
}

/** Resume an incomplete upload with the same text: the server accepts only the exact declared bytes. */
export async function resumeUpload(evidence: EvidenceView, text: string, options: Options = {}): Promise<Outcome> {
  const bytes = utf8Bytes(text);
  return checkSize(bytes) ?? continueUpload(evidence, bytes, options);
}

export const canResume = (evidence: EvidenceView) => ["AWAITING_CONTENT", "PROCESSING"].includes(evidence.upload_state);

export const getEvidence = (evidenceId: string, fetcher: Fetch = fetch) =>
  get<EvidenceView>(`/api/v1/evidence/${encodeURIComponent(evidenceId)}`, fetcher);
export const listEvidence = (submissionId: string, fetcher: Fetch = fetch) =>
  get<{ items: EvidenceView[] }>(`/api/v1/submissions/${encodeURIComponent(submissionId)}/evidence?limit=20`, fetcher);
