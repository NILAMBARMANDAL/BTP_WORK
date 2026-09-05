"""Configurable audio preprocessing.

Each step is independently toggleable via Settings (see utils/config.py) so
"preprocessing on vs off" (and each component individually) is an experimental
variable, not a silent default — required by RESEARCH.md / project spec section 10.

Nothing here is applied unconditionally except mono/resample, which are
required for Whisper to accept the array at all; every other step is opt-in.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import librosa

from utils.config import settings


@dataclass
class PreprocessResult:
    audio: np.ndarray
    sample_rate: int
    applied_steps: list[str]


def load_and_preprocess(path: str) -> PreprocessResult:
    applied: list[str] = []

    audio, sr = librosa.load(path, sr=None, mono=False)

    if settings.preproc_mono and audio.ndim > 1:
        audio = librosa.to_mono(audio)
        applied.append("mono")

    if settings.preproc_resample and sr != settings.preproc_target_sr:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=settings.preproc_target_sr)
        sr = settings.preproc_target_sr
        applied.append(f"resample:{sr}")

    if settings.preproc_normalize:
        peak = np.max(np.abs(audio)) if audio.size else 0.0
        if peak > 0:
            audio = audio / peak
        applied.append("normalize")

    if settings.preproc_trim_silence:
        audio, _ = librosa.effects.trim(audio)
        applied.append("trim_silence")

    if settings.preproc_vad:
        # Placeholder: no VAD model wired in yet. Documented limitation rather
        # than a silent no-op pretending to be real VAD.
        applied.append("vad:not_implemented")

    if settings.preproc_denoise:
        # Placeholder: no denoising implementation wired in yet.
        applied.append("denoise:not_implemented")

    return PreprocessResult(audio=audio.astype(np.float32), sample_rate=sr, applied_steps=applied)
