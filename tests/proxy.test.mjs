// Offline tests for the Netlify function. Run: node --test tests/
import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";

const KEY = "jevp_test_key";
process.env.JEV_PROXY_KEY_SHA256 = createHash("sha256").update(KEY).digest("hex");
const { default: handler, authorized } = await import("../proxy/netlify/functions/jev.mjs");

let calls;
beforeEach(() => {
  calls = [];
  process.env.TYPESAFE_API_KEY = "gateway-key";
  process.env.TYPESAFE_BASE_URL = "https://gateway.example";
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return new Response(JSON.stringify({ answers: { q: { noul: 0.9 } } }), {
      status: 200, headers: { "content-type": "application/json", "x-typesafe-request-id": "req_1" },
    });
  };
});

const req = (path, { key, method = "POST", body } = {}) => new Request("https://site.example" + path, {
  method, body, headers: key ? { authorization: `Bearer ${key}` } : {},
});

test("rejects missing and wrong keys without calling upstream", async () => {
  assert.equal((await handler(req("/v1/systemone", { body: "{}" }))).status, 401);
  assert.equal((await handler(req("/v1/systemone", { key: "nope", body: "{}" }))).status, 401);
  assert.equal(calls.length, 0);
});

test("refuses everything when no hash is configured", () => {
  const saved = process.env.JEV_PROXY_KEY_SHA256;
  process.env.JEV_PROXY_KEY_SHA256 = "";
  try { assert.equal(authorized(req("/v1/models", { key: KEY, method: "GET" })), false); }
  finally { process.env.JEV_PROXY_KEY_SHA256 = saved; }
});

test("forwards POST /v1/systemone with the gateway key and passes the answer through", async () => {
  const res = await handler(req("/v1/systemone", { key: KEY, body: '{"state":"x"}' }));
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("x-typesafe-request-id"), "req_1");
  assert.deepEqual(await res.json(), { answers: { q: { noul: 0.9 } } });
  assert.equal(calls[0].url, "https://gateway.example/v1/systemone");
  assert.equal(calls[0].init.headers.Authorization, "Bearer gateway-key");
  assert.equal(calls[0].init.body, '{"state":"x"}');
});

test("serves /v1/models in TypeSafe format", async () => {
  const res = await handler(req("/v1/models", { key: KEY, method: "GET" }));
  assert.equal(res.status, 200);
  assert.deepEqual((await res.json()).models.map(m => m.name), ["jev-latest", "jev-preview"]);
  assert.equal(calls.length, 0);
});

test("explains a missing AI Gateway configuration", async () => {
  delete process.env.TYPESAFE_API_KEY;
  const res = await handler(req("/v1/systemone", { key: KEY, body: "{}" }));
  assert.equal(res.status, 500);
  assert.match((await res.json()).error.message, /production/);
});

test("rejects GET on /v1/systemone", async () => {
  assert.equal((await handler(req("/v1/systemone", { key: KEY, method: "GET" }))).status, 405);
});
