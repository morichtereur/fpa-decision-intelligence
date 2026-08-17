from src.commentary import verify_grounding


OUTPUTS = {
    "actual_operating_profit": 2056.0,
    "actual_revenue": 24811.0,
    "driver_based_operating_profit": 1750.0,
    "naive_operating_profit_error_pct": -22.3,
}


def test_fully_grounded_commentary():
    text = (
        "The driver-based forecast of €1,750 million fell short of actual "
        "operating profit of €2,056 million on revenue of €24,811 million."
    )
    result = verify_grounding(text, OUTPUTS)
    assert result["grounding_rate"] == 1.0
    assert result["ungrounded"] == []


def test_hallucinated_number_is_caught():
    text = "Operating profit reached €2,056 million, roughly 12% above what analysts had modeled."
    result = verify_grounding(text, OUTPUTS)
    assert result["grounding_rate"] < 1.0
    assert any("12%" in u for u in result["ungrounded"])


def test_rounding_within_tolerance_is_still_grounded():
    # LLM writes "2,055" for a stored value of 2056.0 -- close enough to be
    # a rounding artifact, not a fabrication.
    text = "Actual operating profit was approximately €2,055 million."
    result = verify_grounding(text, OUTPUTS)
    assert result["grounding_rate"] == 1.0


def test_empty_commentary_has_no_claims():
    result = verify_grounding("No numeric claims here at all.", OUTPUTS)
    assert result["total_claims"] == 0
    assert result["grounding_rate"] is None


def test_magnitude_of_a_negative_table_value_grounds_without_its_sign():
    # The table stores naive_operating_profit_error_pct as -22.3 (signed:
    # forecast came in under actual). Natural-language phrasing states the
    # magnitude of a miss without repeating the sign -- "missed by 22.3%",
    # not "missed by -22.3%". That's not a fabrication and shouldn't be
    # flagged as one.
    text = "The naive forecast missed operating profit by 22.3%."
    result = verify_grounding(text, OUTPUTS)
    assert result["grounding_rate"] == 1.0
