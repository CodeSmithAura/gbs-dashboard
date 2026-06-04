from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Literal
import urllib


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    # -- Database -- MS SQL Server (SQL Server Authentication) -----------------
    # All five fields are individually configurable in .env
    DB_HOST:     str = "localhost"
    DB_PORT:     int = 1433
    DB_NAME:     str = "gbs_health"
    DB_USER:     str = "gbs_app"
    DB_PASSWORD: str = "changeme"

    # ODBC Driver name must match exactly what is installed on the Windows VM.
    # Verify installed driver name with:
    #   python -c "import pyodbc; print(pyodbc.drivers())"
    # Common values:
    #   "ODBC Driver 18 for SQL Server"  <- recommended, latest
    #   "ODBC Driver 17 for SQL Server"  <- fallback if 18 not installed
    DB_DRIVER: str = "ODBC Driver 18 for SQL Server"

    @property
    def DATABASE_URL(self) -> str:
        # URL-encode the connection string components to handle special chars
        # in passwords safely
        params = (
            f"DRIVER={{{self.DB_DRIVER}}};"
            f"SERVER={self.DB_HOST},{self.DB_PORT};"
            f"DATABASE={self.DB_NAME};"
            f"UID={self.DB_USER};"
            f"PWD={self.DB_PASSWORD};"
            f"TrustServerCertificate=yes;"   # required for self-signed certs
            f"Encrypt=yes;"                  # enforce encrypted connection
        )
        return f"mssql+pyodbc:///?odbc_connect={urllib.parse.quote_plus(params)}"

    # -- Data source -----------------------------------------------------------
    DATA_SOURCE_TYPE:   Literal["file", "api"] = "file"
    DATA_SOURCE_FORMAT: Literal["csv", "json"] = "csv"

    # Use forward slashes in Windows paths -- Python handles them correctly
    DATA_SOURCE_PATH: str = "C:/CustomProjects/dashboard/gbs/gbs-poc/data/aruba_health.csv"

    # -- Phase 2 -- Aruba API (leave blank for POC) ----------------------------
    ARUBA_BASE_URL:      str = ""
    ARUBA_CLIENT_ID:     str = ""
    ARUBA_CLIENT_SECRET: str = ""
    ARUBA_CUSTOMER_ID:   str = ""

    # -- Polling ---------------------------------------------------------------
    POLL_INTERVAL_SECONDS: int = 60

    # -- Demo mode -------------------------------------------------------------
    DEMO_SAMPLES_PATH:     str = "C:/CustomProjects/dashboard/gbs/gbs-poc/data/realtimesamples"
    DEMO_INTERVAL_SECONDS: int = 30

    # -- App -------------------------------------------------------------------
    APP_NAME:    str = "GBS Service Health Dashboard"
    APP_VERSION: str = "0.1.0-poc"


settings = Settings()
