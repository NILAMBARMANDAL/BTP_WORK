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

describe("GET /health", () => {
  it("returns ok", async () => {
    const res = await request(app).get("/health");
    expect(res.status).toBe(200);
    expect(res.body.status).toBe("ok");
  });
});
