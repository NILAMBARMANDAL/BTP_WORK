"""Fast unit tests for scripts/analyze_baseline_errors.py's pure helper
functions (no GPU/model loading, no real dataset needed)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from analyze_baseline_errors import bucket_stats, load_word_frequencies  # noqa: E402


def test_load_word_frequencies_counts_tokens(tmp_path):
    tsv = tmp_path / "utt_spk_text.tsv"
    tsv.write_text(
        "u1\tspk1\tআমার সোনার বাংলা\n"
        "u2\tspk2\tআমার নাম রহিম\n"
        "malformed line without tabs\n",
        encoding="utf-8",
    )
    freq = load_word_frequencies(tsv)
    assert freq["আমার"] == 2
    assert freq["সোনার"] == 1
    assert freq["নাম"] == 1


def test_bucket_stats_computes_mean_cer_per_label():
    result = bucket_stats({"slow": [0.1, 0.3], "fast": [], "normal": [0.2]})
    assert result["slow"] == {"n": 2, "mean_cer": 0.2}
    assert result["fast"] == {"n": 0, "mean_cer": None}
    assert result["normal"] == {"n": 1, "mean_cer": 0.2}
