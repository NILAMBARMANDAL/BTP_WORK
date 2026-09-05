import { createApp } from "./app.js";
import { connectDb } from "./db/connect.js";
import { env } from "./config/env.js";

async function main() {
  await connectDb();
  const app = createApp();
  app.listen(env.port, () => {
    console.log(`backend listening on http://localhost:${env.port} (mongoMode=${env.mongoMode})`);
  });
}

main().catch((err) => {
  console.error("Failed to start backend:", err);
  process.exit(1);
});
