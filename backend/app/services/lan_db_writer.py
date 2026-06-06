"""
LAN pillar database writer and reader.

Responsibilities:
  - Persist LANNodeHealth records to lan_metrics (bulk insert)
  - Persist LANCountrySnapshot records to lan_country_snapshots (bulk insert)
  - Read latest country snapshots for dashboard API (global view)
  - Read latest node records for country/scope drill-down
  - Read country groups from sw_country_groups for combo box
  - Read distinct country list with node counts
  - Read trend data (hourly aggregated) for trend chart
  - Load LAN thresholds from dashboard_config

Design:
  - All writes use bulk_save_objects for efficiency
  - All reads use parameterised queries -- no string interpolation on user input
  - Scope resolution (all / group / country) centralised here
  - Country group lookup validates slug against DB -- no raw user input in SQL
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.lan_schemas import (
    LANNodeHealth,
    LANCountrySnapshot,
    LANCountryGroup,
    LANCountryInfo,
    LANTrendPoint,
)

logger = logging.getLogger(__name__)


# ------ ORM-free bulk insert using SQLAlchemy core ------------------------------------------------------------------------------------------------
# Using core INSERT for bulk efficiency -- avoids ORM overhead on 700 rows.
# All values come from validated Pydantic models -- no raw user input.

def persist_node_metrics(db: Session, nodes: List[LANNodeHealth]) -> int:
    """Bulk insert LANNodeHealth records into lan_metrics."""
    if not nodes:
        return 0
    rows = [
        {
            "ingested_at":          n.ingested_at or datetime.now(timezone.utc),
            "node_id":              n.node_id,
            "node_name":            n.node_name,
            "ip_address":           n.ip_address,
            "country":              n.country,
            "status":               n.status,
            "avg_response_time_ms": n.avg_response_time_ms,
            "percent_loss":         n.percent_loss,
            "severity":             n.severity,
            "alert_count":          n.alert_count,
            "alert_severity":       n.alert_severity,
            "alert_description":    n.alert_description or "",
            "max_in_util":          n.max_in_util,
            "max_out_util":         n.max_out_util,
            "avg_in_util":          n.avg_in_util,
            "avg_out_util":         n.avg_out_util,
            "interface_count":      n.interface_count,
            "composite_score":      n.composite_score,
            "lan_status":           n.lan_status,
        }
        for n in nodes
    ]
    db.execute(
        text("""
            INSERT INTO dbo.lan_metrics (
                ingested_at, node_id, node_name, ip_address, country,
                status, avg_response_time_ms, percent_loss, severity,
                alert_count, alert_severity, alert_description,
                max_in_util, max_out_util, avg_in_util, avg_out_util,
                interface_count, composite_score, lan_status
            ) VALUES (
                :ingested_at, :node_id, :node_name, :ip_address, :country,
                :status, :avg_response_time_ms, :percent_loss, :severity,
                :alert_count, :alert_severity, :alert_description,
                :max_in_util, :max_out_util, :avg_in_util, :avg_out_util,
                :interface_count, :composite_score, :lan_status
            )
        """),
        rows,
    )
    db.commit()
    logger.info(f"LAN DB: persisted {len(rows)} node metric rows.")
    return len(rows)


def persist_country_snapshots(
    db: Session, snapshots: List[LANCountrySnapshot]
) -> int:
    """Bulk insert LANCountrySnapshot records into lan_country_snapshots."""
    if not snapshots:
        return 0
    rows = [
        {
            "ingested_at":     s.ingested_at or datetime.now(timezone.utc),
            "country":         s.country,
            "node_count":      s.node_count,
            "nodes_up":        s.nodes_up,
            "nodes_warning":   s.nodes_warning,
            "nodes_down":      s.nodes_down,
            "avg_score":       s.avg_score,
            "weighted_score":  s.weighted_score,
            "avg_loss_pct":    s.avg_loss_pct,
            "avg_response_ms": s.avg_response_ms,
            "alert_count":     s.alert_count,
            "critical_count":  s.critical_count,
            "lan_status":      s.lan_status,
        }
        for s in snapshots
    ]
    db.execute(
        text("""
            INSERT INTO dbo.lan_country_snapshots (
                ingested_at, country, node_count, nodes_up, nodes_warning,
                nodes_down, avg_score, weighted_score, avg_loss_pct,
                avg_response_ms, alert_count, critical_count, lan_status
            ) VALUES (
                :ingested_at, :country, :node_count, :nodes_up, :nodes_warning,
                :nodes_down, :avg_score, :weighted_score, :avg_loss_pct,
                :avg_response_ms, :alert_count, :critical_count, :lan_status
            )
        """),
        rows,
    )
    db.commit()
    logger.info(f"LAN DB: persisted {len(rows)} country snapshot rows.")
    return len(rows)


# ------ Reads ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def get_latest_country_snapshots(db: Session) -> List[dict]:
    """
    Return the most recent country snapshot per country.
    Used for global view (all countries) -- returns ~30 rows.
    """
    result = db.execute(text("""
        SELECT cs.*
        FROM dbo.lan_country_snapshots cs
        INNER JOIN (
            SELECT country, MAX(ingested_at) AS max_ia
            FROM dbo.lan_country_snapshots
            GROUP BY country
        ) latest
            ON  cs.country    = latest.country
            AND cs.ingested_at = latest.max_ia
        ORDER BY cs.country
    """))
    return [dict(row) for row in result.mappings()]


def get_latest_nodes_by_countries(
    db: Session, countries: List[str]
) -> List[dict]:
    """
    Return latest node records filtered to a list of countries.
    countries: validated list from scope resolution -- safe for parameterisation.
    Uses IN clause with named parameters -- no string interpolation.
    """
    if not countries:
        return []

    # Build safe parameterised IN clause
    params = {f"c{i}": c for i, c in enumerate(countries)}
    placeholders = ", ".join(f":c{i}" for i in range(len(countries)))

    result = db.execute(
        text(f"""
            SELECT lm.*
            FROM dbo.lan_metrics lm
            INNER JOIN (
                SELECT node_id, MAX(ingested_at) AS max_ia
                FROM dbo.lan_metrics
                WHERE country IN ({placeholders})
                GROUP BY node_id
            ) latest
                ON  lm.node_id    = latest.node_id
                AND lm.ingested_at = latest.max_ia
            WHERE lm.country IN ({placeholders})
            ORDER BY lm.country, lm.node_name
        """),
        {**params, **{f"c{i}": c for i, c in enumerate(countries)}},
    )
    return [dict(row) for row in result.mappings()]


def get_country_groups(db: Session) -> List[LANCountryGroup]:
    """
    Return all active country groups from sw_country_groups.
    Used to populate the combo box groups section.
    """
    result = db.execute(text("""
        SELECT group_id, group_name, group_slug, countries, sort_order, is_active
        FROM dbo.sw_country_groups
        WHERE is_active = 1
        ORDER BY sort_order, group_name
    """))
    groups = []
    for row in result.mappings():
        raw_countries = row["countries"] or ""
        country_list = [
            c.strip() for c in raw_countries.split(",")
            if c.strip()
        ]
        groups.append(LANCountryGroup(
            group_id=row["group_id"],
            group_name=row["group_name"],
            group_slug=row["group_slug"],
            countries=country_list,
            sort_order=row["sort_order"],
            is_active=bool(row["is_active"]),
        ))
    return groups


def get_distinct_countries(db: Session) -> List[LANCountryInfo]:
    """
    Return distinct countries and node counts from latest snapshots.
    Used to populate the combo box countries section.
    """
    result = db.execute(text("""
        SELECT country, node_count
        FROM (
            SELECT
                cs.country,
                cs.node_count,
                ROW_NUMBER() OVER (
                    PARTITION BY cs.country
                    ORDER BY cs.ingested_at DESC
                ) AS rn
            FROM dbo.lan_country_snapshots cs
        ) ranked
        WHERE rn = 1
        ORDER BY country
    """))
    return [
        LANCountryInfo(country=row["country"], node_count=row["node_count"])
        for row in result.mappings()
    ]


def resolve_scope_countries(
    db: Session, scope: str
) -> tuple:
    """
    Resolve a scope string to a (countries list, scope_label) tuple.

    scope formats:
      'all'                 -> all countries, label='All'
      'group:<slug>'        -> countries from sw_country_groups, label=group_name
      'country:<name>'      -> single country, label=country name

    Returns (countries: List[str] | None, label: str)
    None countries means no country filter (all nodes).

    Security: group slug and country name are validated:
      - slug: looked up by exact match in DB (parameterised)
      - country: matched against known countries from DB (parameterised)
    """
    if not scope or scope == "all":
        return None, "All"

    if scope.startswith("group:"):
        slug = scope[6:].strip()
        # Validate slug via DB lookup -- slug value never interpolated
        result = db.execute(
            text("""
                SELECT group_name, countries
                FROM dbo.sw_country_groups
                WHERE group_slug = :slug AND is_active = 1
            """),
            {"slug": slug},
        ).mappings().first()

        if not result:
            logger.warning(f"LAN scope: unknown group slug '{slug}' -- falling back to all")
            return None, "All"

        raw = result["countries"] or ""
        countries = [c.strip() for c in raw.split(",") if c.strip()]
        label = result["group_name"]
        # Empty countries list in 'All' group means no filter
        return (countries if countries else None), label

    if scope.startswith("country:"):
        country_name = scope[8:].strip()
        # Validate country exists in our data -- prevents arbitrary WHERE injection
        result = db.execute(
            text("""
                SELECT TOP 1 country FROM dbo.lan_country_snapshots
                WHERE country = :country
            """),
            {"country": country_name},
        ).mappings().first()

        if not result:
            logger.warning(
                f"LAN scope: unknown country '{country_name}' -- falling back to all"
            )
            return None, "All"

        return [result["country"]], result["country"]

    logger.warning(f"LAN scope: unrecognised format '{scope}' -- falling back to all")
    return None, "All"


def get_lan_trend(
    db: Session,
    countries: Optional[List[str]],
    hours: int = 168,
) -> List[LANTrendPoint]:
    """
    Return hourly trend data for the LAN pillar.
    Aggregates country snapshots by hour -- avoids reading 700-row lan_metrics
    for every trend call.

    countries: None = all, list = filter to those countries.
    hours: rolling window size (default 7 days = 168 hours).

    Uses the same rebase strategy as the wireless trend query:
    Groups by ingested_at hour -- all snapshots share the same ingested_at
    per cycle so grouping is natural.
    """
    safe_hours = max(1, min(int(hours), 720))  # cap at 30 days

    if countries:
        params = {f"c{i}": c for i, c in enumerate(countries)}
        placeholders = ", ".join(f":c{i}" for i in range(len(countries)))
        where_clause = f"AND cs.country IN ({placeholders})"
    else:
        params = {}
        where_clause = ""

    result = db.execute(
        text(f"""
            SELECT
                DATEADD(
                    HOUR,
                    DATEDIFF(HOUR, 0, cs.ingested_at),
                    0
                )                                AS bucket,
                ROUND(AVG(cs.weighted_score), 1) AS avg_score,
                ROUND(
                    CAST(SUM(cs.nodes_up) AS FLOAT)
                    / NULLIF(SUM(cs.node_count), 0) * 100,
                    1
                )                                AS nodes_up_pct,
                ROUND(AVG(cs.avg_loss_pct), 2)   AS avg_loss_pct
            FROM dbo.lan_country_snapshots cs
            WHERE cs.ingested_at >= DATEADD(HOUR, -{safe_hours}, GETUTCDATE())
            {where_clause}
            GROUP BY DATEADD(HOUR, DATEDIFF(HOUR, 0, cs.ingested_at), 0)
            ORDER BY bucket ASC
        """),
        params,
    )
    return [
        LANTrendPoint(
            bucket=str(row["bucket"]),
            avg_score=float(row["avg_score"] or 0),
            nodes_up_pct=float(row["nodes_up_pct"] or 0),
            avg_loss_pct=float(row["avg_loss_pct"] or 0),
        )
        for row in result.mappings()
    ]


def get_lan_thresholds(db: Session) -> Dict[str, float]:
    """
    Load LAN health thresholds from dashboard_config.
    Falls back to normaliser defaults if keys missing.
    """
    result = db.execute(text("""
        SELECT [key], [value]
        FROM dbo.dashboard_config
        WHERE [key] IN (
            'lan_score_green', 'lan_score_amber',
            'lan_avail_green', 'lan_avail_amber',
            'lan_loss_green',  'lan_loss_amber'
        )
    """))
    thresholds = {}
    for row in result.mappings():
        try:
            thresholds[row["key"]] = float(row["value"])
        except (TypeError, ValueError):
            pass
    return thresholds


def get_lan_alert_limit(db: Session) -> int:
    """Load the alert fetch limit from dashboard_config."""
    result = db.execute(text("""
        SELECT [value] FROM dbo.dashboard_config
        WHERE [key] = 'lan_alert_limit'
    """)).mappings().first()
    try:
        return max(1, min(int(result["value"]), 500)) if result else 100
    except (TypeError, ValueError):
        return 100
