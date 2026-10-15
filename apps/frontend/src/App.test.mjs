import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const server = await createServer({ server: { middlewareMode: true }, appType: "custom" });
let App, auth, Workspace, submissionLabels, cases, evidence, KnowledgeStatus, knowledge, evaluation, AnalysisPanel, history, HistoryPanel,
  EvidencePanel, enrichmentClient, EnrichmentPanel;
try {
  ({ default: App } = await server.ssrLoadModule("/src/App.tsx"));
  auth = await server.ssrLoadModule("/src/auth.ts");
  ({ default: Workspace, SUBMISSION_STATE_LABELS: submissionLabels } = await server.ssrLoadModule("/src/Workspace.tsx"));
  cases = await server.ssrLoadModule("/src/cases.ts");
  evidence = await server.ssrLoadModule("/src/evidence.ts");
  ({ default: KnowledgeStatus } = await server.ssrLoadModule("/src/KnowledgeStatus.tsx"));
  knowledge = await server.ssrLoadModule("/src/knowledge.ts");
  evaluation = await server.ssrLoadModule("/src/evaluation.ts");
  ({ default: AnalysisPanel } = await server.ssrLoadModule("/src/AnalysisPanel.tsx"));
  history = await server.ssrLoadModule("/src/history.ts");
  ({ default: HistoryPanel } = await server.ssrLoadModule("/src/HistoryPanel.tsx"));
  ({ default: EvidencePanel } = await server.ssrLoadModule("/src/EvidencePanel.tsx"));
  enrichmentClient = await server.ssrLoadModule("/src/enrichment.ts");
  ({ default: EnrichmentPanel } = await server.ssrLoadModule("/src/EnrichmentPanel.tsx"));
} finally {
  await server.close();
}

const render = (props) => renderToStaticMarkup(createElement(App, props));
const me = { principal_id: "5d1c8f0e-7a43-4b8e-9c6d-2e1f0a9b8c7d", principal_kind: "HUMAN", roles: ["USER"], capabilities: [] };

test("signed-out screen offers a real Keycloak sign-in navigation", () => {
  const html = render({ initialState: { kind: "signed-out" } });
  assert.match(html, /TrustLens/);
  assert.match(html, /<a class="button" href="\/auth\/login">Sign in with Keycloak<\/a>/);
  assert.doesNotMatch(html, /Sign out/);
});

test("signed-in screen shows principal information from /api/v1/me and a sign-out action", () => {
  const html = render({ initialState: { kind: "signed-in", me } });
  assert.match(html, /You are signed in/);
  assert.match(html, /Person/);
  assert.match(html, /<dd>User<\/dd>/);
  assert.match(html, /5d1c8f0e-7a43-4b8e-9c6d-2e1f0a9b8c7d/);
  assert.match(html, /<button type="button" class="button secondary">Sign out<\/button>/);
  assert.doesNotMatch(html, /\/auth\/login/);
});

test("an unprovisioned identity sees a non-sensitive access message", () => {
  const html = render({ initialState: { kind: "signed-out" }, initialNotice: "denied" });
  assert.match(html, /role="alert"/);
  assert.match(html, /has not been given access/);
});

test("unavailable state never implies a signed-in session", () => {
  const html = render({ initialState: { kind: "unavailable" } });
  assert.match(html, /temporarily unavailable/);
  assert.doesNotMatch(html, /Sign out|You are signed in/);
});

