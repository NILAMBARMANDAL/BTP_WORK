"""Fast unit tests (no GPU/model loading) for the phonetics heuristics."""

import pytest

from phonetics.similarity import phonetic_similarity
from phonetics.syllables import syllabify


def test_identical_words_score_one():
    assert phonetic_similarity("আমার", "আমার") == 1.0


def test_similar_words_score_high():
    # স vs শ substitution — genuine homophones in standard Bengali (confirmed
    # independently by espeak-ng producing identical phonemes for both — see
    # phonetics/README.md "Validated finding"). When espeak-ng is available
    # this scores as exactly identical (1.0); the ITRANS fallback treats it
    # as merely similar. The test accepts either backend.
    score = phonetic_similarity("সোনার", "শোনার")
    assert score > 0.7


def test_espeak_confirms_sa_sha_are_homophones():
    from phonetics import espeak_g2p

    if not espeak_g2p.is_available():
        pytest.skip("espeak-ng not available in this environment")

    assert espeak_g2p.to_phonemes("সোনার") == espeak_g2p.to_phonemes("শোনার")


def test_dissimilar_words_score_low():
    score = phonetic_similarity("আমার", "কম্পিউটার")
    assert score <= 0.5


def test_empty_word_handled():
    assert phonetic_similarity("", "") == 1.0
    assert phonetic_similarity("আমার", "") == 0.0


def test_syllabify_returns_nonempty_list():
    syllables = syllabify("বাংলাদেশ")
    assert len(syllables) > 1
    assert "".join(syllables) == "বাংলাদেশ"
