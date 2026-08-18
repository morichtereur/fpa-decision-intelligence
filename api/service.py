"""
Everything the API routes need, kept separate from the routes themselves so
the calculation logic is testable without spinning up FastAPI. This module
calls src.clientpack / src.model / src.backtest / src.scenario — it never
recomputes a forecast itself. "UI is an interface to the model, not a second
model" applies to this layer too.

Every function takes a `client` id and resolves it to a pack. There is no
module-level mutable "active client": the mechanism that prevents one
client's numbers appearing under another's label is that nothing is shared
between them except the engine's pure functions. Caches are keyed by client
id for the same reason — see tests/test_client_switching.py, which asserts
the absence of leakage rather than assuming it.
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np

from src import (backtest, claims, clientpack, commentary, config as C, decisions,
                 materiality, model, scenario, variance)


def pack(client: str | None = None) -> clientpack.ClientPack:
    return clientpack.get_pack(clientpack.resolve_client_id(client))


def list_clients() -> list[dict]:
    """Identity only — enough for the client selector, without loading every
    pack's full driver set."""
    return [clientpack.get_pack(cid).summary() for cid in clientpack.available_clients()]


def get_client_summary(client: str | None = None) -> dict:
    return pack(client).summary()


def get_driver_config(client: str | None = None) -> dict:
    p = pack(client)
    return {driver_id: p.drivers[driver_id].to_dict() for driver_id in p.driver_order}


def driver_order(client: str | None = None) -> list[str]:
    return list(pack(client).driver_order)


def base_driver_values(client: str | None = None) -> dict:
    return pack(client).base_driver_values()


def run_forecast(driver_values: dict, client: str | None = None) -> dict:
    p = pack(client)
    assumptions = p.to_assumptions(driver_values)
    segments_raw = clientpack.read_fact(p.facts, p.segments_path)
    return model.forecast(p.baseline_group, segments_raw, assumptions)


# --------------------------------------------------------------------------
# Backtest and simulation
# --------------------------------------------------------------------------

@lru_cache(maxsize=8)
def get_backtest(client: str | None = None) -> dict | None:
    """None where a client has no honest backtest to show.

    manufacturing_demo is synthetic: a backtest against invented actuals
    would be a number that looks like evidence and is not. Returning None and
    letting the UI say so is the correct answer, not a gap to fill.
    """
    p = pack(client)
    if not p.has_backtest:
        return None
    return backtest.run()


@lru_cache(maxsize=8)
def get_monte_carlo(client: str | None = None) -> dict:
    mc = scenario.run_monte_carlo(pack(client))
    draws = mc.pop("fcf_draws")
    counts, edges = np.histogram(draws, bins=40)
    mc["histogram"] = {"counts": counts.tolist(), "bin_edges": edges.tolist()}
    return mc


def sensitivity_label(correlation: float) -> str:
    magnitude = abs(correlation)
    if magnitude >= 0.5:
        return "High"
    if magnitude >= 0.2:
        return "Medium"
    return "Low"


def get_driver_priority(client: str | None = None) -> list[dict]:
    """Each driver's simulated sensitivity to free cash flow alongside its
    disclosure confidence and its declared controllability.

    This is still the inherited two-axis ranking: sensitivity magnitude first,
    lower confidence as the tie-break. Controllability is carried on each row
    but does not yet affect the order — the three-axis materiality engine
    replaces this ranking, and until it lands the honest thing is to expose
    the axis without pretending it is already being used.
    """
    p = pack(client)
    mc = get_monte_carlo(client)
    rows = []
    for driver_id in p.driver_order:
        spec = p.drivers[driver_id]
        correlation = mc["sensitivity_to_fcf"].get(spec.sensitivity_key) if spec.sensitivity_key else None
        rows.append({
            "driver_id": driver_id,
            "label": spec.label,
            "category": spec.category,
            "confidence": spec.confidence,
            "controllability": spec.controllability,
            "owner": spec.owner,
            "sensitivity": sensitivity_label(correlation) if correlation is not None else "Not simulated",
            "correlation": correlation,
        })
    confidence_rank = {"Low": 0, "Medium": 1, "High": 2}
    rows.sort(key=lambda r: (-(abs(r["correlation"]) if r["correlation"] is not None else -1),
                             confidence_rank.get(r["confidence"], 1)))
    return rows


