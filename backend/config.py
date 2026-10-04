"""Paths and settings. Everything is overridable with environment variables."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PROMPTS = DATA / "prompts"
MODELS = ROOT / "models"
FRONTEND_DIST = ROOT / "frontend" / "dist"

OLLAMA_HOST = os.getenv("OLLAMA_HOST_URL", "http://127.0.0.1:11434")
MODEL = os.getenv("NYAYA_MODEL", "gemma4:e4b")  # set to gemma4:e2b on slow laptops
NUM_CTX = int(os.getenv("NYAYA_NUM_CTX", "8192"))
TEMPERATURE = float(os.getenv("NYAYA_TEMPERATURE", "0.1"))
KEEP_ALIVE = os.getenv("NYAYA_KEEP_ALIVE", "60m")
THINK = os.getenv("NYAYA_THINK", "0") == "1"  # only enable after checking your Ollama build supports it for Gemma 4
LLM_TIMEOUT_S = float(os.getenv("NYAYA_LLM_TIMEOUT", "300"))

TESSERACT_CMD = os.getenv("TESSERACT_CMD") or (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe" if os.name == "nt" else "tesseract"
)
OCR_LANGS = os.getenv("NYAYA_OCR_LANGS", "ben+hin+eng")
# Language packs downloaded by scripts/download_models.py live here (no admin rights needed).
TESSDATA_DIR = Path(os.getenv("NYAYA_TESSDATA_DIR", str(MODELS / "tessdata")))
OCR_PSM = os.getenv("NYAYA_OCR_PSM", "4")

PIPER_DIR = Path(os.getenv("NYAYA_PIPER_DIR", str(MODELS / "piper")))
PIPER_VOICES = {
    "bn": os.getenv("NYAYA_VOICE_BN", "bn_BD-google-medium"),
    "hi": os.getenv("NYAYA_VOICE_HI", "hi_IN-pratham-medium"),
    "en": os.getenv("NYAYA_VOICE_EN", "en_US-lessac-medium"),
}

HOST = os.getenv("NYAYA_HOST", "127.0.0.1")
PORT = int(os.getenv("NYAYA_PORT", "8000"))
SESSION_TTL_S = int(os.getenv("NYAYA_SESSION_TTL", "3600"))
