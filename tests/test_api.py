"""
The API must never compute a different answer than the model itself would.
These tests call the real FastAPI app (via TestClient, no server process)
and cross-check every scenario endpoint response against a direct
src.model.forecast() call for the same inputs — "UI is an interface to the
model, not a second model" enforced at the HTTP boundary, not just in the
Python service layer (tests/test_drivers.py covers that layer already).

The independent side of the cross-check is tests/reference_adidas_drivers.py,
the frozen pre-client-pack implementation. Checking the API against the pack
that now feeds it would be circular; checking it against the implementation
the pack replaced is not.
"""

import json

import pytest
from fastapi.testclient import TestClient

from api.main import app
import reference_adidas_drivers as reference
from src import config as C, model

FACTS_PATH = C.FACTS / "adidas_drivers.json"
pytestmark = pytest.mark.skipif(not FACTS_PATH.exists(), reason="data/facts/adidas_drivers.json not present")

client = TestClient(app)


@pytest.fixture(scope="module")
def facts():
    return json.loads(FACTS_PATH.read_text())


def _direct_forecast(facts, driver_values):
    division24 = {k: v for k, v in facts["product_division"]["2024"].items() if k != "source"}
    assumptions = reference.defaults_to_assumptions(driver_values, division24)
    return model.forecast(facts["group"]["2024"], facts["product_division"]["2024"], assumptions)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_scenario_endpoint_matches_direct_model_call_for_base_values(facts):
    config = client.get("/api/drivers").json()
    base_values = {driver_id: spec["default"] for driver_id, spec in config.items()}

    response = client.post("/api/scenario", json={"driver_values": base_values})
    assert response.status_code == 200
    api_result = response.json()["scenario"]

    direct = _direct_forecast(facts, base_values)

    assert api_result["revenue"] == pytest.approx(direct["revenue"], rel=1e-9)
    assert api_result["free_cash_flow"] == pytest.approx(direct["free_cash_flow"], rel=1e-9)


def test_scenario_endpoint_matches_direct_model_call_for_a_stressed_value(facts):
    config = client.get("/api/drivers").json()
    values = {driver_id: spec["default"] for driver_id, spec in config.items()}
    values["working_capital_pct"] = 24.0

    api_result = client.post("/api/scenario", json={"driver_values": values}).json()["scenario"]
    direct = _direct_forecast(facts, values)

    assert api_result["free_cash_flow"] == pytest.approx(direct["free_cash_flow"], rel=1e-9)
    assert api_result["operating_working_capital"] == pytest.approx(direct["operating_working_capital"], rel=1e-9)


def test_every_preset_resolves_and_matches_direct_model_call(facts):
    presets = client.get("/api/presets").json()
    for preset_id, preset in presets.items():
        api_result = client.post("/api/scenario", json={"driver_values": preset["values"]}).json()["scenario"]
        direct = _direct_forecast(facts, preset["values"])
        assert api_result["free_cash_flow"] == pytest.approx(direct["free_cash_flow"], rel=1e-9), preset_id


# 422, not 400: driver names, driver ranges and body shape are all content
# validation, and FastAPI already answers 422 for a malformed body. Splitting
# them across two codes made the surface inconsistent for no gain.
def test_scenario_rejects_unknown_driver():
    response = client.post("/api/scenario", json={"driver_values": {"not_a_real_driver": 1.0}})
    assert response.status_code == 422


def test_scenario_rejects_missing_driver():
    response = client.post("/api/scenario", json={"driver_values": {"revenue_growth": 8.0}})
    assert response.status_code == 422


def test_out_of_guidance_flag_is_set_when_a_driver_exceeds_its_disclosed_range():
    config = client.get("/api/drivers").json()
    values = {driver_id: spec["default"] for driver_id, spec in config.items()}
    values["working_capital_pct"] = 24.0  # above the disclosed 21-22% range

    result = client.post("/api/scenario", json={"driver_values": values}).json()
    assert result["out_of_guidance"].get("working_capital_pct") is True


def test_commentary_for_unknown_scenario_is_404():
    response = client.get("/api/commentary/not-a-real-scenario")
    assert response.status_code == 404


def test_bridge_starts_at_base_and_ends_at_scenario_fcf():
    config = client.get("/api/drivers").json()
    values = {driver_id: spec["default"] for driver_id, spec in config.items()}
    values["working_capital_pct"] = 24.0

    result = client.post("/api/scenario", json={"driver_values": values}).json()
    bridge = result["bridge"]
    assert bridge[0]["label"] == "Base"
    assert bridge[-1]["label"] == "Scenario"
    assert bridge[-1]["value"] == pytest.approx(result["scenario"]["free_cash_flow"], rel=1e-9)
