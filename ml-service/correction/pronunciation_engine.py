"""Mode A / Mode B correction engine: MVP implementation.

Candidate generation is grounded in actual acoustic evidence — candidates come
from Whisper re-transcribing the user's slow/syllable-level re-pronunciation
audio at several decoding temperatures (whisper.engine.transcribe_word_hypotheses),
not from an LLM inventing spellings. Each raw hypothesis is optionally
augmented (not replaced) with real-Bengali-word candidates phonetically near
it, drawn from the OpenSLR SLR53 corpus lexicon (phonetics/lexicon.py) — see
EXPERIMENTS.md "Experiments B/C" for why: the syllable-condition's very low
accuracy was traced to Whisper transcribing concatenated-syllable audio as
multi-word garbage, with no real-word candidate anywhere in the pool for
ranking to prefer. This is lexicon-AUGMENTED generation, not a hard
constraint: the raw hypothesis is always kept as a candidate too, so real
acoustic evidence is never discarded outright. Toggle via
CORRECTION_LEXICON_CONSTRAINT_ENABLED; effect on correction accuracy must be
measured by re-running run_correction_eval.py, not assumed.

Evidence sources (see RESEARCH.md "evidence-separated candidate ranking"):
  - acoustic_score: derived from Whisper's avg_logprob for that hypothesis.
    Lexicon-derived candidates inherit their parent hypothesis's acoustic
    score at a discount (see _LEXICON_ACOUSTIC_DISCOUNT below) since they are
    a nearest-neighbor guess, not a fresh Whisper decode of that exact text.
  - phonetic_score: similarity (phonetics/similarity.py) between the candidate
    and the ORIGINAL (possibly wrong) Whisper word from the main transcript —
    this rewards candidates that are plausible corrections of what was
    actually misheard, filtering out unrelated hallucinations from the
    re-pronunciation pass.
  - semantic_score: Mode B only. Cosine similarity between LaBSE embeddings
    of the candidate word and the user-supplied meaning/context text
    (semantics/embedder.py) — falls back to literal token containment only if
    the embedding model can't be loaded in this environment. See
    semantics/README.md for validation status/limitations. In Mode A this is
    always 0.0.
  - contextual_score: placeholder, always 0.0 for now (Phase 7 — no Bengali
    language-model fluency scoring implemented yet). Documented, not
    fabricated as working.
"""

from __future__ import annotations

import math

from correction.base import Candidate, CorrectionRequest, CorrectionResult
from phonetics import lexicon as lexicon_module
from phonetics.similarity import phonetic_similarity
from ranking.ranker import current_weights, rank_candidates
from semantics.embedder import semantic_similarity
from utils.config import settings
from whisper.engine import transcribe_word_hypotheses

_LEXICON_ACOUSTIC_DISCOUNT = 0.9


def _acoustic_score_from_logprob(avg_logprob: float) -> float:
    """Maps Whisper's avg_logprob (typically in roughly [-1, 0], more negative
    = less confident) to a [0, 1] score via exp — a standard, simple mapping."""
    return math.exp(avg_logprob)


def _lexicon_augmented_texts(raw_text: str) -> list[str]:
    """Real Bengali words phonetically near each whitespace-split token of
    `raw_text`, de-duplicated, order-preserved. [] if lexicon augmentation is
    disabled or unavailable (e.g. the OpenSLR TSV isn't present in this
    environment) — callers must not treat that as an error."""
    if not settings.correction_lexicon_constraint_enabled:
        return []

    tsv_path = settings.correction_lexicon_tsv_path or None
    seen: set[str] = set()
    ordered: list[str] = []
    for token in raw_text.split():
        for word in lexicon_module.nearest_lexicon_words(
            token,
            top_k=settings.correction_lexicon_top_k,
            max_edit_distance=settings.correction_lexicon_max_edit_distance,
            tsv_path=tsv_path,
        ):
            if word not in seen:
                seen.add(word)
                ordered.append(word)
    return ordered


def generate_candidates(request: CorrectionRequest) -> CorrectionResult:
    hypotheses = transcribe_word_hypotheses(request.audio, request.sample_rate)

    candidates: list[Candidate] = []
    seen_texts: set[str] = set()

    def _add(text: str, acoustic_score: float) -> None:
        if text in seen_texts:
            return
        seen_texts.add(text)
        semantic = (
            semantic_similarity(text, request.meaning_context or "")
            if request.mode == "pronunciation_meaning"
            else 0.0
        )
        candidates.append(
            Candidate(
                text=text,
                acoustic_score=acoustic_score,
                phonetic_score=phonetic_similarity(text, request.original_word),
                semantic_score=semantic,
                contextual_score=0.0,
            )
        )

    for hyp in hypotheses:
        acoustic = _acoustic_score_from_logprob(hyp.avg_logprob)
        _add(hyp.text, acoustic)
        for lexicon_text in _lexicon_augmented_texts(hyp.text):
            _add(lexicon_text, acoustic * _LEXICON_ACOUSTIC_DISCOUNT)

    if not candidates:
        return CorrectionResult(candidates=[], prediction=None, ranking_weights=current_weights())

    ranked = rank_candidates(candidates)
    return CorrectionResult(
        candidates=ranked,
        prediction=ranked[0].text,
        ranking_weights=current_weights(),
    )
