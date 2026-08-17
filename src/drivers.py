"""
Single source of truth for the five assumptions the Scenario Planner
exposes. Everything the UI shows about a driver — its default, range,
guidance context, confidence, and (once computed) its financial
sensitivity — comes from here, not from separately hardcoded frontend
constants. The API serves this directly; the planner never invents a
number the backend doesn't know about.

The default for each driver is chosen so that DRIVERS defaults, run
through src.model.forecast(), reproduce src.backtest.driver_based()'s
result exactly — the planner's "Base" case IS the backtest's driver-based
forecast, not a separately-tuned approximation of it. See
tests/test_drivers.py.

Confidence is a judgment call, not computed — stated here so the reasoning
is visible rather than left implicit in a slider's position:
- Working capital and capex: adidas discloses an explicit range/figure for
  FY2025 -> High confidence.
- Revenue growth: "high-single-digit rate" is a qualitative band, not a
  number -> Medium.
- EBITDA margin: not disclosed at all; back-solved from the operating-
  profit guidance via the same D&A-scaling relationship model.forecast()
  uses -> Medium (it inherits the operating-profit guidance's own
  reliability, one step removed).
- Tax rate: no FY2025 guidance exists; FY2024's actual rate is carried
  forward as a placeholder assumption -> Low.
"""

from __future__ import annotations

import json


def _margin_for_operating_profit(target_operating_profit, revenue, baseline_da, baseline_revenue):
    return (target_operating_profit / revenue + baseline_da / baseline_revenue) * 100


def build_driver_config(facts: dict) -> dict:
    g24 = facts["group"]["2024"]
    division24 = {k: v for k, v in facts["product_division"]["2024"].items() if k != "source"}
    guidance = facts["guidance"]["fy2025_initial"]

    baseline_revenue = sum(division24.values())
    baseline_da = g24["ebitda"] - g24["operating_profit"]

    growth_default = 0.08  # "high-single-digit rate", midpoint of the conventional 7-9% band
    revenue_at_default = baseline_revenue * (1 + growth_default)
    op_profit_mid = (guidance["operating_profit_eur_m_low"] + guidance["operating_profit_eur_m_high"]) / 2
    margin_default = _margin_for_operating_profit(op_profit_mid, revenue_at_default, baseline_da, baseline_revenue)

    wc_default = (guidance["operating_working_capital_pct_low"] + guidance["operating_working_capital_pct_high"]) / 2

    return {
        "revenue_growth": {
            "label": "Revenue growth",
            "unit": "pct",
            "min": 0.0,
            "max": 15.0,
            "step": 0.5,
            "default": growth_default * 100,
            "guidance_low": 7.0,
            "guidance_high": 9.0,
            "guidance_text": "adidas FY2025 guidance: “high-single-digit rate” (interpreted as 7–9%)",
            "confidence": "Medium",
            "source": "Adidas_Report_2024.pdf, Targets – Results – Outlook",
        },
        "ebitda_margin": {
            "label": "EBITDA margin",
            "unit": "pct",
            "min": 8.0,
            "max": 16.0,
            "step": 0.1,
            "default": margin_default,
            "guidance_low": None,
            "guidance_high": None,
            "guidance_text": (
                f"Not disclosed directly — back-solved from operating-profit "
                f"guidance of €{guidance['operating_profit_eur_m_low']:,.0f}–"
                f"{guidance['operating_profit_eur_m_high']:,.0f}m at {growth_default*100:.0f}% revenue growth"
            ),
            "confidence": "Medium",
            "source": "Derived, not disclosed — see src/model.py",
        },
        "working_capital_pct": {
            "label": "Working capital",
            "unit": "pct",
            "min": 18.0,
            "max": 26.0,
            "step": 0.5,
            "default": wc_default,
            "guidance_low": guidance["operating_working_capital_pct_low"],
            "guidance_high": guidance["operating_working_capital_pct_high"],
            "guidance_text": (
                f"adidas FY2025 guidance: {guidance['operating_working_capital_pct_low']:.0f}–"
                f"{guidance['operating_working_capital_pct_high']:.0f}% of net sales "
                f"(actual FY2025: {facts['group']['2025']['operating_working_capital_pct']:.1f}%)"
            ),
            "confidence": "High",
            "source": "Adidas_Report_2024.pdf, Targets – Results – Outlook",
        },
        "capex_eur_m": {
            "label": "Capex",
            "unit": "eur_m",
            "min": 400,
            "max": 700,
            "step": 10,
            "default": guidance["capex_eur_m"],
            "guidance_low": None,
            "guidance_high": None,
            "guidance_text": f"adidas FY2025 guidance: around €{guidance['capex_eur_m']:,.0f}m",
            "confidence": "High",
            "source": "Adidas_Report_2024.pdf, Targets – Results – Outlook",
        },
        "tax_rate_pct": {
            "label": "Effective tax rate",
            "unit": "pct",
            "min": 20.0,
            "max": 30.0,
            "step": 0.5,
            "default": g24["effective_tax_rate_pct"],
            "guidance_low": None,
            "guidance_high": None,
            "guidance_text": f"No FY2025 guidance given — carried forward at FY2024's actual rate ({g24['effective_tax_rate_pct']:.1f}%)",
            "confidence": "Low",
            "source": "Adidas_Report_2024.pdf, Financial Highlights (FY2024 actual)",
        },
    }


def defaults_to_assumptions(driver_values: dict, division24: dict) -> dict:
    """Convert flat {driver_id: value} (as the API/UI use) into the nested
    shape src.model.forecast() expects."""
    growth = driver_values["revenue_growth"] / 100
    return {
        "division_growth": {k: growth for k in division24},
        "ebitda_margin_pct": driver_values["ebitda_margin"],
        "effective_tax_rate_pct": driver_values["tax_rate_pct"],
        "operating_working_capital_pct": driver_values["working_capital_pct"],
        "capex_eur_m": driver_values["capex_eur_m"],
    }


PRESETS = {
    "base": {"label": "Base", "overrides": {}},
    "upside": {
        "label": "Upside",
        "overrides": {"revenue_growth": 9.0, "ebitda_margin_pct_delta": 1.0, "working_capital_pct": 21.0},
    },
    "downside": {
        "label": "Downside",
        "overrides": {"revenue_growth": 7.0, "ebitda_margin_pct_delta": -1.0, "working_capital_pct": 22.0},
    },
    "wc_stress": {
        "label": "Working Capital Stress",
        "overrides": {"working_capital_pct": 24.0},
    },
    "margin_compression": {
        "label": "Margin Compression",
        "overrides": {"ebitda_margin_pct_delta": -2.0},
    },
}


if __name__ == "__main__":
    from pathlib import Path
    facts = json.loads((Path(__file__).resolve().parent.parent / "data" / "facts" / "adidas_drivers.json").read_text())
    print(json.dumps(build_driver_config(facts), indent=2))
