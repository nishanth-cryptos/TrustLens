import { useEffect, useRef, useState } from "react";
import { ResultSections } from "./AnalysisPanel";
import EnrichmentPanel from "./EnrichmentPanel";
import { CLASSIFICATIONS, EvaluationView, STATE_LABELS, getResult, presentationForError, presentationForStatus,
  validateResult, announcement } from "./evaluation";
import { COMPARISON_NOTICE, HISTORY_MESSAGES, HISTORY_TEXT, HistoryEntry, HistoryState, LOADING_STATE, ORIGIN_LABELS, REPLAY_OUTCOMES,
  REPLAY_STATES, ReplayView, createHistoryLoader, createReplay, waitForReplay } from "./history";

type Props = { caseId: string; submissionId: string; canReplay: boolean; refresh?: number; initialState?: HistoryState };

const when = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleString() : "");

/** One STANDARD result per COMPLETED + AVAILABLE evaluation, validated; every read is audited server-side. */
export async function loadEntry(evaluation: EvaluationView): Promise<HistoryEntry> {
  const gate = presentationForStatus(evaluation);
  if (gate !== "REQUEST_RESULT") return { evaluation, result: null, note: announcement(gate) };
  const r = await getResult(evaluation.evaluation_id, "STANDARD");
  if (r.kind === "error") return { evaluation, result: null, note: announcement(presentationForError(r)) };
  const state = validateResult(r.value, evaluation.evaluation_id, "STANDARD");
  return state === "READY" ? { evaluation, result: r.value, note: null } : { evaluation, result: null, note: announcement(state) };
}

export default function HistoryPanel({ caseId, submissionId, canReplay, refresh = 0, initialState }: Props) {
  const [history, setHistory] = useState<HistoryState>(initialState ?? LOADING_STATE);
  const [open, setOpen] = useState<string | null>(null);
  const [replays, setReplays] = useState<Record<string, ReplayView | string>>({});
  const [lookups, setLookups] = useState<string | null>(null);
  const loader = useRef<ReturnType<typeof createHistoryLoader> | null>(null);

  useEffect(() => {
    if (initialState) return;
    const current = createHistoryLoader({ caseId, submissionId, onChange: setHistory, loadEntry });
    loader.current = current;
    current.first();
    return () => current.cancel();                     // a newer case/submission/refresh makes this one stale
  }, [caseId, submissionId, refresh, initialState]);

  async function replay(evaluationId: string) {
    setReplays((prev) => ({ ...prev, [evaluationId]: "Requesting a replay…" }));
    const created = await createReplay(evaluationId);
    if (created.kind === "error") {
      return setReplays((prev) => ({ ...prev, [evaluationId]: HISTORY_MESSAGES[created.code] ?? HISTORY_MESSAGES.INTERNAL_ERROR }));
    }
    setReplays((prev) => ({ ...prev, [evaluationId]: created.value }));
    const done = await waitForReplay(created.value);
    setReplays((prev) => ({ ...prev, [evaluationId]: done }));
  }

  const entries = history.entries;
  return (
    <div className="history-panel" aria-labelledby={`history-${submissionId}`} aria-busy={history.status === "LOADING" || history.loadingMore}>
      <h5 id={`history-${submissionId}`}>Analysis history</h5>
      {history.status === "LOADING" && <p className="meta" role="status">{HISTORY_TEXT.LOADING}</p>}
      {history.status === "EMPTY" && <p className="meta" role="status">{HISTORY_TEXT.EMPTY}</p>}
      {history.status === "UNAVAILABLE" && (
        <p className="notice" role="alert">{HISTORY_TEXT.UNAVAILABLE}{" "}
          <button type="button" className="link-button" onClick={() => loader.current?.first()}>Try again</button></p>
      )}
      {history.status === "AVAILABLE" && <p className="meta">{COMPARISON_NOTICE}</p>}
      {history.status === "AVAILABLE" && <ol className="history-list">
        {entries.map(({ evaluation, result, note }, index) => {
          const id = evaluation.evaluation_id;
          const replayState = replays[id];
          return (
            <li key={id} className={index === 0 ? "history-item latest" : "history-item"}>
              <div className="history-head">
                <strong>{index === 0 ? "Latest" : "Earlier"}</strong>
                <span>{ORIGIN_LABELS[evaluation.origin] ?? evaluation.origin}</span>
                <span className="meta">{STATE_LABELS[evaluation.state] ?? evaluation.state}</span>
              </div>
              <p className="meta">
                Requested {when(evaluation.requested_at)}{evaluation.completed_at ? ` · finished ${when(evaluation.completed_at)}` : ""}
                {evaluation.provenance ? <> · bundle {evaluation.provenance.bundle_version} <code>{evaluation.provenance.bundle_content_digest.slice(0, 12)}…</code>
                  · engine {evaluation.provenance.engine_version}</> : null}
              </p>
              {result && <p>Classification: <strong>{CLASSIFICATIONS[result.classification].label}</strong> <code>{result.classification}</code></p>}
              {note && <p className="meta">{note}</p>}
              <div className="history-actions">
                {result && (
                  <button type="button" className="link-button" aria-expanded={open === id} onClick={() => setOpen(open === id ? null : id)}>
                    {open === id ? "Hide this result" : "Open this result"}
                  </button>
                )}
                {canReplay && (
                  <button type="button" className="link-button" aria-expanded={lookups === id} onClick={() => setLookups(lookups === id ? null : id)}>
                    {lookups === id ? "Hide external lookups" : "External lookups (advisory)"}
                  </button>
                )}
                {canReplay && evaluation.state === "COMPLETED" && (
                  <button type="button" className="link-button" onClick={() => replay(id)}
                          disabled={typeof replayState === "object" && replayState.state === "PENDING"}>
                    Replay to verify
                  </button>
                )}
              </div>
              {typeof replayState === "string" && <p className="meta" role="status">{replayState}</p>}
              {typeof replayState === "object" && (
                <div className="replay" role="status">
                  <p><strong>{REPLAY_STATES[replayState.state].label}</strong> — {REPLAY_STATES[replayState.state].meaning}</p>
                  {replayState.outcome && REPLAY_OUTCOMES[replayState.outcome] && (
                    <p><strong>{REPLAY_OUTCOMES[replayState.outcome].label}</strong> — {REPLAY_OUTCOMES[replayState.outcome].meaning}</p>
                  )}
                  {replayState.missing_material_kinds && replayState.missing_material_kinds.length > 0 && (
                    <p className="meta">Unavailable material: {replayState.missing_material_kinds.join(", ")}</p>
                  )}
                </div>
              )}
              {open === id && result && <ResultSections result={result} evaluation={evaluation} />}
              {canReplay && lookups === id && <EnrichmentPanel evaluationId={id} />}
            </li>
          );
        })}
      </ol>}
      {history.status === "AVAILABLE" && history.moreFailed && (
        <p className="notice" role="alert">{HISTORY_TEXT.MORE_FAILED}</p>
      )}
      {history.status === "AVAILABLE" && history.nextCursor && (
        <button type="button" className="button secondary" onClick={() => loader.current?.more()} disabled={history.loadingMore}>
          {history.loadingMore ? "Loading…" : history.moreFailed ? "Try loading more again" : "Load more"}
        </button>
      )}
    </div>
  );
}
