"""Writes normalised SiteHealth records to MySQL."""

import logging
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import text

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


def get_latest_snapshot(db: Session) -> list:
    """Return the most recent record per site_id.

    MySQL does not support DISTINCT ON --- rewritten as a subquery join.
    """
    result = db.execute(text("""
        SELECT wm.*
        FROM wireless_metrics wm
        INNER JOIN (
            SELECT site_id, MAX(ingested_at) AS max_ingested
            FROM wireless_metrics
            GROUP BY site_id
        ) latest ON wm.site_id = latest.site_id
                     AND wm.ingested_at = latest.max_ingested
        ORDER BY wm.site_id
    """))
    return result.mappings().all()


def get_trend(db: Session, hours: int = 168) -> list:
    """
    Return hourly trend data for the last N hours.

    Rebases data_timestamp offsets onto NOW() so the chart always shows
    a rolling window regardless of when the CSV was generated.

    MySQL differences from PostgreSQL version:
      - DATE_FORMAT replaces date_trunc
      - TIMESTAMPDIFF replaces interval arithmetic
      - INTERVAL syntax uses MySQL format
      - Window functions MAX() OVER () supported in MySQL 8+
    """
    result = db.execute(text(f"""
        WITH ranked AS (
            SELECT *,
                   MAX(ingested_at) OVER () AS max_ingest,
                   MAX(data_timestamp) OVER () AS max_data_ts
            FROM wireless_metrics
            WHERE ingested_at >= (
                SELECT DATE_SUB(MAX(ingested_at), INTERVAL 5 MINUTE)
                FROM wireless_metrics
            )
        ),
        rebased AS (
            SELECT
                DATE_FORMAT(
                    DATE_SUB(
                        NOW(),
                        INTERVAL TIMESTAMPDIFF(SECOND, data_timestamp, max_data_ts) SECOND
                    ),
                    '%Y-%m-%d %H:00:00'
                ) AS bucket,
                composite_score,
                ap_online_pct,
                client_count
            FROM ranked
        )
        SELECT
            bucket,
            ROUND(AVG(composite_score), 1)  AS score,
            ROUND(AVG(ap_online_pct), 1)    AS ap_online_pct,
            SUM(client_count)               AS client_count
        FROM rebased
        WHERE bucket >= DATE_FORMAT(
                DATE_SUB(NOW(), INTERVAL {hours} HOUR),
                '%Y-%m-%d %H:00:00'
              )
        GROUP BY bucket
        ORDER BY bucket ASC
    """))
    return [dict(row) for row in result.mappings()]
