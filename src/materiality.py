"""
The decision materiality engine.

Ranks planning drivers by how much management attention they deserve, on
three axes:

  Financial materiality  — COMPUTED. The euro swing in the client's objective
                           KPI when the driver moves across its plausible
                           range, obtained by re-running model.forecast() at
                           each end. No coefficient, no proxy: the same engine
                           that produces the forecast produces the exposure.

  Uncertainty            — DECLARED. The inverse of the driver's disclosure
                           confidence, which the pack states and justifies.

  Controllability        — DECLARED. How far management can move the driver
                           inside the planning horizon.

Two of the three are judgements. That is not a weakness to hide — no amount
of arithmetic extracts "can management influence FX?" from a set of published
financials — but it does mean the UI must label them as judgements, and this
module carries that labelling in `basis` so the frontend cannot lose it.

Why classification rather than a score
--------------------------------------
The tempting formula is materiality x uncertainty x controllability. It is
rejected here for two reasons. It implies a precision the inputs do not have
(two of them are three-point ordinal scales), and it collapses cases that
demand different responses: a large, uncertain, uncontrollable exposure and a
moderate, certain, controllable one can multiply to the same number while
calling for completely different management behaviour.

So the output is a category, produced by a stated rule:

  materiality Low                          -> Monitor
  controllability Low                      -> Monitor   (watch it; you cannot move it)
  materiality High + uncertainty High      -> Critical
  materiality High                         -> Act
  otherwise (materiality Medium)           -> Review

The second line is the one that earns the model its keep. A naive
materiality x uncertainty ranking sends management straight at the largest
uncertain exposure even when nothing can be done about it inside the year.
Ranking it Monitor is a deliberate statement: attention is a budget, and it
should be spent where it converts into an outcome.
"""

from __future__ import annotations

from src import clientpack, model

PRIORITIES = ("Critical", "Act", "Review", "Monitor")
BANDS = ("High", "Medium", "Low")

# Uncertainty is the inverse of declared confidence: an assumption the company
# stated explicitly is a less uncertain input than one carried forward because
# no guidance existed.
CONFIDENCE_TO_UNCERTAINTY = {"High": "Low", "Medium": "Medium", "Low": "High"}

_ORDER = {"High": 0, "Medium": 1, "Low": 2}
_PRIORITY_ORDER = {p: i for i, p in enumerate(PRIORITIES)}


def classify(materiality: str, uncertainty: str, controllability: str) -> str:
    """The stated rule. Kept as one small function so the methodology shown in
    the UI and the behaviour of the engine cannot drift apart."""
    if materiality == "Low":
        return "Monitor"
    if controllability == "Low":
        return "Monitor"
    if materiality == "High" and uncertainty == "High":
        return "Critical"
    if materiality == "High":
        return "Act"
    return "Review"


def band_exposure(exposure: float, thresholds: dict) -> str:
    """Euro exposure -> High/Medium/Low, against thresholds the client sets.

    Thresholds are per client because materiality is relative: EUR 150m is a
    rounding error for one business and an existential number for another.
    """
    magnitude = abs(exposure)
    if magnitude >= thresholds["high"]:
        return "High"
    if magnitude >= thresholds["medium"]:
        return "Medium"
    return "Low"


def exposure_range(pack: clientpack.ClientPack, driver_id: str) -> tuple[float, float, str] | None:
    """The range a driver is swung across to size its exposure, and where that
    range came from.

    Preference order is deliberate: a range the company disclosed beats one
    someone chose. The slider's own min/max is never used — those are the
    bounds of what the model can compute, not of what management considers
    plausible, and using them would make a wide-ranged driver look material
    purely because its slider is long.
    """
    spec = pack.drivers[driver_id]
    if spec.exposure_range is not None:
        low, high = spec.exposure_range
        return low, high, "stated plausible range"
    if spec.guidance_low is not None and spec.guidance_high is not None:
        return spec.guidance_low, spec.guidance_high, "disclosed guidance range"
    return None


def _forecast(pack: clientpack.ClientPack, values: dict) -> dict:
    segments_raw = clientpack.read_fact(pack.facts, pack.segments_path)
    return model.forecast(pack.baseline_group, segments_raw, pack.to_assumptions(values))


OBJECTIVE_TO_METRIC = {
    "Free Cash Flow": "free_cash_flow",
    "EBITDA": "ebitda",
    "EBIT": "operating_profit",
    "Operating Profit": "operating_profit",
    "Revenue": "revenue",
    "Working Capital": "operating_working_capital",
}


