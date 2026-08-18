"""
Decision rules and the executive brief.

A rule fires when a modelled outcome crosses a level the client has said it
cares about. Firing is not a verdict. It marks an area requiring review and
names the question worth asking — the language throughout is "suggested
management question", "suggested owner", "area requiring review", never a
recommendation presented as fact. Software that tells a CFO what to do is
making a claim it cannot support; software that tells a CFO what to ask is
doing the job.

Rules live in clients/<id>/decision_rules.yaml, so the thresholds that matter
to one business do not silently apply to another.
"""

from __future__ import annotations

from src import clientpack, materiality

SEVERITIES = ("critical", "high", "medium", "low")
_SEVERITY_ORDER = {s: i for i, s in enumerate(SEVERITIES)}

CONDITIONS = ("above", "below", "variance_below_base", "variance_above_base")


def _metric_value(rule: dict, pack, driver_values: dict, forecast: dict, base: dict):
    """A rule's metric is either a driver (an input management sets) or a
    forecast output (a result they get). Both are legitimate places to put a
    threshold, so both resolve here rather than forcing the config to say
    which kind it is."""
    metric = rule["metric"]
    if metric in pack.drivers:
        return driver_values[metric], "driver"
    if metric in forecast:
        return forecast[metric], "output"
    # A margin threshold expressed against the assumption rather than the
    # output — the pack's `ebitda_margin` driver may not exist for every client.
    raise clientpack.ClientPackError(
        f"Decision rule {rule.get('id', '?')!r} names metric {metric!r}, which is neither a "
        f"driver of client {pack.id!r} nor a forecast output."
    )


def evaluate_rule(rule: dict, pack, driver_values: dict, forecast: dict, base: dict) -> dict:
    condition = rule["condition"]
    if condition not in CONDITIONS:
        raise clientpack.ClientPackError(
            f"Decision rule {rule.get('id', '?')!r} uses unknown condition {condition!r} "
            f"(have: {list(CONDITIONS)})"
        )
    value, kind = _metric_value(rule, pack, driver_values, forecast, base)
    threshold = float(rule["threshold"])

    if condition == "above":
        breached, observed = value > threshold, value
    elif condition == "below":
        breached, observed = value < threshold, value
    else:
        metric = rule["metric"]
        variance = forecast[metric] - base[metric] if metric in forecast else 0.0
        observed = variance
        breached = variance < threshold if condition == "variance_below_base" else variance > threshold

    return {
        "id": rule.get("id"),
        "label": rule.get("label", rule["metric"]),
        "metric": rule["metric"],
        "metric_kind": kind,
        "condition": condition,
        "threshold": threshold,
        "observed": observed,
        "breached": breached,
        "severity": rule.get("severity", "medium"),
        "management_question": rule.get("management_question", ""),
        "suggested_owner": rule.get("suggested_owner", "Unassigned"),
        "next_action": rule.get("next_action", ""),
        "trigger": rule.get("trigger", ""),
    }


def evaluate(pack, driver_values: dict, forecast: dict, base: dict) -> list[dict]:
    """Every rule, evaluated. Un-breached rules are returned too: showing that
    a threshold was checked and held is information, and a screen that only
    ever renders problems teaches the reader nothing about what was tested."""
    results = [evaluate_rule(r, pack, driver_values, forecast, base) for r in pack.decision_rules]
    results.sort(key=lambda r: (not r["breached"], _SEVERITY_ORDER.get(r["severity"], 9)))
    return results


def threshold_status(rules: list[dict], driver_id: str, breached_only: bool = True) -> dict | None:
    """The most severe rule bearing on one driver.

    `breached_only=False` is used for the brief's owner and review trigger: a
    threshold that exists and has NOT fired still tells you who watches this
    exposure and when they next look at it. Suppressing that until something
    goes wrong would leave the brief's "next" line empty exactly when the plan
    is on track, which is most of the time.
    """
    relevant = [r for r in rules if r["metric"] == driver_id and (r["breached"] or not breached_only)]
    if not relevant:
        return None
    return min(relevant, key=lambda r: _SEVERITY_ORDER.get(r["severity"], 9))


