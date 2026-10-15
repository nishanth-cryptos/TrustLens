// S6 history client: getEvidenceContent (a plain same-origin attachment link), createCorrection, createReplay and getReplay
// (accepted API v1 operations only). Labels, meanings and notices are the exact UX-004 / UX-005 governed text. A replay
// record is content-free and is never a new result; a correction or re-analysis is always a new evaluation.
import { Fetch, MESSAGES, create, get, randomKey } from "./cases";
import { EvaluationView, ResultView } from "./evaluation";

export const DOWNLOAD_NOTICE = "Downloading the original evidence is recorded in the audit log.";
export const REANALYSIS_NOTICE = "A new analysis creates a new evaluation. Earlier evaluations and results are kept unchanged.";
export const CORRECTION_NOTICE = "Your correction creates a new evaluation. The earlier evaluation and its result are kept unchanged.";
export const COMPARISON_NOTICE = "Each evaluation is shown as its own record. No comparison between them is computed.";
export const MAX_CORRECTION_CHARS = 2000;
// Reason codes sent by this interface: NON-NORMATIVE, SYNTHETIC-LOCAL values pending API-owner approval of the reason
// vocabularies (UX-005#4). MAX_CORRECTION_CHARS is a local implementation parameter pending T09/Product approval.
export const CORRECTION_REASON = "EXTRACTION_ERROR";
export const REANALYSIS_REASON = "USER_REQUESTED_REANALYSIS";
export const REPLAY_REASON = "ANALYST_VERIFICATION";

export const ORIGIN_LABELS: Record<string, string> = {
  INITIAL: "First analysis", RE_EVALUATION: "New analysis", USER_CORRECTION: "New analysis after a correction",
  RETRY_AFTER_FAILURE: "New analysis after a failure", AI_RE_EXTRACTION: "New analysis with AI-assisted extraction",
};

export type ReplayView = {
  replay_id: string; evaluation_id: string; state: "PENDING" | "COMPLETED"; capability?: string | null; outcome?: string | null;
  missing_material_kinds?: string[]; replayed_result_digest?: string | null; requested_at: string; completed_at?: string | null;
};
export const REPLAY_STATES: Record<string, { label: string; meaning: string }> = {
  PENDING: { label: "Replay pending", meaning: "The replay was accepted and has not finished; no outcome is implied." },
  COMPLETED: { label: "Replay finished", meaning: "The replay finished with the outcome shown." },
};
export const REPLAY_OUTCOMES: Record<string, { label: string; meaning: string }> = {
  MATCH: { label: "Reproduced exactly", meaning: "Replaying the pinned material produced the recorded result digest." },
  MISMATCH: { label: "Did not reproduce", meaning: "Replaying the pinned material produced a different digest; the recorded result is unchanged." },
  FAILED_MISSING_MATERIAL: { label: "Replay unavailable: material missing",
    meaning: "Required pinned material is missing, so the evaluation cannot be replayed." },
  FAILED_INTEGRITY: { label: "Replay unavailable: integrity failure",
    meaning: "Pinned material failed its integrity check, so the evaluation cannot be replayed." },
  FAILED_ENGINE_UNAVAILABLE: { label: "Replay unavailable: engine unavailable", meaning: "The pinned engine version is not available for replay." },
  FAILED_BUNDLE_UNAVAILABLE: { label: "Replay unavailable: knowledge bundle unavailable",
    meaning: "The pinned knowledge bundle is not available for replay." },
};
export const HISTORY_MESSAGES: Record<string, string> = {
  ...MESSAGES,
  EVALUATION_NOT_COMPLETED: "That analysis has not finished yet.",
  REPLAY_UNAVAILABLE: "Required pinned material is already known to be removed, so this evaluation cannot be replayed.",
  NOT_FOUND: "That analysis could not be found.",
};

export const createCorrection = (evaluationId: string, description: string, fetcher: Fetch = fetch, newKey = randomKey) =>
  create<{ correction_id: string; corrected_evaluation_id: string; new_evaluation: EvaluationView }>(
    `/api/v1/evaluations/${encodeURIComponent(evaluationId)}/corrections`,
    { correction_description: description, reason_code: CORRECTION_REASON }, fetcher, newKey);
export const createReplay = (evaluationId: string, fetcher: Fetch = fetch, newKey = randomKey) =>
  create<ReplayView>(`/api/v1/evaluations/${encodeURIComponent(evaluationId)}/replays`, { reason_code: REPLAY_REASON }, fetcher, newKey);
