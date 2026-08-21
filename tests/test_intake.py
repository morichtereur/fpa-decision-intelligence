"""
The intake workbook round-trip.

A consultant fills a spreadsheet; a complete, loadable client pack comes out.
The failure mode that matters is not a crash — it is a workbook that produces
a pack quietly missing something, because the pack then builds, loads and
ranks as though the missing thing was never meant to be there.
"""

import pytest

from src import clientpack, decisions, materiality
from src.intake import IntakeError, build_pack, read_workbook, write_template

openpyxl = pytest.importorskip("openpyxl")


DRIVERS = [
    # id, label, category, unit, baseline, min, max, step, exp_low, exp_high,
    # maps_to, role, sign, scale, confidence, controllability, owner, source, guidance
    ["volume_growth", "Volume growth", "Commercial", "pct", 3.0, -8, 10, 0.5, -2, 6,
     "division_growth", "base", "", 0.01, "Medium", "Medium", "CCO", "plan", ""],
    ["ebitda_margin", "EBITDA margin", "Margin", "pct", 14.0, 10, 18, 0.1, 12.5, 15.5,
     "ebitda_margin_pct", "base", "", "", "Medium", "Medium", "CFO", "plan", ""],
    ["dso_days", "DSO", "Working Capital", "days", 58, 40, 90, 1, 52, 68,
     "operating_working_capital_pct", "delta", 1, 0.27397, "Medium", "High", "Credit", "plan", ""],
    # Deliberately named after the template's own example driver. A reader that
    # discards rows by matching the example's content deletes this one silently.
    ["inventory_days", "Inventory days", "Working Capital", "days", 96, 70, 140, 1, 88, 112,
     "operating_working_capital_pct", "delta", 1, 0.27397, "Medium", "High", "Supply", "plan", ""],
    ["capex_eur_m", "Capex", "Investment", "eur_m", 72, 40, 120, 2, 60, 90,
     "capex_eur_m", "base", "", "", "Medium", "High", "CFO", "plan", ""],
    ["tax_rate_pct", "Effective tax rate", "Tax", "pct", 24.0, 18, 32, 0.5, 22, 27,
     "effective_tax_rate_pct", "base", "", "", "Low", "Low", "Tax", "plan", ""],
]

CLIENT = {
    "client_id": "trial_co", "name": "Trial Co AG", "short_label": "Trial",
    "data_basis": "Client Data", "is_synthetic": "FALSE", "industry": "Chemicals",
    "currency": "EUR", "currency_symbol": "€", "unit": "millions",
    "fiscal_year": "FY2026", "baseline_year": "FY2025", "objective": "Free Cash Flow",
    "materiality_high": "40", "materiality_medium": "15",
    "materiality_rationale": "Half a year's free cash flow.", "disclaimer": "Illustrative.",
}
BASELINE = {"net_sales": 1200, "gross_profit": 384, "ebitda": 168, "operating_profit": 102,
            "effective_tax_rate_pct": 24.0, "operating_working_capital_pct": 26.0, "capex": 72}
SEGMENTS = [("specialities", 640), ("intermediates", 380), ("services", 180)]


def _fill(path, client=None, drivers=None, segments=None, baseline=None, rules=None):
    wb = openpyxl.load_workbook(path)
    rows = {r[0].value: r[0].row for r in wb["Client"].iter_rows(min_row=2, max_col=1)}
    for key, value in (client or CLIENT).items():
        wb["Client"].cell(rows[key], 2).value = value
    brows = {r[0].value: r[0].row for r in wb["Baseline"].iter_rows(min_row=2, max_col=1)}
    for key, value in (baseline or BASELINE).items():
        wb["Baseline"].cell(brows[key], 2).value = value
    for i, (name, revenue) in enumerate(segments or SEGMENTS, start=2):
        wb["Segments"].cell(i, 1).value, wb["Segments"].cell(i, 2).value = name, revenue
    for row in (drivers if drivers is not None else DRIVERS):
        wb["Drivers"].append(row)
    for row in (rules or []):
        wb["Rules"].append(row)
    wb.save(path)
    return path


@pytest.fixture
def built(tmp_path):
    book = write_template(tmp_path / "intake.xlsx", "trial_co")
    _fill(book)
    clients = tmp_path / "clients"
    build_pack(read_workbook(book), clients_dir=clients)
    return clientpack.load_pack("trial_co", clients_dir=clients)


