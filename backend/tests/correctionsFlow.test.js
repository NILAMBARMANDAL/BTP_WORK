import { describe, it, expect, beforeAll, afterAll, jest } from "@jest/globals";
import request from "supertest";

// Mocks the backend->ML HTTP call (src/services/mlServiceClient.js) so this
// exercises the real Express routes/Mongoose models (mode validation, the
// append-only attempt history, accept/retry state transitions — spec
// section 13) without needing a live ml-service process.
const mockCorrectWord = jest.fn();
jest.unstable_mockModule("../src/services/mlServiceClient.js", () => ({
  correctWord: mockCorrectWord,
  transcribeAudio: jest.fn(),
  MlServiceError: class MlServiceError extends Error {},
}));

const { createApp } = await import("../src/app.js");
const { connectDb, disconnectDb } = await import("../src/db/connect.js");
const { Transcript } = await import("../src/models/Transcript.js");

let app;

beforeAll(async () => {
  process.env.MONGO_MODE = "memory";
  await connectDb();
  app = createApp();
}, 60000);

afterAll(async () => {
  await disconnectDb();
});

async function createSessionAndTranscript() {
  const sessionRes = await request(app)
    .post("/api/sessions")
    .attach("file", Buffer.from("fake"), { filename: "t.wav", contentType: "audio/wav" });
  const sessionId = sessionRes.body.session._id;
  const transcript = await Transcript.create({
    sessionId,
    words: [
      { index: 0, text: "শোনার", start: 0, end: 0.5, confidence: 0.9 },
      { index: 1, text: "বাংলা", start: 0.5, end: 1.0, confidence: 0.95 },
    ],
    rawText: "শোনার বাংলা",
    language: "bn",
  });
  return { sessionId, transcriptId: transcript._id.toString() };
}

describe("correction mode validation", () => {
  it("rejects an invalid mode at creation", async () => {
    const { sessionId, transcriptId } = await createSessionAndTranscript();
    const res = await request(app)
      .post("/api/corrections")
      .send({ sessionId, transcriptId, wordIndex: 0, mode: "typed_text" });
    expect(res.status).toBe(400);
  });
});

describe("correction attempt -> accept/retry flow (mocked ml-service)", () => {
  it("submits two attempts (retry) then accepts the second, isolating the selected word as the correction unit", async () => {
    mockCorrectWord.mockResolvedValueOnce({
      prediction: "বাড়ি",
      candidates: [{ text: "বাড়ি", acousticScore: 0.8, phoneticScore: 0.4, semanticScore: 0, contextualScore: 0, finalScore: 0.5 }],
      ranking_weights: { acoustic: 0.4 },
    });
    mockCorrectWord.mockResolvedValueOnce({
      prediction: "সোনার",
      candidates: [{ text: "সোনার", acousticScore: 0.9, phoneticScore: 0.85, semanticScore: 0, contextualScore: 0, finalScore: 0.88 }],
      ranking_weights: { acoustic: 0.4 },
    });

    const { sessionId, transcriptId } = await createSessionAndTranscript();
    const createRes = await request(app)
      .post("/api/corrections")
      .send({ sessionId, transcriptId, wordIndex: 0, mode: "pronunciation_only" });
    const correctionId = createRes.body.correction._id;

    const attempt1 = await request(app)
      .post(`/api/corrections/${correctionId}/attempts`)
      .field("pronunciationStyle", "slow")
      .attach("file", Buffer.from("fake-word-audio"), { filename: "a1.webm", contentType: "audio/webm" });
    expect(attempt1.status).toBe(201);
    expect(attempt1.body.attempt.prediction).toBe("বাড়ি");
    expect(attempt1.body.attempt.attemptNumber).toBe(1);

    // Retry: the user re-records the selected word again.
    const attempt2 = await request(app)
      .post(`/api/corrections/${correctionId}/attempts`)
      .field("pronunciationStyle", "syllable")
      .attach("file", Buffer.from("fake-word-audio-2"), { filename: "a2.webm", contentType: "audio/webm" });
    expect(attempt2.status).toBe(201);
    expect(attempt2.body.attempt.prediction).toBe("সোনার");
    expect(attempt2.body.attempt.attemptNumber).toBe(2);

    // Both ml-service calls were made with the single selected word's audio,
    // never the full sentence context audio.
    expect(mockCorrectWord).toHaveBeenCalledTimes(2);
    expect(mockCorrectWord.mock.calls[0][0].originalWord).toBe("শোনার");

    const acceptRes = await request(app)
      .post(`/api/corrections/${correctionId}/accept`)
      .send({ attemptId: attempt2.body.attempt._id });
    expect(acceptRes.status).toBe(200);
    expect(acceptRes.body.correction.status).toBe("accepted");
    expect(acceptRes.body.correction.acceptedAttemptId).toBe(attempt2.body.attempt._id);

    // Further attempts are rejected once accepted (stop the correction process).
    const attempt3 = await request(app)
      .post(`/api/corrections/${correctionId}/attempts`)
      .field("pronunciationStyle", "slow")
      .attach("file", Buffer.from("fake-word-audio-3"), { filename: "a3.webm", contentType: "audio/webm" });
    expect(attempt3.status).toBe(409);
  });

  it("404s when accepting an attempt id that doesn't belong to the correction", async () => {
    const { sessionId, transcriptId } = await createSessionAndTranscript();
    const createRes = await request(app)
      .post("/api/corrections")
      .send({ sessionId, transcriptId, wordIndex: 1, mode: "pronunciation_only" });
    const correctionId = createRes.body.correction._id;

    const res = await request(app)
      .post(`/api/corrections/${correctionId}/accept`)
      .send({ attemptId: "64b000000000000000000000" });
    expect(res.status).toBe(404);
  });
});
