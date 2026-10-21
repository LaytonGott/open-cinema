// Thin fetch layer over the app's HTTP API. The only module that calls fetch.

export class ApiError extends Error {
  constructor(status, code, message, field) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.field = field;
  }
}

async function request(url, options) {
  const res = await fetch(url, options);
  let body = null;
  const text = await res.text();
  if (text) {
    try {
      body = JSON.parse(text);
    } catch (e) {
      body = null;
    }
  }
  if (!res.ok) {
    const err = (body && body.error) || {};
    throw new ApiError(
      res.status,
      err.code || "http_error",
      err.message || res.statusText || "Request failed",
      err.field === undefined ? null : err.field
    );
  }
  return body;
}

export function getHealth() {
  return request("/api/health");
}

export function getOptions() {
  return request("/api/options");
}

export function getEstimate(lensMm, framing) {
  const q = new URLSearchParams({ lens_mm: String(lensMm), framing: String(framing) });
  return request("/api/estimate?" + q.toString());
}

export function listShots() {
  return request("/api/shots");
}

export function getShot(id) {
  return request("/api/shots/" + encodeURIComponent(id));
}

export function createShot(params) {
  return request("/api/shots", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
}

export function cancelShot(id) {
  return request("/api/shots/" + encodeURIComponent(id) + "/cancel", { method: "POST" });
}
