"""Fast unit tests (no GPU/model loading) for the phonetics heuristics."""

from phonetics.similarity import phonetic_similarity
from phonetics.syllables import syllabify


def test_identical_words_score_one():
    assert phonetic_similarity("আমার", "আমার") == 1.0


def test_similar_words_score_high():
    # স vs শ substitution — near-homophone in casual Bengali speech
    score = phonetic_similarity("সোনার", "শোনার")
    assert score > 0.7


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
