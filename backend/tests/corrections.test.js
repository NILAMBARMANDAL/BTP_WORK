import { describe, it, expect, beforeAll, afterAll } from "@jest/globals";
import request from "supertest";
import { createApp } from "../src/app.js";
import { connectDb, disconnectDb } from "../src/db/connect.js";
import { Transcript } from "../src/models/Transcript.js";

let app;

beforeAll(async () => {
  process.env.MONGO_MODE = "memory";
  await connectDb();
  app = createApp();
}, 60000);

afterAll(async () => {
  await disconnectDb();
});

function tinyWavBuffer() {
  const numSamples = 100;
  const header = Buffer.alloc(44);
  header.write("RIFF", 0);
  header.writeUInt32LE(36 + numSamples * 2, 4);
  header.write("WAVE", 8);
  header.write("fmt ", 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(1, 22);
  header.writeUInt32LE(16000, 24);
  header.writeUInt32LE(32000, 28);
  header.writeUInt16LE(2, 32);
  header.writeUInt16LE(16, 34);
  header.write("data", 36);
  header.writeUInt32LE(numSamples * 2, 40);
  const data = Buffer.alloc(numSamples * 2);
  return Buffer.concat([header, data]);
}

describe("POST /api/corrections — ground truth / dataset provenance", () => {
  it("records datasetProvenance on the session and groundTruthWord on the correction, kept separate from prediction/acceptance", async () => {
    // Evaluation-harness-style session: known dataset reference, not a live user recording.
    const sessionRes = await request(app)
      .post("/api/sessions")
      .field("datasetId", "openslr_53")
      .field("utteranceId", "0cdb8818d4")
      .field("groundTruthTranscript", "সোনার বাংলা")
      .attach("file", tinyWavBuffer(), { filename: "test.wav", contentType: "audio/wav" });

    expect(sessionRes.status).toBe(201);
    expect(sessionRes.body.session.datasetProvenance).toMatchObject({
      datasetId: "openslr_53",
      utteranceId: "0cdb8818d4",
      groundTruthTranscript: "সোনার বাংলা",
    });

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

    const correctionRes = await request(app).post("/api/corrections").send({
      sessionId,
      transcriptId: transcript._id.toString(),
      wordIndex: 0,
      mode: "pronunciation_only",
      groundTruthWord: "সোনার",
    });

    expect(correctionRes.status).toBe(201);
    expect(correctionRes.body.correction.originalWord).toBe("শোনার");
    expect(correctionRes.body.correction.groundTruthWord).toBe("সোনার");
    // groundTruthWord must never be conflated with acceptedAttemptId/prediction —
    // no attempt has been made or accepted yet.
    expect(correctionRes.body.correction.status).toBe("open");
    expect(correctionRes.body.correction.acceptedAttemptId).toBeNull();
  });

  it("defaults groundTruthWord and datasetProvenance to null for ordinary live sessions", async () => {
    const sessionRes = await request(app)
      .post("/api/sessions")
      .attach("file", tinyWavBuffer(), { filename: "test.wav", contentType: "audio/wav" });

    expect(sessionRes.body.session.datasetProvenance.datasetId).toBeNull();

    const transcript = await Transcript.create({
      sessionId: sessionRes.body.session._id,
      words: [{ index: 0, text: "আম", start: 0, end: 0.3, confidence: 0.9 }],
      rawText: "আম",
      language: "bn",
    });

    const correctionRes = await request(app).post("/api/corrections").send({
      sessionId: sessionRes.body.session._id,
      transcriptId: transcript._id.toString(),
      wordIndex: 0,
      mode: "pronunciation_only",
    });

    expect(correctionRes.body.correction.groundTruthWord).toBeNull();
  });
});
