import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const server = await createServer({ server: { middlewareMode: true }, appType: "custom" });
let App;
try {
  ({ default: App } = await server.ssrLoadModule("/src/App.tsx"));
} finally {
  await server.close();
}

test("renders the React foundation with its explicit scope boundary", () => {
  const html = renderToStaticMarkup(createElement(App));
  assert.match(html, /TrustLens/);
  assert.match(html, /Foundation preview/);
  assert.match(html, /performs no analysis/);
});

test("offers no unprotected content capture or sign-in flow", () => {
  assert.doesNotMatch(renderToStaticMarkup(createElement(App)), /<(form|input|textarea|iframe)\b/);
});
