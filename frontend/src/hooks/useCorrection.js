import { useCallback, useState } from "react";
import { acceptAttempt, createCorrection, submitAttempt } from "../api/client.js";

/**
 * Owns the state machine for one word's correction workflow: open a
 * correction, submit re-pronunciation attempts (each appended, never
 * overwritten — matches backend's append-only CorrectionAttempt model),
 * accept one, or leave it open. Kept separate from UI components.
 */
export function useCorrection() {
  const [correction, setCorrection] = useState(null); // { _id, wordIndex, mode, status, ... }
  const [attempts, setAttempts] = useState([]);
  const [status, setStatus] = useState("idle"); // idle | opening | submitting | accepting | error
  const [error, setError] = useState(null);

  const open = useCallback(async ({ sessionId, transcriptId, wordIndex, mode }) => {
    setStatus("opening");
    setError(null);
    setAttempts([]);
    try {
      const { correction: created } = await createCorrection({ sessionId, transcriptId, wordIndex, mode });
      setCorrection(created);
      setStatus("idle");
      return created;
    } catch (err) {
      setStatus("error");
      setError(err.message);
      throw err;
    }
  }, []);

  const attempt = useCallback(
    async ({ audioBlob, pronunciationStyle, meaningContext }) => {
      if (!correction) throw new Error("No open correction to attempt against.");
      setStatus("submitting");
      setError(null);
      try {
        const { attempt: created } = await submitAttempt(correction._id, {
          audioBlob,
          pronunciationStyle,
          meaningContext,
        });
        setAttempts((prev) => [...prev, created]);
        setStatus("idle");
        return created;
      } catch (err) {
        setStatus("error");
        setError(err.message);
        throw err;
      }
    },
    [correction]
  );

  const accept = useCallback(
    async (attemptId) => {
      if (!correction) throw new Error("No open correction to accept.");
      setStatus("accepting");
      setError(null);
      try {
        const { correction: updated } = await acceptAttempt(correction._id, attemptId);
        setCorrection(updated);
        setStatus("idle");
        return updated;
      } catch (err) {
        setStatus("error");
        setError(err.message);
        throw err;
      }
    },
    [correction]
  );

  const close = useCallback(() => {
    setCorrection(null);
    setAttempts([]);
    setStatus("idle");
    setError(null);
  }, []);

  return { correction, attempts, status, error, open, attempt, accept, close };
}
