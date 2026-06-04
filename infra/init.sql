-- =============================================================================
-- GBS Service Health Dashboard -- Database Initialisation
-- MySQL 8.0+
-- Run once using the gbs_admin (or DBA) account before starting the application.
-- =============================================================================

-- Create database if not already created by the DBA
CREATE DATABASE IF NOT EXISTS gbs_health
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE gbs_health;

-- =============================================================================
-- wireless_metrics -- main time-series table
-- Partitioned by YEAR(data_timestamp) for efficient time-range queries.
-- Add a new partition each year as the data grows.
-- =============================================================================
CREATE TABLE IF NOT EXISTS wireless_metrics (
    id                BIGINT        NOT NULL AUTO_INCREMENT,
    ingested_at       DATETIME(0)   NOT NULL DEFAULT (UTC_TIMESTAMP()),
    site_id           VARCHAR(64)   NOT NULL,
    site_name         VARCHAR(255)  NOT NULL,
    data_timestamp    DATETIME(0)   NOT NULL,
    composite_score   DECIMAL(5,1)  NOT NULL,
    site_health_score INT           NOT NULL,
    ap_total          INT           NOT NULL,
    ap_online         INT           NOT NULL,
    ap_offline        INT           NOT NULL,
    ap_online_pct     DECIMAL(5,1)  NOT NULL,
    client_count      INT           NOT NULL,
    auth_failures_1h  INT           NOT NULL,
    active_alerts     INT           NOT NULL,
    alert_severity    VARCHAR(16)   NOT NULL,
    alert_description TEXT,
    ssid_count        INT           NOT NULL,
    uplink_quality    VARCHAR(16)   NOT NULL,
    status            VARCHAR(8)    NOT NULL,
    PRIMARY KEY (id, data_timestamp)
)
ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_unicode_ci
PARTITION BY RANGE (YEAR(data_timestamp)) (
    PARTITION p2025 VALUES LESS THAN (2026),
    PARTITION p2026 VALUES LESS THAN (2027),
    PARTITION p2027 VALUES LESS THAN (2028),
    PARTITION pfuture VALUES LESS THAN MAXVALUE
);

-- Index for fast per-site lookups and trend queries
CREATE INDEX IF NOT EXISTS idx_wm_site_ingested
    ON wireless_metrics (site_id, ingested_at DESC);

CREATE INDEX IF NOT EXISTS idx_wm_data_timestamp
    ON wireless_metrics (data_timestamp);

-- =============================================================================
-- dashboard_config -- key-value configuration store
-- =============================================================================
CREATE TABLE IF NOT EXISTS dashboard_config (
    `key`       VARCHAR(128) NOT NULL,
    `value`     TEXT         NOT NULL,
    description TEXT,
    updated_at  DATETIME(0)  NOT NULL DEFAULT (UTC_TIMESTAMP())
                             ON UPDATE (UTC_TIMESTAMP()),
    PRIMARY KEY (`key`)
)
ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_unicode_ci;

-- Seed default thresholds (safe to re-run -- INSERT IGNORE skips existing rows)
INSERT IGNORE INTO dashboard_config (`key`, `value`, description) VALUES
    ('score_green',    '72',   'Composite score threshold for Green status'),
    ('score_amber',    '55',   'Composite score threshold for Amber (below = Red)'),
    ('ap_pct_green',   '95',   'AP online % threshold for Green'),
    ('ap_pct_amber',   '85',   'AP online % threshold for Amber'),
    ('poll_interval',  '60',   'Ingestion poll interval in seconds'),
    ('is_poc',         'true', 'Flag indicating POC mode (file-based data)');

-- =============================================================================
-- Retention event -- deletes rows older than 90 days (runs nightly at 02:00)
-- Equivalent of TimescaleDB add_retention_policy()
-- Requires MySQL Event Scheduler to be enabled:
--   SET GLOBAL event_scheduler = ON;
-- =============================================================================
DROP EVENT IF EXISTS gbs_retention_cleanup;

CREATE EVENT gbs_retention_cleanup
    ON SCHEDULE EVERY 1 DAY
    STARTS (CURRENT_DATE + INTERVAL 1 DAY + INTERVAL 2 HOUR)
    DO
        DELETE FROM wireless_metrics
        WHERE data_timestamp < DATE_SUB(UTC_TIMESTAMP(), INTERVAL 90 DAY);

-- Enable event scheduler (requires SUPER or EVENT privilege)
-- Uncomment if not already enabled at server level:
-- SET GLOBAL event_scheduler = ON;

-- =============================================================================
-- Grant permissions to application service account
-- Run this section as the DBA/root account.
-- Replace 'changeme' with the actual password provided by the SQL team.
-- Replace '%' with the actual application VM IP for tighter security.
-- =============================================================================
-- CREATE USER IF NOT EXISTS 'gbs_app'@'%' IDENTIFIED BY 'changeme';
-- GRANT SELECT, INSERT, DELETE ON gbs_health.* TO 'gbs_app'@'%';
-- GRANT EVENT ON gbs_health.* TO 'gbs_app'@'%';
-- FLUSH PRIVILEGES;

SELECT 'GBS Health database initialised successfully.' AS status;
