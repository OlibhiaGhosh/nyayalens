# NyayaLens · ন্যায়লেন্স

**Understand a loan or rent paper before you sign it, offline, in Bengali, Hindi or English.**

Take a photo of a loan or rental contract. NyayaLens hides Aadhaar, PAN and phone numbers, colours each risky clause on the photo, shows **how many rupees you will really pay back**, explains every clause in simple language, reads it aloud, answers questions you type or **speak** in your own language, and drafts a letter asking for fairer terms. It runs on a laptop with **Gemma 4 E4B** through Ollama. No internet is used at any point.

> This is help to understand, not legal advice. For big decisions, talk to a lawyer or call the National Consumer Helpline (1915).

## How it works

```
photo ─► quality check ─► OpenCV cleanup ─► Tesseract (ben+hin+eng) ─► PII redaction ─► clause split
                                                                        (Verhoeff Aadhaar,  + keyword prefilter
                                                                         PAN, phone, email)        │
                ┌──────────────────────────────────────────────────────────────────────────────────┘
                ▼
  Gemma 4 E4B, whole document  ─► money terms as written (no arithmetic)
                │
                ▼
  Python: total repayment + APR (IRR by bisection) ─► shown first, ~30 s in
                │
                ▼
  Gemma 4 E4B, one clause at a time, riskiest first ─► English JSON (verdict, category, rule IDs,
                │                                      fairer rewrite) + Bengali/Hindi explanation
                ▼                                      using a fixed glossary, in ONE call
  rule engine (raises verdicts, never lowers them) ─► curated statutes.json + curated questions
                ▼                                      and requested changes (reviewed text)
  heatmap · clause cards · "3 things to ask" · Piper read-aloud · Q&A · counter-rider (print to PDF) · wipe
```

**Design rule:** OCR finds the text, Gemma understands and explains it, code does the math, and a curated list supplies every legal citation.

- **The model never sees personal data.** Redaction happens right after OCR; Gemma only receives text with `[AADHAAR]`, `[PHONE]` placeholders.
- **The model never does arithmetic.** `backend/apr.py` computes cash in hand, total repayment, extra cost and APR, with the steps shown.
- **The model never writes a citation.** It may only pick rule IDs from an enum in the JSON schema; `rules.py` drops anything else and attaches statutes from `data/statutes.json`.
- **Voice questions are heard by Gemma itself.** The browser records 16 kHz WAV (no cloud speech recognition, no extra speech model), Gemma 4 E4B transcribes it and names the language, the transcript is redacted like OCR text, and the answer comes back in the language the question was asked in, read aloud. The audio is held in memory for that one request only. Gemma does hear the raw voice, so a spoken phone number reaches the model before it is replaced with `[PHONE]` in the transcript. Voice needs Ollama; without it the user is told to type.
- **Every model call has a fallback.** If Ollama is down, keyword rules and curated text in all three languages still produce a (less detailed) result, clearly labelled.

## Quick start (Windows)

