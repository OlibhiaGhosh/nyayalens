"""
Stage 1-2: photo quality check, OpenCV cleanup, Tesseract OCR with word boxes.

Boxes are in the coordinates of the *display* image (resized and deskewed), which
is what the frontend shows under the heatmap, so overlays line up.
"""
from __future__ import annotations

import io
import os
import re
import shutil

import cv2
import numpy as np
from PIL import Image, ImageOps

import config

BLUR_MIN = float(os.getenv("NYAYA_BLUR_MIN", "60"))
DARK_MAX = 70
BRIGHT_MIN = 235
MIN_SIDE = 700


class OCRUnavailable(RuntimeError):
    pass


def load_image(data: bytes) -> np.ndarray:
    """Bytes -> BGR array, honouring phone EXIF rotation."""
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def quality(img: np.ndarray) -> dict:
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Measure sharpness at a fixed width so the threshold doesn't depend on camera resolution.
    small = cv2.resize(gray, (1000, max(1, int(h * 1000 / w))), interpolation=cv2.INTER_AREA)
    blur = float(cv2.Laplacian(small, cv2.CV_64F).var())
    bright = float(gray.mean())
    issues = []
    if blur < BLUR_MIN:
        issues.append("blurry")
    if bright < DARK_MAX:
        issues.append("too_dark")
    # White paper is naturally bright; only flag when there is almost no ink contrast (glare / washed out).
    if bright > BRIGHT_MIN and float(np.percentile(small, 1)) > 170:
        issues.append("too_bright")
    if min(h, w) < MIN_SIDE:
        issues.append("too_small")
    return {"blur_score": round(blur, 1), "brightness": round(bright, 1), "width": w, "height": h,
            "issues": issues, "retake": bool(issues)}


def _order_corners(pts: np.ndarray) -> np.ndarray:
    s, d = pts.sum(axis=1), np.diff(pts, axis=1).ravel()
    return np.float32([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]])


def _find_page(img: np.ndarray) -> np.ndarray | None:
    """Corners of the paper if it is clearly visible against a darker background."""
    h, w = img.shape[:2]
    k = 800 / w
    small = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (800, max(1, int(h * k))), interpolation=cv2.INTER_AREA)
    _, bw = cv2.threshold(cv2.GaussianBlur(small, (5, 5), 0), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    contours, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    c = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(c) / (small.shape[0] * small.shape[1])
    approx = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
    # Skip when the page already fills the frame (flatbed scan / screenshot) or isn't a quadrilateral.
    if len(approx) != 4 or not (0.25 < area < 0.93) or not cv2.isContourConvex(approx):
        return None
    # The frame around the photo must be clearly darker than the page; otherwise the
    # "edge" is just a lighting gradient across the paper.
    mask = np.zeros_like(small)
    cv2.fillConvexPoly(mask, approx.reshape(4, 2), 255)
    bh, bw_ = max(1, small.shape[0] // 25), max(1, small.shape[1] // 25)
    frame = np.concatenate([small[:bh].ravel(), small[-bh:].ravel(), small[:, :bw_].ravel(), small[:, -bw_:].ravel()])
    if float(np.percentile(frame, 75)) > float(small[mask > 0].mean()) - 40:
        return None
    return _order_corners(approx.reshape(4, 2).astype(np.float32) / k)


def _flatten(img: np.ndarray, corners: np.ndarray) -> np.ndarray:
    tl, tr, br, bl = corners
    w = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    h = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    dst = np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])
    return cv2.warpPerspective(img, cv2.getPerspectiveTransform(corners, dst), (w, h))


def _even_lighting(gray: np.ndarray) -> np.ndarray:
    """Divide by a blurred background estimate: removes shadows and lifts dim photos."""
    bg = cv2.GaussianBlur(cv2.dilate(gray, np.ones((9, 9), np.uint8)), (0, 0), 25)
    return cv2.divide(gray, bg, scale=255)


def _deskew_angle(gray: np.ndarray) -> float:
    """Small-angle deskew: pick the rotation that makes text rows sharpest (projection profile)."""
    small = cv2.resize(gray, (800, max(1, int(gray.shape[0] * 800 / gray.shape[1]))), interpolation=cv2.INTER_AREA)
    bw = cv2.adaptiveThreshold(small, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 15)
    h, w = bw.shape

    def score(angle: float) -> float:
        m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        rot = cv2.warpAffine(bw, m, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
        return float(np.var(rot.sum(axis=1)))

    coarse = max(np.arange(-10, 10.01, 1.0), key=score)
    return float(max(np.arange(coarse - 1, coarse + 1.01, 0.1), key=score))


def preprocess(img: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict]:
    """Returns (display_bgr, ocr_gray, meta)."""
    corners = _find_page(img)
    if corners is not None:
        img = _flatten(img, corners)
    h, w = img.shape[:2]
    target = 2000
    scale = target / w if (w < 1400 or w > 3200) else 1.0
    if scale != 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)),
                         interpolation=cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA)
    gray = _even_lighting(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    angle = _deskew_angle(gray)
    if abs(angle) >= 0.3:
        h2, w2 = gray.shape
        m = cv2.getRotationMatrix2D((w2 / 2, h2 / 2), angle, 1.0)
        img = cv2.warpAffine(img, m, (w2, h2), flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255))
        gray = cv2.warpAffine(gray, m, (w2, h2), flags=cv2.INTER_CUBIC, borderValue=255)
    ocr_gray = cv2.medianBlur(gray, 3)
    return img, ocr_gray, {"scale": round(scale, 3), "deskew_deg": round(angle, 2),
                           "page_found": corners is not None}


