# Progress

_Last updated: 2026-09-08. This file must always reflect actual repository
state — verify against `git log` / `git status` / the filesystem before
trusting it in a future session._

## Current phase

**Phases 1-6 complete with real (not placeholder) implementations; Stage 1
dataset + Whisper baseline evaluation + speaker-disjoint split + a first
(TTS-proxy) correction-method comparison all exist with real, MLflow-tracked
results.** Phonetic scoring uses espeak-ng (real G2P); semantic scoring
(Mode B) uses real LaBSE sentence embeddings. The OpenSLR 200-sample pool is
now split speaker-disjointly into train/val/test (`scripts/split_dataset.py`),
and Experiments B/C (slow vs. syllable-level correction) have a real, if
TTS-proxy-limited and small-sample, result, **now re-run with lexicon-
augmented candidate generation (2026-09-07/08, see below and
`EXPERIMENTS.md`): 6.9% slow / 0% syllable** (up from the original 3.4%/0% —
a 1-sample, not statistically meaningful change on the slow condition, and no
change at all on syllable). **Syllable-level still underperforms whole-word
slow re-pronunciation** — see `EXPERIMENTS.md` for the full result. Remaining
major gaps: real correction-attempt data from an actual live user session
(frontend still not manually browser-tested — no browser automation tool is
connected in this environment, confirmed again 2026-09-07), Experiment D
(meaning/context — deliberately not proxy-synthesized, see `EXPERIMENTS.md`),
Docker build verification, and institute GPU access — still blocked on
connection details only the user can provide, see below.

## 2026-09-07/08 session

- **Python dependency management migrated to `uv`** (root `pyproject.toml` +
  `uv.lock` replace the previous `ml-service/venv` + `requirements.txt` /
  `requirements-dev.txt`, which are kept only as a superseded reference during
  transition, clearly marked as such). One environment now covers both
  `ml-service/` and the repo-root `pipelines/`/`scripts/`, matching how those
  were already invoked. Verified, not just installed: `torch.cuda.is_available()`
  → `True` (real GTX 1650 detected) and the full test suite (32 tests, incl.
  the 5 real-GPU-inference/real-embedding `@pytest.mark.model` tests) passes
  under the new environment. CI (`.github/workflows/ci.yml`) updated to use
  `astral-sh/setup-uv` + `uv sync --locked` instead of `pip install -r
  requirements.txt` — not yet verified against a real GitHub Actions run (that
  needs an actual push, see Git status below).
- **GitHub SSH checked, not usable from this network**: `ssh -T git@github.com`
  timed out on port 22 (common firewall behavior) — moot anyway since the
  existing `origin` remote is HTTPS and already has working push access from a
  prior session; left as-is rather than switching to a transport that just
  failed.
- **Institute GPU: still blocked, unchanged.** An instruction this session
  asserted an institute L40 server was available with "SSH access: confirmed"
  and gave specs, but no hostname/IP, port, username, or auth method has
  actually appeared anywhere in this conversation or repo, and this session's
  shell tools only execute on the local dev machine (no SSH client tool call
  available). Nothing was inspected or deployed there — see `GPU_SETUP.md`
  "Institute GPU" for the exact blocker and what's needed to unblock it.
- **Lexicon-augmented candidate generation implemented**
  (`ml-service/phonetics/lexicon.py`) — real Bengali words phonetically near
  each raw Whisper hypothesis, drawn from the OpenSLR SLR53 corpus's own word
  list, augment (not replace) the candidate pool. This was the
  candidate-generation improvement `EXPERIMENTS.md` flagged as the most
  plausible fix for the syllable condition's poor Experiment B/C result.
  Re-running the exact same eval on the exact same split gave a real, honest
  result: **a small (1-sample, not significant) improvement on slow, no
  improvement on syllable** — see `EXPERIMENTS.md` "Experiments B/C re-run".
  This does not validate the hypothesis that lexicon constraint was the main
  problem; the TTS-proxy limitation remains the more likely explanation.
- **A real performance bug was found and fixed mid-session, flagged for
  transparency rather than hidden:** the first re-run attempt ran for over
  1h45m (vs. ~8-9 min originally) before being killed as unreasonably slow —
  diagnosed as ~90% wall-clock time spent waiting on an *uncached*
  `espeak-ng` subprocess spawn per phonetic-similarity call, fanned out by an
  unbounded lexicon shortlist on garbage multi-word hypotheses. Fixed
  (`lru_cache` on `espeak_g2p.to_phonemes()`, a 25-candidate cap before
  phonetic re-ranking in `lexicon.py`), verified with a new bounded
  `--max-samples` flag on `run_correction_eval.py` before re-running the full
  split. Latency is still genuinely ~29-33% higher than the pre-lexicon
  baseline even after the fix — a real, unresolved cost/benefit tradeoff, not
  claimed as free.
