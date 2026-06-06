"""
LAN health normaliser.

Responsibilities:
  1. Merge node and interface data by node_id
  2. Map SolarWinds alert severity codes to GBS severity labels
  3. Compute per-node composite health score
  4. Determine Green/Amber/Red status per node
  5. Aggregate nodes to country-level snapshots (weighted by node count)
  6. Build overall LAN summary for the dashboard API

Score formula:
  composite = (availability  * 0.50)   # node up/warning/down
            + (packet_quality * 0.30)  # 1 - percent_loss
            + (throughput_hdr * 0.20)  # 1 - max(in_util, out_util)
            - alert_penalty

  availability:
    status=1  (Up)      -> 100
    status=3  (Warning) ->  60
    status=14 (Down)    ->   0
    other               ->  50

  alert_penalty:  none=0  info=2  warning=10  critical=20

Thresholds (defaults -- overridden by dashboard_config at runtime):
  green  >= 75
  amber  >= 55
  red     < 55
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional

from app.models.lan_schemas import (
    SolarWindsNodeRaw,
    SolarWindsIfaceRaw,
    SolarWindsAlertRaw,
    LANNodeHealth,
    LANCountrySnapshot,
    LANSummary,
    LANAlertItem,
)

logger = logging.getLogger(__name__)

# ------ Defaults -- overridden at runtime from dashboard_config ---------------------------------------------------------
DEFAULT_THRESHOLDS = {
    "lan_score_green": 75.0,
    "lan_score_amber": 55.0,
}

# SolarWinds severity code -> GBS label
# Codes confirmed from Orion schema: 2=Critical 1=Warning 0=Informational
_SEVERITY_MAP: Dict[int, str] = {
    2: "critical",
    1: "warning",
    0: "info",
}

_ALERT_PENALTY: Dict[str, float] = {
    "none":     0.0,
    "info":     2.0,
    "warning":  10.0,
    "critical": 20.0,
}

_AVAILABILITY: Dict[int, float] = {
    1:  100.0,   # Up
    3:   60.0,   # Warning
    14:   0.0,   # Down
}


# ------ Internal helpers ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def _availability_score(status: int) -> float:
    return _AVAILABILITY.get(status, 50.0)


def _map_alert_severity(code: int) -> str:
    return _SEVERITY_MAP.get(code, "info")


def _compute_node_score(
    node: SolarWindsNodeRaw,
    iface: Optional[SolarWindsIfaceRaw],
    alert_severity: str,
) -> float:
    avail    = _availability_score(node.status)
    pkt_qual = max(0.0, 100.0 - float(node.percent_loss))
    if iface is not None:
        peak_util = max(iface.max_in_util, iface.max_out_util)
        throughput = max(0.0, 100.0 - peak_util)
    else:
        throughput = 100.0   # no interface data -- do not penalise

    score = (
        avail     * 0.50
        + pkt_qual  * 0.30
        + throughput * 0.20
        - _ALERT_PENALTY.get(alert_severity, 0.0)
    )
    return round(max(0.0, min(100.0, score)), 1)


def _determine_status(
    score: float,
    thresholds: Dict[str, float],
) -> str:
    if score >= thresholds.get("lan_score_green", DEFAULT_THRESHOLDS["lan_score_green"]):
        return "green"
    if score >= thresholds.get("lan_score_amber", DEFAULT_THRESHOLDS["lan_score_amber"]):
        return "amber"
    return "red"


def _node_alert(
    node_name: str,
    alerts: List[SolarWindsAlertRaw],
) -> Tuple[int, str, str]:
    """
    Find the highest severity alert for a node.
    Returns (count, severity_label, description).
    """
    node_alerts = [
        a for a in alerts
        if a.node_name.lower() == node_name.lower()
        or (a.related_node and a.related_node.lower() == node_name.lower())
    ]
    if not node_alerts:
        return 0, "none", ""

    # Pick highest severity
    best = max(node_alerts, key=lambda a: a.severity)
    return (
        len(node_alerts),
        _map_alert_severity(best.severity),
        best.description,
    )


# ------ Public normalisation functions ------------------------------------------------------------------------------------------------------------------------------------

def normalise_nodes(
    nodes: List[SolarWindsNodeRaw],
    interfaces: List[SolarWindsIfaceRaw],
    alerts: List[SolarWindsAlertRaw],
    thresholds: Optional[Dict[str, float]] = None,
) -> List[LANNodeHealth]:
    """
    Merge node + interface + alert data and compute per-node health scores.
    Returns a list of LANNodeHealth -- one per node.
    """
    t = thresholds or DEFAULT_THRESHOLDS
    now = datetime.now(timezone.utc)

    # Index interfaces and alerts by node_id / node_name for O(1) lookup
    iface_map: Dict[int, SolarWindsIfaceRaw] = {
        i.node_id: i for i in interfaces
    }

    results: List[LANNodeHealth] = []
    for node in nodes:
        iface = iface_map.get(node.node_id)
        alert_count, alert_sev, alert_desc = _node_alert(node.node_name, alerts)
        score  = _compute_node_score(node, iface, alert_sev)
        status = _determine_status(score, t)

        results.append(LANNodeHealth(
            node_id=node.node_id,
            node_name=node.node_name,
            ip_address=node.ip_address,
            country=node.country,
            status=node.status,
            avg_response_time_ms=node.avg_response_time_ms,
            percent_loss=node.percent_loss,
            severity=node.severity,
            alert_count=alert_count,
            alert_severity=alert_sev,
            alert_description=alert_desc,
            max_in_util=iface.max_in_util  if iface else 0.0,
            max_out_util=iface.max_out_util if iface else 0.0,
            avg_in_util=iface.avg_in_util   if iface else 0.0,
            avg_out_util=iface.avg_out_util  if iface else 0.0,
            interface_count=iface.interface_count if iface else 0,
            composite_score=score,
            lan_status=status,
            ingested_at=now,
        ))

    return results


def build_country_snapshots(
    nodes: List[LANNodeHealth],
    thresholds: Optional[Dict[str, float]] = None,
) -> List[LANCountrySnapshot]:
    """
    Aggregate per-node health into per-country summaries.
    Weighted score uses node count as weight -- countries with more
    nodes have proportionally more influence on regional/global scores.
    """
    t = thresholds or DEFAULT_THRESHOLDS
    now = datetime.now(timezone.utc)

    # Group nodes by country
    by_country: Dict[str, List[LANNodeHealth]] = {}
    for node in nodes:
        by_country.setdefault(node.country, []).append(node)

    snapshots: List[LANCountrySnapshot] = []
    for country, country_nodes in sorted(by_country.items()):
        count      = len(country_nodes)
        up         = sum(1 for n in country_nodes if n.status == 1)
        warning    = sum(1 for n in country_nodes if n.status == 3)
        down       = sum(1 for n in country_nodes if n.status == 14)
        avg_score  = round(
            sum(n.composite_score for n in country_nodes) / count, 1
        )
        avg_loss   = round(
            sum(n.percent_loss for n in country_nodes) / count, 2
        )
        avg_resp   = round(
            sum(n.avg_response_time_ms for n in country_nodes) / count, 2
        )
        alerts     = sum(n.alert_count for n in country_nodes)
        critical   = sum(
            1 for n in country_nodes if n.alert_severity == "critical"
        )
        status     = _determine_status(avg_score, t)

        snapshots.append(LANCountrySnapshot(
            country=country,
            node_count=count,
            nodes_up=up,
            nodes_warning=warning,
            nodes_down=down,
            avg_score=avg_score,
            weighted_score=avg_score,   # same at country level; differs at global
            avg_loss_pct=avg_loss,
            avg_response_ms=avg_resp,
            alert_count=alerts,
            critical_count=critical,
            lan_status=status,
            ingested_at=now,
        ))

    return snapshots


def build_lan_summary(
    snapshots: List[LANCountrySnapshot],
    scope: str,
    scope_label: str,
    thresholds: Optional[Dict[str, float]] = None,
) -> LANSummary:
    """
    Build overall LAN summary for the dashboard API.
    Weighted average score across countries (weight = node_count).
    """
    t = thresholds or DEFAULT_THRESHOLDS

    if not snapshots:
        return LANSummary(
            scope=scope, scope_label=scope_label,
            overall_score=0.0, lan_status="red",
            total_nodes=0, nodes_up=0, nodes_warning=0, nodes_down=0,
            total_countries=0, active_alerts=0, critical_alerts=0,
            avg_loss_pct=0.0, avg_response_ms=0.0,
        )

    total_nodes = sum(s.node_count for s in snapshots)
    weighted_score = (
        sum(s.avg_score * s.node_count for s in snapshots) / total_nodes
        if total_nodes > 0 else 0.0
    )
    overall_score = round(weighted_score, 1)
    status        = _determine_status(overall_score, t)

    return LANSummary(
        scope=scope,
        scope_label=scope_label,
        overall_score=overall_score,
        lan_status=status,
        total_nodes=total_nodes,
        nodes_up=sum(s.nodes_up      for s in snapshots),
        nodes_warning=sum(s.nodes_warning for s in snapshots),
        nodes_down=sum(s.nodes_down   for s in snapshots),
        total_countries=len(snapshots),
        active_alerts=sum(s.alert_count   for s in snapshots),
        critical_alerts=sum(s.critical_count for s in snapshots),
        avg_loss_pct=round(
            sum(s.avg_loss_pct * s.node_count for s in snapshots) / total_nodes, 2
        ),
        avg_response_ms=round(
            sum(s.avg_response_ms * s.node_count for s in snapshots) / total_nodes, 2
        ),
        last_ingested_at=datetime.now(timezone.utc),
    )


def build_alert_items(
    alerts: List[SolarWindsAlertRaw],
    node_countries: Optional[Dict[str, str]] = None,
) -> List[LANAlertItem]:
    """
    Convert raw SolarWinds alerts to LANAlertItem list for the alert feed.
    Sorted critical-first, then by triggered time descending.
    node_countries: optional dict of node_name -> country for scope filtering.
    """
    items: List[LANAlertItem] = []
    for a in alerts:
        items.append(LANAlertItem(
            alert_object_id=a.alert_object_id,
            alert_name=a.alert_name,
            severity_code=a.severity,
            severity=_map_alert_severity(a.severity),
            node_name=a.node_name,
            description=a.description,
            triggered_at=a.triggered_at,
            acknowledged=a.acknowledged,
        ))

    items.sort(key=lambda x: (-x.severity_code, x.triggered_at), reverse=False)
    items.sort(key=lambda x: x.severity_code, reverse=True)
    return items
