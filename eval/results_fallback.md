# NyayLens evaluation results

- Date: 2026-10-04 02:43
- Engine: **fallback** (Ollama not running: keyword fallback, not Gemma)
- Machine: AMD64 Family 25 Model 80 Stepping 0, AuthenticAMD, Windows 11
- OCR: 5.4.0.20240606, languages ben+hin+eng
- Data: 9 synthetic contracts (6 loans, 2 rentals, 1 fair control; English, Bengali, Hindi), fake PII only.

## Summary

| Input            | Docs | Risky clauses caught | ...as NOT OK | False alarms (clean marked NOT OK) | Expected rules found | Money exact (±₹1, ±0.5pp) | Median APR error (pp) | PII hidden   | Extra redactions | Sec/doc |
| ---------------- | ---- | -------------------- | ------------ | ---------------------------------- | -------------------- | ------------------------- | --------------------- | ------------ | ---------------- | ------- |
| text             | 9    | 33/33 (100%)         | 22/33        | 0/21                               | 37/37 (100%)         | 7/7                       | 0.0                   | 19/19 (100%) | 0                | 0.0     |
| photo: angled    | 3    | 15/15 (100%)         | 10/15        | 0/4                                | 18/18 (100%)         | 3/3                       | 0.0                   | 6/6 (100%)   | 0                | 5.6     |
| photo: clean     | 9    | 33/33 (100%)         | 22/33        | 0/21                               | 37/37 (100%)         | 7/7                       | 0.0                   | 19/19 (100%) | 0                | 5.1     |
| photo: smallfont | 3    | 15/15 (100%)         | 10/15        | 0/4                                | 18/18 (100%)         | 3/3                       | 0.0                   | 6/6 (100%)   | 0                | 5.4     |
| photo: dim       | 3    | 10/10 (100%)         | 6/10         | 0/8                                | 10/10 (100%)         | 2/2                       | 0.0                   | 6/6 (100%)   | 0                | 6.0     |
| photo: blurry    | 3    | 6/8 (75%)            | 3/8          | 0/9                                | 8/9 (89%)            | 2/2                       | 0.0                   | 7/7 (100%)   | 0                | 6.9     |

## Known failures (every miss, listed)

- **06_loan_bn** (blurry): missed: clause 4 (MISSING); rules not found: effective_cost_mismatch @ 2
- **09_rental_bn** (blurry): missed: clause 4 (MISSING); rental terms off: {'security_deposit': (40000.0, 50000)}

Bengali explanation clarity (1-5, two native speakers): _not yet rated_.
