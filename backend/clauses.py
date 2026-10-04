"""
Group OCR lines into numbered clauses and pick the suspicious ones for Gemma.

Input lines are already redacted. Each line: {"id", "text", "box": [x,y,w,h] | None, "conf"}.
"""
from __future__ import annotations

import re

from redact import normalize_digits

MAX_ANALYZE = 8
LOW_CONF = 60  # Tesseract word confidence (0-100) below which we warn

# Top-level clause markers: "1.", "2)", "(3)", "Clause 4:", "ধারা ৫।", "खंड 6 -"
_CLAUSE_START = re.compile(
    r"^\s*(?:clause|section|article|para(?:graph)?|ধারা|শর্ত|অনুচ্ছেদ|खंड|धारा|शर्त|अनुच्छेद)?\s*"
    r"[\(\[]?(\d{1,2})\s*(?:[\.\):\]।](?!\d)|[\-–](?=\s))\s*(?=\S)",
    re.I,
)

# Keywords per risk category, in English, Bengali and Hindi.
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "late_fee": [
        "late", "delay", "overdue", "penal", "penalty", "default interest", "bounce", "dishonour",
        "বিলম্ব", "দেরি", "জরিমানা", "বকেয়া", "খেলাপ",
        "विलंब", "देरी", "जुर्माना", "दंड", "बकाया", "चूक",
    ],
    "processing_fee": [
        "processing", "file charge", "documentation", "service charge", "insurance", "deducted",
        "upfront", "advance interest", "fee",
        "প্রসেসিং", "ফি", "চার্জ", "কেটে", "বীমা",
        "प्रोसेसिंग", "शुल्क", "फीस", "काट", "बीमा",
    ],
    "interest_rate": [
        "interest", "rate", "flat", "per month", "per annum", "p.a", "emi", "installment", "instalment",
        "সুদ", "হার", "কিস্তি", "মাসিক",
        "ब्याज", "दर", "किस्त", "मासिक",
    ],
    "unilateral_change": [
        "sole discretion", "at any time", "without notice", "without prior notice", "revise", "modify",
        "amend", "vary", "change the", "absolute discretion",
        "নিজের ইচ্ছা", "যে কোনো সময়", "যেকোনো সময়", "পরিবর্তন", "নোটিশ ছাড়া",
        "किसी भी समय", "बदल", "परिवर्तन", "बिना सूचना", "विवेक",
    ],
    "repossession": [
        "seize", "seizure", "repossess", "take possession", "collateral", "pledge", "mortgage",
        "auction", "sell the", "recovery agent", "enter the premises", "gold",
        "বাজেয়াপ্ত", "দখল", "নিলাম", "জামানত", "বন্ধক", "সোনা",
        "ज़ब्त", "जब्त", "कब्जा", "नीलाम", "गिरवी", "जमानत", "सोना",
    ],
    "rights_waiver": [
        "waive", "waiver", "shall not approach", "no claim", "consumer forum", "consumer court",
        "not challenge", "any court", "final and binding", "no objection", "blank cheque", "blank",
        "দাবি ত্যাগ", "আদালত", "অভিযোগ", "ফোরাম", "সাদা চেক", "ফাঁকা",
        "अधिकार छोड़", "अदालत", "शिकायत", "उपभोक्ता", "खाली चेक", "कोरा",
    ],
    "prepayment": [
        "prepay", "pre-pay", "foreclos", "pre-closure", "preclosure", "early repayment",
        "repay early", "repaid early", "repay before", "pay before", "close the loan early",
        "part payment", "part-payment",
        "আগাম পরিশোধ", "আগে শোধ", "আগেই শোধ",
        "पूर्व भुगतान", "फोरक्लोज़र", "समय से पहले",
    ],
    "security_deposit": [
        "security deposit", "advance rent", "deposit", "refundable", "non-refundable",
        "অগ্রিম", "জামানত", "ফেরতযোগ্য",
        "अग्रिम", "सिक्योरिटी", "वापसी योग्य",
    ],
    "eviction": [
        "evict", "vacate", "terminate the tenancy", "lock", "cut off", "electricity", "water supply",
        "উচ্ছেদ", "খালি করতে", "তালা",
        "बेदखल", "खाली करना", "ताला", "बिजली",
    ],
}

# Strong signals weigh more than generic words like "fee" or "rate".
_STRONG = {
    "sole discretion", "without notice", "without prior notice", "waive", "waiver", "seize",
    "repossess", "compound", "non-refundable", "blank cheque", "absolute discretion",
    "shall not approach", "foreclos", "penal", "নোটিশ ছাড়া", "সাদা চেক", "बिना सूचना", "खाली चेक",
}
_NUMBER_WITH_PCT = re.compile(r"\d+(?:\.\d+)?\s*%|percent|শতাংশ|प्रतिशत")


