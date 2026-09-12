# CPU-only ml-service image for Render's free/paid web-service compute
# (no GPU available there). This is DELIBERATELY a different image from
# docker/ml-service.Dockerfile (which targets the NVIDIA-GPU / institute L40
# path with large-v3) — see ARCHITECTURE.md "Render ML service" and
# GPU_SETUP.md. Model size/device/compute type are env-driven
# (ml-service/utils/config.py); this image just supplies sane Render-side
# defaults via render.yaml, never hardcodes them here.
#
# Built and pushed to Render from this exact file — verify Render's service
# settings point dockerfilePath at this path and dockerContext at ./ml-service
# (see render.yaml).

FROM python:3.12-slim

# espeak-ng: real Bengali G2P (phonetics/espeak_g2p.py), found automatically
# via PATH on Linux — no ESPEAK_NG_EXE override needed here, unlike Windows
# dev. build-essential: python-Levenshtein has historically needed a C build
# on some platforms; kept for build reliability even though manylinux wheels
# usually cover this.
RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only PyTorch wheel (~200MB) instead of the CUDA build pyproject.toml
# pins for local dev/institute-GPU use — installing the default PyPI index's
# torch here would pull multi-GB CUDA runtime packages that are useless (and
# slow to build/exceed free-tier build resources) on a CPU-only instance.
RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu

COPY requirements-render.txt .
RUN pip install --no-cache-dir -r requirements-render.txt

COPY . .

ENV WHISPER_DEVICE=cpu
ENV SEMANTIC_DEVICE=cpu

# Render injects $PORT at runtime and routes traffic to it — do not hardcode
# 8000 here (that's only the local-dev/docker-compose default). ML_SERVICE_*
# settings (utils/config.py) are informational/for local `uvicorn` CLI use;
# the actual bind address/port for this image is this CMD line.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
