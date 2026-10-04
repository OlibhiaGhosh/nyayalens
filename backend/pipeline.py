"""
Stages 4-7 and Q&A: clause analysis (Gemma, English JSON), loan terms, money math,
rule engine, localisation, "3 things to ask", grounded follow-up questions.

Every model call has a deterministic fallback, so the pipeline still runs (with
weaker explanations) when Ollama is not available. Cards say which engine was used.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field

import apr as aprmod
import rules as R
from config import DATA, PROMPTS
from gemma import Gemma, GemmaError
from redact import normalize_digits, redact_text

GLOSSARY = json.loads((DATA / "glossary.json").read_text(encoding="utf-8"))
LANGS = ("bn", "hi", "en")
LANG_NAME = {"en": "simple English", "bn": "Bengali (বাংলা)", "hi": "Hindi (हिन्दी)"}

# Order used to pick a clause's main category when the model is unavailable.
_CATEGORY_PRIORITY = [
    "rights_waiver", "repossession", "unilateral_change", "late_fee", "eviction", "prepayment",
    "security_deposit", "processing_fee", "interest_rate", "other",
]

_NUM = {"type": ["number", "null"]}
ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": R.CATEGORIES},
        "verdict": {"type": "string", "enum": R.VERDICTS},
        "extracted_terms": {
            "type": "object",
            "properties": {
                "amount": _NUM,
                "rate_pct": _NUM,
                "period": {"type": ["string", "null"]},
                "compounding": {"type": ["boolean", "null"]},
            },
            "required": ["amount", "rate_pct", "period", "compounding"],
        },
        "reason_en": {"type": "string"},
        "rule_ids": {"type": "array", "items": {"type": "string", "enum": R.MODEL_RULE_IDS}},
        "fair_rewrite_en": {"type": "string"},
    },
    "required": ["category", "verdict", "extracted_terms", "reason_en", "rule_ids", "fair_rewrite_en"],
}
TERMS_SCHEMA = {
    "type": "object",
    "properties": {
        "doc_type": {"type": "string", "enum": ["loan", "rental", "other"]},
        "principal": _NUM,
        "upfront_fees": _NUM,
        "upfront_fee_pct": _NUM,
        "installment": _NUM,
        "num_installments": {"type": ["integer", "null"]},
        "frequency": {"type": ["string", "null"], "enum": [*aprmod.PERIODS_PER_YEAR, None]},
        "balloon": _NUM,
        "stated_rate_pct": _NUM,
        "stated_rate_period": {"type": ["string", "null"], "enum": [*aprmod.RATE_PERIOD_PER_YEAR, None]},
        "rate_type": {"type": "string", "enum": ["flat", "reducing", "unknown"]},
        "monthly_rent": _NUM,
        "security_deposit": _NUM,
        "apr_disclosed": {"type": "boolean"},
    },
    "required": [
        "doc_type", "principal", "upfront_fees", "upfront_fee_pct", "installment", "num_installments",
        "frequency", "balloon", "stated_rate_pct", "stated_rate_period", "rate_type", "monthly_rent",
        "security_deposit", "apr_disclosed",
    ],
}
LOCALIZE_SCHEMA = {
    "type": "object",
    "properties": {
        "plain_explanation": {"type": "string"},
        "why_it_matters": {"type": "string"},
        "questions_to_ask": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 3},
        "ask_to_change": {"type": "string"},
    },
    "required": ["plain_explanation", "why_it_matters", "questions_to_ask", "ask_to_change"],
}
EXPLAIN_SCHEMA = {
    "type": "object",
    "properties": {"plain_explanation": {"type": "string"}, "why_it_matters": {"type": "string"}},
    "required": ["plain_explanation", "why_it_matters"],
}
TRANSCRIBE_SCHEMA = {
    "type": "object",
    "properties": {
        "transcript": {"type": "string"},
        "language": {"type": "string", "enum": ["bn", "hi", "en", "other"]},
    },
    "required": ["transcript", "language"],
}
QA_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "found": {"type": "boolean"},
        "clause_ids": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["answer", "found", "clause_ids"],
}


def _prompt(name: str, **kw: str) -> str:
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    for k, v in kw.items():
        text = text.replace("{{" + k + "}}", v)
    return text


# ======================================================================
# Session
# ======================================================================
@dataclass
class Session:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created: float = field(default_factory=time.time)
    original_png: bytes | None = None
    redacted_png: bytes | None = None
    image_size: tuple[int, int] | None = None
    quality: dict | None = None
    lines: list[dict] = field(default_factory=list)
    clauses: list[dict] = field(default_factory=list)
    ocr_meta: dict = field(default_factory=dict)
    pii: list[dict] = field(default_factory=list)
    engine: str | None = None
    analyses: dict[int, dict] = field(default_factory=dict)
    terms: dict | None = None
    terms_source: str | None = None
    money: dict | None = None
    money_error: str | None = None
    finals: dict[int, dict] = field(default_factory=dict)
    doc_hits: list[dict] = field(default_factory=list)
    unattached: list[str] = field(default_factory=list)
    cards: dict[str, dict[int, dict]] = field(default_factory=dict)
    audio: dict[str, bytes] = field(default_factory=dict)
    timings: dict[str, float] = field(default_factory=dict)

    def full_text(self) -> str:
        return "\n".join(c["text"] for c in self.clauses)

    def wipe(self) -> None:
        for f in ("original_png", "redacted_png"):
            setattr(self, f, None)
        self.lines.clear()
        self.clauses.clear()
        self.analyses.clear()
        self.cards.clear()
        self.audio.clear()
        self.finals.clear()
        self.terms = self.money = None


# ======================================================================
# Stage 5: clause analysis
# ======================================================================
def _primary_category(cats: list[str]) -> str:
    for c in _CATEGORY_PRIORITY:
        if c in cats:
            return c
    return "other"


# Offline-only keyword rules: used when Gemma is unavailable, never alongside it.
_FALLBACK_RULES = [
    ("unilateral_change", "unilateral_change",
     r"(?=.*(?:sole discretion|absolute discretion|without (?:prior )?notice|at any time|নোটিশ ছাড়া|যে ?কোনো সময়|ইচ্ছামতো|बिना सूचना|किसी भी समय))"
     r"(?=.*(?:revise|change|modify|amend|vary|increase|বদল|পরিবর্তন|বাড়া|बदल|परिवर्तन|बढ़ा))"),
    ("late_fee", "excessive_late_fee", r"per day|each day|daily|প্রতিদিন|দৈনিক|प्रतिदिन|रोज़ाना"),
    ("rights_waiver", "rights_waiver",
     r"waive|shall not approach|no claim|not challenge|final and binding|দাবি ত্যাগ|অধিকার ছেড়ে|अधिकार छोड़"),
    ("repossession", "repossession_without_notice",
     r"without (?:prior )?notice|any time|নোটিশ ছাড়া|बिना सूचना"),
    ("prepayment", "heavy_prepayment_charge",
     r"not (?:be )?(?:allowed|permitted)|no prepayment|(?:shall|can) ?not (?:re)?pay|(?:full|entire|remaining) .{0,20}interest|"
     r"\d+\s*%|অনুমতি নেই|अनुमति नहीं"),
    ("processing_fee", "hidden_upfront_fees",
     r"deduct|upfront|advance interest|কেটে|আগাম সুদ|काट|अग्रिम ब्याज"),
    ("eviction", "eviction_without_notice",
     r"without (?:prior )?notice|lock|cut off|নোটিশ ছাড়া|তালা|बिना सूचना|ताला"),
]


def _fallback_analysis(clause: dict, error: str | None = None) -> dict:
    cat = _primary_category(clause["categories"])
    text = normalize_digits(clause["text"])
    rule_ids = [rid for c, rid, pat in _FALLBACK_RULES if c in clause["categories"] and re.search(pat, text, re.I)]
    verdict = "CAREFUL" if clause["score"] >= 3 or rule_ids else "OK"
    return {
        "category": cat,
        "verdict": verdict,
        "extracted_terms": {"amount": None, "rate_pct": None, "period": None, "compounding": None},
        "reason_en": f"Keyword check only (AI model not available): this clause is about {cat.replace('_', ' ')}.",
        "rule_ids": rule_ids,
        "fair_rewrite_en": "",
        "engine": "fallback",
        "error": error,
    }


def analyze_clause(gemma: Gemma, clause: dict, use_model: bool, deep: bool = False,
                   lang: str | None = None) -> dict:
    """
    English analysis of one clause. With `lang`, the same call also writes the
    plain-language explanation in that language (returned under "loc"): one call per
    clause with one constant system prompt, so Ollama's prompt cache is reused.
    """
    if not use_model:
        return _fallback_analysis(clause)
    system = _prompt("analyze_clause", rule_list=R.rule_list_for_prompt(), categories=", ".join(R.CATEGORIES))
    schema = ANALYSIS_SCHEMA
    if lang:
        system += _prompt("explain_addendum", language=LANG_NAME[lang], glossary=_glossary_for(lang))
        schema = {**ANALYSIS_SCHEMA,
                  "properties": {**ANALYSIS_SCHEMA["properties"], **EXPLAIN_SCHEMA["properties"]},
                  "required": ANALYSIS_SCHEMA["required"] + EXPLAIN_SCHEMA["required"]}
    user = f'Clause {clause["label"] or clause["id"]}:\n"""\n{clause["text"]}\n"""'
    if clause.get("low_conf"):
        user += "\n(OCR confidence for this clause is low; some words may be misread.)"
    try:
        out, thinking = gemma.chat_json(system, user, schema, think=True if deep else None,
                                        num_predict=900 if lang else 700)
    except GemmaError as e:
        return _fallback_analysis(clause, str(e))
    if lang:
        out["loc"] = {"lang": lang,
                      "plain_explanation": str(out.pop("plain_explanation", "")).strip(),
                      "why_it_matters": str(out.pop("why_it_matters", "")).strip()}
    if out.get("category") not in R.CATEGORIES:
        out["category"] = _primary_category(clause["categories"])
    if out.get("verdict") not in R.VERDICTS:
        out["verdict"] = "CAREFUL"
    out["rule_ids"] = [r for r in out.get("rule_ids", []) if r in R.MODEL_RULE_IDS]
    out["engine"] = "gemma"
    out["thinking"] = thinking
    out["stats"] = dict(gemma.last_stats)
    return out


# ======================================================================
# Loan terms (model extracts numbers; code does all math)
# ======================================================================
_AMT = re.compile(
    r"(?:rs\.?|₹|inr|rupees)\s*(\d[\d,.]*\d|\d)|(\d[\d,.]*\d|\d)\s*(?:/-|rupees|টাকা|रुपये|रुपए|रु\.?)",
    re.I,
)
_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent|শতাংশ|प्रतिशत)", re.I)
_PERIOD_WORDS = [
    ("month", r"per month|p\.?\s?m\b|monthly|a month|every month|মাসিক|প্রতি মাসে|মাসে|मासिक|प्रति माह|हर महीने|महीना"),
    ("day", r"per day|daily|a day|দৈনিক|প্রতিদিন|रोज़ाना|प्रतिदिन|प्रति दिन"),
    ("week", r"per week|weekly|সাপ্তাহিক|প্রতি সপ্তাহে|साप्ताहिक|हर हफ्ते"),
    ("year", r"per annum|p\.?\s?a\b|per year|yearly|annual|বার্ষিক|বছরে|वार्षिक|सालाना|प्रति वर्ष"),
]
_N_INST = re.compile(
    r"(\d{1,3})\s*(?:টি|টা)?\s*(?:equal\s+)?"
    r"(?:monthly\s+|weekly\s+|daily\s+|মাসিক\s+|সাপ্তাহিক\s+|দৈনিক\s+|मासिक\s+|साप्ताहिक\s+|दैनिक\s+)?"
    r"(installments|instalments|emis?|months|weeks|days|কিস্তি|মাস|সপ্তাহ|দিন|किस्तों|किस्तें|किस्त|महीने|महीनों|हफ्ते|दिन)",
    re.I,
)


def _to_num(s: str) -> float:
    # OCR often reads the comma in "5,000" as a dot; rupee amounts never have three decimals.
    # Same for lakh format: "1.00,000" is 1,00,000. A dot before a comma is never a decimal point.
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s) or re.fullmatch(r"[\d.]+,[\d,]+", s):
        s = s.replace(".", "")
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:  # e.g. "1.2.3" from OCR noise: keep the leading number
        return float(re.match(r"\d+(?:\.\d+)?", s).group())


def _amounts(text: str) -> list[float]:
    return [_to_num(m.group(1) or m.group(2)) for m in _AMT.finditer(text) if (m.group(1) or m.group(2)).strip(",")]


def _amount_near(text: str, kw: str, window: int = 90) -> float | None:
    """First amount after a keyword; else the amount just before it ("৫০,০০০ টাকা জামানত")."""
    matches = list(re.finditer(kw, text, re.I))
    for m in matches:
        a = _AMT.search(text[m.end(): m.end() + window])
        if a:
            return _to_num(a.group(1) or a.group(2))
    for m in matches:
        before = list(_AMT.finditer(text[max(0, m.start() - 40): m.start()]))
        if before:
            return _to_num(before[-1].group(1) or before[-1].group(2))
    return None


def _period_near(text: str, pos: int) -> str | None:
    """Period word closest to the percentage at `pos` ("12% per annum", "মাসিক 3%")."""
    start = max(0, pos - 40)
    window = text[start: pos + 50]
    best, best_dist = None, None
    for period, pat in _PERIOD_WORDS:
        for m in re.finditer(pat, window, re.I):
            dist = abs(start + m.start() - pos)
            if best_dist is None or dist < best_dist:
                best, best_dist = period, dist
    return best


def regex_terms(clauses: list[dict]) -> dict:
    """Best-effort extraction without the model. Used as fallback and as an eval baseline."""
    full = normalize_digits(" \n".join(c["text"] for c in clauses))
    low = full.lower()
    t: dict = {k: None for k in TERMS_SCHEMA["required"]}
    t["rate_type"] = "unknown"
    t["apr_disclosed"] = bool(re.search(r"\bAPR\b|annual percentage rate|key facts", full, re.I))

    is_rental = bool(re.search(r"\brent\b|tenant|landlord|ভাড়া|ভাড়াটে|किराया|किरायेदार", low))
    is_loan = bool(re.search(r"\bloan\b|borrow|lender|ঋণ|ধার|কর্জ|कर्ज़|कर्ज|ऋण|उधार", low))
    t["doc_type"] = "loan" if is_loan else ("rental" if is_rental else "other")

    t["principal"] = _amount_near(
        full, r"loan amount|amount of (?:the )?loan|(?<!lump )sum of|advances?|lends?|disburse[sd]?|principal|"
              r"ঋণের পরিমাণ|ধার|ঋণ|कर्ज़ की रकम|ऋण राशि|कर्ज|ऋण")
    t["installment"] = _amount_near(
        full, r"install?ments? of|instal?ments? of|\bemis? of|each install?ment|each instal?ment|\bemis?\b|কিস্তি|किस्त")
    lump = re.search(r"lump ?sum|in one payment|single payment|একবারে|এককালীন|एकमुश्त|एक बार में", full, re.I)
    if lump:
        # Moneylender style: everything repaid at once after N months.
        after = re.search(r"after (\d{1,3}) (months?|weeks?|days?)|(\d{1,3})\s*(?:মাস|মাসের|महीने)\s*(?:পরে|পর|बाद)",
                          full, re.I)
        t["balloon"] = _amount_near(full, r"lump ?sum(?: of)?|in one payment|single payment|একবারে|এককালীন|एकमुश्त|एक बार में")
        if after and t["balloon"]:
            t["installment"] = None
            t["num_installments"] = int(after.group(1) or after.group(3))
            unit = (after.group(2) or "month").lower()
            t["frequency"] = "weekly" if unit.startswith("week") else "daily" if unit.startswith("day") else "monthly"
    m = _N_INST.search(full)
    if m and not t["num_installments"]:
        t["num_installments"] = int(m.group(1))
        unit = m.group(2).lower()
        if re.match(r"week|সপ্তাহ|हफ्ते", unit):
            t["frequency"] = "weekly"
        elif re.match(r"day|দিন|दिन", unit):
            t["frequency"] = "daily"
    if t["num_installments"] and not t["frequency"]:
        if re.search(r"weekly|every week|সাপ্তাহিক|साप्ताहिक", low):
            t["frequency"] = "weekly"
        elif re.search(r"daily|every day|দৈনিক|रोज़ाना", low):
            t["frequency"] = "daily"
        else:
            t["frequency"] = "monthly"

    # Fees: amounts in fee clauses, excluding the principal itself.
    fees = 0.0
    for c in clauses:
        if "processing_fee" in c["categories"]:
            ct = normalize_digits(c["text"])
            for a in _amounts(ct):
                if a != t["principal"] and a != t["installment"]:
                    fees += a
            pm = re.search(r"(?:fee|charge|ফি|চার্জ|शुल्क|फीस)[^.%]{0,40}?(\d+(?:\.\d+)?)\s*%", ct, re.I)
            if pm and not fees:
                t["upfront_fee_pct"] = float(pm.group(1))
    t["upfront_fees"] = fees or None

    # Stated interest rate: first percentage in an interest clause that is not about late fees.
    rate_clauses = [c for c in clauses if "interest_rate" in c["categories"] and "late_fee" not in c["categories"]]
    for c in rate_clauses or clauses:
        ct = normalize_digits(c["text"])
        pm = _PCT.search(ct)
        if pm:
            t["stated_rate_pct"] = float(pm.group(1))
            t["stated_rate_period"] = _period_near(ct, pm.start()) or "year"
            if re.search(r"\bflat\b|ফ্ল্যাট|फ्लैट", ct, re.I):
                t["rate_type"] = "flat"
            elif re.search(r"reducing|diminishing|outstanding|বাকি|घटती|बकाया", ct, re.I):
                t["rate_type"] = "reducing"
            break

    if is_rental:
        t["monthly_rent"] = _amount_near(full, r"monthly rent|rent of|rent|ভাড়া|किराया")
        t["security_deposit"] = _amount_near(full, r"security deposit|deposit|জামানত|অগ্রিম|डिपॉज़िट|सिक्योरिटी|अग्रिम")
    return t


def _clean_terms(t: dict) -> dict:
    out = {k: t.get(k) for k in TERMS_SCHEMA["required"]}
    for k in ("principal", "upfront_fees", "upfront_fee_pct", "installment", "balloon",
              "stated_rate_pct", "monthly_rent", "security_deposit"):
        v = out.get(k)
        out[k] = float(v) if isinstance(v, (int, float)) and v > 0 else None
    n = out.get("num_installments")
    out["num_installments"] = int(n) if isinstance(n, (int, float)) and 0 < n <= 2000 else None
    if out.get("frequency") not in aprmod.PERIODS_PER_YEAR:
        out["frequency"] = "monthly" if out["num_installments"] else None
    if out.get("stated_rate_period") not in aprmod.RATE_PERIOD_PER_YEAR:
        out["stated_rate_period"] = "year" if out["stated_rate_pct"] else None
    if out.get("rate_type") not in ("flat", "reducing", "unknown"):
        out["rate_type"] = "unknown"
    return out


def extract_terms(gemma: Gemma, clauses: list[dict], use_model: bool) -> tuple[dict, str]:
    baseline = regex_terms(clauses)
    if not use_model:
        return _clean_terms(baseline), "regex"
    doc = "\n".join(f"Clause {c['label'] or c['id']}: {c['text']}" for c in clauses)
    try:
        out, _ = gemma.chat_json(_prompt("loan_terms"), doc, TERMS_SCHEMA, num_predict=400)
    except GemmaError:
        return _clean_terms(baseline), "regex"
    terms = _clean_terms(out)
    base = _clean_terms(baseline)
    # Lump-sum loans: the model tends to report "1 installment", which turns a 6-month loan
    # into a 1-month one and inflates the APR several-fold. The pattern reading is explicit.
    if base.get("balloon") and not base.get("installment") and base.get("num_installments"):
        for k in ("balloon", "num_installments", "frequency"):
            terms[k] = base[k]
        terms["installment"] = None
    # Fill gaps the model left with the regex reading.
    for k, v in base.items():
        if terms.get(k) in (None, "unknown") and v not in (None, "unknown"):
            terms[k] = v
    return terms, "gemma"


def compute_money(terms: dict | None) -> tuple[dict | None, str | None]:
    """Run the deterministic calculator. Returns (LoanCost dict, error / missing-field note)."""
    if not terms or terms.get("doc_type") == "rental":
        return None, None
    p, n = terms.get("principal"), terms.get("num_installments")
    inst, rate = terms.get("installment"), terms.get("stated_rate_pct")
    missing = [k for k, v in (("principal", p), ("num_installments", n)) if not v]
    if not inst and not rate:
        missing.append("installment_or_rate")
    if missing:
        return None, "missing:" + ",".join(missing)
    fees = terms.get("upfront_fees")
    if not fees and terms.get("upfront_fee_pct"):
        fees = p * terms["upfront_fee_pct"] / 100
    if not inst and terms.get("balloon"):
        inst = 0.0  # single lump-sum repayment: no regular installments
    try:
        res = aprmod.compute_loan_cost(
            p, n,
            installment=inst,
            frequency=terms.get("frequency") or "monthly",
            upfront_fees=fees or 0.0,
            balloon=terms.get("balloon") or 0.0,
            stated_rate_pct=rate,
            stated_rate_period=terms.get("stated_rate_period") or "year",
            rate_type=terms.get("rate_type") or "unknown",
        )
    except ValueError as e:
        return None, f"error:{e}"
    return res.to_dict(), None


# ======================================================================
# Stage 7: localisation into cards
# ======================================================================
def _glossary_for(lang: str) -> str:
    if lang == "en":
        return "(none; plain English)"
    return "; ".join(f"{en} = {v[lang]}" for en, v in GLOSSARY["terms"].items() if lang in v)


def _curated_questions(rule_ids: list[str], lang: str) -> list[str]:
    qs: list[str] = []
    for r in rule_ids:
        for q in R.RULES[r]["questions"].get(lang, []):
            if q not in qs:
                qs.append(q)
    return qs


def _fallback_localization(clause: dict, analysis: dict, final: dict, lang: str) -> dict:
    cat = analysis.get("category") or _primary_category(clause["categories"])
    rule_ids = final["rule_ids"]
    if rule_ids:
        why = R.RULES[rule_ids[0]]["plain"][lang]
    elif final["verdict"] == "OK":
        why = GLOSSARY["looks_standard"][lang]
    else:
        why = analysis["reason_en"] if lang == "en" else GLOSSARY["category_text"][cat][lang]
    qs = _curated_questions(rule_ids, lang)[:3] or GLOSSARY["generic_questions"][lang][:2]
    ask = R.RULES[rule_ids[0]]["ask_to_change"][lang] if rule_ids else ""
    return {
        "plain_explanation": GLOSSARY["category_text"].get(cat, GLOSSARY["category_text"]["other"])[lang],
        "why_it_matters": why,
        "questions_to_ask": qs,
        "ask_to_change": ask,
        "engine": "curated",
    }


def localize(gemma: Gemma, clause: dict, analysis: dict, final: dict, lang: str, use_model: bool) -> dict:
    if final["verdict"] == "OK" or not use_model:
        return _fallback_localization(clause, analysis, final, lang)
    rules_txt = "\n".join(f"- {R.RULES[r]['name']['en']}: {R.RULES[r]['plain']['en']}" for r in final["rule_ids"])
    user = (
        f'Clause text:\n"""\n{clause["text"]}\n"""\n\n'
        f"English analysis: verdict {final['verdict']}. {analysis.get('reason_en', '')}\n"
        f"Suggested fairer version: {analysis.get('fair_rewrite_en') or '(none)'}\n"
        f"Rules it matches:\n{rules_txt or '(none)'}"
    )
    system = _prompt("localize", language=LANG_NAME[lang], glossary=_glossary_for(lang))
    # When curated rules match, their reviewed questions and "change to ask for" are used,
    # and Gemma only writes the two explanation sentences: half the tokens on a slow CPU,
    # and less unreviewed text in front of the user.
    curated = bool(final["rule_ids"])
    schema = EXPLAIN_SCHEMA if curated else LOCALIZE_SCHEMA
    try:
        out, _ = gemma.chat_json(system, user, schema, num_predict=350 if curated else 600)
    except GemmaError:
        return _fallback_localization(clause, analysis, final, lang)
    if curated:
        qs = _curated_questions(final["rule_ids"], lang)
        ask = R.RULES[final["rule_ids"][0]]["ask_to_change"][lang]
    else:
        qs = [q.strip() for q in out.get("questions_to_ask", []) if isinstance(q, str) and q.strip()]
        qs += GLOSSARY["generic_questions"][lang]
        ask = str(out.get("ask_to_change", "")).strip()
    return {
        "plain_explanation": str(out.get("plain_explanation", "")).strip(),
        "why_it_matters": str(out.get("why_it_matters", "")).strip(),
        "questions_to_ask": list(dict.fromkeys(qs))[:3],
        "ask_to_change": ask,
        "engine": "gemma",
    }


def _loc_from_combined(loc: dict, final: dict, lang: str) -> dict:
    """Model-written explanation + curated (reviewed) questions and requested change."""
    rule_ids = final["rule_ids"]
    if rule_ids:
        qs, ask = _curated_questions(rule_ids, lang), R.RULES[rule_ids[0]]["ask_to_change"][lang]
    elif final["verdict"] == "OK":
        qs, ask = [], ""
    else:
        qs, ask = GLOSSARY["generic_questions"][lang], ""
    return {"plain_explanation": loc["plain_explanation"], "why_it_matters": loc["why_it_matters"],
            "questions_to_ask": qs[:3], "ask_to_change": ask, "engine": "gemma"}


def build_card(clause: dict, analysis: dict | None, final: dict | None, loc: dict | None, lang: str,
               pending: bool = False) -> dict:
    base = {
        "pending": pending,
        "clause_id": clause["id"],
        "label": clause["label"],
        "original_text": clause["text"],
        "box": clause["box"],
        "line_boxes": clause["line_boxes"],
        "low_conf": clause["low_conf"],
        "conf": clause["conf"],
        "categories": clause["categories"],
    }
    if final is None:
        return {**base, "verdict": "UNCHECKED", "rule_ids": [], "rules": [], "statutes": []}
    rule_ids = final["rule_ids"]
    return {
        **base,
        "verdict": final["verdict"],
        "verdict_source": final["verdict_source"],
        "rule_ids": rule_ids,
        "rule_ids_from_code": final["rule_ids_from_code"],
        "rules": [R.rule_view(r, lang) for r in rule_ids],
        "statutes": [R.statute_view(s, lang) for s in final["statute_ids"]],
        "category": (analysis or {}).get("category"),
        "reason_en": (analysis or {}).get("reason_en"),
        "fair_rewrite_en": (analysis or {}).get("fair_rewrite_en") or "",
        "riders_en": [R.RULES[r]["rider_en"] for r in rule_ids],
        "extracted_terms": (analysis or {}).get("extracted_terms"),
        "thinking": (analysis or {}).get("thinking"),
        "engine": (analysis or {}).get("engine", "rules"),
        **(loc or {}),
        "loc_engine": (loc or {}).get("engine"),
    }


_RANK = {"NOT_OK": 0, "CAREFUL": 1, "OK": 2, "UNCHECKED": 3}


def three_questions(cards: list[dict], session: Session, lang: str) -> list[dict]:
    """The '3 things to ask before signing': deterministic pick from the worst clauses."""
    picked: list[dict] = []
    seen: set[str] = set()
    if any(h["rule_id"] == "effective_cost_mismatch" for h in session.doc_hits):
        q = R.RULES["effective_cost_mismatch"]["questions"][lang][0]
        picked.append({"question": q, "clause_id": None})
        seen.add(q)
    ranked = sorted([c for c in cards if c["verdict"] in ("NOT_OK", "CAREFUL")],
                    key=lambda c: (_RANK[c["verdict"]], c["clause_id"]))
    for depth in range(3):
        for c in ranked:
            qs = c.get("questions_to_ask") or []
            if depth < len(qs) and qs[depth] not in seen and len(picked) < 3:
                picked.append({"question": qs[depth], "clause_id": c["clause_id"]})
                seen.add(qs[depth])
    return picked


# ======================================================================
# Orchestration
# ======================================================================
def _progress(stage: str, i: int = 0, n: int = 0, label: str = "") -> dict:
    return {"type": "progress", "stage": stage, "i": i, "n": n, "label": label}


def warm_prompts(gemma: Gemma, lang: str = "bn") -> dict:
    """
    Pre-fill Ollama's prompt cache with the two long system prompts (terms, clause
    analysis). With OLLAMA_NUM_PARALLEL=2 each stays cached in its own slot, so the
    first real document skips ~1,000 tokens of prompt processing per call.
    """
    t0 = time.perf_counter()
    dummy = {"id": 0, "label": "1", "text": "The Borrower shall repay the loan.", "categories": [],
             "score": 0, "low_conf": False}
    extract_terms(gemma, [dummy], True)
    analyze_clause(gemma, dummy, True, lang=lang)
    return {"prompt_warmup_s": round(time.perf_counter() - t0, 1)}


def run_analysis(session: Session, gemma: Gemma, lang: str):
    """
    Generator of events. Order is chosen for a slow CPU: the money view first (the
    most important number), then each clause fully analysed AND explained, riskiest
    first, each emitted as a "partial" result so the UI fills in progressively.
    The last event is {"type": "done", "result": ...}.
    """
    use_model = gemma.available()
    session.engine = "gemma" if use_model else "fallback"
    yield {"type": "start", "engine": session.engine, "model": gemma.model}
    session.analyses.clear()
    session.finals.clear()
    session.cards = {}

    yield _progress("terms")
    t0 = time.perf_counter()
    session.terms, session.terms_source = extract_terms(gemma, session.clauses, use_model)
    session.money, session.money_error = compute_money(session.terms)
    session.doc_hits = R.doc_level_hits(session.full_text(), session.terms, session.money)
    # Attach document-wide findings using keyword categories (model categories aren't known yet).
    primary = {c["id"]: _primary_category(c["categories"]) for c in session.clauses}
    doc_extra, session.unattached = R.attach_doc_hits(session.clauses, session.doc_hits, primary)
    session.timings["terms_s"] = round(time.perf_counter() - t0, 2)

    selected = sorted((c for c in session.clauses if c["selected"]), key=lambda c: -c["score"])
    todo = selected + [c for c in session.clauses if c["id"] in doc_extra and not c["selected"]]
    pending = {c["id"] for c in todo}
    cards = session.cards[lang] = {c["id"]: build_card(c, None, None, None, lang, pending=c["id"] in pending)
                                   for c in session.clauses}
    yield {"type": "partial", "result": result_view(session, lang)}

    deep_id = selected[0]["id"] if selected else None
    t0 = time.perf_counter()
    for i, c in enumerate(todo):
        yield _progress("analyze", i + 1, len(todo), c["label"] or str(c["id"]))
        a = analyze_clause(gemma, c, use_model, deep=c["id"] == deep_id, lang=lang) if c["selected"] else None
        if a is not None:
            session.analyses[c["id"]] = a
        final = R.finalize(a, c["text"], doc_extra.get(c["id"]))
        session.finals[c["id"]] = final
        if a is not None and a.get("loc", {}).get("plain_explanation"):
            loc = _loc_from_combined(a["loc"], final, lang)
        else:
            loc = localize(gemma, c, a or _fallback_analysis(c), final, lang, use_model)
        cards[c["id"]] = build_card(c, a, final, loc, lang)
        yield {"type": "clause", "clause_id": c["id"], "verdict": final["verdict"]}
        yield {"type": "partial", "result": result_view(session, lang)}
    session.timings["clauses_s"] = round(time.perf_counter() - t0, 2)
    yield {"type": "done", "result": result_view(session, lang)}


def _apply_rules(session: Session) -> None:
    session.doc_hits = R.doc_level_hits(session.full_text(), session.terms, session.money)
    primary = {c["id"]: _primary_category(c["categories"]) for c in session.clauses}
    per_clause, session.unattached = R.attach_doc_hits(session.clauses, session.doc_hits, primary)
    session.finals = {}
    for c in session.clauses:
        a = session.analyses.get(c["id"])
        extra = per_clause.get(c["id"])
        if a is not None or extra:
            session.finals[c["id"]] = R.finalize(a, c["text"], extra)


def localize_session(session: Session, gemma: Gemma, lang: str, use_model: bool | None = None):
    if use_model is None:
        use_model = session.engine == "gemma" and gemma.available()
    t0 = time.perf_counter()
    cards: dict[int, dict] = {}
    todo = [c for c in session.clauses if c["id"] in session.finals]
    for i, c in enumerate(todo):
        final = session.finals[c["id"]]
        analysis = session.analyses.get(c["id"]) or _fallback_analysis(c)
        if final["verdict"] != "OK" and use_model:
            yield _progress("localize", i + 1, len(todo), c["label"] or str(c["id"]))
        loc = localize(gemma, c, analysis, final, lang, use_model)
        cards[c["id"]] = build_card(c, session.analyses.get(c["id"]), final, loc, lang)
    for c in session.clauses:
        if c["id"] not in cards:
            cards[c["id"]] = build_card(c, None, None, None, lang)
    session.cards[lang] = cards
    session.timings[f"localize_{lang}_s"] = round(time.perf_counter() - t0, 2)


def recompute_money(session: Session, terms: dict, lang: str) -> dict:
    """User corrected the numbers: redo math and rules, keep model analyses."""
    session.terms = _clean_terms({**(session.terms or {}), **terms})
    session.money, session.money_error = compute_money(session.terms)
    old_finals = dict(session.finals)
    _apply_rules(session)
    loc_keys = ("plain_explanation", "why_it_matters", "questions_to_ask", "ask_to_change", "engine")
    for lg, cards in session.cards.items():
        for c in session.clauses:
            final = session.finals.get(c["id"])
            old = cards.get(c["id"])
            if final == old_finals.get(c["id"]) and old is not None:
                continue  # unchanged: keep the model's localized text
            analysis = session.analyses.get(c["id"])
            loc = (_fallback_localization(c, analysis or _fallback_analysis(c), final, lg)
                   if final else None)
            if loc and old and old.get("plain_explanation"):
                loc = {**loc, **{k: old[k] for k in loc_keys[:2] if old.get(k)}}
            cards[c["id"]] = build_card(c, analysis, final, loc, lg)
    return result_view(session, lang)


def result_view(session: Session, lang: str) -> dict:
    cards = [session.cards[lang][c["id"]] for c in session.clauses] if lang in session.cards else []
    return {
        "session_id": session.id,
        "lang": lang,
        "engine": session.engine,
        "image": {"width": session.image_size[0], "height": session.image_size[1]} if session.image_size else None,
        "cards": cards,
        "money": session.money,
        "money_error": session.money_error,
        "terms": session.terms,
        "terms_source": session.terms_source,
        "doc_hits": [
            {**R.rule_view(h["rule_id"], lang), "detail": h["detail"],
             "statutes": [R.statute_view(s, lang) for s in R.RULES[h["rule_id"]]["statute_ids"]],
             "questions": R.RULES[h["rule_id"]]["questions"][lang],
             "rider_en": R.RULES[h["rule_id"]]["rider_en"],
             "ask_to_change": R.RULES[h["rule_id"]]["ask_to_change"][lang],
             "attached": h["rule_id"] not in session.unattached}
            for h in session.doc_hits
        ],
        "summary": three_questions(cards, session, lang),
        "help": R.help_view(lang),
        "timings": session.timings,
        "pii": session.pii,
    }


# ======================================================================
# Grounded follow-up Q&A
# ======================================================================
_WORD = re.compile(r"[\wঀ-৿ऀ-ॿ]+")


def transcribe_question(gemma: Gemma, wav: bytes, lang: str) -> dict:
    """Spoken question -> text, heard by Gemma itself (no separate speech model).
    The transcript is redacted like OCR text, so a spoken phone or Aadhaar number is hidden."""
    system = _prompt("transcribe", language=LANG_NAME[lang])
    out, _ = gemma.chat_json(system, "Transcribe the spoken question.", TRANSCRIBE_SCHEMA,
                             num_predict=200, media=[wav])
    text, _ = redact_text(str(out.get("transcript", "")).strip())
    spoken = out.get("language")
    return {"text": text[:500], "lang": spoken if spoken in LANGS else lang}


def answer_question(gemma: Gemma, session: Session, question: str, lang: str) -> dict:
    not_found = GLOSSARY["not_in_document"][lang]
    valid_ids = {c["id"] for c in session.clauses}
    if gemma.available():
        clauses_txt = "\n".join(f"[id {c['id']}] Clause {c['label'] or c['id']}: {c['text']}" for c in session.clauses)
        system = _prompt("qa", language=LANG_NAME[lang], not_found=not_found, clauses=clauses_txt)
        try:
            out, _ = gemma.chat_json(system, question, QA_SCHEMA, num_predict=300)
            ids = [i for i in out.get("clause_ids", []) if i in valid_ids]
            if out.get("found") and ids:
                return {"answer": out.get("answer", "").strip(), "found": True, "clause_ids": ids, "engine": "gemma"}
            return {"answer": not_found, "found": False, "clause_ids": [], "engine": "gemma"}
        except GemmaError:
            pass
    # Fallback: word overlap, quoting the best clause.
    q_words = {w.lower() for w in _WORD.findall(question) if len(w) > 3}
    best, best_score = None, 0
    for c in session.clauses:
        score = len(q_words & {w.lower() for w in _WORD.findall(c["text"])})
        if score > best_score:
            best, best_score = c, score
    if best is None or best_score < 2:
        return {"answer": not_found, "found": False, "clause_ids": [], "engine": "keywords"}
    return {"answer": best["text"], "found": True, "clause_ids": [best["id"]], "engine": "keywords"}
