"""ZenML steps that orchestrate the repo's already-validated, standalone
evaluation scripts (`scripts/build_manifest.py`, `scripts/split_dataset.py`,
`ml-service/scripts/run_baseline_eval.py`,
`ml-service/scripts/analyze_baseline_errors.py`,
`ml-service/scripts/run_correction_eval.py`).

Design choice, documented rather than silent: steps that wrap a script whose
core logic lives inline in `main()` (ingest, split, baseline eval, correction
eval) invoke that script via `subprocess` with the *same* Python interpreter
running the pipeline, rather than re-implementing or importing partially
extracted logic. This means there is exactly one place each algorithm lives
(the already-tested script), and the pipeline cannot silently drift from what
`EXPERIMENTS.md` documents as reproducible via direct script invocation. The
error-analysis step is the one exception: `analyze_baseline_errors.py`
already exposes its core logic as plain functions (`load_word_frequencies`,
`bucket_stats`), so that step imports them directly instead of parsing
stdout.

Every step is configuration-driven (paths, sample counts, ratios, seeds are
step parameters, never hardcoded) per the project's data-growth requirement
(spec section 44) — pointing these parameters at a larger manifest/shard is
the only change needed to run this pipeline over more data.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

from zenml import step

REPO_ROOT = Path(__file__).resolve().parent.parent
ML_SERVICE_DIR = REPO_ROOT / "ml-service"
PYTHON = sys.executable


def _resolve(path_str: str) -> Path:
    """Resolves a possibly-relative path against REPO_ROOT — steps run
    in-process (not via subprocess with a fixed cwd), so a relative path is
    ambiguous unless anchored explicitly rather than trusting whatever cwd
    the pipeline happened to be launched from."""
    p = Path(path_str)
    return p if p.is_absolute() else (REPO_ROOT / p)


def _run(cmd: list[str], cwd: Path) -> None:
    print(f"[pipeline] running: {' '.join(cmd)} (cwd={cwd})")
    result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8")
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError(f"step subprocess failed (exit {result.returncode}): {' '.join(cmd)}")


@step
def ingest_dataset_step(
    tsv_path: str,
    shard_url: str,
    extract_to: str,
    out_manifest: str,
    max_samples: int = 200,
    seed: int = 42,
    skip_if_exists: bool = True,
) -> str:
    """Builds (or reuses) a dataset manifest. Returns the manifest path.

    `skip_if_exists=True` by default: re-running `build_manifest.py`
    re-fetches audio over the network, which is wasteful (spec section 36)
    and non-deterministic to re-verify byte-for-byte, so an existing manifest
    at `out_manifest` is trusted as-is unless the caller explicitly wants a
    fresh build (e.g. after raising `max_samples`).
    """
    manifest_path = REPO_ROOT / out_manifest
    if skip_if_exists and manifest_path.exists():
        print(f"[pipeline] manifest already exists at {manifest_path}, skipping ingest (skip_if_exists=True)")
        return str(manifest_path)

    _run(
        [
            PYTHON,
            "scripts/build_manifest.py",
            "--tsv", tsv_path,
            "--shard-url", shard_url,
            "--extract-to", extract_to,
            "--out", out_manifest,
            "--max-samples", str(max_samples),
            "--seed", str(seed),
        ],
        cwd=REPO_ROOT,
    )
    if not manifest_path.exists():
        raise RuntimeError(f"build_manifest.py reported success but {manifest_path} does not exist")
    return str(manifest_path)


@step
def split_dataset_step(
    manifest_path: str,
    train: float = 0.7,
    val: float = 0.15,
    test: float = 0.15,
    seed: int = 42,
    skip_if_exists: bool = True,
) -> str:
    """Speaker-disjoint train/val/test split. Returns the splits JSON path."""
    with open(manifest_path, "r", encoding="utf-8") as f:
        dataset_id = json.load(f)["dataset_id"]
    out_path = Path(manifest_path).parent / f"{dataset_id}_splits.json"

    if skip_if_exists and out_path.exists():
        print(f"[pipeline] splits already exist at {out_path}, skipping split (skip_if_exists=True)")
        return str(out_path)

    _run(
        [
            PYTHON,
            "scripts/split_dataset.py",
            "--manifest", manifest_path,
            "--train", str(train),
            "--val", str(val),
            "--test", str(test),
            "--seed", str(seed),
        ],
        cwd=REPO_ROOT,
    )
    return str(out_path)


@step
def baseline_eval_step(
    manifest_path: str,
    n_samples: int = 200,
    seed: int = 42,
    use_mlflow: bool = True,
    mlflow_experiment: str = "bengali-asr-baseline",
    dump_per_sample: str = "../data/processed/baseline_per_sample.json",
) -> str:
    """Runs the real Whisper baseline eval. Returns the per-sample dump path.

    NOT cached-skip-if-exists like the steps above: this is the expensive
    real-inference step, and re-running it is a deliberate choice the caller
    makes via `n_samples` (e.g. a small smoke run vs. the full manifest) —
    silently reusing a stale dump here risks reporting last run's numbers
    under new pipeline parameters.
    """
    args = [
        PYTHON,
        "scripts/run_baseline_eval.py",
        "--manifest", manifest_path,
        "--n-samples", str(n_samples),
        "--seed", str(seed),
        "--dump-per-sample", dump_per_sample,
    ]
    if use_mlflow:
        args += ["--use-mlflow", "--mlflow-experiment", mlflow_experiment]
    _run(args, cwd=ML_SERVICE_DIR)

    per_sample_path = ML_SERVICE_DIR / dump_per_sample
    if not per_sample_path.exists():
        raise RuntimeError(f"run_baseline_eval.py reported success but {per_sample_path} does not exist")
    return str(per_sample_path)


@step
def error_analysis_step(
    per_sample_path: str,
    tsv_path: str,
    rare_word_threshold: int = 5,
) -> dict:
    """Real error-category correlation (speech rate, rare-word presence) —
    imports `analyze_baseline_errors`'s pure functions directly rather than
    subprocessing, since they're already free of CLI/argparse coupling."""
    sys.path.insert(0, str(ML_SERVICE_DIR / "scripts"))
    from analyze_baseline_errors import bucket_stats, load_word_frequencies  # noqa: PLC0415

    with open(per_sample_path, "r", encoding="utf-8") as f:
        samples = json.load(f)
    if not samples:
        return {"error": "no per-sample results to analyze"}

    freq = load_word_frequencies(_resolve(tsv_path))
    for s in samples:
        word_count = len(s["reference"].split())
        s["words_per_second"] = word_count / s["audio_duration_s"] if s["audio_duration_s"] > 0 else 0.0
        s["has_rare_word"] = any(freq.get(w, 0) <= rare_word_threshold for w in s["reference"].split())

    rates = sorted(s["words_per_second"] for s in samples)
    tercile_1 = rates[len(rates) // 3]
    tercile_2 = rates[2 * len(rates) // 3]

    def rate_bucket(wps: float) -> str:
        if wps <= tercile_1:
            return "slow"
        if wps <= tercile_2:
            return "normal"
        return "fast"

    by_rate: dict[str, list[float]] = {"slow": [], "normal": [], "fast": []}
    by_rarity: dict[str, list[float]] = {"has_rare_word": [], "no_rare_word": []}
    for s in samples:
        by_rate[rate_bucket(s["words_per_second"])].append(s["cer"])
        by_rarity["has_rare_word" if s["has_rare_word"] else "no_rare_word"].append(s["cer"])

    return {
        "n_samples": len(samples),
        "by_speech_rate": bucket_stats(by_rate),
        "by_rare_word_presence": bucket_stats(by_rarity),
        "note": "single-draw, observational, not significance-tested — see EXPERIMENTS.md",
    }


@step
def correction_eval_step(
    splits_path: str,
    per_sample_path: str,
    split_name: str = "test",
    use_mlflow: bool = True,
    mlflow_experiment: str = "bengali-asr-correction",
    dump_per_sample: Optional[str] = None,
) -> dict:
    """Experiments B/C (slow vs. syllable correction, gTTS proxy — see
    `EXPERIMENTS.md`). Returns the summary dict; also prints full stdout."""
    dump_path = dump_per_sample or "../data/processed/_pipeline_correction_eval.json"
    args = [
        PYTHON,
        "scripts/run_correction_eval.py",
        "--splits", splits_path,
        "--per-sample", per_sample_path,
        "--split-name", split_name,
        "--dump-per-sample", dump_path,
    ]
    if use_mlflow:
        args += ["--use-mlflow", "--mlflow-experiment", mlflow_experiment]
    _run(args, cwd=ML_SERVICE_DIR)

    result_path = ML_SERVICE_DIR / dump_path
    with result_path.open("r", encoding="utf-8") as f:
        return json.load(f)["summary"]
