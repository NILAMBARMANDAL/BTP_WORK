"""Pluggable correction-engine interface (ARCHITECTURE.md).

Any correction method (pronunciation-only, +syllable, +semantic, hybrid)
implements CorrectionEngine so the API layer — and therefore the
frontend/backend — never has to change to compare methods experimentally.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np


@dataclass
class CorrectionRequest:
    audio: np.ndarray
    sample_rate: int
    original_word: str
    context_text: str
    mode: str  # "pronunciation_only" | "pronunciation_meaning"
    meaning_context: str | None = None


@dataclass
class Candidate:
    text: str
    acoustic_score: float = 0.0
    phonetic_score: float = 0.0
    semantic_score: float = 0.0
    contextual_score: float = 0.0
    final_score: float = 0.0


@dataclass
class CorrectionResult:
    candidates: list[Candidate] = field(default_factory=list)
    prediction: str | None = None
    ranking_weights: dict = field(default_factory=dict)


class CorrectionEngine(Protocol):
    def generate_candidates(self, request: CorrectionRequest) -> CorrectionResult: ...
