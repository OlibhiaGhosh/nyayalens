import pytest

from apr import compute_loan_cost, flat_installment, main, periodic_rate, reducing_installment


def test_reducing_rate_round_trips():
    inst = reducing_installment(100_000, 12, 12, "monthly")
    assert inst == pytest.approx(8884.88, abs=0.01)  # textbook EMI
    res = compute_loan_cost(100_000, 12, installment=inst)
    assert res.apr_pct == pytest.approx(12.0, abs=0.01)


def test_flat_12_is_about_21_5_apr():
    res = compute_loan_cost(10_000, 12, stated_rate_pct=12, rate_type="flat")
    assert res.installment == pytest.approx(933.33, abs=0.01)
    assert res.total_repayment == pytest.approx(11_200, abs=0.05)
    assert 21.0 < res.apr_pct < 22.0
    assert res.installment_source == "computed_from_stated_rate"


def test_fees_deducted_raise_cost():
    no_fee = compute_loan_cost(10_000, 12, installment=1000)
    fee = compute_loan_cost(10_000, 12, installment=1000, upfront_fees=1000)
    assert fee.cash_in_hand == 9000
    assert fee.extra_cost == 3000
    assert fee.apr_pct > no_fee.apr_pct


def test_weekly_microloan():
    # Rs 10,000, Rs 500 fee, 25 weekly payments of Rs 500 -> total 12,500
    res = compute_loan_cost(10_000, 25, installment=500, frequency="weekly", upfront_fees=500)
    assert res.total_repayment == 12_500
    assert res.extra_cost == 3_000
    assert res.apr_pct > 50


def test_single_lump_sum_moneylender():
    # Borrow 10,000, repay 12,000 after one month: 20% per month
    res = compute_loan_cost(10_000, 1, installment=12_000)
    assert res.periodic_rate_pct == pytest.approx(20.0, abs=1e-6)
    assert res.apr_pct == pytest.approx(240.0, abs=1e-4)


def test_stated_monthly_rate_converted():
    res = compute_loan_cost(10_000, 10, stated_rate_pct=2, stated_rate_period="month", rate_type="flat")
    assert res.stated_annual_pct == 24
    assert res.apr_pct > 24


def test_unknown_rate_type_warns_and_assumes_flat():
    res = compute_loan_cost(10_000, 12, stated_rate_pct=12, rate_type="unknown")
    assert "rate_type_assumed_flat" in res.warnings
    assert res.installment == pytest.approx(flat_installment(10_000, 12, 12, "monthly"), abs=0.01)


def test_balloon():
    res = compute_loan_cost(10_000, 12, installment=100, balloon=10_000)
    assert res.total_repayment == 11_200
    assert res.periodic_rate_pct == pytest.approx(1.0, abs=1e-6)


def test_zero_interest():
    assert periodic_rate(1200, 100, 12) == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize("kwargs", [
    {"principal": 0, "num_installments": 12, "installment": 100},
    {"principal": 1000, "num_installments": 0, "installment": 100},
    {"principal": 1000, "num_installments": 12},
    {"principal": 1000, "num_installments": 12, "installment": 100, "upfront_fees": 1000},
    {"principal": 1000, "num_installments": 12, "installment": 100, "frequency": "hourly"},
])
def test_bad_input(kwargs):
    with pytest.raises(ValueError):
        compute_loan_cost(**kwargs)


def test_cli_json(capsys):
    assert main(["--principal", "10000", "--n", "12", "--installment", "1000", "--fees", "500"]) == 0
    assert '"apr_pct"' in capsys.readouterr().out
