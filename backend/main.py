"""
NyayaLens backend. Binds to 127.0.0.1 only, no CORS (the built frontend is served
from the same origin; in dev, Vite proxies /api), and a Host-header allowlist
against DNS rebinding.

Run:  python -m uvicorn main:app --host 127.0.0.1 --port 8000   (from backend/)
"""
from __future__ import annotations

import io
import json
import os
import socket
import threading
import time
import wave

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import config
import ocr
import pipeline as P
import tts
from clauses import lines_from_text, split_clauses
from gemma import Gemma, GemmaError
from redact import black_out, redact_lines

app = FastAPI(title="NyayaLens", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

gemma = Gemma()
_sessions: dict[str, P.Session] = {}
_sessions_lock = threading.Lock()
MAX_UPLOAD = 15 * 1024 * 1024
Lang = Query("bn", pattern="^(bn|hi|en)$")


# ---------------------------------------------------------------- sessions
def _purge() -> None:
    now = time.time()
    with _sessions_lock:
        for sid in [s for s, v in _sessions.items() if now - v.created > config.SESSION_TTL_S]:
            _sessions.pop(sid).wipe()


def _get(sid: str) -> P.Session:
    s = _sessions.get(sid)
    if s is None:
        raise HTTPException(404, "session not found (it may have been wiped)")
    return s


def _png(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _build_session(lines: list[dict], image=None, quality=None, meta=None) -> P.Session:
    _purge()
    s = P.Session()
    red_lines, boxes = redact_lines(lines)
    if image is not None:
        s.original_png = _png(image)
        s.redacted_png = _png(black_out(image, boxes))
        s.image_size = image.size
    s.quality = quality
    s.ocr_meta = meta or {}
    s.lines = red_lines
    s.clauses = split_clauses(red_lines)
    s.pii = [p for l in red_lines for p in l.get("pii", [])]
    with _sessions_lock:
        _sessions[s.id] = s
    return s


def _session_view(s: P.Session) -> dict:
    counts: dict[str, int] = {}
    for p in s.pii:
        counts[p["kind"]] = counts.get(p["kind"], 0) + 1
    return {
        "session_id": s.id,
        "quality": s.quality,
        "ocr": s.ocr_meta,
        "image": {"width": s.image_size[0], "height": s.image_size[1]} if s.image_size else None,
        "lines": [{"id": l["id"], "text": l["text"], "conf": l.get("conf"),
                   "low_conf": (l.get("conf") is not None and l["conf"] < 60)} for l in s.lines],
        "clauses": [{k: c[k] for k in ("id", "label", "text", "box", "low_conf", "categories", "selected")}
                    for c in s.clauses],
        "pii_counts": counts,
    }


# ---------------------------------------------------------------- health / self-check
@app.get("/api/selfcheck")
def selfcheck(probe_network: bool = False):
    out = {
        "backend": {"host": config.HOST, "port": config.PORT},
        "ollama": gemma.status(),
        "tesseract": ocr.tesseract_status(),
        "tts": tts.status(),
        "offline_env": {k: os.getenv(k) for k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")},
        "frontend_built": (config.FRONTEND_DIST / "index.html").exists(),
    }
    if probe_network:
        # Only on request: try one outbound connection to show the machine is offline.
        try:
            socket.create_connection(("1.1.1.1", 443), timeout=1.5).close()
            out["internet"] = "reachable"
        except OSError:
            out["internet"] = "unreachable"
    return out


@app.post("/api/warmup")
def warmup(lang: str = Lang):
    if not gemma.available():
        return {"ok": False, "status": gemma.status()}
    return {"ok": True, **gemma.warmup(), **P.warm_prompts(gemma, lang)}


# ---------------------------------------------------------------- intake
@app.post("/api/scan")
async def scan(file: UploadFile = File(...), langs: str = Form(config.OCR_LANGS)):
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "image too large (max 15 MB)")
    try:
        res = ocr.scan(data, langs)
    except ocr.OCRUnavailable as e:
        raise HTTPException(503, f"OCR unavailable: {e}") from e
    except Exception as e:  # noqa: BLE001 - bad image bytes, etc.
        raise HTTPException(400, f"could not read image: {e}") from e
    finally:
        del data
    s = _build_session(res["lines"], res["image"], res["quality"], res["meta"])
    return _session_view(s)


class TextIn(BaseModel):
    text: str = Field(..., max_length=50_000)


@app.post("/api/text")
def from_text(body: TextIn):
    s = _build_session(lines_from_text(body.text), meta={"source": "text"})
    return _session_view(s)


_SAMPLES = config.ROOT / "samples"


@app.get("/api/samples")
def samples():
    """Synthetic demo contracts (fake data), so the app can be tried without a paper."""
    out = []
    for t in sorted(_SAMPLES.glob("*.truth.json")):
        sid = t.name.removesuffix(".truth.json")
        out.append({"id": sid, "lang": json.loads(t.read_text(encoding="utf-8"))["lang"],
                    "photo": (_SAMPLES / "photos" / f"{sid}_clean.png").exists()})
    return out


@app.post("/api/samples/{sample_id}")
def load_sample(sample_id: str, photo: bool = True):
    if not all(ch.isalnum() or ch == "_" for ch in sample_id):
        raise HTTPException(400, "bad sample id")
    png = _SAMPLES / "photos" / f"{sample_id}_clean.png"
    if photo and png.exists() and ocr.tesseract_status()["available"]:
        res = ocr.scan(png.read_bytes())
        return _session_view(_build_session(res["lines"], res["image"], res["quality"], res["meta"]))
    txt = _SAMPLES / f"{sample_id}.txt"
    if not txt.exists():
        raise HTTPException(404, "no such sample")
    s = _build_session(lines_from_text(txt.read_text(encoding="utf-8")), meta={"source": "text"})
    return _session_view(s)


@app.put("/api/session/{sid}/text")
def correct_text(sid: str, body: TextIn):
    """'Is this what your paper says?': user-corrected text replaces the OCR text."""
    s = _get(sid)
    new = lines_from_text(body.text)
    if len(new) == len(s.lines):  # same line count: keep each line's box for the heatmap
        for n, o in zip(new, s.lines):
            n["box"], n["conf"] = o.get("box"), o.get("conf")
    red, _ = redact_lines(new)
    s.lines = red
    s.clauses = split_clauses(red)
    s.pii = s.pii + [p for l in red for p in l.get("pii", [])]
    s.analyses.clear()
    s.cards.clear()
    s.ocr_meta = {**s.ocr_meta, "user_corrected": True}
    return _session_view(s)


@app.get("/api/session/{sid}/image")
def image(sid: str, kind: str = Query("redacted", pattern="^(redacted|original)$")):
    s = _get(sid)
    data = s.redacted_png if kind == "redacted" else s.original_png
    if data is None:
        raise HTTPException(404, "no image for this session")
    return Response(data, media_type="image/png", headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------- analysis
def _ndjson(gen):
    def run():
        try:
            for ev in gen:
                yield json.dumps(ev, ensure_ascii=False) + "\n"
        except Exception as e:  # noqa: BLE001 - surface to the UI instead of a broken stream
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"
    return StreamingResponse(run(), media_type="application/x-ndjson")


@app.post("/api/session/{sid}/analyze")
def analyze(sid: str, lang: str = Lang):
    return _ndjson(P.run_analysis(_get(sid), gemma, lang))


@app.post("/api/session/{sid}/localize")
def localize(sid: str, lang: str = Lang):
    s = _get(sid)

    def gen():
        if lang not in s.cards:
            yield from P.localize_session(s, gemma, lang)
        yield {"type": "done", "result": P.result_view(s, lang)}
    return _ndjson(gen())


@app.get("/api/session/{sid}/result")
def result(sid: str, lang: str = Lang):
    s = _get(sid)
    if lang not in s.cards:
        raise HTTPException(409, "not localized yet; POST /localize first")
    return P.result_view(s, lang)


class MoneyIn(BaseModel):
    principal: float | None = None
    upfront_fees: float | None = None
    installment: float | None = None
    num_installments: int | None = None
    frequency: str | None = None
    balloon: float | None = None
    stated_rate_pct: float | None = None
    stated_rate_period: str | None = None
    rate_type: str | None = None
    monthly_rent: float | None = None
    security_deposit: float | None = None


@app.post("/api/session/{sid}/money")
def money(sid: str, body: MoneyIn, lang: str = Lang):
    s = _get(sid)
    return P.recompute_money(s, body.model_dump(exclude_unset=True), lang)


class AskIn(BaseModel):
    question: str = Field(..., max_length=500)


@app.post("/api/session/{sid}/ask")
def ask(sid: str, body: AskIn, lang: str = Lang):
    return P.answer_question(gemma, _get(sid), body.question, lang)


MAX_VOICE_S = 30  # Gemma 4 listens to at most ~30 s of audio per clip


@app.post("/api/session/{sid}/transcribe")
async def transcribe(sid: str, file: UploadFile = File(...), lang: str = Lang):
    """Spoken question (16 kHz mono WAV from the browser) -> text in the language spoken.
    The audio is only held in memory for this request."""
    _get(sid)
    data = await file.read()
    try:
        with wave.open(io.BytesIO(data)) as wf:
            seconds = wf.getnframes() / wf.getframerate()
    except (wave.Error, EOFError, ZeroDivisionError) as e:
        raise HTTPException(400, "expected a WAV recording") from e
    if seconds > MAX_VOICE_S + 2:
        raise HTTPException(413, f"recording too long (max {MAX_VOICE_S} s)")
    if seconds < 0.3:
        return {"text": "", "lang": lang}
    if not gemma.available():
        raise HTTPException(503, "voice questions need Gemma (Ollama) running; please type the question")
    try:
        return P.transcribe_question(gemma, data, lang)
    except GemmaError as e:
        raise HTTPException(503, f"could not hear the question: {e}") from e
    finally:
        del data


# ---------------------------------------------------------------- speech
class SpeakIn(BaseModel):
    text: str = Field(..., max_length=3000)
    lang: str = Field("bn", pattern="^(bn|hi|en)$")
    session_id: str | None = None


@app.post("/api/tts")
def speak(body: SpeakIn):
    if not tts.available(body.lang):
        raise HTTPException(503, f"no offline voice for {body.lang}")
    s = _sessions.get(body.session_id) if body.session_id else None
    key = f"{body.lang}:{body.text}"
    if s is not None and key in s.audio:
        wav = s.audio[key]
    else:
        wav = tts.synthesize(body.text, body.lang)
        if s is not None:
            s.audio[key] = wav
    return Response(wav, media_type="audio/wav", headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------- wipe
@app.post("/api/session/{sid}/wipe")
def wipe(sid: str):
    with _sessions_lock:
        s = _sessions.pop(sid, None)
    if s:
        s.wipe()
    return {"wiped": bool(s)}


@app.post("/api/wipe")
def wipe_all():
    with _sessions_lock:
        n = len(_sessions)
        for s in _sessions.values():
            s.wipe()
        _sessions.clear()
    return {"wiped": n}


# ---------------------------------------------------------------- frontend
if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = config.FRONTEND_DIST / path
        if path and f.is_file() and config.FRONTEND_DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(config.FRONTEND_DIST / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def root():
        return JSONResponse({"message": "Frontend not built. Run `npm run build` in frontend/, or use `npm run dev`."})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)
