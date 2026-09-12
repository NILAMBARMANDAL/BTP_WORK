"""Unit tests for correction/pronunciation_engine.py candidate generation —
mocking whisper.engine.transcribe_word_hypotheses so these run fast, without a
GPU/model (unlike tests/test_api.py's @pytest.mark.model integration tests).
"""

from __future__ import annotations

import numpy as np
import pytest

from correction import pronunciation_engine
from correction.base import CorrectionRequest
from whisper.engine import WordHypothesis


def _request(mode: str = "pronunciation_only", meaning_context: str | None = None) -> CorrectionRequest:
    return CorrectionRequest(
        audio=np.zeros(16000, dtype=np.float32),
        sample_rate=16000,
        original_word="বাড়ি",
        context_text="আমার বাড়ি আছে",
        mode=mode,
        meaning_context=meaning_context,
    )


def test_multiword_hypothesis_is_split_into_single_word_candidates(monkeypatch):
    """Regression test: a short, isolated-word correction clip must never
    yield a multi-word candidate as the prediction, even if Whisper
    hallucinates extra tokens for that short audio (a real, observed failure
    mode — see pronunciation_engine.py's comment on this loop). The unit being
    corrected is always a single word."""
    monkeypatch.setattr(
        pronunciation_engine,
        "transcribe_word_hypotheses",
        lambda audio, sample_rate: [
            WordHypothesis(text="আমার বাড়ি আছে ভালো", avg_logprob=-0.1),
        ],
    )
    monkeypatch.setattr(pronunciation_engine, "_lexicon_augmented_texts", lambda raw_text: [])

    result = pronunciation_engine.generate_candidates(_request())

    assert result.prediction is not None
    assert " " not in result.prediction, "prediction must be a single word, not a reproduced phrase"
    assert all(" " not in c.text for c in result.candidates)


def test_single_word_hypothesis_passes_through_unsplit(monkeypatch):
    monkeypatch.setattr(
        pronunciation_engine,
        "transcribe_word_hypotheses",
        lambda audio, sample_rate: [WordHypothesis(text="বাড়ি", avg_logprob=-0.05)],
    )
    monkeypatch.setattr(pronunciation_engine, "_lexicon_augmented_texts", lambda raw_text: [])

    result = pronunciation_engine.generate_candidates(_request())

    assert result.prediction == "বাড়ি"


def test_mode_a_never_computes_semantic_score(monkeypatch):
    monkeypatch.setattr(
        pronunciation_engine,
        "transcribe_word_hypotheses",
        lambda audio, sample_rate: [WordHypothesis(text="বাড়ি", avg_logprob=-0.05)],
    )
    monkeypatch.setattr(pronunciation_engine, "_lexicon_augmented_texts", lambda raw_text: [])

    result = pronunciation_engine.generate_candidates(_request(mode="pronunciation_only"))

    assert all(c.semantic_score == 0.0 for c in result.candidates)


def test_mode_b_uses_meaning_context_for_semantic_score(monkeypatch):
    monkeypatch.setattr(
        pronunciation_engine,
        "transcribe_word_hypotheses",
        lambda audio, sample_rate: [WordHypothesis(text="বাড়ি", avg_logprob=-0.05)],
    )
    monkeypatch.setattr(pronunciation_engine, "_lexicon_augmented_texts", lambda raw_text: [])
    monkeypatch.setattr(pronunciation_engine, "semantic_similarity", lambda text, ctx: 0.77)

    result = pronunciation_engine.generate_candidates(
        _request(mode="pronunciation_meaning", meaning_context="এটা একটা ফলের নাম")
    )

    assert result.candidates[0].semantic_score == pytest.approx(0.77)


def test_no_hypotheses_yields_empty_result_not_error(monkeypatch):
    monkeypatch.setattr(pronunciation_engine, "transcribe_word_hypotheses", lambda audio, sample_rate: [])

    result = pronunciation_engine.generate_candidates(_request())

    assert result.candidates == []
    assert result.prediction is None
