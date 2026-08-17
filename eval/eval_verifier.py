"""Adversarial evaluation of the grounding verifier itself.

`verify_grounding()` is the guardrail: it decides whether a number in
LLM-written commentary is backed by the calculated output table. Every
grounding rate this project reports is only as meaningful as that decision.

A "100% grounding rate" measures the model, not the guardrail. This module
measures the guardrail, by feeding it commentary whose numbers are known to
be wrong and counting how many it lets through. No API calls — the
commentary is synthesised, so this runs in CI on every push.

Run: python -m eval.eval_verifier
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from api import service
from src.commentary import _flatten_outputs, verify_grounding

TOLERANCE = 0.05  # the verifier's own relative tolerance


@dataclass
class Case:
    name: str
    description: str
    caught: int
    total: int

    @property
    def catch_rate(self) -> float:
        return self.caught / self.total if self.total else 0.0


def _table() -> dict:
    """The real output table a commentary would be written from."""
    return _flatten_outputs(service.get_backtest())


def _is_caught(claim: float, outputs: dict) -> bool:
    """True when the verifier rejects a number — i.e. the guardrail works."""
    result = verify_grounding(f"The figure was {claim:,.1f}.", outputs)
    return result["grounding_rate"] == 0.0


def near_miss_fabrication(outputs: dict, offsets=(0.01, 0.02, 0.03, 0.04)) -> Case:
    """A number close to a real one, but not it.

    This is the realistic hallucination: models do not invent wild figures,
    they drift. Anything inside the verifier's relative tolerance is
    indistinguishable from the truth to it.
    """
    caught = total = 0
    for value in outputs.values():
        if abs(value) < 1:
            continue
        for offset in offsets:
            total += 1
            caught += _is_caught(value * (1 + offset), outputs)
    return Case(
        "near-miss fabrication",
        f"a real value perturbed by {int(offsets[0]*100)}-{int(offsets[-1]*100)}%",
        caught, total,
    )


def cross_metric_attribution(outputs: dict) -> Case:
    """A real number from the table, attributed to the wrong metric.

    The verifier compares values against the whole table, never against the
    label a claim attaches them to. Free cash flow quoted as operating
    profit is arithmetically 'grounded' and semantically false — a blind
    spot no tolerance setting can close.
    """
    items = [(k, v) for k, v in outputs.items() if abs(v) >= 1]
    caught = total = 0
    for (label, _), (_, other_value) in zip(items, items[1:]):
        total += 1
        text = f"{label.replace('_', ' ')} was {other_value:,.1f}."
        caught += verify_grounding(text, outputs)["grounding_rate"] == 0.0
    return Case(
        "cross-metric attribution",
        "a real value reported under the wrong metric's name",
        caught, total,
    )


def magnitude_error(outputs: dict) -> Case:
    """Off by a factor of ten — millions quoted as billions."""
    caught = total = 0
    for value in outputs.values():
        if abs(value) < 1:
            continue
        for factor in (10, 0.1):
            total += 1
            caught += _is_caught(value * factor, outputs)
    return Case("order-of-magnitude error", "a real value times 10 or divided by 10", caught, total)


def free_invention(outputs: dict, n: int = 2000, seed: int = 0) -> Case:
    """Numbers drawn at random across the plausible reporting range.

    The complement of this catch rate is the share of the number line the
    table's tolerance bands happen to cover — the verifier's blind area for
    a figure that has nothing to do with the model.
    """
    rng = random.Random(seed)
    values = [abs(v) for v in outputs.values() if abs(v) >= 1]
    high = max(values) * 1.2
    caught = 0
    for _ in range(n):
        caught += _is_caught(rng.uniform(1, high), outputs)
    return Case("free invention", f"uniform random in [1, {high:,.0f}]", caught, n)


def truthful_control(outputs: dict) -> Case:
    """Real values, correctly quoted. A guardrail that rejects these is
    useless in the other direction, so this is the false-positive check."""
    caught = total = 0
    for value in outputs.values():
        if abs(value) < 1:
            continue
        total += 1
        # 'caught' here means wrongly rejected
        caught += _is_caught(value, outputs)
    return Case("truthful control", "real values, correctly quoted", caught, total)


def run() -> dict[str, Case]:
    outputs = _table()
    return {
        c.name: c
        for c in (
            free_invention(outputs),
            magnitude_error(outputs),
            near_miss_fabrication(outputs),
            cross_metric_attribution(outputs),
            truthful_control(outputs),
        )
    }


def main() -> None:
    outputs = _table()
    cases = run()
    print(f"Verifier adversarial eval — {len(outputs)} values in the output table, "
          f"tolerance ±{TOLERANCE:.0%}\n")
    print(f"{'attack':<26}{'caught':>10}{'rate':>9}   {'what it is'}")
    print("-" * 96)
    for name, case in cases.items():
        if name == "truthful control":
            continue
        print(f"{name:<26}{case.caught:>4}/{case.total:<5}{case.catch_rate:>8.0%}   {case.description}")
    control = cases["truthful control"]
    print(f"\n{'truthful control':<26}{control.total - control.caught:>4}/{control.total:<5}"
          f"{1 - control.catch_rate:>8.0%}   accepted (false positives would show here)")
    print(
        "\nRead this as the guardrail's operating envelope, not a score. It is\n"
        "strong against invention it has no anchor for, and blind wherever a\n"
        "wrong number sits close to a right one — or is a right one under the\n"
        "wrong name."
    )


if __name__ == "__main__":
    main()
