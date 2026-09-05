import mongoose from "mongoose";

/**
 * One Correction = one user-flagged word in one transcript. Attempts are
 * stored separately (CorrectionAttempt) and never overwritten — this document
 * only tracks which attempt (if any) was accepted.
 */
const correctionSchema = new mongoose.Schema(
  {
    sessionId: { type: mongoose.Schema.Types.ObjectId, ref: "Session", required: true, index: true },
    transcriptId: { type: mongoose.Schema.Types.ObjectId, ref: "Transcript", required: true, index: true },
    wordIndex: { type: Number, required: true },
    originalWord: { type: String, required: true },
    mode: { type: String, enum: ["pronunciation_only", "pronunciation_meaning"], required: true },
    status: { type: String, enum: ["open", "accepted", "abandoned"], default: "open" },
    acceptedAttemptId: { type: mongoose.Schema.Types.ObjectId, ref: "CorrectionAttempt", default: null },
    // Independently-known correct word, ONLY set when this correction was
    // created against a session with datasetProvenance (Session.js) — e.g. an
    // evaluation harness that knows the true word from a dataset reference
    // transcript. Never inferred/auto-filled from a prediction or an accepted
    // attempt: those are a model prediction and a user-feedback signal
    // respectively, NOT ground truth (RESEARCH.md's evidence-separation
    // rule — see EXPERIMENTS.md "Data leakage protocol" for why this
    // distinction matters for evaluation).
    groundTruthWord: { type: String, default: null },
  },
  { timestamps: true }
);

export const Correction = mongoose.model("Correction", correctionSchema);
