"""Mode A / Mode B correction engine: MVP implementation.

Candidate generation is grounded in actual acoustic evidence — candidates come
from Whisper re-transcribing the user's slow/syllable-level re-pronunciation
audio at several decoding temperatures (whisper.engine.transcribe_word_hypotheses),
not from an LLM inventing spellings.

Evidence sources (see RESEARCH.md "evidence-separated candidate ranking"):
  - acoustic_score: derived from Whisper's avg_logprob for that hypothesis.
  - phonetic_score: similarity (phonetics/similarity.py) between the candidate
    and the ORIGINAL (possibly wrong) Whisper word from the main transcript —
    this rewards candidates that are plausible corrections of what was
    actually misheard, filtering out unrelated hallucinations from the
    re-pronunciation pass.
  - semantic_score: Mode B only. Current implementation is a v0 placeholder —
    literal token containment between the candidate and the user-supplied
    meaning/context text. This is NOT a validated semantic model; a real
    embedding-based implementation is planned for Phase 6/7 (see PROGRESS.md).
    In Mode A this is always 0.0.
  - contextual_score: placeholder, always 0.0 for now (Phase 7 — no Bengali
    language-model fluency scoring implemented yet). Documented, not
    fabricated as working.
"""

from __future__ import annotations

import math

from correction.base import Candidate, CorrectionRequest, CorrectionResult
from phonetics.similarity import phonetic_similarity
from ranking.ranker import current_weights, rank_candidates
from whisper.engine import transcribe_word_hypotheses


def _acoustic_score_from_logprob(avg_logprob: float) -> float:
    """Maps Whisper's avg_logprob (typically in roughly [-1, 0], more negative
    = less confident) to a [0, 1] score via exp — a standard, simple mapping."""
    return math.exp(avg_logprob)


def _semantic_score_v0(candidate_text: str, meaning_context: str | None) -> float:
    if not meaning_context:
        return 0.0
    return 1.0 if candidate_text in meaning_context else 0.0


def generate_candidates(request: CorrectionRequest) -> CorrectionResult:
    hypotheses = transcribe_word_hypotheses(request.audio, request.sample_rate)

    candidates: list[Candidate] = []
    for hyp in hypotheses:
        semantic = (
            _semantic_score_v0(hyp.text, request.meaning_context)
            if request.mode == "pronunciation_meaning"
            else 0.0
        )
        candidates.append(
            Candidate(
                text=hyp.text,
                acoustic_score=_acoustic_score_from_logprob(hyp.avg_logprob),
                phonetic_score=phonetic_similarity(hyp.text, request.original_word),
                semantic_score=semantic,
                contextual_score=0.0,
            )
        )

    if not candidates:
        return CorrectionResult(candidates=[], prediction=None, ranking_weights=current_weights())

    ranked = rank_candidates(candidates)
    return CorrectionResult(
        candidates=ranked,
        prediction=ranked[0].text,
        ranking_weights=current_weights(),
    )
