"""
Ingestion service — pluggable connector pattern.

Phase 1 (POC): reads CSV or JSON file.
Phase 2 upgrade: set DATA_SOURCE_TYPE=api, supply Aruba credentials.
All downstream code (normaliser, DB writer, API) is UNCHANGED on upgrade.
"""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from app.core.config import settings
from app.models.schemas import ArubaRawRecord

logger = logging.getLogger(__name__)


# ── Abstract connector interface ──────────────────────────────────────────────
class BaseConnector:
    def fetch(self) -> List[ArubaRawRecord]:
        raise NotImplementedError


# ── Phase 1: File connector ───────────────────────────────────────────────────
class FileConnector(BaseConnector):
    def __init__(self, path: str, fmt: str):
        self.path = Path(path)
        self.fmt = fmt

    def fetch(self) -> List[ArubaRawRecord]:
        if not self.path.exists():
            logger.error(f"Data file not found: {self.path}")
            return []
        try:
            if self.fmt == "csv":
                return self._read_csv()
            return self._read_json()
        except Exception as e:
            logger.error(f"File read error: {e}")
            return []

    def _read_csv(self) -> List[ArubaRawRecord]:
        records = []
        with open(self.path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    records.append(ArubaRawRecord(**self._coerce(row)))
                except Exception as e:
                    logger.warning(f"Skipping invalid row {row.get('site_id','?')}: {e}")
        logger.info(f"File connector: loaded {len(records)} records from {self.path.name}")
        return records

    def _read_json(self) -> List[ArubaRawRecord]:
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        records = []
        for item in data:
            try:
                records.append(ArubaRawRecord(**self._coerce(item)))
            except Exception as e:
                logger.warning(f"Skipping invalid record: {e}")
        logger.info(f"File connector: loaded {len(records)} records from {self.path.name}")
        return records

    @staticmethod
    def _coerce(row: dict) -> dict:
        """Cast string values from CSV to correct Python types."""
        int_fields = [
            "site_health_score", "ap_total", "ap_online", "ap_offline",
            "client_count", "auth_failures_1h", "active_alerts", "ssid_count",
        ]
        for f in int_fields:
            if f in row and row[f] != "":
                row[f] = int(row[f])
        if "timestamp" in row and isinstance(row["timestamp"], str):
            row["timestamp"] = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
        return row


# ── Phase 2 stub: Aruba API connector (not active in POC) ────────────────────
class ArubaAPIConnector(BaseConnector):
    """
    Phase 2 replacement for FileConnector.
    Authenticates with Aruba Central OAuth 2.0 and polls REST API.
    Activate by setting DATA_SOURCE_TYPE=api and supplying credentials.
    """
    def fetch(self) -> List[ArubaRawRecord]:
        # Phase 2 implementation goes here.
        # The Pydantic model (ArubaRawRecord) and all downstream code are unchanged.
        raise NotImplementedError("ArubaAPIConnector is Phase 2 scope. Set DATA_SOURCE_TYPE=file for POC.")


# ── Factory — the only place that knows which connector to use ────────────────
def get_connector() -> BaseConnector:
    if settings.DATA_SOURCE_TYPE == "api":
        return ArubaAPIConnector()
    return FileConnector(settings.DATA_SOURCE_PATH, settings.DATA_SOURCE_FORMAT)
