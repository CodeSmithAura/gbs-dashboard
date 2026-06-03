"""
Background polling worker -- asyncio-native, no APScheduler.
Runs inside uvicorn's event loop; survives hot-reload correctly.
Phase 2: replace polling_loop with an Apache Airflow DAG.
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.ingestion import get_connector
from app.services.normaliser import normalise_records, build_summary, deduplicate_latest
from app.services.db_writer import persist_sites

logger = logging.getLogger(__name__)

_state = {
    "last_ingested_at": None,
    "sites": [],
    "summary": None,
    "error": None,
}


def get_state() -> dict:
    return _state


def run_ingestion_cycle():
    """Execute one full ingest -> normalise -> persist cycle."""
    logger.info("Ingestion cycle starting...")
    try:
        connector = get_connector()
        raw = connector.fetch()

        if not raw:
            _state["error"] = "No records returned from data source"
            logger.warning("Ingestion cycle: no records fetched.")
            return

        # ── Persist ALL rows to DB (for trend chart history) ─────────────────
        # normalise without dedup so every timestamp in the CSV gets a DB row
        all_sites = normalise_records(raw, deduplicate=False)

        db = SessionLocal()
        try:
            persist_sites(db, all_sites)
        finally:
            db.close()

        # ── Deduplicate to latest per site for dashboard display ──────────────
        # _state['sites'] must have exactly 1 row per site (current status)
        latest_raw   = deduplicate_latest(raw)
        latest_sites = normalise_records(latest_raw, deduplicate=False)

        summary = build_summary(
            latest_sites,
            data_source_type=settings.DATA_SOURCE_TYPE,
            data_source_path=settings.DATA_SOURCE_PATH,
            last_ingested_at=datetime.now(timezone.utc),
        )

        _state["sites"]           = latest_sites
        _state["summary"]         = summary
        _state["last_ingested_at"] = datetime.now(timezone.utc)
        _state["error"]           = None

        logger.info(
            f"Ingestion cycle complete: persisted {len(all_sites)} rows, "
            f"dashboard shows {len(latest_sites)} sites, "
            f"overall score={summary.overall_score}, status={summary.status}"
        )

    except Exception as e:
        _state["error"] = str(e)
        logger.error(f"Ingestion cycle failed: {e}", exc_info=True)


async def polling_loop():
    """Async loop -- fires every POLL_INTERVAL_SECONDS."""
    logger.info(f"Polling loop started -- interval: {settings.POLL_INTERVAL_SECONDS}s")
    run_ingestion_cycle()
    while True:
        await asyncio.sleep(settings.POLL_INTERVAL_SECONDS)
        run_ingestion_cycle()
