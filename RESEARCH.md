# Research Design

## Core research questions

1. **Primary:** Can targeted slow and syllable-level re-pronunciation improve
   correction of Bengali ASR (Whisper) errors, without requiring keyboard-based
   text correction?
2. **Secondary:** Does adding optional meaning/context as supplementary evidence
   improve correction accuracy beyond pronunciation-only correction?

Neither question is assumed answered. Both require measured data from the
experiments in `EXPERIMENTS.md`.

## What is and isn't the contribution

- Whisper is the **baseline ASR component**, not the contribution. We do not
  fine-tune Whisper unless baseline experiments show clear evidence it's warranted
  (see `EXPERIMENTS.md`).
- The contribution is the **interactive correction mechanism**: how a user's
  re-pronunciation (and optionally meaning) of a single flagged word is turned
  into a corrected transcript without typing.
- Automatic error detection is explicitly **out of scope** for the core system.
  The user manually identifies the incorrect word by reading the transcript.

## Two correction modes (experimental conditions, not "features to ship and forget")

- **Mode A — Pronunciation only**: acoustic + phonetic evidence from a slow /
  syllable-level re-recording of the target word.
- **Mode B — Pronunciation + meaning/context**: same acoustic/phonetic evidence,
  plus optional user-supplied meaning or sentence context as additional ranking
  evidence. Meaning is always optional and never replaces pronunciation.

## Evidence-separated candidate ranking

`final_score = acoustic_score + phonetic_score + semantic_score + contextual_score`

Weights are configuration, not code (see `configs/`). Every experiment records
which weights were used (via MLflow once introduced) so results are reproducible
and comparable.

## Engineering choices made for research validity, not convenience

- **faster-whisper (CTranslate2) is used as the Whisper inference engine**
  instead of `openai-whisper`. This is an engine/runtime choice, not a modeling
  choice — it loads the same published Whisper model weights, just with a more
  memory/latency-efficient inference backend. This does not bias transcription
  output in a way that affects the research question, and it makes local
  development feasible on a 4GB GPU. If this assumption is ever in question, we
  can A/B the two engines on a held-out set — this is a testable claim we are not
  currently treating as settled.
- Preprocessing (resampling, VAD, normalization, noise reduction, segmentation)
  is implemented as **configurable, individually toggleable** components (see
  `ml-service/audio/`) specifically so "preprocessing on vs off" is itself an
  experimental variable, not a silent default.
- The correction engine is a **pluggable interface** (see `ml-service/correction/`)
  so methods (pronunciation-only, +syllable, +semantic, hybrid) can be swapped
  without touching frontend/backend — required for the comparison in
  `EXPERIMENTS.md` section "Core experiments A–E".

## Data integrity discipline

We maintain a hard distinction between:
- **raw user input** (what the user typed/recorded/selected)
- **model prediction** (what the correction engine produced)
- **user feedback** (accept/retry signal)
- **validated correction** (a prediction the user explicitly accepted)
- **ground truth** (independently known correct transcript, used only for
  offline evaluation, never conflated with validated corrections)

This distinction is enforced in the MongoDB schema (`backend/`) — see
`DATA_PIPELINE.md`.

## Observed findings so far (from smoke-testing, not a rigorous benchmark)

These come from testing the Phase 2/4 vertical slice against a handful of
synthetic (gTTS) Bengali audio clips on the local GTX 1650. They are real
observations worth tracking, but are **not** a substitute for the real
evaluation in `EXPERIMENTS.md` — sample size is effectively 1-2 phrases.

- **Whisper model size matters a lot for Bengali, in a specific way**: the
  `small` and `medium` faster-whisper checkpoints were observed to sometimes
  output Bengali speech using Devanagari-like transliteration instead of
  Bengali (Bangla) Unicode script, even with `language="bn"` forced and
  `language_probability=1.0` reported. `large-v3` (int8-quantized, which fits
  the 4GB GPU) correctly used Bengali script. This changed our default
  (`WHISPER_MODEL_SIZE=large-v3`, see `GPU_SETUP.md`) but needs a real
  benchmark across more samples/models before treating it as settled.
- **স/শ/ষ are frequently indistinguishable acoustically** in standard Bengali
  pronunciation (all commonly realized as a similar "sh" sound), which means
  Whisper's exact script choice between them can be non-deterministic across
  decode passes for a word containing one of these letters. This is a real
  challenge for a pronunciation-only correction approach: re-pronouncing a
  word doesn't help disambiguate a merger that exists in the pronunciation
  itself. This is exactly the kind of case where Mode B's optional
  meaning/context evidence could plausibly help — worth watching for in
  experiment results, not assumed.
- **The nukta diacritic (়, as in ড়/ঢ়/য়) was observed to sometimes get
  dropped** in Whisper output (e.g. "বাড়ি" transcribed without the nukta on
  ড়). Test assertions and any exact-match evaluation logic should account for
  this rather than requiring byte-exact Unicode equality.

## Known limitations (documented, not hidden)

- No specialized Bengali phoneme/pronunciation-dictionary resource has been
  identified and validated yet (see `ml-service/phonetics/README.md` once
  written). Until one is validated, phonetic similarity uses the most
  scientifically defensible available alternative, documented at the point it's
  implemented — not invented linguistic rules.
- Dataset selection (`DATA_PIPELINE.md`) is pending research into licensing and
  suitability; nothing has been downloaded or used for training yet as of this
  writing.
