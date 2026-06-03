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
    Return hourly trend data for the last N hours.

    The 7-day CSV may have been generated days or weeks ago so its
    data_timestamp values are stale. We filter by ingested_at (always
    recent) but preserve the relative shape from data_timestamp by
    computing an hour offset from the earliest data_timestamp in each
    ingest batch — then rebasing those offsets onto NOW() so the chart
    always shows a rolling window ending at the current time.
    """
    from sqlalchemy import text
    result = db.execute(text(f"""
        WITH ranked AS (
            -- Get all rows from the most recent ingest batch
            -- (identified by the latest ingested_at value)
            SELECT *,
                   MAX(ingested_at) OVER () AS latest_ingest
            FROM wireless_metrics
            WHERE ingested_at >= (
                SELECT MAX(ingested_at) - INTERVAL '5 minutes'
                FROM wireless_metrics
            )
        ),
        rebased AS (
            -- Rebase data_timestamp so that the latest data point
            -- aligns with NOW(), preserving the relative hourly shape
            SELECT
                date_trunc('hour',
                    NOW() - (MAX(data_timestamp) OVER () - data_timestamp)
                ) AS bucket,
                composite_score,
                ap_online_pct,
                client_count
            FROM ranked
        )
        SELECT
            bucket,
            ROUND(AVG(composite_score)::numeric, 1) AS score,
            ROUND(AVG(ap_online_pct)::numeric, 1)   AS ap_online_pct,
            SUM(client_count)                        AS client_count
        FROM rebased
        WHERE bucket >= NOW() - INTERVAL '{hours} hours'
        GROUP BY bucket
        ORDER BY bucket ASC
    """))
    return [dict(row) for row in result.mappings()]
