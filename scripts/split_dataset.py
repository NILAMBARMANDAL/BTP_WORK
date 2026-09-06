"""Speaker-disjoint train/validation/test split of a dataset manifest.

Why this exists: `data/processed/openslr_53_shard0_manifest.json` (built by
build_manifest.py) is a single undivided 200-sample pool. Splitting it
naively (e.g. shuffle-and-cut on samples) would let the same speaker appear
in both the training-side pool and the held-out evaluation pool, which is a
data-leakage risk for anything that could pick up speaker-specific acoustic
traits rather than genuine transcription/correction quality. See
PROGRESS.md "Next steps" #1 and EXPERIMENTS.md/DATA_PIPELINE.md "Data
leakage protection".

Method: group samples by speaker_id, then greedily assign whole speakers
(largest speaker-group first) to whichever split is furthest below its
target share of samples. This keeps every speaker entirely within one split
while getting close to the requested ratios (exact ratios aren't always
achievable with lumpy per-speaker sample counts, which is why the resulting
counts are printed and written into the output for transparency instead of
being asserted to match the ratio exactly).

Usage (from repo root):
    python scripts/split_dataset.py \
        --manifest data/processed/openslr_53_shard0_manifest.json \
        --train 0.7 --val 0.15 --test 0.15 --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=None, help="Defaults to <manifest_dir>/<dataset_id>_splits.json")
    parser.add_argument("--train", type=float, default=0.7)
    parser.add_argument("--val", type=float, default=0.15)
    parser.add_argument("--test", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    ratios = {"train": args.train, "val": args.val, "test": args.test}
    total_ratio = sum(ratios.values())
    if abs(total_ratio - 1.0) > 1e-6:
        raise SystemExit(f"--train/--val/--test must sum to 1.0, got {total_ratio}")

    with args.manifest.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    samples = manifest["samples"]
    by_speaker: dict[str, list[dict]] = defaultdict(list)
    for s in samples:
        by_speaker[s["speaker_id"]].append(s)

    speaker_groups = list(by_speaker.values())
    rng = random.Random(args.seed)
    rng.shuffle(speaker_groups)
    # Largest-first bin-packing gives a closer match to target ratios than
    # pure shuffle order, while shuffle breaks ties / any incidental ordering
    # in the source manifest.
    speaker_groups.sort(key=len, reverse=True)

    n_total = len(samples)
    targets = {k: v * n_total for k, v in ratios.items()}
    assigned_counts = {k: 0 for k in ratios}
    split_utt_ids: dict[str, list[str]] = {k: [] for k in ratios}
    split_speakers: dict[str, list[str]] = {k: [] for k in ratios}

    for group in speaker_groups:
        # Assign this whole speaker to whichever split is furthest below its target.
        deficits = {k: targets[k] - assigned_counts[k] for k in ratios}
        chosen = max(deficits, key=deficits.get)
        split_utt_ids[chosen].extend(s["utt_id"] for s in group)
        split_speakers[chosen].append(group[0]["speaker_id"])
        assigned_counts[chosen] += len(group)

    # Sanity check: no speaker in more than one split.
    seen_speakers: dict[str, str] = {}
    for split_name, speaker_ids in split_speakers.items():
        for sp in speaker_ids:
            assert sp not in seen_speakers, f"speaker {sp} leaked into both {seen_speakers[sp]} and {split_name}"
            seen_speakers[sp] = split_name

    out_path = args.out or args.manifest.parent / f"{manifest['dataset_id']}_splits.json"
    output = {
        "dataset_id": manifest["dataset_id"],
        "source_manifest": str(args.manifest),
        "source_manifest_sha256": manifest["manifest_sha256"],
        "split_method": "speaker-disjoint greedy bin-packing (largest speaker group first) to approximate requested ratios; see script docstring",
        "requested_ratios": ratios,
        "seed": args.seed,
        "n_total_samples": n_total,
        "n_total_speakers": len(speaker_groups),
        "splits": {
            name: {
                "n_samples": len(utt_ids),
                "n_speakers": len(split_speakers[name]),
                "actual_ratio": round(len(utt_ids) / n_total, 4),
                "utt_ids": sorted(utt_ids),
                "speaker_ids": sorted(split_speakers[name]),
            }
            for name, utt_ids in split_utt_ids.items()
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Wrote speaker-disjoint split to {out_path}")
    for name, info in output["splits"].items():
        print(f"  {name}: {info['n_samples']} samples ({info['actual_ratio']:.1%}), {info['n_speakers']} speakers")


if __name__ == "__main__":
    main()
