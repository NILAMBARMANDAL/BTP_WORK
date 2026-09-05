# Progress

_Last updated: 2026-09-06. This file must always reflect actual repository
state — verify against `git log` / `git status` / the filesystem before
trusting it in a future session._

## Current phase

**Phases 1-6 complete with real (not placeholder) implementations; Stage 1
dataset + Whisper baseline evaluation + MLflow tracking now exist with real
measured results.** Phonetic scoring now uses espeak-ng (real G2P) rather
than the old ITRANS heuristic; semantic scoring (Mode B) now uses real LaBSE
sentence embeddings rather than the old literal-containment placeholder.
Remaining major gaps: systematic Whisper error-category analysis, a real
correction-attempt dataset from actual user interactions, speaker-disjoint
train/val/test splits, ZenML pipeline, CI hardening for the new deps, and
institute GPU access — see below.

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
- **Bengali phonetics: espeak-ng (real G2P) now primary**, not the ITRANS heuristic — `ml-service/phonetics/espeak_g2p.py`, set up locally via `ml-service/scripts/setup_espeak.ps1` (admin-free `msiexec /a` extraction into gitignored `ml-service/vendor/`; on Linux/Docker it's just `apt-get install espeak-ng`, already added to the Dockerfile and CI). ITRANS remains an automatic fallback if espeak-ng isn't found. See `ml-service/phonetics/README.md`.
- **Semantic scoring (Mode B): real LaBSE embeddings now primary**, not the v0 literal-containment placeholder — `ml-service/semantics/embedder.py`. Chose LaBSE (Google, Apache-2.0) over the more commonly recommended `paraphrase-multilingual-mpnet-base-v2` specifically because the latter's published language list does not include Bengali and LaBSE's does — checked, not assumed. Runs on CPU by default (`SEMANTIC_DEVICE=cpu`) to avoid contending with Whisper for the 4GB GPU. Falls back to literal containment if the model can't load. See `ml-service/semantics/README.md`.
- Evaluation metrics (`ml-service/evaluation/metrics.py`) use `jiwer` (established library) for WER/CER, plus a `normalize_transcript()` step (strip punctuation, NFC-normalize, collapse whitespace) applied before scoring by default — found necessary after observing Whisper emit trailing punctuation (e.g. "?") that OpenSLR reference transcripts don't have, which was inflating WER on non-substantive differences. Both normalized and raw rates are reported for transparency.
- Dataset acquisition: fetched a 200-sample subset of OpenSLR SLR53 via HTTP range requests (`remotezip`), not a full ~900MB shard download — see `DATA_PIPELINE.md`. A manifest (`data/processed/openslr_53_shard0_manifest.json`) pins the exact sample selection via a `manifest_sha256` (hash of the selection, not the full remote shard, which was never downloaded).

## Completed

- [x] Phase 0 inspection
- [x] Monorepo structure; root docs: README, ARCHITECTURE, RESEARCH, PROGRESS, DATA_PIPELINE, EXPERIMENTS, API, GPU_SETUP
- [x] `.gitignore`, `.env.example`
- [x] **ml-service** (Python 3.12 venv, all deps installed and verified):
  - [x] `utils/config.py` — env-driven settings, nothing hardcoded
  - [x] `audio/preprocessing.py` — configurable resample/mono/normalize/trim; VAD/denoise are documented no-op placeholders
  - [x] `whisper/engine.py` — faster-whisper wrapper (`transcribe`, `transcribe_word_hypotheses`)
  - [x] `phonetics/` — espeak-ng G2P (`espeak_g2p.py`) as primary method, ITRANS as automatic fallback, similarity, heuristic syllabification, with an honest limitations README
  - [x] `semantics/embedder.py` — real LaBSE sentence-embedding semantic scoring (Mode B), literal-containment as automatic fallback
  - [x] `evaluation/metrics.py` — CER/WER (via `jiwer`) with punctuation/whitespace normalization, correction-stats, latency aggregation
  - [x] `correction/` — pluggable `CorrectionEngine` interface + `pronunciation_engine.py` (Mode A and Mode B both grounded in real scoring now — no placeholders left in the scoring path)
  - [x] `ranking/ranker.py` — configurable weighted scoring
  - [x] `api/main.py` — FastAPI app, `/health`, `/transcribe`, `/correct`
  - [x] **Verified end-to-end against real (synthetic gTTS) Bengali audio**: transcription produces correct Bengali script + structured words; correction endpoint correctly recovers a mis-transcribed word from a re-pronunciation clip
  - [x] `tests/` — 24 tests (19 fast unit/mechanics tests + 5 marked `@pytest.mark.model` real-inference/real-embedding tests), all passing locally on GPU
- [x] **Stage 1 dataset + baseline evaluation (2026-09-06, real, not scaffolded):**
  - [x] `scripts/build_manifest.py` — fetched 200 real audio samples from OpenSLR SLR53 shard 0 via `remotezip` HTTP range requests (~14MB transferred, not the full ~900MB shard); manifest at `data/processed/openslr_53_shard0_manifest.json`
  - [x] `ml-service/scripts/run_baseline_eval.py` — ran real Whisper (`large-v3`, int8_float16, CUDA) inference on all 200 samples: **WER 0.8106 (normalized) / 0.2580 CER**, avg latency 3718.8ms/sample — see `EXPERIMENTS.md` Experiment A for full detail and manual sanity-check of 5 sample transcripts
  - [x] MLflow tracking wired up and used for this real run (`ml-service/mlruns/`, experiment `bengali-asr-baseline`) — Phase 9 started with a real experiment, not a stub
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
- [x] Docker files + docker-compose (written, **not build-tested**; espeak-ng now added to the ml-service image)
- [x] GitHub Actions CI (`backend` + `ml-service` (non-model tests only) + `frontend` build/lint) — espeak-ng apt-get step added for the new phonetics path; still not yet run against the real GitHub remote, only validated locally by running the equivalent commands
- [x] Real dataset research (`DATA_PIPELINE.md`): OpenSLR SLR53, Common Voice Bengali, AI4Bharat IndicVoices/-R, Bengali.AI OOD-Speech, IndicSUPERB — sizes/licenses sourced from web search; **OpenSLR SLR53 now actually acquired** (200-sample manifest, see above), others still unverified/unused

## Known issues / open questions for the user

- **Dataset licensing:** proceeded with OpenSLR SLR53 (CC-BY-SA-4.0, a clear share-alike license appropriate for academic thesis use with attribution) for Stage 1 baseline work — this is a defensible research/eval use, not redistribution, but flag it explicitly: if results or derived data are published, CC-BY-SA-4.0's share-alike/attribution terms apply. Bengali.AI OOD-Speech's license is still unresolved and has not been used.
- Institute GPU access not yet available — GPU_SETUP.md's institute-server benchmarking is blocked until then. The baseline eval above ran on the local dev 4GB GTX 1650, not institute hardware.
- Production MongoDB hosting (self-hosted on institute server vs. managed service) not yet decided.
- Docker Desktop not installed locally — containers are written but unverified. If you'd like me to proceed with a Docker Desktop install, that needs admin rights I don't have in this environment; you'd need to install it, or grant admin access.
- Contextual (language-model fluency) scoring is entirely unimplemented (`contextual_score` always 0.0) — this is genuinely future work, not started.
- The OpenSLR manifest is a single 200-sample pool, not yet speaker-disjoint-split into train/val/test (168 unique speakers, 31 with 2-3 samples each) — needed before running any correction-method comparison that must protect a held-out test set.
- No systematic Whisper error-category analysis has been done yet (rare words / proper nouns / place names / phonetically-similar words / fast vs. noisy speech) — only 5 samples were manually inspected as a sanity check on the aggregate WER/CER, not a real categorized analysis.

## Test status (as of this writing, all verified locally)

- ml-service: `pytest tests/ -v` → 24 passed (5 marked `@pytest.mark.model`, includes real GPU Whisper inference and real LaBSE embedding inference)
- backend: `npm test` → 3 passed (Jest + mongodb-memory-server)
- frontend: `npm run build` → succeeds; `npm run lint` → clean

## Experiments completed

**Experiment A (Whisper baseline) — real, MLflow-tracked result.** See
`EXPERIMENTS.md` for full detail: WER 0.8106 / CER 0.2580 (normalized) on 200
real OpenSLR SLR53 samples, `large-v3` int8_float16 on the dev GPU. The
earlier `GPU_SETUP.md`/`RESEARCH.md` findings about model-size script
correctness and স/শ ambiguity remain real observations from smoke-testing,
not rigorous experiments — still flagged as such, not upgraded to "results."

## Next steps (in rough priority order)

1. Speaker-disjoint train/validation/test split of the OpenSLR pool (and any
   future dataset additions) before running correction-method comparisons —
   currently a single undivided 200-sample pool.
2. Systematic Whisper error-category analysis (rare words, proper nouns,
   place names, phonetically-similar words, speech rate, noise) on a larger
   sample than the 5 manually inspected so far, to decide which correction
   scenarios are actually worth targeting — per the project rule not to
   assume categories matter without data support.
3. Build the real correction-attempt dataset schema/recording path end-to-end
   (backend already has the raw/prediction/feedback/validated distinction in
   its Mongoose schema — verify it captures every field the spec requires:
   attempt_number, correction method, optional meaning, speaker metadata).
4. Manually test the frontend in a real browser (mic permissions, recording,
   word selection, correction flow) — still not done in any session so far.
5. Run Experiments B-E (pronunciation/syllable/meaning-mode correction
   comparisons) once 1-3 above exist — currently blocked on real correction
   interaction data, not on scoring-method implementation (which is done).
6. Verify Docker builds once Docker Desktop is available.
7. ZenML pipeline once the above stages are individually stable (per the
   project's "no fake wrapper pipeline" rule).
