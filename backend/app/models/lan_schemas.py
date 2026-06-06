"""
Pydantic data models for the SolarWinds LAN health pillar.

Model hierarchy:
  SolarWindsNodeRaw      -- raw SWQL query result per node
  SolarWindsIfaceRaw     -- raw SWQL interface aggregation per node
  SolarWindsAlertRaw     -- raw SWQL alert query result
  LANNodeHealth          -- normalised per-node health record (stored to DB)
  LANCountrySnapshot     -- aggregated per-country summary (stored to DB)
  LANSummary             -- overall LAN pillar summary for dashboard
  LANCountryGroup        -- country group definition from sw_country_groups
  LANCountryInfo         -- country name + node count for combo box
  LANAlertItem           -- single alert for alert feed
  LANTrendPoint          -- single hourly data point for trend chart
"""

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, field_validator


# ------ Raw SWQL results ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

class SolarWindsNodeRaw(BaseModel):
    """Maps directly from SWQL Query 1 (Orion.Nodes) response fields."""
    node_id:              int
    node_name:            str
    ip_address:           str
    status:               int            # 1=Up 3=Warning 14=Down
    avg_response_time_ms: float = 0.0
    percent_loss:         float = 0.0
    severity:             int   = 0
    country:              str   = "Unclassified"

    @field_validator("country", mode="before")
    @classmethod
    def default_country(cls, v):
        if v is None or str(v).strip() == "":
            return "Unclassified"
        return str(v).strip()

    @field_validator("status", mode="before")
    @classmethod
    def coerce_status(cls, v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 14   # treat unparseable as Down (safe default)


class SolarWindsIfaceRaw(BaseModel):
    """Maps from SWQL Query 2 (Orion.NPM.Interfaces aggregated) response."""
    node_id:         int
    node_name:       str
    max_in_util:     float = 0.0
    max_out_util:    float = 0.0
    avg_in_util:     float = 0.0
    avg_out_util:    float = 0.0
    interface_count: int   = 0

    @field_validator("max_in_util", "max_out_util",
                     "avg_in_util", "avg_out_util", mode="before")
    @classmethod
    def coerce_float(cls, v):
        try:
            return float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0


class SolarWindsAlertRaw(BaseModel):
    """Maps from SWQL Query 3 (Orion.AlertObjects) response."""
    alert_object_id: int
    alert_name:      str
    severity:        int           # 2=Critical 1=Warning 0=Informational
    node_name:       str
    related_node:    Optional[str] = None
    triggered_at:    str           # ISO string from SWIS
    description:     str
    acknowledged:    bool = False

    @field_validator("acknowledged", mode="before")
    @classmethod
    def coerce_bool(cls, v):
        if isinstance(v, bool):
            return v
        if isinstance(v, int):
            return v != 0
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return False
    @field_validator("node_name", "related_node", mode="before")
    @classmethod
    def clean_str(cls, v):
        return str(v).strip() if v is not None else ""

    @field_validator("severity", mode="before")
    @classmethod
    def coerce_severity(cls, v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0


# ------ Normalised models (stored to database and served by API) ------------------------------------------------------

class LANNodeHealth(BaseModel):
    """
    Per-node normalised health record.
    Stored to lan_metrics table. One row per node per ingest cycle.
    """
    node_id:             int
    node_name:           str
    ip_address:          str
    country:             str
    status:              int
    avg_response_time_ms: float
    percent_loss:        float
    severity:            int
    alert_count:         int   = 0
    alert_severity:      Literal["none", "info", "warning", "critical"] = "none"
    alert_description:   str   = ""
    max_in_util:         float = 0.0
    max_out_util:        float = 0.0
    avg_in_util:         float = 0.0
    avg_out_util:        float = 0.0
    interface_count:     int   = 0
    composite_score:     float = 0.0
    lan_status:          Literal["green", "amber", "red"] = "amber"
    ingested_at:         Optional[datetime] = None


class LANCountrySnapshot(BaseModel):
    """
    Pre-aggregated country-level summary.
    Stored to lan_country_snapshots. One row per country per ingest cycle.
    Used for the global dashboard view to avoid re-aggregating 700 rows per call.
    """
    country:         str
    node_count:      int
    nodes_up:        int
    nodes_warning:   int
    nodes_down:      int
    avg_score:       float
    weighted_score:  float
    avg_loss_pct:    float
    avg_response_ms: float
    alert_count:     int
    critical_count:  int
    lan_status:      Literal["green", "amber", "red"]
    ingested_at:     Optional[datetime] = None


class LANSummary(BaseModel):
    """
    Overall LAN pillar summary returned by GET /api/v1/lan/summary.
    Scope-aware -- reflects the currently selected country/group.
    """
    scope:              str           # 'all', 'group:asia-pacific', 'country:India'
    scope_label:        str           # human-readable: 'All', 'Asia Pacific', 'India'
    overall_score:      float
    lan_status:         Literal["green", "amber", "red"]
    total_nodes:        int
    nodes_up:           int
    nodes_warning:      int
    nodes_down:         int
    total_countries:    int
    active_alerts:      int
    critical_alerts:    int
    avg_loss_pct:       float
    avg_response_ms:    float
    last_ingested_at:   Optional[datetime] = None
    data_source:        str = "SolarWinds Observability Self-Hosted"


class LANCountryGroup(BaseModel):
    """Country group from sw_country_groups table -- used to build combo box."""
    group_id:    int
    group_name:  str
    group_slug:  str
    countries:   List[str]    # split from comma-separated DB column
    sort_order:  int
    is_active:   bool


class LANCountryInfo(BaseModel):
    """Country name and node count for the combo box countries section."""
    country:    str
    node_count: int


class LANAlertItem(BaseModel):
    """Single alert for the LAN alert feed."""
    alert_object_id: int
    alert_name:      str
    severity_code:   int
    severity:        Literal["none", "info", "warning", "critical"]
    node_name:       str
    description:     str
    triggered_at:    str
    acknowledged:    bool


class LANTrendPoint(BaseModel):
    """Single hourly data point for the LAN trend chart."""
    bucket:         str       # ISO hour string e.g. '2026-04-18 09:00:00'
    avg_score:      float
    nodes_up_pct:   float
    avg_loss_pct:   float
