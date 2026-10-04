"""
PII redaction: Aadhaar (Verhoeff checksum), PAN, Indian mobile numbers, email.

Runs right after OCR. Everything downstream (clause split, Gemma, Q&A) sees only
the redacted text, so the model never sees an Aadhaar number.

Works on OCR lines that carry per-word boxes, so the same matches produce both
black boxes on the image and placeholders in the text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ---------- digit normalisation (length-preserving, so offsets stay valid) ----------
_DIGIT_MAP = {}
for _base in (0x09E6, 0x0966):  # Bengali ০-৯, Devanagari ०-९
    for _i in range(10):
        _DIGIT_MAP[chr(_base + _i)] = str(_i)
_DIGIT_TABLE = str.maketrans(_DIGIT_MAP)


def normalize_digits(s: str) -> str:
    return s.translate(_DIGIT_TABLE)


# ---------- Verhoeff ----------
_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]
_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def verhoeff_valid(num: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(num)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def verhoeff_check_digit(num: str) -> str:
    """Check digit to append to `num` (used to make synthetic test Aadhaar numbers)."""
    c = 0
    for i, ch in enumerate(reversed(num)):
        c = _D[c][_P[(i + 1) % 8][int(ch)]]
    return str(_INV[c])


# ---------- detectors ----------
_SEP = r"[ \- ]?"
_AADHAAR = re.compile(rf"(?<![\dA-Za-z])([2-9]\d{{3}}{_SEP}\d{{4}}{_SEP}\d{{4}})(?![\dA-Za-z])")
_AADHAAR_GROUPED = re.compile(r"^\d{4}[ \- ]\d{4}[ \- ]\d{4}$")
# Masked Aadhaar printed on e-Aadhaar: XXXX XXXX 1234 — the last 4 digits still identify.
_AADHAAR_MASKED = re.compile(r"(?<![A-Za-z\d])([Xx*]{4}[ \-]?[Xx*]{4}[ \-]?\d{4})(?![\dA-Za-z])")
_AADHAAR_KEYWORD = re.compile(r"aadha+r|adhar|uid(ai)?\b|আধার|आधार", re.I)
_PAN = re.compile(r"(?<![A-Za-z0-9])([A-Z]{3}[ABCFGHLJPTK][A-Z]\d{4}[A-Z])(?![A-Za-z0-9])")
_PHONE = re.compile(r"(?<![\d])((?:\+?91[ \-]?|0)?[6-9]\d{4}[ \-]?\d{5})(?!\d)")
_PHONE_KEYWORD = re.compile(r"phone|mobile|\bmob\b|\bph\b|contact|ফোন|মোবাইল|फ़ोन|फोन|मोबाइल|संपर्क", re.I)
_LONG_DIGITS = re.compile(r"(?<!\d)(\d(?:[ \-]?\d){7,14})(?!\d)")
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

PLACEHOLDER = {"aadhaar": "[AADHAAR]", "pan": "[PAN]", "phone": "[PHONE]", "email": "[EMAIL]"}


@dataclass
class Match:
    kind: str
    start: int
    end: int
    checksum_ok: bool | None = None


def find_pii(text: str) -> list[Match]:
    """Find PII spans in one line of text. Offsets refer to `text`."""
    norm = normalize_digits(text)
    found: list[Match] = []
    has_kw = bool(_AADHAAR_KEYWORD.search(norm))

    for m in _AADHAAR.finditer(norm):
        raw = m.group(1)
        digits = re.sub(r"\D", "", raw)
        ok = verhoeff_valid(digits)
        # Valid checksum: confident. Failed checksum still redacted when it looks like
        # an Aadhaar (4-4-4 grouping or keyword on the line) because OCR misreads a digit
        # often, and a missed Aadhaar costs far more than a hidden account number.
        if ok or _AADHAAR_GROUPED.match(raw) or has_kw:
            found.append(Match("aadhaar", m.start(1), m.end(1), ok))
    for m in _AADHAAR_MASKED.finditer(norm):
        found.append(Match("aadhaar", m.start(1), m.end(1), None))
    for m in _PAN.finditer(norm):
        found.append(Match("pan", m.start(1), m.end(1)))
    for m in _PHONE.finditer(norm):
        if not _overlaps(m.start(1), m.end(1), found):
            found.append(Match("phone", m.start(1), m.end(1)))
    for m in _EMAIL.finditer(norm):
        found.append(Match("email", m.start(), m.end()))
    # OCR often adds or drops a digit, which breaks the strict patterns. On a line that
    # says "Aadhaar" or "phone", hide any remaining long digit run (8+ digits).
    for kw, kind in ((_AADHAAR_KEYWORD, "aadhaar"), (_PHONE_KEYWORD, "phone")):
        if kw.search(norm):
            for m in _LONG_DIGITS.finditer(norm):
                if not _overlaps(m.start(1), m.end(1), found) and len(re.sub(r"\D", "", m.group(1))) >= 8:
                    # Attribute to the nearest preceding keyword when both appear on one line.
                    found.append(Match(_nearest_kind(norm, m.start(1)) or kind, m.start(1), m.end(1)))
    found.sort(key=lambda x: x.start)
    return found


def _nearest_kind(text: str, pos: int) -> str | None:
    best, best_pos = None, -1
    for kw, kind in ((_AADHAAR_KEYWORD, "aadhaar"), (_PHONE_KEYWORD, "phone")):
        for m in kw.finditer(text[:pos]):
            if m.start() > best_pos:
                best, best_pos = kind, m.start()
    return best


def _overlaps(s: int, e: int, matches: list[Match]) -> bool:
    return any(s < m.end and m.start < e for m in matches)


def redact_text(text: str) -> tuple[str, list[Match]]:
    """Replace PII in a single string with placeholders."""
    out_lines, all_matches = [], []
    for line in text.split("\n"):
        matches = find_pii(line)
        all_matches.extend(matches)
        out, last = [], 0
        for m in matches:
            out.append(line[last:m.start])
            out.append(PLACEHOLDER[m.kind])
            last = m.end
        out.append(line[last:])
        out_lines.append("".join(out))
    return "\n".join(out_lines), all_matches


def redact_lines(lines: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    lines: [{"id", "words": [{"text", "box": [x, y, w, h]}], ...}]
    Returns (redacted_lines, boxes_to_black_out).
    Each redacted line gets "text" with placeholders; words inside a match are
    flagged "redacted": True and their text replaced.
    """
    boxes: list[dict] = []
    out: list[dict] = []
    for line in lines:
        words = line["words"]
        # Join words with single spaces, remembering each word's character span.
        spans, pos = [], 0
        for w in words:
            spans.append((pos, pos + len(w["text"])))
            pos += len(w["text"]) + 1
        joined = " ".join(w["text"] for w in words)
        matches = find_pii(joined)

        new_words = [dict(w) for w in words]
        for m in matches:
            first = True
            for i, (s, e) in enumerate(spans):
                if s < m.end and m.start < e:
                    new_words[i]["redacted"] = True
                    new_words[i]["text"] = PLACEHOLDER[m.kind] if first else ""
                    first = False
                    if new_words[i].get("box"):
                        boxes.append({"kind": m.kind, "box": new_words[i]["box"]})
        text = " ".join(w["text"] for w in new_words if w["text"])
        out.append({**line, "words": new_words, "text": text,
                    "pii": [{"kind": m.kind, "checksum_ok": m.checksum_ok} for m in matches]})
    return out, boxes


def black_out(image, boxes: list[dict], pad: int = 4):
    """Draw solid black rectangles on a copy of a PIL image."""
    from PIL import ImageDraw

    img = image.copy()
    d = ImageDraw.Draw(img)
    for b in boxes:
        x, y, w, h = b["box"]
        d.rectangle([x - pad, y - pad, x + w + pad, y + h + pad], fill="black")
    return img
