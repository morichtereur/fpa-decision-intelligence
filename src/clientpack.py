"""
Client packs: the boundary between the reusable decision engine and one
client's economics.

Everything that is *this company* rather than *this method* lives in
clients/<id>/ as configuration. The engine (src/model.py, src/scenario.py,
the materiality logic) reads a pack and has no knowledge of which client
it is serving.

Why a resolver vocabulary rather than literal numbers
-----------------------------------------------------
The obvious schema gives every driver a literal baseline:

    revenue_growth: {baseline: 8.0}

That works for a demo client and quietly breaks the adidas one. adidas's
driver defaults are not free parameters — they are *derived* from what the
company disclosed, and they are chosen so that running them through
model.forecast() reproduces src.backtest.driver_based() exactly. The
planner's Base case IS the backtested forecast; that identity is what makes
the backtest evidence for the planner rather than a separate exhibit. Freeze
those numbers as literals and the link silently rots the first time a fact
is corrected.

So a baseline is one of:

    baseline: {literal: 8.0}
    baseline: {fact: "group.2024.effective_tax_rate_pct"}
    baseline: {midpoint: ["guidance...pct_low", "guidance...pct_high"]}
    baseline: {solve: ebitda_margin_for_operating_profit, args: {...}}

`literal` covers synthetic clients. `fact` and `midpoint` cover values read
straight off a disclosure. `solve` names a function registered in SOLVERS
below — model-specific algebra stays in Python where it is testable, and the
YAML only says which one to apply. There is deliberately no general
expression evaluator: config should be declarative and safe to read, not a
second programming language.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = ROOT / "clients"

# The assumption keys src.model.forecast() understands. A driver's `maps_to`
# must name one of these, or the engine would silently ignore it.
MODEL_ASSUMPTION_KEYS = {
    "division_growth",  # special: broadcast across every revenue segment
    "ebitda_margin_pct",
    "effective_tax_rate_pct",
    "operating_working_capital_pct",
    "capex_eur_m",
}

CONFIDENCE_LEVELS = ("High", "Medium", "Low")
CONTROLLABILITY_LEVELS = ("High", "Medium", "Low")


class ClientPackError(ValueError):
    """A pack that cannot be loaded, or that would produce a model the
    engine cannot run. Raised at load time rather than at forecast time —
    a malformed pack should fail loudly on startup, not produce a plausible
    wrong number three screens later."""


# --------------------------------------------------------------------------
# Fact access
# --------------------------------------------------------------------------

def read_fact(facts: dict, path: str) -> Any:
    """Dotted path into the facts document: "group.2024.ebitda"."""
    node: Any = facts
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise ClientPackError(f"Fact path not found: {path!r} (failed at {part!r})")
        node = node[part]
    return node


# --------------------------------------------------------------------------
# Baseline resolvers
# --------------------------------------------------------------------------

def _solve_ebitda_margin_for_operating_profit(facts: dict, args: dict, resolved: dict) -> float:
    """The EBITDA margin (%) that makes model.forecast() land on a target
    operating profit, given its D&A-scaling rule.

    This is the same algebra as src.backtest._margin_for_operating_profit —
    kept in one place now, and referenced from config, so the planner and
    the backtest cannot drift apart.

    `at_growth_driver` accepts one driver id or several. Several matter when a
    client decomposes growth (manufacturing_demo splits it into volume and
    price): the margin has to be solved at the *total* growth those drivers
    imply, or it would be consistent with only part of the revenue line.
    """
    names = args["at_growth_driver"]
    if isinstance(names, str):
        names = [names]
    missing = [n for n in names if n not in resolved]
    if missing:
        raise ClientPackError(
            f"solve: ebitda_margin_for_operating_profit references driver(s) {missing}, "
            f"which have no resolved baseline. A solver may only reference drivers with "
            f"a literal/fact/midpoint baseline."
        )
    growth = sum(resolved[n] for n in names) / 100

    segments = read_fact(facts, args["segments"])
    baseline_revenue = sum(v for k, v in segments.items() if k != "source")
    revenue = baseline_revenue * (1 + growth)

    group = read_fact(facts, args["baseline_group"])
    baseline_da = group["ebitda"] - group["operating_profit"]

    target = _resolve_scalar(facts, args["target"], resolved)
    return (target / revenue + baseline_da / baseline_revenue) * 100


SOLVERS = {
    "ebitda_margin_for_operating_profit": _solve_ebitda_margin_for_operating_profit,
}


def _resolve_scalar(facts: dict, spec: Any, resolved: dict) -> float:
    """Resolve a baseline spec that is not a solver."""
    if isinstance(spec, (int, float)):
        return float(spec)
    if not isinstance(spec, dict) or len(spec) == 0:
        raise ClientPackError(f"Un-resolvable baseline spec: {spec!r}")

    if "literal" in spec:
        return float(spec["literal"])
    if "fact" in spec:
        value = read_fact(facts, spec["fact"])
        if not isinstance(value, (int, float)):
            raise ClientPackError(f"Fact {spec['fact']!r} is not numeric: {value!r}")
        return float(value)
    if "fact_scaled" in spec:
        path, multiplier = spec["fact_scaled"]
        return _resolve_scalar(facts, {"fact": path}, resolved) * float(multiplier)
    if "midpoint" in spec:
        low, high = spec["midpoint"]
        return (_resolve_scalar(facts, {"fact": low} if isinstance(low, str) else low, resolved)
                + _resolve_scalar(facts, {"fact": high} if isinstance(high, str) else high, resolved)) / 2
    raise ClientPackError(f"Unknown baseline form: {sorted(spec)}")


def resolve_scalar(facts: dict, spec: Any) -> float:
    """Public form of the resolver, for config outside the driver block —
    Monte Carlo bounds, decision thresholds."""
    return _resolve_scalar(facts, spec, {})


def resolve_baselines(facts: dict, driver_specs: dict) -> dict[str, float]:
    """Two passes: plain baselines first, then solvers, which may reference
    the values the first pass produced. Deliberately not a general dependency
    graph — one level of reference is all the finance needs, and a DAG here
    would be machinery in search of a use."""
    resolved: dict[str, float] = {}
    deferred: list[str] = []

    for driver_id, spec in driver_specs.items():
        baseline = spec.get("baseline")
        if baseline is None:
            raise ClientPackError(f"Driver {driver_id!r} has no baseline")
        if isinstance(baseline, dict) and "solve" in baseline:
            deferred.append(driver_id)
            continue
        resolved[driver_id] = _resolve_scalar(facts, baseline, resolved)

    for driver_id in deferred:
        baseline = driver_specs[driver_id]["baseline"]
        name = baseline["solve"]
        if name not in SOLVERS:
            raise ClientPackError(f"Unknown solver {name!r} (have: {sorted(SOLVERS)})")
        resolved[driver_id] = SOLVERS[name](facts, baseline.get("args", {}), resolved)

    return resolved


# --------------------------------------------------------------------------
# Pack model
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class DriverSpec:
    """One planning driver. `confidence` and `controllability` are declared
    judgements, not computed — see the materiality docs. They are carried as
    data so the UI can label them as judgements rather than implying they
    fell out of the model."""

    id: str
    label: str
    category: str
    unit: str
    default: float
    min: float
    max: float
    step: float
    maps_to: str
    impacts: tuple[str, ...]
    confidence: str
    controllability: str
    owner: str
    source: str
    guidance_text: str
    description: str = ""
    guidance_low: float | None = None
    guidance_high: float | None = None
    scale: float = 1.0  # multiplier applied when handing the value to the model

    # How this driver contributes to its model assumption. Several drivers
    # may share one assumption; exactly one of them is the base.
    #
    #   base  — the driver IS the assumption.        assumption  = value x scale
    #   add   — the driver is a component of it.     assumption += value x scale x sign
    #   delta — only the driver's MOVEMENT counts.   assumption += (value - baseline) x scale x sign
    #
    # The add/delta distinction is a real finance distinction, not a
    # technicality. Price growth is a *component* of revenue growth: at plan
    # it still contributes its two points. Inventory days are a *deviation*:
    # the plan level is already inside the working-capital base, so only
    # movement away from plan may move the assumption, or the same days would
    # be counted twice. Getting this wrong silently understates the base case,
    # which is exactly the class of error that makes a model untrustworthy.
    role: str = "base"
    sign: float = 1.0

    # Which Monte Carlo variable this driver's uncertainty rides on. Several
    # drivers may share one (manufacturing_demo's DSO, inventory days and DPO
    # all ride working_capital_pct) because the simulation samples the model
    # assumption, not the business driver. None means "not simulated" — stated
    # rather than silently scored zero.
    sensitivity_key: str | None = None

    # The range this driver is swung across to size its euro exposure. Falls
    # back to the disclosed guidance range when the client published one. The
    # slider's min/max is deliberately never used: those are the bounds of what
    # the model can compute, not of what management considers plausible.
    exposure_range: tuple[float, float] | None = None

    def to_dict(self) -> dict:
        """The shape the API and frontend consume. Field names match what the
        inherited UI already reads, so the pack layer is invisible to it."""
        return {
            "label": self.label,
            "category": self.category,
            "unit": self.unit,
            "min": self.min,
            "max": self.max,
            "step": self.step,
            "default": self.default,
            "guidance_low": self.guidance_low,
            "guidance_high": self.guidance_high,
            "guidance_text": self.guidance_text,
            "confidence": self.confidence,
            "controllability": self.controllability,
            "owner": self.owner,
            "source": self.source,
            "description": self.description,
            "impacts": list(self.impacts),
            "role": self.role,
            # The interface's driver tree hangs each client's drivers off the
            # calculation step they feed, so it needs to know which model
            # assumption each one maps to.
            "maps_to": self.maps_to,
            "sensitivity_key": self.sensitivity_key,
            "exposure_range": list(self.exposure_range) if self.exposure_range else None,
        }


@dataclass(frozen=True)
class ClientPack:
    id: str
    name: str
    short_label: str
    data_basis: str  # "Public Data" | "Synthetic Demo" — shown next to the name
    industry: str
    currency: str
    currency_symbol: str
    unit: str
    fiscal_year: str
    baseline_year: str
    objective: str
    is_synthetic: bool
    has_backtest: bool
    disclaimer: str
    facts: dict
    drivers: dict[str, DriverSpec]
    driver_order: tuple[str, ...]
    segments_path: str
    baseline_group_path: str
    presets: dict
    monte_carlo: dict
    assumption_bases: dict = field(default_factory=dict)
    materiality_thresholds: dict = field(default_factory=lambda: {"high": 0.0, "medium": 0.0})
    decision_rules: tuple[dict, ...] = ()
    mappings: dict = field(default_factory=dict)
    audiences: tuple[str, ...] = ()

    # -- engine interface --------------------------------------------------

    @property
    def segments(self) -> dict:
        return {k: v for k, v in read_fact(self.facts, self.segments_path).items() if k != "source"}

    @property
    def baseline_group(self) -> dict:
        return read_fact(self.facts, self.baseline_group_path)

    def base_driver_values(self) -> dict[str, float]:
        return {driver_id: spec.default for driver_id, spec in self.drivers.items()}

    def to_assumptions(self, driver_values: dict[str, float]) -> dict:
        """Flat {driver_id: value} -> the nested shape model.forecast() wants.

        Replaces the hardcoded drivers.defaults_to_assumptions(): the mapping
        comes from each driver's `maps_to`, so a client with different drivers
        needs no code change.

        Each model assumption starts from either its `base` driver or an
        `assumption_bases` entry, then every `delta` driver mapped to it adds
        `sign x (value - baseline) x scale`. At baseline values every delta is
        zero by construction, so a client's base case is exactly its declared
        plan — which is what makes "reproduces the backtest" checkable.
        """
        missing_values = [d for d in self.drivers if d not in driver_values]
        if missing_values:
            raise ClientPackError(f"Missing value(s) for driver(s): {sorted(missing_values)}")

        assumptions: dict[str, Any] = {}
        for key, spec_value in self.assumption_bases.items():
            assumptions[key] = spec_value

        # Bases first — a delta is meaningless without something to adjust.
        for driver_id, spec in self.drivers.items():
            if spec.role != "base":
                continue
            if spec.maps_to in assumptions:
                raise ClientPackError(
                    f"Assumption {spec.maps_to!r} has both an assumption_bases entry and a "
                    f"base driver ({driver_id!r}) — one source only."
                )
            assumptions[spec.maps_to] = driver_values[driver_id] * spec.scale

        for driver_id, spec in self.drivers.items():
            if spec.role == "base":
                continue
            if spec.maps_to not in assumptions:
                raise ClientPackError(
                    f"Driver {driver_id!r} contributes to {spec.maps_to!r}, which has no base. "
                    f"Give that assumption a base driver or an assumption_bases entry."
                )
            value = driver_values[driver_id]
            contribution = value if spec.role == "add" else (value - spec.default)
            assumptions[spec.maps_to] += contribution * spec.scale * spec.sign

        missing = MODEL_ASSUMPTION_KEYS - set(assumptions)
        if missing:
            raise ClientPackError(
                f"Client {self.id!r} leaves model assumption(s) {sorted(missing)} unset — "
                f"each needs a driver with that `maps_to`, or an assumption_bases entry."
            )

        # division_growth is the one assumption the model wants per segment
        # rather than as a scalar.
        growth = assumptions["division_growth"]
        if not isinstance(growth, dict):
            assumptions["division_growth"] = {k: growth for k in self.segments}
        return assumptions

    def out_of_guidance(self, driver_id: str, value: float) -> bool:
        spec = self.drivers[driver_id]
        if spec.guidance_low is None or spec.guidance_high is None:
            return False
        return value < spec.guidance_low or value > spec.guidance_high

    def summary(self) -> dict:
        """Identity, for the client selector and page chrome."""
        return {
            "id": self.id,
            "name": self.name,
            "short_label": self.short_label,
            "data_basis": self.data_basis,
            "industry": self.industry,
            "currency": self.currency,
            "currency_symbol": self.currency_symbol,
            "unit": self.unit,
            "fiscal_year": self.fiscal_year,
            "objective": self.objective,
            "is_synthetic": self.is_synthetic,
            "has_backtest": self.has_backtest,
            "disclaimer": self.disclaimer,
            "audiences": list(self.audiences),
        }


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def _read_yaml(path: Path) -> dict:
    if not path.exists():
        raise ClientPackError(f"Missing pack file: {path}")
    return yaml.safe_load(path.read_text()) or {}


def _materiality_thresholds(client_id: str, client: dict) -> dict:
    """Euro bands for High / Medium exposure. Required, and per client:
    materiality is relative to the size of the business, and a shared default
    would quietly rank a EUR 1.9bn manufacturer against a EUR 24bn brand's
    yardstick."""
    raw = client.get("materiality_thresholds") or {}
    missing = {"high", "medium"} - set(raw)
    if missing:
        raise ClientPackError(
            f"Client {client_id!r} must declare materiality_thresholds with "
            f"`high` and `medium` (missing: {sorted(missing)})"
        )
    high, medium = float(raw["high"]), float(raw["medium"])
    if not high > medium > 0:
        raise ClientPackError(
            f"Client {client_id!r} materiality_thresholds must satisfy high > medium > 0, "
            f"got high={high}, medium={medium}"
        )
    return {"high": high, "medium": medium}


def _validate_driver(driver_id: str, spec: DriverSpec) -> None:
    if spec.maps_to not in MODEL_ASSUMPTION_KEYS:
        raise ClientPackError(
            f"Driver {driver_id!r} maps_to {spec.maps_to!r}, which the model does not "
            f"understand (valid: {sorted(MODEL_ASSUMPTION_KEYS)})"
        )
    if spec.confidence not in CONFIDENCE_LEVELS:
        raise ClientPackError(f"Driver {driver_id!r} has confidence {spec.confidence!r}")
    if spec.controllability not in CONTROLLABILITY_LEVELS:
        raise ClientPackError(f"Driver {driver_id!r} has controllability {spec.controllability!r}")
    if not spec.min <= spec.default <= spec.max:
        raise ClientPackError(
            f"Driver {driver_id!r} baseline {spec.default} falls outside its own "
            f"range [{spec.min}, {spec.max}] — the slider could not show it"
        )
    if spec.exposure_range is not None:
        low, high = spec.exposure_range
        if low >= high:
            raise ClientPackError(f"Driver {driver_id!r} exposure_range needs low < high, got {low}/{high}")
        if low < spec.min or high > spec.max:
            raise ClientPackError(
                f"Driver {driver_id!r} exposure_range [{low}, {high}] falls outside the model's own "
                f"domain [{spec.min}, {spec.max}] — the forecast is not defined there"
            )
    elif spec.guidance_low is None or spec.guidance_high is None:
        raise ClientPackError(
            f"Driver {driver_id!r} has neither an exposure_range nor a disclosed guidance range, "
            f"so its financial exposure cannot be sized. Declare one."
        )
    if spec.role not in ("base", "add", "delta"):
        raise ClientPackError(f"Driver {driver_id!r} has role {spec.role!r} (want base, add or delta)")


def load_pack(client_id: str, clients_dir: Path | None = None) -> ClientPack:
    base = (clients_dir or CLIENTS_DIR) / client_id
    if not base.is_dir():
        raise ClientPackError(f"No client pack at {base}")

    client = _read_yaml(base / "client.yaml")
    drivers_doc = _read_yaml(base / "drivers.yaml")
    scenarios = _read_yaml(base / "scenarios.yaml")
    rules = _read_yaml(base / "decision_rules.yaml")
    mappings = _read_yaml(base / "mappings.yaml")

    facts_ref = client.get("facts")
    if not facts_ref:
        raise ClientPackError(f"Client {client_id!r} declares no `facts` file")
    facts_path = base / facts_ref
    if not facts_path.exists():
        raise ClientPackError(f"Missing facts document: {facts_path}")
    import json

    facts = json.loads(facts_path.read_text())

    driver_specs = drivers_doc.get("drivers") or {}
    if not driver_specs:
        raise ClientPackError(f"Client {client_id!r} defines no drivers")

    baselines = resolve_baselines(facts, driver_specs)

    drivers: dict[str, DriverSpec] = {}
    for driver_id, raw in driver_specs.items():
        guidance = raw.get("guidance") or {}
        spec = DriverSpec(
            id=driver_id,
            label=raw["label"],
            category=raw.get("category", "Other"),
            unit=raw.get("unit", "pct"),
            default=baselines[driver_id],
            min=float(raw["min"]),
            max=float(raw["max"]),
            step=float(raw.get("step", 0.5)),
            maps_to=raw["maps_to"],
            impacts=tuple(raw.get("impacts", ())),
            confidence=raw["confidence"],
            controllability=raw["controllability"],
            owner=raw.get("owner", "Unassigned"),
            source=raw.get("source", "Not stated"),
            guidance_text=raw.get("guidance_text", ""),
            description=raw.get("description", ""),
            guidance_low=guidance.get("low"),
            guidance_high=guidance.get("high"),
            scale=float(raw.get("scale", 1.0)),
            role=raw.get("role", "base"),
            sign=float(raw.get("sign", 1.0)),
            sensitivity_key=raw.get("sensitivity_key"),
            exposure_range=(
                (float(raw["exposure_range"]["low"]), float(raw["exposure_range"]["high"]))
                if raw.get("exposure_range") else None
            ),
        )
        _validate_driver(driver_id, spec)
        drivers[driver_id] = spec

    order = tuple(drivers_doc.get("order") or drivers.keys())
    unknown = [d for d in order if d not in drivers]
    if unknown:
        raise ClientPackError(f"drivers.yaml `order` names unknown driver(s): {unknown}")
    if set(order) != set(drivers):
        raise ClientPackError(
            f"drivers.yaml `order` must list every driver exactly once "
            f"(missing: {sorted(set(drivers) - set(order))})"
        )

    pack = ClientPack(
        id=client_id,
        name=client["name"],
        short_label=client.get("short_label", client["name"]),
        data_basis=client.get("data_basis", "Synthetic Demo"),
        industry=client.get("industry", ""),
        currency=client.get("currency", "EUR"),
        currency_symbol=client.get("currency_symbol", "€"),
        unit=client.get("unit", "millions"),
        fiscal_year=str(client.get("fiscal_year", "")),
        baseline_year=str(client.get("baseline_year", "")),
        objective=client.get("objective", "Free Cash Flow"),
        is_synthetic=bool(client.get("is_synthetic", True)),
        has_backtest=bool(client.get("has_backtest", False)),
        disclaimer=client.get("disclaimer", ""),
        facts=facts,
        drivers=drivers,
        driver_order=order,
        segments_path=client["segments_path"],
        baseline_group_path=client["baseline_group_path"],
        presets=scenarios.get("presets") or {},
        monte_carlo=scenarios.get("monte_carlo") or {},
        materiality_thresholds=_materiality_thresholds(client_id, client),
        assumption_bases={
            key: resolve_scalar(facts, spec)
            for key, spec in (drivers_doc.get("assumption_bases") or {}).items()
        },
        decision_rules=tuple(rules.get("rules") or ()),
        mappings=mappings.get("metrics") or {},
        audiences=tuple(client.get("audiences") or ()),
    )

    # Fail at load time if the pack cannot actually drive the model.
    pack.to_assumptions(pack.base_driver_values())
    return pack


def available_clients(clients_dir: Path | None = None) -> list[str]:
    base = clients_dir or CLIENTS_DIR
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir() and (p / "client.yaml").exists())


DEFAULT_CLIENT = "adidas"


@lru_cache(maxsize=8)
def get_pack(client_id: str | None = None) -> ClientPack:
    """Packs are immutable once loaded, so caching them is safe. The cache is
    keyed by client id — the mechanism that stops one client's facts from
    leaking into another's forecast is that they are separate objects, never
    a mutated global."""
    return load_pack(client_id or DEFAULT_CLIENT)


def resolve_client_id(client_id: str | None) -> str:
    """Map a request's ?client= to a real pack, rejecting unknown ids rather
    than silently falling back — a typo that quietly served adidas numbers
    under a manufacturing label would be the worst possible failure here."""
    if client_id is None or client_id == "":
        return DEFAULT_CLIENT
    if client_id not in available_clients():
        raise ClientPackError(f"Unknown client {client_id!r} (available: {available_clients()})")
    return client_id
