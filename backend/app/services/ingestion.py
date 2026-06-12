"""
Wireless pillar data connector layer.

Two connectors share the same BaseConnector interface:
  FileConnector     -- reads CSV or JSON file (POC / demo mode)
  ArubaAPIConnector -- calls Aruba Central REST API (live production mode)

Switching between them: change DATA_SOURCE_TYPE in .env
  file -> FileConnector
  api  -> ArubaAPIConnector

Token management (ArubaAPIConnector):
  - On startup: exchanges refresh token for a new access token
  - Every 90 minutes: proactively refreshes before expiry
  - On 401 response: immediately refreshes and retries once
  - Refresh token itself expires after 14 days (Aruba default)
    -> Network team regenerates from Aruba Central portal
  - Future Option 2 (client_credentials): set ARUBA_CLIENT_SECRET
    and the connector switches to client_credentials grant automatically

Security:
  - Tokens stored in memory only, never written to disk or logs
  - All credential errors sanitised before logging
  - SSL verification on all Aruba API calls
"""

import csv
import json
import logging
import time
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

import httpx

from app.core.config import settings
from app.models.schemas import ArubaRawRecord

logger = logging.getLogger(__name__)


# ------ Base connector interface ---------------------------------------------------------------------------------------------------------------------------------------------------------

class BaseConnector(ABC):
    @abstractmethod
    def fetch(self) -> List[ArubaRawRecord]:
        """Fetch wireless health data. Returns list of ArubaRawRecord."""


# ------ File connector (POC / demo) ------------------------------------------------------------------------------------------------------------------------------------------------

