import { useState } from "react";
import { Recorder } from "./Recorder.jsx";

const MODE_LABELS = {
  pronunciation_only: "Pronunciation Only",
  pronunciation_meaning: "Pronunciation + Meaning/Context",
};

/**
 * UI for correcting one flagged word, for a mode that was already chosen
 * (and sent to the backend) before this panel ever rendered — see App.jsx's
 * mode-choice step. `mode` is a prop, not local state: the backend's
 * Correction document fixes the mode at creation
 * (backend/src/routes/corrections.js), and every attempt against it reuses
 * that same mode (correction.mode) server-side — choosing a mode here after
 * the fact would have no effect on what the ml-service actually does, which
 * is exactly the contract mismatch this was fixed to avoid.
 *
 * Presentation only — all API calls and state transitions live in
 * useCorrection (ARCHITECTURE.md: keep UI components separate from API
 * communication).
 */
export function CorrectionPanel({ word, mode, correction, attempts, status, error, onSubmitAttempt, onAccept, onClose }) {
  const [pronunciationStyle, setPronunciationStyle] = useState("slow");
  const [meaningContext, setMeaningContext] = useState("");

  const isBusy = status === "opening" || status === "submitting" || status === "accepting";
  const isAccepted = correction?.status === "accepted";

  const handleRecorded = (blob) => {
    onSubmitAttempt({ audioBlob: blob, pronunciationStyle, meaningContext: meaningContext || undefined });
  };

  return (
    <div className="correction-panel">
      <div className="correction-panel__header">
        <h3>
          Correcting: <span lang="bn">{word.text}</span>
        </h3>
        <button onClick={onClose}>Close</button>
      </div>

      <p className="correction-panel__mode">
        Mode: <strong>{MODE_LABELS[mode] ?? mode}</strong>
      </p>

      {!isAccepted && (
        <>
          <fieldset className="style-select">
            <legend>How will you pronounce it?</legend>
            <label>
              <input
                type="radio"
                name="style"
                value="slow"
                checked={pronunciationStyle === "slow"}
                onChange={() => setPronunciationStyle("slow")}
              />
              Slowly and clearly
            </label>
            <label>
              <input
                type="radio"
                name="style"
                value="syllable"
                checked={pronunciationStyle === "syllable"}
                onChange={() => setPronunciationStyle("syllable")}
              />
              Syllable-by-syllable
            </label>
          </fieldset>

          <p className="hint">
            Record <strong>only the word above</strong> — not the whole sentence. Speak slowly and
            clearly{pronunciationStyle === "syllable" ? ", syllable by syllable" : ""}.
          </p>

          {mode === "pronunciation_meaning" && (
            <div className="meaning-input">
              <label htmlFor="meaning-context">
                Optional: describe what the word means, or use it in a sentence. You can change
                this between retries.
              </label>
              <textarea
                id="meaning-context"
                value={meaningContext}
                onChange={(e) => setMeaningContext(e.target.value)}
                placeholder="e.g. এটা একটা ফলের নাম"
                lang="bn"
              />
            </div>
          )}

          <Recorder label={`Record ${pronunciationStyle === "syllable" ? "syllable-by-syllable" : "slow"} pronunciation`} onRecorded={handleRecorded} />
        </>
      )}

      {isBusy && <p className="hint" role="status">Working…</p>}
      {error && <p className="error-banner" role="alert">{error}</p>}

      {attempts.length > 0 && (
        <div className="attempt-history">
          <h4>Attempts</h4>
          <ol>
            {attempts.map((a, i) => (
              <li key={a._id ?? i} className={a.accepted ? "attempt--accepted" : ""}>
                <div>
                  Attempt {a.attemptNumber ?? i + 1}: prediction{" "}
                  <strong lang="bn">{a.prediction ?? "(none)"}</strong>
                  {a.latencyMs != null && <span className="latency"> ({a.latencyMs}ms)</span>}
                </div>
                {a.candidates?.length > 1 && (
                  <details>
                    <summary>{a.candidates.length} candidates</summary>
                    <ul>
                      {a.candidates.map((c) => (
                        <li key={c.text} lang="bn">
                          {c.text} — score {c.finalScore.toFixed(3)}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
                {!isAccepted && (
                  <button onClick={() => onAccept(a._id)} disabled={isBusy} aria-label={`Accept prediction ${a.prediction}`}>
                    Accept this prediction
                  </button>
                )}
              </li>
            ))}
          </ol>
          {!isAccepted && attempts.length > 0 && (
            <p className="hint">Not right? Record the word again above to retry.</p>
          )}
        </div>
      )}

      {isAccepted && <p className="success-banner">Correction accepted.</p>}
    </div>
  );
}
