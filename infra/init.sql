-- GBS Health Dashboard — Database Initialisation
-- Runs once on first container start via docker-entrypoint-initdb.d

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ── Wireless metrics hypertable ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS wireless_metrics (
    id              BIGSERIAL,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    site_id         VARCHAR(64)  NOT NULL,
    site_name       VARCHAR(255) NOT NULL,
    data_timestamp  TIMESTAMPTZ  NOT NULL,
    composite_score NUMERIC(5,1) NOT NULL,
    site_health_score INTEGER    NOT NULL,
    ap_total        INTEGER      NOT NULL,
    ap_online       INTEGER      NOT NULL,
    ap_offline      INTEGER      NOT NULL,
    ap_online_pct   NUMERIC(5,1) NOT NULL,
    client_count    INTEGER      NOT NULL,
    auth_failures_1h INTEGER     NOT NULL,
    active_alerts   INTEGER      NOT NULL,
    alert_severity  VARCHAR(16)  NOT NULL,
    alert_description TEXT,
    ssid_count      INTEGER      NOT NULL,
    uplink_quality  VARCHAR(16)  NOT NULL,
    status          VARCHAR(8)   NOT NULL,
    PRIMARY KEY (ingested_at, id)
);

SELECT create_hypertable('wireless_metrics', 'ingested_at', if_not_exists => TRUE);

-- Retention: keep 90 days in POC (extend in Phase 2)
SELECT add_retention_policy('wireless_metrics', INTERVAL '90 days', if_not_exists => TRUE);

-- Index for fast per-site queries
CREATE INDEX IF NOT EXISTS idx_wm_site_id ON wireless_metrics (site_id, ingested_at DESC);

-- ── Dashboard config store ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dashboard_config (
    key         VARCHAR(128) PRIMARY KEY,
    value       TEXT         NOT NULL,
    description TEXT,
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Seed default thresholds
INSERT INTO dashboard_config (key, value, description) VALUES
    ('score_green',   '80', 'Composite score threshold for Green status'),
    ('score_amber',   '60', 'Composite score threshold for Amber status (below = Red)'),
    ('ap_pct_green',  '95', 'AP online % threshold for Green'),
    ('ap_pct_amber',  '85', 'AP online % threshold for Amber (below = Red)'),
    ('poll_interval', '60', 'Ingestion poll interval in seconds'),
    ('is_poc',        'true', 'Flag indicating POC mode (file-based data)')
ON CONFLICT (key) DO NOTHING;
