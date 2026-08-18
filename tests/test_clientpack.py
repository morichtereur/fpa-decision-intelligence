"""
The pack loader's guard rails.

A malformed pack must fail at load time with a message naming the problem,
not at forecast time with a plausible wrong number. Everything here builds a
deliberately broken pack on disk and asserts it is refused.
"""

import json
import shutil

import pytest

from src import clientpack

BASE = clientpack.CLIENTS_DIR / "adidas"


@pytest.fixture
def pack_dir(tmp_path):
    """A working copy of the adidas pack, for tests to break in one specific
    way each."""
    target = tmp_path / "clients" / "trial"
    shutil.copytree(BASE, target)
    return target


def _edit(path, replace: str, with_: str):
    text = path.read_text()
    assert replace in text, f"fixture drift: {replace!r} not found in {path.name}"
    path.write_text(text.replace(replace, with_, 1))


def load(pack_dir):
    return clientpack.load_pack(pack_dir.name, clients_dir=pack_dir.parent)


def test_the_unmodified_copy_loads(pack_dir):
    """Guards the other tests: if this fails, they are testing the fixture."""
    assert load(pack_dir).name == "adidas AG"


def test_missing_pack_is_rejected(tmp_path):
    with pytest.raises(clientpack.ClientPackError, match="No client pack"):
        clientpack.load_pack("nonexistent", clients_dir=tmp_path)


def test_baseline_outside_its_own_range_is_rejected(pack_dir):
    _edit(pack_dir / "drivers.yaml", "    min: 400\n    max: 700", "    min: 400\n    max: 500")
    with pytest.raises(clientpack.ClientPackError, match="outside its own range"):
        load(pack_dir)


def test_driver_mapping_to_an_unknown_assumption_is_rejected(pack_dir):
    _edit(pack_dir / "drivers.yaml", 'maps_to: "capex_eur_m"', 'maps_to: "gross_margin_pct"')
    with pytest.raises(clientpack.ClientPackError, match="which the model does not"):
        load(pack_dir)


def test_leaving_a_model_assumption_unset_is_rejected(pack_dir):
    """Deleting a driver without replacing what it fed would otherwise
    produce a forecast built on a missing assumption."""
    text = (pack_dir / "drivers.yaml").read_text()
    start = text.index("  tax_rate_pct:")
    (pack_dir / "drivers.yaml").write_text(
        text[:start].replace("  - tax_rate_pct\n", "")
    )
    with pytest.raises(clientpack.ClientPackError, match="leaves model assumption"):
        load(pack_dir)


def test_unknown_confidence_or_controllability_is_rejected(pack_dir):
    _edit(pack_dir / "drivers.yaml", 'controllability: "High"', 'controllability: "Quite high"')
    with pytest.raises(clientpack.ClientPackError, match="controllability"):
        load(pack_dir)


def test_order_must_name_every_driver(pack_dir):
    # Targets the `order:` block specifically. A bare driver-name replace
    # would hit `variance_order:` first, which lists the same ids.
    path = pack_dir / "drivers.yaml"
    text = path.read_text()
    head, _, tail = text.partition("\norder:\n")
    assert tail, "fixture drift: no `order:` block"
    path.write_text(head + "\norder:\n" + tail.replace("  - working_capital_pct\n", "", 1))

    with pytest.raises(clientpack.ClientPackError, match="order"):
        load(pack_dir)


def test_variance_order_may_not_name_an_unknown_driver(pack_dir):
    _edit(pack_dir / "drivers.yaml", "variance_order:\n  - revenue_growth",
          "variance_order:\n  - revenue_growth_v2")
    with pytest.raises(clientpack.ClientPackError, match="variance_order"):
        load(pack_dir)


def test_unknown_solver_is_rejected(pack_dir):
    _edit(pack_dir / "drivers.yaml", "solve: ebitda_margin_for_operating_profit",
          "solve: whatever_makes_the_number_work")
    with pytest.raises(clientpack.ClientPackError, match="Unknown solver"):
        load(pack_dir)


def test_fact_path_that_does_not_exist_is_rejected(pack_dir):
    _edit(pack_dir / "drivers.yaml", 'baseline: {fact: "group.2024.effective_tax_rate_pct"}',
          'baseline: {fact: "group.2024.ebit_margin_after_tax"}')
    with pytest.raises(clientpack.ClientPackError, match="Fact path not found"):
        load(pack_dir)


def test_missing_facts_document_is_rejected(pack_dir):
    (pack_dir / "facts.json").unlink()
    with pytest.raises(clientpack.ClientPackError, match="Missing facts document"):
        load(pack_dir)


def test_a_delta_with_no_base_is_rejected(pack_dir):
    """A delta adjusts something. If nothing establishes the level, the
    adjustment is meaningless and the model would silently start from zero."""
    _edit(pack_dir / "drivers.yaml",
          '    maps_to: "operating_working_capital_pct"',
          '    maps_to: "operating_working_capital_pct"\n    role: "delta"')
    with pytest.raises(clientpack.ClientPackError, match="has no base"):
        load(pack_dir)


def test_resolvers_produce_the_documented_values(pack_dir):
    """The four baseline forms, checked against arithmetic done by hand
    rather than against the loader's own output."""
    facts = json.loads((pack_dir / "facts.json").read_text())
    guidance = facts["guidance"]["fy2025_initial"]

    assert clientpack.resolve_scalar(facts, {"literal": 8.0}) == 8.0
    assert clientpack.resolve_scalar(facts, {"fact": "group.2024.effective_tax_rate_pct"}) == 26.5
    assert clientpack.resolve_scalar(facts, {"midpoint": [
        "guidance.fy2025_initial.operating_working_capital_pct_low",
        "guidance.fy2025_initial.operating_working_capital_pct_high",
    ]}) == pytest.approx((guidance["operating_working_capital_pct_low"]
                          + guidance["operating_working_capital_pct_high"]) / 2)
    assert clientpack.resolve_scalar(
        facts, {"fact_scaled": ["guidance.fy2025_initial.capex_eur_m", 0.95]}
    ) == pytest.approx(guidance["capex_eur_m"] * 0.95)


def test_add_and_delta_roles_behave_differently(pack_dir):
    """The distinction that a naive schema gets wrong: a component counts in
    full at baseline, a deviation counts for nothing."""
    demo = clientpack.load_pack("manufacturing_demo")
    values = demo.base_driver_values()

    # price_growth is an `add`: it contributes its full 2.0 points at plan.
    base_growth = list(demo.to_assumptions(values)["division_growth"].values())[0]
    assert base_growth == pytest.approx((values["volume_growth"] + values["price_growth"]) / 100)

    # inventory_days is a `delta`: at plan it contributes nothing, and one day
    # above plan adds 100/365 of a point to working capital.
    base_wc = demo.to_assumptions(values)["operating_working_capital_pct"]
    assert base_wc == pytest.approx(demo.assumption_bases["operating_working_capital_pct"])

    moved = dict(values, inventory_days=values["inventory_days"] + 1)
    assert demo.to_assumptions(moved)["operating_working_capital_pct"] - base_wc == pytest.approx(
        demo.drivers["inventory_days"].scale
    )

    # DPO carries the opposite sign: paying later releases cash.
    later = dict(values, dpo_days=values["dpo_days"] + 1)
    assert demo.to_assumptions(later)["operating_working_capital_pct"] < base_wc
