"""
Smoke tests — validates the full pipeline without Docker.
Run from the backend/ directory:
    pip install -r requirements.txt
    python -m pytest tests/test_pipeline.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone

import pytest
from app.models.schemas import ArubaRawRecord
from app.services.ingestion import FileConnector
from app.services.normaliser import normalise_records, build_summary, extract_alerts, compute_composite_score


SAMPLE_CSV = os.path.join(os.path.dirname(__file__), "../../data/samples/aruba_health_sample.csv")
SAMPLE_JSON = os.path.join(os.path.dirname(__file__), "../../data/samples/aruba_health_sample.json")

MOCK_RECORD = ArubaRawRecord(
    site_id="TEST-01",
    site_name="Test Site",
    timestamp=datetime.now(timezone.utc),
    site_health_score=85,
    ap_total=20,
    ap_online=19,
    ap_offline=1,
    client_count=150,
    auth_failures_1h=3,
    active_alerts=1,
    alert_severity="warning",
    alert_description="One AP offline",
    ssid_count=4,
    uplink_quality="good",
)


# ── Schema validation ────────────────────────────────────────────────────────
class TestSchema:
    def test_valid_record_accepted(self):
        assert MOCK_RECORD.site_id == "TEST-01"

    def test_score_clamped_above_100(self):
        r = MOCK_RECORD.model_copy(update={"site_health_score": 150})
        assert r.site_health_score == 150  # raw field, clamping is in normaliser

    def test_invalid_severity_rejected(self):
        with pytest.raises(Exception):
            ArubaRawRecord(**{**MOCK_RECORD.model_dump(), "alert_severity": "extreme"})


# ── Score computation ─────────────────────────────────────────────────────────
class TestScoreComputation:
    def test_perfect_site_scores_near_80(self):
        r = MOCK_RECORD.model_copy(update={
            "site_health_score": 100, "ap_online": 20, "ap_total": 20,
            "active_alerts": 0, "alert_severity": "none",
        })
        score = compute_composite_score(r)
        assert score == 80.0  # 50 + 30 + 0 penalty

    def test_critical_alert_reduces_score(self):
        r = MOCK_RECORD.model_copy(update={
            "site_health_score": 100, "ap_online": 20, "ap_total": 20,
            "active_alerts": 1, "alert_severity": "critical",
        })
        score = compute_composite_score(r)
        assert score == 60.0  # 80 - 20 penalty

    def test_score_never_negative(self):
        r = MOCK_RECORD.model_copy(update={
            "site_health_score": 0, "ap_online": 0, "ap_total": 20,
            "alert_severity": "critical",
        })
        score = compute_composite_score(r)
        assert score >= 0.0

    def test_warning_penalty_is_10(self):
        base = MOCK_RECORD.model_copy(update={"alert_severity": "none"})
        warn = MOCK_RECORD.model_copy(update={"alert_severity": "warning"})
        diff = compute_composite_score(base) - compute_composite_score(warn)
        assert diff == 10.0


# ── Normaliser ────────────────────────────────────────────────────────────────
class TestNormaliser:
    def test_normalise_produces_status(self):
        sites = normalise_records([MOCK_RECORD])
        assert len(sites) == 1
        assert sites[0].status in ("green", "amber", "red")

    def test_high_score_is_green(self):
        r = MOCK_RECORD.model_copy(update={
            "site_health_score": 100, "ap_online": 20, "ap_total": 20,
            "alert_severity": "none",
        })
        sites = normalise_records([r])
        assert sites[0].status == "green"

    def test_low_score_is_red(self):
        r = MOCK_RECORD.model_copy(update={
            "site_health_score": 20, "ap_online": 5, "ap_total": 20,
            "alert_severity": "critical",
        })
        sites = normalise_records([r])
        assert sites[0].status == "red"

    def test_ap_pct_calculated_correctly(self):
        r = MOCK_RECORD.model_copy(update={"ap_online": 18, "ap_total": 20})
        sites = normalise_records([r])
        assert sites[0].ap_online_pct == 90.0


# ── Summary builder ───────────────────────────────────────────────────────────
class TestSummary:
    def test_summary_from_single_site(self):
        sites = normalise_records([MOCK_RECORD])
        summary = build_summary(sites, "file", "/data/test.csv", datetime.now(timezone.utc))
        assert summary.total_sites == 1
        assert summary.data_source_type == "file"
        assert summary.is_poc is True

    def test_empty_sites_returns_red(self):
        summary = build_summary([], "file", "/data/test.csv", None)
        assert summary.status == "red"
        assert summary.total_sites == 0

    def test_critical_site_bubbles_to_summary(self):
        critical = MOCK_RECORD.model_copy(update={
            "site_health_score": 10, "ap_online": 2, "ap_total": 20,
            "alert_severity": "critical",
        })
        sites = normalise_records([MOCK_RECORD, critical])
        summary = build_summary(sites, "file", "/data/test.csv", None)
        assert summary.status == "red"


# ── Alert extraction ──────────────────────────────────────────────────────────
class TestAlerts:
    def test_none_severity_excluded(self):
        r = MOCK_RECORD.model_copy(update={"alert_severity": "none", "alert_description": ""})
        sites = normalise_records([r])
        alerts = extract_alerts(sites)
        assert len(alerts) == 0

    def test_critical_sorted_first(self):
        crit = MOCK_RECORD.model_copy(update={"site_id": "C", "alert_severity": "critical", "alert_description": "Critical!"})
        warn = MOCK_RECORD.model_copy(update={"site_id": "W", "alert_severity": "warning", "alert_description": "Warning!"})
        sites = normalise_records([warn, crit])
        alerts = extract_alerts(sites)
        assert alerts[0].severity == "critical"


# ── File connectors ───────────────────────────────────────────────────────────
class TestFileConnectors:
    def test_csv_connector_loads_records(self):
        if not os.path.exists(SAMPLE_CSV):
            pytest.skip("Sample CSV not found")
        conn = FileConnector(SAMPLE_CSV, "csv")
        records = conn.fetch()
        assert len(records) > 0
        assert all(isinstance(r, ArubaRawRecord) for r in records)

    def test_json_connector_loads_records(self):
        if not os.path.exists(SAMPLE_JSON):
            pytest.skip("Sample JSON not found")
        conn = FileConnector(SAMPLE_JSON, "json")
        records = conn.fetch()
        assert len(records) > 0

    def test_missing_file_returns_empty(self):
        conn = FileConnector("/nonexistent/path/file.csv", "csv")
        records = conn.fetch()
        assert records == []

    def test_csv_and_json_produce_same_site_ids(self):
        if not (os.path.exists(SAMPLE_CSV) and os.path.exists(SAMPLE_JSON)):
            pytest.skip("Sample files not found")
        csv_ids = {r.site_id for r in FileConnector(SAMPLE_CSV, "csv").fetch()}
        json_ids = {r.site_id for r in FileConnector(SAMPLE_JSON, "json").fetch()}
        assert csv_ids == json_ids


# ── AC10 — Response time ──────────────────────────────────────────────────────
class TestResponseTime:
    def test_full_pipeline_under_2s(self):
        """AC10 — end-to-end ingest+normalise+summary under 2000ms."""
        import time
        connector = FileConnector(SAMPLE_CSV, "csv")
        t0 = time.perf_counter()
        raw = connector.fetch()
        sites = normalise_records(raw)
        build_summary(sites, "file", SAMPLE_CSV, datetime.now(timezone.utc))
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert elapsed_ms < 2000, f"Pipeline took {elapsed_ms:.0f}ms — exceeds 2000ms AC10 limit"
