"""
Stage 3: scenario ranges and Monte Carlo.

With only three fiscal years, estimating each driver's volatility from
historical data would mean computing a "standard deviation" from two
year-over-year observations — a number that looks precise but carries
almost no statistical information. Rather than manufacture false
precision, the ranges used here come from adidas's own disclosed FY2025
guidance bands where one exists (revenue growth interpreted as 7-9% for
"high-single-digit rate"; operating profit given directly as €1.7-1.8bn,
converted to an equivalent EBITDA-margin range; working capital given
directly as 21-22% of sales) — real disclosed uncertainty, not invented
statistical uncertainty. Capex has no disclosed range (guided as a single
point, "~€600 million"), so a ±5% band is assumed around it and flagged as
such, not measured.

The point of the simulation is which assumption explains the most output
variance in free cash flow — reported via each input's correlation with
the FCF outcome across the run — not the simulation for its own sake.
"""

from __future__ import annotations

import json

import numpy as np

from src import config as C
from src import model


def _margin_for_operating_profit(target_operating_profit, revenue, baseline_da, baseline_revenue):
    return (target_operating_profit / revenue + baseline_da / baseline_revenue) * 100


def build_assumption_ranges(facts: dict) -> dict:
    g24 = facts["group"]["2024"]
    division24 = {k: v for k, v in facts["product_division"]["2024"].items() if k != "source"}
    guidance = facts["guidance"]["fy2025_initial"]

    baseline_revenue = sum(division24.values())
    baseline_da = g24["ebitda"] - g24["operating_profit"]

    # Revenue growth ~ triangular(7%, 8%, 9%) -- "high-single-digit rate"
    growth_low, growth_mode, growth_high = 0.07, 0.08, 0.09

    # Operating-profit guidance converted to the equivalent EBITDA-margin
    # range, via the same D&A-scaling relationship model.forecast() uses,
    # so the sampled margin is consistent with the sampled growth rate at
    # each draw (not two independently sampled numbers that could imply an
    # inconsistent D&A figure).
    op_low, op_high = guidance["operating_profit_eur_m_low"], guidance["operating_profit_eur_m_high"]

    return {
        "growth": (growth_low, growth_mode, growth_high),
        "operating_profit_range": (op_low, op_high),
        "working_capital_pct_range": (
            guidance["operating_working_capital_pct_low"],
            guidance["operating_working_capital_pct_high"],
        ),
        "capex_range": (guidance["capex_eur_m"] * 0.95, guidance["capex_eur_m"] * 1.05),
        "baseline_revenue": baseline_revenue,
        "baseline_da": baseline_da,
        "division24": division24,
        "g24": g24,
        "tax_rate_pct": g24["effective_tax_rate_pct"],  # held fixed — no disclosed range
    }


def run_monte_carlo(facts: dict, n: int = 10_000, seed: int = 0) -> dict:
    ranges = build_assumption_ranges(facts)
    rng = np.random.default_rng(seed)

    growth_low, growth_mode, growth_high = ranges["growth"]
    growths = rng.triangular(growth_low, growth_mode, growth_high, n)
    op_low, op_high = ranges["operating_profit_range"]
    op_targets = rng.uniform(op_low, op_high, n)
    wc_low, wc_high = ranges["working_capital_pct_range"]
    wc_pcts = rng.uniform(wc_low, wc_high, n)
    capex_low, capex_high = ranges["capex_range"]
    capexes = rng.uniform(capex_low, capex_high, n)

    fcfs = np.empty(n)
    revenues = np.empty(n)
    for i in range(n):
        revenue = sum(v * (1 + growths[i]) for v in ranges["division24"].values())
        margin = _margin_for_operating_profit(op_targets[i], revenue, ranges["baseline_da"], ranges["baseline_revenue"])
        assumptions = {
            "division_growth": {k: growths[i] for k in ranges["division24"]},
            "ebitda_margin_pct": margin,
            "effective_tax_rate_pct": ranges["tax_rate_pct"],
            "operating_working_capital_pct": wc_pcts[i],
            "capex_eur_m": capexes[i],
        }
        out = model.forecast(ranges["g24"], facts["product_division"]["2024"], assumptions)
        fcfs[i] = out["free_cash_flow"]
        revenues[i] = revenue

    def corr(x):
        return float(np.corrcoef(x, fcfs)[0, 1])

    sensitivity = {
        "growth": corr(growths),
        "operating_profit_target": corr(op_targets),
        "working_capital_pct": corr(wc_pcts),
        "capex": corr(capexes),
    }

    return {
        "n": n,
        "fcf_p10": float(np.percentile(fcfs, 10)),
        "fcf_p50": float(np.percentile(fcfs, 50)),
        "fcf_p90": float(np.percentile(fcfs, 90)),
        "fcf_mean": float(np.mean(fcfs)),
        "fcf_std": float(np.std(fcfs)),
        "sensitivity_to_fcf": dict(sorted(sensitivity.items(), key=lambda kv: -abs(kv[1]))),
        "caveat": (
            "Ranges are adidas's own disclosed FY2025 guidance bands, not "
            "historical volatility -- three fiscal years is too few to "
            "estimate volatility honestly. Capex has no disclosed range; "
            "a +/-5% band was assumed around the guided point figure."
        ),
        "fcf_draws": fcfs,  # raw array, for charting — stripped before any JSON dump
    }


if __name__ == "__main__":
    facts = json.loads((C.FACTS / "adidas_drivers.json").read_text())
    result = run_monte_carlo(facts)
    printable = {k: v for k, v in result.items() if k != "fcf_draws"}
    print(json.dumps(printable, indent=2))
