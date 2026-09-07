"""Bengali word lexicon derived from the OpenSLR SLR53 transcript TSV.

Used to augment correction candidate generation
(correction/pronunciation_engine.py) with real Bengali words phonetically
close to Whisper's raw re-transcription of a correction clip, rather than
relying on that raw output alone — see EXPERIMENTS.md "Experiments B/C" for
why this matters: unconstrained candidates on syllable-concatenated
re-pronunciation audio produced multi-word garbage, not real corrections.

Honest scope: this is NOT an external pronunciation dictionary. It is the set
of words that actually occur in the one Bengali speech corpus this project
uses (OpenSLR SLR53, CC-BY-SA-4.0), already downloaded for Stage 1 (see
DATA_PIPELINE.md). Any true word absent from this ~218,703-line corpus cannot
be produced as a lexicon-derived candidate — this is a real limitation, not
a full Bengali dictionary.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from pathlib import Path

import Levenshtein

_DEFAULT_TSV_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "raw" / "openslr_53" / "utt_spk_text.tsv"
)


@lru_cache(maxsize=1)
def load_lexicon(tsv_path: str | None = None) -> Counter:
    """Word -> frequency count, built from the TSV's transcript column (3rd
    tab-separated field: utterance_id, speaker_id, transcript). Cached
    per-process — the TSV is ~15.8MB / 218,703 lines, parsed once.

    `lru_cache` keys on `tsv_path`, so passing an explicit path vs. None (the
    default) are cached separately; tests that need a fresh load should call
    `load_lexicon.cache_clear()`.
    """
    path = Path(tsv_path) if tsv_path else _DEFAULT_TSV_PATH
    if not path.exists():
        return Counter()

    freq: Counter = Counter()
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            for word in parts[2].split():
                freq[word] += 1
    return freq


def is_available(tsv_path: str | None = None) -> bool:
    return len(load_lexicon(tsv_path)) > 0


_MAX_PHONETIC_RERANK_CANDIDATES = 25


def nearest_lexicon_words(
    text: str,
    top_k: int = 3,
    max_edit_distance: int = 3,
    tsv_path: str | None = None,
) -> list[str]:
    """Shortlists lexicon words within `max_edit_distance` raw-text
    Levenshtein distance of `text` (a cheap first pass over the corpus's
    unique words), then ranks the shortlist by phonetic similarity (espeak-ng
    G2P, phonetics/similarity.py) and returns the top_k, most-similar-first.

    Returns [] if the lexicon isn't available or nothing is within range —
    callers must fall back to the raw hypothesis in that case, never silently
    drop the candidate.

    This is a simple edit-distance shortlist + phonetic re-rank, not a full
    phonetic index (e.g. a BK-tree or phoneme trie) — adequate for this
    project's per-request candidate counts and corpus size, not benchmarked
    for anything larger. Flagged as a real engineering choice to revisit if
    the lexicon grows.

    Performance note (found 2026-09-07 during the correction-eval re-run,
    real not hypothetical): a short/garbage `text` (e.g. one multi-word-junk
    token from a bad Whisper hypothesis) can edit-distance-match hundreds of
    short lexicon words, and each phonetic_similarity() call was originally
    an uncached espeak-ng subprocess spawn (see espeak_g2p.py — now cached).
    To bound worst-case latency regardless of that cache, only the closest
    `_MAX_PHONETIC_RERANK_CANDIDATES` edit-distance matches are phonetically
    re-ranked, not the full shortlist — this can only drop already-marginal
    (high edit-distance) candidates, never the exact/near-exact matches that
    matter most.
    """
    freq = load_lexicon(tsv_path)
    if not freq or not text:
        return []

    from phonetics.similarity import phonetic_similarity  # local import: avoid import cycle at module load

    shortlist = [
        (word, Levenshtein.distance(text, word))
        for word in freq
        if abs(len(word) - len(text)) <= max_edit_distance
    ]
    shortlist = [(w, d) for w, d in shortlist if d <= max_edit_distance]
    if not shortlist:
        return []

    shortlist.sort(key=lambda pair: pair[1])
    shortlist = shortlist[:_MAX_PHONETIC_RERANK_CANDIDATES]

    scored = sorted(
        (word for word, _ in shortlist),
        key=lambda w: (phonetic_similarity(text, w), freq[w]),
        reverse=True,
    )
    return scored[:top_k]
