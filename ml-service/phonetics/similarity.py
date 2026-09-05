"""Phonetic similarity between two Bengali words.

Heuristic: normalized Levenshtein distance over ITRANS transliterations.
See phonetics/README.md for limitations.
"""

from __future__ import annotations

import Levenshtein

from phonetics.g2p import to_phonetic


def phonetic_similarity(word_a: str, word_b: str) -> float:
    """Returns a score in [0, 1], 1.0 = identical phonetic representation."""
    a, b = to_phonetic(word_a), to_phonetic(word_b)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    distance = Levenshtein.distance(a, b)
    return 1.0 - distance / max(len(a), len(b))
