# Experiments

**Status: no experiments have been run yet.** This file defines what will be
measured and how; results get filled in (with MLflow tracking, once Phase 9
begins) only as they actually happen. Never treat anything in this file as a
result until a corresponding MLflow run / evaluation output exists.

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

None.

## Pending

Everything above — blocked on: (1) a dataset decision (`DATA_PIPELINE.md` —
needs a licensing decision from the user for OpenSLR's CC-BY-SA-4.0 and
OOD-Speech's unresolved license), (2) `ml-service/evaluation/` implementation,
(3) MLflow integration (Phase 9).
