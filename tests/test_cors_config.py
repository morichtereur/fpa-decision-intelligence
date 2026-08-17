"""CORS_ORIGINS parsing.

A production deployment rejected every origin — including the localhost
defaults — because the variable was present but empty. `os.getenv(name,
default)` only falls back when the name is ABSENT, so "" survived to
split/filter and reduced to [], which allows nothing. The symptom was two
unrelated-looking UI bugs; the cause was one empty string.
"""

import importlib
import os
import re

import pytest


def _config(value: str | None):
    os.environ.pop("CORS_ORIGINS", None)
    if value is not None:
        os.environ["CORS_ORIGINS"] = value
    import src.config as C

    return importlib.reload(C)


@pytest.fixture(autouse=True)
def _restore_env():
    before = os.environ.get("CORS_ORIGINS")
    yield
    os.environ.pop("CORS_ORIGINS", None)
    if before is not None:
        os.environ["CORS_ORIGINS"] = before
    import src.config as C

    importlib.reload(C)


def test_absent_falls_back_to_localhost():
    assert _config(None).CORS_ORIGINS == ["http://localhost:3000", "http://localhost:3001"]


def test_empty_is_treated_as_absent_not_as_allow_nothing():
    # The regression. An empty value used to yield [], and FastAPI's
    # CORSMiddleware then answered every preflight with 400.
    assert _config("").CORS_ORIGINS == ["http://localhost:3000", "http://localhost:3001"]


def test_whitespace_only_is_also_treated_as_absent():
    assert _config("   ").CORS_ORIGINS == ["http://localhost:3000", "http://localhost:3001"]


@pytest.mark.parametrize(
    "raw",
    [
        "https://fpa-decision-model.vercel.app",
        "https://fpa-decision-model.vercel.app/",
        '"https://fpa-decision-model.vercel.app"',
        "'https://fpa-decision-model.vercel.app'",
        "  https://fpa-decision-model.vercel.app  ",
    ],
)
def test_dashboard_typos_still_match_an_origin_header(raw):
    # An Origin header carries no quotes and no trailing slash; a value typed
    # into a hosting dashboard often carries both.
    assert _config(raw).CORS_ORIGINS == ["https://fpa-decision-model.vercel.app"]


def test_comma_list_is_split_and_trimmed():
    got = _config(" https://a.vercel.app , http://localhost:3000 ").CORS_ORIGINS
    assert got == ["https://a.vercel.app", "http://localhost:3000"]


def test_regex_covers_previews_but_not_the_rest_of_vercel():
    pattern = _config(None).CORS_ORIGIN_REGEX
    assert re.match(pattern, "https://fpa-decision-model.vercel.app")
    assert re.match(pattern, "https://fpa-decision-model-git-branch-scope.vercel.app")
    # Another tenant's project must not be able to call an API that holds a
    # billable key.
    assert not re.match(pattern, "https://evil.vercel.app")
    # Anchored at the end, so a lookalike suffix does not pass.
    assert not re.match(pattern, "https://fpa-decision-model.vercel.app.evil.com")
