# Progress

_Last updated: 2026-09-05. This file must always reflect actual repository
state — verify against `git log` / `git status` / the filesystem before
trusting it in a future session._

## Current phase

**Phase 4/5 substantially scaffolded** (pronunciation-only correction +
iterative attempt loop), on top of completed Phases 1–3. Phase 6 (meaning
mode) has a working but v0/placeholder semantic scoring implementation.
Phases 7 onward (deeper phonetic/ranking work, evaluation, MLflow, dataset
ingestion, ZenML, CI hardening, institute GPU) are pending — see below.

## Environment (inspected 2026-09-05)

- Repo was completely empty at session start.
- Node v24.15.0, npm 11.12.1.
- Python: system default is 3.14.4 (too new for stable PyTorch wheels) — `ml-service/venv` uses **Python 3.12** instead.
- Git 2.53.0.
- GPU: NVIDIA GTX 1650, 4GB VRAM, driver 566.07, CUDA 12.7. Confirmed working with `torch==2.5.1+cu121`.
- **No Docker Desktop, no admin rights** to install it in this environment.
- **No system MongoDB, no system ffmpeg** — worked around, see below.

## Decisions made autonomously (routine engineering, documented)

- ml-service Python 3.12, not system default 3.14.
- Whisper engine: `faster-whisper` (CTranslate2), not `openai-whisper` — see `RESEARCH.md`.
- **`WHISPER_MODEL_SIZE=large-v3` / `WHISPER_COMPUTE_TYPE=int8_float16` as the default**, based on real smoke-testing: `small`/`medium` were observed producing wrong-script (Devanagari-like) output for Bengali; `large-v3` int8 was correct and fits the 4GB GPU. See `GPU_SETUP.md` "Model size findings" — this is from 1-2 samples, not a rigorous benchmark, and is flagged as such everywhere it's mentioned.
- ffmpeg: `imageio-ffmpeg` PyPI package (bundled static binary), no system install.
- MongoDB (dev): `mongodb-memory-server`, no system install. Production Mongo hosting is an open decision (see below).
- Windows CTranslate2 DLL fix: reuse PyTorch's bundled `cublas64_12.dll`/`cudnn64_9.dll` via `os.add_dll_directory()` in `ml-service/api/main.py`, rather than a second CUDA runtime install. See `GPU_SETUP.md`.
- Bengali phonetic similarity: ITRANS transliteration (`indic_transliteration`) + Levenshtein distance, documented as an unvalidated interim heuristic, not a validated G2P system (`ml-service/phonetics/README.md`).
- Docker: Dockerfiles + `docker-compose.yml` written but **not build-tested** (no Docker Desktop available). Flagged in every Dockerfile's header comment.

## Completed

- [x] Phase 0 inspection
- [x] Monorepo structure; root docs: README, ARCHITECTURE, RESEARCH, PROGRESS, DATA_PIPELINE, EXPERIMENTS, API, GPU_SETUP
- [x] `.gitignore`, `.env.example`
- [x] **ml-service** (Python 3.12 venv, all deps installed and verified):
  - [x] `utils/config.py` — env-driven settings, nothing hardcoded
  - [x] `audio/preprocessing.py` — configurable resample/mono/normalize/trim; VAD/denoise are documented no-op placeholders
  - [x] `whisper/engine.py` — faster-whisper wrapper (`transcribe`, `transcribe_word_hypotheses`)
  - [x] `phonetics/` — ITRANS-based G2P, similarity, heuristic syllabification, with an honest limitations README
  - [x] `correction/` — pluggable `CorrectionEngine` interface + `pronunciation_engine.py` (Mode A fully real; Mode B semantic score is a v0 literal-containment placeholder, documented as such)
  - [x] `ranking/ranker.py` — configurable weighted scoring
  - [x] `api/main.py` — FastAPI app, `/health`, `/transcribe`, `/correct`
  - [x] **Verified end-to-end against real (synthetic gTTS) Bengali audio**: transcription produces correct Bengali script + structured words; correction endpoint correctly recovers a mis-transcribed word from a re-pronunciation clip
  - [x] `tests/` — 9 tests (7 fast unit/mechanics tests + 2 marked `@pytest.mark.model` real-inference tests), all passing locally on GPU
