"""ZenML pipeline: dataset ingestion -> speaker-disjoint split -> Whisper
baseline evaluation -> error-category analysis -> correction-method
evaluation (Experiments A/B/C).

Every parameter here has a plain default matching what EXPERIMENTS.md
documents as the official 200-sample / seed-42 run, but nothing is
hardcoded: pass different values (a bigger `max_samples`, a different
manifest, a different `--split-name`) to run this over more data without
touching this file or any step, per spec section 44 (data growth without
code rewrites).

Usage (from the REPO ROOT, with ml-service/venv active — this package needs
zenml/mlflow/etc. from that venv but must run with repo root on sys.path,
after `zenml init` has been run once at the repo root):
    python -m pipelines.evaluation_pipeline
    python -m pipelines.evaluation_pipeline --max-samples 8 --smoke   # smoke run, separate artifacts/MLflow experiments
"""

from __future__ import annotations

import argparse

from zenml import pipeline

from pipelines.steps import (
    baseline_eval_step,
    correction_eval_step,
    error_analysis_step,
    ingest_dataset_step,
    split_dataset_step,
)


@pipeline
def bengali_asr_evaluation_pipeline(
    tsv_path: str = "data/raw/openslr_53/utt_spk_text.tsv",
    shard_url: str = "https://www.openslr.org/resources/53/asr_bengali_0.zip",
    extract_to: str = "data/raw/openslr_53/audio",
    out_manifest: str = "data/processed/openslr_53_shard0_manifest.json",
    max_samples: int = 200,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
    n_baseline_samples: int = 200,
    use_mlflow: bool = True,
    correction_split_name: str = "test",
    baseline_dump_per_sample: str = "../data/processed/baseline_per_sample.json",
    baseline_mlflow_experiment: str = "bengali-asr-baseline",
    correction_mlflow_experiment: str = "bengali-asr-correction",
    correction_dump_per_sample: str | None = None,
) -> None:
    manifest_path = ingest_dataset_step(
        tsv_path=tsv_path,
        shard_url=shard_url,
        extract_to=extract_to,
        out_manifest=out_manifest,
        max_samples=max_samples,
        seed=seed,
    )
    splits_path = split_dataset_step(
        manifest_path=manifest_path,
        train=train_ratio,
        val=val_ratio,
        test=test_ratio,
        seed=seed,
    )
    per_sample_path = baseline_eval_step(
        manifest_path=manifest_path,
        n_samples=n_baseline_samples,
        seed=seed,
        use_mlflow=use_mlflow,
        mlflow_experiment=baseline_mlflow_experiment,
        dump_per_sample=baseline_dump_per_sample,
    )
    error_analysis_step(per_sample_path=per_sample_path, tsv_path=tsv_path)
    correction_eval_step(
        splits_path=splits_path,
        per_sample_path=per_sample_path,
        split_name=correction_split_name,
        use_mlflow=use_mlflow,
        mlflow_experiment=correction_mlflow_experiment,
        dump_per_sample=correction_dump_per_sample,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-samples", type=int, default=200, help="Dataset ingestion size (spec section 44: change this, not the code, to scale up)")
    parser.add_argument("--n-samples", type=int, default=None, help="Baseline eval sample count; defaults to --max-samples")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--split-name", default="test", choices=["train", "val", "test"])
    parser.add_argument("--no-mlflow", action="store_true")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Write to separate _pipeline_smoke_* artifact paths and MLflow experiment names, "
        "so a small validation run of the pipeline mechanics never overwrites the official "
        "EXPERIMENTS.md-documented Experiment A/B/C artifacts.",
    )
    args = parser.parse_args()

    kwargs = dict(
        max_samples=args.max_samples,
        n_baseline_samples=args.n_samples if args.n_samples is not None else args.max_samples,
        seed=args.seed,
        use_mlflow=not args.no_mlflow,
        correction_split_name=args.split_name,
    )
    if args.smoke:
        kwargs.update(
            baseline_dump_per_sample="../data/processed/_pipeline_smoke_baseline_per_sample.json",
            baseline_mlflow_experiment="bengali-asr-baseline-pipeline-smoke",
            correction_mlflow_experiment="bengali-asr-correction-pipeline-smoke",
            correction_dump_per_sample="../data/processed/_pipeline_smoke_correction_eval.json",
        )

    bengali_asr_evaluation_pipeline(**kwargs)


if __name__ == "__main__":
    main()
