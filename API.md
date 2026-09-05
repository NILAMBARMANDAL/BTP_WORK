# API

Authoritative, current contract. Update this file whenever routes actually
change — do not let it drift from `backend/src/routes/*` / `ml-service/api/main.py`.

## Backend (Node/Express) — `http://localhost:4000`

### `GET /health`
`{ "status": "ok" }`

### `POST /api/sessions`
Multipart form: `file` (audio, required), `speakerId` (optional string).
Creates a session and stores the original audio. Returns `{ session }`.

### `POST /api/sessions/:id/transcribe`
Sends the session's stored audio to the ML service, persists the structured
transcript. Returns `{ transcript }` where `transcript.words` is
`[{ index, text, start, end, confidence }, ...]` (never a single string).

### `GET /api/sessions/:id`
Returns `{ session, transcript }` (latest transcript for that session, if any).

### `POST /api/corrections`
Body (JSON): `{ sessionId, transcriptId, wordIndex, mode }` where
`mode` is `"pronunciation_only"` or `"pronunciation_meaning"`.
Flags one transcript word for correction. Returns `{ correction }`.

### `POST /api/corrections/:id/attempts`
Multipart form: `file` (re-pronunciation audio, required),
`pronunciationStyle` (`"slow"` | `"syllable"`, optional, default `"slow"`),
`meaningContext` (optional string, Mode B only).
Sends the attempt to the ML service, stores the result (append-only — never
overwrites a prior attempt). Returns `{ attempt }` including ranked
`candidates` and `prediction` (a model prediction, NOT yet accepted).

### `POST /api/corrections/:id/accept`
Body: `{ attemptId }`. Marks that attempt's prediction as the accepted
correction. Returns `{ correction, attempt }`.

### `GET /api/corrections/:id`
Returns `{ correction, attempts }` — the full, unmodified attempt history.

## ML service (FastAPI) — `http://localhost:8000`

Called only by the backend, never directly by the frontend.

### `GET /health`
`{ "status": "ok" }`

### `POST /transcribe`
Multipart form: `file` (audio).
```json
{
  "text": "...",
  "language": "bn",
  "config": { "modelSize": "large-v3", "device": "cuda", "computeType": "int8_float16", "beamSize": 5 },
  "words": [{ "index": 0, "text": "...", "start": 0.0, "end": 0.44, "confidence": 0.99 }],
  "preprocessing_applied": ["resample:16000"]
}
```

### `POST /correct`
Multipart form: `file` (re-pronunciation audio), `original_word` (string),
`context_text` (string, full transcript text for context), `mode`
(`"pronunciation_only"` | `"pronunciation_meaning"`), `meaning_context`
(optional string).
```json
{
  "prediction": "সোনার",
  "candidates": [
    {"text": "সোনার", "acousticScore": 0.87, "phoneticScore": 0.86, "semanticScore": 0.0, "contextualScore": 0.0, "finalScore": 0.69}
  ],
  "ranking_weights": {"acoustic": 0.4, "phonetic": 0.4, "semantic": 0.1, "contextual": 0.1}
}
```
Note: `semanticScore` (Mode B only) is real LaBSE embedding similarity as of
2026-09-06 (`ml-service/semantics/embedder.py`), falling back to a literal-
containment heuristic only if the model can't load in a given environment —
see `ml-service/semantics/README.md` for validation status/limitations.
`contextualScore` is still an unimplemented placeholder, always `0.0` — see
`ml-service/correction/pronunciation_engine.py` docstring and `RESEARCH.md`.
