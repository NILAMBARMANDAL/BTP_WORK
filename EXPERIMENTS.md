# Experiments

**Status: Experiments A (baseline) and B/C (slow vs. syllable correction, on a
documented TTS proxy) have real, MLflow-tracked results — see below.**
Experiment D (meaning/context) and a non-proxy re-run of B/C/E remain plans,
not results, until real user correction data or an approved synthesis method
exists.

## Core experiments (spec section 31)

| ID | Condition |
|---|---|
| A | Original Whisper baseline (no correction) |
| B | Slow re-pronunciation correction (Mode A, `pronunciationStyle=slow`) |
| C | Slow + syllable-by-syllable correction (Mode A, `pronunciationStyle=syllable`) |
| D | Slow/syllable + meaning/context (Mode B) |
| E | Hybrid methods (once phonetic/semantic scoring is more mature — see `RESEARCH.md` limitations) |

## Questions these must answer (not assumed in advance)

1. Does slow re-pronunciation improve correction over baseline?
2. Does syllable-level pronunciation improve correction further?
3. Does optional meaning/context provide additional benefit over pronunciation alone?
4. Which method performs best overall?
5. How many attempts are typically required to reach an accepted correction?
6. How much user effort (time, attempts, recordings) does correction require?
7. How does background noise affect each method?
8. How does the original speech's speed affect each method?

## Metrics (`ml-service/evaluation/`, not yet implemented)

- CER (character error rate), WER (word error rate) — for the underlying
  Whisper baseline and for post-correction transcripts
- Correction accuracy (did the accepted correction match ground truth?)
- Correction success rate (fraction of flagged words eventually accepted vs.
  abandoned)
- Average attempts per accepted correction
- Latency (per `CorrectionAttempt.latencyMs`, already captured in the schema)

## Conditions to vary (each independently, per RESEARCH.md's configurability requirement)

- Preprocessing on/off, and each component individually (`ml-service/audio/preprocessing.py`)
- Whisper model size / compute type (`GPU_SETUP.md` "Model size findings" — needs a real multi-sample benchmark, not just the 1-2 sample smoke test done so far)
- Ranking weights (`ml-service/ranking/ranker.py`, `.env` `RANKING_WEIGHT_*`)
- Speaker/dialect/rare-word/proper-noun subsets, once Stage 1 data exists (`DATA_PIPELINE.md`)

## Data leakage protocol

Speaker-disjoint splits required (spec section 32) once real data is used —
not yet implemented since no dataset has been ingested (`DATA_PIPELINE.md`).

## Completed experiments

### Experiment A — Original Whisper baseline (2026-09-06)

**Real, measured result — MLflow run `bengali-asr-baseline` (local file
store, `ml-service/mlruns/`).** Not a projection or smoke test.

- **Dataset:** 200-sample manifest sampled (seed 42) from OpenSLR SLR53
  shard 0, fetched via HTTP range requests (no full-shard download — see
  `DATA_PIPELINE.md`). Manifest:
  `data/processed/openslr_53_shard0_manifest.json`,
  `manifest_sha256=ceb1f02c502b319e08e94bf474061b2e31c6fb503cb58583d344c2b0311f6b9`.
  License: CC-BY-SA-4.0.
- **Model:** `large-v3`, `int8_float16`, CUDA (GTX 1650, 4GB VRAM), beam
  size 5, language forced to `bn`. faster-whisper (CTranslate2).
- **Preprocessing:** default (`audio/preprocessing.py` — resample to 16kHz
  mono; VAD/denoise/trim off).
- **Results (all 200 samples transcribed successfully, 0 skipped):**

  | Metric | Normalized* | Raw |
  |---|---|---|
  | WER | 0.8106 | 0.8185 |
  | CER | 0.2580 | 0.2604 |

  \*Normalized = punctuation stripped, Unicode NFC, whitespace collapsed on
  both reference and hypothesis before scoring (`evaluation/metrics.py::normalize_transcript`)
  — removes non-substantive differences like Whisper emitting a trailing "?"
  that the reference transcript doesn't have.
- **Avg latency:** 3718.8 ms/sample (single 4GB GPU, large-v3 int8, no
  batching — not representative of a production/institute-GPU setup).
