"""Central config. All secrets come from the environment — nothing is hardcoded."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
FACTS = DATA / "facts"

COMPANY = "adidas AG"

# adidas doesn't disclose a price/volume bridge (checked — see
# data/raw/README.md). The real driver structure it reports is channel and
# category splits of currency-neutral growth, so that's what this models.
CHANNELS = ["Wholesale", "Direct-to-Consumer"]
CATEGORIES = ["Footwear", "Apparel", "Accessories and Gear"]
FISCAL_YEARS = [2023, 2024, 2025]

# LLM — only used for the grounded commentary layer, never for the forecast
# numbers themselves. The deployment does hold a key, scoped to its own
# workspace with a monthly spend cap: that cap, not the code, is what bounds
# the damage on a public endpoint. Without a key the live endpoint returns 503
# and preset commentary still works, served from the committed
# data/commentary.json.
#
# Which vendor serves it is `LLM_PROVIDER` — see src/provider.py. Two are
# implemented: the Anthropic API directly, and Amazon Bedrock through its
# OpenAI-compatible endpoint.
LLM_PROVIDER = (os.getenv("LLM_PROVIDER") or "anthropic").strip().lower()

# Anthropic. Haiku by default: p2p-process-mining measured Haiku 4.5 matching
# Sonnet 5 on citation grounding (100% on both) at roughly a third of the
# cost, and this layer does the same job — prose over a numbers table it must
# not depart from.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Bedrock, via its OpenAI-compatible endpoint. The base URL carries the
# region. OPENAI_* are accepted as fallbacks because that is what the Bedrock
# console hands you and what the `openai` SDK reads by default — but the
# BEDROCK_-prefixed names are preferred, since a variable called
# OPENAI_API_KEY holding a Bedrock key is a trap for the next reader.
BEDROCK_API_KEY = os.getenv("BEDROCK_API_KEY") or os.getenv("OPENAI_API_KEY", "")
BEDROCK_BASE_URL = os.getenv("BEDROCK_BASE_URL") or os.getenv("OPENAI_BASE_URL", "")

# Empty means "whatever the active provider's default is". A single hardcoded
# model id would name a model that only one of the providers can serve.
COMMENTARY_MODEL = os.getenv("COMMENTARY_MODEL", "").strip()

# Browser origins allowed to call the API. Local dev by default; the deployed
# frontend's origin is added through the environment.
_DEFAULT_ORIGINS = "http://localhost:3000,http://localhost:3001"


def _clean_origin(value: str) -> str:
    """An Origin header carries no trailing slash and no quotes. A value typed
    into a hosting dashboard often carries both, and then silently matches
    nothing — which looks identical to CORS being broken."""
    return value.strip().strip('"').strip("'").rstrip("/")


# `os.getenv(name, default)` falls back to the default only when the variable
# is ABSENT. Present-but-empty returns "", which split/filter reduces to [] —
# allowing no origin at all, including the localhost defaults. That is exactly
# what an env-var UI produces when a key is added with a blank value, so treat
# empty as absent.
# .strip() before the `or`: a whitespace-only value is truthy and would
# otherwise survive to the same empty result as "".
_raw_origins = (os.getenv("CORS_ORIGINS") or "").strip() or _DEFAULT_ORIGINS
CORS_ORIGINS = [o for o in (_clean_origin(p) for p in _raw_origins.split(",")) if o]

# Every Vercel preview deployment gets its own hostname, so an exact list
# breaks on each branch. Scoped to this project rather than all of
# *.vercel.app on purpose: with an API key in the environment, this list is
# what stands between /api/commentary/live and somebody else's browser
# spending the bill.
CORS_ORIGIN_REGEX = (
    os.getenv("CORS_ORIGIN_REGEX")
    or r"^https://fpa-decision-model[a-z0-9-]*\.vercel\.app$"
)
