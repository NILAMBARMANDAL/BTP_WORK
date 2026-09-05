import { useCallback, useRef, useState } from "react";

/**
 * Wraps MediaRecorder with explicit states so components can render
 * permission errors / recording state without duplicating this logic.
 * status: "idle" | "requesting" | "recording" | "stopped" | "permission_denied" | "error"
 */
export function useAudioRecorder() {
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState(null);
  const [audioBlob, setAudioBlob] = useState(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);

  const start = useCallback(async () => {
    setError(null);
    setAudioBlob(null);
    setStatus("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];

      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setAudioBlob(blob);
        setStatus("stopped");
        stream.getTracks().forEach((t) => t.stop());
      };

      recorder.start();
      setStatus("recording");
    } catch (err) {
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        setStatus("permission_denied");
        setError("Microphone permission denied. Please allow microphone access and try again.");
      } else if (err.name === "NotFoundError") {
        setStatus("error");
        setError("No microphone found on this device.");
      } else {
        setStatus("error");
        setError(err.message || "Could not start recording.");
      }
    }
  }, []);

  const stop = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
  }, []);

  const reset = useCallback(() => {
    setStatus("idle");
    setError(null);
    setAudioBlob(null);
  }, []);

  return { status, error, audioBlob, start, stop, reset };
}
