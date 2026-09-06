"""Experiments B/C: does a re-pronunciation correction pass recover Whisper's
word-level errors, and does syllable-level re-pronunciation help more than a
single slow re-pronunciation of the whole word?

IMPORTANT METHODOLOGY LIMITATION (read before citing these numbers anywhere):
No real human "user re-pronounces the word" audio exists yet — the frontend
has not been used by a live person (see PROGRESS.md). This script therefore
synthesizes the re-pronunciation audio with gTTS (Google TTS, `slow=True`)
as a documented PROXY for a human re-pronunciation, run through the exact
same real Whisper + phonetic-scoring correction engine
(correction/pronunciation_engine.py) a real user's audio would go through.
This measures "can the correction engine recover the right word given a
clean, correctly-spoken re-pronunciation," which is a real and useful signal,
but it is NOT a measurement of real human re-pronunciation behavior (hesitation,
mispronunciation-of-the-correction-itself, background noise, etc.). Do not
present this as validating real-user correction accuracy — see EXPERIMENTS.md.

Mode B (pronunciation + meaning/context) is intentionally NOT covered here:
synthesizing non-leaking meaning/context text (text that helps disambiguate
the word without literally containing the answer) is a methodology decision,
not a routine engineering one — flagged for the user rather than fabricated.

Method per test-set sample with a real Whisper word-level error:
  1. Word-align reference vs. hypothesis (difflib) to find one substituted
     word: (ground_truth_word, whisper_wrong_word).
  2. Condition "slow": gTTS(ground_truth_word, lang=bn, slow=True) -> one clip.
  3. Condition "syllable": syllabify(ground_truth_word), synthesize each
     syllable separately (gTTS slow=True), concatenate with short silence gaps.
  4. Run each clip through the real correction engine
     (mode="pronunciation_only", original_word=whisper_wrong_word,
     context_text=reference sentence).
  5. Record whether the top-ranked candidate == ground_truth_word.

Usage (from ml-service/, venv active, requires internet for gTTS + a GPU/CPU
Whisper model already working):
    python scripts/run_correction_eval.py \
        --splits ../data/processed/openslr_53_splits.json \
        --per-sample ../data/processed/baseline_per_sample.json \
        --split-name test --use-mlflow
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    import torch

    torch_lib_dir = Path(torch.__file__).parent / "lib"
    if torch_lib_dir.is_dir():
        os.add_dll_directory(str(torch_lib_dir))

import numpy as np
import librosa
from gtts import gTTS

from audio.preprocessing import load_and_preprocess
from correction.base import CorrectionRequest
from correction.pronunciation_engine import generate_candidates
from phonetics.syllables import syllabify
from utils.config import settings

TTS_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "tts_correction_eval"
TARGET_SR = 16000
SILENCE_GAP_S = 0.25


def _normalize(word: str) -> str:
    return unicodedata.normalize("NFC", word.strip())


def find_one_substitution(reference: str, hypothesis: str) -> tuple[str, str] | None:
    """Returns (ground_truth_word, whisper_wrong_word) for the first word-level
    'replace' block the aligner finds, or None if there isn't a clean
    single-word substitution to correct (e.g. only insertions/deletions,
    or reference == hypothesis)."""
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    if ref_words == hyp_words:
        return None
    matcher = difflib.SequenceMatcher(a=ref_words, b=hyp_words, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace" and i2 - i1 >= 1 and j2 - j1 >= 1:
            return _normalize(ref_words[i1]), _normalize(hyp_words[j1])
    return None


def _synth_clip(text: str, cache_key: str) -> Path:
    TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = TTS_CACHE_DIR / f"{cache_key}.mp3"
    if not path.exists():
        gTTS(text=text, lang="bn", slow=True).save(str(path))
    return path


def synth_slow(word: str) -> np.ndarray:
    path = _synth_clip(word, f"slow_{word}")
    audio, _ = librosa.load(str(path), sr=TARGET_SR, mono=True)
    return audio


def synth_syllable(word: str) -> np.ndarray:
    syllables = syllabify(word)
    gap = np.zeros(int(SILENCE_GAP_S * TARGET_SR), dtype=np.float32)
    parts: list[np.ndarray] = []
    for i, syl in enumerate(syllables):
        path = _synth_clip(syl, f"syl_{syl}")
        audio, _ = librosa.load(str(path), sr=TARGET_SR, mono=True)
        if i > 0:
            parts.append(gap)
        parts.append(audio)
    return np.concatenate(parts) if parts else np.zeros(1, dtype=np.float32)


@dataclass
class AttemptResult:
    utt_id: str
    speaker_id: str
    condition: str
    ground_truth_word: str
    whisper_wrong_word: str
    predicted_word: str | None
    correct: bool
    n_candidates: int
    latency_ms: float


def run_condition(condition: str, word: str, wrong_word: str, context_text: str) -> tuple[str | None, int, float]:
    audio = synth_slow(word) if condition == "slow" else synth_syllable(word)

    import soundfile as sf

    tmp_path = TTS_CACHE_DIR / f"_tmp_{condition}_{os.getpid()}.wav"
    sf.write(str(tmp_path), audio, TARGET_SR)
    try:
        preprocessed = load_and_preprocess(str(tmp_path))
        request = CorrectionRequest(
            audio=preprocessed.audio,
            sample_rate=preprocessed.sample_rate,
            original_word=wrong_word,
            context_text=context_text,
            mode="pronunciation_only",
            meaning_context=None,
        )
        start = time.time()
        result = generate_candidates(request)
        latency_ms = (time.time() - start) * 1000
        return result.prediction, len(result.candidates), latency_ms
    finally:
        tmp_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--splits", required=True, type=Path)
    parser.add_argument("--per-sample", required=True, type=Path, help="baseline_per_sample.json from run_baseline_eval.py --dump-per-sample")
    parser.add_argument("--split-name", default="test", choices=["train", "val", "test"])
    parser.add_argument("--dump-per-sample", type=Path, default=None)
    parser.add_argument("--use-mlflow", action="store_true")
    parser.add_argument("--mlflow-experiment", default="bengali-asr-correction")
    args = parser.parse_args()

    with args.splits.open("r", encoding="utf-8") as f:
        splits = json.load(f)
    with args.per_sample.open("r", encoding="utf-8") as f:
        per_sample = json.load(f)

    test_utt_ids = set(splits["splits"][args.split_name]["utt_ids"])
    candidates_pool = [r for r in per_sample if r["utt_id"] in test_utt_ids and r["wer"] > 0]
    print(f"{len(candidates_pool)} / {len(test_utt_ids)} '{args.split_name}'-split samples have a real Whisper error.")

    attempts: list[AttemptResult] = []
    skipped_no_substitution = 0

    for i, rec in enumerate(candidates_pool):
        sub = find_one_substitution(rec["reference"], rec["hypothesis"])
        if sub is None:
            skipped_no_substitution += 1
            continue
        ground_truth_word, wrong_word = sub

        for condition in ("slow", "syllable"):
            try:
                predicted, n_cand, latency_ms = run_condition(condition, ground_truth_word, wrong_word, rec["reference"])
            except Exception as exc:  # noqa: BLE001 — record failure, don't fabricate a result
                print(f"  [{i+1}/{len(candidates_pool)}] {condition} FAILED on {rec['utt_id']}: {exc}")
                continue
            correct = predicted is not None and _normalize(predicted) == ground_truth_word
            attempts.append(
                AttemptResult(
                    utt_id=rec["utt_id"],
                    speaker_id=rec["speaker_id"],
                    condition=condition,
                    ground_truth_word=ground_truth_word,
                    whisper_wrong_word=wrong_word,
                    predicted_word=predicted,
                    correct=correct,
                    n_candidates=n_cand,
                    latency_ms=latency_ms,
                )
            )
        if (i + 1) % 5 == 0:
            print(f"  [{i+1}/{len(candidates_pool)}] processed...")

    print(f"\nSkipped (no clean single-word substitution found): {skipped_no_substitution}")

    summary = {}
    for condition in ("slow", "syllable"):
        cond_attempts = [a for a in attempts if a.condition == condition]
        n = len(cond_attempts)
        n_correct = sum(1 for a in cond_attempts if a.correct)
        avg_latency = sum(a.latency_ms for a in cond_attempts) / n if n else 0.0
        summary[condition] = {
            "n_attempts": n,
            "n_correct": n_correct,
            "correction_accuracy": (n_correct / n) if n else None,
            "avg_latency_ms": avg_latency,
        }

    print("\n=== Correction evaluation results (REAL Whisper + real correction engine, TTS-synthesized re-pronunciation PROXY — see script docstring) ===")
    for condition, s in summary.items():
        acc_str = f"{s['correction_accuracy']:.3f}" if s["correction_accuracy"] is not None else "N/A"
        print(f"{condition}: n={s['n_attempts']} correct={s['n_correct']} accuracy={acc_str} avg_latency={s['avg_latency_ms']:.1f}ms")

    if args.use_mlflow:
        import mlflow

        mlflow.set_experiment(args.mlflow_experiment)
        with mlflow.start_run(run_name=f"correction-eval-{args.split_name}"):
            mlflow.log_params(
                {
                    "split_name": args.split_name,
                    "dataset_id": splits["dataset_id"],
                    "source_manifest_sha256": splits["source_manifest_sha256"],
                    "n_error_samples_in_split": len(candidates_pool),
                    "n_skipped_no_substitution": skipped_no_substitution,
                    "whisper_model_size": settings.whisper_model_size,
                    "repronunciation_source": "gTTS-synthesized PROXY, not real human re-pronunciation",
                }
            )
            for condition, s in summary.items():
                mlflow.log_metrics(
                    {
                        f"{condition}_n_attempts": s["n_attempts"],
                        f"{condition}_correction_accuracy": s["correction_accuracy"] or 0.0,
                        f"{condition}_avg_latency_ms": s["avg_latency_ms"],
                    }
                )
            print(f"Logged to MLflow experiment '{args.mlflow_experiment}'")

    if args.dump_per_sample:
        args.dump_per_sample.parent.mkdir(parents=True, exist_ok=True)
        with args.dump_per_sample.open("w", encoding="utf-8") as f:
            json.dump(
                {"summary": summary, "attempts": [a.__dict__ for a in attempts], "skipped_no_substitution": skipped_no_substitution},
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"Wrote detailed results to {args.dump_per_sample}")


if __name__ == "__main__":
    main()
