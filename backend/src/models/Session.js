import mongoose from "mongoose";

const sessionSchema = new mongoose.Schema(
  {
    speakerId: { type: String, default: null },
    originalAudioRef: { type: String, required: true },
    status: {
      type: String,
      enum: ["created", "transcribed", "in_correction", "closed"],
      default: "created",
    },
    notes: { type: String, default: "" },
    // Set only for sessions created from a known dataset (e.g. an evaluation
    // harness replaying OpenSLR SLR53 manifest samples), never for live user
    // recordings — lets downstream analysis tell live sessions apart from
    // controlled-evaluation ones without guessing from other fields.
    datasetProvenance: {
      datasetId: { type: String, default: null },
      utteranceId: { type: String, default: null },
      groundTruthTranscript: { type: String, default: null },
    },
  },
  { timestamps: true }
);

export const Session = mongoose.model("Session", sessionSchema);
