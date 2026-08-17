"""The guardrail's operating envelope, asserted so it cannot drift unnoticed.

These tests do not claim the verifier is correct. They pin down where it
works and where it is blind, so that the README's published limits and the
code stay in agreement. A test that fails here means the envelope moved —
either the guardrail improved, in which case the README understates it, or
it degraded.

No API calls: the commentary is synthesised, so this runs in CI.
"""

from eval.eval_verifier import run

CASES = run()


def test_truthful_numbers_are_never_rejected():
    """False positives are the one failure that makes a guardrail unusable:
    it would block correct output and train everyone to ignore it."""
    control = CASES["truthful control"]
    assert control.caught == 0, (
        f"{control.caught}/{control.total} correctly quoted values were rejected"
    )


def test_unanchored_invention_is_mostly_caught():
    """The guardrail's actual strength: a number with no relation to the
    model gets rejected most of the time. Below this the layer would be
    decorative."""
    case = CASES["free invention"]
    assert case.catch_rate >= 0.80, f"catch rate fell to {case.catch_rate:.0%}"


def test_magnitude_errors_are_mostly_caught():
    case = CASES["order-of-magnitude error"]
    assert case.catch_rate >= 0.80, f"catch rate fell to {case.catch_rate:.0%}"


def test_near_miss_fabrication_is_a_known_blind_spot():
    """Anything inside the relative tolerance is invisible to the verifier by
    construction — and drift, not invention, is how models actually fail.

    Asserted as a bound rather than an aspiration: if this ever improves, the
    README's stated limitation is wrong and must be updated alongside.
    """
    case = CASES["near-miss fabrication"]
    assert case.catch_rate <= 0.25, (
        f"near-miss catch rate is now {case.catch_rate:.0%} — the README still "
        "documents this as a blind spot; update it"
    )


def test_cross_metric_attribution_cannot_be_caught_at_all():
    """A real value reported under the wrong metric's name.

    Structural, not a tuning artifact: verify_grounding() compares numbers
    against the whole table and never sees which label a claim attaches them
    to. Closing this needs claim-level checking, not a tighter tolerance —
    the same gap that let a stress scenario be described as the driver-based
    forecast while every number in the sentence was real.
    """
    case = CASES["cross-metric attribution"]
    assert case.caught == 0, (
        "the verifier now catches mis-attribution — that is a design change, "
        "so update the README and this test together"
    )
