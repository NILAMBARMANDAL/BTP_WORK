# Semantic scoring (Mode B) — current approach and limitations

**Update (2026-09-06): real embedding-based semantic scoring implemented**,
replacing the v0 literal-substring-containment placeholder described in
earlier versions of `PROGRESS.md`.

## Current approach

`semantics/embedder.py` uses `sentence-transformers/LaBSE` (Google,
Apache-2.0) to embed the candidate word and the user-supplied
meaning/context sentence, and scores them by cosine similarity (rescaled
from LaBSE's roughly `[-1, 1]` range to `[0, 1]`).

**Why LaBSE specifically:** it was chosen only after checking its model
card's language list, which explicitly includes Bengali (`bn`) among its 109
supported languages. The more commonly recommended
`paraphrase-multilingual-mpnet-base-v2` was checked first and its published
50-language list does **not** include Bengali, so it was rejected rather than
assumed to work. This is a local, open model — no paid API — per the
project's "prefer local/open models" rule; it runs on CPU by default
(`SEMANTIC_DEVICE=cpu`) since the dev GPU (4GB) is already used by Whisper.

If the model can't be loaded in a given environment (e.g. no internet on
first run and no local Hugging Face cache yet), `semantic_similarity()`
falls back automatically to the old literal-containment heuristic rather than
crashing the correction endpoint — call `semantic_method()` to check which
one is actually active, and always log it alongside experiment results.

## Known limitations (honest, not yet resolved)

- **Not benchmarked for Bengali specifically.** LaBSE's Bengali support is
  claimed by its own model card and by general multilingual-embedding
  literature, but no Bengali-specific semantic-similarity benchmark has been
  run in this project. Treat `semantic_score` as a real (not fabricated)
  signal, but not a validated metric, until such an evaluation exists — same
  discipline as `phonetics/README.md`.
- LaBSE embeds a candidate **word** against a **sentence**-level
  meaning/context string; this is an asymmetric comparison (word-to-sentence,
  not word-to-word or sentence-to-sentence) that sentence embedding models
  are not specifically optimized for. It may under- or over-score depending
  on context length/specificity — not yet studied.
- No contextual/fluency scoring exists yet (`contextual_score` is still
  always `0.0` — a Bengali language-model fluency signal is future work, not
  part of this change).
- Candidate generation is still grounded entirely in Whisper re-transcription
  of the user's re-pronunciation audio (see `correction/pronunciation_engine.py`)
  — the semantic score only re-ranks those candidates, it never invents a
  spelling, per the project's "no LLM-invented spellings" rule.

## What would improve this

- A small human-annotated Bengali word-meaning relevance test set, to
  actually measure whether `semantic_score` correlates with human judgment.
- Comparing LaBSE against a Bengali-specific sentence embedding model (e.g.
  from AI4Bharat or a BanglaBERT-derived sentence encoder), if one with a
  clear, permissive license is found — not yet investigated.
