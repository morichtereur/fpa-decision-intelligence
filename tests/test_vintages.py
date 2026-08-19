"""
Two backtest vintages, and what they jointly support.

A single point could not distinguish "the method works" from "the method got
one year right". Two can do a little better.

The second vintage's first job was to expose a defect. Carrying FY2023's
effective tax rate forward gave a FY2024 plan built on a 189.2% tax rate — tax
expense on a near-zero pre-tax result in the write-off year — which made the
driver-based forecast look worse than a naive extrapolation on free cash flow.
That was the model being wrong, not the method being weak. The rule is guarded
now, and these tests pin both the guard and the result.
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


def test_the_tax_carry_forward_rule_is_guarded(results):
    """FY2023's effective rate was 189.2% — tax expense on a near-zero pre-tax
    result. Carrying that into a FY2024 plan is not conservative, it is
    meaningless, and it cost the driver-based forecast 32 points of
    free-cash-flow error on its own."""
    import json
    from src import config as C

    facts = json.loads((C.FACTS / "adidas_drivers.json").read_text())

    raw = facts["group"]["2023"]["effective_tax_rate_pct"]
    assert raw > 100, "fixture drift: FY2023 is the anomalous year this guard exists for"

    used, basis = backtest.normalised_tax_rate(facts, "2023")
    low, high = backtest.PLAUSIBLE_TAX_RATE
    assert low <= used <= high
    assert "outside" in basis

    # FY2024's own rate must not be used to normalise the FY2024 forecast.
    assert used != facts["group"]["2024"]["effective_tax_rate_pct"], "look-ahead bias"
    assert used == facts["group"]["2022"]["effective_tax_rate_pct"], (
        "the only in-band rate published by FY2023 is FY2022's"
    )


def test_a_normal_year_still_carries_its_own_rate_forward():
    """The guard must not disturb the vintage everything else was built
    against — FY2025's baseline rate is plausible and is used unchanged."""
    import json
    from src import config as C

    facts = json.loads((C.FACTS / "adidas_drivers.json").read_text())
    used, basis = backtest.normalised_tax_rate(facts, "2024")
    assert used == facts["group"]["2024"]["effective_tax_rate_pct"]
    assert "carried forward" in basis


def test_the_guard_does_not_flatter_the_forecast(results):
    """The substituted rate is HIGHER than the year's eventual actual, so the
    guard makes the forecast more conservative, not more accurate. A fix that
    happened to help the metric being tested would deserve suspicion."""
    import json
    from src import config as C

    facts = json.loads((C.FACTS / "adidas_drivers.json").read_text())
    used, _ = backtest.normalised_tax_rate(facts, "2023")
    assert used > facts["group"]["2024"]["effective_tax_rate_pct"]


def test_both_vintages_undershoot(results):
    """adidas guided conservatively in both years and beat its own guidance in
    both. A forecast anchored on that guidance inherits the conservatism —
    which is a property of the input, not a flaw in the arithmetic, and is the
    single most useful thing two points reveal that one cannot."""
    for vintage in VINTAGES:
        assert results[vintage]["driver_based"]["operating_profit_error_pct"] < 0


def test_the_scorecard_is_six_of_six(results):
    """Driver-based lands closer on every metric in both vintages.

    Stated as a count rather than a claim so that if a fact correction moves
    it, this fails and the README has to move with it. It has already moved
    once: it read 5 of 6 while the tax rule was unguarded.
    """
    wins = sum(
        abs(results[v]["driver_based"][f"{m}_error_pct"])
        < abs(results[v]["naive"][f"{m}_error_pct"])
        for v in VINTAGES
        for m in METRICS
    )
    assert wins == 6, f"scorecard moved to {wins}/6 — the stated claim must move with it"


def test_winning_every_comparison_is_not_the_same_as_being_accurate(results):
    """Beating a weak baseline on all six says nothing about the size of the
    misses, which remain large. Asserted so the scorecard is never read as
    accuracy."""
    assert abs(results["fy2024"]["driver_based"]["operating_profit_error_pct"]) > 50
    assert abs(results["fy2024"]["driver_based"]["free_cash_flow_error_pct"]) > 40


def test_unknown_vintage_is_rejected():
    with pytest.raises(ValueError, match="Unknown vintage"):
        backtest.run("fy2099")
