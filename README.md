# Interactive Bengali ASR Error Correction

BTP research prototype: correcting Bengali Whisper ASR errors through user-driven
slow / syllable-level re-pronunciation, with optional meaning/context as
supplementary evidence — **without requiring keyboard-based correction**.

See [`RESEARCH.md`](./RESEARCH.md) for the research questions and non-goals,
[`ARCHITECTURE.md`](./ARCHITECTURE.md) for system design, and
[`PROGRESS.md`](./PROGRESS.md) for current implementation status (read this first
in any new session).

## Monorepo layout

```
frontend/       React app — recording, transcript UI, correction workflow
backend/        Node.js + Express — orchestration, sessions, MongoDB persistence
ml-service/     Python + FastAPI — Whisper, correction engine, phonetics, semantics
evaluation/     CER/WER and correction-accuracy evaluation tooling
experiments/    Experiment configs/results (tracked via MLflow once populated)
pipelines/      ZenML pipelines (added once a real multi-step workflow exists)
configs/        Shared configuration (model choice, preprocessing, ranking weights)
scripts/        One-off / operational scripts
tests/          Cross-cutting integration & e2e tests
docs/           Additional documentation
data/           raw/processed/validated/evaluation datasets (gitignored, versioned separately)
docker/         Dockerfiles / compose support files
```

## Status

Early scaffolding stage. See [`PROGRESS.md`](./PROGRESS.md) for exact state.

## Local development environment (as inspected)

- Node v24, npm 11
- Python 3.12 (used for `ml-service`, via a dedicated venv — NOT the system default
  Python 3.14, which is too new for stable PyTorch wheels)
- GPU: NVIDIA GTX 1650, 4GB VRAM — sufficient for small/base Whisper models locally;
  larger models are benchmarked later on institute GPU hardware (see `GPU_SETUP.md`)
- No admin rights available for system-wide installs (Docker Desktop, Chocolatey
  packages) in this environment — see `PROGRESS.md` "Known Limitations"
- ffmpeg is provided via the `imageio-ffmpeg` Python package (bundled static binary,
  no admin/install required) rather than a system install
- MongoDB for local dev runs via `mongodb-memory-server` (downloads a real `mongod`
  binary to user space, no admin required); production deployment uses a real
  MongoDB instance via `MONGO_URI`

See `.env.example` for required configuration.
