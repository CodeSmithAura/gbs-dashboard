-- =============================================================================
-- GBS Service Health Dashboard -- Database Initialisation
-- Microsoft SQL Server 2017+ | Version: v1.1
-- Adds SolarWinds LAN pillar tables to existing schema.
-- Run once using DBA account. Safe to re-run (IF NOT EXISTS guards).
-- =============================================================================

-- ------ Prerequisite: existing tables from v1.0 ---------------------------------------------------------------------------------------------------------
-- wireless_metrics and dashboard_config must already exist.
-- If starting fresh, this script creates everything from scratch.

USE gbs_health;
GO

-- =============================================================================
-- wireless_metrics (from v1.0 -- included for fresh installs)
-- =============================================================================
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'dbo.wireless_metrics') AND type = N'U'
)
BEGIN
    CREATE TABLE dbo.wireless_metrics (
        id                BIGINT          NOT NULL IDENTITY(1,1),
        ingested_at       DATETIME2(0)    NOT NULL DEFAULT GETUTCDATE(),
        site_id           NVARCHAR(64)    NOT NULL,
        site_name         NVARCHAR(255)   NOT NULL,
        data_timestamp    DATETIME2(0)    NOT NULL,
        composite_score   DECIMAL(5,1)    NOT NULL,
        site_health_score INT             NOT NULL,
        ap_total          INT             NOT NULL,
        ap_online         INT             NOT NULL,
        ap_offline        INT             NOT NULL,
        ap_online_pct     DECIMAL(5,1)    NOT NULL,
        client_count      INT             NOT NULL,
        auth_failures_1h  INT             NOT NULL,
        active_alerts     INT             NOT NULL,
        alert_severity    NVARCHAR(16)    NOT NULL,
        alert_description NVARCHAR(MAX)   NULL,
        ssid_count        INT             NOT NULL,
        uplink_quality    NVARCHAR(16)    NOT NULL,
        status            NVARCHAR(8)     NOT NULL,
        CONSTRAINT PK_wireless_metrics PRIMARY KEY CLUSTERED (id ASC)
    );
    CREATE NONCLUSTERED INDEX IX_wm_site_ingested
        ON dbo.wireless_metrics (site_id ASC, ingested_at DESC);
    CREATE NONCLUSTERED INDEX IX_wm_data_timestamp
        ON dbo.wireless_metrics (data_timestamp ASC)
        INCLUDE (composite_score, ap_online_pct, client_count, ingested_at);
    PRINT 'Table wireless_metrics created.';
END
GO

-- =============================================================================
-- dashboard_config (from v1.0 -- included for fresh installs)
-- =============================================================================
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'dbo.dashboard_config') AND type = N'U'
)
BEGIN
    CREATE TABLE dbo.dashboard_config (
        [key]       NVARCHAR(128)   NOT NULL,
        [value]     NVARCHAR(MAX)   NOT NULL,
        description NVARCHAR(MAX)   NULL,
        updated_at  DATETIME2(0)    NOT NULL DEFAULT GETUTCDATE(),
        CONSTRAINT PK_dashboard_config PRIMARY KEY CLUSTERED ([key] ASC)
    );
    PRINT 'Table dashboard_config created.';
END
GO

-- Seed wireless thresholds
MERGE dbo.dashboard_config AS target
USING (VALUES
    ('score_green',    '72',   'Wireless composite score threshold for Green'),
    ('score_amber',    '55',   'Wireless composite score threshold for Amber'),
    ('ap_pct_green',   '95',   'AP online % threshold for Green'),
    ('ap_pct_amber',   '85',   'AP online % threshold for Amber'),
    ('poll_interval',  '60',   'Wireless ingestion poll interval seconds'),
    ('is_poc',         'true', 'POC mode flag')
) AS source ([key], [value], description)
ON target.[key] = source.[key]
WHEN NOT MATCHED THEN
    INSERT ([key], [value], description)
    VALUES (source.[key], source.[value], source.description);
GO

