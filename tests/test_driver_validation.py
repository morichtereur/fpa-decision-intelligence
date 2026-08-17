"""Driver values are bounded by the same spec the sliders are built from.

/api/commentary/live is public and billable, so an out-of-range value must
be rejected before the API call rather than spend one producing confident
nonsense. The UI cannot send such a value — its sliders carry these bounds —
so this only fires on a hand-made request, which is exactly the case worth
covering.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.service import DriverValueError, base_driver_values, get_driver_config, validate_driver_values

client = TestClient(app)


def test_base_values_pass():
    validate_driver_values(base_driver_values())


@pytest.mark.parametrize("driver", list(get_driver_config().keys()))
def test_below_minimum_is_rejected(driver):
    values = base_driver_values()
    values[driver] = get_driver_config()[driver]["min"] - 1
    with pytest.raises(DriverValueError, match="below the minimum"):
        validate_driver_values(values)


@pytest.mark.parametrize("driver", list(get_driver_config().keys()))
def test_above_maximum_is_rejected(driver):
    values = base_driver_values()
    values[driver] = get_driver_config()[driver]["max"] + 1
    with pytest.raises(DriverValueError, match="above the maximum"):
        validate_driver_values(values)


def test_bounds_are_inclusive():
    config = get_driver_config()
    at_min = {k: spec["min"] for k, spec in config.items()}
    at_max = {k: spec["max"] for k, spec in config.items()}
    validate_driver_values(at_min)
    validate_driver_values(at_max)


def test_outside_guidance_but_inside_range_is_allowed():
    """Stress testing past the company's disclosed guidance is the point of
    the planner — the UI flags it, it must not be blocked."""
    config = get_driver_config()
    values = base_driver_values()
    spec = config["working_capital_pct"]
    beyond_guidance = spec["guidance_high"] + 1
    assert beyond_guidance <= spec["max"], "fixture assumes headroom above guidance"
    values["working_capital_pct"] = beyond_guidance
    validate_driver_values(values)


def test_unknown_and_missing_drivers_are_rejected():
    values = base_driver_values()
    with pytest.raises(DriverValueError, match="Unknown driver"):
        validate_driver_values({**values, "made_up": 1.0})
    with pytest.raises(DriverValueError, match="Missing driver"):
        validate_driver_values({k: v for k, v in list(values.items())[:-1]})


def test_scenario_endpoint_returns_422_out_of_range():
    values = base_driver_values()
    values["revenue_growth"] = 1e9
    r = client.post("/api/scenario", json={"driver_values": values})
    assert r.status_code == 422
    assert "above the maximum" in r.text


def test_commentary_live_validates_before_spending_a_call():
    values = base_driver_values()
    values["revenue_growth"] = 1e9
    r = client.post("/api/commentary/live", json={"driver_values": values})
    # 503 when no key is configured, 422 when one is — either way the request
    # is refused without reaching the model.
    assert r.status_code in (422, 503)
