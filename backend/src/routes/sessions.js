import { Router } from "express";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Session } from "../models/Session.js";
import { Transcript } from "../models/Transcript.js";
import { audioUpload } from "../middleware/upload.js";
import { transcribeAudio } from "../services/mlServiceClient.js";
import { env } from "../config/env.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const router = Router();

async function saveAudioBuffer(buffer, extHint) {
  const dir = path.resolve(__dirname, "../../", env.audioStorageDir);
  await fs.mkdir(dir, { recursive: true });
  const filename = `${Date.now()}-${Math.random().toString(36).slice(2)}.${extHint}`;
  const filePath = path.join(dir, filename);
  await fs.writeFile(filePath, buffer);
  return filePath;
}

function extFromMime(mime) {
  if (mime.includes("wav")) return "wav";
  if (mime.includes("webm")) return "webm";
  if (mime.includes("ogg")) return "ogg";
  if (mime.includes("mp4") || mime.includes("m4a")) return "m4a";
  if (mime.includes("mpeg")) return "mp3";
  return "bin";
}

// POST /api/sessions  (multipart: file=<audio>, speakerId?=<string>,
// datasetId?/utteranceId?/groundTruthTranscript?=<string> for evaluation-harness sessions only)
router.post("/", audioUpload.single("file"), async (req, res, next) => {
  try {
    if (!req.file) return res.status(400).json({ error: "Audio file is required" });

    const audioRef = await saveAudioBuffer(req.file.buffer, extFromMime(req.file.mimetype));
    const session = await Session.create({
      speakerId: req.body.speakerId || null,
      originalAudioRef: audioRef,
      status: "created",
      datasetProvenance: {
        datasetId: req.body.datasetId || null,
        utteranceId: req.body.utteranceId || null,
        groundTruthTranscript: req.body.groundTruthTranscript || null,
      },
    });

    res.status(201).json({ session });
  } catch (err) {
    next(err);
  }
});

// POST /api/sessions/:id/transcribe
router.post("/:id/transcribe", async (req, res, next) => {
  try {
    const session = await Session.findById(req.params.id);
    if (!session) return res.status(404).json({ error: "Session not found" });

    const audioBuffer = await fs.readFile(session.originalAudioRef);
    const result = await transcribeAudio({
      audioBuffer,
      filename: path.basename(session.originalAudioRef),
      mimeType: "audio/wav",
    });

    const transcript = await Transcript.create({
      sessionId: session._id,
      words: result.words,
      rawText: result.text,
      language: result.language ?? "bn",
      whisperConfig: result.config ?? {},
    });

    session.status = "transcribed";
    await session.save();

    res.status(201).json({ transcript });
  } catch (err) {
    next(err);
  }
});

// GET /api/sessions/:id
router.get("/:id", async (req, res, next) => {
  try {
    const session = await Session.findById(req.params.id);
    if (!session) return res.status(404).json({ error: "Session not found" });
    const transcript = await Transcript.findOne({ sessionId: session._id }).sort({ createdAt: -1 });
    res.json({ session, transcript });
  } catch (err) {
    next(err);
  }
});

export default router;
