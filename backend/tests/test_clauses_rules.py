import pipeline as P
import rules as R
from clauses import lines_from_text, prefilter, split_clauses

SAMPLE = """LOAN AGREEMENT
Between Sri Lender Finance and the Borrower.
1. Loan amount: Rs 10,000 (Rupees ten thousand). A processing fee of Rs 500 will be deducted at disbursal.
2. Interest at 12% per annum flat. Repayable in 12 monthly installments of Rs 933.
3. Late payment: penal interest of 3% per month will be added and compounded monthly on overdue amounts.
4. The Lender may change the interest rate and charges at its sole discretion without notice.
5. The Borrower shall hand over two blank cheques signed in advance.
6. The Borrower waives the right to approach any court or consumer forum.
7. This agreement is governed by the laws of India.
"""


def test_split_numbered():
    cl = split_clauses(lines_from_text(SAMPLE))
    assert [c["label"] for c in cl] == ["", "1", "2", "3", "4", "5", "6", "7"]
    assert cl[0]["text"].startswith("LOAN AGREEMENT")


def test_decimal_and_date_lines_do_not_start_clauses():
    text = "1. Interest is\n1.5% per month from\n15-08-2026 onwards.\n2. Second clause here."
    cl = split_clauses(lines_from_text(text))
    assert [c["label"] for c in cl] == ["1", "2"]


def test_bengali_numbering():
    text = "১. ঋণের পরিমাণ ১০,০০০ টাকা।\n২. দেরি হলে জরিমানা দিতে হবে।\n৩। ঋণদাতা যে কোনো সময় সুদের হার পরিবর্তন করতে পারবে।"
    cl = split_clauses(lines_from_text(text))
    assert [c["label"] for c in cl] == ["1", "2", "3"]
    assert "unilateral_change" in cl[2]["categories"]


def test_paragraph_fallback():
    cl = split_clauses(lines_from_text("First para line\ncontinues\n\nSecond para"))
    assert len(cl) == 2


def test_prefilter_scores_strong_terms():
    cats, score = prefilter("The Lender may revise charges at its sole discretion without notice")
    assert "unilateral_change" in cats and score >= 6


def test_deterministic_rule_hits():
    cl = split_clauses(lines_from_text(SAMPLE))
    hits = {c["label"]: R.clause_deterministic_hits(c["text"]) for c in cl}
    assert "penal_compounding" in hits["3"]
    assert "blank_documents" in hits["5"]
    assert "flat_rate_presented" in hits["2"]
    assert hits["7"] == []


def test_flat_apartment_is_not_flat_rate():
    assert R.clause_deterministic_hits("The tenant shall occupy the flat on the 2nd floor.") == []


def test_finalize_rules_raise_never_lower():
    f = R.finalize({"verdict": "OK", "rule_ids": []}, "penal interest compounded on overdue amounts")
    assert f["verdict"] == "NOT_OK" and f["verdict_source"] == "raised_by_rules"
    f = R.finalize({"verdict": "NOT_OK", "rule_ids": ["made_up_rule"]}, "plain clause")
    assert f["verdict"] == "NOT_OK" and f["rule_ids"] == []
    f = R.finalize({"verdict": "CAREFUL", "rule_ids": ["rights_waiver"]}, "x")
    assert "ica1872_s28" in f["statute_ids"]
    # Model says OK but tags a NOT_OK rule: capped at CAREFUL.
    f = R.finalize({"verdict": "OK", "rule_ids": ["repossession_without_notice"]}, "auction after 7 days' notice")
    assert f["verdict"] == "CAREFUL"


def test_every_rule_references_known_statutes_and_has_all_languages():
    for rid, r in R.RULES.items():
        for s in r["statute_ids"]:
            assert s in R.STATUTES, (rid, s)
        for key in ("name", "plain", "ask_to_change", "questions"):
            assert set(r[key]) >= {"en", "bn", "hi"}, (rid, key)
        for lang in ("en", "bn", "hi"):
            assert 2 <= len(r["questions"][lang]) <= 3


def test_regex_terms_and_money():
    cl = split_clauses(lines_from_text(SAMPLE))
    t = P._clean_terms(P.regex_terms(cl))
    assert t["principal"] == 10_000
    assert t["upfront_fees"] == 500
    assert t["num_installments"] == 12
    assert t["stated_rate_pct"] == 12 and t["stated_rate_period"] == "year"
    assert t["rate_type"] == "flat"
    money, err = P.compute_money(t)
    assert err is None and money["apr_pct"] > 25
    hits = {h["rule_id"] for h in R.doc_level_hits(SAMPLE, t, money)}
    assert {"effective_cost_mismatch", "missing_apr_disclosure"} <= hits


def test_rental_deposit_rule():
    hits = R.doc_level_hits("rent agreement", {"doc_type": "rental", "monthly_rent": 5000,
                                                "security_deposit": 30000}, None)
    assert hits[0]["rule_id"] == "excessive_security_deposit"


class _Offline:
    model = "offline"

    def available(self):
        return False


def test_full_pipeline_offline_fallback():
    s = P.Session()
    s.lines = lines_from_text(SAMPLE)
    s.clauses = split_clauses(s.lines)
    events = list(P.run_analysis(s, _Offline(), "bn"))
    assert events[0]["engine"] == "fallback"
    res = events[-1]["result"]
    by_label = {c["label"]: c for c in res["cards"]}
    assert by_label["3"]["verdict"] == "NOT_OK"
    assert by_label["5"]["verdict"] == "NOT_OK"
    assert by_label["3"]["statutes"][0]["id"] == "rbi_penal_charges_2023"
    # Cost mismatch belongs on the interest clause, not the late-fee clause that mentions "interest".
    assert "effective_cost_mismatch" in by_label["2"]["rule_ids"]
    assert "effective_cost_mismatch" not in by_label["3"]["rule_ids"]
    # Offline keyword rules still catch the obvious ones.
    assert by_label["4"]["verdict"] == "NOT_OK" and by_label["6"]["verdict"] == "NOT_OK"
    assert by_label["7"]["verdict"] == "OK"
    assert len(res["summary"]) == 3
    assert all(q["question"] for q in res["summary"])
    assert res["money"]["total_repayment"] > 10_000


def test_qa_fallback_not_found():
    s = P.Session()
    s.clauses = split_clauses(lines_from_text(SAMPLE))
    out = P.answer_question(_Offline(), s, "Is there a guarantor needed?", "en")
    assert out["found"] is False
    out = P.answer_question(_Offline(), s, "Can the lender change the interest rate?", "en")
    assert out["found"] and out["clause_ids"]
