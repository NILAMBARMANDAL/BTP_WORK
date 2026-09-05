"""Builds a versioned dataset manifest by fetching a scientifically-defensible
SUBSET of an OpenSLR SLR53 shard directly over HTTP range requests — not by
downloading the full ~900MB shard. Uses `remotezip` (pip install remotezip)
to read the remote zip's central directory and extract only the specific
audio files we sample, confirmed working against the real openslr.org server
(which advertises `Accept-Ranges: bytes`).

Per DATA_PIPELINE.md's "versioning strategy": rather than introducing DVC for
a small subset, we record a JSON manifest (checked into data/processed/, NOT
the audio itself) pinning exactly which utterance IDs, transcripts, and
source shard this evaluation run used, so any experiment result can point at
an exact manifest and be reproduced.

Usage (from repo root, ml-service venv):
    ./ml-service/venv/Scripts/python.exe scripts/build_manifest.py \
        --tsv data/raw/openslr_53/utt_spk_text.tsv \
        --shard-url https://www.openslr.org/resources/53/asr_bengali_0.zip \
        --extract-to data/raw/openslr_53/audio \
        --out data/processed/openslr_53_shard0_manifest.json \
        --max-samples 200 --seed 42
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from remotezip import RemoteZip


def extract_with_retry(shard_url, entry_name, extract_to, attempts=4, backoff_seconds=2.0):
    """Remote range requests over a flaky connection occasionally get reset
    (observed in practice against openslr.org — not hypothetical). A fresh
    RemoteZip connection is opened per retry, since a socket that already
    errored mid-read is not safely reusable. Retrying a handful of times with
    backoff is enough to get past transient resets without silently losing
    samples."""
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            with RemoteZip(shard_url) as zf:
                zf.extract(entry_name, path=extract_to)
            return True
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(backoff_seconds * attempt)
    print(f"  GIVING UP on {entry_name} after {attempts} attempts: {last_exc}")
    return False


def load_transcripts(tsv_path: Path) -> dict[str, dict]:
    transcripts = {}
    with tsv_path.open("r", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3:
                continue
            utt_id, speaker_id, text = parts
            transcripts[utt_id] = {"speaker_id": speaker_id, "text": text}
    return transcripts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tsv", required=True, type=Path)
    parser.add_argument("--shard-url", required=True)
    parser.add_argument("--extract-to", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--max-samples", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dataset-id", default="openslr_53")
    parser.add_argument("--license", default="CC-BY-SA-4.0")
    parser.add_argument("--source-url", default="https://www.openslr.org/53/")
    args = parser.parse_args()

    transcripts = load_transcripts(args.tsv)
    print(f"Loaded {len(transcripts)} transcripts from {args.tsv}")

    args.extract_to.mkdir(parents=True, exist_ok=True)

    with RemoteZip(args.shard_url) as zf:
        names = zf.namelist()
        flac_entries = [n for n in names if n.endswith(".flac")]
        print(f"Remote shard has {len(flac_entries)} audio files (fetched listing without downloading the shard)")

        # Map utt_id -> zip entry name, restricted to utt_ids we have a transcript for.
        available = {}
        for entry in flac_entries:
            utt_id = Path(entry).stem
            if utt_id in transcripts:
                available[utt_id] = entry

        print(f"{len(available)} of those have a matching transcript in this TSV")

        rng = random.Random(args.seed)
        chosen_ids = rng.sample(list(available.keys()), min(args.max_samples, len(available)))

        samples = []
        for i, utt_id in enumerate(chosen_ids):
            entry_name = available[utt_id]
            zf.extract(entry_name, path=args.extract_to)
            extracted_path = args.extract_to / entry_name
            samples.append(
                {
                    "utt_id": utt_id,
                    "speaker_id": transcripts[utt_id]["speaker_id"],
                    "transcript": transcripts[utt_id]["text"],
                    # Stored as given on the CLI (--extract-to), which callers
                    # pass relative to the repo root — NOT re-rooted via
                    # relative_to(), which previously dropped the "data/raw/"
                    # prefix and silently pointed at nonexistent paths.
                    "audio_path": str(extracted_path).replace("\\", "/"),
                }
            )
            if (i + 1) % 25 == 0:
                print(f"  fetched {i + 1}/{len(chosen_ids)}...")

    # We deliberately do NOT download the full ~900MB shard, so we cannot hash
    # it. Instead we hash the exact sampled (utt_id, transcript, audio_path)
    # triples: this pins the exact 200-sample selection any experiment result
    # can be traced back to, per DATA_PIPELINE.md's versioning strategy,
    # without requiring a full-shard download just to compute a checksum.
    selection_digest = hashlib.sha256(
        json.dumps(
            [(s["utt_id"], s["transcript"], s["audio_path"]) for s in samples],
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    manifest = {
        "dataset_id": args.dataset_id,
        "license": args.license,
        "source_url": args.source_url,
        "shard_url": args.shard_url,
        "acquisition_method": "remotezip partial extraction (HTTP range requests) — full shard was NOT downloaded",
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "role": "stage1_baseline_eval_pool",
        "seed": args.seed,
        "manifest_sha256": selection_digest,
        "manifest_sha256_note": "sha256 of the sampled (utt_id, transcript, audio_path) selection, NOT of the full remote shard (which was never downloaded) — pins the exact sample set, not the shard's byte content",
        "counts": {
            "total_transcripts_in_tsv": len(transcripts),
            "audio_files_in_shard": len(flac_entries),
            "available_in_shard_with_transcript": len(available),
            "sampled": len(samples),
        },
        "samples": samples,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\nWrote manifest with {len(samples)} samples to {args.out}")
    print(f"manifest_sha256={selection_digest}")


if __name__ == "__main__":
    main()
