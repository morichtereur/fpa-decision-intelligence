"""
Checks the extracted numbers against values read by hand from the source
PDFs (see the exploration in this project's history — every number here
was confirmed against the actual report text before being written down).

Skipped in CI: the source PDFs are gitignored (third-party, large — see
data/raw/README.md), so this only runs where they've been placed locally.
"""

import pytest

from src import config as C
from src import extract

PDFS_PRESENT = (C.RAW / "Adidas_Report_2024.pdf").exists() and (C.RAW / "Adidas_Report_2025.pdf").exists()
pytestmark = pytest.mark.skipif(not PDFS_PRESENT, reason="source PDFs not present in data/raw/")


@pytest.fixture(scope="module")
def facts():
    return extract.run()


def test_group_financials_match_hand_checked_values(facts):
    assert facts["group"]["2023"]["net_sales"] == 21427
    assert facts["group"]["2024"]["net_sales"] == 23683
    assert facts["group"]["2025"]["net_sales"] == 24811
    assert facts["group"]["2025"]["operating_profit"] == 2056
    assert facts["group"]["2025"]["ebitda"] == 3124
    # cash_from_operations must be the € millions figure, not the per-share
    # one — the label appears twice in the source table and a naive parser
    # picks up whichever occurs last (see extract.py's setdefault comment).
    assert facts["group"]["2024"]["cash_from_operations"] == 2910
    assert facts["group"]["2025"]["cash_from_operations"] == 751


def test_product_division_restatement_is_real_and_preserved(facts):
    # As originally reported in the FY2024 report.
    assert facts["product_division"]["2024"]["accessories"] == 1499
    # As restated in the FY2025 report — genuinely different, not a typo.
    assert facts["product_division"]["2024_restated"]["accessories"] == 1779


def test_channel_2024_derived_matches_2025_reports_direct_table(facts):
    # 2024 channel euros are derived from a % share narrative in the 2024
    # report; the 2025 report later discloses 2024 directly as a table.
    # They should be close (both describe the same fiscal year) but the
    # derivation isn't expected to match exactly — checked, not assumed.
    derived = facts["channel"]["2024"]["dtc"]
    reported = facts["channel"]["2024_restated"]["dtc"]
    assert abs(derived - reported) / reported < 0.01


def test_guidance_is_the_stated_fy2025_outlook(facts):
    g = facts["guidance"]["fy2025_initial"]
    assert g["operating_profit_eur_m_low"] == 1700
    assert g["operating_profit_eur_m_high"] == 1800
    assert g["cn_sales_growth"] == "high-single-digit rate"
