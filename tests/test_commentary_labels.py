"""The forecast series must be tabled under the name it actually has.

A scenario's output used to be handed to the LLM under the key
`driver_based_*`, so commentary on the Working Capital Stress preset
described a −61.2% free-cash-flow miss as "the driver-based model" — while
the backtest on the same page reports that model's error as 3.4%. The
numbers were grounded; the label was not.
"""

from src.commentary import _flatten_outputs


BACKTEST = {
    "actual": {"free_cash_flow": 1106.4, "revenue": 24811.0},
    "naive": {"free_cash_flow": 1270.2},
    "driver_based": {"free_cash_flow": 1070.0},
}

SCENARIO = {
    "actual": {"free_cash_flow": 1106.4, "revenue": 24811.0},
    "naive": {"free_cash_flow": 1270.2},
    "wc_stress": {"free_cash_flow": 429.6, "free_cash_flow_error_pct": -61.2},
}


def test_backtest_series_keeps_its_name():
    flat = _flatten_outputs(BACKTEST)
    assert flat["driver_based_free_cash_flow"] == 1070.0
    assert flat["actual_free_cash_flow"] == 1106.4
    assert flat["naive_free_cash_flow"] == 1270.2


def test_scenario_is_not_tabled_as_the_driver_based_forecast():
    flat = _flatten_outputs(SCENARIO)
    assert flat["wc_stress_free_cash_flow"] == 429.6
    assert flat["wc_stress_free_cash_flow_error_pct"] == -61.2
    assert not any(key.startswith("driver_based") for key in flat), (
        "a scenario tabled under driver_based_* invites the model to call a "
        "stress case the driver-based forecast"
    )


def test_every_numeric_metric_survives_the_flattening():
    # The series names are no longer a fixed allow-list, so a caller adding a
    # series must not silently lose it.
    flat = _flatten_outputs({"actual": {"a": 1.0}, "naive": {"b": 2.0}, "custom": {"c": 3.0}})
    assert flat == {"actual_a": 1.0, "naive_b": 2.0, "custom_c": 3.0}


def test_non_numeric_fields_are_dropped():
    flat = _flatten_outputs({"actual": {"a": 1.0, "label": "FY2025", "flag": True}})
    assert "actual_label" not in flat
    # bool is an int subclass, so a flag would otherwise enter the table as 1 —
    # a number the model could then cite and verify_grounding() would accept.
    assert "actual_flag" not in flat
    assert flat["actual_a"] == 1.0


def test_live_endpoint_default_is_neutral_not_the_backtest_label():
    """The default series name must not claim to be the driver-based forecast.

    /api/commentary/live passes no name, so whatever the default is ends up
    describing arbitrary slider positions. It used to be `driver_based`, which
    made a custom stress scenario read as the backtested forecast.
    """
    import inspect

    from api.service import generate_live_commentary

    default = inspect.signature(generate_live_commentary).parameters["series_name"].default
    assert default != "driver_based"
    assert default == "scenario"
