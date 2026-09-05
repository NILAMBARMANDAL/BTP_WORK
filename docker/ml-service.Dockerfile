# NOT YET BUILD-TESTED — no Docker Desktop available in the dev environment
# this was written in (see PROGRESS.md "Known limitations").
#
# Base image assumes an NVIDIA GPU host with the NVIDIA Container Toolkit
# installed (required on the institute GPU server — see GPU_SETUP.md). For a
# CPU-only environment, swap the base image for a plain python:3.12-slim and
# set WHISPER_DEVICE=cpu.

FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# imageio-ffmpeg bundles its own static ffmpeg binary, so no system ffmpeg
# package is installed here — consistent with local dev (see README.md).
COPY requirements.txt .
RUN python3.12 -m pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu121 \
    && python3.12 -m pip install --no-cache-dir -r requirements.txt

COPY . .

ENV ML_SERVICE_HOST=0.0.0.0
ENV ML_SERVICE_PORT=8000
EXPOSE 8000

CMD ["python3.12", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
