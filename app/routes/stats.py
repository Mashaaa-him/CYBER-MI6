"""
WHAT: GET /api/stats: the numbers the dashboard's stat tiles show.
HOW:  Calls storage.stats, which counts events today (UTC), alerts by severity and status,
      open alerts, and the top five source IPs over the last 24 hours.
LINKS: app/storage.py (stats), app/models.py (Stats), app/deps.py (get_db).
WATCH OUT: "Today" means since 00:00 UTC, not local time. Counts run on every request, so
           the dashboard should poll this endpoint no more than every few seconds.
"""

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from app import storage
from app.deps import get_db
from app.models import Stats

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=Stats)
async def get_stats(db=Depends(get_db)):
    """Dashboard counts: events today and in total, alerts by severity and status, top source IPs."""
    return await run_in_threadpool(storage.stats, db)