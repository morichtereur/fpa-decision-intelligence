"""
The materiality engine's job is to rank management attention. These tests
check the two things that could make it dishonest: an exposure that is not
what the model would actually produce, and a classification rule that differs
from the one the UI explains.
"""

import pytest

from src import clientpack, materiality, model

CLIENTS = clientpack.available_clients()


# --------------------------------------------------------------------------
# The classification rule
# --------------------------------------------------------------------------

@pytest.mark.parametrize("m,u,c,expected", [
    ("High",   "High",   "High",   "Critical"),
    ("High",   "High",   "Medium", "Critical"),
    ("High",   "Low",    "High",   "Act"),
    ("High",   "Medium", "High",   "Act"),
    ("Medium", "High",   "High",   "Review"),
    ("Medium", "Low",    "Medium", "Review"),
    ("Low",    "High",   "High",   "Monitor"),
    ("Low",    "Low",    "Low",    "Monitor"),
])
def test_classification_follows_the_stated_rule(m, u, c, expected):
    assert materiality.classify(m, u, c) == expected


@pytest.mark.parametrize("uncertainty", ["High", "Medium", "Low"])
@pytest.mark.parametrize("mat", ["High", "Medium"])
def test_uncontrollable_exposure_is_never_escalated(mat, uncertainty):
    """The cell that earns the model its keep. A large, uncertain exposure
    management cannot move must not outrank a smaller one it can act on —
    attention is a budget, and it should be spent where it converts."""
    assert materiality.classify(mat, uncertainty, "Low") == "Monitor"


def test_high_materiality_and_uncertainty_outranks_high_materiality_alone():
    assert materiality.classify("High", "High", "High") == "Critical"
    assert materiality.classify("High", "Low", "High") == "Act"


def test_every_combination_yields_a_known_priority():
    for m in materiality.BANDS:
        for u in materiality.BANDS:
            for c in materiality.BANDS:
                assert materiality.classify(m, u, c) in materiality.PRIORITIES


def test_confidence_maps_to_the_inverse_uncertainty():
    assert materiality.CONFIDENCE_TO_UNCERTAINTY["High"] == "Low"
    assert materiality.CONFIDENCE_TO_UNCERTAINTY["Low"] == "High"


# --------------------------------------------------------------------------
# Exposure is computed, not asserted
# --------------------------------------------------------------------------

@pytest.mark.parametrize("client_id", CLIENTS)
def test_exposure_matches_a_direct_model_call(client_id):
    """The exposure figure must be what model.forecast() actually produces at
    each end of the range — not a coefficient, a proxy, or a remembered
    number. Recomputed here independently of the engine."""
    pack = clientpack.load_pack(client_id)
    metric = materiality.objective_metric(pack)
    segments = clientpack.read_fact(pack.facts, pack.segments_path)

    for driver_id in pack.driver_order:
        result = materiality.driver_exposure(pack, driver_id)
        low, high, _ = materiality.exposure_range(pack, driver_id)

        for end, value in (("value_at_low", low), ("value_at_high", high)):
            values = dict(pack.base_driver_values(), **{driver_id: value})
            direct = model.forecast(pack.baseline_group, segments, pack.to_assumptions(values))[metric]
            assert result[end] == pytest.approx(direct, rel=1e-12), f"{driver_id} {end}"

        assert result["exposure"] == pytest.approx(result["value_at_high"] - result["value_at_low"])


@pytest.mark.parametrize("client_id", CLIENTS)
def test_exposure_range_never_exceeds_the_models_domain(client_id):
    pack = clientpack.load_pack(client_id)
    for driver_id, spec in pack.drivers.items():
        low, high, _ = materiality.exposure_range(pack, driver_id)
        assert spec.min <= low < high <= spec.max, driver_id


def test_range_prefers_disclosed_guidance_over_a_chosen_band():
    """adidas guided revenue growth to 7-9%. That range must be used rather
    than one someone picked."""
    pack = clientpack.load_pack("adidas")
    low, high, basis = materiality.exposure_range(pack, "revenue_growth")
    assert (low, high) == (7.0, 9.0)
    assert basis == "disclosed guidance range"


def test_working_capital_exposure_has_the_right_sign_and_scale():
    """A 2.5-point working-capital swing on ~EUR 25.6bn of revenue is ~EUR 640m
    of cash. Checked against arithmetic done by hand, not against the engine."""
    pack = clientpack.load_pack("adidas")
    result = materiality.driver_exposure(pack, "working_capital_pct")

    revenue = model.forecast(
        pack.baseline_group,
        clientpack.read_fact(pack.facts, pack.segments_path),
        pack.to_assumptions(pack.base_driver_values()),
    )["revenue"]
    expected = (result["range_high"] - result["range_low"]) / 100 * revenue

    assert result["exposure_magnitude"] == pytest.approx(expected, rel=1e-9)
    # More working capital consumes cash.
    assert result["exposure"] < 0