export const getReplay = (replayId: string, fetcher: Fetch = fetch) => get<ReplayView>(`/api/v1/replays/${encodeURIComponent(replayId)}`, fetcher);
export const HISTORY_PAGE = 20;
export const listSubmissionEvaluations = (caseId: string, submissionId: string, cursor: string | null = null, fetcher: Fetch = fetch) =>
  get<{ items: EvaluationView[]; page: { next_cursor?: string | null; limit: number } }>(
    `/api/v1/cases/${encodeURIComponent(caseId)}/evaluations?submission_id=${encodeURIComponent(submissionId)}&limit=${HISTORY_PAGE}`
    + (cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""), fetcher);

// ---- history loading: explicit states, cursor pagination, no duplicates, stale responses dropped
export type HistoryEntry = { evaluation: EvaluationView; result: ResultView | null; note: string | null };
export type HistoryStatus = "LOADING" | "EMPTY" | "AVAILABLE" | "UNAVAILABLE";
export type HistoryState = { status: HistoryStatus; entries: HistoryEntry[]; nextCursor: string | null; loadingMore: boolean;
                             moreFailed: boolean };
export const HISTORY_TEXT = {
  LOADING: "Loading the analysis history…",
  EMPTY: "No analyses are recorded for this submission yet.",
  UNAVAILABLE: "The analysis history could not be loaded. This does not mean there is none.",
  MORE_FAILED: "More history could not be loaded. The entries above are unchanged.",
};
export const LOADING_STATE: HistoryState = { status: "LOADING", entries: [], nextCursor: null, loadingMore: false, moreFailed: false };

/** Append a page in server order (requested_at desc, id desc), keeping the first occurrence of every evaluation. */
export function mergeHistory(existing: HistoryEntry[], page: HistoryEntry[]): HistoryEntry[] {
  const seen = new Set(existing.map((e) => e.evaluation.evaluation_id));
  return [...existing, ...page.filter((e) => !seen.has(e.evaluation.evaluation_id) && seen.add(e.evaluation.evaluation_id))];
}

/** One loader per (case, submission): first() (re)loads page one, more() follows next_cursor, cancel() makes every
 * in-flight response stale. A failed request is UNAVAILABLE, never an authoritative empty history. */
export function createHistoryLoader(options: { caseId: string; submissionId: string; onChange: (state: HistoryState) => void;
                                               loadEntry: (evaluation: EvaluationView) => Promise<HistoryEntry>; fetcher?: Fetch }) {
  const { caseId, submissionId, onChange, loadEntry, fetcher = fetch } = options;
  let generation = 0;
  let state = LOADING_STATE;
  const set = (next: HistoryState) => { state = next; onChange(next); };
  async function first() {
    const mine = ++generation;
    set(LOADING_STATE);
    const r = await listSubmissionEvaluations(caseId, submissionId, null, fetcher);
    if (mine !== generation) return;
    if (r.kind === "error") return set({ ...LOADING_STATE, status: "UNAVAILABLE" });
    const entries = mergeHistory([], await Promise.all(r.value.items.map(loadEntry)));
    if (mine !== generation) return;
    set({ status: entries.length ? "AVAILABLE" : "EMPTY", entries, nextCursor: r.value.page?.next_cursor ?? null, loadingMore: false,
          moreFailed: false });
  }
  async function more() {
    if (!state.nextCursor || state.loadingMore || state.status !== "AVAILABLE") return;
    const mine = generation;
    set({ ...state, loadingMore: true, moreFailed: false });
    const r = await listSubmissionEvaluations(caseId, submissionId, state.nextCursor, fetcher);
    if (mine !== generation) return;
    if (r.kind === "error") return set({ ...state, loadingMore: false, moreFailed: true });   // loaded entries stay
    const page = await Promise.all(r.value.items.map(loadEntry));
    if (mine !== generation) return;
    set({ ...state, entries: mergeHistory(state.entries, page), nextCursor: r.value.page?.next_cursor ?? null, loadingMore: false });
  }
  return { first, more, cancel: () => { generation++; }, get state() { return state; } };
}

/** Poll a pending replay a bounded number of times; never claims a completion that was not reported. */
export async function waitForReplay(replay: ReplayView, options: { fetcher?: Fetch; sleep?: (ms: number) => Promise<unknown> } = {}) {
  const { fetcher = fetch, sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms)) } = options;
  let latest = replay;
  for (let poll = 0; latest.state === "PENDING" && poll < 10; poll++) {
    await sleep(Math.min(1000 * (poll + 1), 3000));
    const r = await getReplay(replay.replay_id, fetcher);
    if (r.kind === "error") break;
    latest = r.value;
  }
  return latest;
}
