"""
WHAT: HTTP endpoints for events: POST /api/events (ingest) and GET /api/events (query).
HOW:  POST checks the API key, the per-IP rate limit and the batch size, validates each
      event with models.EventIn, stores the batch atomically, then broadcasts each stored
      event over WebSocket. GET returns recent events with optional filters.
LINKS: app/storage.py (insert_events, list_events), app/models.py, app/security.py,
       app/deps.py, app/routes/ws.py (broadcast_event).
WATCH OUT: Alert detection is not called from here yet. Allan's engine hooks in after
           insert_events returns.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

from app import storage
from app.config import Settings, get_settings
from app.deps import get_db, get_ingest_limiter
from app.models import Event, EventIn, EventType
from app.ratelimit import SlidingWindowLimiter
from app.routes.ws import broadcast_event
from app.security import require_api_key

router = APIRouter(tags=["events"])


def enforce_rate_limit(
    request: Request,
    limiter: SlidingWindowLimiter = Depends(get_ingest_limiter),
) -> None:
    """Limit ingestion per client IP. Returns 429 with Retry-After when exceeded."""
    client = request.client.host if request.client else "unknown"
    if not limiter.allow(client):
        raise HTTPException(
            429, "Rate limit exceeded", headers={"Retry-After": str(limiter.window)}
        )


@router.post(
    "/events",
    status_code=202,
    dependencies=[Depends(require_api_key), Depends(enforce_rate_limit)],
)
async def ingest_events(
    payload: EventIn | list[EventIn],
    db=Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Accept one event, or a list of events, from a sensor or application."""
    batch = payload if isinstance(payload, list) else [payload]
    if not batch:
        raise HTTPException(422, "Batch must contain at least one event")
    if len(batch) > settings.ingest_max_batch:
        raise HTTPException(
            413, f"Batch too large: {len(batch)} events (max {settings.ingest_max_batch})"
        )

    stored = await run_in_threadpool(storage.insert_events, db, batch)
    for event in stored:
        await broadcast_event(event.model_dump(mode="json"))
    return {"accepted": len(stored)}


@router.get("/events", response_model=list[Event])
async def list_events_route(
    type: EventType | None = None,
    src_ip: str | None = Query(default=None, max_length=45),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db=Depends(get_db),
):
    """Recent events, newest first. Optional filters: type, src_ip, from, to, limit."""
    return await run_in_threadpool(
        lambda: storage.list_events(
            db, type=type, src_ip=src_ip, since=from_, until=to, limit=limit
        )
    )