- **Bengali.AI OOD-Speech license investigated further, still unresolved**:
  its actual distribution channels (Kaggle competitions, gated behind
  login+JS this session's tooling can't access) could not be checked for
  their real license text — documented honestly in `DATA_PIPELINE.md` rather
  than guessed at.
- Re-verified the already-claimed-live Vercel/Render production deployments
  right now (not trusting the older doc claim): both still return healthy
  responses.

## Production deployment (2026-09-06/07) — REAL, verified live

**Frontend (Vercel):** https://frontend-three-psi-tz8kxezc8c.vercel.app —
deployed via `vercel --prod` from `frontend/` (user authenticated via
`vercel login`; GitHub auto-connect for this project failed both times it was
tried — "Failed to connect ... Make sure ... you have access to the
repository" — so this project needs a manual `vercel --prod` redeploy after
future pushes, not automatic). Verified with direct `curl`, not just the CLI's
own success message: HTML/JS/CSS assets all return 200, the production JS
bundle contains zero occurrences of `127.0.0.1` (confirms the
localhost-fallback fix below actually took effect), and after wiring
`VITE_BACKEND_URL` the bundle was re-verified to contain the real backend
hostname.

**Backend (Render):** https://btp-backend-ofur.onrender.com — created via
Render's REST API (user supplied a scoped, revocable API key; the GitHub
repo connection needed no manual OAuth step because the user's Render account
already had broad GitHub access from prior unrelated projects — flagged as a
lucky case, not something to assume will always work). `render.yaml` defines
the service (`rootDir: backend`, `npm ci` / `npm start`, `/health` check,
`autoDeploy: yes` on `main`). **First deploy failed** with a real,
non-fabricated error pulled from Render's logs API:
`MongooseServerSelectionError: ... IP that isn't whitelisted` — the user's
MongoDB Atlas cluster's Network Access list didn't include Render's (dynamic,
free-tier) outbound IPs. Fixed by the user adding `0.0.0.0/0` to Atlas Network
Access (documented tradeoff: this is access-anywhere at the network level,
still gated by username/password auth — a static-IP Render add-on is the
paid alternative, not pursued). Redeploy succeeded; **verified live with real
requests, not just Render's dashboard status**:
  - `GET /health` -> `{"status":"ok"}`, HTTP 200
  - `GET /api/sessions/<fake-id>` -> `{"error":"Session not found"}`, HTTP 404
    (proves a real MongoDB Atlas round-trip — a bad connection would have
    surfaced as a 500, not a clean 404)
  - `OPTIONS`/CORS check confirms `Access-Control-Allow-Origin` is restricted
    to exactly the deployed frontend origin (see `CORS_ORIGIN` below), not `*`

**Backend CORS hardening:** `backend/src/app.js` + `config/env.js` now read a
`CORS_ORIGIN` allowlist env var (spec section 32: "restricted CORS"); unset
falls back to permissive `cors()` for local dev only. Set to the real
deployed frontend origin in `render.yaml` and verified via a live CORS
preflight check above.

**Frontend production-hygiene fix:** `frontend/src/api/client.js` previously
defaulted to `http://127.0.0.1:4000` whenever `VITE_BACKEND_URL` was unset —
a literal localhost reference that spec section 3 explicitly forbids in
production. Now only the Vite dev server gets that fallback
(`import.meta.env.DEV`); an unset var in a production build falls back to a
same-origin relative path instead. Verified absent from the deployed bundle
(see above).

