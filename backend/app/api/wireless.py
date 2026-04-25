from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.schemas import WirelessSummary, SiteHealth, AlertItem, TrendPoint
from app.services.normaliser import extract_alerts
from app.services.db_writer import get_trend
from app.workers.scheduler import get_state

router = APIRouter(prefix="/api/v1/wireless", tags=["Wireless"])


def _require_state():
    state = get_state()
    if state["summary"] is None:
        raise HTTPException(status_code=503, detail="Data not yet available — ingestion pending")
    return state


@router.get("/summary", response_model=WirelessSummary)
def get_summary():
    """Overall wireless health summary — headline KPIs for the dashboard banner."""
    return _require_state()["summary"]


@router.get("/sites", response_model=List[SiteHealth])
def get_sites():
    """Per-site health breakdown — one row per site."""
    return _require_state()["sites"]


@router.get("/alerts", response_model=List[AlertItem])
def get_alerts():
    """Active alert feed, sorted by severity (critical first)."""
    state = _require_state()
    return extract_alerts(state["sites"])


@router.get("/trend", response_model=List[TrendPoint])
def get_trend_data(hours: int = 168, db: Session = Depends(get_db)):
    """7-day (default) hourly trend — composite score, AP %, client count."""
    rows = get_trend(db, hours=hours)
    return [
        TrendPoint(
            timestamp=r["bucket"],
            score=float(r["score"] or 0),
            ap_online_pct=float(r["ap_online_pct"] or 0),
            client_count=int(r["client_count"] or 0),
        )
        for r in rows
    ]


@router.post("/ingest/trigger")
def trigger_ingest():
    """Manually trigger an ingestion cycle (dev/demo use)."""
    from app.workers.scheduler import run_ingestion_cycle
    run_ingestion_cycle()
    state = get_state()
    if state["error"]:
        raise HTTPException(status_code=500, detail=state["error"])
    return {"status": "ok", "last_ingested_at": state["last_ingested_at"]}
