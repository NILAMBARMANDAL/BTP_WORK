"""Fast unit tests for evaluation/metrics.py (no GPU/model loading)."""

import pytest

from evaluation.metrics import (
    average_latency_ms,
    compute_correction_stats,
    compute_error_rates,
    normalize_transcript,
)


def test_normalize_strips_punctuation_and_collapses_whitespace():
    assert normalize_transcript("কি আমাদের বল্বেন?") == "কি আমাদের বল্বেন"
    assert normalize_transcript("একটি,   দুটি।") == "একটি দুটি"


def test_normalization_reduces_wer_for_punctuation_only_difference():
    ref, hyp = ["কি আমাদের বলবেন"], ["কি আমাদের বলবেন?"]
    normalized = compute_error_rates(ref, hyp, normalize=True)
    raw = compute_error_rates(ref, hyp, normalize=False)
    assert normalized.wer == 0.0
    assert raw.wer > 0.0


def test_identical_transcripts_zero_error():
    result = compute_error_rates(["আমার সোনার বাংলা"], ["আমার সোনার বাংলা"])
    assert result.wer == 0.0
    assert result.cer == 0.0
    assert result.n_samples == 1


def test_one_word_substitution():
    result = compute_error_rates(["আমার সোনার বাংলা"], ["আমার শোনার বাংলা"])
    assert result.wer == pytest.approx(1 / 3)
    assert 0 < result.cer < 1


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError):
        compute_error_rates(["a", "b"], ["a"])


def test_empty_inputs_raise():
    with pytest.raises(ValueError):
        compute_error_rates([], [])


def test_correction_stats_basic():
    corrections = [
        {"status": "accepted", "attempt_count": 1},
        {"status": "accepted", "attempt_count": 3},
        {"status": "open", "attempt_count": 1},
        {"status": "abandoned", "attempt_count": 2},
    ]
    stats = compute_correction_stats(corrections)
    assert stats.total_corrections == 4
    assert stats.accepted == 2
    assert stats.abandoned == 1
    assert stats.success_rate == 0.5
    assert stats.avg_attempts_per_accepted == 2.0


def test_correction_stats_no_corrections():
    stats = compute_correction_stats([])
    assert stats.total_corrections == 0
    assert stats.success_rate == 0.0
    assert stats.avg_attempts_per_accepted is None


def test_average_latency():
    assert average_latency_ms([100.0, 200.0, 300.0]) == 200.0


def test_average_latency_empty_raises():
    with pytest.raises(ValueError):
        average_latency_ms([])
