import { Router } from "express";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Correction } from "../models/Correction.js";
import { CorrectionAttempt } from "../models/CorrectionAttempt.js";
import { Transcript } from "../models/Transcript.js";
import { audioUpload } from "../middleware/upload.js";
import { correctWord } from "../services/mlServiceClient.js";
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
  return "bin";
}

// POST /api/corrections  { sessionId, transcriptId, wordIndex, mode, groundTruthWord? }
// groundTruthWord is accepted ONLY for evaluation-harness callers that
// independently know the true word (e.g. from a dataset reference
// transcript) — never inferred here from the transcript/prediction itself.
router.post("/", async (req, res, next) => {
  try {
    const { sessionId, transcriptId, wordIndex, mode, groundTruthWord } = req.body;
    if (!sessionId || !transcriptId || wordIndex === undefined || !mode) {
      return res.status(400).json({ error: "sessionId, transcriptId, wordIndex, mode are required" });
    }
    if (!["pronunciation_only", "pronunciation_meaning"].includes(mode)) {
      return res.status(400).json({ error: "Invalid mode" });
    }

    const transcript = await Transcript.findById(transcriptId);
    if (!transcript) return res.status(404).json({ error: "Transcript not found" });

    const word = transcript.words.find((w) => w.index === Number(wordIndex));
    if (!word) return res.status(404).json({ error: "Word index not found in transcript" });

    const correction = await Correction.create({
      sessionId,
      transcriptId,
      wordIndex: Number(wordIndex),
      originalWord: word.text,
      mode,
      groundTruthWord: groundTruthWord || null,
    });

    res.status(201).json({ correction });
  } catch (err) {
    next(err);
  }
});

// POST /api/corrections/:id/attempts  (multipart: file=<audio>, meaningContext?)
router.post("/:id/attempts", audioUpload.single("file"), async (req, res, next) => {
  try {
    if (!req.file) return res.status(400).json({ error: "Audio file is required" });

    const correction = await Correction.findById(req.params.id);
    if (!correction) return res.status(404).json({ error: "Correction not found" });
    if (correction.status !== "open") {
      return res.status(409).json({ error: `Correction is already ${correction.status}` });
    }

    const transcript = await Transcript.findById(correction.transcriptId);
    const contextText = transcript?.words.map((w) => w.text).join(" ") ?? "";

    const audioRef = await saveAudioBuffer(req.file.buffer, extFromMime(req.file.mimetype));
    const attemptNumber = (await CorrectionAttempt.countDocuments({ correctionId: correction._id })) + 1;

    const start = Date.now();
    const result = await correctWord({
      audioBuffer: req.file.buffer,
      filename: path.basename(audioRef),
      mimeType: req.file.mimetype,
      originalWord: correction.originalWord,
      contextText,
      mode: correction.mode,
      meaningContext: req.body.meaningContext,
    });
    const latencyMs = Date.now() - start;

    const attempt = await CorrectionAttempt.create({
      correctionId: correction._id,
      attemptNumber,
      audioRef,
      pronunciationStyle: req.body.pronunciationStyle === "syllable" ? "syllable" : "slow",
      meaningContext: req.body.meaningContext || null,
      candidates: result.candidates ?? [],
      prediction: result.prediction ?? null,
      rankingWeights: result.ranking_weights ?? {},
      latencyMs,
    });

    res.status(201).json({ attempt });
  } catch (err) {
    next(err);
  }
});

// POST /api/corrections/:id/accept  { attemptId }
router.post("/:id/accept", async (req, res, next) => {
  try {
    const { attemptId } = req.body;
    if (!attemptId) return res.status(400).json({ error: "attemptId is required" });

    const correction = await Correction.findById(req.params.id);
    if (!correction) return res.status(404).json({ error: "Correction not found" });

    const attempt = await CorrectionAttempt.findOne({ _id: attemptId, correctionId: correction._id });
    if (!attempt) return res.status(404).json({ error: "Attempt not found for this correction" });

    attempt.accepted = true;
    await attempt.save();

    correction.status = "accepted";
    correction.acceptedAttemptId = attempt._id;
    await correction.save();

    res.json({ correction, attempt });
  } catch (err) {
    next(err);
  }
});

// GET /api/corrections/:id  (includes full attempt history)
router.get("/:id", async (req, res, next) => {
  try {
    const correction = await Correction.findById(req.params.id);
    if (!correction) return res.status(404).json({ error: "Correction not found" });
    const attempts = await CorrectionAttempt.find({ correctionId: correction._id }).sort({ attemptNumber: 1 });
    res.json({ correction, attempts });
  } catch (err) {
    next(err);
  }
});

export default router;
