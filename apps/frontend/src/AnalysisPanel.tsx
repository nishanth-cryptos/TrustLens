import { useEffect, useState } from "react";
import { ACTION_REASON, ACTIONS, AI_STATEMENT, ANALYZE_MESSAGES, AXES, CLASSIFICATIONS, DEGRADED_MEANING, EMPTY_LIST, EvaluationView,
  FAILURE_REASONS, INPUT_SUPPORT, NOT_PROVIDED, Presentation, ResultView, SECTION_TITLES, STATE_LABELS, announcement, createEvaluation,
  getResult, listCaseEvaluations, presentationForError, presentationForStatus, validateResult, waitForEvaluation } from "./evaluation";

type Props = { caseId: string; submissionId: string; hasFinalized: boolean;
               initialEvaluation?: EvaluationView | null; initialResult?: ResultView | null };
type Shown = { evaluation: EvaluationView | null; state: Presentation; result: ResultView | null };

const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString() : "");

function initial(evaluation: EvaluationView | null | undefined, result: ResultView | null | undefined): Shown | null {
  if (evaluation === undefined) return null;
  if (evaluation === null) return { evaluation: null, state: "RESULT_STATUS_UNRESOLVED", result: null };
  const gate = presentationForStatus(evaluation);
  if (gate !== "REQUEST_RESULT") return { evaluation, state: gate, result: null };
  const state = result ? validateResult(result, evaluation.evaluation_id, "STANDARD") : "RESULT_RESPONSE_UNCONFIRMED";
  return { evaluation, state, result: state === "READY" ? result ?? null : null };
}

/** Read the authoritative status, then (only when COMPLETED + AVAILABLE) the STANDARD result; withhold anything else. */
async function present(evaluation: EvaluationView): Promise<Shown> {
  const settled = await waitForEvaluation(evaluation);
  if (settled.kind === "error") return { evaluation, state: "RESULT_STATUS_UNRESOLVED", result: null };
  const gate = presentationForStatus(settled.value);
  if (gate !== "REQUEST_RESULT") return { evaluation: settled.value, state: gate, result: null };
  const response = await getResult(settled.value.evaluation_id, "STANDARD");
  if (response.kind === "error") return { evaluation: settled.value, state: presentationForError(response), result: null };
  const state = validateResult(response.value, settled.value.evaluation_id, "STANDARD");
  return { evaluation: settled.value, state, result: state === "READY" ? response.value : null };   // payload discarded otherwise
}

export default function AnalysisPanel({ caseId, submissionId, hasFinalized, initialEvaluation, initialResult }: Props) {
  const [shown, setShown] = useState<Shown | null>(initial(initialEvaluation, initialResult));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialEvaluation !== undefined) return;
    let live = true;
    listCaseEvaluations(caseId).then(async (r) => {
      if (!live) return;
      if (r.kind === "error") return setShown({ evaluation: null, state: presentationForError(r), result: null });
      const latest = r.value.items.find((e) => e.submission_id === submissionId);      // newest first (server order)
      if (!latest) return setShown(null);
      setShown({ evaluation: latest, state: "ACTION_PENDING", result: null });
      const next = await present(latest);
      if (live) setShown(next);
    });
    return () => { live = false; };
  }, [caseId, submissionId, initialEvaluation]);

  async function analyze() {
    setBusy(true);
    setError(null);
    const previous = shown?.evaluation;
    const retry = previous?.state === "FAILED" && previous.failure?.retry_guidance === "RETRY_AS_NEW_EVALUATION";
    const created = await createEvaluation(submissionId, retry ? { predecessor_evaluation_id: previous.evaluation_id } : {});
    if (created.kind === "error") {
      setBusy(false);
      return setError(ANALYZE_MESSAGES[created.code] ?? ANALYZE_MESSAGES.INTERNAL_ERROR);
    }
    const evaluation = created.value.evaluations[0];
    setShown({ evaluation, state: "ACTION_PENDING", result: null });
    setShown(await present(evaluation));
    setBusy(false);
  }

  const evaluation = shown?.evaluation ?? null;
  const pending = shown?.state === "ACTION_PENDING";
  return (
    <div className="analysis-panel" aria-labelledby={`analysis-${submissionId}`}>
      <h5 id={`analysis-${submissionId}`}>Analysis</h5>
      {!hasFinalized && <p className="meta">Analysis becomes available once one message text is stored and verified.</p>}
      {hasFinalized && (
        <button type="button" className="button" onClick={analyze} disabled={busy || pending}>
          {busy || pending ? "Analysing…" : evaluation ? "Analyze message again" : "Analyze message"}
        </button>
      )}
      {error && <p className="notice" role="alert">{error}</p>}
      {evaluation && (
        <p className="meta">
          {STATE_LABELS[evaluation.state] ?? evaluation.state} · requested {when(evaluation.requested_at)}
          {evaluation.completed_at ? ` · finished ${when(evaluation.completed_at)}` : ""}
        </p>
      )}
      {shown && (
        <div role="status" aria-live="polite" className={shown.state === "READY" ? "meta" : "notice"}>
          {announcement(shown.state, shown.result ?? undefined)}
        </div>
      )}
      {shown?.state === "ACTION_FAILED" && evaluation?.failure && (
        <p className="meta">{FAILURE_REASONS[evaluation.failure.reason] ?? evaluation.failure.reason} This is not a result and not a
          determination that the content is safe.{evaluation.failure.retry_guidance === "RETRY_AS_NEW_EVALUATION" ? " You can analyse it again as a new evaluation." : ""}</p>
      )}
      {shown?.state === "READY" && shown.result && evaluation && <ResultSections result={shown.result} evaluation={evaluation} />}
    </div>
  );
}

