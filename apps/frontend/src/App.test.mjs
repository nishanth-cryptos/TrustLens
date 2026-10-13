import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const server = await createServer({ server: { middlewareMode: true }, appType: "custom" });
let App, auth;
try {
  ({ default: App } = await server.ssrLoadModule("/src/App.tsx"));
  auth = await server.ssrLoadModule("/src/auth.ts");
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
  const source = code("./App.tsx") + code("./auth.ts");
  for (const forbidden of [/localStorage/, /sessionStorage/, /document\.cookie/, /Authorization/, /access_token|id_token|refresh_token/]) {
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
