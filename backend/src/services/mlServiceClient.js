import { env } from "../config/env.js";

class MlServiceError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "MlServiceError";
    this.status = status ?? 502;
  }
}

async function postForm(path, form) {
  let res;
  try {
    res = await fetch(`${env.mlServiceUrl}${path}`, {
      method: "POST",
      body: form,
      // Sent only backend -> ml-service, over HTTPS (the tunnel) — never
      // forwarded to or readable by the browser. No-op header if unset.
      headers: env.mlServiceApiKey ? { "X-ML-Service-Key": env.mlServiceApiKey } : undefined,
      // Whisper/correction inference can take a long time on CPU-only
      // hosting; without an explicit signal, a hung connection would block
      // the request indefinitely instead of surfacing a clear error.
      signal: AbortSignal.timeout(env.mlServiceTimeoutMs),
    });
  } catch (cause) {
    if (cause.name === "TimeoutError" || cause.name === "AbortError") {
      throw new MlServiceError(
        `ml-service at ${env.mlServiceUrl} did not respond within ${env.mlServiceTimeoutMs}ms`,
        504
      );
    }
    // fetch() throws a bare "fetch failed" (no context) on connection
    // refused/DNS failure — surface something a user-facing error message
    // can actually explain, rather than leaking a raw Node/undici message.
    throw new MlServiceError(`ml-service unreachable at ${env.mlServiceUrl} (${cause.message})`, 503);
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new MlServiceError(`ml-service ${path} failed: ${res.status} ${body}`, res.status);
  }
  return res.json();
}

/**
 * audioBuffer: Buffer, filename: string, mimeType: string
 */
export async function transcribeAudio({ audioBuffer, filename, mimeType }) {
  const form = new FormData();
  form.append("file", new Blob([audioBuffer], { type: mimeType }), filename);
  return postForm("/transcribe", form);
}

/**
 * Sends a re-pronunciation recording (+ optional meaning/context) for a
 * single flagged word and returns ranked candidates.
 */
export async function correctWord({
  audioBuffer,
  filename,
  mimeType,
  originalWord,
  contextText,
  mode,
  meaningContext,
}) {
  const form = new FormData();
  form.append("file", new Blob([audioBuffer], { type: mimeType }), filename);
  form.append("original_word", originalWord);
  form.append("context_text", contextText ?? "");
  form.append("mode", mode);
  if (meaningContext) form.append("meaning_context", meaningContext);
  return postForm("/correct", form);
}

export { MlServiceError };
