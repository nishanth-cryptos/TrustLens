import { useEffect, useRef, useState } from "react";
import { ADVISORY_NOTICE, ENRICHMENT_LOADING, ENRICHMENT_TEXT, EnrichmentState, OBSERVED_AT_ABSENT, createEnrichmentLoader,
  interpret } from "./enrichment";

type Props = { evaluationId: string; initialState?: EnrichmentState };

const when = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleString() : null);

/** Advisory external lookups for one evaluation (assigned analysts only; the backend decides). Kept apart from the result. */
export default function EnrichmentPanel({ evaluationId, initialState }: Props) {
  const [state, setState] = useState<EnrichmentState>(initialState ?? ENRICHMENT_LOADING);
  const loader = useRef<ReturnType<typeof createEnrichmentLoader> | null>(null);

  useEffect(() => {
    if (initialState) return;
    const current = createEnrichmentLoader(evaluationId, setState);
    loader.current = current;
    current.first();
    return () => current.cancel();
  }, [evaluationId, initialState]);

  return (
    <section className="enrichment" aria-label="External lookups (advisory)" aria-busy={state.status === "LOADING" || state.loadingMore}>
      <h6>External lookups (advisory)</h6>
      <p className="meta">{ADVISORY_NOTICE}</p>
      {state.status === "LOADING" && <p className="meta" role="status">{ENRICHMENT_TEXT.LOADING}</p>}
      {state.status === "EMPTY" && <p className="meta" role="status">{ENRICHMENT_TEXT.EMPTY}</p>}
      {state.status === "UNAVAILABLE" && (
        <p className="notice" role="alert">{ENRICHMENT_TEXT.UNAVAILABLE}{" "}
          <button type="button" className="link-button" onClick={() => loader.current?.first()}>Try again</button></p>
      )}
      {state.status === "AVAILABLE" && (
        <ul className="enrichment-list">
          {state.items.map((item) => {
            const meaning = interpret(item);
            return (
              <li key={item.enrichment_id}>
                <strong>{meaning.label}</strong> <span className="meta">· {item.provider_category}</span>
                <p className="meta">{meaning.meaning}</p>
                <p className="meta">{when(item.observed_at) ?? OBSERVED_AT_ABSENT}</p>
              </li>
            );
          })}
        </ul>
      )}
      {state.moreFailed && <p className="notice" role="alert">{ENRICHMENT_TEXT.MORE_FAILED}</p>}
      {state.status === "AVAILABLE" && state.nextCursor && (
        <button type="button" className="link-button" onClick={() => loader.current?.more()} disabled={state.loadingMore}>
          {state.loadingMore ? "Loading…" : "Load more lookups"}
        </button>
      )}
    </section>
  );
}
