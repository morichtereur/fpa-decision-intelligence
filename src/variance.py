"""
Stage 4b: why the forecast missed, not just by how much.

`src/backtest.py` establishes that the driver-based FY2025 forecast landed
€37.2m below actual free cash flow and €306m below actual operating profit.
That is the question a controller asks first and stops caring about
immediately. The second question — *which assumption was wrong* — is the one
that changes what anyone does next, and it is the one FP&A is actually paid to
answer.

This module walks the forecast's drivers to their realised values one at a
time, in a fixed order, and attributes the resulting movement in the chosen
metric to the driver that was changed. Which drivers, in what order, and how
each realised value is read out of the facts all come from the client pack —
so a client with ten drivers bridges ten, and a client with no actuals gets no
bridge at all rather than a fabricated one. The same sequential-bridge
mechanic the Scenario Planner already uses between base and scenario, pointed
at forecast versus actual instead.

Two properties make it honest rather than decorative:

**It is order-dependent, and says so.** Drivers interact — margin applied to a
different revenue base gives a different euro impact — so a sequential bridge
assigns interaction effects to whichever driver moves later. That is a
standard limitation of the method, not a defect of this implementation, and
the fixed order is stated rather than tuned to make a particular driver look
decisive.

**It carries a residual line.** Substituting every realised driver does not
reproduce actual exactly: the model scales D&A with revenue, product-division
revenue sums to €23,690m against a reported group figure of €23,683m, and FCF
here is a derived construction. Whatever is left over after all five drivers is
reported as residual rather than silently absorbed into the last step. A bridge
that always closes to zero is hiding something.
"""

from __future__ import annotations

from dataclasses import dataclass

from src import backtest, clientpack, model

METRICS: tuple[str, ...] = ("free_cash_flow", "operating_profit", "revenue")


class VarianceUnavailable(RuntimeError):
    """No actuals exist to bridge against.

    A synthetic client has no outturn, so there is nothing to explain. Raising
    is the honest answer: a bridge from a forecast to invented actuals would
    look like a finding and be none.
    """


# --------------------------------------------------------------------------
# Reading realised driver values out of the facts
# --------------------------------------------------------------------------
#
# Reported figures are used in preference to model-implied ones. Back-solving
# a driver so the bridge closes exactly would bury the model's own error inside
# a number labelled "actual", which is the one thing a variance bridge must
# never do.

def _growth_rate(facts: dict, args: list) -> float:
    start, end = (clientpack.read_fact(facts, a) for a in args)
    return (end / start - 1) * 100


def _ratio(facts: dict, args: list) -> float:
    numerator, denominator = (clientpack.read_fact(facts, a) for a in args)
    return numerator / denominator * 100


def _fact(facts: dict, args: list) -> float:
    path = args[0] if isinstance(args, list) else args
    return float(clientpack.read_fact(facts, path))


REALISED_READERS = {"growth_rate": _growth_rate, "ratio": _ratio, "fact": _fact}


def variance_order(pack: clientpack.ClientPack) -> tuple[str, ...]:
    """The substitution order.

    Revenue first, because every other driver is applied to a revenue base, so
    walking it first means the remaining steps are measured against the revenue
    that actually happened. Within the rest, income-statement drivers precede
    cash drivers, which is the order a P&L-to-cash-flow bridge is read in.
    Declared per client, because that ordering argument depends on the client's
    own driver set.
    """
    return pack.variance_order or pack.driver_order


def is_available(pack: clientpack.ClientPack) -> bool:
    if not pack.has_backtest:
        return False
    return all(pack.drivers[d].realised is not None for d in variance_order(pack))


def _substitute(args, spec: dict) -> list:
    """Fill {year} / {baseline} in a realised fact path from the vintage.

    One declaration in the pack then serves every backtest point, instead of
    a set of paths hardcoded to whichever year happened to be latest.
    """
    return [
        a.format(year=spec["actual"], baseline=spec["baseline"]) if isinstance(a, str) else a
        for a in (args if isinstance(args, list) else [args])
    ]


