"""
WHAT: HTTP endpoints for alerts: list, detail with evidence, and status changes.
HOW:  GET endpoints read through storage. PATCH checks the allowed status change and
      writes inside one database transaction, so two simultaneous changes can't both pass.
LINKS: app/storage.py (list_alerts, get_alert, get_events_by_ids, update_alert_status),
       app/routes/ws.py (broadcast_alert), app/deps.py.
WATCH OUT: Alerts are created by the detection engine, not by this API. The only write
           here is a status change.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from app import storage
from app.deps import get_db
from app.models import Alert, AlertUpdate, Event
from app.routes.ws import broadcast_alert

router = APIRouter(tags=["alerts"])

Severity = Literal["low", "medium", "high", "critical"]
AlertStatus = Literal["new", "investigating", "resolved", "false_positive"]

# Allowed status changes. Anything else returns 409.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "new": frozenset({"investigating", "resolved", "false_positive"}),
    "investigating": frozenset({"resolved", "false_positive"}),
    "resolved": frozenset({"investigating"}),
    "false_positive": frozenset({"investigating"}),
}


class AlertDetail(Alert):
    """An alert plus the events that triggered it."""

    evidence: list[Event] = []


def _apply_transition(db, alert_id: int, body: AlertUpdate) -> tuple[str, Alert | None, list[str] | None]:
    """Check and write a status change under one write lock.

    Returns (outcome, alert, allowed):
      ("missing", None, None)       the alert doesn't exist
      ("unchanged", alert, None)    already in the requested status
      ("conflict", alert, allowed)  the change isn't allowed from the current status
      ("changed", alert, None)      the change was written
    """
    with db.transaction():
        current = storage.get_alert(db, alert_id)
        if current is None:
            return ("missing", None, None)
        if body.status == current.status:
            return ("unchanged", current, None)
        allowed = sorted(ALLOWED_TRANSITIONS.get(current.status, frozenset()))
        if body.status not in allowed:
            return ("conflict", current, allowed)
        updated = storage.update_alert_status(db, alert_id, body)
        if updated is None:
            return ("missing", None, None)
        return ("changed", updated, None)


@router.get("/alerts", response_model=list[Alert])
async def list_alerts_route(
    severity: Severity | None = None,
    status: AlertStatus | None = None,
    rule: str | None = Query(default=None, max_length=64),
    src_ip: str | None = Query(default=None, max_length=45),
    limit: int = Query(default=100, ge=1, le=500),
    db=Depends(get_db),
):
    """Alerts, newest first. Optional filters: severity, status, rule, src_ip, limit."""
    return await run_in_threadpool(
        lambda: storage.list_alerts(
            db, severity=severity, status=status, rule=rule, src_ip=src_ip, limit=limit
        )
    )


@router.get("/alerts/{alert_id}", response_model=AlertDetail)
async def get_alert_route(alert_id: int, db=Depends(get_db)):
    """One alert with its evidence events. Evidence removed by retention is omitted."""

    def load():
        alert = storage.get_alert(db, alert_id)
        if alert is None:
            return None
        evidence = storage.get_events_by_ids(db, alert.evidence_event_ids)
        return AlertDetail(**alert.model_dump(), evidence=evidence)

    detail = await run_in_threadpool(load)
    if detail is None:
        raise HTTPException(404, "Alert not found")
    return detail


@router.patch("/alerts/{alert_id}", response_model=Alert)
async def update_alert_route(alert_id: int, body: AlertUpdate, db=Depends(get_db)):
    """Change an alert's status. 404 if missing, 409 if the change isn't allowed."""
    outcome, alert, allowed = await run_in_threadpool(_apply_transition, db, alert_id, body)
    if outcome == "missing":
        raise HTTPException(404, "Alert not found")
    if outcome == "conflict":
        raise HTTPException(
            409,
            detail={
                "message": f"Cannot change status from '{alert.status}' to '{body.status}'",
                "allowed": allowed,
            },
        )
    if outcome == "changed":  # only broadcast real changes
        await broadcast_alert(alert.model_dump(mode="json"))
    return alert