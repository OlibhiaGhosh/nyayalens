"""
Evaluate NyayLens on the synthetic contracts in samples/.

Modes:
  text   ground-truth text -> redaction -> clauses -> analysis   (tests the reasoning)
  image  photo -> OCR -> redaction -> clauses -> analysis         (tests the full pipeline)

Metrics (written to eval/results.md and eval/results.json):
  - seeded risky clauses caught (verdict CAREFUL or NOT_OK), and caught as NOT_OK
  - false alarms: clean clauses marked NOT_OK
  - expected rule IDs found
  - total-repayment and APR error vs ground truth
  - PII redaction recall and extra redactions
  - seconds per document

Run:  python eval/run_eval.py [--mode text|image|both] [--limit N]
Uses Gemma via Ollama if it is running, otherwise the keyword fallback (reported).
"""
from __future__ import annotations

import argparse
import json
import platform
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import config  # noqa: E402
import ocr  # noqa: E402
import pipeline as P  # noqa: E402
from clauses import lines_from_text, split_clauses  # noqa: E402
from gemma import Gemma  # noqa: E402
from redact import PLACEHOLDER, normalize_digits, redact_lines  # noqa: E402

SAMPLES = ROOT / "samples"
PHOTOS = SAMPLES / "photos"


def make_session(lines: list[dict]) -> P.Session:
    s = P.Session()
    red, _ = redact_lines(lines)
    s.lines = red
    s.clauses = split_clauses(red)
    s.pii = [p for l in red for p in l.get("pii", [])]
    return s


def digits(s: str) -> str:
    return re.sub(r"\D", "", normalize_digits(s))


def score(truth: dict, s: P.Session, result: dict) -> dict:
    cards = {c["label"]: c for c in result["cards"]}
    all_rules = {r for c in result["cards"] for r in c["rule_ids"]} | {h["id"] for h in result["doc_hits"]}
    risky = [c for c in truth["clauses"] if c["risky"]]
    clean = [c for c in truth["clauses"] if not c["risky"]]

    caught, caught_hard, missed, false_alarm, rules_hit, rules_total, rule_misses = 0, 0, [], [], 0, 0, []
    for c in risky:
        card = cards.get(c["label"])
        v = card["verdict"] if card else "MISSING"
        if v in ("CAREFUL", "NOT_OK"):
            caught += 1
        else:
            missed.append(f"clause {c['label']} ({v})")
        if v == "NOT_OK":
            caught_hard += 1
    for c in clean:
        card = cards.get(c["label"])
        if card and card["verdict"] == "NOT_OK":
            false_alarm.append(f"clause {c['label']} {card['rule_ids']}")
    for c in truth["clauses"]:
        for r in c["rules"]:
            rules_total += 1
            card = cards.get(c["label"])
            if (card and r in card["rule_ids"]) or r in all_rules:
                rules_hit += 1
            else:
                rule_misses.append(f"{r} @ {c['label']}")

    money = {}
    if truth["money"]:
        m = result["money"]
        if m:
            money = {"total_err": round(abs(m["total_repayment"] - truth["money"]["total_repayment"]), 2),
                     "apr_err_pp": round(abs(m["apr_pct"] - truth["money"]["apr_pct"]), 2),
                     "apr": m["apr_pct"], "apr_truth": truth["money"]["apr_pct"]}
        else:
            money = {"missing": result["money_error"]}
    if truth.get("rental"):
        t = result["terms"] or {}
        money = {k: (t.get(k), v) for k, v in truth["rental"].items()}

    text = normalize_digits("\n".join(l["text"] for l in s.lines))
    flat = digits(text)
    # A PII item counts as leaked if any 6 consecutive digits of it survive (OCR may mangle
    # the rest), or, for PAN, if the string survives.
    def leaked_item(p: str) -> bool:
        d = digits(p)
        if not d:
            return p in text
        return any(d[i:i + 6] in flat for i in range(len(d) - 5))
    leaked = [p for p in truth["pii"] if leaked_item(p)]
    n_placeholders = sum(text.count(v) for v in PLACEHOLDER.values())
    return {
        "risky": len(risky), "caught": caught, "caught_not_ok": caught_hard, "missed": missed,
        "clean": len(clean), "false_alarms": false_alarm,
        "rules_total": rules_total, "rules_hit": rules_hit, "rule_misses": rule_misses,
        "money": money,
        "pii_total": len(truth["pii"]), "pii_hidden": len(truth["pii"]) - len(leaked), "pii_leaked": leaked,
        "pii_extra": max(0, n_placeholders - len(truth["pii"])),
        "n_clauses_found": len(s.clauses), "n_clauses_truth": len(truth["clauses"]),
    }


