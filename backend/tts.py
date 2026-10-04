"""
Offline text-to-speech with Piper voices stored under models/piper/.

Each voice is <name>.onnx plus <name>.onnx.json. If a voice is missing, the
frontend falls back to the browser's own speech synthesis (if it has the language).
"""
from __future__ import annotations

import io
import threading
import wave

import config

_voices: dict[str, object] = {}
_lock = threading.Lock()


def voice_path(lang: str):
    name = config.PIPER_VOICES.get(lang)
    return config.PIPER_DIR / f"{name}.onnx" if name else None


def status() -> dict:
    try:
        import piper  # noqa: F401
        lib = True
    except ImportError:
        lib = False
    out = {"piper_installed": lib, "voices": {}}
    for lang in config.PIPER_VOICES:
        p = voice_path(lang)
        out["voices"][lang] = {"name": config.PIPER_VOICES[lang],
                               "present": bool(p and p.exists() and p.with_suffix(".onnx.json").exists())}
    return out


def available(lang: str) -> bool:
    s = status()
    return s["piper_installed"] and s["voices"].get(lang, {}).get("present", False)


def _load(lang: str):
    from piper import PiperVoice

    if lang not in _voices:
        _voices[lang] = PiperVoice.load(str(voice_path(lang)))
    return _voices[lang]


def synthesize(text: str, lang: str) -> bytes:
    """Return WAV bytes."""
    if not available(lang):
        raise RuntimeError(f"no Piper voice for {lang}")
    buf = io.BytesIO()
    with _lock:
        voice = _load(lang)
        with wave.open(buf, "wb") as wf:
            # piper-tts >= 1.3 has synthesize_wav; older releases used synthesize(text, wav_file).
            if hasattr(voice, "synthesize_wav"):
                voice.synthesize_wav(text, wf)
            else:
                voice.synthesize(text, wf)
    return buf.getvalue()
