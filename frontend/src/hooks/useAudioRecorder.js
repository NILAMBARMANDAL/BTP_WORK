import { useCallback, useRef, useState } from "react";

/**
 * Wraps MediaRecorder with explicit states so components can render
 * permission errors / recording state without duplicating this logic.
 * status: "idle" | "requesting" | "recording" | "stopped" | "permission_denied" | "unsupported" | "empty" | "error"
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

    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setStatus("unsupported");
      setError("This browser doesn't support microphone recording. Try a recent Chrome, Firefox, or Edge.");
      return;
    }

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
        stream.getTracks().forEach((t) => t.stop());
        if (blob.size === 0) {
          setStatus("empty");
          setError("No audio was captured — please try recording again.");
          return;
        }
        setAudioBlob(blob);
        setStatus("stopped");
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
