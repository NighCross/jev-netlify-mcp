// Key-locked Jev proxy for Netlify.
//
// Exposes the same routes as the TypeSafe API (POST /v1/systemone, GET /v1/models),
// so the official SDKs work unchanged when TYPESAFE_BASE_URL points at this site.
// Only the SHA-256 hash of your key lives here. Requests without the right key get 401
// and never reach the model, so they cost no credits. The real call goes through
// Netlify AI Gateway, which injects TYPESAFE_API_KEY and TYPESAFE_BASE_URL at runtime.
import { createHash, timingSafeEqual } from "node:crypto";

// Filled in by scripts/setup.py when it builds dist/. A Netlify environment variable
// named JEV_PROXY_KEY_SHA256 overrides it (do NOT name it TYPESAFE_*: setting those
// yourself stops Netlify from injecting the AI Gateway credentials).
const EMBEDDED_KEY_SHA256 = "__JEV_PROXY_KEY_SHA256__";

function expectedHash() {
  const fromEnv = (process.env.JEV_PROXY_KEY_SHA256 || "").trim().toLowerCase();
  const hex = /^[0-9a-f]{64}$/.test(fromEnv) ? fromEnv : EMBEDDED_KEY_SHA256;
  return /^[0-9a-f]{64}$/.test(hex) ? Buffer.from(hex, "hex") : null;
}

export function authorized(req) {
  const expected = expectedHash();
  if (!expected) return false; // not configured: refuse everything
  const m = /^Bearer\s+(.+)$/i.exec(req.headers.get("authorization") ?? "");
  if (!m) return false;
  const got = createHash("sha256").update(m[1].trim()).digest();
  return got.length === expected.length && timingSafeEqual(got, expected);
}

const error = (status, type, message) => Response.json({ error: { type, message } }, { status });

export default async (req) => {
  if (!authorized(req)) return error(401, "authentication_error", "Invalid or missing API key");

  const path = new URL(req.url).pathname;
  if (path.endsWith("/models")) {
    // The gateway's model list uses a different shape, so answer in TypeSafe's format.
    const description = "Jev via Netlify AI Gateway";
    return Response.json({
      models: [
        { name: "jev-latest", description },
        { name: "jev-preview", description },
      ],
    });
  }
  if (req.method !== "POST") return error(405, "invalid_request_error", "Use POST for /v1/systemone");

  const key = process.env.TYPESAFE_API_KEY;
  if (!key) {
    return error(500, "configuration_error",
      "AI Gateway credentials missing: deploy to production once and make sure AI features are enabled");
  }
  const base = (process.env.TYPESAFE_BASE_URL || "https://api.typesafe.ai").replace(/\/+$/, "");
  const upstream = await fetch(base + "/v1/systemone", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: await req.text(),
  });

  // Pass the answer through unchanged (status and body), keeping the request id header.
  const headers = { "Content-Type": upstream.headers.get("content-type") ?? "application/json" };
  const requestId = upstream.headers.get("x-typesafe-request-id");
  if (requestId) headers["x-typesafe-request-id"] = requestId;
  return new Response(await upstream.text(), { status: upstream.status, headers });
};

export const config = { path: ["/v1/systemone", "/v1/models"] };
