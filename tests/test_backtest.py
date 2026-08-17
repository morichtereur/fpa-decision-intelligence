import json

import pytest

from src import backtest, config as C

FACTS_PATH = C.FACTS / "adidas_drivers.json"
pytestmark = pytest.mark.skipif(not FACTS_PATH.exists(), reason="data/facts/adidas_drivers.json not present")


@pytest.fixture(scope="module")
def facts():
    return json.loads(FACTS_PATH.read_text())


def test_naive_and_driver_based_both_underpredict_actual_operating_profit(facts):
    """adidas beat its own initial FY2025 guidance substantially -- both
    forecasts should come in under actual operating profit. If this ever
    flips, the finding in the README needs re-checking, not just the
    assertion."""
    naive = backtest.naive_baseline(facts)
    driven = backtest.driver_based(facts)
    actual_operating_profit = facts["group"]["2025"]["operating_profit"]

    assert naive["operating_profit"] < actual_operating_profit
    assert driven["operating_profit"] < actual_operating_profit


def test_driver_based_beats_naive_on_every_metric(facts):
    result = backtest.run()
    for metric in ("revenue_error_pct", "operating_profit_error_pct", "free_cash_flow_error_pct"):
        naive_err = abs(result["naive"][metric])
        driven_err = abs(result["driver_based"][metric])
        assert driven_err < naive_err, f"{metric}: driver-based ({driven_err}) not better than naive ({naive_err})"
