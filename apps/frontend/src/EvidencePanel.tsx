import { useEffect, useState } from "react";
import AnalysisPanel from "./AnalysisPanel";
import { EvaluationView, ResultView } from "./evaluation";
import { MAX_EVIDENCE_BYTES, STAGE_LABELS, Stage, EvidenceView, UPLOAD_STATE_LABELS, canResume, listEvidence, resumeUpload, uploadText,
  utf8Bytes } from "./evidence";

type Props = { caseId: string; submissionId: string; canUpload: boolean; initialEvidence?: EvidenceView[];
               initialEvaluation?: EvaluationView | null; initialResult?: ResultView | null };

const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString() : "");
const BUSY: Stage[] = ["PREPARING", "SENDING", "CHECKING"];

export default function EvidencePanel({ caseId, submissionId, canUpload, initialEvidence, initialEvaluation, initialResult }: Props) {
  const [items, setItems] = useState<EvidenceView[] | null>(initialEvidence ?? null);
  const [text, setText] = useState("");
  const [stage, setStage] = useState<Stage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialEvidence) return;
    setItems(null);
    listEvidence(submissionId).then((r) => (r.kind === "ok" ? setItems(r.value.items) : setError(r.message)));
  }, [submissionId, initialEvidence]);

  const size = utf8Bytes(text).length;
  const busy = stage !== null && BUSY.includes(stage);

  async function upload(existing?: EvidenceView) {
    setError(null);
    const result = existing ? await resumeUpload(existing, text, { onStage: setStage })
      : await uploadText(submissionId, text, { onStage: setStage });
    setStage(result.stage);
    if (result.error) setError(result.error.message);
    if (result.evidence) {
      const evidence = result.evidence;
      setItems((prev) => [evidence, ...(prev ?? []).filter((e) => e.evidence_id !== evidence.evidence_id)]);
    }
    if (result.stage === "FINALIZED") setText("");      // the text now lives only in encrypted server storage
  }

  return (
    <div className="evidence-panel" aria-labelledby={`evidence-${submissionId}`}>
      <h5 id={`evidence-${submissionId}`}>Message text for this submission</h5>
      {items === null && !error && <p>Loading…</p>}
      {items !== null && items.length === 0 && <p>No message text uploaded yet.</p>}
      {items !== null && items.length > 0 && (
        <ul className="evidence-list">
          {items.map((e) => (
            <li key={e.evidence_id}>
              <span>{UPLOAD_STATE_LABELS[e.upload_state] ?? e.upload_state}</span>
              {e.byte_length !== null && <span className="meta"> · {e.byte_length.toLocaleString()} bytes</span>}
              {e.content_sha256 && <span className="meta"> · SHA-256 <code>{e.content_sha256.slice(0, 12)}…</code></span>}
              <span className="meta"> · {e.finalized_at ? `stored ${when(e.finalized_at)}` : `started ${when(e.ingested_at)}`}</span>
              {canUpload && canResume(e) && (
                <button type="button" className="link-button" onClick={() => upload(e)} disabled={busy || size === 0}
                        aria-label="Continue this unfinished upload with the text in the box below">
                  Continue this upload
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {canUpload && (
        <div className="evidence-form">
          <label htmlFor={`text-${submissionId}`}>Paste the message text (synthetic test data only)</label>
          <textarea id={`text-${submissionId}`} rows={5} value={text} disabled={busy} spellCheck={false} autoComplete="off"
                    onChange={(e) => { setText(e.target.value); setStage(null); setError(null); }}
                    aria-describedby={`size-${submissionId}`} />
          <p id={`size-${submissionId}`} className={size > MAX_EVIDENCE_BYTES ? "notice" : "meta"}>
            {size.toLocaleString()} of {MAX_EVIDENCE_BYTES.toLocaleString()} bytes
          </p>
          <button type="button" className="button secondary" onClick={() => upload()}
                  disabled={busy || size === 0 || size > MAX_EVIDENCE_BYTES}>
            {busy ? "Uploading…" : "Upload message text"}
          </button>
        </div>
      )}
      {stage && <p className={stage === "FINALIZED" ? "success" : "meta"} role="status">{STAGE_LABELS[stage]}</p>}
      {error && <p className="notice" role="alert">{error}</p>}
      <p className="note">The text is stored encrypted for this case. It is analysed only when you choose to analyse it.</p>
      <AnalysisPanel caseId={caseId} submissionId={submissionId}
                     hasFinalized={(items ?? []).filter((e) => e.upload_state === "FINALIZED").length === 1}
                     initialEvaluation={initialEvaluation} initialResult={initialResult} />
    </div>
  );
}