def brief(pack, driver_values: dict | None = None) -> dict:
    """The executive decision brief.

    Answers, in one structure: what matters, how much is at risk, why, whether
    it is outside tolerance, whether management can influence it, what to
    discuss, who should own it, and what happens next.

    The lead exposure is the top-ranked driver from the materiality engine,
    not the largest euro number. Those differ, and the difference is the
    product's argument: the biggest exposure is not automatically the best use
    of management time.
    """
    values = driver_values if driver_values is not None else pack.base_driver_values()
    base_values = pack.base_driver_values()

    segments_raw = clientpack.read_fact(pack.facts, pack.segments_path)
    from src import model  # local import keeps the engine's import graph flat
    forecast = model.forecast(pack.baseline_group, segments_raw, pack.to_assumptions(values))
    base = model.forecast(pack.baseline_group, segments_raw, pack.to_assumptions(base_values))

    ranked = materiality.rank(pack)
    rules = evaluate(pack, values, forecast, base)
    lead = ranked[0]
    breached = [r for r in rules if r["breached"]]
    lead_rule = threshold_status(rules, lead["driver_id"])
    # Falls back to an un-breached rule on the same driver, so the brief can
    # still name a watcher and a review point when nothing has gone wrong.
    lead_watch = lead_rule or threshold_status(rules, lead["driver_id"], breached_only=False)

    metric = materiality.objective_metric(pack)
    return {
        "client": pack.summary(),
        "objective": pack.objective,
        "objective_metric": metric,
        "objective_value": forecast[metric],
        "objective_variance": forecast[metric] - base[metric],
        "is_base_case": values == base_values,

        "lead": {
            **lead,
            "threshold": lead_rule,
            # Language discipline: a question to put to management, not an
            # instruction issued to them.
            "management_question": (
                lead_rule["management_question"] if lead_rule
                else _default_question(pack, lead)
            ),
            "suggested_owner": lead_watch["suggested_owner"] if lead_watch else lead["owner"],
            "next_action": lead_rule["next_action"] if lead_rule else "",
            "trigger": lead_watch["trigger"] if lead_watch else "",
            "watching_rule": lead_watch["label"] if lead_watch and not lead_rule else None,
        },
        "ranked": ranked,
        "rules": rules,
        "breached_count": len(breached),
        "attention": _attention(breached, ranked),
        "methodology": materiality.methodology(pack),
    }


def _default_question(pack, lead: dict) -> str:
    """Used when no configured rule bears on the lead exposure. Phrased as a
    question about the assumption, because that is all the model knows —
    inventing a specific operational question would be putting words in the
    business's mouth."""
    # The euro figure is already on the line above in the brief, so it is not
    # repeated here — the question should be the question, not a restatement.
    return (
        f"Is the plan assumption for {lead['label'].lower()} still the right one, "
        f"and what would have to change for it to move?"
    )


def _attention(breached: list[dict], ranked: list[dict]) -> dict:
    """The one-line management state that opens the Outlook page."""
    critical = [r for r in ranked if r["priority"] == "Critical"]
    act = [r for r in ranked if r["priority"] == "Act"]

    if breached:
        worst = breached[0]
        state = "critical" if worst["severity"] == "critical" else "attention"
        headline = f"{len(breached)} threshold{'s' if len(breached) > 1 else ''} breached — {worst['label'].lower()}"
    elif critical:
        state, headline = "critical", f"{len(critical)} exposure(s) both material and unresolved"
    elif act:
        state = "attention"
        headline = (
            f"No threshold breached. {len(act)} exposure{'s' if len(act) > 1 else ''} "
            f"ranked for action."
        )
    else:
        state, headline = "steady", "No threshold breached, and no exposure ranked above Review."

    return {
        "state": state,
        "headline": headline,
        "breached": breached,
        "critical_count": len(critical),
        "act_count": len(act),
    }
