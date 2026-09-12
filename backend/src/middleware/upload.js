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
      // Client-side validation error, not a server fault — errorHandler.js
      // reads `.status` to decide the response code (and whether to log it
      // as a server error), so this must not fall through to a bare 500.
      const err = new Error(`Unsupported audio type: ${file.mimetype}`);
      err.status = 400;
      cb(err);
      return;
    }
    cb(null, true);
  },
});
