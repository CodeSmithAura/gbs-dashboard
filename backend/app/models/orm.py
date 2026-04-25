from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean
from sqlalchemy.sql import func
from app.core.database import Base


class WirelessMetric(Base):
    """Time-series hypertable — one row per site per ingestion run."""
    __tablename__ = "wireless_metrics"

    id = Column(Integer, primary_key=True, index=True)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    site_id = Column(String(64), nullable=False, index=True)
    site_name = Column(String(255), nullable=False)
    data_timestamp = Column(DateTime(timezone=True), nullable=False)
    composite_score = Column(Float, nullable=False)
    site_health_score = Column(Integer, nullable=False)
    ap_total = Column(Integer, nullable=False)
    ap_online = Column(Integer, nullable=False)
    ap_offline = Column(Integer, nullable=False)
    ap_online_pct = Column(Float, nullable=False)
    client_count = Column(Integer, nullable=False)
    auth_failures_1h = Column(Integer, nullable=False)
    active_alerts = Column(Integer, nullable=False)
    alert_severity = Column(String(16), nullable=False)
    alert_description = Column(Text, nullable=True)
    ssid_count = Column(Integer, nullable=False)
    uplink_quality = Column(String(16), nullable=False)
    status = Column(String(8), nullable=False)  # green / amber / red


class DashboardConfig(Base):
    """Configuration store — thresholds and data source settings."""
    __tablename__ = "dashboard_config"

    key = Column(String(128), primary_key=True)
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