# --------------------------------------------------------------------------
# Outlook
# --------------------------------------------------------------------------

def build_executive_statement(client: str | None = None) -> dict:
    p = pack(client)
    priority = get_driver_priority(client)
    top = priority[0]
    bt = get_backtest(client)

    if bt is None:
        headline = (
            f"{p.name}'s {p.fiscal_year} plan turns on {top['label'].lower()}, which carries the "
            f"largest simulated effect on free cash flow of any assumption in the model."
        )
        evidence = [
            f"{top['label']} shows {top['sensitivity'].lower()} sensitivity to free cash flow "
            f"({top['confidence'].lower()} confidence assumption, "
            f"{top['controllability'].lower()} management controllability).",
            "No backtest is shown for this client: the data is synthetic, and a forecast error "
            "measured against invented actuals would not be evidence of anything.",
            f"Ranges are constructed, not measured — see the caveat on the simulation.",
        ]
        return {"headline": headline, "evidence": evidence}

    op_error = bt["driver_based"]["operating_profit_error_pct"]
    # pct_error = (forecast - actual) / actual * 100, so a negative error
    # means the forecast landed below what was actually delivered.
    direction = "below" if op_error < 0 else "above"
    headline = (
        f"{p.fiscal_year} outlook landed {direction} actual operating profit even when "
        f"built directly from {p.short_label}'s own guidance, while "
        f"{top['label'].lower()} remains the largest source of forecast risk."
    )
    evidence = [
        f"Driver-based operating profit forecast missed actual {p.fiscal_year} results by "
        f"{abs(op_error):.1f}% ({p.currency_symbol}{bt['driver_based']['operating_profit']:,.0f}m vs. "
        f"{p.currency_symbol}{bt['actual']['operating_profit']:,.0f}m actual).",
        f"{top['label']} shows {top['sensitivity'].lower()} sensitivity to free cash flow "
        f"({top['confidence'].lower()} confidence assumption).",
        "Naive extrapolation would have missed by more on every metric — see Evidence.",
    ]
    return {"headline": headline, "evidence": evidence}


def get_outlook(client: str | None = None) -> dict:
    return {
        "client": get_client_summary(client),
        "forecast": run_forecast(base_driver_values(client), client),
        "backtest": get_backtest(client),
        "statement": build_executive_statement(client),
        "driver_priority": get_driver_priority(client)[:3],
    }


# --------------------------------------------------------------------------
# Presets and scenarios
# --------------------------------------------------------------------------

def resolve_preset(preset_id: str, client: str | None = None) -> dict:
    p = pack(client)
    if preset_id not in p.presets:
        raise KeyError(preset_id)
    values = p.base_driver_values()
    for driver_id, override in (p.presets[preset_id].get("overrides") or {}).items():
        if driver_id not in values:
            raise clientpack.ClientPackError(
                f"Preset {preset_id!r} overrides unknown driver {driver_id!r} for client {p.id!r}"
            )
        if "set" in override:
            values[driver_id] = float(override["set"])
        elif "delta" in override:
            values[driver_id] = values[driver_id] + float(override["delta"])
        else:
            raise clientpack.ClientPackError(
                f"Preset {preset_id!r} override for {driver_id!r} has neither `set` nor `delta`"
            )
    return values