def objective_metric(pack: clientpack.ClientPack) -> str:
    try:
        return OBJECTIVE_TO_METRIC[pack.objective]
    except KeyError:
        raise clientpack.ClientPackError(
            f"Client {pack.id!r} names objective {pack.objective!r}, which the model does not "
            f"compute (have: {sorted(OBJECTIVE_TO_METRIC)})"
        ) from None


def driver_exposure(pack: clientpack.ClientPack, driver_id: str) -> dict:
    """The euro swing in the objective KPI across the driver's plausible range.

    Every other driver is held at its baseline, so this is a one-at-a-time
    sensitivity. Interaction effects are not captured — the same limitation
    the FCF bridge carries, and stated for the same reason.
    """
    metric = objective_metric(pack)
    bounds = exposure_range(pack, driver_id)
    if bounds is None:
        # No plausible range has been agreed, so there is no exposure to
        # compute. Saying so is the honest answer; inventing a range around the
        # baseline would put a euro figure on a judgement nobody has made.
        return {"driver_id": driver_id, "metric": metric, "quantified": False,
                "unit": pack.drivers[driver_id].unit, "exposure": 0.0,
                "exposure_magnitude": 0.0, "per_unit": 0.0, "range_basis": "no range declared"}
    low, high, basis = bounds
    base_values = pack.base_driver_values()

    at_low = _forecast(pack, dict(base_values, **{driver_id: low}))[metric]
    at_high = _forecast(pack, dict(base_values, **{driver_id: high}))[metric]
    at_base = _forecast(pack, base_values)[metric]

    spec = pack.drivers[driver_id]
    # Per-unit sensitivity, which is the form a CFO actually uses:
    # "+1 inventory day costs EUR Xm".
    span = high - low
    per_unit = (at_high - at_low) / span if span else 0.0

    return {
        "driver_id": driver_id,
        "metric": metric,
        "quantified": True,
        "range_low": low,
        "range_high": high,
        "range_basis": basis,
        "unit": spec.unit,
        "value_at_low": at_low,
        "value_at_high": at_high,
        "value_at_base": at_base,
        "exposure": at_high - at_low,          # signed: direction carries meaning
        "exposure_magnitude": abs(at_high - at_low),
        "downside": min(at_low, at_high) - at_base,
        "per_unit": per_unit,
    }


def assess_driver(pack: clientpack.ClientPack, driver_id: str, thresholds: dict) -> dict:
    spec = pack.drivers[driver_id]
    exposure = driver_exposure(pack, driver_id)

    if not exposure["quantified"]:
        return {
            **exposure, "label": spec.label, "category": spec.category, "owner": spec.owner,
            "confidence": spec.confidence, "materiality": "Not quantified",
            "uncertainty": CONFIDENCE_TO_UNCERTAINTY[spec.confidence],
            "controllability": spec.controllability, "priority": "Unranked",
            "basis": {"materiality": "not computed", "uncertainty": "declared",
                      "controllability": "declared"},
            "rationale": (
                f"No plausible range has been agreed for {spec.label.lower()}, so its exposure "
                f"cannot be sized. It is shown here rather than hidden, and ranked nowhere."
            ),
        }

    materiality = band_exposure(exposure["exposure_magnitude"], thresholds)
    uncertainty = CONFIDENCE_TO_UNCERTAINTY[spec.confidence]
    controllability = spec.controllability
    priority = classify(materiality, uncertainty, controllability)

    return {
        **exposure,
        "label": spec.label,
        "category": spec.category,
        "owner": spec.owner,
        "confidence": spec.confidence,
        "materiality": materiality,
        "uncertainty": uncertainty,
        "controllability": controllability,
        "priority": priority,
        # What each axis rests on, carried through to the UI so a declared
        # judgement is never displayed as if it had been computed.
        "basis": {
            "materiality": "computed",
            "uncertainty": "declared",
            "controllability": "declared",
        },
        "rationale": _rationale(materiality, uncertainty, controllability, priority, spec.label),
    }


def _rationale(materiality, uncertainty, controllability, priority, label) -> str:
    """Why this row sits where it does, naming the axis that bound the
    decision. Rows in the same band get different sentences when different
    axes put them there — a rationale that reads the same for every row in a
    band is telling the reader nothing the band header did not."""
    if materiality == "Low":
        return (
            f"Ranked on exposure: {label.lower()} moves the objective too little across its "
            f"plausible range to compete for attention, whatever else is true of it."
        )
    if controllability == "Low":
        return (
            f"Ranked on controllability: the exposure is {materiality.lower()}, but management has "
            f"little influence over {label.lower()} inside the horizon. Worth watching; not worth a "
            f"workstream."
        )
    if priority == "Critical":
        return (
            f"Material, unresolved and movable. {label} is the assumption where the plan is least "
            f"settled and management still has a lever."
        )
    if priority == "Act":
        if uncertainty == "Low":
            return (
                f"Large exposure on a firm assumption. The number is not in doubt — the question is "
                f"whether {label.lower()} is being managed to it."
            )
        return (
            f"Large exposure on an assumption that is only partly settled, and management can move it."
        )
    if controllability == "High":
        return f"Moderate exposure, and {label.lower()} is directly controllable. A review, not an escalation."
    return f"Moderate exposure with a partial lever. Worth a review."


