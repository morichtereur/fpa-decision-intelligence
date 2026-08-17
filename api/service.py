"""
Everything the API routes need, kept separate from the routes themselves
so the calculation logic is testable without spinning up FastAPI. This
module calls src.model / src.backtest / src.scenario / src.drivers —
it never recomputes a forecast itself. "UI is an interface to the model,
not a second model" applies to this layer too.
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np

from src import backtest, claims, commentary, config as C, drivers, model, scenario

DRIVER_ORDER = ["revenue_growth", "ebitda_margin", "working_capital_pct", "capex_eur_m", "tax_rate_pct"]
DRIVER_TO_ASSUMPTION_KEY = {
    "revenue_growth": None,  # handled specially — feeds every division_growth entry
    "ebitda_margin": "ebitda_margin_pct",
    "working_capital_pct": "operating_working_capital_pct",
    "capex_eur_m": "capex_eur_m",
    "tax_rate_pct": "effective_tax_rate_pct",
}


@lru_cache(maxsize=1)
def load_facts() -> dict:
    return json.loads((C.FACTS / "adidas_drivers.json").read_text())


@lru_cache(maxsize=1)
def get_driver_config() -> dict:
    return drivers.build_driver_config(load_facts())


def _division24() -> dict:
    facts = load_facts()
    return {k: v for k, v in facts["product_division"]["2024"].items() if k != "source"}


def base_driver_values() -> dict:
    return {driver_id: spec["default"] for driver_id, spec in get_driver_config().items()}


def run_forecast(driver_values: dict) -> dict:
    facts = load_facts()
    assumptions = drivers.defaults_to_assumptions(driver_values, _division24())
    return model.forecast(facts["group"]["2024"], facts["product_division"]["2024"], assumptions)


@lru_cache(maxsize=1)
def get_backtest() -> dict:
    return backtest.run()


@lru_cache(maxsize=1)
def get_monte_carlo() -> dict:
    facts = load_facts()
    mc = scenario.run_monte_carlo(facts, n=10_000, seed=0)
    draws = mc.pop("fcf_draws")
    counts, edges = np.histogram(draws, bins=40)
    mc["histogram"] = {
        "counts": counts.tolist(),
        "bin_edges": edges.tolist(),
    }
    return mc


def sensitivity_label(correlation: float) -> str:
    magnitude = abs(correlation)
    if magnitude >= 0.5:
        return "High"
    if magnitude >= 0.2:
        return "Medium"
    return "Low"


DRIVER_TO_SENSITIVITY_KEY = {
    "revenue_growth": "growth",
    "ebitda_margin": "operating_profit_target",
    "working_capital_pct": "working_capital_pct",
    "capex_eur_m": "capex",
    "tax_rate_pct": None,  # not sampled in the Monte Carlo — held fixed, no guided range
}


def get_driver_priority() -> list[dict]:
    """Combines each driver's Monte Carlo sensitivity with its disclosure
    confidence — the ranking the Outlook and Forecast & Risk views use to
    answer "where should FP&A spend the next hour of diligence?"."""
    mc = get_monte_carlo()
    config = get_driver_config()
    rows = []
    for driver_id in DRIVER_ORDER:
        spec = config[driver_id]
        sens_key = DRIVER_TO_SENSITIVITY_KEY[driver_id]
        correlation = mc["sensitivity_to_fcf"].get(sens_key) if sens_key else None
        rows.append({
            "driver_id": driver_id,
            "label": spec["label"],
            "confidence": spec["confidence"],
            "sensitivity": sensitivity_label(correlation) if correlation is not None else "Not simulated",
            "correlation": correlation,
        })
    # Rank by sensitivity magnitude first (Nones/zero last), tie-break by lower confidence
    confidence_rank = {"Low": 0, "Medium": 1, "High": 2}
    rows.sort(key=lambda r: (-(abs(r["correlation"]) if r["correlation"] is not None else -1),
                              confidence_rank.get(r["confidence"], 1)))
    return rows


def build_executive_statement() -> dict:
    bt = get_backtest()
    priority = get_driver_priority()
    top = priority[0]

    op_error = bt["driver_based"]["operating_profit_error_pct"]
    # pct_error = (forecast - actual) / actual * 100, so a negative error
    # means the forecast landed below what was actually delivered.
    direction = "below" if op_error < 0 else "above"

    headline = (
        f"FY2025 outlook landed {direction} actual operating profit even when "
        f"built directly from adidas's own guidance, while "
        f"{top['label'].lower()} remains the largest source of forecast risk."
    )
    evidence = [
        f"Driver-based operating profit forecast missed actual FY2025 results by "
        f"{abs(op_error):.1f}% (€{bt['driver_based']['operating_profit']:,.0f}m vs. "
        f"€{bt['actual']['operating_profit']:,.0f}m actual).",
        f"{top['label']} shows {top['sensitivity'].lower()} sensitivity to free cash flow "
        f"({top['confidence'].lower()} confidence assumption).",
        f"Naive extrapolation would have missed by more on every metric — see Forecast & Risk.",
    ]
    return {"headline": headline, "evidence": evidence}


def get_outlook() -> dict:
    base = run_forecast(base_driver_values())
    bt = get_backtest()
    statement = build_executive_statement()
    return {
        "forecast": base,
        "backtest": bt,
        "statement": statement,
        "driver_priority": get_driver_priority()[:3],
    }


def resolve_preset(preset_id: str) -> dict:
    if preset_id not in drivers.PRESETS:
        raise KeyError(preset_id)
    base = base_driver_values()
    overrides = drivers.PRESETS[preset_id]["overrides"]
    values = dict(base)
    if "ebitda_margin_pct_delta" in overrides:
        values["ebitda_margin"] = base["ebitda_margin"] + overrides["ebitda_margin_pct_delta"]
    for key, value in overrides.items():
        if key == "ebitda_margin_pct_delta":
            continue
        values[key] = value
    return values


def get_presets() -> dict:
    return {
        preset_id: {
            "label": spec["label"],
            "values": resolve_preset(preset_id),
            "changed_drivers": [k for k in DRIVER_ORDER if resolve_preset(preset_id)[k] != base_driver_values()[k]],
        }
        for preset_id, spec in drivers.PRESETS.items()
    }


def out_of_guidance(driver_id: str, value: float) -> bool:
    spec = get_driver_config()[driver_id]
    low, high = spec.get("guidance_low"), spec.get("guidance_high")
    if low is None or high is None:
        return False
    return value < low or value > high


class DriverValueError(ValueError):
    """A driver value outside the range the model is defined over."""


def validate_driver_values(driver_values: dict) -> None:
    """Names and ranges, checked against drivers.py rather than re-declared.

    The UI cannot produce an out-of-range value — its sliders are bounded by
    the same spec — so this only ever fires on a hand-made request. Worth
    having anyway: the endpoint is public, and an unbounded revenue_growth
    produces confident nonsense rather than an error.

    Note this bounds `min`/`max`, not the narrower `guidance_low`/`_high`.
    Moving outside the company's disclosed guidance is a deliberate feature
    (the UI flags it red); leaving the model's own domain is not.
    """
    config = get_driver_config()
    known = set(config)
    unknown = sorted(set(driver_values) - known)
    if unknown:
        raise DriverValueError(f"Unknown driver(s): {unknown}")
    missing = sorted(known - set(driver_values))
    if missing:
        raise DriverValueError(f"Missing driver(s): {missing}")

    for name, spec in config.items():
        value = driver_values[name]
        low, high = spec.get("min"), spec.get("max")
        if low is not None and value < low:
            raise DriverValueError(f"{name}={value} is below the minimum of {low}")
        if high is not None and value > high:
            raise DriverValueError(f"{name}={value} is above the maximum of {high}")


def compute_scenario(driver_values: dict) -> dict:
    base_values = base_driver_values()
    base_forecast = run_forecast(base_values)
    scenario_forecast = run_forecast(driver_values)

    deltas = {}
    for key in ("revenue", "operating_profit", "free_cash_flow", "operating_working_capital"):
        deltas[key] = scenario_forecast[key] - base_forecast[key]

    changed = {k: {"base": base_values[k], "value": driver_values[k]}
               for k in DRIVER_ORDER if driver_values[k] != base_values[k]}
    warnings = {k: out_of_guidance(k, v) for k, v in driver_values.items() if out_of_guidance(k, v)}

    return {
        "base": base_forecast,
        "scenario": scenario_forecast,
        "deltas": deltas,
        "changed_drivers": changed,
        "out_of_guidance": warnings,
        "bridge": compute_bridge(base_values, driver_values),
    }


DRIVER_BRIDGE_LABELS = {
    "revenue_growth": "Revenue growth",
    "ebitda_margin": "EBITDA margin",
    "working_capital_pct": "Working capital",
    "capex_eur_m": "Capex",
    "tax_rate_pct": "Tax rate",
}


def compute_bridge(base_values: dict, scenario_values: dict) -> list[dict]:
    """Sequential FCF waterfall: applies each changed driver one at a time,
    in a fixed order, and attributes the resulting FCF delta to it. This is
    order-dependent for drivers with interaction effects (standard
    limitation of sequential bridge analysis) — noted in the UI, not
    hidden."""
    current = dict(base_values)
    prev_fcf = run_forecast(current)["free_cash_flow"]
    steps = [{"label": "Base", "value": prev_fcf, "delta": None}]
    for key in DRIVER_ORDER:
        if scenario_values[key] == base_values[key]:
            continue
        current[key] = scenario_values[key]
        new_fcf = run_forecast(current)["free_cash_flow"]
        steps.append({"label": DRIVER_BRIDGE_LABELS[key], "value": new_fcf, "delta": new_fcf - prev_fcf})
        prev_fcf = new_fcf
    if len(steps) > 1:
        steps.append({"label": "Scenario", "value": prev_fcf, "delta": None})
    return steps


def get_assumption_register() -> list[dict]:
    config = get_driver_config()
    priority = {row["driver_id"]: row for row in get_driver_priority()}
    register = []
    for driver_id in DRIVER_ORDER:
        spec = config[driver_id]
        p = priority[driver_id]
        register.append({
            "driver_id": driver_id,
            "label": spec["label"],
            "current_value": spec["default"],
            "unit": spec["unit"],
            "source": spec["source"],
            "guidance_text": spec["guidance_text"],
            "confidence": spec["confidence"],
            "sensitivity": p["sensitivity"],
            "fiscal_year": "FY2025",
        })
    return register


def get_commentary_for(scenario_id: str) -> dict | None:
    path = C.DATA / "commentary.json"
    if not path.exists():
        return None
    all_commentary = json.loads(path.read_text())
    return all_commentary.get(scenario_id)


def generate_live_commentary(driver_values: dict, series_name: str = "scenario") -> dict:
    """`series_name` labels the forecast series in the table the LLM writes
    from, and the model calls the series by the name it is given.

    The default is the neutral one on purpose. It used to be `driver_based`,
    which was right for the backtest and wrong for everything else: a caller
    that forgot to pass a name — as /api/commentary/live did — got a custom
    stress scenario described as "the driver-based forecast", contradicting
    the backtest's own error on the same page. Only `generate_commentary.py`
    names the base case explicitly now, so forgetting fails safe.
    """
    scenario_forecast = run_forecast(driver_values)
    base_forecast = run_forecast(base_driver_values())
    bt = get_backtest()
    pseudo_backtest_result = {
        "actual": bt["actual"],
        "naive": bt["naive"],
        series_name: {
            **scenario_forecast,
            "revenue_error_pct": (scenario_forecast["revenue"] - bt["actual"]["revenue"]) / bt["actual"]["revenue"] * 100,
            "operating_profit_error_pct": (scenario_forecast["operating_profit"] - bt["actual"]["operating_profit"]) / bt["actual"]["operating_profit"] * 100,
            "free_cash_flow_error_pct": (scenario_forecast["free_cash_flow"] - bt["actual"]["free_cash_flow"]) / bt["actual"]["free_cash_flow"] * 100,
        },
    }
    text, outputs, provenance = commentary.write(pseudo_backtest_result)
    grounding = commentary.verify_grounding(text, outputs)
    # Two independent questions. Grounding: is this number in the table?
    # Coherence: is it being used to say something the table supports? A
    # paragraph can pass the first completely and fail the second, which is
    # exactly what the published presets did.
    coherence = claims.verify_claims(text, claims.index_outputs(pseudo_backtest_result))
    return {
        "text": text,
        "grounding": grounding,
        "coherence": coherence,
        "provenance": provenance,
    }
