"""
Stage 2: the driver-based forecast.

Takes a baseline year's facts (product-division and channel revenue split,
margins, working capital %, capex, tax rate) plus a set of explicit,
visible growth/margin assumptions for the forecast period, and traces them
through to EBITDA and free cash flow — the same separation of reported
facts vs. planning assumptions vs. calculated outputs used throughout this
portfolio.

The chain, bottom-up:
    baseline revenue by division × (1 + growth assumption per division)
    -> forecast revenue
    -> forecast EBITDA = forecast revenue × assumed EBITDA margin
    -> D&A: held at the baseline year's D&A run-rate (EBITDA - operating
       profit), scaled by the revenue growth ratio, since D&A tracks asset
       base more than sales but no better driver is available from what's
       disclosed
    -> forecast operating profit = EBITDA - D&A
    -> tax = operating profit × assumed effective tax rate
    -> NOPAT = operating profit - tax
    -> working capital investment = revenue x assumed working-capital % of
       sales, and the CHANGE in that balance versus the baseline year is
       a cash outflow (or inflow, if working capital as a % of sales falls)
    -> free cash flow = NOPAT + D&A - change in working capital - capex

FCF here is a derived construction (NOPAT + D&A - ΔWC - capex), not a
number adidas discloses directly — adidas reports operating cash flow and
capex separately. That derivation is a modeling choice, stated here rather
than presented as if adidas reported "free cash flow" itself.
"""

from __future__ import annotations


def _revenue_by_division(baseline_division: dict, growth_assumptions: dict) -> dict:
    """baseline_division: {"footwear": 14232, "apparel": 8764, "accessories": 1815}
    growth_assumptions: {"footwear": 0.08, "apparel": 0.08, "accessories": 0.08}
    (fractional growth, e.g. 0.08 = 8%)
    """
    return {
        division: value * (1 + growth_assumptions[division])
        for division, value in baseline_division.items()
    }


def forecast(baseline_group: dict, baseline_division: dict, assumptions: dict) -> dict:
    """
    baseline_group: one year's entry from facts["group"], e.g. facts["group"]["2024"]
    baseline_division: one year's entry from facts["product_division"], excluding "source"
    assumptions: {
        "division_growth": {"footwear": 0.08, "apparel": 0.08, "accessories": 0.08},
        "ebitda_margin_pct": 13.2,
        "effective_tax_rate_pct": 25.0,
        "operating_working_capital_pct": 21.5,
        "capex_eur_m": 600,
    }

    Returns a dict of calculated outputs, each traceable to the fact or
    assumption that produced it (kept in the "trace" field).
    """
    division_baseline = {k: v for k, v in baseline_division.items() if k != "source"}
    revenue_by_division = _revenue_by_division(division_baseline, assumptions["division_growth"])
    revenue = sum(revenue_by_division.values())

    ebitda = revenue * assumptions["ebitda_margin_pct"] / 100

    baseline_revenue = sum(division_baseline.values())
    baseline_da = baseline_group["ebitda"] - baseline_group["operating_profit"]
    da = baseline_da * (revenue / baseline_revenue)

    operating_profit = ebitda - da
    tax = operating_profit * assumptions["effective_tax_rate_pct"] / 100
    nopat = operating_profit - tax

    baseline_wc = baseline_group["net_sales"] * baseline_group["operating_working_capital_pct"] / 100
    forecast_wc = revenue * assumptions["operating_working_capital_pct"] / 100
    change_in_wc = forecast_wc - baseline_wc

    capex = assumptions["capex_eur_m"]
    fcf = nopat + da - change_in_wc - capex

    return {
        "revenue_by_division": revenue_by_division,
        "revenue": revenue,
        "ebitda": ebitda,
        "da": da,
        "operating_profit": operating_profit,
        "tax": tax,
        "nopat": nopat,
        "operating_working_capital": forecast_wc,
        "change_in_working_capital": change_in_wc,
        "capex": capex,
        "free_cash_flow": fcf,
        "assumptions": assumptions,
        "baseline_year_used": baseline_group.get("source"),
    }