-- =============================================================================
-- lan_metrics -- time-series node health records from SolarWinds
-- One row per node per ingest cycle. Indexed for time-range and country queries.
-- =============================================================================
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'dbo.lan_metrics') AND type = N'U'
)
BEGIN
    CREATE TABLE dbo.lan_metrics (
        id                  BIGINT          NOT NULL IDENTITY(1,1),
        ingested_at         DATETIME2(0)    NOT NULL DEFAULT GETUTCDATE(),
        node_id             INT             NOT NULL,
        node_name           NVARCHAR(255)   NOT NULL,
        ip_address          NVARCHAR(64)    NOT NULL,
        country             NVARCHAR(128)   NOT NULL DEFAULT 'Unclassified',
        status              INT             NOT NULL,   -- 1=Up 3=Warning 14=Down
        avg_response_time_ms DECIMAL(10,2)  NOT NULL DEFAULT 0,
        percent_loss        DECIMAL(5,2)    NOT NULL DEFAULT 0,
        severity            INT             NOT NULL DEFAULT 0,
        alert_count         INT             NOT NULL DEFAULT 0,
        alert_severity      NVARCHAR(16)    NOT NULL DEFAULT 'none',
        alert_description   NVARCHAR(MAX)   NULL,
        max_in_util         DECIMAL(5,2)    NOT NULL DEFAULT 0,
        max_out_util        DECIMAL(5,2)    NOT NULL DEFAULT 0,
        avg_in_util         DECIMAL(5,2)    NOT NULL DEFAULT 0,
        avg_out_util        DECIMAL(5,2)    NOT NULL DEFAULT 0,
        interface_count     INT             NOT NULL DEFAULT 0,
        composite_score     DECIMAL(5,1)    NOT NULL DEFAULT 0,
        lan_status          NVARCHAR(8)     NOT NULL DEFAULT 'amber',
        CONSTRAINT PK_lan_metrics PRIMARY KEY CLUSTERED (id ASC)
    );
    -- Fast country + time range queries for trend and country selector
    CREATE NONCLUSTERED INDEX IX_lan_country_ingested
        ON dbo.lan_metrics (country ASC, ingested_at DESC)
        INCLUDE (composite_score, status, alert_severity);
    -- Fast per-node lookups for latest snapshot
    CREATE NONCLUSTERED INDEX IX_lan_node_ingested
        ON dbo.lan_metrics (node_id ASC, ingested_at DESC)
        INCLUDE (composite_score, lan_status);
    -- Trend chart queries filter by ingested_at range
    CREATE NONCLUSTERED INDEX IX_lan_ingested
        ON dbo.lan_metrics (ingested_at ASC)
        INCLUDE (country, composite_score, status);
    PRINT 'Table lan_metrics created.';
END
GO

-- =============================================================================
-- lan_country_snapshots -- pre-aggregated country-level summary
-- Written once per ingest cycle. Used for global view (30 rows not 700).
-- Avoids re-aggregating 700 node rows on every dashboard API call.
-- =============================================================================
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'dbo.lan_country_snapshots') AND type = N'U'
)
BEGIN
    CREATE TABLE dbo.lan_country_snapshots (
        id              BIGINT          NOT NULL IDENTITY(1,1),
        ingested_at     DATETIME2(0)    NOT NULL DEFAULT GETUTCDATE(),
        country         NVARCHAR(128)   NOT NULL,
        node_count      INT             NOT NULL DEFAULT 0,
        nodes_up        INT             NOT NULL DEFAULT 0,
        nodes_warning   INT             NOT NULL DEFAULT 0,
        nodes_down      INT             NOT NULL DEFAULT 0,
        avg_score       DECIMAL(5,1)    NOT NULL DEFAULT 0,
        weighted_score  DECIMAL(5,1)    NOT NULL DEFAULT 0,
        avg_loss_pct    DECIMAL(5,2)    NOT NULL DEFAULT 0,
        avg_response_ms DECIMAL(10,2)   NOT NULL DEFAULT 0,
        alert_count     INT             NOT NULL DEFAULT 0,
        critical_count  INT             NOT NULL DEFAULT 0,
        lan_status      NVARCHAR(8)     NOT NULL DEFAULT 'amber',
        CONSTRAINT PK_lan_country_snapshots PRIMARY KEY CLUSTERED (id ASC)
    );
    CREATE NONCLUSTERED INDEX IX_lcs_ingested
        ON dbo.lan_country_snapshots (ingested_at DESC)
        INCLUDE (country, weighted_score, lan_status);
    CREATE NONCLUSTERED INDEX IX_lcs_country_ingested
        ON dbo.lan_country_snapshots (country ASC, ingested_at DESC);
    PRINT 'Table lan_country_snapshots created.';