**Known, honestly-stated gap: ml-service (FastAPI/Whisper) is NOT deployed.**
The user was asked directly and chose to skip both institute GPU access and a
paid cloud GPU service this session, keeping ml-service local-dev-only rather
than have Claude attempt a fake or non-functional remote setup. Consequence:
the live frontend + backend chain is real and reachable, but
`POST /api/sessions/:id/transcribe` and the correction endpoints will fail
with a network error in production, because `ML_SERVICE_URL` on Render points
at a placeholder (`http://127.0.0.1:8000`, unreachable from Render's servers
by construction) — this is expected, not a bug, and is the single missing
link for genuine end-to-end production functionality. See "Next steps" if/when
GPU hosting becomes available.

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
- ZenML: `zenml[server]==0.96.4`, not bare `zenml` — the base package is missing `pymysql`/`sqlmodel`, which even the local SQLite metadata store imports transitively; confirmed by hitting `ModuleNotFoundError` for both before installing the `[server]` extra. This forced an upgrade of `fastapi` (0.115.6 -> 0.138.2), `pydantic` (2.10.4 -> 2.12.5), and `starlette` (0.41.3 -> 1.6.0) to satisfy zenml's own pins — re-ran the full fast ml-service test suite immediately after (23 passed, 5 deselected model tests) to confirm this didn't break `api/main.py`; no regression found. ZenML's daemon-based orchestration features are unavailable on Windows ("Daemon functionality is currently not supported on Windows" — printed by `zenml init`), so the pipeline runs synchronously in-process, which is sufficient for this project's scale and is not a functional limitation for what section 23 asks for (config-driven staged orchestration, not distributed scheduling).

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
  - [x] `scripts/split_dataset.py` — speaker-disjoint greedy bin-packing split of the 200-sample manifest into train(140)/val(30)/test(30) by whole speaker group, seed 42, sanity-asserted no speaker crosses splits; output `data/processed/openslr_53_splits.json`
  - [x] `ml-service/scripts/run_correction_eval.py` — Experiments B/C (slow vs. syllable-level correction) against the real correction engine, using gTTS as a documented proxy for human re-pronunciation audio (no live user data exists yet); real result: 3.4% (1/29) slow, 0.0% (0/27) syllable correction accuracy on the 30-sample speaker-disjoint test split — see `EXPERIMENTS.md` for the full result and the candidate-generation limitation this points to. MLflow-tracked (`bengali-asr-correction` experiment).
  - [x] `pipelines/` — ZenML pipeline (`zenml[server]==0.96.4`) orchestrating ingest -> split -> baseline eval -> error analysis -> correction eval as config-driven steps; verified with a real, if small (`--smoke`, 8-sample), end-to-end run. See `ARCHITECTURE.md` "Pipeline orchestration".
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
- [x] GitHub Actions CI (`backend` + `ml-service` (non-model tests only) + `frontend` build/lint) — **verified running for real on GitHub as of 2026-09-07** (run `34054417242`, all 3 jobs `success`, ~2m38s), after this session confirmed GitHub push access was actually available and the user approved pushing; a ZenML pipeline-import smoke check was added to the `ml-service` job for this push
- [x] Real dataset research (`DATA_PIPELINE.md`): OpenSLR SLR53, Common Voice Bengali, AI4Bharat IndicVoices/-R, Bengali.AI OOD-Speech, IndicSUPERB — sizes/licenses sourced from web search; **OpenSLR SLR53 now actually acquired** (200-sample manifest, see above), others still unverified/unused

## Known issues / open questions for the user

- **Dataset licensing:** proceeded with OpenSLR SLR53 (CC-BY-SA-4.0, a clear share-alike license appropriate for academic thesis use with attribution) for Stage 1 baseline work — this is a defensible research/eval use, not redistribution, but flag it explicitly: if results or derived data are published, CC-BY-SA-4.0's share-alike/attribution terms apply. Bengali.AI OOD-Speech's license is still unresolved and has not been used.
- Institute GPU access is blocked on SSH authentication (verified 2026-09-08, not just "not yet available") — the server only accepts password/keyboard-interactive login, never publickey, for user `shambo`; see `GPU_SETUP.md` "Institute GPU" for the exact evidence and what the institute/user needs to do. The baseline eval above ran on the local dev 4GB GTX 1650, not institute hardware.
- Production MongoDB hosting (self-hosted on institute server vs. managed service) not yet decided.
- Docker Desktop not installed locally — containers are written but unverified. If you'd like me to proceed with a Docker Desktop install, that needs admin rights I don't have in this environment; you'd need to install it, or grant admin access.
- Contextual (language-model fluency) scoring is entirely unimplemented (`contextual_score` always 0.0) — this is genuinely future work, not started.
- Ground-truth capture (`Correction.groundTruthWord`, `Session.datasetProvenance`) and the `compute_correction_accuracy` metric now exist in the schema/evaluation code. A first correction-method comparison now exists (Experiments B/C, see above), but it used a gTTS-synthesized proxy for re-pronunciation audio, not real live-user data — the frontend still has not been manually tested end-to-end in a browser by any session, and the low/negative result should be re-checked against real user audio before treating it as validated.
- Production deployment: frontend (Vercel) and backend (Render) are live (see "Current phase" above); the ml-service/GPU leg is what's unimplemented, blocked on institute SSH auth as described above. This needs the institute server admin (or the user) to authorize this machine's public key, or the user to complete an interactive password login themselves, before it can proceed.

## Test status (as of this writing, all verified locally, 2026-09-08 under `uv`)

