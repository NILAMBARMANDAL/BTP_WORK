"""Reproducible evaluation metrics — CER, WER, correction accuracy, success
rate, average attempts, latency. Uses `jiwer` for CER/WER (an established,
independently-maintained library) rather than a hand-rolled edit-distance
implementation, to avoid subtly-wrong metric bugs undermining EXPERIMENTS.md.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import jiwer

# Bengali sentence-final punctuation (dari) plus common ASCII punctuation that
# Whisper sometimes emits but transcript references (e.g. OpenSLR SLR53's
# utt_spk_text.tsv) don't include — leaving these in inflates WER with
# differences that aren't actually transcription errors. Observed directly
# comparing real OpenSLR baseline outputs (e.g. Whisper emitting "বলবেন?" for
# reference "বলবেন"), not a hypothetical concern.
_PUNCTUATION_RE = re.compile(r"[।,.?!;:\"'‘’“”]")


def normalize_transcript(text: str) -> str:
    """Standard pre-WER/CER normalization: NFC-normalize Unicode, drop
    sentence-final/quotation punctuation, and collapse whitespace. Applied to
    BOTH reference and hypothesis before comparison so it can only remove
    non-substantive differences, never hide a real transcription error."""
    text = unicodedata.normalize("NFC", text)
    text = _PUNCTUATION_RE.sub("", text)
    return " ".join(text.split())


@dataclass
class ErrorRates:
    wer: float
    cer: float
    n_samples: int


def compute_error_rates(references: list[str], hypotheses: list[str], normalize: bool = True) -> ErrorRates:
    """references/hypotheses: parallel lists of ground-truth vs. predicted
    transcripts. Word Error Rate treats Bengali space-separated tokens as
    words; note that Bengali word segmentation by whitespace is a
    simplification worth revisiting if it ever seems to skew results
    (RESEARCH.md limitations discipline).

    normalize=True (default) applies normalize_transcript() to both sides
    first — set False only to inspect raw/unnormalized error rates."""
    if len(references) != len(hypotheses):
        raise ValueError("references and hypotheses must be the same length")
    if not references:
        raise ValueError("cannot compute error rates over zero samples")

    if normalize:
        references = [normalize_transcript(r) for r in references]
        hypotheses = [normalize_transcript(h) for h in hypotheses]

    wer = jiwer.wer(references, hypotheses)
    cer = jiwer.cer(references, hypotheses)
    return ErrorRates(wer=wer, cer=cer, n_samples=len(references))


@dataclass
class CorrectionStats:
    total_corrections: int
    accepted: int
    abandoned: int
    success_rate: float  # accepted / total_corrections
    avg_attempts_per_accepted: float | None  # None if nothing was accepted


def compute_correction_stats(corrections: list[dict]) -> CorrectionStats:
    """corrections: list of dicts with at least {"status": "accepted"|"open"|"abandoned",
    "attempt_count": int}. This operates on already-fetched data (e.g. from
    MongoDB via the backend, or exported for offline analysis) — no DB access
    here, keeping evaluation decoupled from the live app per ARCHITECTURE.md.
    """
    total = len(corrections)
    accepted = [c for c in corrections if c["status"] == "accepted"]
    abandoned = [c for c in corrections if c["status"] == "abandoned"]

    success_rate = len(accepted) / total if total > 0 else 0.0
    avg_attempts = (
        sum(c["attempt_count"] for c in accepted) / len(accepted) if accepted else None
    )

    return CorrectionStats(
        total_corrections=total,
        accepted=len(accepted),
        abandoned=len(abandoned),
        success_rate=success_rate,
        avg_attempts_per_accepted=avg_attempts,
    )


def average_latency_ms(latencies_ms: list[float]) -> float:
    if not latencies_ms:
        raise ValueError("cannot average zero latencies")
    return sum(latencies_ms) / len(latencies_ms)