END
GO

-- =============================================================================
-- sw_country_groups -- client-configurable country groupings
-- Updated directly by the client team in SSMS. No restart required.
-- =============================================================================
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'dbo.sw_country_groups') AND type = N'U'
)
BEGIN
    CREATE TABLE dbo.sw_country_groups (
        group_id    INT             NOT NULL IDENTITY(1,1),
        group_name  NVARCHAR(64)    NOT NULL,
        group_slug  NVARCHAR(64)    NOT NULL,
        countries   NVARCHAR(MAX)   NOT NULL,
        sort_order  INT             NOT NULL DEFAULT 0,
        is_active   BIT             NOT NULL DEFAULT 1,
        created_at  DATETIME2(0)    NOT NULL DEFAULT GETUTCDATE(),
        updated_at  DATETIME2(0)    NOT NULL DEFAULT GETUTCDATE(),
        CONSTRAINT PK_sw_country_groups PRIMARY KEY CLUSTERED (group_id),
        CONSTRAINT UQ_sw_country_groups_slug UNIQUE (group_slug)
    );
    PRINT 'Table sw_country_groups created.';
END
GO

-- Seed example country groups using India as placeholder country
-- Replace country names with actual values from SolarWinds custom property
MERGE dbo.sw_country_groups AS target
USING (VALUES
    ('All',           'all',            '',         0,   1),
    ('Asia Pacific',  'asia-pacific',   'India',    1,   1),
    ('South Asia',    'south-asia',     'India',    2,   1),
    ('Unclassified',  'unclassified',   'Unclassified', 99, 1)
) AS source (group_name, group_slug, countries, sort_order, is_active)
ON target.group_slug = source.group_slug
WHEN NOT MATCHED THEN
    INSERT (group_name, group_slug, countries, sort_order, is_active)
    VALUES (source.group_name, source.group_slug,
            source.countries, source.sort_order, source.is_active);
GO

-- Seed LAN health thresholds into dashboard_config
MERGE dbo.dashboard_config AS target
USING (VALUES
    ('lan_score_green',   '75',  'LAN composite score threshold for Green'),
    ('lan_score_amber',   '55',  'LAN composite score threshold for Amber'),
    ('lan_avail_green',   '98',  'Node availability % threshold for Green'),
    ('lan_avail_amber',   '90',  'Node availability % threshold for Amber'),
    ('lan_loss_green',    '1',   'Packet loss % threshold for Green (below)'),
    ('lan_loss_amber',    '5',   'Packet loss % threshold for Amber (below)'),
    ('lan_poll_interval', '60',  'SolarWinds poll interval seconds'),
    ('lan_alert_limit',   '100', 'Max alerts fetched per SolarWinds cycle')
) AS source ([key], [value], description)
ON target.[key] = source.[key]
WHEN NOT MATCHED THEN
    INSERT ([key], [value], description)
    VALUES (source.[key], source.[value], source.description);
GO

-- =============================================================================
-- Permissions for application account
-- =============================================================================
IF EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'gbs_app')
BEGIN
    GRANT SELECT, INSERT, DELETE ON dbo.lan_metrics           TO gbs_app;
    GRANT SELECT, INSERT, DELETE ON dbo.lan_country_snapshots TO gbs_app;
    GRANT SELECT                  ON dbo.sw_country_groups     TO gbs_app;
    PRINT 'Permissions granted to gbs_app on LAN tables.';
END
GO

-- Retention -- add to existing nightly job:
-- DELETE FROM dbo.lan_metrics WHERE ingested_at < DATEADD(DAY, -90, GETUTCDATE());
-- DELETE FROM dbo.lan_country_snapshots WHERE ingested_at < DATEADD(DAY, -90, GETUTCDATE());

PRINT 'GBS Health database -- LAN pillar tables initialised successfully.';
GO
