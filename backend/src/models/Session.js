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
  },
  { timestamps: true }
);

export const Session = mongoose.model("Session", sessionSchema);
