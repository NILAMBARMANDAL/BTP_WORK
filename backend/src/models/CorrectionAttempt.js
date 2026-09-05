import mongoose from "mongoose";

const candidateSchema = new mongoose.Schema(
  {
    text: { type: String, required: true },
    acousticScore: { type: Number, default: 0 },
    phoneticScore: { type: Number, default: 0 },
    semanticScore: { type: Number, default: 0 },
    contextualScore: { type: Number, default: 0 },
    finalScore: { type: Number, required: true },
  },
  { _id: false }
);

/**
 * Append-only: every re-pronunciation attempt is stored, never overwritten.
 * `prediction` is the model's top-ranked candidate — a MODEL PREDICTION, not
 * ground truth. `accepted` is a USER FEEDBACK signal set only via the accept
 * endpoint, distinct from the prediction itself.
 */
const correctionAttemptSchema = new mongoose.Schema(
  {
    correctionId: { type: mongoose.Schema.Types.ObjectId, ref: "Correction", required: true, index: true },
    attemptNumber: { type: Number, required: true },
    audioRef: { type: String, required: true },
    pronunciationStyle: { type: String, enum: ["slow", "syllable"], default: "slow" },
    meaningContext: { type: String, default: null },
    candidates: { type: [candidateSchema], default: [] },
    prediction: { type: String, default: null },
    accepted: { type: Boolean, default: false },
    rankingWeights: {
      acoustic: Number,
      phonetic: Number,
      semantic: Number,
      contextual: Number,
    },
    latencyMs: { type: Number, default: null },
  },
  { timestamps: true }
);

correctionAttemptSchema.index({ correctionId: 1, attemptNumber: 1 }, { unique: true });

export const CorrectionAttempt = mongoose.model("CorrectionAttempt", correctionAttemptSchema);
