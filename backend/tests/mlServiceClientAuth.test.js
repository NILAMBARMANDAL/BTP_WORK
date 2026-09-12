import { describe, it, expect, jest } from "@jest/globals";

// Mocks config/env.js (rather than mutating process.env after
// mlServiceClient.js has already imported `env`) so this actually exercises
// a configured ML_SERVICE_API_KEY deterministically, regardless of whatever
// real .env this test run happens to load.
jest.unstable_mockModule("../src/config/env.js", () => ({
  env: {
    mlServiceUrl: "https://laptop.example.trycloudflare.com",
    mlServiceTimeoutMs: 5000,
    mlServiceApiKey: "test-secret-key",
  },
}));

const { correctWord } = await import("../src/services/mlServiceClient.js");

describe("mlServiceClient API key auth (spec: shared secret for a tunneled ml-service)", () => {
  it("sends the X-ML-Service-Key header when ML_SERVICE_API_KEY is configured", async () => {
    const fetchMock = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ prediction: "ok", candidates: [] }),
      })
    );
    global.fetch = fetchMock;

    await correctWord({
      audioBuffer: Buffer.from("fake"),
      filename: "a.webm",
      mimeType: "audio/webm",
      originalWord: "বাড়ি",
      contextText: "আমার বাড়ি",
      mode: "pronunciation_only",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers).toMatchObject({ "X-ML-Service-Key": "test-secret-key" });
  });
});
