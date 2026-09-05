import { env } from "../config/env.js";

class MlServiceError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "MlServiceError";
    this.status = status ?? 502;
  }
}

async function postForm(path, form) {
  const res = await fetch(`${env.mlServiceUrl}${path}`, {
    method: "POST",
    body: form,
  });
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
