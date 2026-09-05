import express from "express";
import cors from "cors";
import morgan from "morgan";
import sessionsRouter from "./routes/sessions.js";
import correctionsRouter from "./routes/corrections.js";
import { notFoundHandler, errorHandler } from "./middleware/errorHandler.js";
import { env } from "./config/env.js";

export function createApp() {
  const app = express();

  app.use(cors());
  app.use(express.json());
  if (!env.isTest) app.use(morgan("dev"));

  app.get("/health", (req, res) => res.json({ status: "ok" }));

  app.use("/api/sessions", sessionsRouter);
  app.use("/api/corrections", correctionsRouter);

  app.use(notFoundHandler);
  app.use(errorHandler);

  return app;
}