_OCR_ONE = re.compile(r"^\s*[Il|](?=[.)]\s)")


def _union_box(boxes: list[list[int]]) -> list[int] | None:
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[0] + b[2] for b in boxes)
    y1 = max(b[1] + b[3] for b in boxes)
    return [x0, y0, x1 - x0, y1 - y0]


def prefilter(text: str) -> tuple[list[str], float]:
    """Return (matched categories, suspicion score)."""
    low = normalize_digits(text).lower()
    cats, score = [], 0.0
    for cat, kws in CATEGORY_KEYWORDS.items():
        hits = [k for k in kws if k.lower() in low]
        if hits:
            cats.append(cat)
            score += sum(3.0 if k in _STRONG else 1.0 for k in hits)
    if "compound" in low:
        score += 3
    if _NUMBER_WITH_PCT.search(low):
        score += 1
    # Interest/fee words alone are routine; money words plus a number are worth a look.
    return cats, score


def split_clauses(lines: list[dict]) -> list[dict]:
    """
    Group lines into clauses on top-level numbering. Text before the first number
    becomes clause 0 (title, parties). With no numbering at all, fall back to
    paragraphs separated by blank lines or vertical gaps.
    """
    lines = [l for l in lines if l.get("text", "").strip()]
    if not lines:
        return []

    groups: list[tuple[str | None, list[dict]]] = []
    numbered = 0
    for line in lines:
        # OCR often reads a leading "1." as "I." or "l.".
        m = _CLAUSE_START.match(_OCR_ONE.sub("1", normalize_digits(line["text"])))
        if m:
            numbered += 1
            groups.append((m.group(1), [line]))
        elif groups:
            groups[-1][1].append(line)
        else:
            groups.append((None, [line]))

    if numbered < 2:
        groups = [(None, g) for g in _paragraphs(lines)]

    clauses = []
    for idx, (label, ls) in enumerate(groups):
        text = " ".join(l["text"].strip() for l in ls)
        confs = [l["conf"] for l in ls if l.get("conf") is not None]
        conf = sum(confs) / len(confs) if confs else None
        cats, score = prefilter(text)
        clauses.append({
            "id": idx,
            "label": label or ("" if idx == 0 and numbered >= 2 else str(idx + 1)),
            "text": text,
            "line_ids": [l["id"] for l in ls],
            "box": _union_box([l.get("box") for l in ls]),
            "line_boxes": [l["box"] for l in ls if l.get("box")],
            "conf": round(conf, 1) if conf is not None else None,
            "low_conf": conf is not None and conf < LOW_CONF,
            "categories": cats,
            "score": score,
            "selected": False,
        })
    _select(clauses)
    return clauses


def _paragraphs(lines: list[dict]) -> list[list[dict]]:
    """Fallback split: blank-line markers (text input) or large vertical gaps (images)."""
    paras: list[list[dict]] = [[]]
    heights = [l["box"][3] for l in lines if l.get("box")]
    med_h = sorted(heights)[len(heights) // 2] if heights else None
    prev = None
    for l in lines:
        gap_break = False
        if med_h and prev is not None and prev.get("box") and l.get("box"):
            gap = l["box"][1] - (prev["box"][1] + prev["box"][3])
            gap_break = gap > 1.2 * med_h
        if (l.get("para_break") or gap_break) and paras[-1]:
            paras.append([])
        paras[-1].append(l)
        prev = l
    return [p for p in paras if p]


def _select(clauses: list[dict]) -> None:
    """Mark up to MAX_ANALYZE clauses for model analysis: all if few, else the most suspicious."""
    # The unnumbered preamble (title, parties) holds no terms; it is never analysed.
    body = [c for c in clauses if len(c["text"]) > 15 and c["label"]]
    if len(body) <= MAX_ANALYZE:
        chosen = body
    else:
        ranked = sorted(body, key=lambda c: c["score"], reverse=True)
        chosen = [c for c in ranked if c["score"] > 0][:MAX_ANALYZE]
    for c in chosen:
        c["selected"] = True


def lines_from_text(text: str) -> list[dict]:
    """Make OCR-shaped lines from pasted or corrected text (no boxes)."""
    out, pending_break = [], False
    for raw in text.splitlines():
        if not raw.strip():
            pending_break = True
            continue
        out.append({"id": len(out), "text": raw.strip(), "box": None, "conf": None,
                    "words": [{"text": w, "box": None} for w in raw.split()],
                    "para_break": pending_break})
        pending_break = False
    return out
