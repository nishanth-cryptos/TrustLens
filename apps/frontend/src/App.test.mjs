import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const server = await createServer({ server: { middlewareMode: true }, appType: "custom" });
let App, auth, Workspace, submissionLabels, cases, evidence;
try {
  ({ default: App } = await server.ssrLoadModule("/src/App.tsx"));
  auth = await server.ssrLoadModule("/src/auth.ts");
  ({ default: Workspace, SUBMISSION_STATE_LABELS: submissionLabels } = await server.ssrLoadModule("/src/Workspace.tsx"));
  cases = await server.ssrLoadModule("/src/cases.ts");
  evidence = await server.ssrLoadModule("/src/evidence.ts");
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
    + code("./EvidencePanel.tsx");
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
  assert.match(html, /Nothing is\s+analysed/);
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
  assert.match(html, /not analysed and no result is produced/);
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
