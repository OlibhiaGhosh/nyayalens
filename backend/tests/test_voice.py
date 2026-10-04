"""Voice-question upload checks. These never reach Gemma: Ollama is reported unavailable."""
import io
import wave

import pytest
from fastapi.testclient import TestClient

import main
import pipeline as P


def _wav(seconds: float, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\0\0" * int(seconds * rate))
    return buf.getvalue()


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(main.gemma, "available", lambda: False)
    c = TestClient(main.app, base_url="http://127.0.0.1")
    sid = c.post("/api/text", json={"text": "1. The borrower shall pay a late fee of 5% per month."}).json()["session_id"]
    return c, sid


def _post(c, sid, data):
    return c.post(f"/api/session/{sid}/transcribe?lang=bn", files={"file": ("q.wav", data, "audio/wav")})


def test_rejects_non_wav(client):
    assert _post(*client, b"not audio").status_code == 400


def test_rejects_too_long(client):
    assert _post(*client, _wav(40)).status_code == 413


def test_near_silent_clip_returns_empty_without_model(client):
    assert _post(*client, _wav(0.1)).json() == {"text": "", "lang": "bn"}


def test_needs_gemma(client):
    assert _post(*client, _wav(2)).status_code == 503


def test_unknown_session(client):
    c, _ = client
    assert _post(c, "nope", _wav(2)).status_code == 404


class _FakeGemma:
    def __init__(self, out):
        self.out, self.media = out, None

    def chat_json(self, system, user, schema, *, media=None, **kw):
        self.media = media
        return self.out, None


def test_transcript_is_redacted_and_language_kept():
    g = _FakeGemma({"transcript": "আমার নম্বর 9830012345, জরিমানা কত?", "language": "hi"})
    out = P.transcribe_question(g, b"RIFF", "bn")
    assert "9830012345" not in out["text"] and "[PHONE]" in out["text"]
    assert out["lang"] == "hi" and g.media == [b"RIFF"]


def test_unknown_language_falls_back_to_ui_language():
    out = P.transcribe_question(_FakeGemma({"transcript": "hello", "language": "other"}), b"", "bn")
    assert out["lang"] == "bn"