# --------------------------------------------------------------------------
# The round trip
# --------------------------------------------------------------------------

def test_a_filled_workbook_produces_a_loadable_pack(built):
    assert built.name == "Trial Co AG"
    assert built.objective == "Free Cash Flow"
    assert built.materiality_thresholds["rationale"]


def test_every_driver_entered_survives(built):
    """The regression that matters. The reader once discarded rows by matching
    the template's example id, so a real driver called `inventory_days` was
    deleted without a word — and the pack still built, loaded and ranked, just
    without it. A silent drop is worse than a crash: the workbook still looks
    right."""
    assert len(built.drivers) == len(DRIVERS)
    assert list(built.driver_order) == [d[0] for d in DRIVERS]
    assert "inventory_days" in built.drivers


def test_the_generated_pack_drives_the_whole_engine(built):
    ranked = materiality.rank(built)
    assert len(ranked) == len(DRIVERS)
    assert all(r["exposure_magnitude"] >= 0 for r in ranked)

    brief = decisions.brief(built)
    assert brief["lead"]["label"]
    assert brief["lead"]["suggested_owner"]


def test_days_drivers_convert_into_the_model_correctly(built):
    """Working capital entered in days has to reach the model as a percentage
    of sales, or every euro exposure downstream is wrong by a factor of 365."""
    values = built.base_driver_values()
    base = built.to_assumptions(values)["operating_working_capital_pct"]
    moved = built.to_assumptions(dict(values, inventory_days=values["inventory_days"] + 1))
    assert moved["operating_working_capital_pct"] - base == pytest.approx(0.27397, abs=1e-4)


def test_no_backtest_is_claimed(built):
    """The intake collects a plan, never an outturn. Claiming a backtest from
    it would be inventing evidence."""
    assert built.has_backtest is False


# --------------------------------------------------------------------------
# What it refuses
# --------------------------------------------------------------------------

def test_a_blank_workbook_is_rejected(tmp_path):
    book = write_template(tmp_path / "blank.xlsx", "trial_co")
    with pytest.raises(IntakeError):
        build_pack(read_workbook(book), clients_dir=tmp_path / "clients")


def test_a_missing_rationale_is_rejected(tmp_path):
    """A threshold nobody can justify is a threshold nobody should trust."""
    book = write_template(tmp_path / "i.xlsx", "trial_co")
    _fill(book, client={**CLIENT, "materiality_rationale": None})
    with pytest.raises(IntakeError, match="materiality_rationale"):
        build_pack(read_workbook(book), clients_dir=tmp_path / "clients")


def test_deltas_with_no_base_are_rejected_with_a_useful_message(tmp_path):
    """Working capital driven only by day counts has no level for them to
    adjust unless the baseline sheet supplies one — and if the assumption is
    not working capital, the intake cannot guess."""
    book = write_template(tmp_path / "i.xlsx", "trial_co")
    only_deltas = [d for d in DRIVERS if d[10] != "ebitda_margin_pct"]
    only_deltas.append(["margin_drift", "Margin drift", "Margin", "ppt", 0.0, -3, 3, 0.25, 0, 2,
                        "ebitda_margin_pct", "delta", -1, "", "Low", "Low", "CFO", "plan", ""])
    _fill(book, drivers=only_deltas)
    with pytest.raises(IntakeError, match="nothing sets its level"):
        build_pack(read_workbook(book), clients_dir=tmp_path / "clients")


def test_a_driver_missing_a_required_number_names_its_row(tmp_path):
    book = write_template(tmp_path / "i.xlsx", "trial_co")
    broken = [list(d) for d in DRIVERS]
    broken[1][4] = None  # baseline
    _fill(book, drivers=broken)
    with pytest.raises(IntakeError, match="ebitda_margin"):
        build_pack(read_workbook(book), clients_dir=tmp_path / "clients")


def test_the_template_alone_reads_as_empty(tmp_path):
    """The template ships an example row and a guidance row. Neither may be
    mistaken for data."""
    intake = read_workbook(write_template(tmp_path / "t.xlsx", "trial_co"))
    assert intake["drivers"] == []
    assert intake["rules"] == []
