import { useState } from "react";
import { Recorder } from "./Recorder.jsx";

/**
 * UI for correcting one flagged word. Presentation only — all API calls and
 * state transitions live in useCorrection (ARCHITECTURE.md: keep UI
 * components separate from API communication).
 */
export function CorrectionPanel({ word, correction, attempts, status, error, onSubmitAttempt, onAccept, onClose }) {
  const [mode, setMode] = useState("pronunciation_only");
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

      {!isAccepted && (
        <>
          <fieldset className="mode-select">
            <legend>Correction mode</legend>
            <label>
              <input
                type="radio"
                name="mode"
                value="pronunciation_only"
                checked={mode === "pronunciation_only"}
                onChange={() => setMode("pronunciation_only")}
              />
              Pronunciation only
            </label>
            <label>
              <input
                type="radio"
                name="mode"
                value="pronunciation_meaning"
                checked={mode === "pronunciation_meaning"}
                onChange={() => setMode("pronunciation_meaning")}
              />
              Pronunciation + meaning/context
            </label>
          </fieldset>

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

          {mode === "pronunciation_meaning" && (
            <div className="meaning-input">
              <label htmlFor="meaning-context">
                Optional: describe what the word means, or use it in a sentence
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

      {isBusy && <p className="hint">Working…</p>}
      {error && <p className="error-banner">{error}</p>}

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
                  <button onClick={() => onAccept(a._id)} disabled={isBusy}>
                    Accept this prediction
                  </button>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}

      {isAccepted && <p className="success-banner">Correction accepted.</p>}
    </div>
  );
}
