"""Writes normalised SiteHealth records to TimescaleDB."""

import logging
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from app.models.orm import WirelessMetric
from app.models.schemas import SiteHealth

logger = logging.getLogger(__name__)


def persist_sites(db: Session, sites: List[SiteHealth]) -> int:
    """Insert a batch of normalised site records. Returns count written."""
    if not sites:
        return 0
    now = datetime.now(timezone.utc)
    rows = [
        WirelessMetric(
            ingested_at=now,
            site_id=s.site_id,
            site_name=s.site_name,
            data_timestamp=s.timestamp,
            composite_score=s.composite_score,
            site_health_score=s.site_health_score,
            ap_total=s.ap_total,
            ap_online=s.ap_online,
            ap_offline=s.ap_offline,
            ap_online_pct=s.ap_online_pct,
            client_count=s.client_count,
            auth_failures_1h=s.auth_failures_1h,
            active_alerts=s.active_alerts,
            alert_severity=s.alert_severity,
            alert_description=s.alert_description,
            ssid_count=s.ssid_count,
            uplink_quality=s.uplink_quality,
            status=s.status,
        )
        for s in sites
    ]
    db.bulk_save_objects(rows)
    db.commit()
    logger.info(f"DB writer: persisted {len(rows)} site records.")
    return len(rows)


def get_latest_snapshot(db: Session) -> List[WirelessMetric]:
    """Return the most recent record per site_id."""
    from sqlalchemy import text
    result = db.execute(text("""
        SELECT DISTINCT ON (site_id) *
        FROM wireless_metrics
        ORDER BY site_id, ingested_at DESC
    """))
    return result.mappings().all()


def get_trend(db: Session, hours: int = 168) -> list:
    """
    Return hourly average scores for the last N hours.

    Groups by data_timestamp (the time in the CSV/API record) rather than
    ingested_at. This means a 7-day CSV loaded in a single ingest cycle
    correctly produces 168 hourly data points instead of 1.
    """
    from sqlalchemy import text
    result = db.execute(text(f"""
        SELECT
            date_trunc('hour', data_timestamp) AS bucket,
            ROUND(AVG(composite_score)::numeric, 1) AS score,
            ROUND(AVG(ap_online_pct)::numeric, 1)   AS ap_online_pct,
            SUM(client_count)                        AS client_count
        FROM wireless_metrics
        WHERE data_timestamp >= NOW() - INTERVAL '{hours} hours'
        GROUP BY bucket
        ORDER BY bucket ASC
    """))
    return [dict(row) for row in result.mappings()]