def rank(pack: clientpack.ClientPack) -> list[dict]:
    """Every driver, assessed and ordered by priority then by euro exposure.

    Sorting by exposure *within* a priority band, rather than by exposure
    overall, is the whole point: the ranking answers "where should management
    spend the next 30 minutes", not "which number is biggest".
    """
    thresholds = pack.materiality_thresholds
    rows = [assess_driver(pack, driver_id, thresholds) for driver_id in pack.driver_order]
    # Unranked rows sort last: they are part of the model and absent from the
    # ordering, which is exactly their status.
    rows.sort(key=lambda r: (_PRIORITY_ORDER.get(r["priority"], len(PRIORITIES)),
                             -r["exposure_magnitude"]))
    return rows


def _objective_at_plan(pack: clientpack.ClientPack) -> float:
    return _forecast(pack, pack.base_driver_values())[objective_metric(pack)]


def methodology(pack: clientpack.ClientPack) -> dict:
    """The explanation the UI shows next to the ranking. Generated from the
    same constants the engine uses, so it cannot describe a rule that is not
    the one being applied."""
    thresholds = pack.materiality_thresholds
    symbol, unit = pack.currency_symbol, pack.unit
    plan = _objective_at_plan(pack)
    share = lambda value: (value / plan * 100) if plan else 0.0  # noqa: E731
    return {
        "objective": pack.objective,
        "objective_metric": objective_metric(pack),
        "objective_at_plan": plan,
        "thresholds": thresholds,
        "threshold_share": {"high": share(thresholds["high"]), "medium": share(thresholds["medium"])},
        "threshold_text": (
            f"Exposure of {symbol}{thresholds['high']:,.0f}m or more is High "
            f"({share(thresholds['high']):.0f}% of plan {pack.objective.lower()}); "
            f"{symbol}{thresholds['medium']:,.0f}m or more is Medium "
            f"({share(thresholds['medium']):.0f}%); below that, Low."
        ),
        "threshold_rationale": thresholds["rationale"],
        "axes": [
            {
                "name": "Financial materiality",
                "basis": "computed",
                "detail": (
                    f"The swing in {pack.objective.lower()} ({symbol}{unit}) when the driver moves "
                    f"across its plausible range, with every other driver held at plan. Produced by "
                    f"re-running the forecast at each end of the range, not by a coefficient."
                ),
            },
            {
                "name": "Uncertainty",
                "basis": "declared",
                "detail": (
                    "The inverse of the driver's disclosure confidence, which the client pack states "
                    "and justifies. An assumption the company guided to explicitly is a firmer input "
                    "than one carried forward because no guidance existed."
                ),
            },
            {
                "name": "Controllability",
                "basis": "declared",
                "detail": (
                    "How far management can move the driver inside the planning horizon. This is a "
                    "judgement recorded in configuration — it cannot be derived from financial "
                    "statements, and pretending otherwise would be the least defensible thing this "
                    "engine could do."
                ),
            },
        ],
        "rules": [
            {"when": "Materiality is Low", "then": "Monitor",
             "why": "Too small to compete for management attention, whatever else is true of it."},
            {"when": "Controllability is Low", "then": "Monitor",
             "why": "Attention is a budget. An exposure management cannot move does not convert into an outcome."},
            {"when": "Materiality High and Uncertainty High", "then": "Critical",
             "why": "Large, unresolved, and movable — the highest return on management time."},
            {"when": "Materiality High", "then": "Act",
             "why": "Large exposure on a reasonably firm assumption, and controllable."},
            {"when": "Otherwise", "then": "Review",
             "why": "Moderate exposure, controllable — worth a look, not an escalation."},
        ],
        "limitations": [
            "Exposures are one-at-a-time: each driver is swung with the others held at plan, so "
            "interaction effects are not captured.",
            "Uncertainty and controllability are declared judgements, not measurements. They are "
            "auditable in the client pack, but they are opinions.",
            "The priority categories are an ordering device for management attention, not a "
            "probability or a risk score.",
        ],
    }
