import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

FIXTURE = Path(__file__).parent / "fixtures" / "minimal_request.json"


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_optimize_fixture(client):
    payload = json.loads(FIXTURE.read_text())
    r = client.post("/optimize", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["metadata"]["currency"] == "INR"
    assert data["loadShift"][0]["blockShifts"][0]["newStart_t"] == 0


def test_bad_rate_length(client):
    payload = json.loads(FIXTURE.read_text())
    payload["rates"]["rateVector"] = [1.0] * 10
    r = client.post("/optimize", json=payload)
    assert r.status_code == 422  # pydantic validation
