import { useEffect, useState } from "react";
import EvidencePanel from "./EvidencePanel";
import { CaseView, INPUT_TYPES, RELATIONSHIPS, SubmissionView, createCase, createSubmission, listCases, listSubmissions } from "./cases";
import { EvaluationView, ResultView } from "./evaluation";
import { EvidenceView } from "./evidence";

type Props = { initialCases?: CaseView[]; initialSubmissions?: SubmissionView[]; initialSelected?: string | null;
               initialSubmission?: string | null; initialEvidence?: EvidenceView[];
               initialEvaluation?: EvaluationView | null; initialResult?: ResultView | null };

const when = (iso: string) => new Date(iso).toLocaleString();
const CASE_STATE_LABELS: Record<string, string> = { OPEN: "Open", UNDER_REVIEW: "Under review", CLOSED: "Closed" };
// Submission processing state (UX-002 submission_states), not evidence content state: RECEIVING means the submission is
// open for evidence intake, whether or not evidence is already stored. Each evidence item's own state is shown with it.
export const SUBMISSION_STATE_LABELS: Record<string, string> = {
  RECEIVING: "Open for evidence", RECEIVED: "Evidence intake recorded", PROCESSING: "Processing recorded",
  PROCESSED: "Processing finished", PARTIALLY_FAILED: "Some processing failed", FAILED: "Processing failed",
};

export default function Workspace({ initialCases, initialSubmissions = [], initialSelected = null, initialSubmission = null,
                                    initialEvidence, initialEvaluation, initialResult }: Props) {
  const [cases, setCases] = useState<CaseView[] | null>(initialCases ?? null);
  const [selected, setSelected] = useState<string | null>(initialSelected);
  const [submissions, setSubmissions] = useState<SubmissionView[]>(initialSubmissions);
  const [openSubmission, setOpenSubmission] = useState<string | null>(initialSubmission);
  const [inputType, setInputType] = useState("SMS");
  const [relationship, setRelationship] = useState("RECEIVED");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ tone: "error" | "ok"; text: string } | null>(null);

  useEffect(() => {
    if (initialCases) return;
    listCases().then((r) => (r.kind === "ok" ? setCases(r.value.items) : setMessage({ tone: "error", text: r.message })));
  }, [initialCases]);

  useEffect(() => {
    if (!selected || initialCases) return;
    listSubmissions(selected).then((r) => (r.kind === "ok" ? setSubmissions(r.value.items) : setMessage({ tone: "error", text: r.message })));
  }, [selected, initialCases]);

  async function newCase() {
    setBusy(true);
    setMessage(null);
    const r = await createCase();
    setBusy(false);
    if (r.kind === "error") return setMessage({ tone: "error", text: r.message });
    setCases((prev) => [r.value, ...(prev ?? [])]);
    setSelected(r.value.case_id);
    setSubmissions([]);
    setOpenSubmission(null);
    setMessage({ tone: "ok", text: "Case created." });
  }

  async function newSubmission() {
    if (!selected) return;
    setBusy(true);
    setMessage(null);
    const r = await createSubmission(selected, inputType, relationship);
    setBusy(false);
    if (r.kind === "error") return setMessage({ tone: "error", text: r.message });
    setSubmissions((prev) => [r.value, ...prev]);
    setOpenSubmission(r.value.submission_id);
    setMessage({ tone: "ok", text: "Submission recorded. You can now add its message text." });
  }

  const current = cases?.find((c) => c.case_id === selected) ?? null;

  return (
    <section className="workspace-panel" aria-labelledby="cases-title">
      <div className="panel-head">
        <h2 id="cases-title">Your cases</h2>
        <button type="button" className="button" onClick={newCase} disabled={busy}>{busy ? "Working…" : "Create a case"}</button>
      </div>
      {message && <p className={message.tone === "error" ? "notice" : "success"} role={message.tone === "error" ? "alert" : "status"}>{message.text}</p>}
      {cases === null && <p>Loading your cases…</p>}
      {cases !== null && cases.length === 0 && <p>You have no cases yet.</p>}
      {cases !== null && cases.length > 0 && (
        <ul className="case-list">
          {cases.map((c) => (
            <li key={c.case_id}>
              <button type="button" className={c.case_id === selected ? "case-item selected" : "case-item"}
                      aria-pressed={c.case_id === selected} onClick={() => { setSelected(c.case_id); setOpenSubmission(null); setMessage(null); }}>
                <span>Case created {when(c.created_at)}</span>
                <span className="meta">{CASE_STATE_LABELS[c.state] ?? c.state}{c.is_synthetic ? " · synthetic test data" : ""}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {current && (
        <div className="case-detail" aria-labelledby="case-detail-title">
          <h3 id="case-detail-title">Case details</h3>
          <dl className="principal">
            <dt>Status</dt><dd>{CASE_STATE_LABELS[current.state] ?? current.state}</dd>
            <dt>Your access</dt><dd>{current.viewer_access.relationship === "OWNER" ? "Owner" : current.viewer_access.relationship}</dd>
            <dt>Case reference</dt><dd><code>{current.case_id}</code></dd>
          </dl>

          <h4>Submissions</h4>
          {submissions.length === 0 ? <p>No submissions yet.</p> : (
            <ul className="submission-list">
              {submissions.map((s) => (
                <li key={s.submission_id}>
                  <button type="button" className={s.submission_id === openSubmission ? "case-item selected" : "case-item"}
                          aria-expanded={s.submission_id === openSubmission}
                          onClick={() => setOpenSubmission(s.submission_id === openSubmission ? null : s.submission_id)}>
                    {INPUT_TYPES[s.declared_input_type] ?? s.declared_input_type} · {SUBMISSION_STATE_LABELS[s.state] ?? s.state} · received {when(s.received_at)}
                  </button>
                  {s.submission_id === openSubmission && (
                    <EvidencePanel caseId={current.case_id} submissionId={s.submission_id} initialEvidence={initialEvidence}
                                   initialEvaluation={initialEvaluation} initialResult={initialResult}
                                   canUpload={current.viewer_access.relationship === "OWNER" && current.state === "OPEN"} />
                  )}
                </li>
              ))}
            </ul>
          )}

          {current.viewer_access.relationship === "OWNER" && current.state === "OPEN" && (
            <fieldset className="submission-form">
              <legend>Record a new submission</legend>
              <label htmlFor="input-type">What kind of message is it?</label>
              <select id="input-type" value={inputType} onChange={(e) => setInputType(e.target.value)}>
                {Object.entries(INPUT_TYPES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
              <label htmlFor="relationship">How did you get it?</label>
              <select id="relationship" value={relationship} onChange={(e) => setRelationship(e.target.value)}>
                {Object.entries(RELATIONSHIPS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
              <button type="button" className="button secondary" onClick={newSubmission} disabled={busy}>Record submission</button>
            </fieldset>
          )}
          <p className="note">
            Choose a submission to see or add its message text and to analyse it. Only synthetic test data should be
            used. Results come from TrustLens's governed rules; they are not official determinations.
          </p>
        </div>
      )}
    </section>
  );
}
