"""
Stage 4: the actual test of the repo's core question.

Can a driver-based forecast, built only from data available as of a past
period, beat a naive top-down extrapolation at predicting what actually
happened?

With three fiscal years (2023-2025) there is exactly one honest backtest
point: build the model as of FY2024 — using only the FY2024 report's own
figures (not the later-restated ones; the restated numbers weren't
available yet at the point this forecast is pretending to be made) and
adidas's own stated FY2025 guidance ("high-single-digit rate" currency-
neutral growth, operating profit between €1.7bn and €1.8bn, working
capital 21-22% of sales, capex ~€600m) — forecast FY2025, and compare both
the driver-based forecast and a naive top-down extrapolation against
FY2025 actuals. That is a thin sample — one point, not a track record.

Modeling choices made explicit here, not buried:
- "high-single-digit rate" is interpreted as 8% (the middle of the
  conventional 7-9% band economists use for that phrase), applied
  uniformly across product divisions since the guidance is company-wide,
  not given by division.
- The EBITDA margin needed to hit the guided operating-profit range is
  solved for algebraically (see _margin_for_operating_profit), rather than
  guessed, since adidas doesn't guide EBITDA margin directly.
- No tax-rate guidance is given, so FY2024's actual effective tax rate is
  carried forward as the assumption.
- adidas doesn't report free cash flow as a line item; it's derived the
  same way (NOPAT + D&A - change in working capital - capex) for the
  actual FY2025 result as for both forecasts, so the comparison is
  apples-to-apples rather than comparing a modeled FCF against a
  differently-defined reported number.
"""

from __future__ import annotations

import json

from src import config as C
from src import model


#: A backtest vintage: build the model as of `baseline`, using only that
#: report's own figures and the guidance it published for the year ahead, then
#: compare against what `actual` turned out to be.
#:
#: `growth` is the interpretation of a qualitative guidance phrase, stated per
#: vintage rather than buried in a function. adidas guides currency-neutral
#: sales in words — "mid-single-digit rate", "high-single-digit rate" — and the
#: midpoint of the conventional band is the reading used here.
VINTAGES = {
    "fy2024": {
        "label": "FY2023 → FY2024",
        "baseline": "2023",
        "actual": "2024",
        "guidance": "fy2024_initial",
        "growth": 0.05,          # "mid-single-digit rate"
        "growth_phrase": "mid-single-digit rate",
        "published": "February 2024",
    },
    "fy2025": {
        "label": "FY2024 → FY2025",
        "baseline": "2024",
        "actual": "2025",
        "guidance": "fy2025_initial",
        "growth": 0.08,          # "high-single-digit rate"
        "growth_phrase": "high-single-digit rate",
        "published": "March 2025",
    },
}

DEFAULT_VINTAGE = "fy2025"


def _margin_for_operating_profit(target_operating_profit: float, revenue: float, baseline_da: float, baseline_revenue: float) -> float:
    """Solve for the EBITDA margin (%) that makes
    forecast_operating_profit = revenue*margin - baseline_da*(revenue/baseline_revenue)
    equal target_operating_profit, given model.forecast()'s D&A scaling rule.
    """
    return (target_operating_profit / revenue + baseline_da / baseline_revenue) * 100


def _derive_fcf(operating_profit: float, tax_rate_pct: float, ebitda: float, working_capital: float,
                 prior_working_capital: float, capex: float) -> float:
    da = ebitda - operating_profit
    nopat = operating_profit * (1 - tax_rate_pct / 100)
    change_in_wc = working_capital - prior_working_capital
    return nopat + da - change_in_wc - capex


def naive_baseline(facts: dict, vintage: str = DEFAULT_VINTAGE) -> dict:
    """Extrapolate FY2025 from the FY2024 run-rate only: same nominal
    revenue growth rate as FY2023->FY2024, margins/working-capital%/capex
    held flat at FY2024's actual level. No judgement beyond "more of the
    same"."""
    spec = VINTAGES[vintage]
    baseline_year = int(spec["baseline"])
    g24 = facts["group"][spec["baseline"]]
    prior = facts["group"].get(str(baseline_year - 1))
    if prior is None:
        raise ValueError(
            f"Vintage {vintage!r} needs FY{baseline_year - 1} to extrapolate a run-rate from, "
            f"and the facts document does not carry it."
        )
    g23 = prior
    growth_rate = g24["net_sales"] / g23["net_sales"] - 1

    revenue = g24["net_sales"] * (1 + growth_rate)
    ebitda_margin = g24["ebitda"] / g24["net_sales"]
    ebitda = revenue * ebitda_margin
    da = g24["ebitda"] - g24["operating_profit"]  # held flat, not scaled
    operating_profit = ebitda - da
    tax = operating_profit * g24["effective_tax_rate_pct"] / 100
    nopat = operating_profit - tax
    wc = revenue * g24["operating_working_capital_pct"] / 100
    prior_wc = g24["net_sales"] * g24["operating_working_capital_pct"] / 100
    capex = g24["capex"]
    fcf = nopat + da - (wc - prior_wc) - capex

    return {
        "method": "naive extrapolation",
        "revenue": revenue,
        "ebitda": ebitda,
        "operating_profit": operating_profit,
        "free_cash_flow": fcf,
        "assumptions": {
            "revenue_growth_pct": growth_rate * 100,
            "ebitda_margin_pct": ebitda_margin * 100,
            "operating_working_capital_pct": g24["operating_working_capital_pct"],
            "capex_eur_m": capex,
            "effective_tax_rate_pct": g24["effective_tax_rate_pct"],
        },
    }


