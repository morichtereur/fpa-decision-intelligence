import json

import pytest

from src import backtest, config as C, report, scenario

FACTS_PATH = C.FACTS / "adidas_drivers.json"
pytestmark = pytest.mark.skipif(not FACTS_PATH.exists(), reason="data/facts/adidas_drivers.json not present")


def test_results_md_states_the_actual_numbers():
    facts = json.loads(FACTS_PATH.read_text())
    bt = backtest.run()
    mc = scenario.run_monte_carlo(facts, n=500, seed=0)

    md = report.build_results_md(bt, mc)

    assert "Bottom line" in md
    assert "working capital" in md
    # the actual FY2025 operating profit, not a rounded or invented figure
    assert f"€{bt['actual']['operating_profit']:,.0f}m" in md


def test_chart_is_written(tmp_path):
    facts = json.loads(FACTS_PATH.read_text())
    bt = backtest.run()
    mc = scenario.run_monte_carlo(facts, n=500, seed=0)

    out = tmp_path / "chart.png"
    report.plot_fcf_distribution(mc, bt["actual"]["free_cash_flow"], out)

    assert out.exists()
    assert out.stat().st_size > 0
