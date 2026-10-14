// Governed knowledge status: the accepted read operation getActiveKnowledge (roles ANALYST, KNOWLEDGE_EDITOR,
// KNOWLEDGE_APPROVER, ADMINISTRATOR). It reports the deployment's recorded state only; it never claims analysis is
// available (S5 is not implemented) and never shows rule content.
import { Fetch, Result, get } from "./cases";

export const KNOWLEDGE_READERS = ["ANALYST", "KNOWLEDGE_EDITOR", "KNOWLEDGE_APPROVER", "ADMINISTRATOR"];

export type KnowledgeBundle = {
  content_digest: string; bundle_version: string; manifest_schema_version: string; commit_sha?: string | null;
  governance_eligibility: string;
};
export type ActiveKnowledge = { deployment_state: string; active_bundle?: KnowledgeBundle | null; state_changed_at: string };

export const canReadKnowledge = (roles: string[]) => roles.some((r) => KNOWLEDGE_READERS.includes(r));

export const DEPLOYMENT_STATE_LABELS: Record<string, string> = {
  NO_ACTIVE_BUNDLE: "No governed knowledge bundle is active for this deployment, so governed analysis cannot run.",
  ACTIVE: "A governed knowledge bundle is recorded as active for this deployment.",
  ACTIVE_BUNDLE_WITHDRAWN: "The active knowledge bundle has been withdrawn. New analysis is blocked until a governed replacement is activated.",
};
export const ELIGIBILITY_LABELS: Record<string, string> = {
  ELIGIBLE: "eligible", WITHDRAWN: "withdrawn", UNKNOWN: "eligibility not established",
};

export const getActiveKnowledge = (fetcher: Fetch = fetch): Promise<Result<ActiveKnowledge>> =>
  get<ActiveKnowledge>("/api/v1/knowledge/active", fetcher);
