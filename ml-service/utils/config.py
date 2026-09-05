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

    # --- Candidate ranking weights ---
    ranking_weight_acoustic: float = 0.4
    ranking_weight_phonetic: float = 0.4
    ranking_weight_semantic: float = 0.1
    ranking_weight_contextual: float = 0.1

    # --- Service ---
    ml_service_host: str = "0.0.0.0"
    ml_service_port: int = 8000


settings = Settings()
