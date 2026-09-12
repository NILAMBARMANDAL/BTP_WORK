"""Central configuration, loaded from environment variables.

Every experimentally-relevant knob (model size, device, compute type, decoding
params, preprocessing toggles, ranking weights) lives here — never hardcoded
inline in the modules that use them. See RESEARCH.md / ARCHITECTURE.md.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Whisper (faster-whisper) ---
    # See GPU_SETUP.md "Model size findings": small/medium observed to output
    # wrong-script transliteration for Bengali; large-v3 int8 does not, and
    # fits a 4GB GPU. Override via env for experiments comparing model sizes.
    whisper_model_size: str = "large-v3"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "int8_float16"
    whisper_language: str = "bn"
    whisper_beam_size: int = 5

    # --- Audio preprocessing toggles ---
    preproc_resample: bool = True
    preproc_target_sr: int = 16000
    preproc_mono: bool = True
    preproc_trim_silence: bool = False
    preproc_vad: bool = False
    preproc_normalize: bool = False
    preproc_denoise: bool = False

    # --- Phonetics ---
    # Path to an espeak-ng executable. Empty string = not configured, in which
    # case phonetics/similarity.py falls back to shutil.which("espeak-ng")
    # (works out of the box on Linux/Docker after `apt-get install espeak-ng`),
    # and if that also fails, falls back further to the ITRANS+Levenshtein
    # heuristic (see phonetics/README.md). On Windows, run
    # scripts/setup_espeak.ps1 and point this at the extracted .exe.
    espeak_ng_exe: str = ""
    espeak_ng_data_path: str = ""

    # --- Semantics (Mode B: pronunciation + meaning/context) ---
    # LaBSE (Google, Apache-2.0) is used because its model card confirms
    # Bengali ('bn') support explicitly — unlike more common multilingual
    # sentence-transformer models. See semantics/README.md. Runs on CPU by
    # default since the GPU is already used by Whisper on the dev 4GB card;
    # override SEMANTIC_DEVICE=cuda where VRAM allows.
    semantic_model_name: str = "sentence-transformers/LaBSE"
    semantic_device: str = "cpu"

    # --- Candidate ranking weights ---
    ranking_weight_acoustic: float = 0.4
    ranking_weight_phonetic: float = 0.4
    ranking_weight_semantic: float = 0.1
    ranking_weight_contextual: float = 0.1

    # --- Lexicon-augmented candidate generation (phonetics/lexicon.py) ---
    # See EXPERIMENTS.md "Experiments B/C" lexicon-constraint follow-up: adds
    # real-Bengali-word candidates phonetically near Whisper's raw
    # re-transcription of a correction clip, instead of relying on that raw
    # output alone. Empty path = use the OpenSLR SLR53 TSV already downloaded
    # for Stage 1 (phonetics/lexicon.py's default path resolution).
    correction_lexicon_constraint_enabled: bool = True
    correction_lexicon_tsv_path: str = ""
    correction_lexicon_top_k: int = 3
    correction_lexicon_max_edit_distance: int = 3

    # --- Service ---
    ml_service_host: str = "0.0.0.0"
    ml_service_port: int = 8000
    # Shared-secret auth between the Node backend and this service — required
    # once this service is reachable over the public internet (e.g. via a
    # tunnel from a local machine, not just localhost/private Docker network).
    # Empty (default) = no auth required, matching prior local-dev behavior
    # where ml-service was never itself internet-facing. Never sent to or
    # readable by the browser — only backend -> ml-service, over HTTPS.
    ml_service_api_key: str = ""


settings = Settings()
