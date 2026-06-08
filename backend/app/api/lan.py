"""
LAN Health pillar REST API endpoints.

All endpoints are scope-aware via the `scope` query parameter:
  scope=all                 global view (default)
  scope=group:<slug>        region group defined in sw_country_groups
  scope=country:<name>      single country

Scope resolution is centralised in lan_db_writer.resolve_scope_countries.
Country/group names are validated against the database -- no raw user
input is interpolated into SQL.

Response strategy:
  - /summary and /sites for scope=all -> served from _lan_state (in-memory, <1ms)
  - /sites for scope=group or country  -> DB query (scoped, fast with index)
  - /trend                             -> DB query (time-series aggregation)
  - /groups and /countries             -> DB query (small, cached at client)
  - /alerts                            -> served from _lan_state (filtered in Python)

HTTP error codes:
  503 -- data not yet available (first cycle not complete)
  400 -- invalid scope parameter format
  500 -- unexpected server error (logged, not exposed to client)
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.workers.lan_scheduler import get_lan_state
from app.services.lan_normaliser import build_lan_summary, build_alert_items
from app.services.lan_db_writer import (
    get_latest_country_snapshots,
    get_latest_nodes_by_countries,
    get_country_groups,
    get_distinct_countries,
    resolve_scope_countries,
    get_lan_trend,
    get_lan_thresholds,
)
from app.core.security import sanitise_scope_part
from app.models.lan_schemas import (
    LANSummary,
    LANCountrySnapshot,
    LANNodeHealth,
    LANCountryGroup,
    LANCountryInfo,
    LANAlertItem,
    LANTrendPoint,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/lan", tags=["LAN Health"])

# ------ Guards ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def _require_lan_state():
    """Raise 503 if the first LAN ingest cycle has not yet completed."""
    state = get_lan_state()
    if state["summary_all"] is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "LAN data not yet available. "
                "First SolarWinds ingest cycle is still running. "
                "Please wait 30-60 seconds and retry."
            ),
        )
    return state


def _validate_scope(scope: str) -> str:
    """
    Validate and sanitise scope parameter.
    Permitted formats: 'all', 'group:<slug>', 'country:<name>'

    Security:
      - Format validated before reaching DB resolution
      - Value part (after prefix) sanitised via security.sanitise_scope_part
      - DB resolution always uses parameterised queries (defence in depth)
    """
    if not scope:
        return "all"
    if scope == "all":
        return scope
    if scope.startswith("group:"):
        value = sanitise_scope_part(scope[6:])
        if not value:
            raise HTTPException(
                status_code=400,
                detail="Invalid group identifier in scope parameter."
            )
        return f"group:{value}"
    if scope.startswith("country:"):
        value = sanitise_scope_part(scope[8:])
        if not value:
            raise HTTPException(
                status_code=400,
                detail="Invalid country name in scope parameter."
            )
        return f"country:{value}"
    raise HTTPException(
        status_code=400,
        detail=(
            "Invalid scope format. "
            "Use 'all', 'group:<slug>', or 'country:<name>'."
        ),
    )


# ------ Endpoints ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

@router.get("/summary", response_model=LANSummary)
def lan_summary(
    scope: str = Query(default="all", description="Scope: all | group:<slug> | country:<name>"),
    db: Session = Depends(get_db),
):
    """
    Overall LAN health score and KPIs for the selected scope.
    For scope=all: served from in-memory state (<1ms).
    For group/country scopes: aggregated from DB country snapshots.
    """
    scope = _validate_scope(scope)
    state = _require_lan_state()

    if scope == "all":
        return state["summary_all"]

    countries, label = resolve_scope_countries(db, scope)
    thresholds = get_lan_thresholds(db)

    if countries:
        snapshots_raw = get_latest_country_snapshots(db)
        filtered = [
            s for s in snapshots_raw
            if s["country"] in countries
        ]
    else:
        filtered = get_latest_country_snapshots(db)

    # Reconstruct LANCountrySnapshot objects for build_lan_summary
    from app.models.lan_schemas import LANCountrySnapshot
    snapshot_objs = [LANCountrySnapshot(**s) for s in filtered]
    return build_lan_summary(snapshot_objs, scope, label, thresholds)


@router.get("/sites")
def lan_sites(
    scope: str = Query(default="all"),
    db: Session = Depends(get_db),
):
    """
    Site/country table data for the selected scope.

    scope=all           -> list of LANCountrySnapshot (30 rows, global view)
    scope=group/country -> list of LANNodeHealth (node-level, filtered)

    Returns different schemas depending on scope -- frontend handles both.
    Response includes a 'view_type' field: 'country' or 'node'.
    """
    scope = _validate_scope(scope)
    _require_lan_state()

    if scope == "all":
        rows = get_latest_country_snapshots(db)
        if not rows:
            # Snapshots not yet written -- fall back to in-memory state
            state   = get_lan_state()
            snaps   = state.get("country_snapshots", [])
            return {
                "view_type": "country",
                "data": [s.model_dump() for s in snaps]
            }
        return {"view_type": "country", "data": rows}

    countries, label = resolve_scope_countries(db, scope)
    if countries:
        nodes = get_latest_nodes_by_countries(db, countries)
    else:
        # 'All' group with empty countries -- return country view
        rows = get_latest_country_snapshots(db)
        return {"view_type": "country", "data": rows}

    return {"view_type": "node", "scope_label": label, "data": nodes}


@router.get("/alerts", response_model=List[LANAlertItem])
def lan_alerts(
    scope: str = Query(default="all"),
    db: Session = Depends(get_db),
):
    """
    Active alert feed for the selected scope.
    Alerts are served from in-memory state and filtered by country in Python.
    No additional DB query required.
    """
    scope = _validate_scope(scope)
    state = _require_lan_state()
    alerts: List[LANAlertItem] = state["alert_items"]

    if scope == "all":
        return alerts

    countries, _ = resolve_scope_countries(db, scope)
    if countries is None:
        return alerts

    # Filter alerts whose node appears in the scoped country set
    # node_name -> country lookup from in-memory node state
    node_country: dict = {
        n.node_name: n.country
        for n in state["nodes"]
    }
    return [
        a for a in alerts
        if node_country.get(a.related_node_id, "") in countries
    ]


@router.get("/trend", response_model=List[LANTrendPoint])
def lan_trend(
    scope: str   = Query(default="all"),
    hours: int   = Query(default=168, ge=1, le=720),
    db: Session  = Depends(get_db),
):
    """
    Hourly trend data for the trend chart.
    hours: rolling window size (default 168 = 7 days, max 720 = 30 days).
    """
    scope = _validate_scope(scope)
    _require_lan_state()

    if scope == "all":
        countries = None
    else:
        countries, _ = resolve_scope_countries(db, scope)

    return get_lan_trend(db, countries, hours)


@router.get("/groups", response_model=List[LANCountryGroup])
def lan_groups(db: Session = Depends(get_db)):
    """
    Country group definitions for the combo box groups section.
    Reads from sw_country_groups -- reflects any DB changes immediately.
    """
    return get_country_groups(db)


@router.get("/countries", response_model=List[LANCountryInfo])
def lan_countries(db: Session = Depends(get_db)):
    """
    Distinct countries and node counts for the combo box countries section.
    """
    return get_distinct_countries(db)


@router.get("/status")
def lan_status():
    """
    LAN pillar health -- SolarWinds connectivity, last ingest, error state.
    Used by the dashboard footer data source indicator.
    """
    state = get_lan_state()
    return {
        "sw_connected":     state["sw_connected"],
        "last_ingested_at": state["last_ingested_at"],
        "error":            state["error"],
        "node_count":       len(state["nodes"]),
        "country_count":    len(state["country_snapshots"]),
    }
