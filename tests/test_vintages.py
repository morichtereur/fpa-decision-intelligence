"""
Two backtest vintages, and what they jointly support.

A single point could not distinguish "the method works" from "the method got
one year right". Two can do a little better — and the second one immediately
falsified a claim this project had been making, which is the most useful thing
a second data point can do.
"""

import pytest

from src import backtest

VINTAGES = sorted(backtest.VINTAGES)
METRICS = ("revenue", "operating_profit", "free_cash_flow")


@pytest.fixture(scope="module")
def results():
    return {r["vintage"]: r for r in backtest.run_all()}


def test_both_vintages_are_built_from_information_available_at_the_time(results):
    """The FY2024 report's own targets column is labelled 'As published on
    October 15, 2024' — guidance revised three quarters into the year it
    describes. The vintages use the INITIAL guidance from the prior year's
    report, which is the only honest input for a forecast."""
    assert results["fy2024"]["guidance_published"] == "February 2024"
    assert results["fy2025"]["guidance_published"] == "March 2025"


def test_the_default_vintage_is_unchanged(results):
    """run() with no argument must still be the FY2025 point everything else
    in the project was built against."""
    assert backtest.DEFAULT_VINTAGE == "fy2025"
    assert backtest.run()["vintage"] == "fy2025"
    assert backtest.run()["actual"] == results["fy2025"]["actual"]


@pytest.mark.parametrize("vintage", VINTAGES)
@pytest.mark.parametrize("metric", METRICS)
def test_every_vintage_reports_an_error_against_a_real_actual(results, vintage, metric):
    r = results[vintage]
    assert r["actual"][metric] > 0
    for method in ("naive", "driver_based"):
        assert f"{metric}_error_pct" in r[method]


def test_driver_based_beats_naive_on_revenue_and_operating_profit(results):
    """Where guidance speaks to the metric directly, it helps in both years."""
    for vintage in VINTAGES:
        r = results[vintage]
        for metric in ("revenue", "operating_profit"):
            driver = abs(r["driver_based"][f"{metric}_error_pct"])
            naive = abs(r["naive"][f"{metric}_error_pct"])
            assert driver < naive, f"{vintage} {metric}: driver {driver} vs naive {naive}"


def test_driver_based_LOSES_to_naive_on_fy2024_free_cash_flow(results):
    """The claim this project used to make — that the driver-based forecast
    beat a naive extrapolation on every metric — was true of one vintage and
    is false across two.

    In FY2024 adidas released working capital from 25.7% to 19.7% of sales
    while guiding 23-24%. The guidance-anchored forecast inherited that error;
    the naive one, holding the prior year's ratio flat, happened to land
    closer. Asserted so the claim cannot quietly reappear.
    """
    r = results["fy2024"]
    driver = abs(r["driver_based"]["free_cash_flow_error_pct"])
    naive = abs(r["naive"]["free_cash_flow_error_pct"])
    assert driver > naive, "if this reverses, the README's scorecard needs rewriting"


def test_both_vintages_undershoot(results):
    """adidas guided conservatively in both years and beat its own guidance in
    both. A forecast anchored on that guidance inherits the conservatism —
    which is a property of the input, not a flaw in the arithmetic, and is the
    single most useful thing two points reveal that one cannot."""
    for vintage in VINTAGES:
        assert results[vintage]["driver_based"]["operating_profit_error_pct"] < 0


def test_the_scorecard_is_five_of_six(results):
    """The honest headline: driver-based wins 5 of 6 metric-vintage pairs."""
    wins = sum(
        abs(results[v]["driver_based"][f"{m}_error_pct"])
        < abs(results[v]["naive"][f"{m}_error_pct"])
        for v in VINTAGES
        for m in METRICS
    )
    assert wins == 5, f"scorecard moved to {wins}/6 — the stated claim must move with it"


def test_unknown_vintage_is_rejected():
    with pytest.raises(ValueError, match="Unknown vintage"):
        backtest.run("fy2099")
