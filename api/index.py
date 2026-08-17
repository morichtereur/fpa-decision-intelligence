"""Serverless entrypoint for the API.

Vercel's Python runtime serves an ASGI app exported as `app`. The FastAPI
application itself lives in api/main.py — this module only makes the repo
root importable and re-exports it, so `from src import ...` resolves the
same way it does under uvicorn locally.

Routing is in vercel.json: every /api/* request lands here, and FastAPI
matches on the original path.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.main import app  # noqa: E402

__all__ = ["app"]
