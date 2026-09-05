import mongoose from "mongoose";

/**
 * A transcript word has a stable `index` within the transcript so the frontend
 * can select it unambiguously even when the same Bengali word appears more
 * than once. Never represent the transcript as a single unstructured string.
 */
const wordSchema = new mongoose.Schema(
  {
    index: { type: Number, required: true },
    text: { type: String, required: true },
    start: { type: Number, default: null },
    end: { type: Number, default: null },
    confidence: { type: Number, default: null },
  },
  { _id: false }
);

const transcriptSchema = new mongoose.Schema(
  {
    sessionId: { type: mongoose.Schema.Types.ObjectId, ref: "Session", required: true, index: true },
    words: { type: [wordSchema], required: true },
    rawText: { type: String, required: true },
    language: { type: String, default: "bn" },
    whisperConfig: {
      modelSize: String,
      device: String,
      computeType: String,
      beamSize: Number,
    },
  },
  { timestamps: true }
);

export const Transcript = mongoose.model("Transcript", transcriptSchema);
