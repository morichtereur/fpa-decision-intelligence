"""
FastAPI layer over api/service.py. Every route calls into service.py,
which calls into src/* — this file has no forecasting logic of its own.
Run with `make api` (uvicorn api.main:app --reload --port 8000).
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api import service
from src import clientpack, config as C

app = FastAPI(title="FP&A Decision Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=C.CORS_ORIGINS,
    allow_origin_regex=C.CORS_ORIGIN_REGEX,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class ScenarioRequest(BaseModel):
    driver_values: dict[str, float]
    client: str | None = None


def _client(value: str | None) -> str:
    """Reject an unknown client id rather than falling back to the default.
    A typo that quietly served adidas numbers under a manufacturing label
    would be the worst failure this API could produce."""
    try:
        return clientpack.resolve_client_id(value)
    except clientpack.ClientPackError as exc:
        raise HTTPException(404, str(exc)) from exc


ClientQuery = Query(default=None, description="Client pack id; defaults to adidas.")


def _validate(driver_values: dict, client: str) -> None:
    """Names and ranges come from the client pack — the same spec the sliders
    are built from — so the API and the UI cannot drift apart."""
    try:
        service.validate_driver_values(driver_values, client)
    except service.DriverValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/outlook")
def outlook(client: str | None = ClientQuery):
    return service.get_outlook(_client(client))


@app.get("/api/drivers")
def driver_config(client: str | None = ClientQuery):
    return service.get_driver_config(_client(client))


@app.get("/api/presets")
def presets(client: str | None = ClientQuery):
    return service.get_presets(_client(client))


@app.post("/api/scenario")
def scenario(req: ScenarioRequest):
    client = _client(req.client)
    _validate(req.driver_values, client)
    return service.compute_scenario(req.driver_values, client)


@app.get("/api/backtest")
def backtest(client: str | None = ClientQuery):
    return service.get_backtest(_client(client))


@app.get("/api/driver-priority")
def driver_priority(client: str | None = ClientQuery):
    return service.get_driver_priority(_client(client))


@app.get("/api/monte-carlo")
def monte_carlo(client: str | None = ClientQuery):
    return service.get_monte_carlo(_client(client))


@app.get("/api/assumptions")
def assumptions(client: str | None = ClientQuery):
    return service.get_assumption_register(_client(client))


@app.get("/api/clients")
def clients():
    """The client selector's source of truth. Identity only — drivers and
    numbers come from the per-client routes."""
    return {"default": clientpack.DEFAULT_CLIENT, "clients": service.list_clients()}


@app.get("/api/client")
def client_summary(client: str | None = ClientQuery):
    return service.get_client_summary(_client(client))


@app.get("/api/decision-rules")
def decision_rules(client: str | None = ClientQuery):
    return service.get_decision_rules(_client(client))


@app.get("/api/mappings")
def mappings(client: str | None = ClientQuery):
    return service.get_mappings(_client(client))


@app.get("/api/commentary/{scenario_id}")
def commentary(scenario_id: str, client: str | None = ClientQuery):
    resolved = _client(client)
    if scenario_id not in service.pack(resolved).presets:
        raise HTTPException(404, f"Unknown scenario: {scenario_id}")
    result = service.get_commentary_for(scenario_id, resolved)
    if result is None:
        raise HTTPException(
            503, "Commentary not yet generated — run `make commentary`."
        )
    return result


@app.post("/api/commentary/live")
def commentary_live(req: ScenarioRequest):
    if not C.ANTHROPIC_API_KEY:
        raise HTTPException(503, "ANTHROPIC_API_KEY not set — commentary unavailable.")
    # Validate before the billable call, not after: this endpoint is public,
    # and an out-of-range value would otherwise spend a request to produce
    # confident nonsense.
    client = _client(req.client)
    _validate(req.driver_values, client)
    return service.generate_live_commentary(req.driver_values, client=client)
