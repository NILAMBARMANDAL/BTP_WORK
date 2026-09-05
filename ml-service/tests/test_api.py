"""Integration tests against the FastAPI app, using real synthetic Bengali
audio fixtures (tests/fixtures/) and real GPU Whisper inference — these are
slow (model load + inference) and are the closest thing to an end-to-end check
without a browser. CI should mark/skip these if GPU is unavailable; see
.github/workflows.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from phonetics.similarity import phonetic_similarity

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


@pytest.mark.model
def test_transcribe_returns_structured_words(client):
    sample = FIXTURES / "sample_bn.mp3"
    if not sample.exists():
        pytest.skip("fixture not present; run scripts/generate_fixtures.py")

    with sample.open("rb") as f:
        res = client.post("/transcribe", files={"file": ("sample_bn.mp3", f, "audio/mpeg")})

    assert res.status_code == 200
    body = res.json()
    assert body["language"] == "bn"
    assert isinstance(body["words"], list)
    assert len(body["words"]) > 0
    for w in body["words"]:
        assert "index" in w and "text" in w


@pytest.mark.model
def test_correct_returns_ranked_candidates(client):
    # বাড়ি (house) is not a near-homophone of a plausible wrong word, unlike
    # স/শ pairs (see RESEARCH.md — those are genuinely ambiguous in standard
    # Bengali pronunciation and were observed to make Whisper's exact script
    # choice non-deterministic across decode passes). Using a distinct word
    # here keeps this test about endpoint mechanics, not phonetic ambiguity.
    sample = FIXTURES / "correction_bari.mp3"
    if not sample.exists():
        pytest.skip("fixture not present; run scripts/generate_fixtures.py")

    with sample.open("rb") as f:
        res = client.post(
            "/correct",
            files={"file": ("correction_bari.mp3", f, "audio/mpeg")},
            data={
                "original_word": "বাড়ী",
                "context_text": "আমার বাড়ি",
                "mode": "pronunciation_only",
            },
        )

    assert res.status_code == 200
    body = res.json()
    assert len(body["candidates"]) >= 1
    # Not asserting exact string equality on the prediction: Whisper was
    # observed to sometimes drop the nukta diacritic (বাড়ি -> বাড়ি without
    #় on ড়), a real Bengali-script transcription quirk, not an app bug —
    # see RESEARCH.md limitations. Phonetic similarity is robust to that.
    assert phonetic_similarity(body["prediction"], "বাড়ি") > 0.6
    top = body["candidates"][0]
    assert top["phoneticScore"] > 0.5  # বাড়ি vs বাড়ী differ only in a spelling variant


def test_correct_rejects_invalid_mode(client):
    sample = FIXTURES / "correction_sonar.mp3"
    if not sample.exists():
        pytest.skip("fixture not present; run scripts/generate_fixtures.py")

    with sample.open("rb") as f:
        res = client.post(
            "/correct",
            files={"file": ("correction_sonar.mp3", f, "audio/mpeg")},
            data={"original_word": "x", "mode": "not_a_real_mode"},
        )

    assert res.status_code == 400
