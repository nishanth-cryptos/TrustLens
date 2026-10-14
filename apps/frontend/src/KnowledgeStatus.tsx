import { useEffect, useState } from "react";
import { ActiveKnowledge, DEPLOYMENT_STATE_LABELS, ELIGIBILITY_LABELS, getActiveKnowledge } from "./knowledge";

type Props = { initial?: ActiveKnowledge | null };

export default function KnowledgeStatus({ initial }: Props) {
  const [status, setStatus] = useState<ActiveKnowledge | null>(initial ?? null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initial !== undefined) return;
    getActiveKnowledge().then((r) => (r.kind === "ok" ? setStatus(r.value) : setError("Knowledge status is unavailable right now.")));
  }, [initial]);

  const bundle = status?.active_bundle;
  return (
    <section className="knowledge-status" aria-labelledby="knowledge-title">
      <h2 id="knowledge-title">Governed analysis knowledge</h2>
      {status === null && !error && <p>Checking knowledge status…</p>}
      {error && <p className="notice" role="alert">{error}</p>}
      {status && <p role="status">{DEPLOYMENT_STATE_LABELS[status.deployment_state] ?? status.deployment_state}</p>}
      {bundle && (
        <dl className="principal">
          <dt>Bundle version</dt><dd>{bundle.bundle_version}</dd>
          <dt>Content digest</dt><dd><code>{bundle.content_digest.slice(0, 16)}…</code></dd>
          <dt>Governance</dt><dd>{ELIGIBILITY_LABELS[bundle.governance_eligibility] ?? bundle.governance_eligibility}</dd>
        </dl>
      )}
      <p className="note">
        This shows the recorded deployment state only. Analysis is not part of this version, and nothing here is a
        result about any message.
      </p>
    </section>
  );
}
