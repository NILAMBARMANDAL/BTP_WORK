# Experiments

**Status: Experiment A (baseline) has a real, MLflow-tracked result — see
below.** Everything else in this file remains a plan, not a result, until a
corresponding MLflow run / evaluation output exists for it too.

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

## Pending

Experiments B–E (all correction-method comparisons) — blocked on building the
correction-attempt dataset from real user interactions (or a controlled
proxy), per `DATA_PIPELINE.md`'s correction-dataset design section. The
Whisper-error analysis needed to pick which categories (rare words, proper
nouns, etc.) are actually worth targeting has not been done yet — the 5
manually-inspected samples above are illustrative, not a systematic error
analysis.