# ---------- Tesseract ----------
def _pytesseract():
    import pytesseract

    if os.path.exists(config.TESSERACT_CMD):
        pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD
    elif shutil.which("tesseract"):
        pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract")
    return pytesseract


def _tessdata_arg() -> str:
    d = config.TESSDATA_DIR
    if not any(d.glob("*.traineddata")):
        return ""
    p = d.as_posix()
    return f'--tessdata-dir "{p}"' if " " in p else f"--tessdata-dir {p}"


def tesseract_status() -> dict:
    try:
        pt = _pytesseract()
        version = str(pt.get_tesseract_version())
        langs = pt.get_languages(config=_tessdata_arg())
    except Exception as e:  # noqa: BLE001
        return {"available": False, "error": str(e)}
    want = config.OCR_LANGS.split("+")
    return {"available": True, "version": version, "langs": langs,
            "missing": [l for l in want if l not in langs]}


# Systematic Tesseract `ben` confusions. ঋণ (loan) is read as খণ; the real word খণ্ড has a
# hasanta after ণ, so only fix খণ when no hasanta follows.
_BN_FIXES = [(re.compile(r"খণ(?!্)"), "ঋণ")]


def _fix_word(text: str) -> str:
    for pat, rep in _BN_FIXES:
        text = pat.sub(rep, text)
    return text


def run_ocr(gray: np.ndarray, langs: str | None = None) -> list[dict]:
    status = tesseract_status()
    if not status["available"]:
        raise OCRUnavailable(status.get("error", "Tesseract not found"))
    want = (langs or config.OCR_LANGS).split("+")
    use = "+".join(l for l in want if l in status["langs"]) or "eng"
    pt = _pytesseract()
    d = pt.image_to_data(Image.fromarray(gray), lang=use, config=f"--psm {config.OCR_PSM} {_tessdata_arg()}",
                         output_type=pt.Output.DICT)
    lines: dict[tuple, dict] = {}
    for i, text in enumerate(d["text"]):
        text = _fix_word((text or "").strip())
        conf = float(d["conf"][i])
        if not text or conf < 0:
            continue
        key = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
        word = {"text": text, "conf": conf,
                "box": [int(d["left"][i]), int(d["top"][i]), int(d["width"][i]), int(d["height"][i])]}
        lines.setdefault(key, {"words": []})["words"].append(word)

    out = []
    for key in sorted(lines, key=lambda k: (min(w["box"][1] for w in lines[k]["words"]), k)):
        words = lines[key]["words"]
        xs = [w["box"][0] for w in words]
        ys = [w["box"][1] for w in words]
        x1 = max(w["box"][0] + w["box"][2] for w in words)
        y1 = max(w["box"][1] + w["box"][3] for w in words)
        out.append({
            "id": len(out),
            "words": words,
            "text": " ".join(w["text"] for w in words),
            "box": [min(xs), min(ys), x1 - min(xs), y1 - min(ys)],
            "conf": round(sum(w["conf"] for w in words) / len(words), 1),
            "lang": use,
        })
    return out


_SCRIPTS = {"ben": re.compile(r"[ঀ-৿]"), "hin": re.compile(r"[ऀ-ॿ]"), "eng": re.compile(r"[A-Za-z]")}


def dominant_langs(lines: list[dict]) -> str:
    """
    With ben+hin+eng all enabled, Tesseract invents glyphs from the wrong script on
    blurry text (Devanagari inside Bengali, Bengali inside English). Pick the main
    Indic script by character count and keep English alongside it.
    """
    text = " ".join(l["text"] for l in lines)
    counts = {k: len(p.findall(text)) for k, p in _SCRIPTS.items()}
    indic = max(("ben", "hin"), key=counts.get)
    # Treat the document as Indic only if that script is a real share of the text, not stray noise.
    if counts[indic] > 0.25 * max(1, counts["eng"] + counts[indic]):
        return f"{indic}+eng"
    return "eng"


def _mean_conf(lines: list[dict]) -> float:
    words = [w["conf"] for l in lines for w in l["words"]]
    return sum(words) / len(words) if words else 0.0


def scan(data: bytes, langs: str | None = None) -> dict:
    img = load_image(data)
    q = quality(img)
    display, gray, meta = preprocess(img)
    lines = run_ocr(gray, langs)
    requested = langs or config.OCR_LANGS
    meta["ocr_langs"] = requested
    if "+" in requested:
        chosen = dominant_langs(lines)
        if chosen != requested:
            # The narrower pass removes wrong-script glyphs on blurry pages but can drop
            # digits on clean Hindi; keep whichever pass Tesseract is more confident in.
            retry = run_ocr(gray, chosen)
            if _mean_conf(retry) >= _mean_conf(lines):
                lines, meta["ocr_langs"] = retry, chosen
    display_pil = Image.fromarray(cv2.cvtColor(display, cv2.COLOR_BGR2RGB))
    confs = [l["conf"] for l in lines]
    meta.update({"n_lines": len(lines), "mean_conf": round(sum(confs) / len(confs), 1) if confs else None})
    return {"quality": q, "image": display_pil, "lines": lines, "meta": meta}
