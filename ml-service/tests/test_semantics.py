"""Tests for semantics/embedder.py (Mode B real semantic scoring)."""

import pytest

from semantics.embedder import is_available, semantic_method, semantic_similarity


def test_empty_inputs_score_zero():
    assert semantic_similarity("", "কিছু একটা প্রসঙ্গ") == 0.0
    assert semantic_similarity("শব্দ", "") == 0.0


@pytest.mark.model
def test_semantic_method_reports_something():
    # Marked @pytest.mark.model: checking which backend is active triggers
    # loading the (~1.8GB, first-run-downloaded) LaBSE model via
    # is_available(). Whichever backend is active, semantic_method() must
    # report which one, per the project's "always log which method is
    # active" rule.
    assert semantic_method() in ("sentence-transformers/LaBSE", "fallback-literal-containment")


@pytest.mark.model
def test_labse_available_in_this_environment():
    # This is marked @pytest.mark.model (deselected in normal CI, per
    # pytest.ini) because it downloads/loads a real ~1.8GB model on first
    # run. It's here to catch a silent fallback to the weaker heuristic.
    assert is_available()


@pytest.mark.model
def test_related_word_scores_higher_than_unrelated():
    # "আম" (mango) is much more related to a mango-fruit context than
    # "কম্পিউটার" (computer) — a real LaBSE inference, not a mocked value.
    context = "এটি একটি মিষ্টি ফল যা গাছে জন্মায়"  # "a sweet fruit that grows on trees"
    related = semantic_similarity("আম", context)
    unrelated = semantic_similarity("কম্পিউটার", context)
    assert related > unrelated
