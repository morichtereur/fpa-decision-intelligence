"""
Stage 3: scenario ranges and Monte Carlo.

The ranges come from the active client's pack (clients/<id>/scenarios.yaml),
not from this module. For adidas they are the company's own disclosed FY2025
guidance bands — real disclosed uncertainty rather than invented statistical
uncertainty. With only three fiscal years, estimating each driver's
volatility from history would mean computing a "standard deviation" from two
year-over-year observations: a number that looks precise and carries almost
no statistical information.

The point of the simulation is which assumption explains the most output
variance in free cash flow — reported as each input's correlation with the
FCF outcome across the run — not the simulation for its own sake.

`margin_mode: solve_operating_profit` samples the guided operating-profit
range and solves for the EBITDA margin at each draw, so the sampled margin
stays consistent with the sampled growth rate. Sampling the two
independently would imply D&A figures the model never produced.
"""

from __future__ import annotations

import json

import numpy as np

from src import clientpack, model

# Sampling order is fixed here rather than taken from the YAML's dict order.
# Every draw comes from one seeded generator, so the order the variables are
# drawn in determines the numbers each one receives — reordering a pack's
# sampling block would otherwise silently change every result it produces.
SAMPLE_ORDER = (
    "growth",
    "operating_profit_target",
    "ebitda_margin_pct",
    "working_capital_pct",
    "capex",
)


def _draw(rng, spec: dict, facts: dict, n: int) -> np.ndarray:
    dist = spec["distribution"]

    def bound(key: str) -> float:
        return clientpack.resolve_scalar(facts, spec[key])

    if dist == "triangular":
        return rng.triangular(bound("low"), bound("mode"), bound("high"), n)
    if dist == "uniform":
        return rng.uniform(bound("low"), bound("high"), n)
    if dist == "normal":
        return rng.normal(bound("mean"), bound("sd"), n)
    raise clientpack.ClientPackError(f"Unknown distribution {dist!r}")


def _margin_for_operating_profit(target_operating_profit, revenue, baseline_da, baseline_revenue):
    return (target_operating_profit / revenue + baseline_da / baseline_revenue) * 100


def build_assumption_ranges(pack: clientpack.ClientPack) -> dict:
    """The resolved numeric bounds a pack's Monte Carlo samples between.

    Exposed separately from the run so the ranges can be shown in the UI, and
    asserted in tests, without executing ten thousand forecasts.
    """
    facts = pack.facts
    ranges = {}
    for name, spec in (pack.monte_carlo.get("sampling") or {}).items():
        resolved = {k: clientpack.resolve_scalar(facts, v) for k, v in spec.items() if k != "distribution"}
        resolved["distribution"] = spec["distribution"]
        ranges[name] = resolved
    group = pack.baseline_group
    ranges["_baseline_revenue"] = sum(pack.segments.values())
    ranges["_baseline_da"] = group["ebitda"] - group["operating_profit"]
    return ranges


def run_monte_carlo(pack: clientpack.ClientPack, n: int | None = None, seed: int | None = None) -> dict:
    mc = pack.monte_carlo
    if not mc:
        raise clientpack.ClientPackError(f"Client {pack.id!r} declares no monte_carlo block")

    facts = pack.facts
    sampling = mc.get("sampling") or {}
    unknown = set(sampling) - set(SAMPLE_ORDER)
    if unknown:
        raise clientpack.ClientPackError(
            f"monte_carlo.sampling names variable(s) the engine does not sample: {sorted(unknown)}"
        )

    n = int(mc.get("n", 10_000)) if n is None else n
    seed = int(mc.get("seed", 0)) if seed is None else seed
    rng = np.random.default_rng(seed)

    draws: dict[str, np.ndarray] = {
        name: _draw(rng, sampling[name], facts, n) for name in SAMPLE_ORDER if name in sampling
    }

    segments = pack.segments
    segments_raw = clientpack.read_fact(facts, pack.segments_path)
    group = pack.baseline_group
    baseline_revenue = sum(segments.values())
    baseline_da = group["ebitda"] - group["operating_profit"]
    fixed = {k: clientpack.resolve_scalar(facts, v) for k, v in (mc.get("fixed") or {}).items()}
    margin_mode = mc.get("margin_mode", "direct")

    fcfs = np.empty(n)
    for i in range(n):
        growth = float(draws["growth"][i])
        revenue = baseline_revenue * (1 + growth)
        if margin_mode == "solve_operating_profit":
            margin = _margin_for_operating_profit(
                float(draws["operating_profit_target"][i]), revenue, baseline_da, baseline_revenue
            )
        else:
            margin = float(draws["ebitda_margin_pct"][i])

        assumptions = {
            "division_growth": {k: growth for k in segments},
            "ebitda_margin_pct": margin,
            "effective_tax_rate_pct": fixed["tax_rate_pct"],
            "operating_working_capital_pct": float(draws["working_capital_pct"][i]),
            "capex_eur_m": float(draws["capex"][i]),
        }
        fcfs[i] = model.forecast(group, segments_raw, assumptions)["free_cash_flow"]

    def corr(x):
        return float(np.corrcoef(x, fcfs)[0, 1])

    sensitivity = {name: corr(values) for name, values in draws.items()}

    return {
        "n": n,
        "fcf_p10": float(np.percentile(fcfs, 10)),
        "fcf_p50": float(np.percentile(fcfs, 50)),
        "fcf_p90": float(np.percentile(fcfs, 90)),
        "fcf_mean": float(np.mean(fcfs)),
        "fcf_std": float(np.std(fcfs)),
        "sensitivity_to_fcf": dict(sorted(sensitivity.items(), key=lambda kv: -abs(kv[1]))),
        "caveat": mc.get("caveat", ""),
        "fcf_draws": fcfs,  # raw array, for charting — stripped before any JSON dump
    }


if __name__ == "__main__":
    import sys

    client_id = sys.argv[1] if len(sys.argv) > 1 else clientpack.DEFAULT_CLIENT
    result = run_monte_carlo(clientpack.get_pack(client_id))
    print(json.dumps({k: v for k, v in result.items() if k != "fcf_draws"}, indent=2))
