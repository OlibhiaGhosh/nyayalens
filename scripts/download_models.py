"""
Download every offline asset NyayLens needs, ONCE, while you still have internet:
  - Tesseract language packs (ben, hin, eng, osd) -> models/tessdata/
  - Piper voices (Bengali, Hindi, English)        -> models/piper/
  - Gemma 4 via `ollama pull` (if Ollama is installed)

After this, the app runs with networking switched off.
Run:  python scripts/download_models.py [--skip-gemma] [--best]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
import config  # noqa: E402

PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
TESS_BASE = "https://github.com/tesseract-ocr/{repo}/raw/main/{lang}.traineddata"


def fetch(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  ok (already present) {dest.name}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"  downloading {dest.name} ...", flush=True)
    with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, length=1 << 20)
    tmp.replace(dest)


def piper_path(voice: str) -> str:
    lang_region, name, quality = voice.split("-")
    return f"{lang_region.split('_')[0]}/{lang_region}/{name}/{quality}/{voice}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-gemma", action="store_true")
    ap.add_argument("--best", action="store_true", help="tessdata_best (more accurate, slower) instead of tessdata")
    a = ap.parse_args()

    print("Tesseract language packs ->", config.TESSDATA_DIR)
    repo = "tessdata_best" if a.best else "tessdata"
    for lang in ("eng", "ben", "hin", "osd"):
        fetch(TESS_BASE.format(repo="tessdata" if lang == "osd" else repo, lang=lang),
              config.TESSDATA_DIR / f"{lang}.traineddata")

    print("Piper voices ->", config.PIPER_DIR)
    for voice in config.PIPER_VOICES.values():
        base = f"{PIPER_BASE}/{piper_path(voice)}"
        fetch(f"{base}.onnx?download=true", config.PIPER_DIR / f"{voice}.onnx")
        fetch(f"{base}.onnx.json?download=true", config.PIPER_DIR / f"{voice}.onnx.json")

    if not a.skip_gemma:
        exe = shutil.which("ollama")
        if exe:
            print(f"Gemma: ollama pull {config.MODEL}")
            subprocess.run([exe, "pull", config.MODEL], check=False)
        else:
            print("Ollama not found: install it from https://ollama.com, then run `ollama pull", config.MODEL + "`")
    print("Done.")


if __name__ == "__main__":
    main()
