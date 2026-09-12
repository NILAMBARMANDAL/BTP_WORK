import { useAudioRecorder } from "../hooks/useAudioRecorder.js";

/**
 * Generic recorder UI. `onRecorded(blob)` fires once a recording is stopped;
 * the caller decides what to do with the blob (create session, submit
 * attempt, etc.) — this component has no knowledge of the API.
 */
export function Recorder({ onRecorded, label = "Record" }) {
  const { status, error, audioBlob, start, stop, reset } = useAudioRecorder();

  const handleUseRecording = () => {
    if (audioBlob) onRecorded(audioBlob);
    reset();
  };

  return (
    <div className="recorder">
      {status === "idle" && <button onClick={start}>{label}</button>}

      {status === "requesting" && <p className="hint">Requesting microphone access…</p>}

      {status === "recording" && (
        <div>
          <span className="recording-indicator" role="status">● Recording…</span>
          <button onClick={stop} aria-label="Stop recording">Stop</button>
        </div>
      )}

      {status === "stopped" && audioBlob && (
        <div>
          <audio controls src={URL.createObjectURL(audioBlob)} />
          <div className="recorder-actions">
            <button onClick={handleUseRecording}>Use this recording</button>
            <button onClick={reset}>Discard &amp; re-record</button>
          </div>
        </div>
      )}

      {(status === "permission_denied" || status === "unsupported" || status === "empty" || status === "error") && (
        <div className="error-banner" role="alert">
          <p>{error}</p>
          <button onClick={reset}>Try again</button>
        </div>
      )}
    </div>
  );
}
