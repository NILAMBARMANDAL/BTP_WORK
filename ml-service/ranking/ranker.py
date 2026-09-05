"""Combines per-source scores into a final ranking score using configurable
weights (RESEARCH.md: final_score = acoustic + phonetic + semantic + contextual,
weighted). Weights are never hardcoded silently — they come from Settings, and
the exact weights used are returned alongside results so every attempt is
reproducible.
"""

from __future__ import annotations

from correction.base import Candidate
from utils.config import settings


def rank_candidates(candidates: list[Candidate]) -> list[Candidate]:
    w_acoustic = settings.ranking_weight_acoustic
    w_phonetic = settings.ranking_weight_phonetic
    w_semantic = settings.ranking_weight_semantic
    w_contextual = settings.ranking_weight_contextual

    for c in candidates:
        c.final_score = (
            w_acoustic * c.acoustic_score
            + w_phonetic * c.phonetic_score
            + w_semantic * c.semantic_score
            + w_contextual * c.contextual_score
        )

    return sorted(candidates, key=lambda c: c.final_score, reverse=True)


def current_weights() -> dict:
    return {
        "acoustic": settings.ranking_weight_acoustic,
        "phonetic": settings.ranking_weight_phonetic,
        "semantic": settings.ranking_weight_semantic,
        "contextual": settings.ranking_weight_contextual,
    }
