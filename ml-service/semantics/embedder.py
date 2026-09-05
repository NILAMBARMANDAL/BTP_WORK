"""Real embedding-based semantic similarity for Mode B (pronunciation +
meaning/context), replacing the v0 literal-containment placeholder that used
to live in correction/pronunciation_engine.py.

Model: sentence-transformers/LaBSE (Google, Apache-2.0, local/open — no paid
API). LaBSE's own model card lists Bengali ('bn') among its 109 supported
languages, which is why it was chosen over more common multilingual models
like paraphrase-multilingual-mpnet-base-v2, whose language list does NOT
include Bengali (checked before choosing, not assumed). See
semantics/README.md for the honest limitations of this choice.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from utils.config import settings


@lru_cache(maxsize=1)
def _load_model():
    """Lazily loads the SentenceTransformer model once per process. Returns
    None (not an exception) if it can't be loaded — e.g. no internet on
    first run and no local HF cache yet — so callers can fall back cleanly
    instead of crashing the correction endpoint."""
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(settings.semantic_model_name, device=settings.semantic_device)
    except Exception:  # noqa: BLE001 — any load failure means "unavailable", not a crash
        return None


def is_available() -> bool:
    return _load_model() is not None


def semantic_method() -> str:
    """Reports which semantic scoring method is actually active, so
    experiment results/logs can record it (same principle as
    phonetics.similarity.phonetic_method())."""
    return settings.semantic_model_name if is_available() else "fallback-literal-containment"


def semantic_similarity(candidate_text: str, meaning_context: str) -> float:
    """Returns a [0, 1] score: cosine similarity between the candidate word's
    embedding and the user-supplied meaning/context sentence's embedding,
    rescaled from LaBSE's typical [-1, 1] range. Returns via the literal
    v0 fallback if the model isn't available in this environment."""
    if not candidate_text or not meaning_context:
        return 0.0

    model = _load_model()
    if model is None:
        return 1.0 if candidate_text in meaning_context else 0.0

    embeddings = model.encode([candidate_text, meaning_context], normalize_embeddings=True)
    cosine = float(np.dot(embeddings[0], embeddings[1]))
    return max(0.0, min(1.0, (cosine + 1.0) / 2.0))
