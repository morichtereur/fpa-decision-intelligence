"""Claim-level coherence: the checks, and the cases they must not fire on.

The false-positive tests carry as much weight as the catches. A prose linter
that flags correct sentences gets switched off, and then it protects nothing —
so every check here is paired with a sentence it must leave alone.

No API calls: the commentary is synthesised, so this runs in CI.
"""

from __future__ import annotations

from src import claims

# The real FY2025 backtest shape, at the precision the table carries.
RESULT = {
    "actual": {"revenue": 24811.0, "operating_profit": 2056.0, "free_cash_flow": 1106.4},
    "naive": {
        "revenue": 26176.5,
        "operating_profit": 1596.5,
        "free_cash_flow": 1270.2,
        "operating_profit_error_pct": -22.3,
        "free_cash_flow_error_pct": 14.8,
    },
    "driver_based": {
        "revenue": 25585.2,
        "operating_profit": 1750.0,
        "free_cash_flow": 1069.2,
        "operating_profit_error_pct": -14.9,
    },
}
ENTRIES = claims.index_outputs(RESULT)


def check(text: str) -> dict:
    return claims.verify_claims(text, ENTRIES)


# ------------------------------------------------------------------- indexing
def test_series_and_metric_survive_indexing():
    entry = next(e for e in ENTRIES if e.series == "driver_based" and e.metric == "operating_profit")
    assert entry.value == 1750.0
    assert not entry.is_error_pct


def test_error_percentages_are_marked_as_such():
    entry = next(e for e in ENTRIES if e.label == "naive_operating_profit_error_pct")
    assert entry.is_error_pct
    assert entry.metric == "operating_profit"


def test_non_numeric_and_boolean_fields_are_skipped():
    entries = claims.index_outputs({"actual": {"revenue": 1.0, "method": "x", "flag": True}})
    assert [e.metric for e in entries] == ["revenue"]


# ------------------------------------------------------------------ direction
def test_inverted_comparison_is_caught():
    """The failure that shipped: the project's central finding, backwards,
    with every number correct."""
    result = check(
        "Operating profit showed the largest divergence: actual results of 2,056 fell short "
        "of the driver-based forecast of 1,750.0 by 14.9 percent."
    )
    assert not result["clean"]
    assert result["findings"][0]["kind"] == "direction"


def test_the_same_sentence_stated_correctly_passes():
    assert check(
        "Operating profit showed the largest divergence: the driver-based forecast of 1,750.0 "
        "fell short of actual results of 2,056 by 14.9 percent."
    )["clean"]


def test_inverted_exceeded_is_caught():
    assert not check("Free cash flow of 1069.2 exceeded the actual 1106.4.")["clean"]


def test_a_percentage_is_not_compared_against_a_euro_figure():
    """"undershooting by just 3.4 percent" states the size of a gap. Reading
    it as one side of a comparison produces "1,069.2 undershot 3.4"."""
    assert check(
        "Free cash flow of 1,106.4 was closest to the driver-based estimate of 1,069.2, "
        "undershooting by just 3.4 percent."
    )["clean"]


def test_comparisons_do_not_reach_across_clauses():
    assert check(
        "Free cash flow of 1,106.4 was closest to the driver-based estimate of 1,069.2, "
        "undershooting by just 3.4 percent, versus the naive forecast's 14.8 percent "
        "overestimation."
    )["clean"]


def test_one_subject_compared_against_two_objects_is_not_a_comparison_between_them():
    """Real Bedrock output that the checker first flagged wrongly. 2,056 is
    above both forecasts; 1,596.5 and 2,024.4 are its two objects, not a
    comparison with each other. A parenthetical and an "and" separate them."""
    assert check(
        "Operating profit was 2,056, above the naive forecast of 1,596.5 (which understated "
        "actual by 22.3%) and slightly above the driver-based forecast of 1,750.0."
    )["clean"]


def test_thousands_separators_do_not_split_a_clause():
    """A comma inside "2,056" is not a clause boundary. Splitting on it cut the
    number in half and silently disabled every downstream check."""
    assert claims._clause_around("actual results of 2,056 fell short of 1,750.0", 20).count("2,056")


# ------------------------------------------------------------ comparison base
def test_forecast_error_relabelled_as_a_beat_is_caught():
    """-22.3% is the naive forecast's error against actual. The outperformance
    of actual over that forecast is 28.8%. Quoting the first as the second is
    grounded and wrong."""
    result = check(
        "Operating profit outperformed expectations, delivering 2056 against the naive "
        "forecast of 1596.5, beating it by 22.3%."
    )
    assert not result["clean"]
    assert result["findings"][0]["kind"] == "comparison_base"


def test_the_symbol_and_the_word_form_are_treated_alike():
    """"22.3%" and "22.3 percent" must behave identically — a parser that
    handles only the spelled-out form is blind to half the output."""
    symbol = check("Operating profit beat the naive forecast of 1596.5 by 22.3%.")
    word = check("Operating profit beat the naive forecast of 1596.5 by 22.3 percent.")
    assert symbol["finding_count"] == word["finding_count"] == 1


def test_the_same_figure_framed_as_a_forecast_error_passes():
    """Identical number, correct framing: the forecast missed, it did not get
    beaten by that percentage."""
    assert check(
        "The naive forecast understated operating profit of 2056, missing by 22.3%."
    )["clean"]


def test_framing_is_read_per_clause_not_per_sentence():
    """One sentence routinely carries a beat and a shortfall. Attributing the
    first clause's verb to the second clause's figure is a false positive."""
    assert check(
        "Free cash flow of 1106.4 fell short of the naive projection of 1270.2 by 14.8%."
    )["clean"]


# ---------------------------------------------------------------- attribution
def test_a_value_quoted_under_the_wrong_metric_is_caught():
    """The blind spot tests/test_verifier_adversarial.py pins as uncatchable
    by value matching: a real number under the wrong metric's name."""
    result = check("Operating profit came in at 24811.")
    assert not result["clean"]
    assert result["findings"][0]["kind"] == "attribution"


def test_the_same_value_under_its_own_metric_passes():
    assert check("Revenue came in at 24811.")["clean"]


def test_attribution_stays_silent_when_two_metrics_are_in_play():
    """With revenue and operating profit both named, which number belongs to
    which is genuinely ambiguous, and a guardrail should not guess."""
    assert check("Revenue of 24811 and operating profit of 2056 were both reported.")["clean"]


def test_an_ungrounded_number_is_left_to_the_grounding_check():
    """Not this layer's job — and double-reporting one defect as two findings
    would overstate how much is wrong."""
    assert check("Revenue came in at 99999.")["clean"]


# ------------------------------------------------------------------- envelope
def test_prose_without_numbers_is_clean():
    result = check("The forecast performed better than the extrapolation.")
    assert result["clean"] and result["finding_count"] == 0


def test_findings_quote_the_sentence_they_came_from():
    """A finding a reviewer cannot locate in the text is not actionable."""
    text = "Revenue was 24811. Operating profit came in at 24811."
    finding = check(text)["findings"][0]
    assert finding["sentence"] == "Operating profit came in at 24811."
    assert "24811" in finding["detail"]
