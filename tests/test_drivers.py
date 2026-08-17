"""
The migration from hardcoded drivers to client packs must have preserved the
finance, not merely kept the tests passing.

Three implementations are cross-checked here:

  1. clients/adidas/drivers.yaml, resolved by src.clientpack   (production)
  2. tests/reference_adidas_drivers.py                          (frozen legacy)
  3. src.backtest.driver_based()                                (independent)

(1) and (2) are separate code paths; (3) computes the same forecast from the
raw facts without consulting either. If all three agree, the pack is a
faithful migration rather than a plausible rewrite.
"""

import json

import pytest

import reference_adidas_drivers as reference
from src import backtest, clientpack, config as C, model

FACTS_PATH = C.FACTS / "adidas_drivers.json"
pytestmark = pytest.mark.skipif(not FACTS_PATH.exists(), reason="data/facts/adidas_drivers.json not present")


@pytest.fixture(scope="module")
def facts():
    return json.loads(FACTS_PATH.read_text())


@pytest.fixture(scope="module")
def adidas():
    return clientpack.load_pack("adidas")


def test_pack_baselines_match_the_frozen_legacy_implementation(adidas, facts):
    """Every adidas driver default must resolve to exactly what the
    pre-config implementation produced. This is the test that would catch a
    baseline quietly frozen as a literal during the migration."""
    legacy = {k: v["default"] for k, v in reference.build_driver_config(facts).items()}
    resolved = adidas.base_driver_values()

    assert set(resolved) == set(legacy)
    for driver_id, expected in legacy.items():
        assert resolved[driver_id] == pytest.approx(expected, rel=1e-12), driver_id


def test_base_case_reproduces_backtest_driver_based_exactly(adidas, facts):
    """The planner's Base case must BE src.backtest.driver_based()'s result,
    not a separately-tuned number that happens to look similar — this is what
    "UI is an interface to the model, not a second model" means in practice.

    It is also the constraint most at risk from a configuration refactor: a
    literal-valued driver schema would pass every other test in this file and
    silently sever this one.
    """
    assumptions = adidas.to_assumptions(adidas.base_driver_values())
    result = model.forecast(adidas.baseline_group, facts["product_division"]["2024"], assumptions)
    expected = backtest.driver_based(facts)

    for metric in ("revenue", "operating_profit", "free_cash_flow"):
        assert result[metric] == pytest.approx(expected[metric], rel=1e-9), metric


def test_pack_assumptions_match_the_frozen_legacy_mapping(adidas, facts):
    """The driver -> model-assumption mapping moved from a hardcoded function
    into each driver's `maps_to`. It must still produce the same shape."""
    division24 = {k: v for k, v in facts["product_division"]["2024"].items() if k != "source"}
    values = adidas.base_driver_values()

    legacy = reference.defaults_to_assumptions(values, division24)
    resolved = adidas.to_assumptions(values)

    assert resolved["division_growth"] == pytest.approx(legacy["division_growth"])
    for key in ("ebitda_margin_pct", "effective_tax_rate_pct",
                "operating_working_capital_pct", "capex_eur_m"):
        assert resolved[key] == pytest.approx(legacy[key], rel=1e-12), key


@pytest.mark.parametrize("client_id", clientpack.available_clients())
def test_every_driver_has_required_metadata(client_id):
    pack = clientpack.load_pack(client_id)
    for driver_id, spec in pack.drivers.items():
        assert spec.label and spec.unit and spec.source and spec.owner, driver_id
        assert spec.min <= spec.default <= spec.max, f"{driver_id} default outside its own range"
        assert spec.confidence in clientpack.CONFIDENCE_LEVELS, driver_id
        assert spec.controllability in clientpack.CONTROLLABILITY_LEVELS, driver_id
        assert spec.role in ("base", "add", "delta"), driver_id


@pytest.mark.parametrize("client_id", clientpack.available_clients())
def test_base_case_leaves_every_delta_at_zero(client_id):
    """A delta driver contributes only its movement from baseline, so at base
    values it must contribute nothing. If it did, the client's "plan" would
    not be the plan its own configuration declares — which is exactly the bug
    that the add/delta distinction exists to prevent."""
    pack = clientpack.load_pack(client_id)
    assumptions = pack.to_assumptions(pack.base_driver_values())

    for key, base_value in pack.assumption_bases.items():
        has_deltas = any(s.maps_to == key and s.role == "delta" for s in pack.drivers.values())
        if has_deltas:
            assert assumptions[key] == pytest.approx(base_value, rel=1e-9), key
