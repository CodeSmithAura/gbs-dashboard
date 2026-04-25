from pydantic import BaseModel, field_validator
from typing import Literal, Optional
from datetime import datetime


# ── Raw ingested record (matches CSV/JSON schema AND Aruba API field names) ──
class ArubaRawRecord(BaseModel):
    site_id: str
    site_name: str
    timestamp: datetime
    site_health_score: int          # 0–100
    ap_total: int
    ap_online: int
    ap_offline: int
    client_count: int
    auth_failures_1h: int
    active_alerts: int
    alert_severity: Literal["none", "info", "warning", "critical"]
    alert_description: str
    ssid_count: int
    uplink_quality: Literal["good", "fair", "poor", "down"]

    @field_validator("site_health_score")
    @classmethod
    def clamp_score(cls, v: int) -> int:
        return max(0, min(100, v))


# ── Normalised per-site health record ────────────────────────────────────────
class SiteHealth(BaseModel):
    site_id: str
    site_name: str
    timestamp: datetime
    composite_score: float          # 0–100, computed
    site_health_score: int
    ap_total: int
    ap_online: int
    ap_offline: int
    ap_online_pct: float
    client_count: int
    auth_failures_1h: int
    active_alerts: int
    alert_severity: str
    alert_description: str
    ssid_count: int
    uplink_quality: str
    status: Literal["green", "amber", "red"]


# ── Aggregated wireless summary (dashboard headline) ─────────────────────────
class WirelessSummary(BaseModel):
    overall_score: float
    status: Literal["green", "amber", "red"]
    total_sites: int
    sites_healthy: int
    sites_degraded: int
    sites_critical: int
    total_aps: int
    aps_online: int
    ap_online_pct: float
    total_clients: int
    active_alerts: int
    critical_alerts: int
    data_source_type: str           # "file" or "api"
    data_source_path: str
    last_ingested_at: Optional[datetime]
    is_poc: bool = True


# ── Alert item for the alert feed ────────────────────────────────────────────
class AlertItem(BaseModel):
    site_id: str
    site_name: str
    severity: str
    description: str
    timestamp: datetime


# ── Trend data point ─────────────────────────────────────────────────────────
class TrendPoint(BaseModel):
    timestamp: datetime
    score: float
    ap_online_pct: float
    client_count: int