function List({ items }: { items: string[] }) {
  return items.length === 0 ? <p className="meta">{EMPTY_LIST}</p> : <ul>{items.map((item, i) => <li key={i}>{item}</li>)}</ul>;
}

function Rule({ rule }: { rule: RuleReferenceLike }) {
  return <><code>{rule.rule_id}</code> v{rule.rule_version}</>;
}
type RuleReferenceLike = { rule_id: string; rule_version: string; source_references?: string[] };

export function ResultSections({ result, evaluation }: { result: ResultView; evaluation: EvaluationView }) {
  const classification = CLASSIFICATIONS[result.classification];
  const support = INPUT_SUPPORT[result.input_support_status];
  const sources = Array.from(new Set([...(result.governing_rule?.source_references ?? []),
    ...result.matched_rules.flatMap((r) => r.source_references ?? [])]));
  return (
    <article className="result" aria-label="Analysis result">
      <section>
        <h6>{SECTION_TITLES.A}</h6>
        <p className="classification"><strong>{classification.label}</strong> <code>{result.classification}</code></p>
        <p>{classification.meaning}</p>
      </section>
      <section>
        <h6>{SECTION_TITLES.B}</h6>
        <p><strong>{support.label}</strong> <code>{result.input_support_status}</code> — {support.meaning}</p>
        <p className="meta">Language: {result.language.join(", ")} · script: {result.script.join(", ")}</p>
      </section>
      <section>
        <h6>{SECTION_TITLES.C}</h6>
        <dl className="axes">
          {AXES.map((axis) => (
            <div key={axis.field}>
              <dt>{axis.label}</dt>
              <dd><strong>{result[axis.field]}</strong> <span className="meta">— {axis.question}</span></dd>
            </div>
          ))}
        </dl>
      </section>
      <section>
        <h6>{SECTION_TITLES.D}</h6>
        <p>{result.explanation.summary}</p>
        {result.explanation.evidence_basis === undefined ? <p className="meta">{NOT_PROVIDED}</p> : (
          result.explanation.evidence_basis.length === 0 ? <p className="meta">{EMPTY_LIST}</p> : (
            <ul className="sources">{result.explanation.evidence_basis.map((s, i) => <li key={i}><blockquote>{s}</blockquote></li>)}</ul>))}
      </section>
      <section>
        <h6>{SECTION_TITLES.E}</h6>
        <p>Governing rule: {result.governing_rule ? <Rule rule={result.governing_rule} /> : <span className="meta">{NOT_PROVIDED}</span>}</p>
        {result.matched_rules.length === 0 ? <p className="meta">{EMPTY_LIST}</p> : (
          <ul>{result.matched_rules.map((r) => <li key={r.rule_id}><Rule rule={r} /></li>)}</ul>)}
      </section>
      <section>
        <h6>{SECTION_TITLES.F}</h6>
        {sources.length === 0 ? <p className="meta">{EMPTY_LIST}</p> : <p>{sources.map((s) => <code key={s}>{s} </code>)}</p>}
        <p className="meta">Observations and indicator identities are not exposed by this result.</p>
      </section>
      <section>
        <h6>{SECTION_TITLES.H}</h6>
        <p className="meta">Unknowns</p><List items={result.unknowns} />
        <p className="meta">Ambiguities</p><List items={result.ambiguities} />
        <p className="meta">Limitations</p><List items={result.limitations} />
        {result.degraded && <p className="notice">{DEGRADED_MEANING}</p>}
      </section>
      <section>
        <h6>{SECTION_TITLES.I}</h6>
        {result.recommended_actions.length === 0 ? <p className="meta">{EMPTY_LIST}</p> : (
          <ul>{result.recommended_actions.filter((a) => a.action_code in ACTIONS).map((a) => <li key={a.action_code}>{ACTIONS[a.action_code]}</li>)}</ul>)}
        {result.recommended_actions.some((a) => !(a.action_code in ACTIONS)) && <p className="meta">A recommended action could not be presented.</p>}
        <p className="meta">{ACTION_REASON}</p>
      </section>
      <section>
        <h6>{SECTION_TITLES.J}</h6>
        <dl className="principal">
          <dt>Engine</dt><dd>{result.provenance.engine_version} (result contract {result.result_contract_version})</dd>
          <dt>Knowledge bundle</dt><dd>{result.provenance.bundle_version} · <code>{result.provenance.bundle_content_digest.slice(0, 16)}…</code></dd>
          <dt>Evaluation profile</dt><dd>{result.provenance.evaluation_profile_id}</dd>
          <dt>Evaluated</dt><dd>{when(result.provenance.evaluation_timestamp)}</dd>
          <dt>Result digest</dt><dd><code>{result.result_digest.slice(0, 16)}…</code></dd>
          <dt>View</dt><dd>{result.view}</dd>
          <dt>AI used</dt><dd>{evaluation.ai_usage.used ? "Yes" : "No"}{evaluation.ai_usage.fallback_reason ? ` (${evaluation.ai_usage.fallback_reason})` : ""}</dd>
        </dl>
        <p className="meta">{AI_STATEMENT}</p>
      </section>
      <section>
        <h6>{SECTION_TITLES.K}</h6>
        {result.not_an_official_determination && <p>This result is not an official determination.</p>}
        {result.absence_of_finding_notice && <p className="notice">{result.absence_of_finding_notice}</p>}
      </section>
    </article>
  );
}
