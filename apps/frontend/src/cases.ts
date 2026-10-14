// Case and submission API client (accepted API v1 operations only). Same-origin requests carry the HttpOnly session
// cookie automatically; state-changing requests add the CSRF synchronizer token and an Idempotency-Key. Nothing is
// stored in localStorage or sessionStorage, and no message text is ever sent from here.

export type CaseView = {
  case_id: string; state: string; is_synthetic: boolean; created_at: string; closed_at?: string | null;
  viewer_access: { relationship: string; can_view_evidence_content: boolean }; etag: string;
};
export type SubmissionView = {
  submission_id: string; case_id: string; declared_input_type: string; relationship_to_content?: string;
  state: string; received_at: string; is_synthetic: boolean;
};
export type ApiFailure = { kind: "error"; code: string; message: string };
export type Result<T> = { kind: "ok"; value: T } | ApiFailure;

export const INPUT_TYPES: Record<string, string> = { SMS: "Text message (SMS)", CHAT_MESSAGE: "Chat message", TEXT: "Other text", EMAIL: "Email" };
export const RELATIONSHIPS: Record<string, string> = {
  RECEIVED: "I received it", FORWARDED: "It was forwarded to me", REPORTING_ON_BEHALF: "Reporting for someone else", UNKNOWN: "Not sure",
};
export const MAX_ATTEMPTS = 3;   // bounded retries of the same idempotent request (approved T09 profile); never infinite
export const RETRYABLE = ["IDEMPOTENCY_IN_PROGRESS", "DEPENDENCY_UNAVAILABLE", "RATE_LIMITED"];

export type Fetch = typeof fetch;

export async function failure(response: Response): Promise<ApiFailure> {
  try {
    const body = (await response.json()) as { error?: { code?: string } };
    const code = body.error?.code ?? "INTERNAL_ERROR";
    return { kind: "error", code, message: MESSAGES[code] ?? MESSAGES.INTERNAL_ERROR };
  } catch {
    return { kind: "error", code: "INTERNAL_ERROR", message: MESSAGES.INTERNAL_ERROR };
  }
}

export const MESSAGES: Record<string, string> = {
  UNAUTHENTICATED: "Your session has ended. Please sign in again.",
  FORBIDDEN: "You do not have permission to do that.",
  NOT_FOUND: "That case could not be found.",
  STATE_CONFLICT: "That is not possible while the case is in its current state.",
  IDEMPOTENCY_IN_PROGRESS: "Your previous request is still being processed. Please try again in a moment.",
  IDEMPOTENCY_KEY_REUSED: "The request changed while it was being retried. Please try again.",
  INVALID_REQUEST: "Something in the request was not accepted.",
  DEPENDENCY_UNAVAILABLE: "TrustLens is temporarily unavailable. Please try again in a moment.",
  PAYLOAD_TOO_LARGE: "The message text is larger than the 64 KiB limit.",
  UNSUPPORTED_MEDIA_TYPE: "Only plain UTF-8 text can be uploaded.",
  RATE_LIMITED: "Too many requests in a short time. Please wait a moment and try again.",
  INTEGRITY_FAILURE: "The stored copy did not match what was sent, so it was not accepted.",
  INTERNAL_ERROR: "Something went wrong. Please try again.",
};

export async function get<T>(path: string, fetcher: Fetch): Promise<Result<T>> {
  try {
    const response = await fetcher(path, { credentials: "same-origin", headers: { Accept: "application/json" } });
    return response.ok ? { kind: "ok", value: (await response.json()) as T } : failure(response);
  } catch {
    return { kind: "error", code: "DEPENDENCY_UNAVAILABLE", message: MESSAGES.DEPENDENCY_UNAVAILABLE };
  }
}

/** POST with one Idempotency-Key reused across bounded retries, so a lost response can never create a duplicate. */
export async function create<T>(path: string, body: object, fetcher: Fetch, newKey: () => string): Promise<Result<T>> {
  const key = newKey();
  for (let attempt = 1; ; attempt++) {
    try {
      const csrf = await fetcher("/auth/csrf", { credentials: "same-origin", headers: { Accept: "application/json" } });
      if (!csrf.ok) return failure(csrf);
      const { csrf_token } = (await csrf.json()) as { csrf_token: string };
      const response = await fetcher(path, {
        method: "POST", credentials: "same-origin", body: JSON.stringify(body),
        headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": csrf_token, "Idempotency-Key": key },
      });
      if (response.ok) return { kind: "ok", value: (await response.json()) as T };
      const problem = await failure(response);
      if (attempt >= MAX_ATTEMPTS || !RETRYABLE.includes(problem.code)) return problem;
    } catch {
      if (attempt >= MAX_ATTEMPTS) return { kind: "error", code: "DEPENDENCY_UNAVAILABLE", message: MESSAGES.DEPENDENCY_UNAVAILABLE };
    }
    await new Promise((resolve) => setTimeout(resolve, 500 * attempt));
  }
}

export const randomKey = () => crypto.randomUUID();

export const listCases = (fetcher: Fetch = fetch) => get<{ items: CaseView[] }>("/api/v1/cases?limit=20", fetcher);
export const createCase = (fetcher: Fetch = fetch, newKey = randomKey) => create<CaseView>("/api/v1/cases", {}, fetcher, newKey);
export const listSubmissions = (caseId: string, fetcher: Fetch = fetch) =>
  get<{ items: SubmissionView[] }>(`/api/v1/cases/${encodeURIComponent(caseId)}/submissions?limit=20`, fetcher);
export const createSubmission = (caseId: string, declaredInputType: string, relationship: string | null,
                                 fetcher: Fetch = fetch, newKey = randomKey) =>
  create<SubmissionView>(`/api/v1/cases/${encodeURIComponent(caseId)}/submissions`,
    relationship ? { declared_input_type: declaredInputType, relationship_to_content: relationship } : { declared_input_type: declaredInputType },
    fetcher, newKey);
