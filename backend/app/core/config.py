from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Literal


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql://gbs_user:gbs_pass@localhost:5432/gbs_health"

    # Data source — swap DATA_SOURCE_TYPE to "api" in Phase 2
    DATA_SOURCE_TYPE: Literal["file", "api"] = "file"
    DATA_SOURCE_PATH: str = "/app/data/aruba_health.csv"
    DATA_SOURCE_FORMAT: Literal["csv", "json"] = "csv"

    # Phase 2 — Aruba API (leave blank for POC)
    ARUBA_BASE_URL: str = ""
    ARUBA_CLIENT_ID: str = ""
    ARUBA_CLIENT_SECRET: str = ""
    ARUBA_CUSTOMER_ID: str = ""

    # Polling
    POLL_INTERVAL_SECONDS: int = 60

    # App
    APP_NAME: str = "GBS Service Health Dashboard"
    APP_VERSION: str = "0.1.0-poc"


settings = Settings()
