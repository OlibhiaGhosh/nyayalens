"""
Deterministic loan-cost math for NyayaLens.

The language model never does arithmetic. Every rupee figure and rate the
borrower sees comes from this file.

Stdlib only, so the same file ships as
skills/consumer-justice-audit/scripts/apr.py and an agent can run it directly:

    python apr.py --principal 10000 --fees 500 --installment 1000 --n 12
    python apr.py --principal 10000 --n 12 --stated-rate 12 --rate-type flat
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass, field

PERIODS_PER_YEAR = {
    "daily": 365,
    "weekly": 52,
    "fortnightly": 26,
    "monthly": 12,
    "quarterly": 4,
    "yearly": 1,
}
UNIT = {
    "daily": "day",
    "weekly": "week",
    "fortnightly": "fortnight",
    "monthly": "month",
    "quarterly": "quarter",
    "yearly": "year",
}
# How a rate quoted "per X" converts to a per-year figure.
RATE_PERIOD_PER_YEAR = {"day": 365, "week": 52, "month": 12, "year": 1}


@dataclass
class Step:
    key: str  # stable id; the frontend translates using `values`
    text: str  # English rendering
    values: dict = field(default_factory=dict)


@dataclass
class LoanCost:
    principal: float
    upfront_fees: float
    cash_in_hand: float
    installment: float
    num_installments: int
    frequency: str
    balloon: float
    total_repayment: float
    extra_cost: float
    periodic_rate_pct: float
    apr_pct: float  # nominal yearly rate = periodic rate x periods per year
    effective_annual_pct: float  # with compounding
    stated_rate_pct: float | None
    stated_rate_period: str | None
    stated_rate_type: str | None
    stated_annual_pct: float | None
    installment_source: str  # "document" | "computed_from_stated_rate"
    steps: list[Step]
    warnings: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _rupees(x: float) -> str:
    return f"Rs {x:,.2f}" if abs(x - round(x)) > 0.004 else f"Rs {x:,.0f}"


def flat_installment(principal: float, annual_rate_pct: float, n: int, frequency: str) -> float:
    """Flat rate: interest charged on the full original amount for the whole term."""
    years = n / PERIODS_PER_YEAR[frequency]
    total_interest = principal * annual_rate_pct / 100 * years
    return (principal + total_interest) / n


def reducing_installment(principal: float, annual_rate_pct: float, n: int, frequency: str) -> float:
    """Reducing balance (standard EMI): interest only on what is still owed."""
    r = annual_rate_pct / 100 / PERIODS_PER_YEAR[frequency]
    if r == 0:
        return principal / n
    return principal * r / (1 - (1 + r) ** -n)


def _present_value(r: float, installment: float, n: int, balloon: float) -> float:
    if r == 0:
        return installment * n + balloon
    # expm1/log1p keep precision when r is close to zero.
    log_growth = n * math.log1p(r)
    return installment * -math.expm1(-log_growth) / r + balloon * math.exp(-log_growth)


def periodic_rate(cash_in_hand: float, installment: float, n: int, balloon: float = 0.0) -> float:
    """
    Rate per period r such that the payments, discounted at r, equal the cash
    actually received. Solved by bisection (present value falls as r rises).
    """
    def f(r: float) -> float:
        return _present_value(r, installment, n, balloon) - cash_in_hand

    lo, hi = -0.99, 1.0
    while f(hi) > 0:
        hi *= 2
        if hi > 1e6:
            raise ValueError("rate too high to solve; check the numbers")
    if f(lo) < 0:
        raise ValueError("payments are far smaller than the loan; check the numbers")
    for _ in range(400):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-13:
            break
    return (lo + hi) / 2


def compute_loan_cost(
    principal: float,
    num_installments: int,
    *,
    installment: float | None = None,
    frequency: str = "monthly",
    upfront_fees: float = 0.0,
    balloon: float = 0.0,
    stated_rate_pct: float | None = None,
    stated_rate_period: str = "year",
    rate_type: str = "flat",
) -> LoanCost:
    """
    principal         amount written on the paper
    upfront_fees      processing/insurance/"file" charges taken at the start
                      (deducted from the loan or paid in cash; same effect)
    installment       amount per payment, if the paper states it
    balloon           extra lump sum due with the last payment
    stated_rate_pct   the rate written on the paper, e.g. 12 or 2
    stated_rate_period  "year" | "month" | "week" | "day"  (12% per year, 2% per month ...)
    rate_type         "flat" | "reducing" | "unknown"
    """
    if frequency not in PERIODS_PER_YEAR:
        raise ValueError(f"frequency must be one of {sorted(PERIODS_PER_YEAR)}")
    if principal <= 0:
        raise ValueError("principal must be positive")
    if num_installments < 1:
        raise ValueError("num_installments must be at least 1")
    if stated_rate_period not in RATE_PERIOD_PER_YEAR:
        raise ValueError(f"stated_rate_period must be one of {sorted(RATE_PERIOD_PER_YEAR)}")

    warnings: list[str] = []
    ppy = PERIODS_PER_YEAR[frequency]
    unit = UNIT[frequency]
    n = int(num_installments)

    stated_annual = None
    if stated_rate_pct is not None:
        stated_annual = stated_rate_pct * RATE_PERIOD_PER_YEAR[stated_rate_period]

    if installment is None:
        if stated_annual is None:
            raise ValueError("need either the installment amount or the stated rate")
        if rate_type == "reducing":
            installment = reducing_installment(principal, stated_annual, n, frequency)
        else:
            if rate_type != "flat":
                warnings.append("rate_type_assumed_flat")
            installment = flat_installment(principal, stated_annual, n, frequency)
        source = "computed_from_stated_rate"
    else:
        source = "document"

    cash = principal - upfront_fees
    if cash <= 0:
        raise ValueError("fees are larger than the loan")

    total = installment * n + balloon
    extra = total - cash
    r = periodic_rate(cash, installment, n, balloon)
    apr = r * ppy * 100
    eff = ((1 + r) ** ppy - 1) * 100

    steps: list[Step] = []
    if upfront_fees:
        steps.append(Step(
            "cash_in_hand",
            f"Loan {_rupees(principal)} - fees taken at start {_rupees(upfront_fees)} = {_rupees(cash)} in your hand",
            {"principal": principal, "fees": upfront_fees, "cash": cash},
        ))
    else:
        steps.append(Step("cash_in_hand_nofee", f"You receive {_rupees(cash)}", {"cash": cash}))
    if source == "computed_from_stated_rate":
        steps.append(Step(
            "installment_from_rate",
            f"Paper says {stated_rate_pct:g}% per {stated_rate_period} ({rate_type}), so each payment is {_rupees(installment)}",
            {"rate": stated_rate_pct, "period": stated_rate_period, "rate_type": rate_type, "installment": installment},
        ))
    steps.append(Step(
        "installments",
        f"{n} payments (one per {unit}) x {_rupees(installment)} = {_rupees(installment * n)}",
        {"n": n, "unit": unit, "installment": installment, "subtotal": installment * n},
    ))
    if balloon:
        steps.append(Step("balloon", f"Plus a last lump sum of {_rupees(balloon)}", {"balloon": balloon}))
    steps.append(Step("total_repayment", f"Total you pay back: {_rupees(total)}", {"total": total}))
    steps.append(Step(
        "extra_cost",
        f"{_rupees(total)} - {_rupees(cash)} = {_rupees(extra)} extra",
        {"total": total, "cash": cash, "extra": extra},
    ))
    steps.append(Step(
        "periodic_rate",
        f"The rate per {unit} that turns {_rupees(cash)} into these payments is {r * 100:.3f}%",
        {"rate": r * 100, "unit": unit, "cash": cash},
    ))
    steps.append(Step(
        "apr",
        f"{r * 100:.3f}% x {ppy} {unit}s in a year = {apr:.1f}% per year (APR)",
        {"periodic": r * 100, "ppy": ppy, "unit": unit, "apr": apr},
    ))
    if stated_annual is not None:
        steps.append(Step(
            "stated",
            f"The paper says {stated_rate_pct:g}% per {stated_rate_period} = {stated_annual:.1f}% per year",
            {"rate": stated_rate_pct, "period": stated_rate_period, "annual": stated_annual},
        ))

    return LoanCost(
        principal=principal,
        upfront_fees=upfront_fees,
        cash_in_hand=cash,
        installment=round(installment, 2),
        num_installments=n,
        frequency=frequency,
        balloon=balloon,
        total_repayment=round(total, 2),
        extra_cost=round(extra, 2),
        periodic_rate_pct=round(r * 100, 4),
        apr_pct=round(apr, 2),
        effective_annual_pct=round(eff, 2),
        stated_rate_pct=stated_rate_pct,
        stated_rate_period=stated_rate_period if stated_rate_pct is not None else None,
        stated_rate_type=rate_type if stated_rate_pct is not None else None,
        stated_annual_pct=round(stated_annual, 2) if stated_annual is not None else None,
        installment_source=source,
        steps=steps,
        warnings=warnings,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Compute the true cost of a loan (total repayment and APR).")
    p.add_argument("--principal", type=float, required=True, help="loan amount written on the paper")
    p.add_argument("--n", type=int, required=True, help="number of installments")
    p.add_argument("--installment", type=float, help="amount per installment, if stated")
    p.add_argument("--frequency", default="monthly", choices=sorted(PERIODS_PER_YEAR))
    p.add_argument("--fees", type=float, default=0.0, help="fees taken at the start")
    p.add_argument("--balloon", type=float, default=0.0, help="extra lump sum with the last payment")
    p.add_argument("--stated-rate", type=float, help="rate written on the paper, e.g. 12")
    p.add_argument("--stated-rate-period", default="year", choices=sorted(RATE_PERIOD_PER_YEAR))
    p.add_argument("--rate-type", default="flat", choices=["flat", "reducing", "unknown"])
    p.add_argument("--text", action="store_true", help="print the steps as text instead of JSON")
    a = p.parse_args(argv)
    try:
        res = compute_loan_cost(
            a.principal, a.n,
            installment=a.installment, frequency=a.frequency, upfront_fees=a.fees,
            balloon=a.balloon, stated_rate_pct=a.stated_rate,
            stated_rate_period=a.stated_rate_period, rate_type=a.rate_type,
        )
    except ValueError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 2
    if a.text:
        for s in res.steps:
            print("-", s.text)
    else:
        print(json.dumps(res.to_dict(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
