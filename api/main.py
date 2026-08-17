"""
FastAPI layer over api/service.py. Every route calls into service.py,
which calls into src/* — this file has no forecasting logic of its own.
Run with `make api` (uvicorn api.main:app --reload --port 8000).
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api import service
from src import config as C, drivers

app = FastAPI(title="FP&A Decision Model API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=C.CORS_ORIGINS,
    allow_origin_regex=C.CORS_ORIGIN_REGEX,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class ScenarioRequest(BaseModel):
    driver_values: dict[str, float]


def _validate(driver_values: dict) -> None:
    """Names and ranges come from drivers.py — the same spec the sliders are
    built from — so the API and the UI cannot drift apart."""
    try:
        service.validate_driver_values(driver_values)
    except service.DriverValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/outlook")
def outlook():
    return service.get_outlook()


@app.get("/api/drivers")
def driver_config():
    return service.get_driver_config()


@app.get("/api/presets")
def presets():
    return service.get_presets()


@app.post("/api/scenario")
def scenario(req: ScenarioRequest):
    _validate(req.driver_values)
    return service.compute_scenario(req.driver_values)


@app.get("/api/backtest")
def backtest():
    return service.get_backtest()


@app.get("/api/driver-priority")
def driver_priority():
    return service.get_driver_priority()


@app.get("/api/monte-carlo")
def monte_carlo():
    return service.get_monte_carlo()


@app.get("/api/assumptions")
def assumptions():
    return service.get_assumption_register()


@app.get("/api/commentary/{scenario_id}")
def commentary(scenario_id: str):
    if scenario_id not in drivers.PRESETS:
        raise HTTPException(404, f"Unknown scenario: {scenario_id}")
    result = service.get_commentary_for(scenario_id)
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
    _validate(req.driver_values)
    return service.generate_live_commentary(req.driver_values)
