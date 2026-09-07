"""Fast unit tests (no GPU/model loading) for the OpenSLR-derived lexicon
used to augment correction candidates (phonetics/lexicon.py)."""

import pytest

from phonetics import lexicon


def test_lexicon_loads_real_words_from_tsv():
    if not lexicon.is_available():
        pytest.skip("OpenSLR SLR53 TSV not present in this environment (see DATA_PIPELINE.md)")

    freq = lexicon.load_lexicon()
    # A word actually present in data/raw/openslr_53/utt_spk_text.tsv's first lines.
    assert freq["বাংলাদেশে"] >= 1


def test_nearest_lexicon_words_returns_exact_match_first():
    if not lexicon.is_available():
        pytest.skip("OpenSLR SLR53 TSV not present in this environment (see DATA_PIPELINE.md)")

    matches = lexicon.nearest_lexicon_words("বাংলাদেশে", top_k=3)
    assert matches
    assert matches[0] == "বাংলাদেশে"


def test_nearest_lexicon_words_empty_when_lexicon_unavailable():
    lexicon.load_lexicon.cache_clear()
    matches = lexicon.nearest_lexicon_words("বাংলাদেশে", tsv_path="nonexistent_file.tsv")
    assert matches == []
    lexicon.load_lexicon.cache_clear()


def test_is_available_false_for_missing_path():
    lexicon.load_lexicon.cache_clear()
    assert lexicon.is_available(tsv_path="nonexistent_file.tsv") is False
    lexicon.load_lexicon.cache_clear()
