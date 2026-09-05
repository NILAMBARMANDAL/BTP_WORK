"""Regenerates synthetic Bengali speech test fixtures via gTTS.

These are clearly-enunciated TTS samples used only to smoke-test the pipeline
(they are NOT a substitute for real recorded speech in evaluation — see
DATA_PIPELINE.md). Run from ml-service/ with requirements-dev.txt installed:

    python scripts/generate_fixtures.py
"""

from gtts import gTTS

FIXTURES_DIR = "tests/fixtures"

SAMPLES = {
    "sample_bn.mp3": "আমার সোনার বাংলা আমি তোমায় ভালোবাসি",
    "correction_sonar.mp3": "সোনার",
    "correction_bari.mp3": "বাড়ি",
}


def main():
    for filename, text in SAMPLES.items():
        gTTS(text=text, lang="bn").save(f"{FIXTURES_DIR}/{filename}")
        print(f"wrote {filename}")


if __name__ == "__main__":
    main()
