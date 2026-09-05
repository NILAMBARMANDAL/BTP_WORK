"""FastAPI app entrypoint. Run with:
    uvicorn api.main:app --host $ML_SERVICE_HOST --port $ML_SERVICE_PORT
from the ml-service/ directory (so the `audio`, `whisper`, etc. packages resolve).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import imageio_ffmpeg
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

# CTranslate2 (used by faster-whisper) needs cuBLAS/cuDNN DLLs on Windows but
# does not ship or locate them itself. PyTorch's cu121 wheel already bundles
# compatible copies (torch/lib/cublas64_12.dll, cudnn64_9.dll, ...) — reusing
# those avoids a second multi-GB CUDA runtime install. Must happen before any
# faster-whisper/ctranslate2 import triggers a DLL load.
if sys.platform == "win32":
    import torch

    torch_lib_dir = Path(torch.__file__).parent / "lib"
    if torch_lib_dir.is_dir():
        os.add_dll_directory(str(torch_lib_dir))

from audio.preprocessing import load_and_preprocess
from correction.base import CorrectionRequest
from correction.pronunciation_engine import generate_candidates
from whisper.engine import transcribe

# faster-whisper / soundfile fall back to ffmpeg being on PATH for some codecs;
# imageio-ffmpeg bundles a static binary so we don't require a system install.
os.environ.setdefault("IMAGEIO_FFMPEG_EXE", imageio_ffmpeg.get_ffmpeg_exe())

app = FastAPI(title="BTP Bengali ASR Correction — ML Service")


@app.get("/health")
def health():
    return {"status": "ok"}


def _save_upload_to_tempfile(upload: UploadFile) -> str:
    suffix = Path(upload.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(upload.file.read())
        return tmp.name


@app.post("/transcribe")
async def transcribe_endpoint(file: UploadFile = File(...)):
    tmp_path = _save_upload_to_tempfile(file)
    try:
        preprocessed = load_and_preprocess(tmp_path)
        result = transcribe(preprocessed.audio, preprocessed.sample_rate)
    except Exception as exc:  # noqa: BLE001 — surface as HTTP error, log server-side
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {
        "text": result.text,
        "language": result.language,
        "config": result.config,
        "words": [
            {
                "index": w.index,
                "text": w.text,
                "start": w.start,
                "end": w.end,
                "confidence": w.confidence,
            }
            for w in result.words
        ],
        "preprocessing_applied": preprocessed.applied_steps,
    }


@app.post("/correct")
async def correct_endpoint(
    file: UploadFile = File(...),
    original_word: str = Form(...),
    context_text: str = Form(""),
    mode: str = Form(...),
    meaning_context: str | None = Form(None),
):
    if mode not in ("pronunciation_only", "pronunciation_meaning"):
        raise HTTPException(status_code=400, detail="mode must be pronunciation_only or pronunciation_meaning")

    tmp_path = _save_upload_to_tempfile(file)
    try:
        preprocessed = load_and_preprocess(tmp_path)
        request = CorrectionRequest(
            audio=preprocessed.audio,
            sample_rate=preprocessed.sample_rate,
            original_word=original_word,
            context_text=context_text,
            mode=mode,
            meaning_context=meaning_context,
        )
        result = generate_candidates(request)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Correction failed: {exc}") from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {
        "prediction": result.prediction,
        "candidates": [
            {
                "text": c.text,
                "acousticScore": c.acoustic_score,
                "phoneticScore": c.phonetic_score,
                "semanticScore": c.semantic_score,
                "contextualScore": c.contextual_score,
                "finalScore": c.final_score,
            }
            for c in result.candidates
        ],
        "ranking_weights": result.ranking_weights,
    }
