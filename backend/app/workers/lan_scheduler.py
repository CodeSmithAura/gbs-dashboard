"""
LAN pillar background polling worker.

Runs as an asyncio Task alongside the wireless polling loop.
Fetches data from SolarWinds, normalises, and persists each cycle.

Architecture:
  - One async polling loop per pillar -- independent failure isolation
  - Wireless pillar failure does not affect LAN pillar and vice versa
  - In-memory _lan_state holds the latest processed data for fast API reads
  - All DB writes happen in the sync worker (acceptable -- ~30-50ms per cycle)
  - State is module-level -- shared safely across FastAPI worker threads
    because uvicorn runs single-process with asyncio concurrency

Error handling:
  - Any exception in a cycle sets _lan_state['error'] and logs at ERROR level
  - The cycle always completes -- a bad cycle never crashes the loop
  - Last good state remains in _lan_state -- dashboard shows stale data
    with a visible indicator rather than going blank
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.solarwinds_connector import (
    fetch_nodes,
    fetch_interfaces,
    fetch_alerts,
    test_connectivity,
)
from app.services.lan_normaliser import (
    normalise_nodes,
    build_country_snapshots,
    build_lan_summary,
    build_alert_items,
)
from app.services.lan_db_writer import (
    persist_node_metrics,
    persist_country_snapshots,
    get_lan_thresholds,
    get_lan_alert_limit,
)

logger = logging.getLogger(__name__)

# ------ In-memory state ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_lan_state = {
    "nodes":              [],    # List[LANNodeHealth] -- latest per node
    "country_snapshots":  [],    # List[LANCountrySnapshot] -- latest per country
    "alert_items":        [],    # List[LANAlertItem] -- latest alert feed
    "summary_all":        None,  # LANSummary for scope=all
    "last_ingested_at":   None,  # datetime of last successful cycle
    "sw_connected":       False, # SolarWinds reachability flag
    "error":              None,  # str error message or None
}


def get_lan_state() -> dict:
    return _lan_state


def run_lan_cycle() -> None:
    """
    Execute one full LAN ingest cycle (synchronous).
    Called by the async polling loop -- runs in the event loop thread.
    """
    logger.info("LAN ingest cycle starting...")
    db = SessionLocal()
    try:
        # Load runtime config from DB
        thresholds  = get_lan_thresholds(db)
        alert_limit = get_lan_alert_limit(db)

        # Fetch from SolarWinds
        raw_nodes  = fetch_nodes()
        raw_ifaces = fetch_interfaces()
        raw_alerts = fetch_alerts(limit=alert_limit)

        if not raw_nodes:
            _lan_state["error"] = "SolarWinds: no node data returned"
            logger.warning("LAN ingest: no nodes fetched.")
            return

        # Normalise
        nodes     = normalise_nodes(raw_nodes, raw_ifaces, raw_alerts, thresholds)
        snapshots = build_country_snapshots(nodes, thresholds)
        alerts    = build_alert_items(raw_alerts)
        summary   = build_lan_summary(snapshots, "all", "All", thresholds)

        # Persist to DB (all rows -- supports trend chart history)
        persist_node_metrics(db, nodes)
        persist_country_snapshots(db, snapshots)

        # Update in-memory state
        _lan_state["nodes"]             = nodes
        _lan_state["country_snapshots"] = snapshots
        _lan_state["alert_items"]       = alerts
        _lan_state["summary_all"]       = summary
        _lan_state["last_ingested_at"]  = datetime.now(timezone.utc)
        _lan_state["sw_connected"]      = True
        _lan_state["error"]             = None

        logger.info(
            f"LAN ingest complete: {len(nodes)} nodes, "
            f"{len(snapshots)} countries, "
            f"score={summary.overall_score}, "
            f"status={summary.lan_status}"
        )

    except Exception as exc:
        _lan_state["error"]        = str(exc)
        _lan_state["sw_connected"] = False
        logger.error(f"LAN ingest cycle failed: {exc}", exc_info=True)
    finally:
        db.close()


async def lan_polling_loop() -> None:
    """
    Async polling loop for the LAN pillar.
    Runs indefinitely -- cancelled cleanly on application shutdown.
    Performs a connectivity test on first run before entering the main loop.
    """
    logger.info(
        f"LAN polling loop starting -- "
        f"interval: {settings.SW_POLL_INTERVAL_SECONDS}s"
    )

    # Connectivity test at startup -- log result but do not abort
    connected = test_connectivity()
    _lan_state["sw_connected"] = connected
    if not connected:
        logger.warning(
            "SolarWinds connectivity test failed at startup. "
            "Will retry on first poll cycle. "
            "Check SW_HOST, SW_PORT, SW_USER in .env."
        )

    # First cycle immediately on startup
    run_lan_cycle()

    while True:
        await asyncio.sleep(settings.SW_POLL_INTERVAL_SECONDS)
        run_lan_cycle()