def run_one(gemma: Gemma, truth: dict, lines: list[dict], ocr_s: float = 0.0) -> dict:
    t0 = time.perf_counter()
    s = make_session(lines)
    events = list(P.run_analysis(s, gemma, truth["lang"] if truth["lang"] in P.LANGS else "en"))
    result = events[-1]["result"]
    out = score(truth, s, result)
    out["seconds"] = round(time.perf_counter() - t0 + ocr_s, 1)
    out["engine"] = result["engine"]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="both", choices=["text", "image", "both"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip-clean-photos", action="store_true",
                    help="photo mode: only the degraded photos (clean ones behave like text on a slow CPU run)")
    args = ap.parse_args()

    gemma = Gemma()
    engine = "gemma" if gemma.available() else "fallback"
    if engine == "gemma":
        gemma.warmup()
    truths = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(SAMPLES.glob("*.truth.json"))]
    if args.limit:
        truths = truths[: args.limit]

    runs = []
    if args.mode in ("text", "both"):
        for tr in truths:
            text = (SAMPLES / f"{tr['id']}.txt").read_text(encoding="utf-8")
            r = run_one(gemma, tr, lines_from_text(text))
            runs.append({"doc": tr["id"], "input": "text", **r})
            print(f"text  {tr['id']:<28} caught {r['caught']}/{r['risky']}  {r['seconds']}s")

    ocr_ok = ocr.tesseract_status()["available"]
    if args.mode in ("image", "both"):
        if not ocr_ok:
            print("Tesseract not available; skipping image mode.")
        else:
            for tr in truths:
                for photo in sorted(PHOTOS.glob(f"{tr['id']}_*.png")):
                    if args.skip_clean_photos and photo.stem.endswith("_clean"):
                        continue
                    t0 = time.perf_counter()
                    res = ocr.scan(photo.read_bytes())
                    r = run_one(gemma, tr, res["lines"], time.perf_counter() - t0)
                    r["ocr_conf"] = res["meta"]["mean_conf"]
                    r["retake_flag"] = res["quality"]["retake"]
                    runs.append({"doc": tr["id"], "input": photo.stem.split("_")[-1], **r})
                    print(f"image {photo.stem:<36} caught {r['caught']}/{r['risky']}  pii {r['pii_hidden']}/{r['pii_total']}  {r['seconds']}s")

    (ROOT / "eval" / "results.json").write_text(json.dumps(runs, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(runs, engine, gemma.model)


def _agg(rows: list[dict]) -> dict:
    s = lambda k: sum(r[k] for r in rows)  # noqa: E731
    money = [r["money"] for r in rows if "total_err" in r["money"]]
    loans = [r for r in rows if r["money"] and "missing" in r["money"] or "total_err" in r["money"]]
    return {
        "docs": len(rows),
        "caught": f"{s('caught')}/{s('risky')} ({100 * s('caught') / max(1, s('risky')):.0f}%)",
        "caught_not_ok": f"{s('caught_not_ok')}/{s('risky')}",
        "false_alarms": f"{sum(len(r['false_alarms']) for r in rows)}/{s('clean')}",
        "rules": f"{s('rules_hit')}/{s('rules_total')} ({100 * s('rules_hit') / max(1, s('rules_total')):.0f}%)",
        "money_exact": f"{sum(1 for m in money if m['total_err'] <= 1 and m['apr_err_pp'] <= 0.5)}/{len(loans)}",
        "median_apr_err": (sorted(m["apr_err_pp"] for m in money)[len(money) // 2] if money else None),
        "pii": f"{s('pii_hidden')}/{s('pii_total')} ({100 * s('pii_hidden') / max(1, s('pii_total')):.0f}%)",
        "pii_extra": s("pii_extra"),
        "sec_per_doc": round(s("seconds") / max(1, len(rows)), 1),
    }


def write_markdown(runs: list[dict], engine: str, model: str) -> None:
    out = ["# NyayLens evaluation results", "",
           f"- Date: {time.strftime('%Y-%m-%d %H:%M')}",
           f"- Engine: **{engine}**" + (f" (`{model}`, num_ctx {config.NUM_CTX}, temperature {config.TEMPERATURE})"
                                         if engine == "gemma" else " (Ollama not running: keyword fallback, not Gemma)"),
           f"- Machine: {platform.processor() or platform.machine()}, {platform.system()} {platform.release()}",
           f"- OCR: {ocr.tesseract_status().get('version', 'not installed')}, languages {config.OCR_LANGS}",
           "- Data: 9 synthetic contracts (6 loans, 2 rentals, 1 fair control; English, Bengali, Hindi), fake PII only.",
           "", "## Summary", "",
           "| Input | Docs | Risky clauses caught | ...as NOT OK | False alarms (clean marked NOT OK) | Expected rules found | Money exact (±₹1, ±0.5pp) | Median APR error (pp) | PII hidden | Extra redactions | Sec/doc |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    groups: dict[str, list[dict]] = {}
    for r in runs:
        groups.setdefault("text" if r["input"] == "text" else "photo: " + r["input"], []).append(r)
    for name, rows in groups.items():
        a = _agg(rows)
        out.append(f"| {name} | {a['docs']} | {a['caught']} | {a['caught_not_ok']} | {a['false_alarms']} | {a['rules']} | "
                   f"{a['money_exact']} | {a['median_apr_err']} | {a['pii']} | {a['pii_extra']} | {a['sec_per_doc']} |")
    out += ["", "## Known failures (every miss, listed)", ""]
    for r in runs:
        issues = []
        if r["missed"]:
            issues.append("missed: " + ", ".join(r["missed"]))
        if r["false_alarms"]:
            issues.append("false alarm: " + ", ".join(r["false_alarms"]))
        if r["rule_misses"]:
            issues.append("rules not found: " + ", ".join(r["rule_misses"]))
        if r["pii_leaked"]:
            issues.append(f"PII NOT hidden: {len(r['pii_leaked'])}")
        m = r["money"]
        if "missing" in m:
            issues.append(f"money not computed ({m['missing']})")
        elif "total_err" in m and (m["total_err"] > 1 or m["apr_err_pp"] > 0.5):
            issues.append(f"money off: APR {m['apr']} vs {m['apr_truth']}, total error ₹{m['total_err']}")
        elif m and "total_err" not in m:
            bad = {k: v for k, v in m.items() if v[0] != v[1]}
            if bad:
                issues.append(f"rental terms off: {bad}")
        if r["n_clauses_found"] != r["n_clauses_truth"] + 1:
            issues.append(f"clause split: {r['n_clauses_found']} found vs {r['n_clauses_truth']} + header")
        if issues:
            out.append(f"- **{r['doc']}** ({r['input']}): " + "; ".join(issues))
    out += ["", "Bengali explanation clarity (1-5, two native speakers): _not yet rated_.", ""]
    (ROOT / "eval" / "results.md").write_text("\n".join(out), encoding="utf-8")
    print("\nwrote eval/results.md")


if __name__ == "__main__":
    main()
