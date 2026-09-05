"""Data-driven Whisper error-category analysis (DATA_PIPELINE.md /
EXPERIMENTS.md: "identify actual Whisper errors... analyze what types of
errors occur... do not assume these categories are important until supported
by the data").

Consumes the --dump-per-sample output of run_baseline_eval.py (real
per-sample WER/CER/duration from real Whisper inference — nothing re-derived
or invented here) and correlates error rate with two categories that are
actually measurable from what OpenSLR SLR53 gives us:

  - speech rate (words / second, derived from audio duration) — OpenSLR
    doesn't label speech rate, but duration and word count are real, so this
    is a real derived signal, not an assumption.
  - rare-word presence, using word frequency counted directly from the full
    218,703-line utt_spk_text.tsv as the frequency reference (not an external
    corpus, and not invented weights).

Categories NOT analyzed here (proper nouns, place names, noise, dialect):
OpenSLR SLR53's TSV has no such labels, and inventing them would violate the
project's "don't assume categories matter without data support" rule. If
those turn out to matter, a labeled subset would need to be built first.

Usage (from ml-service/, with venv active):
    python scripts/analyze_baseline_errors.py \
        --per-sample ../data/processed/baseline_per_sample.json \
        --tsv ../data/raw/openslr_53/utt_spk_text.tsv
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path


def load_word_frequencies(tsv_path: Path) -> Counter:
    freq = Counter()
    with tsv_path.open("r", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3:
                continue
            freq.update(parts[2].split())
    return freq


def bucket_stats(label_to_values: dict[str, list[float]]) -> dict:
    return {
        label: {
            "n": len(values),
            "mean_cer": round(statistics.mean(values), 4) if values else None,
        }
        for label, values in label_to_values.items()
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-sample", required=True, type=Path)
    parser.add_argument("--tsv", required=True, type=Path)
    parser.add_argument("--rare-word-threshold", type=int, default=5, help="Words occurring <= this many times in the TSV are 'rare'.")
    args = parser.parse_args()

    with args.per_sample.open("r", encoding="utf-8") as f:
        samples = json.load(f)
    if not samples:
        print("No per-sample results to analyze.")
        return

    print(f"Loading word frequencies from {args.tsv} (this is the ONLY frequency reference used — no external corpus)...")
    freq = load_word_frequencies(args.tsv)
    print(f"{len(freq)} unique word types across the full TSV.\n")

    # --- Speech rate ---
    for s in samples:
        word_count = len(s["reference"].split())
        s["words_per_second"] = word_count / s["audio_duration_s"] if s["audio_duration_s"] > 0 else 0.0
        s["has_rare_word"] = any(freq.get(w, 0) <= args.rare_word_threshold for w in s["reference"].split())

    rates = sorted(s["words_per_second"] for s in samples)
    tercile_1 = rates[len(rates) // 3]
    tercile_2 = rates[2 * len(rates) // 3]

    def rate_bucket(wps: float) -> str:
        if wps <= tercile_1:
            return "slow"
        if wps <= tercile_2:
            return "normal"
        return "fast"

    by_rate = {"slow": [], "normal": [], "fast": []}
    by_rarity = {"has_rare_word": [], "no_rare_word": []}

    for s in samples:
        by_rate[rate_bucket(s["words_per_second"])].append(s["cer"])
        by_rarity["has_rare_word" if s["has_rare_word"] else "no_rare_word"].append(s["cer"])

    print("=== Speech rate vs. CER (terciles of words/second, this sample only) ===")
    print(json.dumps(bucket_stats(by_rate), indent=2, ensure_ascii=False))

    print(f"\n=== Rare-word presence (word freq <= {args.rare_word_threshold} in full TSV) vs. CER ===")
    print(json.dumps(bucket_stats(by_rarity), indent=2, ensure_ascii=False))

    print(f"\nOverall mean CER: {statistics.mean(s['cer'] for s in samples):.4f} (n={len(samples)})")
    print(
        "\nNote: this is a single 200-sample draw from one OpenSLR SLR53 shard — differences here are "
        "observational, not statistically tested (no significance test run), and must not be reported "
        "as a validated finding without a larger/repeated sample. See EXPERIMENTS.md."
    )


if __name__ == "__main__":
    main()
