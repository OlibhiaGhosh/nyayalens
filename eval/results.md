# NyayaLens evaluation results

- Date: 2026-10-04 03:40
- Engine: **gemma** (`gemma4:e4b`, num_ctx 8192, temperature 0.1)
- Machine: AMD64 Family 25 Model 80 Stepping 0, AuthenticAMD, Windows 11
- OCR: 5.4.0.20240606, languages ben+hin+eng
- Data: 9 synthetic contracts (6 loans, 2 rentals, 1 fair control; English, Bengali, Hindi), fake PII only.

## Summary

| Input | Docs | Risky clauses caught | ...as NOT OK | False alarms (clean marked NOT OK) | Expected rules found | Money exact (±₹1, ±0.5pp) | Median APR error (pp) | PII hidden | Extra redactions | Sec/doc |
|---|---|---|---|---|---|---|---|---|---|---|
| text | 9 | 33/33 (100%) | 26/33 | 1/21 | 37/37 (100%) | 6/7 | 0.0 | 19/19 (100%) | 0 | 165.2 |
| photo: angled | 3 | 15/15 (100%) | 10/15 | 0/4 | 18/18 (100%) | 3/3 | 0.0 | 6/6 (100%) | 0 | 159.5 |
| photo: smallfont | 3 | 15/15 (100%) | 10/15 | 0/4 | 18/18 (100%) | 3/3 | 0.0 | 6/6 (100%) | 0 | 138.8 |
| photo: dim | 3 | 10/10 (100%) | 8/10 | 1/8 | 10/10 (100%) | 1/2 | 182.44 | 6/6 (100%) | 0 | 131.9 |
| photo: blurry | 3 | 6/8 (75%) | 4/8 | 0/9 | 8/9 (89%) | 2/2 | 0.0 | 7/7 (100%) | 0 | 138.4 |

## Known failures (every miss, listed)

- **02_moneylender_gold_en** (text): money off: APR 216.0 vs 33.56, total error ₹0.0
- **08_gold_loan_en** (text): false alarm: clause 4 ['repossession_without_notice']
- **02_moneylender_gold_en** (dim): money off: APR 216.0 vs 33.56, total error ₹0.0
- **06_loan_bn** (blurry): missed: clause 4 (MISSING); rules not found: effective_cost_mismatch @ 2
- **08_gold_loan_en** (dim): false alarm: clause 4 ['repossession_without_notice']
- **09_rental_bn** (blurry): missed: clause 4 (MISSING); rental terms off: {'security_deposit': (40000.0, 50000)}

Bengali explanation clarity (1-5, two native speakers): _not yet rated_.
