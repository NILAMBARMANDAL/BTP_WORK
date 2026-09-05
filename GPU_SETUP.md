# GPU Setup

## Local development GPU (inspected 2026-09-05)

- GPU: NVIDIA GeForce GTX 1650
- VRAM: 4096 MiB
- Driver: 566.07
- CUDA (driver-reported max): 12.7
- PyTorch installed: `torch==2.5.1+cu121` (`pip install torch --index-url https://download.pytorch.org/whl/cu121`)
- `torch.cuda.is_available()` confirmed `True` in `ml-service/venv`.

### Windows-specific gotcha: CTranslate2 can't find cuBLAS/cuDNN

`faster-whisper` (CTranslate2) failed with `Library cublas64_12.dll is not
found or cannot be loaded` even though CUDA drivers were present. Root cause:
CTranslate2 doesn't ship these DLLs and doesn't know where to find them on
Windows. Fix (see `ml-service/api/main.py`): PyTorch's cu121 wheel already
bundles compatible `cublas64_12.dll` / `cudnn64_9.dll` etc. under
`torch/lib/`; we call `os.add_dll_directory()` on that path at ml-service
startup before any faster-whisper import triggers a DLL load. This avoids a
second multi-GB CUDA runtime install. If this ever breaks (e.g. a torch
version bump changes bundled DLL names), install `nvidia-cublas-cu12` and
`nvidia-cudnn-cu12` via pip as the standard alternative.

### Model size findings (from smoke-testing on this GPU, NOT a rigorous benchmark)

Tested faster-whisper on the same short Bengali (gTTS-synthesized) audio clip:

| Model | Compute type | Output script correct? | Notes |
|---|---|---|---|
| small | float16 | **No** — Devanagari-like transliteration | Fast, low VRAM |
| medium | int8_float16 | **No** — same issue, better phonetic accuracy | |
| large-v3 | int8_float16 | **Yes** — correct Bengali script, good accuracy | Fits comfortably in 4GB with int8 quantization |

This is why `WHISPER_MODEL_SIZE=large-v3` / `WHISPER_COMPUTE_TYPE=int8_float16`
are the current defaults (`.env.example`, `ml-service/utils/config.py`). This
was checked on essentially one phrase and one single word — a real benchmark
(latency, VRAM headroom under concurrent load, accuracy across many samples
and speakers) is still pending and belongs in `EXPERIMENTS.md` once a real
evaluation dataset is in place (`DATA_PIPELINE.md`). Do not cite this table as
a validated benchmark in any report.

### Known constraint

4GB VRAM is tight for `large-v3` if the correction engine's word-level
re-transcription (`whisper/engine.py:transcribe_word_hypotheses`) runs
concurrently with the main transcript's transcription in the same process —
both currently share one cached model instance (`get_model()`), which is
fine because they run sequentially per request, but concurrent multi-user load
has not been tested and may need a request queue or a second, smaller model
dedicated to word-level correction. Flagging as a design question for later,
not solved yet.

## Institute GPU (pending)

Not yet available. When it is, per project instructions we must inspect and
document (not assume): GPU model, driver version, CUDA version, available
VRAM, disk space, Docker support, and Python environment, before running any
benchmark or deployment there. This section will be filled in with actual
inspection output at that time — nothing here should be assumed to describe
the institute server.
