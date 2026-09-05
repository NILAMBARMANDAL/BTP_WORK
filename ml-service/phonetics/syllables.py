"""Heuristic Bengali syllable segmentation, for user-facing instructions
("say this in N syllables") — see phonetics/README.md for validation status.

Approach: walk the Unicode grapheme stream; a syllable ends after a vowel
nucleus (independent vowel letter, or a consonant + dependent vowel sign /
bare consonant carrying the inherent vowel), unless the consonant is joined to
the next one by a virama (hasant), in which case they form a conjunct that
stays attached to the following syllable.
"""

from __future__ import annotations

BENGALI_VIRAMA = "্"  # hasant
BENGALI_VOWEL_SIGNS = set(
    "ািীুূৃৄেৈোৌৢৣ"
)
BENGALI_INDEPENDENT_VOWELS = set("অআইঈউঊঋঌএঐওঔ")
BENGALI_CONSONANTS = set(
    "কখগঘঙচছজঝঞটঠ"
    "ডঢণতথদধনপফবভ"
    "মযরলশষসহড়ঢ়য়"
)


def syllabify(word: str) -> list[str]:
    syllables: list[str] = []
    current = ""
    i = 0
    n = len(word)

    while i < n:
        ch = word[i]
        current += ch

        if ch in BENGALI_INDEPENDENT_VOWELS:
            syllables.append(current)
            current = ""
        elif ch in BENGALI_CONSONANTS:
            # Look ahead: virama -> conjunct continues, stay in current syllable
            if i + 1 < n and word[i + 1] == BENGALI_VIRAMA:
                current += word[i + 1]
                i += 1
            # Look ahead: vowel sign attaches, then syllable ends
            elif i + 1 < n and word[i + 1] in BENGALI_VOWEL_SIGNS:
                current += word[i + 1]
                i += 1
                syllables.append(current)
                current = ""
            else:
                # bare consonant carries inherent vowel -> syllable ends here
                syllables.append(current)
                current = ""
        i += 1

    if current:
        syllables.append(current)

    return syllables if syllables else [word]