class FileConnector(BaseConnector):
    """
    Reads wireless health data from a CSV or JSON file.
    Used for POC development and demo simulation.
    No network calls -- all data comes from disk.
    """

    def __init__(self, path: str, fmt: str):
        self._path = Path(path)
        self._fmt  = fmt.lower()

    def fetch(self) -> List[ArubaRawRecord]:
        try:
            if self._fmt == "json":
                return self._read_json()
            return self._read_csv()
        except FileNotFoundError:
            logger.error(f"Data file not found: {self._path}")
            return []
        except Exception as exc:
            logger.error(f"File connector error: {exc}")
            return []

    def _read_csv(self) -> List[ArubaRawRecord]:
        records = []
        with open(self._path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    records.append(ArubaRawRecord(**self._coerce(row)))
                except Exception as exc:
                    logger.warning(
                        f"Skipping invalid row site_id="
                        f"{row.get('site_id', '?')}: {exc}"
                    )
        logger.info(f"File connector: loaded {len(records)} records from CSV")
        return records

    def _read_json(self) -> List[ArubaRawRecord]:
        records = []
        with open(self._path, encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            try:
                records.append(ArubaRawRecord(**self._coerce(item)))
            except Exception as exc:
                logger.warning(f"Skipping invalid record: {exc}")
        logger.info(f"File connector: loaded {len(records)} records from JSON")
        return records

    @staticmethod
    def _coerce(row: dict) -> dict:
        int_fields = [
            "site_health_score", "ap_total", "ap_online", "ap_offline",
            "client_count", "auth_failures_1h", "active_alerts", "ssid_count",
        ]
        result = dict(row)
        for field in int_fields:
            if field in result and result[field] not in (None, ""):
                try:
                    result[field] = int(result[field])
                except (ValueError, TypeError):
                    result[field] = 0
        if "timestamp" in result and isinstance(result["timestamp"], str):
            result["timestamp"] = result["timestamp"].replace("Z", "+00:00")
        return result


# ------ Aruba API token manager ------------------------------------------------------------------------------------------------------------------------------------------------------------

class _ArubaTokenManager:
    """
    Manages Aruba Central OAuth 2.0 tokens.

    Flow A (refresh_token -- current):
      Uses ARUBA_REFRESH_TOKEN to obtain access tokens.
      Access token valid for ~2 hours. Refreshes every 90 minutes proactively.
      Refresh token valid for 14 days -- Network team regenerates from portal.

    Flow B (client_credentials -- future Option 2):
      Activated automatically when ARUBA_CLIENT_SECRET is set AND
      ARUBA_REFRESH_TOKEN is blank.
      Fully automatic -- no manual token management needed.

    Thread safety: _lock protects token state for concurrent fetch calls.
    """

    # Refresh 30 minutes before expiry to avoid edge cases
    _REFRESH_MARGIN_SECONDS = 30 * 60

    def __init__(self):
        self._access_token:    Optional[str]      = None
        self._token_expiry:    Optional[datetime]  = None
        self._refresh_token:   Optional[str]       = (
            settings.ARUBA_REFRESH_TOKEN or None
        )
        self._lock = threading.Lock()

    @property
    def _token_endpoint(self) -> str:
        return f"{settings.ARUBA_BASE_URL}/oauth2/token"

    def _use_client_credentials(self) -> bool:
        """True if we should use client_credentials flow instead of refresh."""
        return (
            bool(settings.ARUBA_CLIENT_SECRET)
            and not bool(settings.ARUBA_REFRESH_TOKEN)
        )

    def get_access_token(self) -> str:
        """
        Return a valid access token, refreshing if needed.
        Thread-safe -- safe to call from concurrent ingest cycles.
        """
        with self._lock:
            if self._needs_refresh():
                self._refresh()
            if not self._access_token:
                raise RuntimeError(
                    "Aruba access token unavailable. "
                    "Check ARUBA_REFRESH_TOKEN or ARUBA_CLIENT_SECRET in .env."
                )
            return self._access_token

    def _needs_refresh(self) -> bool:
        if not self._access_token:
            return True
        if not self._token_expiry:
            return True
        now = datetime.now(timezone.utc)
        return now >= (self._token_expiry - timedelta(
            seconds=self._REFRESH_MARGIN_SECONDS
        ))

    def _refresh(self) -> None:
        if self._use_client_credentials():
            self._refresh_client_credentials()
        else:
            self._refresh_with_token()

    def _refresh_client_credentials(self) -> None:
        """Option 2: client_credentials grant -- fully automatic."""
        logger.info("Aruba: refreshing token via client_credentials flow")
        data = {
            "client_id":     settings.ARUBA_CLIENT_ID,
            "client_secret": settings.ARUBA_CLIENT_SECRET,
            "grant_type":    "client_credentials",
        }
        self._execute_token_request(data)

    def _refresh_with_token(self) -> None:
        """Option 1: refresh_token grant -- requires 14-day refresh token."""
        if not self._refresh_token:
            raise RuntimeError(
                "No Aruba refresh token available. "
                "Set ARUBA_REFRESH_TOKEN in .env or provide "
                "ARUBA_CLIENT_SECRET for client_credentials flow."
            )
        logger.info("Aruba: refreshing access token via refresh_token flow")
        data = {
            "client_id":     settings.ARUBA_CLIENT_ID,
            "client_secret": settings.ARUBA_CLIENT_SECRET,
            "grant_type":    "refresh_token",
            "refresh_token": self._refresh_token,
        }
        self._execute_token_request(data)

    def _execute_token_request(self, data: dict) -> None:
        """Execute token request and update internal state."""
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    self._token_endpoint,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                resp.raise_for_status()
                payload = resp.json()

            self._access_token = payload["access_token"]
            expires_in = int(payload.get("expires_in", 7200))
            self._token_expiry = datetime.now(timezone.utc) + timedelta(
                seconds=expires_in
            )
            # Update refresh token if a new one is issued
            if "refresh_token" in payload:
                self._refresh_token = payload["refresh_token"]

            logger.info(
                f"Aruba: token refreshed successfully, "
                f"expires in {expires_in // 60} minutes"
            )
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Aruba token refresh failed: HTTP {exc.response.status_code}. "
                f"Check ARUBA_CLIENT_ID and ARUBA_REFRESH_TOKEN in .env."
            ) from None
        except Exception as exc:
            raise RuntimeError(
                f"Aruba token refresh error: {type(exc).__name__}"
            ) from None


# ------ Aruba API connector (live) ---------------------------------------------------------------------------------------------------------------------------------------------------

class ArubaAPIConnector(BaseConnector):
    """
    Fetches wireless health data from HPE Aruba Central REST API.

    Endpoints used:
      GET /monitoring/v2/aps              -- AP inventory and status
      GET /monitoring/v2/clients/count    -- connected client count per site
      GET /aiops/v2/sites/health          -- composite site health score
      GET /monitoring/v2/alerts           -- active wireless alerts

    Each Aruba site becomes one ArubaRawRecord -- same model as FileConnector.
    Field names match the CSV schema exactly so normaliser is unchanged.

    Pagination:
      Aruba API returns max 1000 records per call by default.
      offset/limit pagination used for large deployments.
    """

    _PAGE_LIMIT = 1000

    def __init__(self):
        self._token_mgr = _ArubaTokenManager()
        self._base_url  = settings.ARUBA_BASE_URL.rstrip("/")
        self._customer_id = settings.ARUBA_CUSTOMER_ID

    def _headers(self) -> dict:
        return {
            "Authorization":  f"Bearer {self._token_mgr.get_access_token()}",
            "Content-Type":   "application/json",
            **({"Customer-Id": self._customer_id} if self._customer_id else {}),
        }

    def _get(self, client: httpx.Client, path: str, params: dict = None) -> dict:
        """
        Execute a GET request with automatic token refresh on 401.
        Retries once after refreshing the token.
        """
        url = f"{self._base_url}{path}"
        for attempt in range(2):
            try:
                resp = client.get(
                    url,
                    params=params or {},
                    headers=self._headers(),
                )
                if resp.status_code == 401 and attempt == 0:
                    logger.warning(
                        "Aruba API: 401 received -- refreshing token and retrying"
                    )
                    # Force token refresh by clearing current token
                    self._token_mgr._access_token = None
                    continue
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"Aruba API error on {path}: HTTP {exc.response.status_code}"
                ) from None
            except Exception as exc:
                raise RuntimeError(
                    f"Aruba API connection error: {type(exc).__name__}"
                ) from None
        raise RuntimeError("Aruba API: failed after token refresh retry.")

    def _fetch_all_pages(
        self, client: httpx.Client, path: str, key: str
    ) -> List[dict]:
        """Fetch all pages from a paginated Aruba endpoint."""
        results = []
        offset  = 0
        while True:
            data  = self._get(client, path, {
                "limit":  self._PAGE_LIMIT,
                "offset": offset,
            })
            items = data.get(key, [])
            results.extend(items)
            total = data.get("total", len(results))
            offset += len(items)
            if offset >= total or not items:
                break
        return results

    def fetch(self) -> List[ArubaRawRecord]:
        """
        Fetch wireless health data from Aruba Central API.
        Returns list of ArubaRawRecord -- one per site.
        """
        logger.info("Aruba API connector: starting fetch cycle")
        try:
            with httpx.Client(timeout=30.0) as client:
                aps      = self._fetch_aps(client)
                clients  = self._fetch_clients(client)
                health   = self._fetch_site_health(client)
                alerts   = self._fetch_alerts(client)
        except RuntimeError as exc:
            logger.error(f"Aruba API fetch failed: {exc}")
            return []

        records = self._merge_to_records(aps, clients, health, alerts)
        logger.info(f"Aruba API connector: built {len(records)} site records")
        return records

    def _fetch_aps(self, client: httpx.Client) -> List[dict]:
        """Fetch AP list with status per site."""
        aps = self._fetch_all_pages(client, "/monitoring/v2/aps", "aps")
        logger.info(f"Aruba API: fetched {len(aps)} APs")
        return aps

    def _fetch_clients(self, client: httpx.Client) -> dict:
        """Fetch client count per site. Returns dict keyed by site_id."""
        try:
            data = self._get(client, "/monitoring/v2/clients/count",
                             {"group_by": "site"})
            # Response: {"sites": [{"site_id": "...", "client_count": N}]}
            return {
                item["site_id"]: item.get("client_count", 0)
                for item in data.get("sites", [])
            }
        except Exception as exc:
            logger.warning(f"Aruba API: client count fetch failed: {exc}")
            return {}

    def _fetch_site_health(self, client: httpx.Client) -> dict:
        """
        Fetch AI Insights site health scores.
        Returns dict keyed by site_id.
        If endpoint not available (subscription tier), returns empty dict
        -- normaliser uses AP ratio as fallback.
        """
        try:
            data = self._get(client, "/aiops/v2/sites/health")
            return {
                item["site_id"]: item
                for item in data.get("sites", [])
            }
        except Exception as exc:
            logger.warning(
                f"Aruba API: site health fetch failed (AI Insights "
                f"may not be in subscription tier): {exc}"
            )
            return {}

    def _fetch_alerts(self, client: httpx.Client) -> List[dict]:
        """Fetch active wireless alerts."""
        try:
            data = self._get(
                client, "/monitoring/v2/alerts",
                {"state": "Open", "limit": 100}
            )
            return data.get("alerts", [])
        except Exception as exc:
            logger.warning(f"Aruba API: alerts fetch failed: {exc}")
            return []

    def _merge_to_records(
        self,
        aps:     List[dict],
        clients: dict,
        health:  dict,
        alerts:  List[dict],
    ) -> List[ArubaRawRecord]:
        """
        Merge AP, client, health, and alert data into ArubaRawRecord objects.
        Groups APs by site_id and aggregates to site-level totals.
        Field names match the CSV schema -- normaliser is unchanged.
        """
        # Group APs by site
        sites: dict = {}
        for ap in aps:
            sid = ap.get("site_id") or ap.get("swarm_id") or "unknown"
            sites.setdefault(sid, []).append(ap)

        # Build alert summary per site
        site_alerts: dict = {}
        for alert in alerts:
            sid = alert.get("site_id", "")
            site_alerts.setdefault(sid, []).append(alert)

        now = datetime.now(timezone.utc).isoformat()
        records = []

        for site_id, site_aps in sites.items():
            ap_total   = len(site_aps)
            ap_online  = sum(
                1 for ap in site_aps
                if ap.get("status", "").lower() in ("up", "online", "1")
            )
            ap_offline = ap_total - ap_online

            site_health_data = health.get(site_id, {})
            health_score     = int(
                site_health_data.get("health_score", 0) or 0
            )

            client_count   = clients.get(site_id, 0)
            site_alert_list = site_alerts.get(site_id, [])

            # Determine alert severity from site alert list
            severities      = [a.get("severity", "").lower()
                                for a in site_alert_list]
            if "critical" in severities:
                alert_severity = "critical"
            elif "major" in severities or "warning" in severities:
                alert_severity = "warning"
            elif severities:
                alert_severity = "info"
            else:
                alert_severity = "none"

            top_alert = site_alert_list[0] if site_alert_list else {}
            alert_desc = top_alert.get("description", "") or ""

            # Uplink quality from site health data
            uplink_map = {
                "good": "good", "fair": "fair",
                "poor": "poor", "down": "down",
                "": "good",
            }
            uplink_raw = str(
                site_health_data.get("wan_uplink_status", "good") or "good"
            ).lower()
            uplink_quality = uplink_map.get(uplink_raw, "good")

            # Site name -- Aruba returns it in various fields
            site_name = (
                site_health_data.get("site_name")
                or (site_aps[0].get("site") if site_aps else None)
                or site_id
            )

            try:
                records.append(ArubaRawRecord(
                    site_id=str(site_id),
                    site_name=str(site_name),
                    timestamp=now,
                    site_health_score=health_score,
                    ap_total=ap_total,
                    ap_online=ap_online,
                    ap_offline=ap_offline,
                    client_count=client_count,
                    auth_failures_1h=0,        # not available in v2 AP endpoint
                    active_alerts=len(site_alert_list),
                    alert_severity=alert_severity,
                    alert_description=alert_desc[:500] if alert_desc else "",
                    ssid_count=0,              # not available at site level
                    uplink_quality=uplink_quality,
                ))
            except Exception as exc:
                logger.warning(
                    f"Aruba API: skipping site {site_id}: {exc}"
                )

        return records


# ------ Connector factory ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def get_connector() -> BaseConnector:
    """
    Return the correct connector based on DATA_SOURCE_TYPE in .env.
    Single decision point -- all callers use this factory.
    """
    if settings.DATA_SOURCE_TYPE == "api":
        logger.info("Connector: using ArubaAPIConnector (live API mode)")
        return ArubaAPIConnector()
    logger.info(
        f"Connector: using FileConnector "
        f"(path={settings.DATA_SOURCE_PATH}, fmt={settings.DATA_SOURCE_FORMAT})"
    )
    return FileConnector(settings.DATA_SOURCE_PATH, settings.DATA_SOURCE_FORMAT)
