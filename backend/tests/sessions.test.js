import { describe, it, expect, beforeAll, afterAll } from "@jest/globals";
import request from "supertest";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import { createApp } from "../src/app.js";
import { connectDb, disconnectDb } from "../src/db/connect.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

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
  // Minimal valid-enough WAV header + a few silent samples, just to exercise
  // the upload path in tests without hitting the real ml-service.
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

describe("POST /api/sessions", () => {
  it("creates a session when given an audio file", async () => {
    const res = await request(app)
      .post("/api/sessions")
      .attach("file", tinyWavBuffer(), { filename: "test.wav", contentType: "audio/wav" });

    expect(res.status).toBe(201);
    expect(res.body.session).toBeDefined();
    expect(res.body.session.status).toBe("created");

    // cleanup the file written to storage
    if (fs.existsSync(res.body.session.originalAudioRef)) {
      fs.unlinkSync(res.body.session.originalAudioRef);
    }
  });

  it("rejects requests without an audio file", async () => {
    const res = await request(app).post("/api/sessions").send({});
    expect(res.status).toBe(400);
  });
});