test("collects no content and keeps no credential in browser storage", () => {
  for (const state of [{ kind: "signed-out" }, { kind: "signed-in", me }, { kind: "unavailable" }, { kind: "loading" }]) {
    assert.doesNotMatch(render({ initialState: state }), /<(form|input|textarea|iframe)\b/);
  }
  const code = (file) => readFileSync(new URL(file, import.meta.url), "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  const source = code("./App.tsx") + code("./auth.ts") + code("./cases.ts") + code("./Workspace.tsx") + code("./evidence.ts")
    + code("./EvidencePanel.tsx") + code("./knowledge.ts") + code("./KnowledgeStatus.tsx") + code("./evaluation.ts")
    + code("./AnalysisPanel.tsx") + code("./history.ts") + code("./HistoryPanel.tsx") + code("./enrichment.ts") + code("./EnrichmentPanel.tsx");
  for (const forbidden of [/localStorage/, /sessionStorage/, /indexedDB/i, /document\.cookie/, /Authorization/,
                           /access_token|id_token|refresh_token/, /console\./]) {
    assert.doesNotMatch(source, forbidden);
  }
});

function fakeFetch(responses) {
  const calls = [];
  const fetcher = async (url, init = {}) => {
    calls.push({ url, init });
    const [status, body] = responses[url];
    return { status, ok: status >= 200 && status < 300, json: async () => body };
  };
  return { fetcher, calls };
}

test("session loading maps 200, 401 and failures to explicit states", async () => {
  let f = fakeFetch({ "/api/v1/me": [200, me] });
  assert.deepEqual(await auth.loadSession(f.fetcher), { kind: "signed-in", me });
  assert.equal(f.calls[0].init.credentials, "same-origin");
  assert.deepEqual(await auth.loadSession(fakeFetch({ "/api/v1/me": [401, {}] }).fetcher), { kind: "signed-out" });
  assert.deepEqual(await auth.loadSession(fakeFetch({ "/api/v1/me": [503, {}] }).fetcher), { kind: "unavailable" });
  assert.deepEqual(await auth.loadSession(fakeFetch({ "/api/v1/me": [200, { roles: "USER" }] }).fetcher), { kind: "unavailable" });
});

test("sign-out sends the CSRF token in a header on a same-origin POST", async () => {
  const f = fakeFetch({ "/auth/csrf": [200, { csrf_token: "synthetic-csrf" }], "/auth/logout": [200, { status: "SIGNED_OUT" }] });
  assert.equal(await auth.signOut(f.fetcher), true);
  const post = f.calls[1];
  assert.equal(post.url, "/auth/logout");
  assert.equal(post.init.method, "POST");
  assert.equal(post.init.credentials, "same-origin");
  assert.equal(post.init.headers["X-CSRF-Token"], "synthetic-csrf");
});

test("sign-in outcome is categorical and removed from the address bar", () => {
  assert.equal(auth.readSigninNotice("?signin=denied"), "denied");
  assert.equal(auth.readSigninNotice("?signin=<script>"), "failed");
  assert.equal(auth.readSigninNotice(""), null);
  let replaced = null;
  auth.clearSigninNotice({ search: "?signin=failed&x=1", pathname: "/", hash: "" }, { replaceState: (_s, _t, url) => { replaced = url; } });
  assert.equal(replaced, "/?x=1");
});

const aCase = { case_id: "2b1f8c3e-5d6a-4f7b-8c9d-0e1f2a3b4c5d", state: "OPEN", is_synthetic: true, created_at: "2026-10-14T09:00:00Z",
  closed_at: null, viewer_access: { relationship: "OWNER", can_view_evidence_content: true }, etag: '"x"' };
const aSubmission = { submission_id: "7c6b5a49-3827-4161-9e0f-1a2b3c4d5e6f", case_id: aCase.case_id, declared_input_type: "SMS",
  state: "RECEIVING", received_at: "2026-10-14T09:01:00Z", is_synthetic: true };

test("workspace lists cases and submissions; text entry appears only for a chosen submission", () => {
  const html = renderToStaticMarkup(createElement(Workspace, { initialCases: [aCase], initialSubmissions: [aSubmission], initialSelected: aCase.case_id }));
  assert.match(html, /Your cases/);
  assert.match(html, /Create a case/);
  assert.match(html, /synthetic test data/);
  assert.match(html, /Text message \(SMS\) · Open for evidence/);
  assert.match(html, /Record submission/);
  assert.match(html, /not official\s+determinations/);
  assert.doesNotMatch(html, /<(form|input|textarea|iframe)\b/);
  assert.doesNotMatch(html, /risk|score|verdict|safe|scam detected/i);
});

test("an analyst's view offers no submission form", () => {
  const analystCase = { ...aCase, viewer_access: { relationship: "ASSIGNED_ANALYST", can_view_evidence_content: false } };
  const html = renderToStaticMarkup(createElement(Workspace, { initialCases: [analystCase], initialSelected: aCase.case_id }));
  assert.doesNotMatch(html, /Record submission/);
});

function scripted(responses) {
  const calls = [];
  const fetcher = async (url, init = {}) => {
    calls.push({ url, init });
    const next = responses.shift();
    if (next instanceof Error) throw next;
    const [status, body, headers = {}] = next;
    return { status, ok: status >= 200 && status < 300, json: async () => body, headers: new Headers(headers) };
  };
  return { fetcher, calls };
}

test("create sends CSRF token and one Idempotency-Key reused across bounded retries", async () => {
  const s = scripted([[200, { csrf_token: "t1" }], [503, { error: { code: "DEPENDENCY_UNAVAILABLE" } }],
                      [200, { csrf_token: "t2" }], [201, aCase]]);
  let n = 0;
  const result = await cases.createCase(s.fetcher, () => `synthetic-key-${++n}-abcdefghijkl`);
  assert.equal(result.kind, "ok");
  const posts = s.calls.filter((c) => c.init.method === "POST");
  assert.equal(posts.length, 2);
  assert.equal(posts[0].init.headers["Idempotency-Key"], posts[1].init.headers["Idempotency-Key"]);
  assert.deepEqual([posts[0].init.headers["X-CSRF-Token"], posts[1].init.headers["X-CSRF-Token"]], ["t1", "t2"]);
  assert.equal(n, 1);
});

test("retries are bounded and non-retryable errors stop immediately", async () => {
  const unavailable = [503, { error: { code: "DEPENDENCY_UNAVAILABLE" } }];
  const s = scripted([[200, { csrf_token: "t" }], unavailable, [200, { csrf_token: "t" }], unavailable, [200, { csrf_token: "t" }], unavailable]);
  const result = await cases.createCase(s.fetcher, () => "synthetic-key-abcdefghijklmnop");
  assert.equal(result.kind, "error");
  assert.equal(s.calls.filter((c) => c.init.method === "POST").length, 3);
  const f = scripted([[200, { csrf_token: "t" }], [403, { error: { code: "FORBIDDEN" } }]]);
  assert.equal((await cases.createCase(f.fetcher, () => "synthetic-key-abcdefghijklmnop")).code, "FORBIDDEN");
  assert.equal(f.calls.length, 2);
});

test("submission requests carry categorical metadata only", async () => {
  const s = scripted([[200, { csrf_token: "t" }], [201, aSubmission]]);
  await cases.createSubmission(aCase.case_id, "SMS", "RECEIVED", s.fetcher, () => "synthetic-key-abcdefghijklmnop");
  assert.deepEqual(JSON.parse(s.calls[1].init.body), { declared_input_type: "SMS", relationship_to_content: "RECEIVED" });
  assert.equal(s.calls[1].url, `/api/v1/cases/${aCase.case_id}/submissions`);
});

const SMS = "SYNTHETIC TEST: your parcel is held, pay 1.99 at http://example.invalid é";
const evidenceView = (state, extra = {}) => ({ evidence_id: "9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d", submission_id: aSubmission.submission_id,
  artifact_kind: "TEXT_BODY", upload_state: state, content_sha256: null, byte_length: null, declared_media_type: "text/plain; charset=utf-8",
  verified_media_type: null, display_filename: null, ingested_at: "2026-10-14T09:02:00Z", finalized_at: null, ...extra });

test("an owner's chosen submission offers one text box with a byte counter and honest labels", () => {
  const stored = evidenceView("FINALIZED", { byte_length: 57, content_sha256: "ab".repeat(32), finalized_at: "2026-10-14T09:03:00Z" });
  const html = renderToStaticMarkup(createElement(Workspace, { initialCases: [aCase], initialSubmissions: [aSubmission],
    initialSelected: aCase.case_id, initialSubmission: aSubmission.submission_id, initialEvidence: [stored] }));
  assert.equal(html.match(/<textarea\b/g).length, 1);
  assert.doesNotMatch(html, /<(form|input|iframe)\b/);
  assert.match(html, /synthetic test data only/);
  assert.match(html, /0 of 65,536 bytes/);
  assert.match(html.replace(/<\/?(span|code)[^>]*>/g, ""), /Stored and verified · 57 bytes · SHA-256 abababababab…/);
  assert.match(html, /analysed only when you choose to analyse it/);
  assert.match(html, /Analyze message<\/button>/);                       // one finalized text: the analysis action is offered
  assert.doesNotMatch(html, /risk|score|verdict|safe|scam detected|report ready/i);
});

test("an analyst sees evidence metadata but no text box", () => {
  const analystCase = { ...aCase, viewer_access: { relationship: "ASSIGNED_ANALYST", can_view_evidence_content: false } };
  const html = renderToStaticMarkup(createElement(Workspace, { initialCases: [analystCase], initialSubmissions: [aSubmission],
    initialSelected: aCase.case_id, initialSubmission: aSubmission.submission_id, initialEvidence: [evidenceView("PROCESSING")] }));
  assert.doesNotMatch(html, /<textarea\b/);
  assert.match(html, /Being stored/);
});

test("byte length is UTF-8, not characters", () => {
  assert.equal(evidence.utf8Bytes("é中").length, 5);
});

const keys = () => { let n = 0; return () => `synthetic-key-${++n}-abcdefghijkl`; };
const noSleep = async () => {};

test("three-step upload: intent, exact UTF-8 bytes with CSRF, finalize with a new key", async () => {
  const s = scripted([[200, { csrf_token: "a" }], [201, evidenceView("AWAITING_CONTENT")],
                      [200, { csrf_token: "b" }], [200, evidenceView("PROCESSING")],
                      [200, { csrf_token: "c" }], [202, evidenceView("FINALIZED", { finalized_at: "2026-10-14T09:03:00Z" })]]);
  const stages = [];
  const result = await evidence.uploadText(aSubmission.submission_id, SMS, { fetcher: s.fetcher, newKey: keys(), sleep: noSleep,
                                                                             onStage: (x) => stages.push(x) });
  assert.equal(result.stage, "FINALIZED");
  assert.deepEqual(stages, ["PREPARING", "SENDING", "CHECKING"]);
  const [intent, put, finalize] = s.calls.filter((c) => c.init.method);
  const declared = JSON.parse(intent.init.body);
  const bytes = new TextEncoder().encode(SMS);
  assert.deepEqual(Object.keys(declared).sort(), ["artifact_kind", "client_declared_sha256", "declared_byte_length", "declared_media_type"]);
  assert.equal(declared.declared_byte_length, bytes.length);
  assert.match(declared.client_declared_sha256, /^[0-9a-f]{64}$/);
  assert.doesNotMatch(intent.init.body, /parcel/);                       // text never travels in JSON
  assert.equal(put.init.method, "PUT");
  assert.equal(put.init.headers["Content-Type"], "text/plain; charset=utf-8");
  assert.equal(put.init.headers["X-CSRF-Token"], "b");
  assert.deepEqual(Array.from(put.init.body), Array.from(bytes));
  assert.equal(put.init.headers["Idempotency-Key"], undefined);
  assert.notEqual(intent.init.headers["Idempotency-Key"], finalize.init.headers["Idempotency-Key"]);
  assert.equal(finalize.url, `/api/v1/evidence/${evidenceView().evidence_id}/finalize`);
});

test("status polling is bounded and never claims completion", async () => {
  const processing = [200, evidenceView("PROCESSING")];
  const s = scripted([[200, { csrf_token: "a" }], [201, evidenceView("AWAITING_CONTENT")], [200, { csrf_token: "b" }], processing,
                      [200, { csrf_token: "c" }], [202, evidenceView("PROCESSING")], ...Array(20).fill(processing)]);
  const result = await evidence.uploadText(aSubmission.submission_id, SMS, { fetcher: s.fetcher, newKey: keys(), sleep: noSleep });
  assert.equal(result.stage, "STILL_PROCESSING");
  assert.equal(s.calls.filter((c) => !c.init.method && c.url.startsWith("/api/v1/evidence/")).length, 10);
  assert.match(evidence.STAGE_LABELS.STILL_PROCESSING, /Reload later/);
});

test("content retries honour Retry-After, are bounded, and oversize text is refused locally", async () => {
  const busy = [503, { error: { code: "DEPENDENCY_UNAVAILABLE" } }, { "Retry-After": "2" }];
  const s = scripted([[200, { csrf_token: "a" }], [201, evidenceView("AWAITING_CONTENT")],
                      [200, { csrf_token: "b" }], busy, [200, { csrf_token: "b" }], busy, [200, { csrf_token: "b" }], busy]);
  const waits = [];
  const result = await evidence.uploadText(aSubmission.submission_id, SMS, { fetcher: s.fetcher, newKey: keys(),
                                                                             sleep: async (ms) => waits.push(ms) });
  assert.equal(result.stage, "FAILED");
  assert.equal(s.calls.filter((c) => c.init.method === "PUT").length, 3);
  assert.deepEqual(waits, [2000, 2000]);
  const none = scripted([]);
  const big = await evidence.uploadText(aSubmission.submission_id, "x".repeat(64 * 1024 + 1), { fetcher: none.fetcher });
  assert.equal(big.error.code, "PAYLOAD_TOO_LARGE");
  assert.equal(none.calls.length, 0);
});

test("a rejected upload is reported as not stored", async () => {
  const s = scripted([[200, { csrf_token: "a" }], [201, evidenceView("AWAITING_CONTENT")], [200, { csrf_token: "b" }],
                      [200, evidenceView("PROCESSING")], [200, { csrf_token: "c" }], [500, { error: { code: "INTEGRITY_FAILURE" } }],
                      [200, evidenceView("REJECTED")]]);
  const result = await evidence.uploadText(aSubmission.submission_id, SMS, { fetcher: s.fetcher, newKey: keys(), sleep: noSleep });
  assert.equal(result.stage, "REJECTED");
  assert.match(result.error.message, /did not match/);
  assert.doesNotMatch(evidence.STAGE_LABELS.REJECTED + evidence.STAGE_LABELS.FINALIZED, /safe|verdict|score|risk/i);
});

test("a failure after the upload record exists never claims nothing was saved", async () => {
  const busy = [503, { error: { code: "DEPENDENCY_UNAVAILABLE" } }, { "Retry-After": "1" }];
  const s = scripted([[200, { csrf_token: "a" }], [201, evidenceView("AWAITING_CONTENT")],
                      [200, { csrf_token: "b" }], busy, [200, { csrf_token: "b" }], busy, [200, { csrf_token: "b" }], busy]);
  const result = await evidence.uploadText(aSubmission.submission_id, SMS, { fetcher: s.fetcher, newKey: keys(), sleep: noSleep });
  assert.equal(result.stage, "FAILED");
  assert.equal(result.evidence.evidence_id, evidenceView().evidence_id);          // the record exists and is reported
  assert.match(result.error.message, /details are saved/);
  assert.match(result.error.message, /not been stored/);
  assert.doesNotMatch(result.error.message, /nothing was saved/i);
  assert.doesNotMatch(cases.MESSAGES.DEPENDENCY_UNAVAILABLE, /nothing was saved/i);
});

test("a finalize failure says the text is not verified, never finalized", async () => {
  const unavailable = [503, { error: { code: "DEPENDENCY_UNAVAILABLE" } }];
  const s = scripted([[200, { csrf_token: "a" }], [201, evidenceView("AWAITING_CONTENT")], [200, { csrf_token: "b" }],
                      [200, evidenceView("PROCESSING")], [200, { csrf_token: "c" }], unavailable, [200, { csrf_token: "c" }],
                      unavailable, [200, { csrf_token: "c" }], unavailable, ...Array(10).fill([200, evidenceView("PROCESSING")])]);
  const result = await evidence.uploadText(aSubmission.submission_id, SMS, { fetcher: s.fetcher, newKey: keys(), sleep: noSleep });
  assert.equal(result.stage, "STILL_PROCESSING");
  assert.match(result.error.message, /not been verified/);
  assert.doesNotMatch(result.error.message, /stored and verified|finalized|nothing was saved/i);
});

test("an unfinished upload can be resumed with the same text and offers a continue action", async () => {
  const pending = evidenceView("AWAITING_CONTENT");
  const s = scripted([[200, { csrf_token: "b" }], [200, evidenceView("PROCESSING")], [200, { csrf_token: "c" }],
                      [202, evidenceView("FINALIZED", { finalized_at: "2026-10-14T09:03:00Z" })]]);
  const result = await evidence.resumeUpload(pending, SMS, { fetcher: s.fetcher, newKey: keys(), sleep: noSleep });
  assert.equal(result.stage, "FINALIZED");
  assert.equal(s.calls.filter((c) => c.init.method === "POST" && c.url.endsWith("/evidence")).length, 0);   // no new upload
  assert.equal(s.calls.find((c) => c.init.method === "PUT").url, `/api/v1/evidence/${pending.evidence_id}/content`);
  const different = scripted([[200, { csrf_token: "b" }], [409, { error: { code: "STATE_CONFLICT" } }]]);
  const conflict = await evidence.resumeUpload(evidenceView("PROCESSING"), "other text", { fetcher: different.fetcher, sleep: noSleep });
  assert.match(conflict.error.message, /already holds different message text/);
  const html = renderToStaticMarkup(createElement(Workspace, { initialCases: [aCase], initialSubmissions: [aSubmission],
    initialSelected: aCase.case_id, initialSubmission: aSubmission.submission_id, initialEvidence: [pending] }));
  assert.match(html, /Continue this upload/);
  const done = renderToStaticMarkup(createElement(Workspace, { initialCases: [aCase], initialSubmissions: [aSubmission],
    initialSelected: aCase.case_id, initialSubmission: aSubmission.submission_id,
    initialEvidence: [evidenceView("FINALIZED", { finalized_at: "2026-10-14T09:03:00Z" })] }));
  assert.doesNotMatch(done, /Continue this upload/);
});

test("a submission with finalized evidence never reads as waiting for evidence", () => {
  const stored = evidenceView("FINALIZED", { byte_length: 57, content_sha256: "cd".repeat(32), finalized_at: "2026-10-14T09:03:00Z" });
  const html = renderToStaticMarkup(createElement(Workspace, { initialCases: [aCase], initialSubmissions: [aSubmission],
    initialSelected: aCase.case_id, initialSubmission: aSubmission.submission_id, initialEvidence: [stored] }));
  assert.equal(aSubmission.state, "RECEIVING");                          // backend state unchanged: still open for intake
  assert.doesNotMatch(html, /Waiting for evidence/i);
  assert.match(html, /Text message \(SMS\) · Open for evidence/);
  assert.match(html.replace(/<\/?(span|code)[^>]*>/g, ""), /Stored and verified · 57 bytes · SHA-256 cdcdcdcdcdcd…/);
});

test("every accepted submission state has a truthful label distinct from evidence content state", () => {
  const catalog = JSON.parse(readFileSync(new URL("../../../contracts/api/api-v1.json", import.meta.url), "utf8"));
  const states = catalog.vocabularies.api_submission_state.values;
  const labels = submissionLabels;
  assert.deepEqual(Object.keys(labels).sort(), [...states].sort());
  for (const label of Object.values(labels)) {
    assert.doesNotMatch(label, /waiting|missing|no evidence|safe|verdict|score|risk|analys/i);
  }
  for (const state of states) {
    const html = renderToStaticMarkup(createElement(Workspace, { initialCases: [aCase], initialSubmissions: [{ ...aSubmission, state }],
      initialSelected: aCase.case_id }));
    assert.match(html, new RegExp(` · ${labels[state]} · received`));
  }
});

const bundle = { content_digest: "ab".repeat(32), bundle_version: "1.0.0", manifest_schema_version: "1.1.0", commit_sha: null,
  governance_eligibility: "ELIGIBLE" };

test("knowledge status is shown only to knowledge-read roles", () => {
  const userHtml = render({ initialState: { kind: "signed-in", me: { ...me, roles: ["USER"] } } });
  assert.doesNotMatch(userHtml, /Governed analysis knowledge/);
  for (const role of ["ANALYST", "KNOWLEDGE_EDITOR", "KNOWLEDGE_APPROVER", "ADMINISTRATOR"]) {
    assert.match(render({ initialState: { kind: "signed-in", me: { ...me, roles: [role] } } }), /Governed analysis knowledge/, role);
  }
});

test("knowledge states are stated honestly and never as an analysis result", () => {
  const none = renderToStaticMarkup(createElement(KnowledgeStatus, { initial: { deployment_state: "NO_ACTIVE_BUNDLE", active_bundle: null,
    state_changed_at: "2026-10-14T10:00:00Z" } }));
  assert.match(none, /No governed knowledge bundle is active/);
  const active = renderToStaticMarkup(createElement(KnowledgeStatus, { initial: { deployment_state: "ACTIVE", active_bundle: bundle,
    state_changed_at: "2026-10-14T10:00:00Z" } }));
  assert.match(active, /recorded as active/);
  assert.match(active, /1\.0\.0/);
  assert.match(active, /abababababababab…/);
  assert.match(active, /eligible/);
  const withdrawn = renderToStaticMarkup(createElement(KnowledgeStatus, { initial: { deployment_state: "ACTIVE_BUNDLE_WITHDRAWN",
    active_bundle: { ...bundle, governance_eligibility: "WITHDRAWN" }, state_changed_at: "2026-10-14T10:00:00Z" } }));
  assert.match(withdrawn, /withdrawn\. New analysis is blocked/);
  for (const html of [none, active, withdrawn]) {
    assert.doesNotMatch(html, /\bready\b|verdict|score|\bsafe\b|risk|scam detected|no scam/i);
    assert.match(html, /nothing here is a\s+result about any message/);
  }
});

test("knowledge status uses only the accepted read operation", async () => {
  const s = scripted([[200, { deployment_state: "NO_ACTIVE_BUNDLE", active_bundle: null, state_changed_at: "2026-10-14T10:00:00Z" }]]);
  const r = await knowledge.getActiveKnowledge(s.fetcher);
  assert.equal(r.kind, "ok");
  assert.deepEqual(s.calls.map((c) => [c.url, c.init.method ?? "GET"]), [["/api/v1/knowledge/active", "GET"]]);
  assert.deepEqual(knowledge.KNOWLEDGE_READERS, ["ANALYST", "KNOWLEDGE_EDITOR", "KNOWLEDGE_APPROVER", "ADMINISTRATOR"]);
});

// ---- S5 analysis and result presentation (UX-003)
const evaluationId = "3f2e1d0c-9b8a-4c7d-8e6f-5a4b3c2d1e0f";
const anEvaluation = (state, extra = {}) => ({ evaluation_id: evaluationId, case_id: aCase.case_id, submission_id: aSubmission.submission_id,
  origin: "INITIAL", predecessor_evaluation_id: null, state, failure: null,
  result_availability: state === "COMPLETED" ? "AVAILABLE" : state === "FAILED" ? "NOT_PRODUCED" : "NOT_YET_AVAILABLE",
  requested_at: "2026-10-15T09:00:00Z", completed_at: state === "COMPLETED" ? "2026-10-15T09:00:01Z" : null,
  ai_usage: { requested: false, enabled_by_policy: false, used: false, fallback_reason: null }, provenance: null, links: {}, ...extra });
const aResult = (extra = {}) => ({ evaluation_id: evaluationId, result_contract_version: "1.1.0", result_digest: "ef".repeat(32), view: "STANDARD",
  input_support_status: "SUPPORTED", language: ["en"], script: ["Latn"], classification: "SCAM_PATTERN_DETECTED", decision_severity: "CRITICAL",
  matched_evidence_strength: "STRONG", risk_level: "CRITICAL", detection_confidence: "HIGH", degraded: false,
  governing_rule: { rule_id: "TL-CRED-001", rule_version: "1.0.0", source_references: ["SRC-004"] },
  matched_rules: [{ rule_id: "TL-CRED-001", rule_version: "1.0.0", source_references: ["SRC-004"] }],
  explanation: { summary: "Scam pattern detected: OTP solicited from the recipient under a pretext — risk CRITICAL, confidence HIGH.",
                 evidence_basis: ["Reserve Bank of India (SRC-004): “banks never ask for OTP”"] },
  recommended_actions: [{ action_code: "DO_NOT_SHARE_CREDENTIALS" }, { action_code: "CONTACT_BANK" }],
  limitations: ["Synthetic-only validation; no accuracy/precision/recall claim (G-09)."], unknowns: [], ambiguities: [],
  provenance: { engine_version: "1.0.0", result_contract_version: "1.1.0", bundle_content_digest: "bd4f1dca".padEnd(64, "0"), bundle_version: "1.0.0",
                evaluation_profile_id: "mvp-default", evaluation_timestamp: "2026-10-15T09:00:00.000000Z" },
  not_an_official_determination: true, absence_of_finding_notice: null, ...extra });
const panel = (props) => renderToStaticMarkup(createElement(AnalysisPanel, { caseId: aCase.case_id, submissionId: aSubmission.submission_id,
  hasFinalized: true, ...props }));
const visible = (html) => html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");

test("a completed result renders every governed section with separate categorical axes", () => {
  const html = visible(panel({ initialEvaluation: anEvaluation("COMPLETED"), initialResult: aResult() }));
  assert.match(html, /Result available: Scam pattern detected\./);
  for (const title of Object.values(evaluation.SECTION_TITLES)) assert.ok(html.includes(title), title);
  assert.match(html, /A governed scam pattern matched the evidence evaluated\. This is not a legal finding/);
  assert.match(html, /Risk level \(band\) CRITICAL/);
  assert.match(html, /Detection confidence \(not a probability\) HIGH/);
  assert.match(html, /Severity if genuine CRITICAL/);
  assert.match(html, /TL-CRED-001 v1\.0\.0/);
  assert.match(html, /Reserve Bank of India \(SRC-004\)/);
  assert.match(html, /Do not share passwords, one-time codes, PINs or other credentials in response to this message\./);
  assert.match(html, /Recommended by the governed action policy/);
  assert.match(html, /This result is not an official determination\./);
  assert.match(html, /Analyze message again/);
  assert.doesNotMatch(html, /%|\bscore\b|probability of|\d+ ?\/ ?100/i);
});

test("no-pattern, insufficient and unsupported results are never presented as safe", () => {
  const notice = "No governed scam pattern was established from the evidence evaluated. This is not a determination that the content is safe or legitimate.";
  for (const [classification, support, extra] of [["NO_SCAM_PATTERN", "SUPPORTED", { absence_of_finding_notice: notice }],
                                                  ["INSUFFICIENT_EVIDENCE", "SUPPORTED", {}], ["UNSUPPORTED", "UNSUPPORTED", {}],
                                                  ["ERROR", "ERROR", {}]]) {
    const result = aResult({ classification, input_support_status: support, risk_level: "NONE", decision_severity: "NONE",
      matched_evidence_strength: "NONE", detection_confidence: "NOT_APPLICABLE", governing_rule: null, matched_rules: [],
      recommended_actions: [{ action_code: "SEEK_HUMAN_REVIEW" }], ...extra });
    const html = visible(panel({ initialEvaluation: anEvaluation("COMPLETED"), initialResult: result }));
    assert.match(html, new RegExp(evaluation.CLASSIFICATIONS[classification].label.replace(/[()]/g, "\\$&")));
    const claims = html.replace(/not a determination that the content is safe( or legitimate)?/g, "");
    assert.doesNotMatch(claims, /\bsafe\b|legitimate|no risk|verified/i, classification);
    if (classification === "NO_SCAM_PATTERN") assert.ok(html.includes(notice));
  }
});

test("incomplete, contradictory or other-view responses are withheld, never partially shown", () => {
  const cases = [[{ ...aResult(), risk_level: undefined }, "RESULT_UNRENDERABLE"],
                 [aResult({ evaluation_id: "00000000-0000-4000-8000-000000000000" }), "RESULT_UNRENDERABLE"],
                 [aResult({ view: "DETAILED" }), "RESULT_VIEW_NOT_AUTHORIZED"],
                 [aResult({ rule_results: [] }), "RESULT_VIEW_NOT_AUTHORIZED"],
                 [aResult({ classification: "SAFE" }), "RESULT_UNRENDERABLE"],
                 [aResult({ risk_level: "7/10" }), "RESULT_UNRENDERABLE"],
                 [aResult({ input_support_status: "UNSUPPORTED" }), "RESULT_UNRENDERABLE"],
                 [aResult({ classification: "NO_SCAM_PATTERN" }), "RESULT_UNRENDERABLE"],
                 [aResult({ not_an_official_determination: false }), "RESULT_UNRENDERABLE"]];
  for (const [body, state] of cases) {
    assert.equal(evaluation.validateResult(body, evaluationId, "STANDARD"), state);
    const html = visible(panel({ initialEvaluation: anEvaluation("COMPLETED"), initialResult: body }));
    assert.ok(html.includes(evaluation.ANNOUNCEMENTS[state]), state);
    assert.doesNotMatch(html, /Scam pattern detected|TL-CRED-001|Do not share/);
  }
  assert.equal(evaluation.validateResult(aResult(), evaluationId, "STANDARD"), "READY");
});

test("pending and failed evaluations show their state and never a result", () => {
  const queued = visible(panel({ initialEvaluation: anEvaluation("QUEUED"), initialResult: aResult() }));
  assert.match(queued, /Analysis requested/);
  assert.match(queued, /The evaluation has not finished; no result is available yet\./);
  assert.match(queued, /Analysing…/);
  assert.doesNotMatch(queued, /Scam pattern detected/);
  const failed = visible(panel({ initialEvaluation: anEvaluation("FAILED", { failure: { failure_class: "INFRASTRUCTURE",
    reason: "INFRASTRUCTURE_FAILURE", retry_guidance: "RETRY_AS_NEW_EVALUATION" } }) }));
  assert.match(failed, /The evaluation or request did not produce a result\./);
  assert.match(failed, /not a determination that the content is safe/);
  assert.match(failed, /Analyze message again/);
  const none = visible(panel({ hasFinalized: false, initialEvaluation: undefined }));
  assert.match(none, /once one message text is stored and verified/);
  assert.doesNotMatch(none, /<button/);
});

test("analysis requests carry no decision fields; retries of a failure reference it as predecessor", async () => {
  const { fetcher, calls } = fakeFetch({ "/auth/csrf": [200, { csrf_token: "t" }],
    [`/api/v1/submissions/${aSubmission.submission_id}/evaluations`]: [202, { evaluations: [anEvaluation("QUEUED")] }] });
  const r = await evaluation.createEvaluation(aSubmission.submission_id, {}, fetcher, () => "key-0123456789abcdef");
  assert.equal(r.kind, "ok");
  const post = calls.find((c) => c.init.method === "POST");
  assert.equal(post.init.body, "{}");
  assert.equal(post.init.headers["X-CSRF-Token"], "t");
  assert.equal(post.init.headers["Idempotency-Key"], "key-0123456789abcdef");
  const source = readFileSync(new URL("./AnalysisPanel.tsx", import.meta.url), "utf8");
  assert.match(source, /predecessor_evaluation_id: previous\.evaluation_id/);
  const request = readFileSync(new URL("./evaluation.ts", import.meta.url), "utf8").match(/export const createEvaluation = [\s\S]*?;\n/)[0];
  assert.doesNotMatch(request, /classification|risk_level|severity|confidence/);         // the request carries no decision field
});

test("status polling is bounded and the result is requested only after COMPLETED + AVAILABLE", async () => {
  let polls = 0;
  const fetcher = async (url) => { polls++; return { status: 200, ok: true, json: async () => anEvaluation("RUNNING") }; };
  const r = await evaluation.waitForEvaluation(anEvaluation("QUEUED"), { fetcher, sleep: async () => {} });
  assert.equal(polls, evaluation.MAX_STATUS_POLLS);
  assert.equal(r.value.state, "RUNNING");
  assert.equal(evaluation.presentationForStatus(anEvaluation("COMPLETED")), "REQUEST_RESULT");
  assert.equal(evaluation.presentationForStatus(anEvaluation("COMPLETED", { result_availability: "NOT_YET_AVAILABLE" })), "RESULT_STATUS_UNRESOLVED");
  assert.equal(evaluation.presentationForStatus(anEvaluation("FAILED")), "ACTION_FAILED");
  assert.equal(evaluation.presentationForStatus(null), "RESULT_STATUS_UNRESOLVED");
  assert.equal(evaluation.presentationForError({ kind: "error", code: "FORBIDDEN", message: "" }), "ACCESS_DENIED");
  assert.equal(evaluation.presentationForError({ kind: "error", code: "SOMETHING_NEW", message: "" }), "RESULT_RESPONSE_UNCONFIRMED");
});

test("contradictory axis combinations are withheld (UX-003 axis_consistency), valid combinations render", () => {
  const none = { decision_severity: "NONE", matched_evidence_strength: "NONE", risk_level: "NONE", detection_confidence: "NOT_APPLICABLE",
                 governing_rule: null, matched_rules: [], recommended_actions: [{ action_code: "SEEK_HUMAN_REVIEW" }] };
  const notice = { absence_of_finding_notice: "No governed scam pattern was established from the evidence evaluated. This is not a determination that the content is safe or legitimate." };
  const contradictions = {
    "ERROR support with NO_SCAM_PATTERN": aResult({ ...none, ...notice, input_support_status: "ERROR", classification: "NO_SCAM_PATTERN" }),
    "LOW confidence with SCAM_PATTERN_DETECTED": aResult({ detection_confidence: "LOW" }),
    "HIGH severity + WEAK evidence as CRITICAL risk": aResult({ decision_severity: "HIGH", matched_evidence_strength: "WEAK", risk_level: "CRITICAL" }),
    "INSUFFICIENT_INFORMATION with NO_SCAM_PATTERN": aResult({ ...none, ...notice, input_support_status: "INSUFFICIENT_INFORMATION", classification: "NO_SCAM_PATTERN" }),
    "finding without a governing rule": aResult({ governing_rule: null }),
    "governing rule not among matched rules": aResult({ governing_rule: { rule_id: "TL-PAY-001", rule_version: "1.0.0" } }),
    "detected without any matched rule": aResult({ matched_rules: [], governing_rule: null }),
    "no finding with non-NONE risk": aResult({ ...none, classification: "INSUFFICIENT_EVIDENCE", risk_level: "LOW" }),
    "no finding with a governing rule": aResult({ ...none, classification: "INSUFFICIENT_EVIDENCE", governing_rule: { rule_id: "TL-CRED-001", rule_version: "1.0.0" } }),
    "degraded with HIGH confidence": aResult({ degraded: true }),
    "malformed rule identity": aResult({ matched_rules: [{ rule_id: "cred-1", rule_version: "1" }], governing_rule: { rule_id: "cred-1", rule_version: "1" } }),
    "duplicated matched rule": aResult({ matched_rules: [aResult().matched_rules[0], aResult().matched_rules[0]] }),
  };
  for (const [name, body] of Object.entries(contradictions)) {
    assert.equal(evaluation.validateResult(body, evaluationId, "STANDARD"), "RESULT_UNRENDERABLE", name);
    const html = visible(panel({ initialEvaluation: anEvaluation("COMPLETED"), initialResult: body }));
    assert.ok(html.includes(evaluation.ANNOUNCEMENTS.RESULT_UNRENDERABLE), name);
    assert.doesNotMatch(html, /Scam pattern detected|No governed scam pattern established|TL-CRED-001|Risk level/, name);
  }
  const valid = [aResult(),
    aResult({ classification: "SCAM_PATTERN_SUSPECTED", detection_confidence: "LOW", decision_severity: "HIGH", matched_evidence_strength: "WEAK", risk_level: "MEDIUM" }),
    aResult({ degraded: true, detection_confidence: "MEDIUM" }),
    aResult({ ...none, ...notice, classification: "NO_SCAM_PATTERN" }),
    aResult({ ...none, classification: "INSUFFICIENT_EVIDENCE", input_support_status: "PARTIALLY_SUPPORTED" }),
    aResult({ ...none, classification: "INSUFFICIENT_EVIDENCE", input_support_status: "INSUFFICIENT_INFORMATION" }),
    aResult({ ...none, classification: "UNSUPPORTED", input_support_status: "UNSUPPORTED" }),
    aResult({ ...none, classification: "ERROR", input_support_status: "ERROR" }),
    aResult({ ...none, classification: "ERROR", input_support_status: "SUPPORTED" })];
  for (const body of valid) assert.equal(evaluation.validateResult(body, evaluationId, "STANDARD"), "READY", body.classification);
});

test("frontend consistency tables equal the accepted UX-003 contract (no invented risk model)", () => {
  const contract = JSON.parse(readFileSync(new URL("../../../contracts/ux/ux-result-v1.json", import.meta.url), "utf8")).response_validation;
  assert.deepEqual(evaluation.PERMITTED_SUPPORT_CLASSIFICATION,
    Object.fromEntries(contract.permitted_support_classification.map((r) => [r.input_support_status, r.classifications])));
  const axes = contract.axis_consistency;
  assert.deepEqual(evaluation.RISK_MATRIX, axes.risk_matrix.map((r) => [r.decision_severity, r.matched_evidence_strength, r.risk_level]));
  assert.deepEqual(evaluation.FINDING_CLASSIFICATION_BY_CONFIDENCE, axes.finding_classification_by_confidence);
  assert.deepEqual(evaluation.NO_FINDING_AXES, axes.no_finding_axes);
  assert.equal(evaluation.DEGRADED_CONFIDENCE_CAP, axes.degraded_confidence_cap);
  assert.equal(axes.finding_basis, "matched_rules NON_EMPTY");
  assert.equal(contract.rule_identity.rule_id_pattern, "^TL-[A-Z]{3,5}-\\d{3}$");
});

// ---- S6 history, evidence download, correction and replay (UX-004 / UX-005)
const available = (entries, extra = {}) => ({ status: "AVAILABLE", entries, nextCursor: null, loadingMore: false, moreFailed: false, ...extra });

test("history lists every evaluation as its own record, newest first, with immutable provenance", () => {
  const older = anEvaluation("COMPLETED", { evaluation_id: "11111111-2222-4333-8444-555555555555", requested_at: "2026-10-14T09:00:00Z",
    provenance: { engine_version: "1.0.0", result_contract_version: "1.1.0", bundle_content_digest: "bd4f1dca".padEnd(64, "0"),
                  bundle_version: "1.0.0", evaluation_profile_id: "mvp-default", evaluation_timestamp: "2026-10-14T09:00:00Z" } });
  const newer = anEvaluation("COMPLETED", { origin: "USER_CORRECTION", predecessor_evaluation_id: older.evaluation_id });
  const entries = [{ evaluation: newer, result: aResult(), note: null },
                   { evaluation: older, result: aResult({ evaluation_id: older.evaluation_id }), note: null }];
  const html = visible(renderToStaticMarkup(createElement(HistoryPanel, { caseId: aCase.case_id, submissionId: aSubmission.submission_id,
    canReplay: false, initialState: available(entries) })));
  assert.match(html, /Latest New analysis after a correction/);
  assert.match(html, /Earlier First analysis/);
  assert.ok(html.includes(history.COMPARISON_NOTICE));
  assert.match(html, /bundle 1\.0\.0 bd4f1dca0000…/);
  assert.equal(html.match(/Classification: Scam pattern detected/g).length, 2);
  assert.equal(html.match(/Open this result/g).length, 2);
  assert.doesNotMatch(html, /Replay to verify|difference|improved|better|worse|%/i);    // no computed comparison
  const analyst = visible(renderToStaticMarkup(createElement(HistoryPanel, { caseId: aCase.case_id, submissionId: aSubmission.submission_id,
    canReplay: true, initialState: available(entries) })));
  assert.equal(analyst.match(/Replay to verify/g).length, 2);
});

test("original evidence is offered only with content permission and after the audit notice", () => {
  const stored = evidenceView("FINALIZED", { byte_length: 57, content_sha256: "ab".repeat(32), finalized_at: "2026-10-14T09:03:00Z",
    content_link: "/api/v1/evidence/9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d/content" });
  const panel6 = (props) => renderToStaticMarkup(createElement(EvidencePanel, { caseId: aCase.case_id, submissionId: aSubmission.submission_id,
    canUpload: false, initialEvidence: [stored], initialEvaluation: null, ...props }));
  const owner = panel6({ canViewContent: true });
  assert.match(owner, /<a href="\/api\/v1\/evidence\/9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d\/content" download="">Download the original<\/a>/);
  assert.ok(owner.includes(history.DOWNLOAD_NOTICE));
  const noContent = panel6({ canViewContent: false });
  assert.doesNotMatch(noContent, /Download the original|recorded in the audit log/);
});

test("a correction is offered to the owner of a ready result with the governed notice; never to others", () => {
  const ready = { initialEvaluation: anEvaluation("COMPLETED"), initialResult: aResult() };
  const owner = visible(panel({ ...ready, canCorrect: true }));
  assert.match(owner, /Describe the correction/);
  assert.ok(owner.includes(history.CORRECTION_NOTICE));
  assert.ok(owner.includes(history.REANALYSIS_NOTICE));
  assert.match(owner, /Submit correction and analyse again/);
  assert.doesNotMatch(visible(panel({ ...ready, canCorrect: false })), /Describe the correction/);
  assert.doesNotMatch(visible(panel({ initialEvaluation: anEvaluation("QUEUED"), canCorrect: true })), /Describe the correction/);
});

test("correction and replay requests carry only their accepted fields with CSRF and an Idempotency-Key", async () => {
  for (const [call, path, expected] of [
    [(f, k) => history.createCorrection(evaluationId, "SYNTHETIC: misread", f, k), `/api/v1/evaluations/${evaluationId}/corrections`,
     { correction_description: "SYNTHETIC: misread", reason_code: "EXTRACTION_ERROR" }],
    [(f, k) => history.createReplay(evaluationId, f, k), `/api/v1/evaluations/${evaluationId}/replays`, { reason_code: "ANALYST_VERIFICATION" }]]) {
    const { fetcher, calls } = fakeFetch({ "/auth/csrf": [200, { csrf_token: "t" }], [path]: [202, {}] });
    await call(fetcher, () => "key-0123456789abcdef");
    const post = calls.find((c) => c.init.method === "POST");
    assert.deepEqual(JSON.parse(post.init.body), expected);
    assert.equal(post.init.headers["X-CSRF-Token"], "t");
    assert.equal(post.init.headers["Idempotency-Key"], "key-0123456789abcdef");
  }
});

test("replay polling is bounded and outcomes use the governed labels", async () => {
  let polls = 0;
  const fetcher = async () => { polls++; return { status: 200, ok: true, json: async () => ({ replay_id: "r", evaluation_id: evaluationId, state: "PENDING", requested_at: "x" }) }; };
  const r = await history.waitForReplay({ replay_id: "r", evaluation_id: evaluationId, state: "PENDING", requested_at: "x" }, { fetcher, sleep: async () => {} });
  assert.equal(r.state, "PENDING");
  assert.equal(polls, 10);
  assert.equal(history.REPLAY_OUTCOMES.MATCH.label, "Reproduced exactly");
  assert.equal(history.REPLAY_OUTCOMES.FAILED_BUNDLE_UNAVAILABLE.label, "Replay unavailable: knowledge bundle unavailable");
  for (const { label, meaning } of Object.values(history.REPLAY_OUTCOMES)) assert.doesNotMatch(label + meaning, /new result|current engine|latest/i);
});

// ---- Codex S6 findings 3 and 4: pagination and explicit history states
const historyPanel = (initialState) => visible(renderToStaticMarkup(createElement(HistoryPanel, { caseId: aCase.case_id,
  submissionId: aSubmission.submission_id, canReplay: false, initialState })));
const evaluationsFor = (n, offset = 0) => Array.from({ length: n }, (_, i) => anEvaluation("QUEUED", {
  evaluation_id: `00000000-0000-4000-8000-${String(offset + i).padStart(12, "0")}`, requested_at: new Date(Date.UTC(2026, 9, 15, 9, 59 - (offset + i))).toISOString() }));
const shallow = async (evaluation) => ({ evaluation, result: null, note: null });

test("history states are explicit: loading, empty, unavailable with retry, available with load more", () => {
  assert.ok(historyPanel(history.LOADING_STATE).includes(history.HISTORY_TEXT.LOADING));
  const empty = historyPanel({ ...history.LOADING_STATE, status: "EMPTY" });
  assert.ok(empty.includes(history.HISTORY_TEXT.EMPTY));
  const failed = historyPanel({ ...history.LOADING_STATE, status: "UNAVAILABLE" });
  assert.ok(failed.includes(history.HISTORY_TEXT.UNAVAILABLE));
  assert.match(failed, /Try again/);
  assert.doesNotMatch(failed, new RegExp(history.HISTORY_TEXT.EMPTY));                  // a failure is never "no history"
  const entries = evaluationsFor(2).map((evaluation) => ({ evaluation, result: null, note: null }));
  const page = historyPanel(available(entries, { nextCursor: "c1" }));
  assert.match(page, /Latest.*Earlier/);
  assert.match(page, /Load more/);
  assert.doesNotMatch(historyPanel(available(entries)), /Load more/);
  assert.ok(historyPanel(available(entries, { nextCursor: "c1", moreFailed: true })).includes(history.HISTORY_TEXT.MORE_FAILED));
});

test("cursor pagination reaches every evaluation of the submission once, in server order", async () => {
  const all = evaluationsFor(21);
  const calls = [];
  const fetcher = async (url) => {
    calls.push(url);
    const cursor = new URL(url, "http://x").searchParams.get("cursor");
    const body = cursor === null ? { items: all.slice(0, 20), page: { limit: 20, next_cursor: "page-2" } }
      : { items: [all[19], all[20]], page: { limit: 20, next_cursor: null } };           // overlapping page: no duplicate
    return { status: 200, ok: true, json: async () => body };
  };
  const states = [];
  const loader = history.createHistoryLoader({ caseId: aCase.case_id, submissionId: aSubmission.submission_id, fetcher,
    loadEntry: shallow, onChange: (s) => states.push(s) });
  await loader.first();
  assert.equal(loader.state.entries.length, 20);
  assert.equal(loader.state.nextCursor, "page-2");
  await loader.more();
  const ids = loader.state.entries.map((e) => e.evaluation.evaluation_id);
  assert.deepEqual(ids, all.map((e) => e.evaluation_id));                                // newest first, oldest reachable
  assert.equal(new Set(ids).size, 21);
  assert.equal(loader.state.nextCursor, null);
  assert.ok(states.some((s) => s.loadingMore && s.entries.length === 20));               // earlier entries stay visible
  for (const url of calls) assert.match(url, new RegExp(`/api/v1/cases/${aCase.case_id}/evaluations\\?submission_id=${aSubmission.submission_id}&limit=20`));
  assert.match(calls[1], /&cursor=page-2$/);
  await loader.more();                                                                   // nothing more: no request
  assert.equal(calls.length, 2);
});

test("a failed request is unavailable, never empty; retry recovers; an empty 200 is empty", async () => {
  let status = 503;
  const fetcher = async () => status === 503
    ? { status: 503, ok: false, json: async () => ({ error: { code: "DEPENDENCY_UNAVAILABLE" } }) }
    : { status: 200, ok: true, json: async () => ({ items: status === 204 ? [] : evaluationsFor(1), page: { limit: 20 } }) };
  const loader = history.createHistoryLoader({ caseId: aCase.case_id, submissionId: aSubmission.submission_id, fetcher, loadEntry: shallow,
    onChange: () => {} });
  await loader.first();
  assert.equal(loader.state.status, "UNAVAILABLE");
  status = 200;
  await loader.first();                                                                  // the retry action
  assert.equal(loader.state.status, "AVAILABLE");
  status = 204;
  await loader.first();
  assert.equal(loader.state.status, "EMPTY");
  status = 200;
  await loader.first();
  const more = history.createHistoryLoader({ caseId: aCase.case_id, submissionId: aSubmission.submission_id, loadEntry: shallow, onChange: () => {},
    fetcher: async (url) => url.includes("cursor") ? { status: 503, ok: false, json: async () => ({ error: { code: "DEPENDENCY_UNAVAILABLE" } }) }
      : { status: 200, ok: true, json: async () => ({ items: evaluationsFor(20), page: { limit: 20, next_cursor: "p2" } }) } });
  await more.first();
  await more.more();
  assert.equal((more.state.entries.length), 20);                                         // a failed next page keeps the history
  assert.equal(more.state.moreFailed, true);
  assert.equal(more.state.status, "AVAILABLE");
});

test("responses for a previous case or submission are dropped, never shown", async () => {
  const pending = [];
  const fetcher = (url) => new Promise((resolve) => pending.push({ url, resolve }));
  const seen = [];
  const first = history.createHistoryLoader({ caseId: "case-a", submissionId: "sub-a", fetcher, loadEntry: shallow, onChange: (s) => seen.push(["a", s]) });
  const loadingA = first.first();
  first.cancel();                                                                        // the user chose another submission
  const second = history.createHistoryLoader({ caseId: "case-b", submissionId: "sub-b", fetcher, loadEntry: shallow, onChange: (s) => seen.push(["b", s]) });
  const loadingB = second.first();
  pending[1].resolve({ status: 200, ok: true, json: async () => ({ items: evaluationsFor(1, 50), page: { limit: 20 } }) });
  pending[0].resolve({ status: 200, ok: true, json: async () => ({ items: evaluationsFor(3), page: { limit: 20 } }) });   // late, stale
  await Promise.all([loadingA, loadingB]);
  assert.ok(!seen.some(([who, s]) => who === "a" && s.status === "AVAILABLE"));
  assert.deepEqual(second.state.entries.map((e) => e.evaluation.evaluation_id), [evaluationsFor(1, 50)[0].evaluation_id]);
});

// ---- S7 advisory enrichment (UX-006)
const lookup = (status, reputation_result, extra = {}) => ({ enrichment_id: `e-${status}-${reputation_result}`, provider_category: "REPUTATION_LOOKUP",
  status, reputation_result, observed_at: "2026-10-15T12:00:00Z", advisory: true, ...extra });
const enrichmentPanel = (initialState) => visible(renderToStaticMarkup(createElement(EnrichmentPanel, { evaluationId, initialState })));
const enrichmentState = (items, extra = {}) => ({ status: items.length ? "AVAILABLE" : "EMPTY", items, nextCursor: null, loadingMore: false,
  moreFailed: false, ...extra });

test("every governed enrichment pair uses the exact UX-006 label and meaning; anything else is unrecognized", () => {
  const contract = JSON.parse(readFileSync(new URL("../../../contracts/ux/ux-accessibility-v1.json", import.meta.url), "utf8")).enrichment;
  for (const row of contract.interpretation) {
    const meaning = enrichmentClient.interpret(lookup(row.status, row.reputation_result));
    assert.deepEqual([meaning.label, meaning.meaning, meaning.providerAssertion], [row.label, row.meaning, row.provider_assertion], row.presentation);
  }
  assert.equal(enrichmentClient.ADVISORY_NOTICE, contract.advisory_notice);
  assert.equal(enrichmentClient.OBSERVED_AT_ABSENT, contract.observed_at_absent_text);
  assert.equal(enrichmentClient.UNRECOGNIZED.label, contract.unrecognized_pair.label);
  for (const odd of [lookup("SUCCEEDED", "NOT_EVALUATED"), lookup("FAILED", "CLEAN"), lookup("SUCCEEDED", "MALICIOUS", { advisory: false }),
                     lookup("SUCCEEDED", "SAFE")]) {
    assert.equal(enrichmentClient.interpret(odd).label, "Unrecognized lookup record");
  }
});

test("a record without resolvable provider attribution is never shown as a provider assertion", () => {
  const unresolved = { provider_category: enrichmentClient.UNRESOLVED_CATEGORY };
  for (const record of [lookup("SUCCEEDED", "CLEAN", unresolved), lookup("SUCCEEDED", "MALICIOUS", unresolved),
                        lookup("SUCCEEDED", "NOT_EVALUATED", unresolved), lookup("SUCCEEDED", "CLEAN", { provider_category: "" }),
                        lookup("SUCCEEDED", "CLEAN", { provider_category: undefined })]) {
    assert.equal(enrichmentClient.interpret(record), enrichmentClient.UNRECOGNIZED);       // withheld, even if a stale API sent CLEAN
  }
  assert.equal(enrichmentClient.interpret(lookup("SUCCEEDED", "CLEAN")).label, "Provider reports no adverse reputation");   // resolved
  for (const record of [lookup("SUCCEEDED", "CLEAN", unresolved),
                        lookup("SUCCEEDED", "NOT_EVALUATED", unresolved)]) {                  // what the API returns on a digest mismatch
    const html = enrichmentPanel(enrichmentState([record]));
    assert.match(html, /Unrecognized lookup record/);
    assert.doesNotMatch(html, /no adverse reputation|Provider reports|\bsafe\b|legitimate|verified/i);
  }
});

test("enrichment states are explicit and never read as safety", () => {
  assert.ok(enrichmentPanel(enrichmentClient.ENRICHMENT_LOADING).includes(enrichmentClient.ENRICHMENT_TEXT.LOADING));
  const empty = enrichmentPanel(enrichmentState([]));
  assert.ok(empty.includes(enrichmentClient.ENRICHMENT_TEXT.EMPTY));
  const failed = enrichmentPanel({ ...enrichmentClient.ENRICHMENT_LOADING, status: "UNAVAILABLE" });
  assert.ok(failed.includes(enrichmentClient.ENRICHMENT_TEXT.UNAVAILABLE));
  assert.match(failed, /Try again/);
  assert.doesNotMatch(failed, /No external lookup is recorded/);
  const advisory = enrichmentPanel(enrichmentState([lookup("SUCCEEDED", "MALICIOUS"), lookup("SUCCEEDED", "CLEAN"),
    lookup("TIMED_OUT", "NOT_EVALUATED", { observed_at: null }), lookup("REJECTED", "NOT_EVALUATED")], { nextCursor: "c2" }));
  assert.ok(advisory.includes(enrichmentClient.ADVISORY_NOTICE));
  assert.match(advisory, /External lookups \(advisory\)/);
  assert.match(advisory, /Provider reports malicious · REPUTATION_LOOKUP/);
  assert.match(advisory, /Provider reports no adverse reputation/);
  assert.match(advisory, /Lookup timed out .* Observation time not provided\./);
  assert.match(advisory, /Lookup not permitted/);
  assert.match(advisory, /Load more lookups/);
  for (const html of [empty, failed, advisory]) {
    const claims = html.replace(/not a TrustLens (judgement|finding)/g, "").replace(/This says nothing about whether the message is a scam\./, "");
    assert.doesNotMatch(claims, /\bis safe\b|\blegitimate\b|\bverified\b|no scam|not a scam|Scam pattern|risk level|classification/i);
  }
});

test("only assigned analysts see the external-lookup control, apart from the result", () => {
  const entries = [{ evaluation: anEvaluation("COMPLETED"), result: aResult(), note: null }];
  const forAnalyst = visible(renderToStaticMarkup(createElement(HistoryPanel, { caseId: aCase.case_id, submissionId: aSubmission.submission_id,
    canReplay: true, initialState: available(entries) })));
  assert.match(forAnalyst, /External lookups \(advisory\)/);
  const forOwner = visible(renderToStaticMarkup(createElement(HistoryPanel, { caseId: aCase.case_id, submissionId: aSubmission.submission_id,
    canReplay: false, initialState: available(entries) })));
  assert.doesNotMatch(forOwner, /External lookups/);
  const result = visible(panel({ initialEvaluation: anEvaluation("COMPLETED"), initialResult: aResult() }));
  assert.doesNotMatch(result, /External lookups|provider/i);                              // never on the result surface
});

test("enrichment loading: failures are unavailable, pages are deduped, stale responses are dropped", async () => {
  const states = [];
  let mode = "fail";
  const fetcher = async (url) => {
    if (mode === "fail") return { status: 503, ok: false, json: async () => ({ error: { code: "DEPENDENCY_UNAVAILABLE" } }) };
    if (mode === "empty") return { status: 200, ok: true, json: async () => ({ items: [], page: { limit: 20 } }) };
    const page2 = url.includes("cursor=");
    return { status: 200, ok: true, json: async () => page2 ? { items: [lookup("SUCCEEDED", "CLEAN"), lookup("FAILED", "NOT_EVALUATED")], page: { limit: 20 } }
      : { items: [lookup("SUCCEEDED", "MALICIOUS"), lookup("SUCCEEDED", "CLEAN")], page: { limit: 20, next_cursor: "c2" } } };
  };
  const loader = enrichmentClient.createEnrichmentLoader(evaluationId, (s) => states.push(s), fetcher);
  await loader.first();
  assert.equal(loader.state.status, "UNAVAILABLE");
  mode = "empty";
  await loader.first();
  assert.equal(loader.state.status, "EMPTY");
  mode = "pages";
  await loader.first();
  await loader.more();
  assert.deepEqual(loader.state.items.map((i) => i.enrichment_id), ["e-SUCCEEDED-MALICIOUS", "e-SUCCEEDED-CLEAN", "e-FAILED-NOT_EVALUATED"]);
  let release;
  const slow = enrichmentClient.createEnrichmentLoader(evaluationId, (s) => states.push(["slow", s.status]),
    () => new Promise((resolve) => { release = resolve; }));
  const pending = slow.first();
  slow.cancel();
  release({ status: 200, ok: true, json: async () => ({ items: [lookup("SUCCEEDED", "MALICIOUS")], page: { limit: 20 } }) });
  await pending;
  assert.ok(!states.some((s) => Array.isArray(s) && s[1] === "AVAILABLE"));
  const source = readFileSync(new URL("./enrichment.ts", import.meta.url), "utf8");
  assert.equal((source.match(/\/api\/v1\//g) || []).length, 1);                           // the one accepted read operation
});
