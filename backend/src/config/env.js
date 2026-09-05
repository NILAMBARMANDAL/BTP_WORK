import dotenv from "dotenv";

dotenv.config();

function bool(value, fallback) {
  if (value === undefined) return fallback;
  return value === "true" || value === "1";
}

export const env = {
  port: Number(process.env.PORT ?? 4000),
  nodeEnv: process.env.NODE_ENV ?? "development",
  mongoUri: process.env.MONGO_URI ?? "mongodb://127.0.0.1:27017/btp_asr",
  mongoMode: process.env.MONGO_MODE ?? "memory",
  mlServiceUrl: process.env.ML_SERVICE_URL ?? "http://127.0.0.1:8000",
  audioStorageDir: process.env.AUDIO_STORAGE_DIR ?? "../storage/audio",
  maxAudioUploadMb: Number(process.env.MAX_AUDIO_UPLOAD_MB ?? 25),
  isTest: process.env.NODE_ENV === "test",
};
