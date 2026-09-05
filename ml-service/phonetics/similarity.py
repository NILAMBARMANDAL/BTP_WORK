"""Phonetic similarity between two Bengali words.

Primary method: espeak-ng phoneme transcription + normalized Levenshtein
distance (phonetics/espeak_g2p.py) — a real G2P system, not an invented
heuristic. Falls back to ITRANS transliteration + Levenshtein
(phonetics/g2p.py) if espeak-ng isn't available in the environment (see
phonetics/README.md for the honest comparison and remaining limitations of
both).
"""

from __future__ import annotations

import Levenshtein

from phonetics import espeak_g2p
from phonetics.g2p import to_phonetic as to_itrans_phonetic


def _phonetic_form(word: str) -> tuple[str, str]:
    """Returns (representation, method_used)."""
    espeak_form = espeak_g2p.to_phonemes(word)
    if espeak_form is not None:
        return espeak_form.lower(), "espeak-ng"
    return to_itrans_phonetic(word), "itrans"


def phonetic_similarity(word_a: str, word_b: str) -> float:
    """Returns a score in [0, 1], 1.0 = identical phonetic representation."""
    a, method_a = _phonetic_form(word_a)
    b, method_b = _phonetic_form(word_b)

    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0

    distance = Levenshtein.distance(a, b)
    return 1.0 - distance / max(len(a), len(b))


def phonetic_method() -> str:
    """Reports which G2P method is actually active in this environment, so
    experiment results/logs can record it (RESEARCH.md: config must be
    recorded, not assumed)."""
    return "espeak-ng" if espeak_g2p.is_available() else "itrans-heuristic"
