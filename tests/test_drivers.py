import json

import pytest

from src import backtest, config as C, drivers, model

FACTS_PATH = C.FACTS / "adidas_drivers.json"
pytestmark = pytest.mark.skipif(not FACTS_PATH.exists(), reason="data/facts/adidas_drivers.json not present")


@pytest.fixture(scope="module")
def facts():
    return json.loads(FACTS_PATH.read_text())


def test_base_case_reproduces_backtest_driver_based_exactly(facts):
    """The planner's 'Base' preset must BE src.backtest.driver_based()'s
    result, not a separately-tuned number that happens to look similar --
    this is what "UI is an interface to the model, not a second model"
    means in practice."""
    config = drivers.build_driver_config(facts)
    base_values = {driver_id: spec["default"] for driver_id, spec in config.items()}

    division24 = {k: v for k, v in facts["product_division"]["2024"].items() if k != "source"}
    assumptions = drivers.defaults_to_assumptions(base_values, division24)
    result = model.forecast(facts["group"]["2024"], facts["product_division"]["2024"], assumptions)

    reference = backtest.driver_based(facts)

    assert result["revenue"] == pytest.approx(reference["revenue"], rel=1e-6)
    assert result["operating_profit"] == pytest.approx(reference["operating_profit"], rel=1e-6)
    assert result["free_cash_flow"] == pytest.approx(reference["free_cash_flow"], rel=1e-6)


def test_every_driver_has_required_metadata(facts):
    config = drivers.build_driver_config(facts)
    for driver_id, spec in config.items():
        for field in ("label", "unit", "min", "max", "default", "confidence", "source", "guidance_text"):
            assert field in spec, f"{driver_id} missing {field}"
        assert spec["min"] <= spec["default"] <= spec["max"], f"{driver_id} default outside its own range"
        assert spec["confidence"] in ("High", "Medium", "Low")
