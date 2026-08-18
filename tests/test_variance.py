"""
The forecast-to-actual variance bridge.

Ported from the pre-client-pack implementation and re-pointed at the pack API.
The assertions are the upstream ones — they encode what makes the bridge
honest rather than decorative — plus the ones the configurable version needs:
that a client with no outturn gets no bridge, and that the realised values are
read from configuration rather than hardcoded.
"""

import pytest

from src import backtest, clientpack, variance

METRICS = variance.METRICS


@pytest.fixture(scope="module")
def pack():
    return clientpack.load_pack("adidas")


@pytest.fixture(scope="module")
def facts(pack):
    return pack.facts


# --------------------------------------------------------------------------
# Availability
# --------------------------------------------------------------------------

def test_a_client_with_no_actuals_gets_no_bridge():
    """A bridge from a forecast to invented actuals would look like a finding
    and be none. It must refuse rather than fabricate."""
    demo = clientpack.load_pack("manufacturing_demo")
    assert variance.is_available(demo) is False
    with pytest.raises(variance.VarianceUnavailable):
        variance.bridge(demo)


def test_the_public_client_has_a_bridge(pack):
    assert variance.is_available(pack) is True


def test_unknown_metric_is_rejected(pack):
    with pytest.raises(ValueError, match="Unknown metric"):
        variance.bridge(pack, "gross_margin")


# --------------------------------------------------------------------------
# The realised values are reported figures, read from config
# --------------------------------------------------------------------------

def test_realised_drivers_come_from_reported_figures(pack, facts):
    realised = variance.realised_drivers(pack)
    g24, g25 = facts["group"]["2024"], facts["group"]["2025"]

    assert realised["working_capital_pct"] == g25["operating_working_capital_pct"]
    assert realised["capex_eur_m"] == g25["capex"]
    assert realised["tax_rate_pct"] == g25["effective_tax_rate_pct"]
    assert realised["ebitda_margin"] == pytest.approx(g25["ebitda"] / g25["net_sales"] * 100)
    assert realised["revenue_growth"] == pytest.approx(
        (g25["net_sales"] / g24["net_sales"] - 1) * 100
    )


def test_each_step_cites_where_the_actual_value_came_from(pack):
    for step in variance.bridge(pack)["steps"]:
        assert step["source"]
        assert "reported" in step["source"] or "disclosed" in step["source"]


def test_the_bridge_starts_where_the_backtest_starts(pack):
    """Read from the pack rather than restated, so the bridge, the planner's
    base case and the backtest cannot drift apart."""
    base = pack.base_driver_values()
    for driver_id, value in variance.forecast_drivers(pack).items():
        assert value == base[driver_id]


# --------------------------------------------------------------------------
# The arithmetic
# --------------------------------------------------------------------------

def test_every_driver_is_walked_exactly_once(pack):
    order = variance.variance_order(pack)
    steps = variance.bridge(pack)["steps"]
    assert [s["driver_id"] for s in steps] == list(order)
    assert len({s["driver_id"] for s in steps}) == len(order)


@pytest.mark.parametrize("metric", METRICS)
def test_the_parts_add_up_to_the_whole(pack, metric):
    result = variance.bridge(pack, metric)
    assert result["explained_by_drivers"] + result["residual"] == pytest.approx(
        result["total_variance"], abs=0.2
    )


@pytest.mark.parametrize("metric", METRICS)
def test_step_impacts_sum_to_what_the_drivers_explain(pack, metric):
    result = variance.bridge(pack, metric)
    assert sum(s["impact"] for s in result["steps"]) == pytest.approx(
        result["explained_by_drivers"], abs=0.2
    )


@pytest.mark.parametrize("metric", METRICS)
def test_the_endpoints_match_the_backtest(pack, metric):
    result = variance.bridge(pack, metric)
    bt = backtest.run()
    assert result["forecast"] == pytest.approx(bt["driver_based"][metric], abs=0.15)
    assert result["actual"] == pytest.approx(bt["actual"][metric], abs=0.15)


def test_only_revenue_growth_moves_revenue(pack):
    steps = {s["driver_id"]: s["impact"] for s in variance.bridge(pack, "revenue")["steps"]}
    assert abs(steps["revenue_growth"]) > 100
    for driver_id in ("ebitda_margin", "tax_rate_pct", "working_capital_pct", "capex_eur_m"):
        assert steps[driver_id] == 0.0


def test_cash_only_drivers_do_not_move_operating_profit(pack):
    steps = {s["driver_id"]: s["impact"] for s in variance.bridge(pack, "operating_profit")["steps"]}
    for driver_id in ("tax_rate_pct", "working_capital_pct", "capex_eur_m"):
        assert steps[driver_id] == 0.0


# --------------------------------------------------------------------------
# What makes it honest rather than decorative
# --------------------------------------------------------------------------

def test_working_capital_is_the_largest_driver_of_the_cash_flow_miss(pack):
    largest = variance.largest_driver(variance.bridge(pack, "free_cash_flow"))
    assert largest["driver_id"] == "working_capital_pct"
    assert largest["impact"] < 0


def test_the_residual_is_reported_rather_than_absorbed(pack):
    """A bridge that always closes to zero is hiding something."""
    result = variance.bridge(pack, "free_cash_flow")
    assert abs(result["residual"]) > 1
    assert "D&A" in result["residual_note"]


def test_order_dependence_is_disclosed(pack):
    assert "order" in variance.bridge(pack)["order_note"].lower()


def test_offsetting_errors_are_called_out_when_they_dominate(pack):
    """The finding that matters: free cash flow missed by little, but only
    because large driver errors cancelled. That is not an accurate forecast."""
    result = variance.bridge(pack, "free_cash_flow")
    assert result["gross_driver_movement"] > abs(result["total_variance"]) * 3
    assert result["offsetting_note"] is not None
    assert "offset" in result["offsetting_note"]


def test_no_offsetting_note_when_one_driver_explains_the_variance(pack):
    assert variance.bridge(pack, "revenue")["offsetting_note"] is None


def test_the_waterfall_carries_the_residual_as_a_row(pack):
    labels = [row["label"] for row in variance.bridge(pack)["waterfall"]]
    assert labels[0] == "Forecast" and labels[-1] == "Actual"
    assert "Residual" in labels


def test_bridge_is_served_per_client():
    from api import service

    assert service.get_variance_bridge("free_cash_flow", "adidas") is not None
    assert service.get_variance_bridge("free_cash_flow", "manufacturing_demo") is None