def get_presets(client: str | None = None) -> dict:
    p = pack(client)
    base = p.base_driver_values()
    out = {}
    for preset_id, spec in p.presets.items():
        values = resolve_preset(preset_id, client)
        out[preset_id] = {
            "label": spec["label"],
            "values": values,
            "changed_drivers": [d for d in p.driver_order if values[d] != base[d]],
        }
    return out


def out_of_guidance(driver_id: str, value: float, client: str | None = None) -> bool:
    return pack(client).out_of_guidance(driver_id, value)


class DriverValueError(ValueError):
    """A driver value outside the range the model is defined over."""


def validate_driver_values(driver_values: dict, client: str | None = None) -> None:
    """Names and ranges, checked against the client pack rather than
    re-declared. The UI cannot produce an out-of-range value — its sliders are
    built from the same spec — so this only ever fires on a hand-made request.
    Worth having anyway: the endpoint is public, and an unbounded growth rate
    produces confident nonsense rather than an error.

    This also catches the cross-client failure that matters most: posting
    adidas's driver names against the manufacturing client is rejected here,
    rather than silently forecasting with missing assumptions.

    Note this bounds `min`/`max`, not the narrower guidance range. Moving
    outside disclosed guidance is a deliberate feature (the UI flags it);
    leaving the model's own domain is not.
    """
    p = pack(client)
    known = set(p.drivers)
    unknown = sorted(set(driver_values) - known)
    if unknown:
        raise DriverValueError(f"Unknown driver(s) for client {p.id!r}: {unknown}")
    missing = sorted(known - set(driver_values))
    if missing:
        raise DriverValueError(f"Missing driver(s) for client {p.id!r}: {missing}")

    for name, spec in p.drivers.items():
        value = driver_values[name]
        if spec.min is not None and value < spec.min:
            raise DriverValueError(f"{name}={value} is below the minimum of {spec.min}")
        if spec.max is not None and value > spec.max:
            raise DriverValueError(f"{name}={value} is above the maximum of {spec.max}")


def compute_scenario(driver_values: dict, client: str | None = None) -> dict:
    p = pack(client)
    base_values = p.base_driver_values()
    base_forecast = run_forecast(base_values, client)
    scenario_forecast = run_forecast(driver_values, client)

    deltas = {
        key: scenario_forecast[key] - base_forecast[key]
        for key in ("revenue", "operating_profit", "free_cash_flow", "operating_working_capital")
    }
    changed = {
        d: {"base": base_values[d], "value": driver_values[d]}
        for d in p.driver_order if driver_values[d] != base_values[d]
    }
    warnings = {
        d: True for d, v in driver_values.items() if out_of_guidance(d, v, client)
    }

    return {
        "base": base_forecast,
        "scenario": scenario_forecast,
        "deltas": deltas,
        "changed_drivers": changed,
        "out_of_guidance": warnings,
        "bridge": compute_bridge(base_values, driver_values, client),
    }


def compute_bridge(base_values: dict, scenario_values: dict, client: str | None = None) -> list[dict]:
    """Sequential FCF waterfall: applies each changed driver one at a time, in
    the pack's declared driver order, and attributes the resulting FCF delta to
    it. This is order-dependent for drivers with interaction effects (the
    standard limitation of sequential bridge analysis) — noted in the UI, not
    hidden."""
    p = pack(client)
    current = dict(base_values)
    prev_fcf = run_forecast(current, client)["free_cash_flow"]
    steps = [{"label": "Base", "value": prev_fcf, "delta": None}]
    for driver_id in p.driver_order:
        if scenario_values[driver_id] == base_values[driver_id]:
            continue
        current[driver_id] = scenario_values[driver_id]
        new_fcf = run_forecast(current, client)["free_cash_flow"]
        steps.append({
            "label": p.drivers[driver_id].label,
            "value": new_fcf,
            "delta": new_fcf - prev_fcf,
        })
        prev_fcf = new_fcf
    if len(steps) > 1:
        steps.append({"label": "Scenario", "value": prev_fcf, "delta": None})
    return steps


