# Architecture

## System overview

```
┌────────────┐   HTTP (REST)   ┌──────────────┐   HTTP (REST)   ┌───────────────┐
│  frontend  │ ───────────────▶│   backend     │ ───────────────▶│  ml-service   │
│  React     │◀─────────────── │  Node/Express │◀─────────────── │  Python/FastAPI│
└────────────┘                 └──────┬───────┘                 └───────┬───────┘
                                       │                                 │
                                       ▼                                 ▼
                                  ┌─────────┐                     ┌─────────────┐
                                  │ MongoDB │                     │ Whisper /   │
                                  │ (state, │                     │ correction  │
                                  │ history)│                     │ engine (GPU)│
                                  └─────────┘                     └─────────────┘
                                       │
                                       ▼
                                 ┌───────────┐
                                 │  Audio    │
                                 │  storage  │ (local fs in dev; object storage later)
                                 └───────────┘
```

**Why this split:** Node never runs Whisper/PyTorch inference directly (heavy,
GPU-bound, Python-native). Node owns application state, session/correction
lifecycle, and persistence; the ML service is a stateless-per-request inference
API that Node calls over HTTP. This lets the ML service be benchmarked,
containerized, and deployed to institute GPU hardware independently of the app
server.

## Services

### frontend (`frontend/`)
React (Vite). Responsible for: audio recording (MediaRecorder API), structured
transcript rendering (word/segment objects, not a single string — required for
correct Bengali Unicode handling and stable word selection), word selection UI,
correction panel (mode A/B), attempt history, loading/error states. Talks only
to the backend, never directly to the ML service.

### backend (`backend/`)
Node.js + Express. Owns:
- session lifecycle
- transcript state (post-correction transcript is derived, not mutated in place —
  see Data Model below)
- correction + correction-attempt persistence (MongoDB)
- calling the ML service for transcription and correction inference
- request validation, audio upload validation (size/type)

Does not implement any ML logic itself.

### ml-service (`ml-service/`)
Python + FastAPI. Structure:
```
ml-service/
  api/          FastAPI routers
  audio/        preprocessing (resample, mono, VAD, normalize, denoise, segment) — each configurable/toggleable
  whisper/      Whisper (faster-whisper) wrapper: model loading, config, inference, structured output
  correction/   pluggable correction-engine interface + implementations (baseline, pronunciation, +syllable, +semantic, hybrid)
  phonetics/    Bengali phonetic representation / syllable segmentation / pronunciation matching
  semantics/    optional meaning/context evidence scoring
  ranking/      candidate ranking combining acoustic/phonetic/semantic/contextual scores, configurable weights
  evaluation/   CER/WER/correction-accuracy computation utilities
  utils/        shared helpers (config loading, logging)
```

**Engine choice:** `faster-whisper` (CTranslate2), not `openai-whisper` — see
`RESEARCH.md` "Engineering choices" for why this doesn't affect the research
question and why it was necessary for local dev (4GB GPU).

**Configuration, not hardcoding:** model size, device (cuda/cpu), compute type
(int8/fp16/fp32), decoding params (beam size, temperature, language), and every
preprocessing toggle live in `configs/` / environment variables — never
hardcoded inline. This is required by the spec (section 9/10) and by the need
to run experiments that vary exactly one of these at a time.

## Data model (MongoDB)

Collections (see `DATA_PIPELINE.md` for full field lists):
- `sessions` — one per recording session
- `transcripts` — Whisper output for a session, as structured word/segment list with stable ids
- `corrections` — one per user-flagged word (references transcript + word index)
- `correction_attempts` — one per re-pronunciation attempt on a correction (never overwritten; append-only)
- `speakers`, `users` — identity metadata where applicable
- `dataset_metadata`, `experiments` — populated once evaluation/MLflow work begins

Critical invariant (from `RESEARCH.md`): a `correction_attempts` document stores
the model's `prediction` separately from `accepted` (boolean, user-set). A
prediction is never treated as ground truth. If a correction is never flagged,
the original Whisper word is implicitly accepted — this is a read-time
derivation for building the "current transcript" view, not a write to the
original transcript.

