import { describe, it, expect, afterEach, jest } from "@jest/globals";
import { correctWord, MlServiceError } from "../src/services/mlServiceClient.js";

// Exercises the robustness behavior spec section 6 calls for ("make timeout
// handling robust because ML inference may take time") without needing a
// real ml-service instance — mocks global.fetch directly.

const realFetch = global.fetch;

afterEach(() => {
  global.fetch = realFetch;
});

function baseArgs() {
  return {
    audioBuffer: Buffer.from("fake-audio"),
    filename: "attempt.webm",
    mimeType: "audio/webm",
    originalWord: "বাড়ি",
    contextText: "আমার বাড়ি",
    mode: "pronunciation_only",
  };
}

describe("mlServiceClient robustness", () => {
  it("surfaces a distinct 504 MlServiceError on timeout, not a generic error", async () => {
    global.fetch = jest.fn(() => {
      const err = new Error("The operation was aborted");
      err.name = "TimeoutError";
      return Promise.reject(err);
    });

    await expect(correctWord(baseArgs())).rejects.toMatchObject({
      name: "MlServiceError",
      status: 504,
    });
  });

  it("surfaces a 503 MlServiceError (not a raw fetch error) on connection refused", async () => {
    global.fetch = jest.fn(() => Promise.reject(new Error("fetch failed")));

    await expect(correctWord(baseArgs())).rejects.toMatchObject({
      name: "MlServiceError",
      status: 503,
    });
  });

  it("surfaces the ml-service's own status code on a non-2xx response", async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: false,
        status: 500,
        text: () => Promise.resolve("internal error"),
      })
    );

    await expect(correctWord(baseArgs())).rejects.toBeInstanceOf(MlServiceError);
  });
});
