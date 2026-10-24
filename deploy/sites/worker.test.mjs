/** Check private proxy boundaries using controlled requests; no Site is published. */
import assert from "node:assert/strict";
import { test } from "node:test";
import worker from "./worker.js";

test("private API rejects anonymous requests", async () => {
  const response = await worker.fetch(
    new Request("https://site.test/api/v1/profiles"),
    {},
  );
  assert.equal(response.status, 401);
});
test("assets do not receive backend credentials", async () => {
  const response = await worker.fetch(new Request("https://site.test/"), {
    ASSETS: { fetch: () => new Response("page") },
  });
  assert.equal(await response.text(), "page");
});
test("gateway supplies server credential, strips visitor credentials and forwards CSV", async () => {
  const previous = globalThis.fetch;
  let captured;
  globalThis.fetch = async (url, init) => {
    captured = { url: String(url), ...init };
    return new Response("result", { headers: { "Content-Type": "text/csv" } });
  };
  try {
    const request = new Request("https://site.test/api/v1/profiles?x=1", {
      method: "POST",
      body: "csv",
      headers: {
        "oai-authenticated-user-id": "owner",
        Authorization: "visitor-secret",
        Cookie: "visitor-cookie",
        "Content-Type": "text/csv",
      },
    });
    const response = await worker.fetch(request, {
      BACKEND_URL: "https://python.test/service",
      API_ACCESS_TOKEN: "server-secret",
    });
    assert.equal(response.status, 200);
    assert.equal(captured.headers.get("Authorization"), "Bearer server-secret");
    assert.equal(captured.headers.get("Cookie"), null);
    assert.equal(
      captured.url,
      "https://python.test/service/api/v1/profiles?x=1",
    );
    assert.equal(await new Response(captured.body).text(), "csv");
    assert.equal(response.headers.get("Cache-Control"), "no-store");
  } finally {
    globalThis.fetch = previous;
  }
});
test("backend redirects are not followed with credentials", async () => {
  const previous = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(null, {
      status: 302,
      headers: { Location: "https://elsewhere.test" },
    });
  try {
    const response = await worker.fetch(
      new Request("https://site.test/api/v1/profiles", {
        headers: { "oai-authenticated-user-id": "owner" },
      }),
      { BACKEND_URL: "https://python.test", API_ACCESS_TOKEN: "token" },
    );
    assert.equal(response.status, 502);
  } finally {
    globalThis.fetch = previous;
  }
});
