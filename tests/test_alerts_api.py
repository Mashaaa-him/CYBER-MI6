import threading

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.config import get_settings
from app.main import create_app
from app.models import AlertIn, AlertUpdate
from app.routes.alerts import _apply_transition


@pytest.fixture
def alerts_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "alerts.db"))
    monkeypatch.setenv("API_KEY", "test-key")
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()


def _make_alert(client, **overrides):
    """Insert an alert straight into storage, as the detection engine would."""
    fields = dict(rule="port_scan", severity="high", title="Possible port scan",
                  src_ip="10.0.0.1", evidence_event_ids=[])
    fields.update(overrides)
    return storage.insert_alert(client.app.state.db, AlertIn(**fields))


def test_list_returns_alerts(alerts_client):
    _make_alert(alerts_client)
    rows = alerts_client.get("/api/alerts").json()
    assert len(rows) == 1
    assert rows[0]["rule"] == "port_scan"
    assert rows[0]["status"] == "new"


def test_list_filters_by_severity_and_status(alerts_client):
    _make_alert(alerts_client, severity="high")
    _make_alert(alerts_client, severity="low")
    rows = alerts_client.get("/api/alerts", params={"severity": "low"}).json()
    assert [r["severity"] for r in rows] == ["low"]


def test_unknown_filter_value_is_422(alerts_client):
    assert alerts_client.get("/api/alerts", params={"severity": "urgent"}).status_code == 422


def test_detail_returns_alert_with_evidence_list(alerts_client):
    alert = _make_alert(alerts_client)
    r = alerts_client.get(f"/api/alerts/{alert.id}")
    assert r.status_code == 200
    assert r.json()["evidence"] == []


def test_missing_alert_is_404(alerts_client):
    assert alerts_client.get("/api/alerts/9999").status_code == 404
    assert alerts_client.patch("/api/alerts/9999", json={"status": "resolved"}).status_code == 404


def test_allowed_transition_succeeds(alerts_client):
    alert = _make_alert(alerts_client)
    r = alerts_client.patch(f"/api/alerts/{alert.id}", json={"status": "investigating"})
    assert r.status_code == 200
    assert r.json()["status"] == "investigating"


def test_same_status_is_a_no_op(alerts_client):
    alert = _make_alert(alerts_client)
    r = alerts_client.patch(f"/api/alerts/{alert.id}", json={"status": "new"})
    assert r.status_code == 200


def test_disallowed_transition_is_409_with_allowed_list(alerts_client):
    alert = _make_alert(alerts_client)
    alerts_client.patch(f"/api/alerts/{alert.id}", json={"status": "resolved"})
    r = alerts_client.patch(f"/api/alerts/{alert.id}", json={"status": "new"})
    assert r.status_code == 409
    assert r.json()["detail"]["allowed"] == ["investigating"]


def test_simultaneous_conflicting_changes_only_one_wins(alerts_client):
    """Two threads try to change the same alert to different statuses.

    The first write moves the alert to its new status. The second is then checked
    against that new status, so it becomes a conflict. Exactly one change is written.
    """
    db = alerts_client.app.state.db
    alert = _make_alert(alerts_client)
    outcomes = []
    lock = threading.Lock()

    def attempt(status):
        outcome, _, _ = _apply_transition(db, alert.id, AlertUpdate(status=status))
        with lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=attempt, args=(s,))
               for s in ("resolved", "false_positive")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(outcomes) == ["changed", "conflict"]