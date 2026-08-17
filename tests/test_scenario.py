import pytest

from src import clientpack, scenario, config as C

FACTS_PATH = C.FACTS / "adidas_drivers.json"
pytestmark = pytest.mark.skipif(not FACTS_PATH.exists(), reason="data/facts/adidas_drivers.json not present")


@pytest.fixture(scope="module")
def facts():
    """The adidas pack. Named `facts` still because that is what the ranges
    ultimately come from — they are resolved out of the facts document by the
    pack rather than hardcoded in src.scenario."""
    return clientpack.load_pack("adidas")


def test_monte_carlo_is_deterministic_given_a_seed(facts):
    a = scenario.run_monte_carlo(facts, n=500, seed=0)
    b = scenario.run_monte_carlo(facts, n=500, seed=0)
    assert a["fcf_p50"] == b["fcf_p50"]


def test_working_capital_dominates_fcf_variance(facts):
    """The actual finding: working-capital % of sales explains more of the
    simulated FCF variance than revenue growth does -- matching what the
    backtest separately shows (the naive method's FCF error came mostly
    from missing the working-capital build, not from missing revenue
    growth). If this stops holding, the finding needs re-checking."""
    result = scenario.run_monte_carlo(facts, n=5000, seed=1)
    ranked = list(result["sensitivity_to_fcf"].keys())
    assert ranked[0] == "working_capital_pct"
    assert abs(result["sensitivity_to_fcf"]["working_capital_pct"]) > abs(result["sensitivity_to_fcf"]["growth"])