def driver_based(facts: dict, vintage: str = DEFAULT_VINTAGE) -> dict:
    """Build the model as of the vintage's baseline year, using that report's
    own figures (not a later restatement) plus adidas's stated guidance for
    the year ahead."""
    spec = VINTAGES[vintage]
    g24 = facts["group"][spec["baseline"]]
    division24 = facts["product_division"][spec["baseline"]]
    guidance = facts["guidance"][spec["guidance"]]

    growth = spec["growth"]  # a guidance phrase, interpreted — see VINTAGES
    division_baseline = {k: v for k, v in division24.items() if k != "source"}
    revenue = sum(v * (1 + growth) for v in division_baseline.values())

    baseline_da = g24["ebitda"] - g24["operating_profit"]
    baseline_revenue = sum(division_baseline.values())
    op_profit_target = (guidance["operating_profit_eur_m_low"] + guidance["operating_profit_eur_m_high"]) / 2
    ebitda_margin_pct = _margin_for_operating_profit(op_profit_target, revenue, baseline_da, baseline_revenue)

    wc_pct = (guidance["operating_working_capital_pct_low"] + guidance["operating_working_capital_pct_high"]) / 2

    assumptions = {
        "division_growth": {k: growth for k in division_baseline},
        "ebitda_margin_pct": ebitda_margin_pct,
        "effective_tax_rate_pct": g24["effective_tax_rate_pct"],  # no guidance given; carried forward
        "operating_working_capital_pct": wc_pct,
        "capex_eur_m": guidance["capex_eur_m"],
    }

    result = model.forecast(g24, division24, assumptions)
    result["method"] = "driver-based (guidance-informed)"
    result["vintage"] = vintage
    return result


def run(vintage: str = DEFAULT_VINTAGE) -> dict:
    if vintage not in VINTAGES:
        raise ValueError(f"Unknown vintage {vintage!r}. Available: {sorted(VINTAGES)}")
    spec = VINTAGES[vintage]
    facts = json.loads((C.FACTS / "adidas_drivers.json").read_text())

    naive = naive_baseline(facts, vintage)
    driven = driver_based(facts, vintage)

    actual = facts["group"][spec["actual"]]
    baseline = facts["group"][spec["baseline"]]
    actual_wc = actual["net_sales"] * actual["operating_working_capital_pct"] / 100
    prior_wc = baseline["net_sales"] * baseline["operating_working_capital_pct"] / 100
    actual_fcf = _derive_fcf(
        actual["operating_profit"], actual["effective_tax_rate_pct"], actual["ebitda"],
        actual_wc, prior_wc, actual["capex"],
    )

    def pct_error(forecast_value, actual_value):
        return (forecast_value - actual_value) / actual_value * 100

    comparison = {
        "vintage": vintage,
        "label": spec["label"],
        "baseline_year": f"FY{spec['baseline']}",
        "forecast_year": f"FY{spec['actual']}",
        "guidance_published": spec["published"],
        "guidance_phrase": spec["growth_phrase"],
        "actual": {
            "revenue": actual["net_sales"],
            "operating_profit": actual["operating_profit"],
            "free_cash_flow": actual_fcf,
        },
        "naive": {
            "revenue": naive["revenue"],
            "operating_profit": naive["operating_profit"],
            "free_cash_flow": naive["free_cash_flow"],
            "revenue_error_pct": pct_error(naive["revenue"], actual["net_sales"]),
            "operating_profit_error_pct": pct_error(naive["operating_profit"], actual["operating_profit"]),
            "free_cash_flow_error_pct": pct_error(naive["free_cash_flow"], actual_fcf),
        },
        "driver_based": {
            "revenue": driven["revenue"],
            "operating_profit": driven["operating_profit"],
            "free_cash_flow": driven["free_cash_flow"],
            "revenue_error_pct": pct_error(driven["revenue"], actual["net_sales"]),
            "operating_profit_error_pct": pct_error(driven["operating_profit"], actual["operating_profit"]),
            "free_cash_flow_error_pct": pct_error(driven["free_cash_flow"], actual_fcf),
        },
    }
    return comparison


def run_all() -> list[dict]:
    """Every vintage, oldest first.

    Two points is still a thin sample, and the README says so. It is enough to
    show one thing a single point cannot: whether a miss repeats. It does —
    both vintages undershoot, because both are anchored on guidance adidas set
    conservatively and then beat.
    """
    return [run(v) for v in VINTAGES]


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
    print()
    print(f"{'metric':<20}{'naive error':>15}{'driver-based error':>22}")
    for metric in ("revenue", "operating_profit", "free_cash_flow"):
        n = result["naive"][f"{metric}_error_pct"]
        d = result["driver_based"][f"{metric}_error_pct"]
        print(f"{metric:<20}{n:>14.1f}%{d:>21.1f}%")
