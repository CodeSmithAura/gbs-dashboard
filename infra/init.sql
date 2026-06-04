-- =============================================================================
-- GBS Service Health Dashboard -- Database Initialisation
-- Microsoft SQL Server 2017+ / Azure SQL
-- Run once using the gbs_admin (or DBA) account before starting the application.
-- Execute in SQL Server Management Studio (SSMS) or sqlcmd.
-- =============================================================================

-- =============================================================================
-- Create database (comment out if DBA has already created it)
-- =============================================================================
IF NOT EXISTS (
    SELECT name FROM sys.databases WHERE name = N'gbs_health'
)
BEGIN
    CREATE DATABASE gbs_health
        COLLATE SQL_Latin1_General_CP1_CI_AS;
    PRINT 'Database gbs_health created.';
END
GO

USE gbs_health;
GO

-- =============================================================================
-- wireless_metrics -- main time-series table
-- =============================================================================
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'dbo.wireless_metrics')
    AND type = N'U'
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
    PRINT 'Table wireless_metrics created.';
END
GO

-- Index for fast per-site lookups (latest record per site)
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_wireless_metrics_site_ingested'
    AND object_id = OBJECT_ID(N'dbo.wireless_metrics')
)
BEGIN
    CREATE NONCLUSTERED INDEX IX_wireless_metrics_site_ingested
        ON dbo.wireless_metrics (site_id ASC, ingested_at DESC);
    PRINT 'Index IX_wireless_metrics_site_ingested created.';
END
GO

-- Index for trend query (data_timestamp range scans)
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_wireless_metrics_data_timestamp'
    AND object_id = OBJECT_ID(N'dbo.wireless_metrics')
)
BEGIN
    CREATE NONCLUSTERED INDEX IX_wireless_metrics_data_timestamp
        ON dbo.wireless_metrics (data_timestamp ASC)
        INCLUDE (composite_score, ap_online_pct, client_count, ingested_at);
    PRINT 'Index IX_wireless_metrics_data_timestamp created.';
END
GO

-- =============================================================================
-- dashboard_config -- key-value configuration store
-- =============================================================================
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'dbo.dashboard_config')
    AND type = N'U'
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

-- Seed default thresholds
-- MERGE used for idempotency -- safe to re-run without duplicating rows
MERGE dbo.dashboard_config AS target
USING (VALUES
    ('score_green',   '72',   'Composite score threshold for Green status'),
    ('score_amber',   '55',   'Composite score threshold for Amber (below = Red)'),
    ('ap_pct_green',  '95',   'AP online % threshold for Green'),
    ('ap_pct_amber',  '85',   'AP online % threshold for Amber'),
    ('poll_interval', '60',   'Ingestion poll interval in seconds'),
    ('is_poc',        'true', 'Flag indicating POC mode (file-based data)')
) AS source ([key], [value], description)
ON target.[key] = source.[key]
WHEN NOT MATCHED THEN
    INSERT ([key], [value], description)
    VALUES (source.[key], source.[value], source.description);
GO

PRINT 'Default configuration seeded.';
GO

-- =============================================================================
-- Retention -- delete rows older than 90 days
-- Equivalent of TimescaleDB add_retention_policy()
--
-- Option A: Run manually or via SQL Server Agent Job (recommended).
-- Option B: Ask the DBA to schedule the statement below as a nightly job.
--
-- Statement to schedule:
--   DELETE FROM dbo.wireless_metrics
--   WHERE data_timestamp < DATEADD(DAY, -90, GETUTCDATE());
--
-- SQL Server Agent Job setup is left to the DBA team.
-- =============================================================================
PRINT 'NOTE: Schedule a nightly SQL Agent Job to run:';
PRINT '  DELETE FROM dbo.wireless_metrics WHERE data_timestamp < DATEADD(DAY, -90, GETUTCDATE())';
GO

-- =============================================================================
-- Grant permissions to application service account
-- Run this block as SA or a user with ALTER ANY USER privilege.
-- Replace the password placeholder with the actual password.
-- Replace the login host restriction as appropriate for your environment.
-- =============================================================================

-- Create login at server level (if it doesn't exist)
IF NOT EXISTS (
    SELECT 1 FROM sys.server_principals WHERE name = N'gbs_app'
)
BEGIN
    -- Replace 'changeme' with the actual password from the SQL team
    CREATE LOGIN gbs_app WITH PASSWORD = 'changeme',
        CHECK_POLICY = OFF,      -- disable complexity policy for POC
        CHECK_EXPIRATION = OFF;  -- disable password expiry for POC
    PRINT 'Login gbs_app created.';
END
GO

-- Create database user mapped to the login
IF NOT EXISTS (
    SELECT 1 FROM sys.database_principals WHERE name = N'gbs_app'
)
BEGIN
    CREATE USER gbs_app FOR LOGIN gbs_app;
    PRINT 'Database user gbs_app created.';
END
GO

-- Grant minimum required permissions
GRANT SELECT   ON dbo.wireless_metrics  TO gbs_app;
GRANT INSERT   ON dbo.wireless_metrics  TO gbs_app;
GRANT DELETE   ON dbo.wireless_metrics  TO gbs_app;
GRANT SELECT   ON dbo.dashboard_config  TO gbs_app;
GRANT INSERT   ON dbo.dashboard_config  TO gbs_app;
GO

PRINT 'Permissions granted to gbs_app.';
GO

PRINT 'GBS Health database initialised successfully.';
GO
