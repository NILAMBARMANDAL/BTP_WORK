import multer from "multer";
import { env } from "../config/env.js";

const ALLOWED_MIME_TYPES = new Set([
  "audio/wav",
  "audio/x-wav",
  "audio/wave",
  "audio/webm",
  "audio/ogg",
  "audio/mpeg",
  "audio/mp4",
  "audio/m4a",
  "audio/x-m4a",
]);

const storage = multer.memoryStorage();

export const audioUpload = multer({
  storage,
  limits: { fileSize: env.maxAudioUploadMb * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    if (!ALLOWED_MIME_TYPES.has(file.mimetype)) {
      cb(new Error(`Unsupported audio type: ${file.mimetype}`));
      return;
    }
    cb(null, true);
  },
});
