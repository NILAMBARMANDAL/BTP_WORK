"""Approximate Bengali phonetic representation via ITRANS transliteration.

See phonetics/README.md for the honest limitations of this approach — it is an
interim, unvalidated proxy, not a validated G2P system.
"""

from __future__ import annotations

from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate


def to_phonetic(bengali_text: str) -> str:
    """Returns an ITRANS-romanized approximation of the Bengali text's
    pronunciation, lowercased for similarity comparisons."""
    if not bengali_text:
        return ""
    return transliterate(bengali_text, sanscript.BENGALI, sanscript.ITRANS).lower()
