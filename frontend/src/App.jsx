import { useMemo, useState } from "react";
import { Recorder } from "./components/Recorder.jsx";
import { TranscriptView } from "./components/TranscriptView.jsx";
import { CorrectionPanel } from "./components/CorrectionPanel.jsx";
import { useCorrection } from "./hooks/useCorrection.js";
import { createSession, transcribeSession } from "./api/client.js";
import "./App.css";

function App() {
  const [session, setSession] = useState(null); // { _id, ... }
  const [transcript, setTranscript] = useState(null); // { _id, words: [...] }
  const [pipelineStatus, setPipelineStatus] = useState("idle"); // idle | uploading | transcribing | error
  const [pipelineError, setPipelineError] = useState(null);

  const [selectedWordIndex, setSelectedWordIndex] = useState(null);
  const [acceptedByIndex, setAcceptedByIndex] = useState({}); // wordIndex -> accepted text

  const correctionWorkflow = useCorrection();

  const handleMainRecording = async (blob) => {
    setPipelineStatus("uploading");
    setPipelineError(null);
    try {
      const { session: createdSession } = await createSession(blob);
      setSession(createdSession);

      setPipelineStatus("transcribing");
      const { transcript: createdTranscript } = await transcribeSession(createdSession._id);
      setTranscript(createdTranscript);
      setPipelineStatus("idle");
    } catch (err) {
      setPipelineStatus("error");
      setPipelineError(err.message);
    }
  };

  const handleSelectWord = (wordIndex) => {
    if (acceptedByIndex[wordIndex]) return; // already corrected & accepted in this session
    // Don't open the correction yet — the mode must be chosen first (see
    // handleChooseMode) because the backend fixes a Correction's mode at
    // creation time and every attempt against it reuses that same mode.
    // Opening with a hardcoded mode here, then letting the user "choose" a
    // different one inside the correction panel, would be a UI that does
    // nothing — the real bug this two-step flow replaces.
    setSelectedWordIndex(wordIndex);
    correctionWorkflow.close();
  };

  const handleChooseMode = async (mode) => {
    try {
      await correctionWorkflow.open({
        sessionId: session._id,
        transcriptId: transcript._id,
        wordIndex: selectedWordIndex,
        mode,
      });
    } catch {
      // error surfaced via correctionWorkflow.error in the panel
    }
  };

  const handleAccept = async (attemptId) => {
    const updated = await correctionWorkflow.accept(attemptId);
    const acceptedAttempt = correctionWorkflow.attempts.find((a) => a._id === attemptId);
    setAcceptedByIndex((prev) => ({
      ...prev,
      [updated.wordIndex]: acceptedAttempt?.prediction ?? null,
    }));
  };

  const handleCloseCorrection = () => {
    setSelectedWordIndex(null);
    correctionWorkflow.close();
  };

  const handleNewRecording = () => {
    setSession(null);
    setTranscript(null);
    setPipelineStatus("idle");
    setPipelineError(null);
    setSelectedWordIndex(null);
    setAcceptedByIndex({});
    correctionWorkflow.close();
  };

  const correctionsByIndex = useMemo(() => {
    const map = {};
    for (const [idx, text] of Object.entries(acceptedByIndex)) {
      map[idx] = { status: "accepted", acceptedText: text };
    }
    return map;
  }, [acceptedByIndex]);

  const selectedWord = transcript?.words.find((w) => w.index === selectedWordIndex);

  return (
    <div className="app">
      <header>
        <h1>Bengali ASR Correction — Research Prototype</h1>
        <p className="subtitle">
          Record Bengali speech, review the transcript, and correct any wrong word by re-pronouncing it — no typing required.
        </p>
      </header>

      <section className="record-section">
        <h2>1. Record or upload Bengali speech</h2>
        {!session && (
          <>
            <Recorder label="Record Bengali speech" onRecorded={handleMainRecording} />
            <p className="hint upload-hint">
              Or upload an audio file instead:{" "}
              <input
                type="file"
                accept="audio/*"
                aria-label="Upload a Bengali speech audio file"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleMainRecording(file);
                  e.target.value = "";
                }}
              />
            </p>
          </>
        )}
        {pipelineStatus === "uploading" && <p className="hint" role="status">Uploading audio…</p>}
        {pipelineStatus === "transcribing" && (
          <p className="hint" role="status">Transcribing (this can take a while on first run, or on CPU-only hosting)…</p>
        )}
        {pipelineStatus === "error" && <p className="error-banner" role="alert">{pipelineError}</p>}
        {session && (
          <button className="new-recording-btn" onClick={handleNewRecording}>
            Start a new recording
          </button>
        )}
      </section>

      {transcript && (
        <section className="transcript-section">
          <h2>2. Review transcript — click a wrong word to correct it</h2>
          <TranscriptView
            words={transcript.words}
            selectedIndex={selectedWordIndex}
            onSelectWord={handleSelectWord}
            correctionsByIndex={correctionsByIndex}
          />
        </section>
      )}

      {selectedWord && !correctionWorkflow.correction && (
        <section className="correction-section">
          <h2>
            3. Choose a correction mode for <span lang="bn">{selectedWord.text}</span>
          </h2>
          <div className="mode-choice">
            <button onClick={() => handleChooseMode("pronunciation_only")} disabled={correctionWorkflow.status === "opening"}>
              Pronunciation Only
            </button>
            <button onClick={() => handleChooseMode("pronunciation_meaning")} disabled={correctionWorkflow.status === "opening"}>
              Pronunciation + Meaning/Context
            </button>
            <button onClick={handleCloseCorrection}>Cancel</button>
          </div>
          {correctionWorkflow.status === "opening" && <p className="hint" role="status">Opening correction…</p>}
          {correctionWorkflow.error && <p className="error-banner" role="alert">{correctionWorkflow.error}</p>}
        </section>
      )}

      {selectedWord && correctionWorkflow.correction && (
        <section className="correction-section">
          <h2>4. Correct the selected word</h2>
          <CorrectionPanel
            word={selectedWord}
            mode={correctionWorkflow.correction.mode}
            correction={correctionWorkflow.correction}
            attempts={correctionWorkflow.attempts}
            status={correctionWorkflow.status}
            error={correctionWorkflow.error}
            onSubmitAttempt={correctionWorkflow.attempt}
            onAccept={handleAccept}
            onClose={handleCloseCorrection}
          />
        </section>
      )}
    </div>
  );
}

export default App;