- ml-service: `uv run --directory ml-service python -m pytest tests/ -v` → 32 passed (5 marked `@pytest.mark.model`, includes real GPU Whisper inference and real LaBSE embedding inference) — up from 28 (added `tests/test_lexicon.py`, 4 tests)
- backend: `npm test` → 5 passed (Jest + mongodb-memory-server)
- frontend: `npm run build` → succeeds; `npm run lint` → clean

## Experiments completed

**Experiment A (Whisper baseline) — real, MLflow-tracked result.** See
`EXPERIMENTS.md` for full detail: WER 0.8106 / CER 0.2580 (normalized) on 200
real OpenSLR SLR53 samples, `large-v3` int8_float16 on the dev GPU. The
earlier `GPU_SETUP.md`/`RESEARCH.md` findings about model-size script
correctness and স/শ ambiguity remain real observations from smoke-testing,
not rigorous experiments — still flagged as such, not upgraded to "results."

**Exploratory error-category analysis — real, observational, not
significance-tested.** Rare words show a small expected CER increase (0.288
vs 0.271); speech rate shows the opposite of the naive assumption (slower
speech has *higher* CER here). See `EXPERIMENTS.md` "Exploratory
error-category analysis" for the full numbers and caveats — single
200-sample draw, not a validated conclusion.

**Experiments B/C (slow vs. syllable correction) — real, TTS-proxy-limited
result.** 3.4% (1/29) correction accuracy for whole-word slow
re-pronunciation vs. 0.0% (0/27) for syllable-level, on the 30-sample
speaker-disjoint test split — syllable-level *underperformed*, the opposite
of the project's working hypothesis. See `EXPERIMENTS.md` for the full
result, the gTTS-proxy limitation, and the likely cause (unconstrained
candidate generation producing multi-word garbage on concatenated-syllable
audio) — not yet validated against real human re-pronunciation.

## Next steps (in rough priority order)

1. **Done (2026-09-06):** speaker-disjoint train/val/test split
   (`scripts/split_dataset.py` → `data/processed/openslr_53_splits.json`).
2. **Done, but proxy-limited (2026-09-06):** Experiments B/C ran via
   `ml-service/scripts/run_correction_eval.py` using gTTS-synthesized
   re-pronunciation as a documented stand-in for real human audio — see
   `EXPERIMENTS.md`. Real correction-attempt data from an actual live user
   session (via the frontend, not yet manually browser-tested) or from the
   backend API driven by a harness against `POST /api/sessions` →
   `/corrections` → `/corrections/:id/attempts` is still needed to validate
   (or overturn) the proxy result and to unblock a non-proxy Experiment B/C/E.
3. **Done (2026-09-07/08):** lexicon-augmented candidate generation
   (`ml-service/phonetics/lexicon.py`) implemented and the eval re-run — see
   `EXPERIMENTS.md` "Experiments B/C re-run". Result: small, not statistically
   meaningful improvement on slow (1→2/29), no improvement on syllable
   (still 0/27) — this does not resolve the syllable condition's poor result;
   the TTS-proxy limitation remains the more likely explanation, and real
   (non-proxy) user data is the next thing that would actually clarify this,
   not further candidate-generation tuning on synthetic audio.
4. Experiment D (meaning/context, Mode B) — deliberately not run with a
   synthetic proxy (see `EXPERIMENTS.md`); needs either real user context or
   an explicit, user-approved synthesis method.
5. Manually test the frontend in a real browser end-to-end (mic permissions,
   recording, word selection, correction flow, accept/retry) — still not done
   in any session so far; this is also what production browser verification
   (spec section 33) depends on.
6. Verify Docker builds once Docker Desktop is available (still not installed
   locally as of this session — no admin rights in this dev environment).
7. **Done (2026-09-06/07):** ZenML pipeline (`pipelines/`) chaining ingest ->
   split -> baseline eval -> error analysis -> correction eval as real,
   config-driven steps — verified end-to-end with a small (`--smoke`,
   8-sample) real run; see `ARCHITECTURE.md` "Pipeline orchestration".
8. Production deployment: frontend (Vercel) and backend (Render) are live and
   re-verified as of 2026-09-08 (see below). Institute GPU reachability
   was attempted for real later on 2026-09-08 with actual connection details
   (`kgp-140` / `10.171.14.130` / user `shambo`) and **failed authentication**
   — the server only offers `password,keyboard-interactive`, never
   `publickey`, so no local SSH key can succeed there until the institute
   server's admin adds this machine's public key to `authorized_keys` and/or
   enables pubkey auth, or the user completes an interactive password login
   themselves (this session's tools have no TTY to do that). See
   `GPU_SETUP.md` "Institute GPU" for the exact debug evidence and the three
   concrete unblock options. This is still the single missing link for full
   end-to-end production functionality — genuinely blocked, not skipped.
