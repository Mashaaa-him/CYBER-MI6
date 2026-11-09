import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from app.ratelimit import SlidingWindowLimiter

API_KEY = "test-key"
HEADERS = {"X-API-Key": API_KEY}
EVENT ={
    "type": "network_connection",
    "timestamp": "2026-10-19T09:15:02Z",
    "source": "laptop-sensor-1",
    "src_ip": "192.168.1.25",
    "dst_ip": "192.168.1.1",
    "dst_port": 445,
}


@pytest.fixture
def events_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "events.db"))
    monkeypatch.setenv("API_KEY", API_KEY)
    monkeypatch.setenv("INGEST_MAX_BATCH", "3")
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()
    
    
def test_missing_key_is_rejected(events_client):
    assert events_client.post("/api/events", json=EVENT).status_code == 401
    
    
def test_valid_event_is_stored_and_returned(events_client):
    r = events_client.post("/api/events", json=EVENT, headers=HEADERS)
    assert r.status_code == 202
    assert r.json() == {"accepted": 1}
    
    rows = events_client.get("/api/events").json()
    assert len(rows) == 1
    assert rows[0]["src_ip"] == "192.168.1.25"
    assert rows[0]["id"] >= 1
    
    
def test_batch_is_accepted(events_client):
    r = events_client.post("/api/events", json=[EVENT, EVENT], headers=HEADERS)
    assert r.status_code == 202
    assert r.json() == {"accepted": 2}
    
    
def test_oversized_batch_is_rejected_and_nothing_stored(events_client):
    r = events_client.post("/api/events", json=[EVENT] * 4, headers=HEADERS)
    assert r.status_code  == 413
    assert events_client.get("/api/events").json() == []
    
    
def test_invalid_event_returns_standard_422(events_client):
    r = events_client.post("/api/events", json={"type": "not_a_type"}, headers=HEADERS)
    assert r.status_code == 422
    assert r.json()["error"] == "validation_error"
    
    
def test_payload_like_field_is_rejected(events_client):
    r = events_client.post(
        "/api/events", json={**EVENT, "password": "hunter2"}, headers=HEADERS
    )
    assert r.status_code == 422
    assert events_client.get("/api/events").json() == []
    
    
def test_rate_limit_returns_429(events_client):
    events_client.app.state.ingest_limiter = SlidingWindowLimiter(1, 60)
    assert events_client.post("/api/events", json=EVENT, headers=HEADERS).status_code == 202
    r = events_client.post("/api/events", json=EVENT, headers=HEADERS)
    assert r.status_code == 429
    assert r.headers["Retry-After"] == "60"
    
    
def test_filter_by_src_ip(events_client):
    other = {**EVENT, "src_ip": "10.0.0.9"}
    events_client.post("/api/events", json=[EVENT, other], headers=HEADERS)
    rows = events_client.get("/api/events", params={"src_ip": "10.0.0.9"}).json()
    assert len(rows) == 1
    assert rows[0]["src_ip"] == "10.0.0.9"
    
    
def test_filter_by_type(events_client):
    dns = {
        "type": "dns_query",
        "timestamp": "2026-10-19T09:16:00Z",
        "source": "laptop-sensor-1",
        "src_ip": "192.168.1.25",
        "dns_name": "example.com",
    }
    events_client.post("/api/events", json=[EVENT, dns], headers=HEADERS)
    rows = events_client.get("/api/events", params={"type": "dns_query"}).json()
    assert [r["type"]for r in rows] == ["dns_query"]
    
    
def test_accepted_event_is_broadcast_over_websocket(events_client):
    with events_client.websocket_connect("/ws") as ws:
        events_client.post("/api/events", json=EVENT, headers=HEADERS)
        message = ws.receive_json()
    assert message["kind"] == "event"
    assert message["data"]["src_ip"] == "192.168.1.25"