def realised_drivers(pack: clientpack.ClientPack, vintage: str | None = None) -> dict[str, float]:
    """The outturn, expressed in the same drivers the forecast used.

    This is what makes the comparison meaningful: the forecast and the outcome
    are described in one vocabulary, so "the margin assumption was wrong by 2.1
    points" is a statement about the same quantity in both.
    """
    vspec = backtest.VINTAGES[vintage or backtest.DEFAULT_VINTAGE]
    values: dict[str, float] = {}
    for driver_id in variance_order(pack):
        spec = pack.drivers[driver_id].realised
        if spec is None:
            raise VarianceUnavailable(
                f"Driver {driver_id!r} in client {pack.id!r} declares no realised value, "
                f"so the forecast-to-actual bridge cannot be built."
            )
        reader = REALISED_READERS.get(spec["from"])
        if reader is None:
            raise clientpack.ClientPackError(
                f"Driver {driver_id!r} names realised reader {spec['from']!r} "
                f"(have: {sorted(REALISED_READERS)})"
            )
        values[driver_id] = reader(pack.facts, _substitute(spec["args"], vspec))
    return values


@dataclass(frozen=True)
class BridgeStep:
    """One driver moved from its forecast value to what actually happened."""

    driver_id: str
    label: str
    unit: str
    forecast_value: float
    actual_value: float
    metric_before: float
    metric_after: float

    @property
    def impact(self) -> float:
        return self.metric_after - self.metric_before


def forecast_drivers(pack: clientpack.ClientPack, vintage: str | None = None) -> dict[str, float]:
    """What the vintage's plan assumed, taken from backtest.driver_values() so
    the bridge walks the same numbers the forecast was built from. A second
    copy of "what did the plan assume" would drift.

    For the default vintage this is identical to the pack's base case by
    construction — the invariant tests/test_drivers.py asserts.
    """
    values = backtest.driver_values(pack.facts, vintage or backtest.DEFAULT_VINTAGE)
    return {driver_id: values[driver_id] for driver_id in variance_order(pack)}


def _vintage_context(pack: clientpack.ClientPack, vintage: str) -> tuple[dict, dict]:
    """The baseline group and segments the vintage forecasts FROM.

    Taken from the vintage spec rather than the pack, because the pack's
    baseline is whichever year its current plan starts from. A bridge for an
    earlier vintage has to start from that vintage's own baseline year or it
    would be explaining a forecast nobody made.
    """
    spec = backtest.VINTAGES[vintage]
    return pack.facts["group"][spec["baseline"]], pack.facts["product_division"][spec["baseline"]]


def _metric(pack: clientpack.ClientPack, driver_values: dict[str, float],
            metric: str, vintage: str) -> float:
    group, segments = _vintage_context(pack, vintage)
    segment_names = [k for k in segments if k != "source"]
    assumptions = {
        "division_growth": {k: driver_values["revenue_growth"] / 100 for k in segment_names},
        "ebitda_margin_pct": driver_values["ebitda_margin"],
        "effective_tax_rate_pct": driver_values["tax_rate_pct"],
        "operating_working_capital_pct": driver_values["working_capital_pct"],
        "capex_eur_m": driver_values["capex_eur_m"],
    }
    return float(model.forecast(group, segments, assumptions)[metric])


def _actual_metric(pack: clientpack.ClientPack, metric: str, vintage: str) -> float:
    """Actual outturn, derived exactly as src/backtest.py derives it."""
    return float(backtest.run(vintage)["actual"][metric])


def bridge(pack: clientpack.ClientPack, metric: str = "free_cash_flow",
           vintage: str | None = None) -> dict:
    """Decompose the forecast-to-actual gap in ``metric`` across the drivers.

    Returns the steps, what they explain, and what they do not.
    """
    if metric not in METRICS:
        raise ValueError(f"Unknown metric {metric!r}. Available: {list(METRICS)}")
    if not is_available(pack):
        raise VarianceUnavailable(f"Client {pack.id!r} has no actuals to bridge against.")

    vintage = vintage or backtest.DEFAULT_VINTAGE
    if vintage not in backtest.VINTAGES:
        raise ValueError(f"Unknown vintage {vintage!r}. Available: {sorted(backtest.VINTAGES)}")
    vspec = backtest.VINTAGES[vintage]

    order = variance_order(pack)
    forecast_values = forecast_drivers(pack, vintage)
    actual_values = realised_drivers(pack, vintage)

    current = dict(forecast_values)
    running = _metric(pack, current, metric, vintage)
    forecast_metric = running

    steps: list[BridgeStep] = []
    for driver_id in order:
        before = running
        current[driver_id] = actual_values[driver_id]
        running = _metric(pack, current, metric, vintage)
        spec = pack.drivers[driver_id]
        steps.append(
            BridgeStep(
                driver_id=driver_id,
                label=spec.label,
                unit=spec.unit,
                forecast_value=forecast_values[driver_id],
                actual_value=actual_values[driver_id],
                metric_before=before,
                metric_after=running,
            )
        )

    actual_metric = _actual_metric(pack, metric, vintage)
    explained = running - forecast_metric
    total = actual_metric - forecast_metric
    gross = sum(abs(s.impact) for s in steps)

    return {
        "client": pack.id,
        "vintage": vintage,
        "vintage_label": vspec["label"],
        "metric": metric,
        "forecast": round(forecast_metric, 1),
        "actual": round(actual_metric, 1),
        "total_variance": round(total, 1),
        "explained_by_drivers": round(explained, 1),
        "residual": round(total - explained, 1),
        "gross_driver_movement": round(gross, 1),
        "offsetting_note": _offsetting_note(gross, total, pack.currency_symbol),
        "residual_note": (
            "Not attributable to a driver: the model scales D&A with revenue, "
            "product-division revenue does not sum exactly to reported group net "
            "sales, and free cash flow is a derived construction rather than a "
            "disclosed line item."
        ),
        "order_note": (
            "Sequential bridge: drivers are substituted in a fixed order, so "
            "interaction effects are attributed to whichever driver moves later."
        ),
        "waterfall": _waterfall(forecast_metric, steps, actual_metric),
        "steps": [
            {
                "driver_id": s.driver_id,
                "label": s.label,
                "unit": s.unit,
                "forecast_value": round(s.forecast_value, 2),
                "actual_value": round(s.actual_value, 2),
                "impact": round(s.impact, 1),
                "share_of_variance_pct": (
                    round(s.impact / total * 100, 1) if abs(total) > 1e-9 else None
                ),
                "source": (pack.drivers[s.driver_id].realised or {}).get("source", "Not stated"),
            }
            for s in steps
        ],
    }


