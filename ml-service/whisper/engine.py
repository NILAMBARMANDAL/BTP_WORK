"""Whisper inference wrapper using faster-whisper (CTranslate2 engine).

See RESEARCH.md "Engineering choices" for why faster-whisper is used instead of
openai-whisper. Model size / device / compute type / decoding params are all
configuration (utils/config.py), never hardcoded — required so experiments can
vary exactly one of these at a time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
from faster_whisper import WhisperModel

from utils.config import settings


@dataclass
class TranscribedWord:
    index: int
    text: str
    start: float | None
    end: float | None
    confidence: float | None


@dataclass
class TranscriptionResult:
    text: str
    words: list[TranscribedWord]
    language: str
    config: dict = field(default_factory=dict)


@lru_cache(maxsize=1)
def get_model() -> WhisperModel:
    """Loaded once per process. Cached because model load is expensive
    (seconds to tens of seconds depending on size/device)."""
    return WhisperModel(
        settings.whisper_model_size,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )


def transcribe(audio: np.ndarray, sample_rate: int) -> TranscriptionResult:
    if sample_rate != 16000:
        raise ValueError(
            f"faster-whisper expects 16kHz audio, got {sample_rate}Hz — "
            "ensure PREPROC_RESAMPLE is enabled."
        )

    model = get_model()
    segments, info = model.transcribe(
        audio,
        language=settings.whisper_language,
        beam_size=settings.whisper_beam_size,
        word_timestamps=True,
    )

    words: list[TranscribedWord] = []
    full_text_parts: list[str] = []
    idx = 0
    for segment in segments:
        full_text_parts.append(segment.text.strip())
        if segment.words:
            for w in segment.words:
                words.append(
                    TranscribedWord(
                        index=idx,
                        text=w.word.strip(),
                        start=w.start,
                        end=w.end,
                        confidence=w.probability,
                    )
                )
                idx += 1

    return TranscriptionResult(
        text=" ".join(full_text_parts),
        words=words,
        language=info.language,
        config={
            "modelSize": settings.whisper_model_size,
            "device": settings.whisper_device,
            "computeType": settings.whisper_compute_type,
            "beamSize": settings.whisper_beam_size,
        },
    )


@dataclass
class WordHypothesis:
    text: str
    avg_logprob: float


def transcribe_word_hypotheses(
    audio: np.ndarray, sample_rate: int, temperatures: tuple[float, ...] = (0.0, 0.4, 0.7)
) -> list[WordHypothesis]:
    """Runs whisper decoding at several temperatures on a short (single-word /
    single-phrase) re-pronunciation clip to produce multiple acoustic
    hypotheses for candidate generation (correction/pronunciation_engine.py).

    faster-whisper does not expose true n-best beam hypotheses through its
    public API, so diversity is obtained by varying the sampling temperature
    across repeated decode passes instead — a documented engineering choice,
    not a claim of exhaustive n-best search.
    """
    if sample_rate != 16000:
        raise ValueError("Expected 16kHz audio for word-level correction transcription.")

    model = get_model()
    seen: dict[str, float] = {}

    for temperature in temperatures:
        segments, _ = model.transcribe(
            audio,
            language=settings.whisper_language,
            beam_size=settings.whisper_beam_size,
            temperature=temperature,
            word_timestamps=False,
        )
        text_parts = []
        logprobs = []
        for segment in segments:
            text_parts.append(segment.text.strip())
            logprobs.append(segment.avg_logprob)

        text = " ".join(p for p in text_parts if p).strip()
        if not text:
            continue
        avg_logprob = sum(logprobs) / len(logprobs) if logprobs else -10.0
        if text not in seen or avg_logprob > seen[text]:
            seen[text] = avg_logprob

    return [WordHypothesis(text=t, avg_logprob=lp) for t, lp in seen.items()]
