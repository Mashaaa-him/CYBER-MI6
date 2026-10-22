import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import open_database  # noqa: E402
from app.models import AlertIn, EventIn  # noqa: E402

NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)  # fixed, safely in the past (models reject future timestamps)


@pytest.fixture
def db(tmp_path):
    database = open_database(tmp_path / "test.db")
    yield database
    database.close()


def syn(ip="10.0.0.5", port=80, at=NOW, dst="10.0.0.1", source="sensor-1"):
    return EventIn(type="network_connection", timestamp=at, source=source,
                   src_ip=ip, dst_ip=dst, dst_port=port)


def dns(name="example.com", ip="10.0.0.5", at=NOW):
    return EventIn(type="dns_query", timestamp=at, source="sensor-1", src_ip=ip, dns_name=name)


def auth(user="admin", ip="10.0.0.9", at=NOW):
    return EventIn(type="auth_failure", timestamp=at, source="webapp", src_ip=ip, username=user)


def http(path="/", ip="10.0.0.9", at=NOW, status=200):
    return EventIn(type="http_request", timestamp=at, source="webapp", src_ip=ip,
                   http_method="get", http_path=path, http_status=status)


def alert(rule="port_scan", ip="10.0.0.5", ids=(1, 2, 3), severity="medium"):
    return AlertIn(rule=rule, severity=severity, title=f"Possible {rule} from {ip}",
                   src_ip=ip, evidence_event_ids=list(ids),
                   explanation={"threshold": 20, "window_seconds": 30, "observed": len(ids)})


def ago(seconds=0, **kw):
    return NOW - timedelta(seconds=seconds, **kw)