## REST API (initial; see `API.md` for the authoritative, current contract)

```
POST /api/sessions
POST /api/sessions/:id/transcribe        (upload audio -> ml-service -> structured transcript)
GET  /api/sessions/:id
POST /api/corrections                    (flag a word: session, transcript, word index, mode)
POST /api/corrections/:id/attempts       (upload re-pronunciation [+ optional meaning] -> ml-service -> ranked candidates)
POST /api/corrections/:id/accept         (accept a specific attempt's prediction)
GET  /api/corrections/:id
```

## Correction engine plugin interface (ml-service/correction/)

Every correction method implements the same interface (candidate word audio +
context in, ranked candidate list out) so frontend/backend never need to change
when comparing methods:

```python
class CorrectionEngine(Protocol):
    def generate_candidates(self, request: CorrectionRequest) -> list[Candidate]: ...
```

`CorrectionRequest` carries: re-pronunciation audio, the flagged word's original
Whisper hypothesis, surrounding transcript context, optional user-supplied
meaning, and mode (A/B). `Candidate` carries: text, and the separated
acoustic/phonetic/semantic/contextual scores (before weighting), so ranking
weights can be changed post-hoc during evaluation without re-running inference.

## Pipeline orchestration (ZenML) (`pipelines/`)

`pipelines/evaluation_pipeline.py` (`bengali_asr_evaluation_pipeline`) chains
five stages as ZenML steps (`pipelines/steps.py`): dataset ingestion ->
speaker-disjoint split -> Whisper baseline eval -> error-category analysis ->
correction-method eval (Experiments A/B/C). Every stage that has its logic
inline in an existing standalone script (ingest, split, baseline eval,
correction eval — `scripts/build_manifest.py`, `scripts/split_dataset.py`,
`ml-service/scripts/run_baseline_eval.py`,
`ml-service/scripts/run_correction_eval.py`) is orchestrated by invoking that
exact script via `subprocess`, not by re-implementing its logic — a single
source of truth, so the pipeline cannot silently diverge from what
`EXPERIMENTS.md` documents as directly reproducible. The error-analysis step
is the one exception: it imports `analyze_baseline_errors.py`'s already-pure
functions directly. All parameters (dataset paths, sample counts, split
ratios, seed) are step/pipeline arguments, never hardcoded — per spec section
44, scaling to more data is a parameter change, not a code change.

**Verified (2026-09-06/07):** `zenml init` at the repo root, then
`python -m pipelines.evaluation_pipeline --max-samples 8 --smoke` run
end-to-end from a clean process — all 5 steps completed successfully with
real Whisper inference and real correction-engine scoring on a small
(8-sample) slice, using the `--smoke` flag's separate artifact
paths/MLflow-experiment names so it never overwrites the official 200-sample
Experiment A/B/C results already recorded in `EXPERIMENTS.md`. This is a
pipeline-*mechanics* verification, not a new experiment result — the 8-sample
numbers it produced are not meant to be cited. Two environment notes, not
correctness bugs: (1) `zenml[server]` (not bare `zenml`) is required — the
base package is missing `pymysql`/`sqlmodel` that even the local SQLite
metadata store needs; this forced `fastapi`/`pydantic`/`starlette` version
bumps, re-verified against the full ml-service test suite afterward with no
regressions (see `PROGRESS.md`). (2) ZenML's daemon-based orchestration is
unavailable on Windows ("Daemon functionality is currently not supported on
Windows"), so runs execute synchronously in-process — sufficient at this
project's scale.

Run the real (non-smoke) pipeline with `python -m pipelines.evaluation_pipeline`
(defaults match the official 200-sample/seed-42 configuration already used for
the standalone scripts).

## Deployment (planned, not yet built)

Docker Compose for local multi-service dev; institute GPU for ml-service in
production/benchmarking; object storage for audio at scale. See `GPU_SETUP.md`
and `docker-compose.yml`. **Note:** Docker Desktop is not installed in the
current dev environment (no admin rights) — compose files are written but
unverified locally until Docker is available; see `PROGRESS.md`.
