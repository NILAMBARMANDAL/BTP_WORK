"""Runs the real Whisper baseline (Experiment A, EXPERIMENTS.md) against a
dataset manifest (scripts/build_manifest.py at repo root) and reports actual
measured WER/CER — logged to MLflow if available.

This computes real numbers from real Whisper inference on real downloaded
audio. It does NOT fabricate results — if it can't run (missing manifest,
missing audio files), it fails loudly rather than printing placeholder
numbers.

Usage (from ml-service/, with venv active):
    python scripts/run_baseline_eval.py \
        --manifest ../data/processed/openslr_53_shard0_manifest.json \
        --n-samples 100 \
        --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

# Allow running as `python scripts/run_baseline_eval.py` from ml-service/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os

if sys.platform == "win32":
    import torch

    torch_lib_dir = Path(torch.__file__).parent / "lib"
    if torch_lib_dir.is_dir():
        os.add_dll_directory(str(torch_lib_dir))

from audio.preprocessing import load_and_preprocess
from evaluation.metrics import compute_error_rates, normalize_transcript
from utils.config import settings
from whisper.engine import transcribe


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--n-samples", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent.parent.parent)
    parser.add_argument("--use-mlflow", action="store_true")
    parser.add_argument("--mlflow-experiment", default="bengali-asr-baseline")
    parser.add_argument(
        "--dump-per-sample",
        type=Path,
        default=None,
        help="Write per-sample reference/hypothesis/CER/WER/duration/speaker_id to this JSON path, "
        "so a downstream error-category analysis doesn't need to re-run expensive inference.",
    )
    args = parser.parse_args()

    with args.manifest.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    all_samples = manifest["samples"]
    rng = random.Random(args.seed)
    n = min(args.n_samples, len(all_samples))
    sampled = rng.sample(all_samples, n)
    print(f"Evaluating {n} / {len(all_samples)} samples from manifest {args.manifest}")
    print(f"Manifest dataset_id={manifest['dataset_id']} license={manifest['license']} manifest_sha256={manifest['manifest_sha256'][:12]}...")

    references, hypotheses, latencies_ms, skipped = [], [], [], 0
    per_sample = []

    for i, sample in enumerate(sampled):
        audio_path = args.repo_root / sample["audio_path"]
        if not audio_path.exists():
            skipped += 1
            continue

        start = time.time()
        try:
            pre = load_and_preprocess(str(audio_path))
            result = transcribe(pre.audio, pre.sample_rate)
        except Exception as exc:  # noqa: BLE001 — record and continue, don't fabricate a result for this sample
            print(f"  [{i+1}/{n}] FAILED on {sample['utt_id']}: {exc}")
            skipped += 1
            continue
        latency_ms = (time.time() - start) * 1000
        latencies_ms.append(latency_ms)

        references.append(sample["transcript"])
        hypotheses.append(result.text)

        if args.dump_per_sample:
            sample_rates = compute_error_rates([sample["transcript"]], [result.text], normalize=True)
            per_sample.append(
                {
                    "utt_id": sample["utt_id"],
                    "speaker_id": sample["speaker_id"],
                    "reference": sample["transcript"],
                    "hypothesis": result.text,
                    "wer": sample_rates.wer,
                    "cer": sample_rates.cer,
                    "audio_duration_s": len(pre.audio) / pre.sample_rate,
                    "latency_ms": latency_ms,
                }
            )

        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{n}] processed...")

    if not references:
        print("No samples were successfully transcribed — cannot compute error rates.")
        sys.exit(1)

    error_rates = compute_error_rates(references, hypotheses, normalize=True)
    error_rates_raw = compute_error_rates(references, hypotheses, normalize=False)
    avg_latency = sum(latencies_ms) / len(latencies_ms)

    print("\n=== Baseline evaluation results (REAL measured values) ===")
    print(f"Samples evaluated: {error_rates.n_samples} (skipped: {skipped})")
    print(f"WER (normalized): {error_rates.wer:.4f}  |  WER (raw): {error_rates_raw.wer:.4f}")
    print(f"CER (normalized): {error_rates.cer:.4f}  |  CER (raw): {error_rates_raw.cer:.4f}")
    print(f"Avg latency: {avg_latency:.1f} ms/sample")
    print(f"Model: {settings.whisper_model_size} ({settings.whisper_compute_type}, {settings.whisper_device})")

    if args.use_mlflow:
        import mlflow

        mlflow.set_experiment(args.mlflow_experiment)
        with mlflow.start_run(run_name=f"baseline-{settings.whisper_model_size}"):
            mlflow.log_params(
                {
                    "whisper_model_size": settings.whisper_model_size,
                    "whisper_compute_type": settings.whisper_compute_type,
                    "whisper_device": settings.whisper_device,
                    "whisper_beam_size": settings.whisper_beam_size,
                    "dataset_id": manifest["dataset_id"],
                    "dataset_license": manifest["license"],
                    "manifest_sha256": manifest["manifest_sha256"],
                    "n_samples_requested": args.n_samples,
                    "n_samples_evaluated": error_rates.n_samples,
                    "n_samples_skipped": skipped,
                    "seed": args.seed,
                }
            )
            mlflow.log_metrics(
                {
                    "wer": error_rates.wer,
                    "cer": error_rates.cer,
                    "wer_raw": error_rates_raw.wer,
                    "cer_raw": error_rates_raw.cer,
                    "avg_latency_ms": avg_latency,
                }
            )
            mlflow.log_dict(manifest, "manifest.json")
            print(f"Logged to MLflow experiment '{args.mlflow_experiment}'")

    if args.dump_per_sample:
        args.dump_per_sample.parent.mkdir(parents=True, exist_ok=True)
        with args.dump_per_sample.open("w", encoding="utf-8") as f:
            json.dump(per_sample, f, ensure_ascii=False, indent=2)
        print(f"Wrote {len(per_sample)} per-sample results to {args.dump_per_sample}")


if __name__ == "__main__":
    main()
