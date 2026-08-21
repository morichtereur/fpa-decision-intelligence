"""
The readiness diagnostic.

It reports what a planning model cannot answer about itself. The property that
matters is that it works on an incomplete model — that is the only kind that
exists at the start of an engagement, and a diagnostic that requires a finished
model has nothing to diagnose.
"""

import pytest

from src import clientpack, materiality, readiness

CLIENTS = clientpack.available_clients()


@pytest.mark.parametrize("client_id", CLIENTS)
def test_a_curated_pack_answers_almost_everything(client_id):
    result = readiness.assess(clientpack.load_pack(client_id))
    assert result["answered"] >= result["total"] - 1
    assert result["summary"]


def test_the_synthetic_client_is_marked_untestable():
    """It has no outturn, and the diagnostic should say so rather than let the
    absence pass as completeness."""
    result = readiness.assess(clientpack.load_pack("manufacturing_demo"))
    gaps = {g["id"] for g in result["gaps"]}
    assert "outturn" in gaps


@pytest.mark.parametrize("client_id", CLIENTS)
def test_every_check_explains_why_it_matters(client_id):
    """A gap without a reason is a nag. Each one has to say what the field is
    for, because the readout is shown to someone deciding whether to close it."""
    for check in readiness.assess(clientpack.load_pack(client_id))["checks"]:
        assert check["why"].strip()
        assert check["question"].endswith("?")
        assert check["detail"].strip()


@pytest.mark.parametrize("client_id", CLIENTS)
def test_it_counts_rather_than_scores(client_id):
    """Deliberately no composite index: a single number invites comparison
    between businesses whose situations are not comparable."""
    result = readiness.assess(clientpack.load_pack(client_id))
    assert "score" not in result and "percentage" not in result
    assert result["answered"] <= result["total"]


def test_it_does_not_grade_the_finance_function():
    result = readiness.assess(clientpack.load_pack("adidas"))
    assert "not the quality of" in result["note"]


# --------------------------------------------------------------------------
# The case it exists for
# --------------------------------------------------------------------------

def _incomplete_pack(tmp_path):
    """A pack the way a client's actually arrives: some ranges agreed, no
    owners, no tolerances, no outturn."""
    import shutil
    import yaml

    src = clientpack.CLIENTS_DIR / "manufacturing_demo"
    target = tmp_path / "clients" / "partial"
    shutil.copytree(src, target)

    doc = yaml.safe_load((target / "drivers.yaml").read_text())
    for i, (did, spec) in enumerate(doc["drivers"].items()):
        spec.pop("owner", None)
        spec["guidance_text"] = ""
        if i % 2 == 0:
            spec.pop("exposure_range", None)
            spec.pop("guidance", None)
    (target / "drivers.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))
    (target / "decision_rules.yaml").write_text("rules: []\n")
    return clientpack.load_pack("partial", clients_dir=target.parent)


def test_an_incomplete_model_still_opens(tmp_path):
    """The loader used to refuse a driver with no plausible range, which meant
    a real client's model could not be opened until every range had been
    agreed — the one thing nobody has on day one."""
    pack = _incomplete_pack(tmp_path)
    assert len(pack.drivers) > 0


def test_an_incomplete_model_reports_its_gaps(tmp_path):
    result = readiness.assess(_incomplete_pack(tmp_path))
    gaps = {g["id"] for g in result["gaps"]}
    assert {"owner", "exposure_range", "thresholds", "guidance_text"} <= gaps
    assert result["answered"] < result["total"]


def test_unrangeable_drivers_are_shown_not_hidden(tmp_path):
    """A driver whose exposure cannot be sized appears in the ranking as
    unranked. Dropping it would understate the model; inventing a range would
    put a euro figure on a judgement nobody has made."""
    pack = _incomplete_pack(tmp_path)
    rows = materiality.rank(pack)

    assert len(rows) == len(pack.drivers)
    unranked = [r for r in rows if r["priority"] == "Unranked"]
    assert unranked, "half the drivers have no range; some rows must be unranked"
    for row in unranked:
        assert row["materiality"] == "Not quantified"
        assert row["exposure_magnitude"] == 0.0
        assert row["basis"]["materiality"] == "not computed"


def test_unranked_rows_sort_last(tmp_path):
    rows = materiality.rank(_incomplete_pack(tmp_path))
    priorities = [r["priority"] for r in rows]
    first_unranked = priorities.index("Unranked")
    assert all(p == "Unranked" for p in priorities[first_unranked:])


def test_the_endpoint_serves_it():
    from fastapi.testclient import TestClient
    from api.main import app

    api = TestClient(app)
    body = api.get("/api/readiness?client=adidas").json()
    assert body["total"] > 0 and body["summary"]