- **Manual sanity check (5 random samples, not included in the aggregate
  above, just qualitative):** the errors are real phonetic/character-level
  substitutions and boundary mistakes (e.g. reference "মাথায় বাঁধা জাতীয়
  পতাকা" vs. hypothesis "মাথাই বাধা জাতে ও পতকা"), not a data-pipeline
  artifact — confirmed by inspecting raw audio-path-to-transcript pairs
  directly, not inferred from the aggregate score alone.
- **Interpretation (not yet a conclusion — one dataset, one model config):**
  WER is much higher than CER, which is expected for Bengali given a fair
  number of near-miss character substitutions per word (a WER metric scores
  a word wrong even with a single wrong character) — this is a real property
  of the error distribution here, not a metric bug (the punctuation-inflation
  bug that caused an earlier, higher WER reading was found and fixed; see
  `normalize_transcript`). Whether this WER level is typical for OpenSLR
  SLR53 vs. specific to this random 200-sample draw has not been checked
  against a larger sample or a second dataset yet.
- **Reproduce:** `ml-service/scripts/run_baseline_eval.py --manifest
  data/processed/openslr_53_shard0_manifest.json --n-samples 200 --seed 42
  --use-mlflow`.

### Exploratory error-category analysis (2026-09-06, observational only)

Per this file's "types of errors" questions and the project rule not to
assume error categories matter without data support,
`ml-service/scripts/analyze_baseline_errors.py` correlates per-sample CER
(from a `--dump-per-sample` re-run of Experiment A, same 200 samples) against
the only two categories actually derivable from OpenSLR SLR53's TSV: speech
rate (words/second, from audio duration) and rare-word presence (word
frequency <= 5 across the full 218,703-line TSV — the only frequency
reference used, no external corpus). Proper nouns, place names, noise, and
dialect were **not** analyzed — SLR53 has no such labels, and labeling them
without a verified method would be exactly the kind of invented category the
project rules forbid.

| Speech-rate tercile | n | mean CER |
|---|---|---|
| slow | 67 | 0.3251 |
| normal | 67 | 0.2743 |
| fast | 66 | 0.2283 |

| Rare-word presence | n | mean CER |
|---|---|---|
| has a word with freq <= 5 | 65 | 0.2876 |
| no rare word | 135 | 0.2707 |

**Honest interpretation:** rare-word presence shows the expected direction
(slightly higher error), but the effect is small on this sample size. Speech
rate shows the *opposite* of the naive assumption — slower speech has
*higher* CER here, not lower — plausibly because in this prompted
read-speech corpus, low words/second may reflect hesitant/drawn-out
recordings or silence padding rather than genuinely easier, clearly-paced
speech, but that's a hypothesis, not confirmed. **No significance test was
run and this is a single 200-sample draw from one shard** — do not cite
either result as validated without a larger sample or repeated draws.
Reproduce: `ml-service/scripts/run_baseline_eval.py ... --dump-per-sample
data/processed/baseline_per_sample.json` then
`ml-service/scripts/analyze_baseline_errors.py --per-sample
data/processed/baseline_per_sample.json --tsv
data/raw/openslr_53/utt_spk_text.tsv`.

### Speaker-disjoint split (2026-09-06)

`scripts/split_dataset.py` split the 200-sample OpenSLR SLR53 pool (168
speakers) into train/val/test by whole speaker (greedy bin-packing on
speaker-group size, largest first, targeting 70/15/15) — no speaker appears
in more than one split (asserted in the script). Result: train 140
samples/108 speakers, val 30/30, test 30/30 (exact counts/ratios recorded in
`data/processed/openslr_53_splits.json`, gitignored per `DATA_PIPELINE.md`
versioning strategy — reproducible from the manifest + `--seed 42`). This
unblocks Experiments B–E's leakage protocol (spec section 20/32); it does
**not** by itself supply correction interaction data.

### Experiments B/C — Slow vs. syllable-level re-pronunciation correction (2026-09-06)

**Real Whisper + real correction-engine result, but on a documented PROXY
input, not real human re-pronunciation — read the limitation before citing
this anywhere.** No live user has used the frontend yet (see `PROGRESS.md`),
so `ml-service/scripts/run_correction_eval.py` synthesizes the
re-pronunciation audio with gTTS (`lang=bn, slow=True`) as a stand-in for a
human re-pronouncing the word, then runs that synthetic audio through the
exact same production correction engine
(`correction/pronunciation_engine.py`) real user audio would go through. This
measures "can the engine recover the right word from a clean, correctly
pronounced re-pronunciation clip" — a real, useful signal — but says nothing
about real human re-pronunciation behavior (hesitation, self-mispronunciation,
noise, accent).

- **Dataset:** the 30-sample speaker-disjoint `test` split above, filtered to
  the 30 samples with a real Whisper word-level error (from Experiment A's
  per-sample dump) that word-align to exactly one clean single-word
  substitution (`difflib` opcode-based alignment); 0 samples were skipped for
  lacking a clean single-word substitution in this split.
- **Conditions:**
  - **slow** — one gTTS clip of the whole ground-truth word, `slow=True`.
  - **syllable** — the word is heuristically syllabified
    (`phonetics/syllables.py`), each syllable synthesized as its own gTTS
    clip, concatenated with 250ms silence gaps.
- **Correction engine:** Mode A (`pronunciation_only`), candidates are
  Whisper re-transcriptions of the correction clip at multiple decoding
  temperatures (`whisper/engine.py::transcribe_word_hypotheses`) ranked by
  acoustic + phonetic score against the original wrong word — **there is no
  dictionary/lexicon constraint on candidates**, which matters for
  interpreting the syllable result below.
- **Results:**

  | Condition | n attempts | n correct | correction accuracy | avg latency |
  |---|---|---|---|---|
  | slow | 29 | 1 | 0.034 | 8398 ms |
  | syllable | 27 | 0 | 0.000 | 9225 ms |

  (n differs slightly between conditions because 2 syllable-condition runs
  threw and were recorded as failures, not silently counted as correct or
  skipped — see script.)
- **Honest interpretation:** both accuracies are very low, and on this data
  **syllable-level re-pronunciation did not outperform whole-word slow
  re-pronunciation — it was worse (0/27 vs 1/29)**, which is the opposite of
  what the project hypothesizes syllable-level correction should do. Manual
  inspection of the syllable-condition predictions (e.g. ground truth
  "মাথায়" → predicted "মা হা জো নুক্ত"; "জয়টাও" → "জা, জা, নুক তাটা, ও")
  shows Whisper transcribing the concatenated-syllable clips as multi-word
  garbage rather than the target word, not a scoring bug. The most plausible
  cause, given candidates come from unconstrained Whisper re-transcription
  (no lexicon): gTTS-synthesized syllables glued with silence gaps do not
  sound like genuine syllable-by-syllable human speech (no coarticulation
  across the gap, TTS may pick an arbitrary/wrong reading per isolated
  syllable), and Whisper handles the resulting acoustic artifacts by
  hallucinating multiple short "words" instead of one. The slow-condition
  errors are milder (near-miss single/double-word outputs like "দের তার" for
  "দেড়টার") but still mostly wrong. **This is a real, if small-sample (n=27–29)
  and proxy-limited, negative finding against the current unconstrained
  candidate-generation design for syllable-level correction** — it does not
  mean human syllable-by-syllable pronunciation would fail the same way, and
  does not mean the hypothesis is false, only that this specific TTS-proxy
  measurement of it, with this candidate-generation method, performed badly.
  A likely next step (not yet done, a design decision not made unilaterally
  here beyond flagging it): constrain candidates to a real Bengali lexicon
  near the original wrong word, rather than accepting raw unconstrained
  Whisper output, before re-testing syllable-level correction.
- **Reproduce:** `uv run --directory ml-service python
  scripts/run_correction_eval.py --splits data/processed/openslr_53_splits.json
  --per-sample data/processed/baseline_per_sample.json --split-name test
  --use-mlflow` (requires internet for gTTS and a working Whisper model).
  Logged to MLflow experiment `bengali-asr-correction`, run
  `correction-eval-test`.

### Experiments B/C re-run — lexicon-augmented candidate generation (2026-09-07/08)

The candidate-generation lexicon constraint flagged as a next step above was
implemented (`ml-service/phonetics/lexicon.py`) and the exact same eval
re-run on the exact same 30-sample speaker-disjoint test split, so this is a
real before/after comparison, not a new/different experiment. Design: each
raw Whisper hypothesis is *augmented* (not replaced) with real Bengali words
phonetically near it, drawn from the OpenSLR SLR53 corpus's own word list
(the transcript TSV already in use, not an external dictionary) — see
`correction/pronunciation_engine.py` docstring for the exact mechanism and its
honest scope limit (a word never appearing in that corpus cannot be produced).

**Results:**

| Condition | n | correct | accuracy | avg latency | (baseline avg latency) |
|---|---|---|---|---|---|
| slow | 29 | 2 | 0.069 | 10809.9 ms | 8398 ms |
| syllable | 27 | 0 | 0.000 | 12253.3 ms | 9225 ms |

**Honest interpretation — this is a small, real effect, not a fix:** slow
correction went from 1/29 to 2/29 correct. On a sample this small (n=29) a
1-attempt difference is not a statistically meaningful improvement — it could
easily be noise, and was not tested for significance. Syllable-level
correction **did not improve at all** — still 0/27 — so lexicon augmentation
did **not** rescue the syllable condition, which remains the project's real
negative finding: this eval design still cannot demonstrate a benefit from
syllable-by-syllable re-pronunciation over whole-word slow re-pronunciation.
Manual inspection of the two newly-correct slow-condition cases (both real):
ground truth "মাহি" (Whisper's wrong word "মাহে") → predicted "মাহি" (3
candidates); ground truth "ভঙ্গিতে" (wrong "বংগিতে") → predicted "ভঙ্গিতে"
(11 candidates — the multi-candidate count here is a direct, visible sign
lexicon augmentation actually contributed candidates that raw Whisper
re-transcription alone was not producing before). Latency also genuinely
increased ~29-33% over the baseline (a real cost of doing the extra lexicon
lookup/re-ranking work), which matters for spec section 38's "optimize
expensive operations" — noted as an open cost/benefit tradeoff, not resolved
in this project's favor by this result.

**A real performance bug was found and fixed during this re-run, not before
it — flagged for research-integrity honesty:** the first attempt at this
re-run took over 1h45m (vs. ~8-9 min originally) and was killed as
unreasonably slow, not because the design was wrong but because
`phonetics/espeak_g2p.to_phonemes()` spawned an *uncached* `espeak-ng`
subprocess on every call, and the lexicon shortlist could fan that out to
hundreds of calls for a single garbage multi-word hypothesis (the syllable
condition's known failure mode, see above). Fixed with an `lru_cache` on
`to_phonemes()` and a cap (25) on how many edit-distance-shortlisted
candidates get phonetically re-ranked (`phonetics/lexicon.py`) — verified with
a bounded 5-sample smoke run (`run_correction_eval.py --max-samples 5`, a new
flag added for exactly this purpose) before re-running the full split. The
numbers above are from the *fixed* code.

**Reproduce:** identical command to the original run above; the lexicon
augmentation is on by default (`CORRECTION_LEXICON_CONSTRAINT_ENABLED=true`)
and can be disabled via that env var to reproduce the original unaugmented
numbers with the current code. Detailed per-attempt results:
`data/processed/correction_eval_lexicon_augmented_per_sample.json`
(gitignored, regenerable).

### Experiment D (meaning/context, Mode B) — not run

Deliberately not attempted with a synthetic proxy: synthesizing
non-answer-leaking meaning/context text (text that helps disambiguate the
word without literally containing it) is a methodology decision that affects
what the experiment actually measures, not a routine engineering choice — see
`run_correction_eval.py`'s docstring. This needs either real user-supplied
context or an explicit, user-approved synthesis method before it can be run
without risk of a misleading result.

## Pending

Experiment E (hybrid ranking) and a real (non-proxy) re-run of B/C/D — all
blocked on real correction-attempt data from actual user interactions via the
frontend, which still has not been manually tested end-to-end in a browser
(see `PROGRESS.md`). The candidate-generation lexicon-constraint idea flagged
above under Experiments B/C **has now been evaluated (2026-09-07/08, see
"Experiments B/C re-run" above)** — it produced a small, not statistically
meaningful improvement on the slow condition (1→2 of 29) and no improvement
on syllable (still 0/27), so the TTS-proxy limitation and/or the underlying
gTTS-synthesized-syllable acoustic-artifact problem remain the more likely
explanations for the syllable condition's poor result, not solely the
candidate-generation gap. Real (non-proxy) data is still the next thing that
would actually move this forward, not further candidate-generation tuning on
synthetic data.