def get_assumption_register(client: str | None = None) -> list[dict]:
    p = pack(client)
    priority = {row["driver_id"]: row for row in get_driver_priority(client)}
    return [
        {
            "driver_id": driver_id,
            "label": p.drivers[driver_id].label,
            "category": p.drivers[driver_id].category,
            "current_value": p.drivers[driver_id].default,
            "unit": p.drivers[driver_id].unit,
            "source": p.drivers[driver_id].source,
            "guidance_text": p.drivers[driver_id].guidance_text,
            "confidence": p.drivers[driver_id].confidence,
            "controllability": p.drivers[driver_id].controllability,
            "owner": p.drivers[driver_id].owner,
            "sensitivity": priority[driver_id]["sensitivity"],
            "fiscal_year": p.fiscal_year,
        }
        for driver_id in p.driver_order
    ]


@lru_cache(maxsize=8)
def get_priorities(client: str | None = None) -> dict:
    """The three-axis ranking plus the methodology that produced it.

    The methodology travels with the ranking rather than living on a separate
    page: a reader who wants to challenge the order should not have to go
    looking for the rule that produced it.
    """
    p = pack(client)
    return {"ranked": materiality.rank(p), "methodology": materiality.methodology(p)}


def get_decision_brief(driver_values: dict | None = None, client: str | None = None) -> dict:
    p = pack(client)
    if driver_values is not None:
        validate_driver_values(driver_values, client)
    return decisions.brief(p, driver_values)


@lru_cache(maxsize=32)
def get_variance_bridge(metric: str = "free_cash_flow", client: str | None = None) -> dict | None:
    """Why the forecast missed, decomposed across the drivers.

    None where the client has no outturn to bridge against — the same honesty
    as get_backtest(). A bridge from a forecast to invented actuals would look
    like a finding and be none.
    """
    p = pack(client)
    if not variance.is_available(p):
        return None
    return variance.bridge(p, metric)


def variance_available(client: str | None = None) -> bool:
    return variance.is_available(pack(client))


def get_decision_rules(client: str | None = None) -> list[dict]:
    return [dict(rule) for rule in pack(client).decision_rules]


def get_mappings(client: str | None = None) -> dict:
    return pack(client).mappings


# --------------------------------------------------------------------------
# Commentary — the LLM layer. It never calculates; it reads model output.
# --------------------------------------------------------------------------

def get_commentary_for(scenario_id: str, client: str | None = None) -> dict | None:
    """Preset commentary is committed for adidas only. Other clients fall
    through to the live endpoint or to nothing — better than serving one
    client's narrative under another's name."""
    p = pack(client)
    if p.id != clientpack.DEFAULT_CLIENT:
        return None
    path = C.DATA / "commentary.json"
    if not path.exists():
        return None
    return json.loads(path.read_text()).get(scenario_id)


def generate_live_commentary(driver_values: dict, series_name: str = "scenario",
                             client: str | None = None) -> dict:
    """`series_name` labels the forecast series in the table the LLM writes
    from, and the model calls the series by the name it is given.

    The default is the neutral one on purpose. It used to be `driver_based`,
    which was right for the backtest and wrong for everything else: a caller
    that forgot to pass a name got a custom stress scenario described as "the
    driver-based forecast", contradicting the backtest's own error on the same
    page. Only generate_commentary.py names the base case explicitly, so
    forgetting fails safe.
    """
    p = pack(client)
    bt = get_backtest(client)
    if bt is None:
        raise DriverValueError(
            f"Live commentary needs a backtest to anchor against, and client {p.id!r} has none."
        )
    scenario_forecast = run_forecast(driver_values, client)
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
    # exactly what the published presets once did.
    coherence = claims.verify_claims(text, claims.index_outputs(pseudo_backtest_result))
    return {
        "text": text,
        "grounding": grounding,
        "coherence": coherence,
        "provenance": provenance,
    }
