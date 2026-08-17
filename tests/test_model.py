import pytest

from src import model


def test_forecast_chain_with_flat_assumptions():
    """Zero growth, margin held flat, working capital % held flat -> the
    forecast should reproduce the baseline year's economics."""
    baseline_group = {
        "net_sales": 1000,
        "ebitda": 130,
        "operating_profit": 80,
        "operating_working_capital_pct": 20.0,
        "source": "test fixture",
    }
    baseline_division = {"footwear": 600, "apparel": 350, "accessories": 50}
    assumptions = {
        "division_growth": {"footwear": 0.0, "apparel": 0.0, "accessories": 0.0},
        "ebitda_margin_pct": 13.0,
        "effective_tax_rate_pct": 25.0,
        "operating_working_capital_pct": 20.0,
        "capex_eur_m": 60,
    }

    out = model.forecast(baseline_group, baseline_division, assumptions)

    assert out["revenue"] == 1000
    assert out["ebitda"] == pytest.approx(130)
    assert out["change_in_working_capital"] == pytest.approx(0)
    assert out["operating_profit"] == pytest.approx(80)


def test_growth_increases_revenue_and_working_capital_investment():
    baseline_group = {
        "net_sales": 1000,
        "ebitda": 130,
        "operating_profit": 80,
        "operating_working_capital_pct": 20.0,
        "source": "test fixture",
    }
    baseline_division = {"footwear": 600, "apparel": 350, "accessories": 50}
    assumptions = {
        "division_growth": {"footwear": 0.10, "apparel": 0.10, "accessories": 0.10},
        "ebitda_margin_pct": 13.0,
        "effective_tax_rate_pct": 25.0,
        "operating_working_capital_pct": 20.0,
        "capex_eur_m": 60,
    }

    out = model.forecast(baseline_group, baseline_division, assumptions)

    assert out["revenue"] == pytest.approx(1100)
    # 10% more revenue at the same working-capital % of sales still means
    # a real cash outflow to fund that growth.
    assert out["change_in_working_capital"] > 0
