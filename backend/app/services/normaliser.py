"""
Normaliser — converts raw Aruba records into canonical GBS health model.
Computes composite health score and Green/Amber/Red status.
Thresholds are read from DB config (configurable without code changes).
"""

from typing import List, Tuple
from app.models.schemas import ArubaRawRecord, SiteHealth, WirelessSummary, AlertItem

# Default thresholds — overridden by DashboardConfig DB table at runtime
DEFAULT_THRESHOLDS = {
    "score_green": 80,
    "score_amber": 60,
    "ap_pct_green": 95,
    "ap_pct_amber": 85,
}

ALERT_PENALTY = {"none": 0, "info": -2, "warning": -10, "critical": -20}
SEVERITY_ORDER = ["none", "info", "warning", "critical"]


def compute_composite_score(record: ArubaRawRecord) -> float:
    ap_pct = (record.ap_online / record.ap_total * 100) if record.ap_total > 0 else 0
    score = (
        (record.site_health_score / 100) * 50
        + (ap_pct / 100) * 30
        + ALERT_PENALTY.get(record.alert_severity, 0)
    )
    return round(max(0.0, min(100.0, score)), 1)


def determine_status(score: float, thresholds: dict) -> str:
    if score >= thresholds.get("score_green", 80):
        return "green"
    if score >= thresholds.get("score_amber", 60):
        return "amber"
    return "red"


def normalise_records(
    raw: List[ArubaRawRecord],
    thresholds: dict = None,
) -> List[SiteHealth]:
    t = thresholds or DEFAULT_THRESHOLDS
    results = []
    for r in raw:
        ap_pct = round((r.ap_online / r.ap_total * 100) if r.ap_total > 0 else 0, 1)
        score = compute_composite_score(r)
        results.append(SiteHealth(
            site_id=r.site_id,
            site_name=r.site_name,
            timestamp=r.timestamp,
            composite_score=score,
            site_health_score=r.site_health_score,
            ap_total=r.ap_total,
            ap_online=r.ap_online,
            ap_offline=r.ap_offline,
            ap_online_pct=ap_pct,
            client_count=r.client_count,
            auth_failures_1h=r.auth_failures_1h,
            active_alerts=r.active_alerts,
            alert_severity=r.alert_severity,
            alert_description=r.alert_description,
            ssid_count=r.ssid_count,
            uplink_quality=r.uplink_quality,
            status=determine_status(score, t),
        ))
    return results


def build_summary(
    sites: List[SiteHealth],
    data_source_type: str,
    data_source_path: str,
    last_ingested_at,
) -> WirelessSummary:
    if not sites:
        return WirelessSummary(
            overall_score=0, status="red", total_sites=0,
            sites_healthy=0, sites_degraded=0, sites_critical=0,
            total_aps=0, aps_online=0, ap_online_pct=0,
            total_clients=0, active_alerts=0, critical_alerts=0,
            data_source_type=data_source_type,
            data_source_path=data_source_path,
            last_ingested_at=last_ingested_at,
        )

    overall = round(sum(s.composite_score for s in sites) / len(sites), 1)
    total_aps = sum(s.ap_total for s in sites)
    aps_online = sum(s.ap_online for s in sites)
    ap_pct = round((aps_online / total_aps * 100) if total_aps else 0, 1)

    # Worst overall status
    statuses = [s.status for s in sites]
    if "red" in statuses:
        status = "red"
    elif "amber" in statuses:
        status = "amber"
    else:
        status = "green"

    return WirelessSummary(
        overall_score=overall,
        status=status,
        total_sites=len(sites),
        sites_healthy=sum(1 for s in sites if s.status == "green"),
        sites_degraded=sum(1 for s in sites if s.status == "amber"),
        sites_critical=sum(1 for s in sites if s.status == "red"),
        total_aps=total_aps,
        aps_online=aps_online,
        ap_online_pct=ap_pct,
        total_clients=sum(s.client_count for s in sites),
        active_alerts=sum(s.active_alerts for s in sites),
        critical_alerts=sum(1 for s in sites if s.alert_severity == "critical"),
        data_source_type=data_source_type,
        data_source_path=data_source_path,
        last_ingested_at=last_ingested_at,
    )


def extract_alerts(sites: List[SiteHealth]) -> List[AlertItem]:
    alerts = []
    for s in sites:
        if s.alert_severity != "none" and s.alert_description:
            alerts.append(AlertItem(
                site_id=s.site_id,
                site_name=s.site_name,
                severity=s.alert_severity,
                description=s.alert_description,
                timestamp=s.timestamp,
            ))
    alerts.sort(key=lambda a: SEVERITY_ORDER.index(a.severity), reverse=True)
    return alerts
