# GPU Setup

## Python environment: `uv` (as of 2026-09-07)

This project now uses [`uv`](https://docs.astral.sh/uv/) for Python dependency
and environment management — a root-level `pyproject.toml` + `uv.lock`
replaces the earlier manually-managed `ml-service/venv` +
`requirements.txt`/`requirements-dev.txt` (those files are kept for reference
during the transition but `pyproject.toml`/`uv.lock` are now the source of
truth). One environment (`.venv` at the repo root) covers both `ml-service/`
and the repo-root `pipelines/`/`scripts/`, matching how those were already
invoked (`pipelines/evaluation_pipeline.py`'s own docstring: run from the repo
root with `ml-service`'s deps on `sys.path`).

Setup:
```
uv sync                          # creates/updates .venv from uv.lock
uv run --directory ml-service uvicorn api.main:app --host 0.0.0.0 --port 8000
uv run --directory ml-service python -m pytest tests/ -v      # full suite, incl. @pytest.mark.model (GPU)
uv run --directory ml-service python -m pytest tests/ -v -m "not model"  # fast subset, no GPU/model load
uv run python -m pipelines.evaluation_pipeline --max-samples 8 --smoke   # from repo root
```

The CUDA-specific PyTorch build is declared properly as a `uv` dependency
source now (`[[tool.uv.index]]` / `[tool.uv.sources]` in `pyproject.toml`,
scoped to `sys_platform == 'win32'`) rather than a separate manual
`pip install --index-url ...` step — `uv sync` resolves and installs the
correct build (`torch==2.5.1+cu121` on Windows dev machines) in one pass.
Verified for real, not just resolved: `torch.cuda.is_available()` returns
`True` and `torch.cuda.get_device_name(0)` returns the actual GPU name under
the `uv`-managed `.venv` (see "Local development GPU" below) — checked after
migration, not assumed to still work just because the old `venv` did.

Do not `pip install` into the system Python or create an unrelated second
environment — `uv sync`/`uv run` against the root `pyproject.toml` is the only
supported workflow from here on.

## Local development GPU (inspected 2026-09-05, re-verified 2026-09-07 under `uv`)

- GPU: NVIDIA GeForce GTX 1650
- VRAM: 4096 MiB
- Driver: 566.07
- CUDA (driver-reported max): 12.7
- PyTorch: `torch==2.5.1+cu121`, installed via `uv sync` (see above) — was
  previously `pip install torch --index-url https://download.pytorch.org/whl/cu121`
  directly into `ml-service/venv` before the `uv` migration.
- `torch.cuda.is_available()` confirmed `True` under the `uv`-managed `.venv`
  on 2026-09-07 (GPU name: "NVIDIA GeForce GTX 1650").

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

## Institute GPU (blocked on SSH authentication, 2026-09-08 — updated from the 2026-09-07 "no connection details" blocker)

**Update 2026-09-08:** connection details were provided this session (SSH
alias `kgp-140` -> `10.171.14.130`, user `shambo`) and an actual connection
was attempted from this local machine. **Result: authentication failed —
this is now a real, verified blocker, not a missing-information one.**

Exact evidence (`ssh -v -o BatchMode=yes -i ~/.ssh/id_ed25519 kgp-140`):
```
debug1: Authenticating to 10.171.14.130:22 as 'shambo'
...
debug1: Authentications that can continue: password,keyboard-interactive
debug1: No more authentication methods to try.
shambo@10.171.14.130: Permission denied (password,keyboard-interactive).
```
Critically, **`publickey` never appears in the server's offered-methods
list** — the remote sshd is not accepting public-key authentication for this
account at all (only password/keyboard-interactive), so no local private key
could ever succeed here regardless of which one is used. This was checked
against the only keypair present on this dev machine
(`~/.ssh/id_ed25519`, pre-dating this project — comment `mandalnilambar678@gmail.com`,
created 2026-07-21); it parses fine and has no passphrase
(`ssh-keygen -y` succeeds with `-P ""`), so the failure is not a bad/corrupt
key — no key was ever going to be offered a chance.

**This is a genuinely external blocker per the operating instructions' own
escalation rule — not something this session can fix from here.** One of the
following, from the user/institute side, is required to unblock it:
1. The institute server's admin (or the user, if `shambo` already has
   filesystem access via another route) adds this machine's public key —
   `~/.ssh/id_ed25519.pub` — to `~/.ssh/authorized_keys` for user `shambo`
   on the server, **and** confirms/enables `PubkeyAuthentication yes` in
   that server's `sshd_config` if it's currently restricted; or
2. The user supplies the actual login password and runs the interactive
   login themselves (this session's shell tools have no TTY/stdin — they
   cannot answer an interactive password or keyboard-interactive/OTP
   prompt; see tool constraints), then reports back whether the shell
   session that results has passwordless `sudo`/write access needed for
   later install steps; or
3. A separate, already-authorized deploy mechanism (e.g. a jump host, VPN
   client config, or institute VPN requirement) exists that this session
   doesn't know about — if so, the exact steps/credentials for it are
   needed.

None of steps 2-9 in the requested deployment plan (uv setup, PyTorch/GPU
verification, FastAPI deployment, Render connectivity) could be attempted,
inspected, or fabricated as a result — there is no shell access to the
remote machine. The GPU specs quoted in earlier instructions (NVIDIA L40,
~49GB VRAM) remain **unverified by any session** until a real `nvidia-smi`
run succeeds over an authenticated connection.

Once reachable, the plan (unchanged from before): inspect for real (GPU
model, driver, CUDA, disk space, Docker/WSL2 availability, existing Python) —
do not assume the numbers above — install `uv`, use it to provision a Python
3.12 environment (system Python 3.14.7 there is, like the local dev machine,
too new for stable PyTorch wheels) from this repo's `pyproject.toml`/`uv.lock`
possibly with a Linux-specific CUDA index override, verify
`torch.cuda.is_available()` and the real GPU name/VRAM, then run a real
Whisper inference smoke test before considering FastAPI deployment there.