def _waterfall(forecast_metric: float, steps: list[BridgeStep], actual_metric: float) -> list[dict]:
    """The same {label, value, delta} shape the Scenario Planner's bridge uses.

    Emitted by the model rather than reshaped in the frontend, so both bridges
    are one chart component fed by one contract — and so the residual is a bar
    on the chart rather than a footnote the eye skips.
    """
    rows = [{"label": "Forecast", "value": round(forecast_metric, 1), "delta": None}]
    for step in steps:
        rows.append({
            "label": step.label,
            "value": round(step.metric_after, 1),
            "delta": round(step.impact, 1),
        })
    residual = actual_metric - (steps[-1].metric_after if steps else forecast_metric)
    rows.append({"label": "Residual", "value": round(actual_metric, 1), "delta": round(residual, 1)})
    rows.append({"label": "Actual", "value": round(actual_metric, 1), "delta": None})
    return rows


def _offsetting_note(gross: float, total: float, symbol: str) -> str | None:
    """Flag a small net variance built from large, opposing driver errors.

    Without this the share-of-variance percentages read as a defect: a driver
    worth -372 against a net variance of +37 is -1001% of it. The percentages
    are right and the situation is the point — a forecast can land close to
    actual while every assumption behind it was wrong, and that is a materially
    different finding from a forecast that was simply accurate.
    """
    if abs(total) < 1e-9 or gross <= abs(total) * 3:
        return None
    return (
        f"Driver errors largely offset: {symbol}{gross:,.0f}m of gross movement nets to "
        f"{symbol}{total:+,.0f}m. The forecast landed close on this metric despite every "
        f"assumption behind it being wrong, so the small variance is not evidence "
        f"the assumptions were sound."
    )


def largest_driver(bridge_result: dict) -> dict | None:
    """The single assumption that moved the metric most, in absolute terms.

    The headline a reviewer wants: not the size of the miss, but its cause.
    """
    steps = bridge_result["steps"]
    return max(steps, key=lambda s: abs(s["impact"])) if steps else None


def commentary_table(bridge_result: dict) -> dict:
    """The bridge as a {series: {metric: value}} table a model can write from.

    Each driver becomes its own series carrying what was assumed, what
    happened, and what the difference was worth. That shape is what lets the
    coherence checks work on the result: a claim about a driver's cash impact
    is bound to that driver, not floating in a flat list of numbers.
    """
    metric = bridge_result["metric"]
    table: dict[str, dict[str, float]] = {
        "forecast": {metric: bridge_result["forecast"]},
        "actual": {metric: bridge_result["actual"]},
        "variance": {
            f"{metric}_net": bridge_result["total_variance"],
            f"{metric}_gross_driver_error": bridge_result["gross_driver_movement"],
            f"{metric}_residual": bridge_result["residual"],
        },
    }
    for step in bridge_result["steps"]:
        table[step["driver_id"]] = {
            "assumed": step["forecast_value"],
            "realised": step["actual_value"],
            f"{metric}_impact": step["impact"],
        }
    return table
