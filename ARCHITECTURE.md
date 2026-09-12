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

Run the real (non-smoke) pipeline with `uv run python -m pipelines.evaluation_pipeline`
(defaults match the official 200-sample/seed-42 configuration already used for
the standalone scripts). As of 2026-09-07 the project uses `uv` for Python
dependency/environment management (root `pyproject.toml`/`uv.lock`) instead of
a manually-managed `venv` + `requirements.txt` — see `GPU_SETUP.md`.

## Local ML hosting + tunnel (current public configuration, 2026-09-12)

The browser never talks to ml-service directly (see "System overview" above)
— it is only ever reached via the Node backend's `ML_SERVICE_URL`. This makes
*where* ml-service actually runs a pure configuration choice, not an
architectural one: local dev, a tunneled laptop, or the institute L40 are all
"some URL `ML_SERVICE_URL` points at," switchable without touching backend or
frontend code (see GPU_SETUP.md "Institute GPU").

**Render's free web-service tier cannot run this project's ml-service at
all** — this is a measured finding (2026-09-12, on this project's own dev
GPU laptop), not a guess, and is why the ML leg is NOT deployed to Render:

| Model (faster-whisper, CPU, int8) | Real RSS measured | Real output on a real Bengali sample |
|---|---|---|
| `tiny` | ~305 MB | `'Amar shonar banglami tomai vhalobashi'` — **romanized/Banglish, not Bengali script** |
| `base` | ~341 MB | `'Amar sonar bangla amitomay bhalobashi.'` — **romanized/Banglish, not Bengali script** |
| `small` | ~499 MB (at Render's 512MB ceiling) | Devanagari-script transliteration — **not Bengali script** |
| `medium` | ~1005 MB — **exceeds the 512MB budget outright** | genuinely Bengali script, but can't fit |

(Ground truth for the sample: "আমার সোনার বাংলা, আমি তোমায় ভালোবাসি" — the
opening of Bangladesh's national anthem, the project's standing smoke-test
line; see GPU_SETUP.md.) No model size that fits Render's free 512MB produces
correct Bengali script — this isn't a tuning problem; lowering
`WHISPER_BEAM_SIZE` or disabling semantic scoring doesn't change a model's
learned output script. Render's free tier was therefore ruled out by real
evidence, not assumption, and no paid Render plan was purchased to work
around it (per explicit instruction: Render stays 100% free, backend-only).

**Current arrangement: the ml-service runs on the user's own laptop**
(AMD Ryzen 5 4600H, 32GB RAM, NVIDIA GTX 1650/4GB VRAM), using the exact same
`large-v3`/`cuda`/`int8_float16` configuration already validated by this
project's own 200-sample real baseline eval (see EXPERIMENTS.md) — re-verified
working on this exact GPU on 2026-09-12: `torch.cuda.is_available()` ->
`True`, real inference in ~6s (incl. model load) on a real Bengali sample,
correct Bengali script output (`'আমার শোনার বাংলা আমি তোমায় ভালো বাশি'`),
~1.5-2GB of the 4GB VRAM used, released cleanly after the process exits.

- `scripts/start-local-ml.ps1` — starts `uvicorn api.main:app` (via `uv run
  --directory ml-service`) and a free Cloudflare **Quick Tunnel**
  (`tools/cloudflared.exe tunnel --url http://127.0.0.1:8000` — no
  Cloudflare account or domain needed), prints the public
  `https://*.trycloudflare.com` URL, and health-checks it for real before
  declaring success.
- **Quick Tunnel limitation, stated plainly:** the public hostname is
  randomly generated *every time the script restarts* — there is no free way
  to get a stable hostname without a Cloudflare account + a domain you own
  (a named Tunnel instead of a Quick Tunnel). Whenever the laptop/tunnel
  restarts, `ML_SERVICE_URL` must be updated in the Render dashboard to the
  new URL. The laptop must stay powered on, FastAPI must keep running, and
  the tunnel must keep running for the public app to actually work — this is
  explicitly a temporary/dev-grade hosting arrangement, not a production SLA.
- **Shared-secret auth** (`ml-service/api/main.py`'s `require_api_key`
  dependency, gating `POST /transcribe` and `POST /correct` — `/health` stays
  open): once ml-service is reachable from the public internet rather than a
  private Docker network, it needs *some* access control. `ML_SERVICE_API_KEY`
  must match between the backend and ml-service; sent only as the
  `X-ML-Service-Key` header on backend -> ml-service requests
  (`mlServiceClient.js`), never forwarded to or readable by the browser.
  Empty (default) = no auth, for local-only dev where this was never
  internet-facing before.
- Lexicon-augmented candidate generation, LaBSE semantic scoring, and the
  full correction-engine research design are all unchanged and running for
  real on the laptop — no feature was cut to make this fit, because the
  laptop (32GB RAM) has no memory pressure Render's free tier had.

Switching to the institute L40 later (spec section 17/20) means: deploy
ml-service there with `docker/ml-service.Dockerfile` (the existing
GPU/large-v3 image, unchanged) instead of the laptop, then change
`ML_SERVICE_URL` on the Render backend to point at it. No backend/frontend
code changes either way — this is the entire reason ml-service's location is
a config value, not an architectural one.

## Deployment

**Frontend and backend are actually deployed and verified live** (2026-09-06/07
— see `PROGRESS.md` "Production deployment" for the full verification detail,
including the real Atlas IP-whitelist failure and fix):
- Frontend: Vercel, static Vite build, manual `vercel --prod` redeploy per
  push (GitHub auto-connect failed, not yet resolved).
- Backend: Render web service (`render.yaml`), `autoDeploy: yes` on `main` —
  this one DOES auto-deploy on future pushes. Connected to a real MongoDB
  Atlas cluster.
- **ml-service runs on the user's own laptop, reached via a free Cloudflare
  Quick Tunnel** (2026-09-12, see "Local ML hosting + tunnel" above) —
  real-verified end-to-end (local backend -> tunnel -> laptop Whisper ->
  candidates -> accept), not deployed anywhere else. `btp-backend`'s
  `ML_SERVICE_URL`/`ML_SERVICE_API_KEY` on Render still need to be set to the
  laptop's current tunnel URL/secret by the account owner (Render dashboard —
  this session had no Render API key to do it directly); see `PROGRESS.md`
  "Blocked on credentials" for the exact remaining step.

For local multi-service dev: Docker Compose (`docker-compose.yml`). Docker
Desktop is not installed in the current dev environment (no admin rights) —
compose files are written but unverified locally until Docker is available;
see `PROGRESS.md`. Object storage for audio at scale (spec section 15) is
also not yet implemented — Render's free-tier disk is ephemeral, documented
in `render.yaml`'s header comment.