One-time setup **with internet**:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -InstallSystemDeps
```

This installs Ollama and Tesseract via winget, creates `.venv`, builds the frontend, downloads Tesseract language packs (`models/tessdata`), Piper voices (`models/piper`), pulls `gemma4:e4b`, and generates the sample contracts.

Low on space on C:? Models are large (E4B is 6.6 GB). Point Ollama at another drive before pulling: set the user environment variable `OLLAMA_MODELS=D:\ollama\models` and restart Ollama. If you move existing models, also end any leftover `llama-server` process, which otherwise keeps ~5 GB of RAM.

Then, **offline**:

```powershell
powershell -ExecutionPolicy Bypass -File run_demo.ps1                 # Gemma 4 E4B
powershell -ExecutionPolicy Bypass -File run_demo.ps1 -Model gemma4:e2b   # slower laptops
```

Open http://127.0.0.1:8000. macOS/Linux: `scripts/setup.sh` then `./run_demo.sh`.

Development: `cd backend && ..\.venv\Scripts\python -m uvicorn main:app --reload --host 127.0.0.1` and `cd frontend && npm run dev` (Vite proxies `/api`).

### Settings (environment variables)

| Variable | Default | |
|---|---|---|
| `NYAYA_MODEL` | `gemma4:e4b` | `gemma4:e2b` for slow machines |
| `NYAYA_NUM_CTX` | `8192` | |
| `NYAYA_TEMPERATURE` | `0.1` | |
| `NYAYA_KEEP_ALIVE` | `60m` | keeps Gemma loaded |
| `NYAYA_THINK` | `0` | Gemma 4 *thinks by default* in Ollama 0.35; the app always sends `think: false` (thinking made each clause ~8x slower on CPU). Set `1` to get the reasoning panel for the single hardest clause |
| `OLLAMA_NUM_PARALLEL` | `2` (set by `run_demo`) | two prompt-cache slots, so the terms prompt and the clause prompt both stay cached |
| `NYAYA_OCR_LANGS` | `ben+hin+eng` | |
| `NYAYA_VOICE_BN` / `_HI` / `_EN` | `bn_BD-google-medium` / `hi_IN-pratham-medium` / `en_US-lessac-medium` | Piper voices |

## Performance on a CPU-only laptop

Measured on the dev laptop (AMD Ryzen, 16 GB RAM, no discrete GPU; Gemma runs entirely on CPU at ~9.5 output tokens/s), Bengali loan contract with 6 clauses:

| Version | Total | Money view appears | First explained clause |
|---|---|---|---|
| First version (thinking on by default, separate analyse + localise calls) | not run in full; one clause took 132 s | at the end | at the end |
| Thinking off, separate calls | 6.3 min | at the end | at the end |
| Money first + streamed cards | 4.8 min | 12 s | 67 s |
| One combined call per clause | 3.5 min | 13 s | 78 s |
| + warmed prompts, 2 cache slots | **3.3 min** | ~30 s | **~63 s** |

What made the difference: turning off Gemma 4's default thinking, showing the rupee figures before any clause analysis, streaming each clause card as soon as it is ready (riskiest first), merging analysis and explanation into one call so Ollama's prompt cache is reused, and taking the questions and requested changes from the curated rule list instead of generating them. A laptop with a GPU will be several times faster.

**E4B vs E2B.** `gemma4:e2b` finished the same document in 2.3 min but made unsafe mistakes: it described handing over blank signed cheques as "a normal part of the agreement", flagged "governed by the laws of India" as a rights waiver, and missed the flat-rate problem. **Use E4B.** Use E2B only if E4B cannot run at all, and say so.

## Evaluation

`python eval/run_eval.py` runs 9 synthetic contracts (in `samples/`, fake data only: 6 loans, 2 rentals, 1 fair control; English, Bengali, Hindi) through the pipeline, as text and as clean/angled/dim/blurry/small-font photos. It writes [`eval/results.md`](eval/results.md).

**Gemma 4 E4B** (Ollama 0.35.1, CPU only, Tesseract 5.4), full run on 2026-10-04 ([`eval/results.md`](eval/results.md)):

| Input | Docs | Risky clauses caught | ...as NOT OK | False alarms | Expected rules found | Money exact | PII hidden | Min/doc |
|---|---|---|---|---|---|---|---|---|
| text | 9 | 33/33 | 26/33 | 1/21 | 37/37 | 6/7 | 19/19 | 2.8 |
| photo: angled | 3 | 15/15 | 10/15 | 0/4 | 18/18 | 3/3 | 6/6 | 2.7 |
| photo: small font | 3 | 15/15 | 10/15 | 0/4 | 18/18 | 3/3 | 6/6 | 2.3 |
| photo: dim | 3 | 10/10 | 8/10 | 1/8 | 10/10 | 1/2 | 6/6 | 2.2 |
| photo: blurry | 3 | 6/8 | 4/8 | 0/9 | 8/9 | 2/2 | 7/7 | 2.3 |

Every failure in that run, and what happened to it:

- **Lump-sum moneylender loan** (02, text and dim photo): Gemma read "one lump sum after 6 months" as one installment due in month 1, giving 216% APR instead of 33.6%. *Fixed after the run* (prompt rule + the pattern reading overrides the model for lump sums); re-checked: 33.56%, matching the truth exactly.
- **Gold loan "auction after 7 days' notice"** (08, text and dim photo) flagged as repossession without notice. *Fixed after the run* (rule hint excludes clauses that give a notice period; a model "OK" can no longer be escalated past CAREFUL by its own rule tag); re-checked: no longer NOT OK.
- **Blurry Bengali photos** (06, 09): OCR read `৪.` as `8.`, so clause 4 merged into clause 3 and was not judged separately, and `৫০,০০০` was read as `40,000`. **Not fixed**: an OCR limit. The app asks for a retake on blurry photos and lets the user correct text and numbers.

The two fixes were re-checked on the affected documents only; the table above is from the full run before them.

Keyword-only fallback (no Gemma), for comparison: [`eval/results_fallback.md`](eval/results_fallback.md).

**Read these numbers with care.** These are 9 contracts we wrote ourselves, and the keyword fallback rules were tuned while looking at them. Before the demo:

1. Have a team member who did not write the rules create 5+ **held-out** contracts and report those numbers separately.
2. Get two native speakers to rate the Bengali explanations (1–5) and record it in `eval/results.md`.

Unit tests: `cd backend && ..\.venv\Scripts\python -m pytest` (APR against textbook EMI values, Verhoeff, PII in Bengali/Devanagari digits, clause splitting, rule engine, offline pipeline, skill sync).

## Legal content and its verification

`data/statutes.json` and `data/rules.json` are hand-curated. Every entry has `source_url`, a `source_hint` saying exactly what to look up, and `last_verified` / `verified_by`, which are **null until a team member checks the official text**. The UI shows "not yet verified by our team" on every unverified citation.

Notably, the app does **not** call a high rate "illegal": RBI sets no single universal rate cap. It flags the gap between the stated and the real cost, missing APR / Key Facts Statement disclosure, compounding penal charges, unilateral changes, repossession without notice, rights waivers, blank cheques, prepayment penalties, high deposits and eviction without notice.

Verification checklist (assign one person per row):

- [ ] `cpa2019_unfair_contract`: CPA 2019 s. 2(46)
- [ ] `cpa2019_redressal`: consumer commissions; arbitration-clause point
- [ ] `ica1872_s28`, `ica1872_s74`: Indian Contract Act
- [ ] `rbi_penal_charges_2023`: RBI circular, 18 Aug 2023
- [ ] `rbi_kfs_2024`: RBI circular, 15 Apr 2024
- [ ] `rbi_fair_practices_code`: Master Directions FPC sections
- [ ] `rbi_foreclosure`: current scope of foreclosure / pre-payment charge rules
- [ ] `model_tenancy_act_2021`: and whether your state adopted it
- [ ] `bengal_moneylenders_1940`: licensing and interest limits
- [ ] helplines: 1915, RBI CMS 14448, Sachet
- [ ] Bengali and Hindi text in `rules.json`, `glossary.json`, `frontend/src/i18n.ts`, by native speakers

## Agent skill

`skills/consumer-justice-audit/` is an Agent Skill (`SKILL.md` + `scripts/apr.py` + `references/`). The script is byte-identical to `backend/apr.py` (a test enforces this; run `python scripts/sync_skill.py` after edits) and runs standalone:

```
python skills/consumer-justice-audit/scripts/apr.py --principal 10000 --n 12 --stated-rate 12 --rate-type flat --text
```

## Making "offline" bulletproof

- `python scripts/download_models.py` fetches every model, language pack and voice once.
- Fonts (Noto Sans Bengali/Devanagari) and icons are bundled from npm; the build contains no CDN links.
- The backend binds to `127.0.0.1`, has no CORS, and rejects other `Host` headers.
- The **Offline check** screen shows Ollama, model, Tesseract languages, voices, and (on click) that the internet is unreachable.
- Rehearse a cold start with Wi-Fi off at least twice, show DevTools → Network with only `127.0.0.1`, and record a backup video.

## What it can't do

- Handwritten contracts, very poor photos, multi-page PDFs, or stamp-paper watermarks over text.
- Unusual dialects, mixed scripts within one word, or legal language not covered by the rule list.
- Complex contracts (mortgages, business loans, guarantees, arbitration details).
- Clause types outside the rule list are judged by the model alone and labelled as such.
- Lump-sum loans whose terms are spread across clauses may need the numbers corrected by hand ("Numbers wrong? Fix them").
- The Bengali voice (`bn_BD`) has a Bangladeshi accent.
- It does not tell anyone whether to sign. It suggests questions to ask and changes to request.

## Repository layout

```
backend/   main.py (FastAPI) ocr.py redact.py clauses.py gemma.py pipeline.py apr.py rules.py tts.py config.py tests/
frontend/  React + Vite + Tailwind v4; src/voice.ts (mic → WAV); src/components: Capture, Review, Heatmap, ClauseCard, MoneyView, Summary, QA, Rider, SelfCheck
data/      statutes.json rules.json glossary.json prompts/
skills/consumer-justice-audit/   SKILL.md scripts/apr.py references/
samples/   make_samples.py, synthetic contracts (.txt, .truth.json, .html), photos/
eval/      run_eval.py results.md results.json
scripts/   setup.ps1 setup.sh download_models.py sync_skill.py
```

License: Apache-2.0.
