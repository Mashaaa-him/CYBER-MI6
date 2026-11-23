import pytest
from fastapi.testclient import TestClient

from app import storage
from app.config import get_settings
from app.main import create_app
from app.models import AlertIn
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

HEADERS = {"X-API-Key": "test-key"}
EVENT = {
    "type": "network_connection",
    "source": "laptop-sensor-1",
    "src_ip": "192.168.1.25",
    "dst_ip": "192.168.1.1",
    "dst_port": 445,
}


@pytest.fixture
def stats_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "stats.db"))
    monkeypatch.setenv("API_KEY", "test-key")
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        yield client 
    get_settings.cache_clear()
    
    
def test_empty_database_returns_zeros(stats_client):
    body = stats_client.get("/api/stats").json()
    assert body["events_total"] == 0
    assert body["alerts_total"] == 0
    assert body["open_alerts"] == 0
    assert body["top_source_ips"] == []
    assert set(body["alerts_by_severity"]) == {"low", "medium", "high", "critical"}
    
    
def test_counts_events_and_top_sources(stats_client):
    now = _now_iso()
    stats_client.post(
        "/api/events", json=[{**EVENT, "timestamp": now}, {**EVENT, "timestamp": now}], headers=HEADERS
    )
    other = {**EVENT, "src_ip": "10.0.0.9", "timestamp": now}
    stats_client.post("/api/events", json=other, headers=HEADERS)

    body = stats_client.get("/api/stats").json()
    assert body["events_total"] == 3
    assert body["top_source_ips"][0] == {"src_ip": "192.168.1.25", "count": 2}
    
    
def test_counts_alerts_by_severity_and_open_status(stats_client):
    db = stats_client.app.state.db
    storage.insert_alert(db, AlertIn(rule="port_scan", severity="high", title="a", src_ip="10.0.0.1"))
    storage.insert_alert(db, AlertIn(rule="dns_anomaly", severity="low", title="b", src_ip="10.0.0.2"))
    
    body = stats_client.get("/api/stats").json()
    assert body["alerts_total"] == 2
    assert body["open_alerts"] == 2
    assert body["alerts_by_severity"]["high"] == 1
    assert body["alerts_by_severity"]["low"] == 1
    
    
def test_resolved_alerts_are_not_open(stats_client):
    db = stats_client.app.state.db
    alert = storage.insert_alert(
        db, AlertIn(rule="port_scan", severity="high", title="a", src_ip="10.0.0.1")
    )
    stats_client.patch(f"/api/alerts/{alert.id}", json={"status": "investigating"})
    stats_client.patch(f"/api/alerts/{alert.id}", json={"status": "resolved"})
    
    body = stats_client.get("/api/stats").json()
    assert body["alerts_total"] == 1
    assert body["open_alerts"] == 0
    assert body["alerts_by_status"]["resolved"] == 1