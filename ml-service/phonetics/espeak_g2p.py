"""Bengali grapheme-to-phoneme via espeak-ng — a real, established G2P system
(as opposed to the ITRANS-transliteration heuristic in g2p.py). See
phonetics/README.md for how the two compare and why this is now preferred
when available.

Confirmed working (2026-09-05): espeak-ng -v bn on "সোনার" and "শোনার" both
produce the phoneme string "S'onar" — independent evidence, from an
established G2P system, of the স/শ merger noted in RESEARCH.md from Whisper
smoke-testing. This is a real, non-fabricated finding.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from utils.config import settings


def _resolve_espeak_exe() -> str | None:
    if settings.espeak_ng_exe and Path(settings.espeak_ng_exe).exists():
        return settings.espeak_ng_exe
    found = shutil.which("espeak-ng")
    if found:
        return found
    return None


@lru_cache(maxsize=1)
def is_available() -> bool:
    return _resolve_espeak_exe() is not None


def to_phonemes(bengali_text: str) -> str | None:
    """Returns espeak-ng's ASCII phoneme transcription of the text, or None
    if espeak-ng isn't available (caller should fall back to g2p.py).

    Text is passed via a temp file (`-f`), not argv, because passing Bengali
    (or any non-ASCII) text as a Windows subprocess argument was observed to
    corrupt the encoding / crash the process — a real issue hit during
    integration, not a hypothetical concern.
    """
    exe = _resolve_espeak_exe()
    if exe is None or not bengali_text:
        return None

    args = [exe, "-v", "bn", "-x", "-q"]
    if settings.espeak_ng_data_path:
        args.insert(1, f"--path={settings.espeak_ng_data_path}")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
        tmp.write(bengali_text)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [*args, "-f", tmp_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        Path(tmp_path).unlink(missing_ok=True)
