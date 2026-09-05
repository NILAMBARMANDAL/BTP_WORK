import mongoose from "mongoose";
import { env } from "../config/env.js";

let memoryServer;

/**
 * MONGO_MODE=memory (dev default) spins up mongodb-memory-server so local
 * development doesn't require a system-installed MongoDB. Production must set
 * MONGO_MODE=uri and provide a real MONGO_URI.
 */
export async function connectDb() {
  let uri = env.mongoUri;

  if (env.mongoMode === "memory") {
    const { MongoMemoryServer } = await import("mongodb-memory-server");
    memoryServer = await MongoMemoryServer.create();
    uri = memoryServer.getUri();
  }

  await mongoose.connect(uri);
  return mongoose.connection;
}

export async function disconnectDb() {
  await mongoose.disconnect();
  if (memoryServer) {
    await memoryServer.stop();
    memoryServer = undefined;
  }
}
