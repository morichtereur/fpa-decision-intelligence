"""
Client configurability is only real if switching clients changes the answers
and nothing crosses between them.

The failure this file exists to catch is not a crash. It is the quiet one: a
cached forecast, a module-level "active client", or a driver name that
happens to exist in both packs, producing adidas's numbers under the
manufacturing client's label. That would be undetectable by eye and fatal to
the product's credibility, so it is asserted rather than assumed.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api import service
from src import clientpack

client = TestClient(app)
CLIENTS = clientpack.available_clients()


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def test_both_demonstration_clients_are_available():
    assert set(CLIENTS) >= {"adidas", "manufacturing_demo"}


@pytest.mark.parametrize("client_id", CLIENTS)
def test_every_pack_loads_and_can_drive_the_model(client_id):
    """load_pack() runs to_assumptions() on its own base case before
    returning, so a pack that could not produce a forecast fails here rather
    than three screens into the UI."""
    pack = clientpack.load_pack(client_id)
    assumptions = pack.to_assumptions(pack.base_driver_values())
    assert set(assumptions) == clientpack.MODEL_ASSUMPTION_KEYS
    assert pack.name and pack.currency and pack.fiscal_year


def test_unknown_client_is_rejected_rather_than_defaulted():
    """Falling back to the default on a typo would serve adidas's numbers
    under whatever label the caller asked for."""
    with pytest.raises(clientpack.ClientPackError):
        clientpack.resolve_client_id("addidas")
    assert client.get("/api/outlook?client=addidas").status_code == 404


def test_synthetic_client_is_labelled_as_synthetic():
    """A synthetic client presented as real would be the single most damaging
    thing this application could do."""
    demo = clientpack.load_pack("manufacturing_demo")
    assert demo.is_synthetic is True
    assert demo.data_basis == "Synthetic Demo"
    assert "synthetic" in demo.disclaimer.lower()
    assert demo.has_backtest is False, "a backtest on invented data is not evidence"

    adidas = clientpack.load_pack("adidas")
    assert adidas.is_synthetic is False
    assert adidas.data_basis == "Public Data"


# --------------------------------------------------------------------------
# Switching actually changes the model
# --------------------------------------------------------------------------

def test_switching_client_changes_the_drivers():
    adidas = set(service.get_driver_config("adidas"))
    manufacturing = set(service.get_driver_config("manufacturing_demo"))

    assert adidas != manufacturing
    assert len(manufacturing) > len(adidas), "the demo client should be structurally richer, not a rename"
    # Working capital is modelled as a single percentage for adidas and
    # decomposed into DSO / inventory / DPO for the manufacturer.
    assert {"dso_days", "inventory_days", "dpo_days"} <= manufacturing
    assert "working_capital_pct" in adidas and "working_capital_pct" not in manufacturing


def test_switching_client_changes_scenarios_thresholds_and_scale():
    assert set(service.get_presets("adidas")) != set(service.get_presets("manufacturing_demo"))

    adidas_rules = {r["metric"] for r in service.get_decision_rules("adidas")}
    demo_rules = {r["metric"] for r in service.get_decision_rules("manufacturing_demo")}
    assert adidas_rules != demo_rules
    assert "inventory_days" in demo_rules and "inventory_days" not in adidas_rules

    # Order-of-magnitude difference: a €24bn consumer brand against a €1.9bn
    # manufacturer. If these were close, the packs would not be independent.
    adidas_revenue = service.run_forecast(service.base_driver_values("adidas"), "adidas")["revenue"]
    demo_revenue = service.run_forecast(
        service.base_driver_values("manufacturing_demo"), "manufacturing_demo"
    )["revenue"]
    assert adidas_revenue > 10 * demo_revenue


def test_priority_ranking_differs_between_clients():
    adidas_top = service.get_driver_priority("adidas")[0]["driver_id"]
    demo_top = service.get_driver_priority("manufacturing_demo")[0]["driver_id"]
    assert adidas_top != demo_top


# --------------------------------------------------------------------------
# No leakage
# --------------------------------------------------------------------------

def test_one_clients_driver_names_are_rejected_by_another():
    """The most likely leakage path: posting a valid-looking payload built
    for the wrong client. It must be refused, not partially applied."""
    adidas_values = service.base_driver_values("adidas")
    with pytest.raises(service.DriverValueError):
        service.validate_driver_values(adidas_values, "manufacturing_demo")

    response = client.post(
        "/api/scenario",
        json={"driver_values": adidas_values, "client": "manufacturing_demo"},
    )
    assert response.status_code == 422


def test_repeated_switching_does_not_contaminate_results():
    """Caches are keyed by client id. Interleaving requests must give the same
    answers as asking for each client once."""
    first_adidas = service.get_outlook("adidas")
    first_demo = service.get_outlook("manufacturing_demo")

    for _ in range(3):
        service.get_outlook("manufacturing_demo")
        service.get_outlook("adidas")

    assert service.get_outlook("adidas")["forecast"] == first_adidas["forecast"]
    assert service.get_outlook("manufacturing_demo")["forecast"] == first_demo["forecast"]
    assert first_adidas["forecast"]["revenue"] != first_demo["forecast"]["revenue"]


def test_default_client_is_adidas_everywhere():
    """Every inherited entry point kept its behaviour: no argument means
    adidas, as it did before packs existed."""
    assert service.get_client_summary()["id"] == "adidas"
    assert client.get("/api/outlook").json()["client"]["id"] == "adidas"
    assert client.get("/api/clients").json()["default"] == "adidas"


# --------------------------------------------------------------------------
# API surface
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", [
    "/api/outlook", "/api/drivers", "/api/presets", "/api/driver-priority",
    "/api/assumptions", "/api/decision-rules", "/api/mappings", "/api/client",
])
@pytest.mark.parametrize("client_id", CLIENTS)
def test_every_client_scoped_route_serves_every_client(path, client_id):
    response = client.get(f"{path}?client={client_id}")
    assert response.status_code == 200, f"{path} failed for {client_id}"
    assert response.json() not in (None, {}, [])


def test_backtest_route_is_honest_about_having_no_backtest():
    assert client.get("/api/backtest?client=adidas").json() is not None
    assert client.get("/api/backtest?client=manufacturing_demo").json() is None


def test_scenario_endpoint_respects_the_requested_client():
    demo_values = service.base_driver_values("manufacturing_demo")
    demo_values["inventory_days"] = 120

    result = client.post(
        "/api/scenario", json={"driver_values": demo_values, "client": "manufacturing_demo"}
    ).json()

    direct = service.compute_scenario(demo_values, "manufacturing_demo")
    assert result["scenario"]["free_cash_flow"] == pytest.approx(direct["scenario"]["free_cash_flow"])
    # Holding more inventory than plan consumes cash.
    assert result["deltas"]["free_cash_flow"] < 0
