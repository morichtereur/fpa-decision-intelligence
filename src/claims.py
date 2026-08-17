"""
Stage 5b: claim-level coherence, the layer above grounding.

`verify_grounding()` answers one question: does this number appear in the
output table? That is necessary and it is not sufficient. Every number can be
real while the sentence built from them is false, because a number carries no
record of which quantity it is. The published commentary demonstrated this
rather than hypothesised it — three of five preset paragraphs scored a 1.0
grounding rate while saying something untrue:

    "actual results of 2,056 fell short of the driver-based forecast of
     1,750.0 by 14.9 percent"

2,056 is larger than 1,750. Both figures are in the table, so grounding
passes; the sentence states the central finding of the whole project
backwards.

This module checks how numbers are *used*, deterministically and with no API
call. Three checks, each targeting a failure the shipped output actually
contained:

``direction``      a comparison whose arithmetic contradicts its verb
``comparison_base``  a forecast error re-labelled as an outperformance —
                   different quantities with different denominators
``attribution``    a number quoted under a metric it does not belong to,
                   which is the structural blind spot
                   tests/test_verifier_adversarial.py pins as uncatchable by
                   value matching alone

It is a linter for financial prose, not a language model. It only fires on
patterns it can resolve unambiguously, and stays silent otherwise — a
guardrail that cries wolf gets switched off, and this one is meant to gate
publication.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# --------------------------------------------------------------------- vocabulary

#: Surface forms for the metrics the output table can contain. Order matters
#: within a metric: the longest phrase is matched first so "operating profit"
#: is not shadowed by a bare "profit".
METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "free_cash_flow": ("free cash flow", "fcf"),
    "operating_working_capital": ("operating working capital", "working capital"),
    "change_in_working_capital": ("change in working capital",),
    "operating_profit": ("operating profit", "operating income", "ebit"),
    "ebitda": ("ebitda",),
    "revenue": ("revenue", "net sales", "sales", "turnover"),
    "capex": ("capex", "capital expenditure"),
    "tax": ("tax",),
    "nopat": ("nopat",),
    "da": ("depreciation", "amortisation", "amortization"),
}

#: Surface forms for the series a value can belong to. `actual` is the one
#: that matters most: almost every false statement in the shipped commentary
#: got the relationship between actual and a forecast the wrong way round.
SERIES_ALIASES: dict[str, tuple[str, ...]] = {
    "actual": ("actual", "actuals", "came in at", "delivered", "reported", "materialised"),
    "naive": ("naive", "top-down", "extrapolation"),
    "driver_based": ("driver-based", "driver based"),
    "upside": ("upside",),
    "downside": ("downside",),
    "wc_stress": ("working capital stress", "wc stress"),
    "margin_compression": ("margin compression",),
}

#: Phrases asserting the first number is the smaller one.
BELOW_PHRASES: tuple[str, ...] = (
    "fell short of",
    "fell below",
    "came in below",
    "short of",
    "below",
    "under the",
    "trailed",
    "lagged",
    "undershot",
    "undershooting",
    "underperformed",
    "missed",
)

#: Phrases asserting the first number is the larger one.
ABOVE_PHRASES: tuple[str, ...] = (
    "exceeded",
    "came in above",
    "above",
    "ahead of",
    "outperformed",
    "beat",
    "overshot",
    "surpassed",
)

#: Language that frames a figure as the actual outperforming a forecast. A
#: forecast-error percentage cited here is the wrong quantity: the error is
#: measured against actual, the outperformance against the forecast, so they
#: have different denominators and never agree.
OUTPERFORMANCE_PHRASES: tuple[str, ...] = (
    "beat",
    "beating",
    "outperform",
    "outperformed",
    "outperforming",
    "exceeded",
    "exceeding",
    "surpassed",
    "ahead of",
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

_NUMBER = re.compile(
    r"[-−]?\s*€?\s*\d[\d,]*(?:\.\d+)?\s*(?:million|billion|bn|m\b|%|percent|pp)?",
    re.IGNORECASE,
)


# ------------------------------------------------------------------------ model


@dataclass(frozen=True)
class TableEntry:
    """One value in the output table, with its series and metric kept apart.

    `_flatten_outputs()` concatenates them into a single label, which is right
    for showing the model a table and wrong for checking a claim: once
    `driver_based` and `operating_profit` are one string, nothing can ask
    whether a sentence about revenue is quoting a profit figure.
    """

    series: str
    metric: str
    value: float
    is_error_pct: bool

    @property
    def label(self) -> str:
        suffix = "_error_pct" if self.is_error_pct else ""
        return f"{self.series}_{self.metric}{suffix}"


@dataclass(frozen=True)
class Finding:
    """One incoherent claim, quoted with enough context to judge it."""

    kind: str
    sentence: str
    detail: str


@dataclass(frozen=True)
class _Number:
    raw: str
    value: float
    start: int
    end: int
    is_percent: bool
    is_magnitude: bool  # "by 22.3%" — the size of a difference, not a comparand


# -------------------------------------------------------------------- indexing


def index_outputs(backtest_result: dict) -> list[TableEntry]:
    """Turn the nested {series: {metric: value}} result into typed entries.

    Takes the nested result rather than the flattened table on purpose: the
    series/metric split is exactly the information flattening destroys.
    """
    entries: list[TableEntry] = []
    for series, metrics in backtest_result.items():
        if not isinstance(metrics, dict):
            continue
        for key, value in metrics.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            metric, is_error = (key[: -len("_error_pct")], True) if key.endswith("_error_pct") else (key, False)
            entries.append(TableEntry(series, metric, round(float(value), 1), is_error))
    return entries


# -------------------------------------------------------------------- parsing


def _parse_number(raw: str) -> tuple[float, bool] | None:
    text = raw.strip().replace("−", "-").replace("€", "").replace(",", "").strip()
    is_percent = bool(re.search(r"%|percent|pp", text, re.IGNORECASE))
    multiplier = 1000.0 if re.search(r"billion|bn", text, re.IGNORECASE) else 1.0
    # `%` gets no \b: it is not a word character, so "22.3%" at the end of a
    # token has no trailing word boundary and a single \b-terminated
    # alternation silently leaves the symbol attached — which made every
    # symbol-form percentage unparseable while the spelled-out "22.3 percent"
    # went through. The word units keep their boundary so "m" does not eat the
    # "m" of "million".
    text = re.sub(r"\b(million|billion|bn|percent|pp|m)\b|%", "", text, flags=re.IGNORECASE).strip()
    if not text or text == "-":
        return None
    try:
        return float(text) * multiplier, is_percent
    except ValueError:
        return None


def _numbers(sentence: str) -> list[_Number]:
    found: list[_Number] = []
    for match in _NUMBER.finditer(sentence):
        parsed = _parse_number(match.group(0))
        if parsed is None:
            continue
        value, is_percent = parsed
        if abs(value) < 1:  # "3-5 sentences" and similar stray digits
            continue
        preceding = sentence[max(0, match.start() - 40) : match.start()].lower()
        # "by 22.3%" states the size of a gap; it is not one of the two things
        # being compared, and treating it as one produces nonsense comparisons
        # ("1,069.2 undershot 3.4 percent"). The intensifier between the
        # preposition and the figure is optional and common — "by just 3.4
        # percent", "by roughly 12%" — so it is matched rather than required.
        is_magnitude = is_percent and bool(
            re.search(r"\b(?:by|of|a|to)\b(?:\s+\w+){0,3}\s*$", preceding)
        )
        found.append(_Number(match.group(0).strip(), value, match.start(), match.end(), is_percent, is_magnitude))
    return found


def _mentions(sentence: str, aliases: dict[str, tuple[str, ...]]) -> set[str]:
    lowered = sentence.lower()
    return {key for key, terms in aliases.items() if any(term in lowered for term in terms)}


def _matching_entries(value: float, entries: list[TableEntry], tolerance: float) -> list[TableEntry]:
    """Table entries this number could be quoting, closest first.

    Magnitude-only matching (|claim| vs |value|) mirrors verify_grounding():
    natural phrasing states the size of a negative error without its sign.

    Sorted by distance because a finding names the entry it matched, and with
    several inside the tolerance band the nearest one is the one the sentence
    is actually about — naming a different one makes a correct finding read
    like a bug.
    """
    scored: list[tuple[float, TableEntry]] = []
    for entry in entries:
        if entry.value == 0:
            continue
        signed = abs(value - entry.value) / abs(entry.value)
        unsigned = abs(abs(value) - abs(entry.value)) / abs(entry.value)
        distance = min(signed, unsigned)
        if distance <= tolerance:
            scored.append((distance, entry))
    scored.sort(key=lambda pair: pair[0])
    return [entry for _, entry in scored]


#: The comma needs a lookahead: a thousands separator is not a clause
#: boundary, and splitting on it cuts "2,056" into two fragments — which
#: silently removes the number from every check that follows. Only the
#: following character can distinguish the two, since "1,480.3, beating" has a
#: digit on the left of a genuine boundary.
#:
#: A parenthetical is a boundary too. "2,056, above the naive forecast
#: of 1,596.5 (which understated actual by 22.3%) and slightly above the upside
#: forecast of 2,024.4" compares one subject against two objects; without the
#: bracket the two objects get read as a comparison with each other. Splitting
#: on "and" as well would also work and costs a real catch, so it is left out.
_CLAUSE_SPLIT = re.compile(
    r",(?!\d)|[;:()]|—|--|\bthough\b|\byet\b|\bwhile\b|\bwhereas\b|\bbut\b|\bhowever\b|\balthough\b",
    re.IGNORECASE,
)


def _clause_around(sentence: str, position: int) -> str:
    """The clause a number sits in.

    A sentence routinely carries two opposite claims — "exceeded X ... though
    it fell short of Y" — so checking framing at sentence level attributes the
    first clause's verb to the second clause's figure. That is how a guardrail
    starts producing findings nobody trusts.
    """
    start = 0
    end = len(sentence)
    for match in _CLAUSE_SPLIT.finditer(sentence):
        if match.end() <= position:
            start = match.end()
        elif match.start() > position:
            end = match.start()
            break
    return sentence[start:end]


def _phrase_between(sentence: str, first: _Number, second: _Number, phrases: tuple[str, ...]) -> str | None:
    segment = sentence[first.end : second.start].lower()
    for phrase in phrases:
        if phrase in segment:
            return phrase
    return None


# --------------------------------------------------------------------- checks


def _check_direction(sentence: str, numbers: list[_Number]) -> list[Finding]:
    """A comparison whose arithmetic contradicts its own verb.

    Only fires on `A <phrase> B` where the phrase sits between the two
    numbers, so the subject and object of the comparison are unambiguous.
    """
    findings = []
    comparands = [n for n in numbers if not n.is_magnitude]
    for first, second in zip(comparands, comparands[1:]):
        # A euro figure and a percentage are not comparable quantities, and a
        # verb sitting between them is describing something else.
        if first.is_percent != second.is_percent:
            continue
        # Only compare within one clause. "...1,069.2, undershooting by 3.4
        # percent, versus the naive forecast's 14.8 percent" would otherwise
        # read the verb from the middle clause as linking the outer two.
        if _clause_around(sentence, first.start) != _clause_around(sentence, second.start):
            continue
        below = _phrase_between(sentence, first, second, BELOW_PHRASES)
        above = _phrase_between(sentence, first, second, ABOVE_PHRASES)
        if below and first.value <= second.value:
            continue
        if above and first.value >= second.value:
            continue
        if below:
            findings.append(Finding(
                "direction",
                sentence,
                f"'{first.raw}' is stated as {below} '{second.raw}', but "
                f"{first.value:,.1f} is greater than {second.value:,.1f}.",
            ))
        elif above:
            findings.append(Finding(
                "direction",
                sentence,
                f"'{first.raw}' is stated as {above} '{second.raw}', but "
                f"{first.value:,.1f} is less than {second.value:,.1f}.",
            ))
    return findings


def _check_comparison_base(
    sentence: str, numbers: list[_Number], entries: list[TableEntry], tolerance: float
) -> list[Finding]:
    """A forecast error re-labelled as an outperformance.

    The table stores `*_error_pct` as (forecast - actual) / actual: the
    forecast's error, measured against actual. "Actual beat the forecast by
    X%" is a different quantity measured against the forecast. Quoting the
    first as the second is arithmetically grounded and financially wrong, and
    it understates the beat every time.
    """
    findings = []
    for number in numbers:
        if not number.is_percent:
            continue
        clause = _clause_around(sentence, number.start).lower()
        if not any(phrase in clause for phrase in OUTPERFORMANCE_PHRASES):
            continue
        matches = _matching_entries(number.value, entries, tolerance)
        if not matches or not all(entry.is_error_pct for entry in matches):
            continue
        entry = matches[0]
        # The correctly-based figure, for the message: error is x/actual, the
        # beat is the same gap over the forecast.
        findings.append(Finding(
            "comparison_base",
            sentence,
            f"'{number.raw}' is framed as an outperformance but matches "
            f"{entry.label} = {entry.value}, which is the forecast's error "
            "measured against actual. The two use different denominators; the "
            "outperformance is the larger number.",
        ))
    return findings


def _check_attribution(
    sentence: str, numbers: list[_Number], entries: list[TableEntry], tolerance: float
) -> list[Finding]:
    """A real value quoted under a metric it does not belong to.

    Only fires when the sentence names exactly one metric — with two or more
    in play, which number belongs to which is genuinely ambiguous and a
    guardrail should not guess.
    """
    metrics = _mentions(sentence, METRIC_ALIASES)
    if len(metrics) != 1:
        return []
    metric = next(iter(metrics))

    findings = []
    for number in numbers:
        matches = _matching_entries(number.value, entries, tolerance)
        if not matches:
            continue  # ungrounded: verify_grounding()'s job, not this one
        if any(entry.metric == metric for entry in matches):
            continue
        wrong = matches[0]
        findings.append(Finding(
            "attribution",
            sentence,
            f"'{number.raw}' appears in a sentence about {metric.replace('_', ' ')}, "
            f"but matches only {wrong.label} = {wrong.value}.",
        ))
    return findings


# ---------------------------------------------------------------------- public


def verify_claims(commentary: str, entries: list[TableEntry], tolerance: float = 0.05) -> dict:
    """Check how the numbers are used, not just whether they exist.

    Returns the findings plus the counts needed to report a rate alongside the
    grounding rate. `clean` is the gate: false means this paragraph should not
    ship as written.
    """
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(commentary.strip()) if s.strip()]
    findings: list[Finding] = []
    for sentence in sentences:
        numbers = _numbers(sentence)
        if not numbers:
            continue
        findings.extend(_check_direction(sentence, numbers))
        findings.extend(_check_comparison_base(sentence, numbers, entries, tolerance))
        findings.extend(_check_attribution(sentence, numbers, entries, tolerance))

    return {
        "sentences": len(sentences),
        "findings": [
            {"kind": f.kind, "sentence": f.sentence, "detail": f.detail} for f in findings
        ],
        "finding_count": len(findings),
        "clean": not findings,
    }
