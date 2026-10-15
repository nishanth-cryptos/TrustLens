// S7 advisory enrichment client (listEvaluationEnrichments, ANALYST only) and the UX-006 presentation rules. Every label and
// meaning below is the exact UX-006 governed text. Enrichment is supporting advisory metadata: it never appears on the
// TrustLens result, never changes a classification, risk or confidence, and an empty or failed list never implies safety.
import { Fetch, get } from "./cases";

export type EnrichmentView = { enrichment_id: string; provider_category: string; status: string; reputation_result: string;
                               observed_at?: string | null; advisory: boolean };
export const ADVISORY_NOTICE = "External lookups are advisory. They come from outside TrustLens and do not change the TrustLens result.";
export const OBSERVED_AT_ABSENT = "Observation time not provided.";
export const ENRICHMENT_TEXT = {
  LOADING: "Loading external lookups…",
  EMPTY: "No external lookup is recorded for this evaluation. This says nothing about whether the message is a scam.",
  UNAVAILABLE: "External lookups could not be loaded. This does not mean there are none.",
  MORE_FAILED: "More lookups could not be loaded. The entries above are unchanged.",
};
type Interpretation = { label: string; meaning: string; providerAssertion: boolean };
const INTERPRETATIONS: Record<string, Interpretation> = {
  "FAILED|NOT_EVALUATED": { label: "Lookup did not complete", providerAssertion: false,
    meaning: "The lookup failed or its response could not be used, so there is no provider assertion." },
  "NOT_EVALUATED|NOT_EVALUATED": { label: "Not looked up", providerAssertion: false, meaning: "No external lookup was made for this indicator." },
  "REJECTED|NOT_EVALUATED": { label: "Lookup not permitted", providerAssertion: false,
    meaning: "TrustLens policy did not allow this lookup, so there is no provider assertion." },
  "SUCCEEDED|CLEAN": { label: "Provider reports no adverse reputation", providerAssertion: true,
    meaning: "An external provider reported no adverse reputation for this indicator at the time shown. This is the provider's assertion only, not a TrustLens judgement." },
  "SUCCEEDED|MALICIOUS": { label: "Provider reports malicious", providerAssertion: true,
    meaning: "An external provider reported this indicator as malicious at the time shown. This is the provider's assertion, not a TrustLens finding." },
  "SUCCEEDED|SUSPICIOUS": { label: "Provider reports suspicious", providerAssertion: true,
    meaning: "An external provider reported this indicator as suspicious at the time shown. This is the provider's assertion, not a TrustLens finding." },
  "SUCCEEDED|UNKNOWN": { label: "No provider assertion", providerAssertion: false,
    meaning: "The lookup finished without a reputation from the provider. Whether the provider had an entry cannot be told from this record." },
  "TIMED_OUT|NOT_EVALUATED": { label: "Lookup timed out", providerAssertion: false,
    meaning: "The provider did not answer in time, so there is no provider assertion." },
};
export const UNRECOGNIZED: Interpretation = { label: "Unrecognized lookup record", providerAssertion: false,
  meaning: "This lookup record could not be interpreted and is not shown as a provider assertion." };

/** UX-006 interpretation: only the governed (status, reputation) pairs; anything else, or a non-advisory record, is unrecognized. */
export const UNRESOLVED_CATEGORY = "NOT_RESOLVED";

export function interpret(view: EnrichmentView): Interpretation {
  // A record whose provider/policy attribution could not be established is never shown as a provider assertion.
  if (view.advisory !== true || !view.provider_category || view.provider_category === UNRESOLVED_CATEGORY) return UNRECOGNIZED;
  return INTERPRETATIONS[`${view.status}|${view.reputation_result}`] ?? UNRECOGNIZED;
}

export const listEnrichments = (evaluationId: string, cursor: string | null = null, fetcher: Fetch = fetch) =>
  get<{ items: EnrichmentView[]; page: { next_cursor?: string | null; limit: number } }>(
    `/api/v1/evaluations/${encodeURIComponent(evaluationId)}/enrichments?limit=20` + (cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""), fetcher);

export type EnrichmentState = { status: "LOADING" | "EMPTY" | "AVAILABLE" | "UNAVAILABLE"; items: EnrichmentView[]; nextCursor: string | null;
                                loadingMore: boolean; moreFailed: boolean };
export const ENRICHMENT_LOADING: EnrichmentState = { status: "LOADING", items: [], nextCursor: null, loadingMore: false, moreFailed: false };

/** Explicit states, cursor pagination without duplicates, stale responses dropped; a failure is never an empty list. */
export function createEnrichmentLoader(evaluationId: string, onChange: (s: EnrichmentState) => void, fetcher: Fetch = fetch) {
  let generation = 0;
  let state = ENRICHMENT_LOADING;
  const set = (next: EnrichmentState) => { state = next; onChange(next); };
  async function first() {
    const mine = ++generation;
    set(ENRICHMENT_LOADING);
    const r = await listEnrichments(evaluationId, null, fetcher);
    if (mine !== generation) return;
    if (r.kind === "error") return set({ ...ENRICHMENT_LOADING, status: "UNAVAILABLE" });
    set({ status: r.value.items.length ? "AVAILABLE" : "EMPTY", items: r.value.items, nextCursor: r.value.page?.next_cursor ?? null,
          loadingMore: false, moreFailed: false });
  }
  async function more() {
    if (!state.nextCursor || state.loadingMore || state.status !== "AVAILABLE") return;
    const mine = generation;
    set({ ...state, loadingMore: true, moreFailed: false });
    const r = await listEnrichments(evaluationId, state.nextCursor, fetcher);
    if (mine !== generation) return;
    if (r.kind === "error") return set({ ...state, loadingMore: false, moreFailed: true });
    const seen = new Set(state.items.map((i) => i.enrichment_id));
    set({ ...state, items: [...state.items, ...r.value.items.filter((i) => !seen.has(i.enrichment_id))],
          nextCursor: r.value.page?.next_cursor ?? null, loadingMore: false });
  }
  return { first, more, cancel: () => { generation++; }, get state() { return state; } };
}