def test_an_extra_inventory_day_consumes_cash():
    """The per-unit figure is the form a CFO uses: "+1 day costs EUR Xm"."""
    pack = clientpack.load_pack("manufacturing_demo")
    result = materiality.driver_exposure(pack, "inventory_days")
    assert result["per_unit"] < 0
    # One day of sales at ~EUR 1.9bn revenue is roughly EUR 5m.
    assert 3.0 < abs(result["per_unit"]) < 8.0


def test_paying_later_releases_cash():
    pack = clientpack.load_pack("manufacturing_demo")
    assert materiality.driver_exposure(pack, "dpo_days")["per_unit"] > 0


# --------------------------------------------------------------------------
# Ranking
# --------------------------------------------------------------------------

@pytest.mark.parametrize("client_id", CLIENTS)
def test_ranking_is_by_priority_then_exposure(client_id):
    rows = materiality.rank(clientpack.load_pack(client_id))
    order = [materiality.PRIORITIES.index(r["priority"]) for r in rows]
    assert order == sorted(order), "priority bands must not interleave"

    for band in materiality.PRIORITIES:
        within = [r["exposure_magnitude"] for r in rows if r["priority"] == band]
        assert within == sorted(within, reverse=True), f"{band} not ordered by exposure"


@pytest.mark.parametrize("client_id", CLIENTS)
def test_every_driver_is_ranked_exactly_once(client_id):
    pack = clientpack.load_pack(client_id)
    rows = materiality.rank(pack)
    assert [r["driver_id"] for r in rows] and len(rows) == len(pack.drivers)
    assert {r["driver_id"] for r in rows} == set(pack.drivers)


def test_a_larger_exposure_can_rank_below_a_smaller_controllable_one():
    """The product's central argument, asserted rather than assumed. In the
    manufacturing pack, raw material cost carries more euro exposure than
    capex and ranks below it, because management cannot move it."""
    rows = {r["driver_id"]: r for r in materiality.rank(clientpack.load_pack("manufacturing_demo"))}
    raw, capex = rows["raw_material_cost"], rows["capex_eur_m"]

    assert raw["exposure_magnitude"] > capex["exposure_magnitude"]
    assert raw["controllability"] == "Low" and capex["controllability"] == "High"
    assert materiality.PRIORITIES.index(raw["priority"]) > materiality.PRIORITIES.index(capex["priority"])


@pytest.mark.parametrize("client_id", CLIENTS)
def test_declared_axes_are_labelled_as_declared(client_id):
    """A judgement must never reach the UI looking like a measurement."""
    for row in materiality.rank(clientpack.load_pack(client_id)):
        assert row["basis"] == {
            "materiality": "computed",
            "uncertainty": "declared",
            "controllability": "declared",
        }


def test_thresholds_are_per_client():
    adidas = clientpack.load_pack("adidas").materiality_thresholds
    demo = clientpack.load_pack("manufacturing_demo").materiality_thresholds
    assert adidas != demo
    assert adidas["high"] > adidas["medium"] > 0
    assert demo["high"] > demo["medium"] > 0


def test_banding_respects_the_declared_thresholds():
    thresholds = {"high": 150.0, "medium": 60.0}
    assert materiality.band_exposure(150.0, thresholds) == "High"
    assert materiality.band_exposure(-200.0, thresholds) == "High", "sign must not affect the band"
    assert materiality.band_exposure(60.0, thresholds) == "Medium"
    assert materiality.band_exposure(59.9, thresholds) == "Low"


# --------------------------------------------------------------------------
# Methodology
# --------------------------------------------------------------------------

@pytest.mark.parametrize("client_id", CLIENTS)
def test_methodology_describes_the_rule_actually_applied(client_id):
    """The explanation shown to the user is generated from the same constants
    the engine uses, so the two cannot drift. This asserts it stays that way."""
    pack = clientpack.load_pack(client_id)
    doc = materiality.methodology(pack)

    assert doc["thresholds"] == pack.materiality_thresholds
    assert doc["objective"] == pack.objective
    assert {a["name"] for a in doc["axes"]} == {
        "Financial materiality", "Uncertainty", "Controllability"
    }
    assert [a["basis"] for a in doc["axes"]] == ["computed", "declared", "declared"]
    assert doc["limitations"], "the methodology must state its own limits"

    outcomes = {rule["then"] for rule in doc["rules"]}
    assert outcomes <= set(materiality.PRIORITIES)
    assert "Monitor" in outcomes and "Critical" in outcomes
