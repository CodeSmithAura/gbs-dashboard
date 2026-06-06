"""
Application settings loaded from .env file.
All secrets and environment-specific values come from .env.
No defaults for credentials or paths -- application fails fast if missing.
"""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict, field_validator
from typing import Literal


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    # ------ MS SQL Server ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    DB_HOST:     str
    DB_PORT:     int = 1433
    DB_NAME:     str = "gbs_health"
    DB_USER:     str
    DB_PASSWORD: str
    DB_DRIVER:   str = "ODBC Driver 18 for SQL Server"

    @property
    def DATABASE_URL(self) -> str:
        driver = self.DB_DRIVER.replace(" ", "+")
        return (
            f"mssql+pyodbc://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?driver={driver}"
            f"&TrustServerCertificate=yes"
            f"&Encrypt=yes"
        )

    # ------ Wireless data source (Aruba / CSV) ------------------------------------------------------------------------------------------------------------
    DATA_SOURCE_TYPE:   Literal["file", "api"] = "file"
    DATA_SOURCE_FORMAT: Literal["csv", "json"] = "csv"
    DATA_SOURCE_PATH:   str
    DEMO_SAMPLES_PATH:  str

    ARUBA_BASE_URL:      str = ""
    ARUBA_CLIENT_ID:     str = ""
    ARUBA_CLIENT_SECRET: str = ""
    ARUBA_CUSTOMER_ID:   str = ""

    POLL_INTERVAL_SECONDS: int = 60
    DEMO_INTERVAL_SECONDS: int = 30

    # ------ SolarWinds SWIS API ---------------------------------------------------------------------------------------------------------------------------------------------------------
    # No defaults for credentials -- must be supplied in .env
    SW_HOST:     str
    SW_PORT:     int = 17774
    SW_USER:     str
    SW_PASSWORD: str

    # SSL verification -- False for self-signed cert (POC only)
    # Set to true path of CA cert file in production, e.g. /certs/sw.pem
    SW_VERIFY_SSL: str = "false"

    # Custom property field name on Orion.Nodes holding the country value.
    # Must match exactly what SWQL Studio shows under Orion.Nodes.CustomProperties
    SW_COUNTRY_PROPERTY: str = "Country"

    # Interface type filter. 6=Ethernet. Confirm in SWQL Studio for this deployment.
    SW_INTERFACE_TYPE: int = 6

    # Max alerts fetched per cycle. Overrides dashboard_config lan_alert_limit
    # if set here -- dashboard_config value takes precedence at runtime.
    SW_ALERT_LIMIT: int = 100

    # SolarWinds poll interval -- can be longer than wireless (API is remote)
    SW_POLL_INTERVAL_SECONDS: int = 60

    @property
    def SW_BASE_URL(self) -> str:
        return (
            f"https://{self.SW_HOST}:{self.SW_PORT}"
            f"/SolarWinds/InformationService/v3/Json"
        )

    @property
    def sw_verify(self):
        """
        Returns the ssl verify value for httpx/requests.
        'false' -> False (disable -- POC with self-signed cert)
        Any other string -> treated as CA cert file path
        """
        if self.SW_VERIFY_SSL.lower() == "false":
            return False
        return self.SW_VERIFY_SSL

    # ------ App ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    APP_NAME:    str = "GBS Service Health Dashboard"
    APP_VERSION: str = "0.1.0-poc"


settings = Settings()
