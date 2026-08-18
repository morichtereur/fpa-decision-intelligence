"""
Decision rules and the executive brief.

The rules are the part of the product most likely to overreach: it would be
easy to present a fired threshold as a finding, or a suggested owner as an
assignment. These tests pin the behaviour and the language.
"""

import pytest

from api import service
from src import clientpack, decisions, materiality

CLIENTS = clientpack.available_clients()


@pytest.mark.parametrize("client_id", CLIENTS)
def test_base_case_breaches_nothing(client_id):
    """A client's plan is by definition inside its own tolerances. If the base
    case fires a rule, either the plan or the threshold is wrong."""
    brief = decisions.brief(clientpack.load_pack(client_id))
    assert brief["breached_count"] == 0
    assert brief["is_base_case"] is True


@pytest.mark.parametrize("client_id,preset,expect_metric", [
    ("adidas", "wc_stress", "working_capital_pct"),
    ("manufacturing_demo", "wc_slippage", "inventory_days"),
])
def test_a_stress_scenario_breaches_the_rule_it_should(client_id, preset, expect_metric):
    pack = clientpack.load_pack(client_id)
    values = service.resolve_preset(preset, client_id)
    brief = decisions.brief(pack, values)

    breached = {r["metric"] for r in brief["rules"] if r["breached"]}
    assert expect_metric in breached
    assert brief["breached_count"] > 0
    assert brief["is_base_case"] is False


@pytest.mark.parametrize("client_id", CLIENTS)
def test_un_breached_rules_are_still_reported(client_id):
    """A screen that only renders problems teaches nothing about what was
    tested. Every rule comes back, breached or not."""
    pack = clientpack.load_pack(client_id)
    brief = decisions.brief(pack)
    assert len(brief["rules"]) == len(pack.decision_rules)
    assert all(r["breached"] is False for r in brief["rules"])


def test_breached_rules_sort_before_unbreached_and_by_severity():
    pack = clientpack.load_pack("manufacturing_demo")
    rules = decisions.brief(pack, service.resolve_preset("wc_slippage", "manufacturing_demo"))["rules"]

    breached_flags = [r["breached"] for r in rules]
    assert breached_flags == sorted(breached_flags, reverse=True)

    severities = [decisions._SEVERITY_ORDER[r["severity"]] for r in rules if r["breached"]]
    assert severities == sorted(severities)


@pytest.mark.parametrize("client_id", CLIENTS)
def test_every_rule_declares_a_question_an_owner_and_a_trigger(client_id):
    """A threshold with no question attached is an alert, not a decision
    support. The pack is required to say what to ask and who to ask."""
    pack = clientpack.load_pack(client_id)
    for rule in decisions.brief(pack)["rules"]:
        assert rule["management_question"].strip(), rule["id"]
        assert rule["suggested_owner"].strip(), rule["id"]
        assert rule["trigger"].strip(), rule["id"]
        assert rule["severity"] in decisions.SEVERITIES


@pytest.mark.parametrize("client_id", CLIENTS)
def test_the_brief_answers_every_executive_question(client_id):
    pack = clientpack.load_pack(client_id)
    brief = decisions.brief(pack)
    lead = brief["lead"]

    assert lead["label"]                       # what matters
    assert lead["exposure_magnitude"] > 0      # how much is at risk
    assert lead["category"]                    # why
    assert "threshold" in lead                 # outside tolerance?
    assert lead["controllability"] in ("High", "Medium", "Low")
    assert lead["management_question"].strip() # what to discuss
    assert lead["suggested_owner"].strip()     # who owns it
    assert brief["attention"]["state"] in ("critical", "attention", "steady")


@pytest.mark.parametrize("client_id", CLIENTS)
def test_the_lead_is_the_top_ranked_driver_not_the_largest_number(client_id):
    """The brief leads with the top *priority*, which is not always the
    largest euro exposure. That difference is the product's argument."""
    brief = decisions.brief(clientpack.load_pack(client_id))
    assert brief["lead"]["driver_id"] == brief["ranked"][0]["driver_id"]


def test_the_ranking_is_not_merely_a_sort_by_size():
    """The property that distinguishes this from a sensitivity table: at least
    one lower-priority driver carries MORE euro exposure than a
    higher-priority one, because controllability moved it down.

    In the manufacturing pack that is raw material cost (uncontrollable, and
    ranked Monitor) sitting above capex and EBITDA margin on exposure while
    ranking below them on priority.
    """
    ranked = decisions.brief(clientpack.load_pack("manufacturing_demo"))["ranked"]

    inversions = [
        (lower, higher)
        for i, higher in enumerate(ranked)
        for lower in ranked[i + 1:]
        if lower["exposure_magnitude"] > higher["exposure_magnitude"]
    ]
    assert inversions, "ranking is indistinguishable from ordering by exposure alone"

    # and every such inversion is explained by controllability or materiality
    for lower, higher in inversions:
        assert (lower["controllability"] == "Low"
                or materiality.BANDS.index(lower["materiality"])
                > materiality.BANDS.index(higher["materiality"])), (
            f"{lower['label']} outranked by {higher['label']} for no stated reason"
        )


@pytest.mark.parametrize("client_id", CLIENTS)
def test_language_never_issues_an_instruction(client_id):
    """The product suggests questions and owners. It does not tell a CFO what
    to do, because it cannot support that claim."""
    pack = clientpack.load_pack(client_id)
    brief = decisions.brief(pack)

    forbidden = ("you must", "you should", "we recommend", "the company should", "management must")
    texts = [brief["lead"]["management_question"]]
    texts += [r["management_question"] for r in brief["rules"]]
    texts += [r["next_action"] for r in brief["rules"]]
    texts += [r["rationale"] for r in brief["ranked"]]

    for text in texts:
        lowered = text.lower()
        for phrase in forbidden:
            assert phrase not in lowered, f"{phrase!r} in {text!r}"


def test_unknown_condition_is_rejected():
    pack = clientpack.load_pack("adidas")
    rule = {"id": "bad", "metric": "free_cash_flow", "condition": "vibes", "threshold": 1}
    with pytest.raises(clientpack.ClientPackError, match="unknown condition"):
        decisions.evaluate_rule(rule, pack, pack.base_driver_values(), {"free_cash_flow": 1}, {"free_cash_flow": 1})


def test_rule_naming_an_unknown_metric_is_rejected():
    pack = clientpack.load_pack("adidas")
    rule = {"id": "bad", "metric": "ebitda_per_employee", "condition": "above", "threshold": 1}
    with pytest.raises(clientpack.ClientPackError, match="neither a driver"):
        decisions.evaluate_rule(rule, pack, pack.base_driver_values(), {}, {})


def test_rules_do_not_apply_across_clients():
    """adidas has no inventory_days rule and the manufacturer has no
    guidance-floor rule. Neither should see the other's thresholds."""
    adidas = {r["metric"] for r in service.get_decision_rules("adidas")}
    demo = {r["metric"] for r in service.get_decision_rules("manufacturing_demo")}
    assert "inventory_days" in demo and "inventory_days" not in adidas
    assert not demo & {"working_capital_pct"}


def test_brief_endpoint_matches_the_engine():
    from fastapi.testclient import TestClient
    from api.main import app

    api = TestClient(app)
    values = service.resolve_preset("wc_stress", "adidas")
    response = api.post("/api/decision-brief", json={"driver_values": values, "client": "adidas"})

    assert response.status_code == 200
    direct = decisions.brief(clientpack.load_pack("adidas"), values)
    assert response.json()["breached_count"] == direct["breached_count"]
    assert response.json()["lead"]["driver_id"] == direct["lead"]["driver_id"]
