"""
Planning-model readiness.

The client pack asks a specific set of questions: what is the plausible range
for this driver, who owns it, can management actually move it inside the year,
what level would make it worth a conversation. Most finance functions cannot
answer several of them — and that inability is a finding in its own right,
available before anyone has validated a single number.

So this module reads the pack and reports what is *missing* rather than what
the model computes. It is the one output here that is useful on day one of an
engagement, when the data is bad and the interviews have only just started.

Two deliberate constraints:

**It counts, it does not score.** There is no composite index, because a
single number invites comparison between businesses whose situations are not
comparable, and because "6 of 10 drivers have no named owner" is a sentence
someone can act on in a way that "readiness 62%" is not.

**A gap is never inferred to be a failing.** A driver with no owner may be one
nobody needs to own. The readout says what is absent and why the field exists;
it does not grade the finance function.
"""

from __future__ import annotations

from src import clientpack

#: Each check is a question the pack can answer about itself, and the reason
#: the answer matters to a decision. The `why` lines are written for the
#: reader of a diagnostic, not the maintainer of a schema.
CHECKS = [
    {
        "id": "owner",
        "question": "Do the drivers have a named owner?",
        "why": "An exposure with no owner cannot be actioned, only discussed. "
               "This is the most common gap and the cheapest to close.",
    },
    {
        "id": "controllability",
        "question": "Is it stated whether management can move each driver?",
        "why": "Without it, prioritisation defaults to size, and attention goes "
               "to the largest exposure rather than the largest movable one.",
    },
    {
        "id": "confidence",
        "question": "Is the firmness of each assumption stated?",
        "why": "A plan built on a guided figure and one built on a carried-forward "
               "placeholder deserve different levels of trust, and usually get the same.",
    },
    {
        "id": "exposure_range",
        "question": "Is a plausible range declared for each driver?",
        "why": "Without a range there is no exposure to quantify — only a point "
               "estimate, which is what makes a plan look more certain than it is.",
    },
    {
        "id": "source",
        "question": "Is the origin of each assumption recorded?",
        "why": "Traceability is what separates a forecast from an opinion when "
               "someone asks where a number came from six months later.",
    },
    {
        "id": "guidance_text",
        "question": "Is each assumption explained in a sentence?",
        "why": "A slider with no context invites a change nobody can defend.",
    },
]

#: Checks about the model as a whole rather than driver by driver.
MODEL_CHECKS = [
    {
        "id": "thresholds",
        "question": "Are management tolerances defined?",
        "why": "Without a threshold, nothing is ever 'outside plan' — every "
               "variance is a matter of opinion at the meeting.",
    },
    {
        "id": "threshold_questions",
        "question": "Does each tolerance carry a question and an owner?",
        "why": "A breach that names no question produces an alert. One that names "
               "a question produces a conversation.",
    },
    {
        "id": "materiality_rationale",
        "question": "Is the materiality threshold justified?",
        "why": "A number nobody can defend will not survive its first challenge.",
    },
    {
        "id": "scenarios",
        "question": "Are there scenarios beyond the plan?",
        "why": "A single case cannot show what a decision would change.",
    },
    {
        "id": "outturn",
        "question": "Can the forecast be tested against what happened?",
        "why": "Without an outturn there is no forecast quality, only forecast "
               "confidence — and the two are unrelated.",
    },
]


def _driver_answered(spec: clientpack.DriverSpec, check_id: str) -> bool:
    if check_id == "owner":
        return bool(spec.owner) and spec.owner != "Unassigned"
    if check_id == "controllability":
        return spec.controllability in clientpack.CONTROLLABILITY_LEVELS
    if check_id == "confidence":
        return spec.confidence in clientpack.CONFIDENCE_LEVELS
    if check_id == "exposure_range":
        return spec.exposure_range is not None or (
            spec.guidance_low is not None and spec.guidance_high is not None
        )
    if check_id == "source":
        return bool(spec.source) and spec.source not in ("Not stated", "Intake workbook")
    if check_id == "guidance_text":
        return bool((spec.guidance_text or "").strip())
    raise ValueError(f"Unknown driver check {check_id!r}")


def _model_answered(pack: clientpack.ClientPack, check_id: str) -> tuple[bool, str]:
    if check_id == "thresholds":
        n = len(pack.decision_rules)
        return n > 0, f"{n} tolerance{'' if n == 1 else 's'} defined"
    if check_id == "threshold_questions":
        rules = pack.decision_rules
        complete = [r for r in rules
                    if str(r.get("management_question", "")).strip()
                    and str(r.get("suggested_owner", "")).strip()]
        if not rules:
            return False, "no tolerances to carry a question"
        return len(complete) == len(rules), f"{len(complete)} of {len(rules)} carry both"
    if check_id == "materiality_rationale":
        stated = bool(str(pack.materiality_thresholds.get("rationale", "")).strip())
        return stated, "stated" if stated else "not stated"
    if check_id == "scenarios":
        others = [p for p in pack.presets if p != "base"]
        return len(others) > 0, f"{len(others)} beyond the plan case"
    if check_id == "outturn":
        return pack.has_backtest, "outturn available" if pack.has_backtest else "no outturn recorded"
    raise ValueError(f"Unknown model check {check_id!r}")


def assess(pack: clientpack.ClientPack) -> dict:
    """What the planning model can and cannot answer about itself."""
    total_drivers = len(pack.drivers)
    driver_results = []
    for check in CHECKS:
        missing = [
            {"driver_id": did, "label": pack.drivers[did].label}
            for did in pack.driver_order
            if not _driver_answered(pack.drivers[did], check["id"])
        ]
        driver_results.append({
            **check,
            "scope": "driver",
            "answered": total_drivers - len(missing),
            "total": total_drivers,
            "complete": not missing,
            "missing": missing,
            "detail": f"{total_drivers - len(missing)} of {total_drivers} drivers",
        })

    model_results = []
    for check in MODEL_CHECKS:
        ok, detail = _model_answered(pack, check["id"])
        model_results.append({
            **check, "scope": "model", "complete": ok, "missing": [], "detail": detail,
        })

    checks = driver_results + model_results
    open_gaps = [c for c in checks if not c["complete"]]
    return {
        "client": pack.id,
        "driver_count": total_drivers,
        "checks": checks,
        "answered": len(checks) - len(open_gaps),
        "total": len(checks),
        "gaps": [
            {"id": c["id"], "question": c["question"], "detail": c["detail"], "why": c["why"]}
            for c in open_gaps
        ],
        "summary": _summary(pack, open_gaps, len(checks)),
        "note": (
            "This reads the planning model's own completeness, not the quality of "
            "the finance function. A driver with no named owner may be one nobody "
            "needs to own — the readout says what is absent and why the field "
            "exists, and stops there."
        ),
    }


def _summary(pack: clientpack.ClientPack, gaps: list, total: int) -> str:
    if not gaps:
        return (
            f"{pack.short_label}'s planning model answers all {total} questions this "
            f"diagnostic asks: every driver carries an owner, a plausible range and a "
            f"stated firmness, and every tolerance carries a question and an owner."
        )
    named = ", ".join(g["question"].rstrip("?").lower() for g in gaps[:3])
    more = f", and {len(gaps) - 3} more" if len(gaps) > 3 else ""
    return (
        f"{pack.short_label}'s planning model answers {total - len(gaps)} of {total} "
        f"questions. Open: {named}{more}."
    )