- [x] **backend** (Node/Express):
  - [x] Mongoose models with the raw/prediction/feedback/validated/ground-truth distinction enforced in schema (`Correction`, `CorrectionAttempt`, append-only attempts)
  - [x] Routes: sessions (create/transcribe/get), corrections (create/attempt/accept/get)
  - [x] `mlServiceClient.js`, audio upload validation (type/size), error handling
  - [x] Tests (Jest + Supertest + mongodb-memory-server) — 3 passing
- [x] **frontend** (Vite + React):
  - [x] API layer separated from components (`src/api/client.js`)
  - [x] `useAudioRecorder` hook — handles mic permission/error states explicitly
  - [x] `TranscriptView` — structured word rendering keyed by stable index, not text (correct for repeated words / Bengali Unicode)
  - [x] `CorrectionPanel` + `useCorrection` hook — mode A/B selection, slow/syllable instructions, attempt history, accept/retry, loading/error states
  - [x] `npm run build` succeeds; dev server verified serving correctly via curl
  - [x] **NOT visually verified in an actual browser** — no browser automation tool was connected this session (user chose to skip Claude-in-Chrome install). The mic-permission flow, click-to-select-word interaction, and full recording round-trip have only been verified at the code/build level, not by actually using the UI. This should be manually tested by the user, or automated in a future session once browser tools are available.
- [x] Docker files + docker-compose (written, **not build-tested**)
- [x] GitHub Actions CI (`backend` + `ml-service` (non-model tests only) + `frontend` build/lint) — not yet run against the real GitHub remote, only validated locally by running the equivalent commands
- [x] Real dataset research (`DATA_PIPELINE.md`): OpenSLR SLR53, Common Voice Bengali, AI4Bharat IndicVoices/-R, Bengali.AI OOD-Speech, IndicSUPERB — sizes/licenses sourced from web search, not independently downloaded/verified yet

## Known issues / open questions for the user

- **Dataset licensing decisions pending** (per project rule — this needs your input, not a unilateral choice): OpenSLR SLR53 is CC-BY-SA-4.0 (share-alike — need your call on whether that's acceptable given how we'll publish/use derived data); Bengali.AI OOD-Speech's license wasn't found and needs to be checked before any use.
- **No dataset has been downloaded or used yet.** Only synthetic gTTS smoke-test clips exist (`ml-service/tests/fixtures/`).
- Institute GPU access not yet available — Phase 13 benchmarking blocked until then.
- Production MongoDB hosting (self-hosted on institute server vs. managed service) not yet decided.
- Docker Desktop not installed locally — containers are written but unverified. If you'd like me to proceed with a Docker Desktop install, that needs admin rights I don't have in this environment; you'd need to install it, or grant admin access.
- Semantic scoring (Mode B) is currently a weak v0 placeholder (literal substring containment) — real embedding-based semantic scoring is future work (Phase 6/7 follow-up), not yet built. Contextual scoring is entirely unimplemented (always 0.0).
- Real Bengali phonetic/G2P validation (vs. the current ITRANS+Levenshtein heuristic) has not been done — `ml-service/phonetics/README.md` documents this gap.

## Test status (as of this writing, all verified locally)

- ml-service: `pytest tests/ -v` → 9 passed (includes real GPU Whisper inference)
- backend: `npm test` → 3 passed (Jest + mongodb-memory-server)
- frontend: `npm run build` → succeeds; `npm run lint` → clean

## Experiments completed

**None.** The findings in `GPU_SETUP.md`/`RESEARCH.md` about model-size script
correctness and স/শ ambiguity are real observations from smoke-testing, not
rigorous experiments — they're explicitly flagged as such everywhere they
appear and must not be cited as validated results.

## Next steps (in rough priority order)

1. User: decide on dataset licensing questions above so Stage 1 (`DATA_PIPELINE.md`) can start.
2. Manually test the frontend in a real browser (mic permissions, recording, word selection, correction flow) — not yet done this session.
3. Implement `ml-service/evaluation/` (CER/WER/correction-accuracy) once a dataset decision is made.
4. Real embedding-based semantic scoring for Mode B (replace the v0 placeholder).
5. MLflow integration (Phase 9) once there's a real evaluation to track.
6. Verify Docker builds once Docker Desktop is available.
