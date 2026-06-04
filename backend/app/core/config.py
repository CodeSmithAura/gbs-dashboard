from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Literal


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    # ------ Database ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # Separate fields so each value can be changed independently in .env
    # without having to reconstruct the full connection string.
    DB_HOST:     str = "localhost"
    DB_PORT:     int = 3306
    DB_NAME:     str = "gbs_health"
    DB_USER:     str = "gbs_app"
    DB_PASSWORD: str = "changeme"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?charset=utf8mb4"
        )

    # ------ Data source ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    DATA_SOURCE_TYPE:   Literal["file", "api"] = "file"
    DATA_SOURCE_FORMAT: Literal["csv", "json"] = "csv"

    # Windows-friendly default path --- override in .env with your actual path
    # Use forward slashes or double backslashes in .env values
    DATA_SOURCE_PATH: str = "C:/CustomProjects/dashboard/gbs/gbs-poc/data/aruba_health.csv"

    # ------ Phase 2 --- Aruba API (leave blank for POC) ---------------------------------------------------------------------------------------
    ARUBA_BASE_URL:    str = ""
    ARUBA_CLIENT_ID:   str = ""
    ARUBA_CLIENT_SECRET: str = ""
    ARUBA_CUSTOMER_ID: str = ""

    # ------ Polling ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    POLL_INTERVAL_SECONDS: int = 60

    # ------ Demo mode ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    DEMO_SAMPLES_PATH:    str = "C:/CustomProjects/dashboard/gbs/gbs-poc/data/realtimesamples"
    DEMO_INTERVAL_SECONDS: int = 30

    # ------ App ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    APP_NAME:    str = "GBS Service Health Dashboard"
    APP_VERSION: str = "0.1.0-poc"


settings = Settings()
