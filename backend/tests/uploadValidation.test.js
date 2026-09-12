import { describe, it, expect, beforeAll, afterAll } from "@jest/globals";
import request from "supertest";
import { createApp } from "../src/app.js";
import { connectDb, disconnectDb } from "../src/db/connect.js";

let app;

beforeAll(async () => {
  process.env.MONGO_MODE = "memory";
  await connectDb();
  app = createApp();
}, 60000);

afterAll(async () => {
  await disconnectDb();
});

describe("audio upload validation (spec section 6: structured client errors, not 500s)", () => {
  it("rejects an unsupported file type with 400, not 500", async () => {
    const res = await request(app)
      .post("/api/sessions")
      .attach("file", Buffer.from("not audio"), { filename: "notes.txt", contentType: "text/plain" });

    expect(res.status).toBe(400);
    expect(res.body.error).toMatch(/unsupported audio type/i);
  });

  it("rejects a file over the configured size limit with 400, not 500", async () => {
    const oversized = Buffer.alloc(Number(process.env.MAX_AUDIO_UPLOAD_MB ?? 25) * 1024 * 1024 + 1);
    const res = await request(app)
      .post("/api/sessions")
      .attach("file", oversized, { filename: "big.wav", contentType: "audio/wav" });

    expect(res.status).toBe(400);
    expect(res.body.error).toMatch(/exceeds the maximum upload size/i);
  });
});
