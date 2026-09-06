// All backend HTTP calls live here — components never call fetch() directly.
// Keeping this separate from UI components per ARCHITECTURE.md.

// Never bake a localhost fallback into a production build (spec: "no
// localhost references in production"). Dev server (`npm run dev`) still
// defaults to the local backend for convenience; a production build with
// VITE_BACKEND_URL unset falls back to a same-origin relative path instead —
// which fails cleanly (visible network error) rather than silently pointing
// at whichever machine happens to be running the deployed static site.
const BASE_URL = import.meta.env.VITE_BACKEND_URL ?? (import.meta.env.DEV ? "http://127.0.0.1:4000" : "");

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${BASE_URL}${path}`, options);
  } catch {
    throw new ApiError("Network error — is the backend running?", 0);
  }

  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.error) message = body.error;
    } catch {
      // ignore body parse failure, use default message
    }
    throw new ApiError(message, res.status);
  }

  return res.json();
}

export async function createSession(audioBlob, speakerId) {
  const form = new FormData();
  form.append("file", audioBlob, "session.webm");
  if (speakerId) form.append("speakerId", speakerId);
  return request("/api/sessions", { method: "POST", body: form });
}

export async function transcribeSession(sessionId) {
  return request(`/api/sessions/${sessionId}/transcribe`, { method: "POST" });
}

export async function getSession(sessionId) {
  return request(`/api/sessions/${sessionId}`);
}

export async function createCorrection({ sessionId, transcriptId, wordIndex, mode }) {
  return request("/api/corrections", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sessionId, transcriptId, wordIndex, mode }),
  });
}

export async function submitAttempt(correctionId, { audioBlob, pronunciationStyle, meaningContext }) {
  const form = new FormData();
  form.append("file", audioBlob, "attempt.webm");
  form.append("pronunciationStyle", pronunciationStyle);
  if (meaningContext) form.append("meaningContext", meaningContext);
  return request(`/api/corrections/${correctionId}/attempts`, { method: "POST", body: form });
}

export async function acceptAttempt(correctionId, attemptId) {
  return request(`/api/corrections/${correctionId}/accept`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ attemptId }),
  });
}

export async function getCorrection(correctionId) {
  return request(`/api/corrections/${correctionId}`);
}

export { ApiError };
