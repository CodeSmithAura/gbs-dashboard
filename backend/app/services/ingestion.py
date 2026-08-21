"""
Wireless pillar data connector layer.

Two connectors share the same BaseConnector interface:
  FileConnector     -- reads CSV or JSON file (POC / demo mode)
  ArubaAPIConnector -- calls Aruba Central REST API (live production mode)

Switching between them: change DATA_SOURCE_TYPE in .env
  file -> FileConnector
  api  -> ArubaAPIConnector

Token management (ArubaAPIConnector):
  - Uses the OAuth 2.0 refresh_token grant exclusively. Aruba Central's
    /oauth2/token endpoint only supports authorization_code (one-time,
    interactive) and refresh_token (renewal) -- it has no client_credentials
    grant, so there is no fully-unattended alternative to bootstrap from.
  - One-time manual bootstrap: a human generates the first access/refresh
    token pair via the Central UI (System Apps & Tokens) and sets
    ARUBA_REFRESH_TOKEN in .env.
  - After that it's fully automatic: every refresh call both renews the
    access token and rotates in a new refresh token. Aruba only revokes a
    refresh token if it goes unused for 15 consecutive days, so refreshing
    well inside that window (every 90 minutes, proactively, plus
    immediately on any 401) keeps the connector authenticated indefinitely
    without further manual steps.
  - Each newly-issued refresh token is persisted back to .env so a service
    restart picks up the latest one instead of the one that was rotated out.
  - If the service is ever down for more than 15 days, Aruba revokes the
    token and the one-time manual bootstrap must be repeated.

Security:
  - Access token stored in memory only, never written to disk or logs.
    The refresh token IS persisted to plaintext .env on every rotation
    (see _persist_refresh_token) -- tracked as a known gap in
    docs/STATUS.md ("Credential storage"), not yet remediated.
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

import os

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
    Manages Aruba Central OAuth 2.0 tokens via the refresh_token grant.

    This is the only grant Aruba Central's /oauth2/token endpoint supports
    for renewal (there is no client_credentials grant on this API -- see
    module docstring). ARUBA_REFRESH_TOKEN must be seeded once via a manual
    authorization_code exchange in the Central UI (System Apps & Tokens);
    from then on this class refreshes automatically:
      - Access token valid for ~2 hours; refreshed every 90 minutes
        proactively, and immediately on any 401.
      - Each refresh rotates in a new refresh token, which is persisted to
        .env so the chain survives restarts.
      - Aruba revokes the refresh token only after 15 days of no use --
        refreshing this often never comes close to that window.

    Thread safety: _lock protects token state for concurrent fetch calls.
    """

    # Refresh 30 minutes before expiry to avoid edge cases
    _REFRESH_MARGIN_SECONDS = 30 * 60

    def __init__(self):
        self._access_token:    Optional[str]      = None
        self._token_expiry:    Optional[datetime]  = None
        self._refresh_token:   Optional[str]       = (
            self._real_value(settings.ARUBA_REFRESH_TOKEN)
        )
        self._lock = threading.Lock()

        if settings.ARUBA_REFRESH_TOKEN and not self._refresh_token:
            logger.warning(
                "Aruba: ARUBA_REFRESH_TOKEN looks like a placeholder "
                f"({settings.ARUBA_REFRESH_TOKEN!r}) and is being treated "
                "as unset. Paste the real refresh token issued by Aruba "
                "Central (System Apps & Tokens), or the connector will "
                "have no token to refresh with."
            )

    @staticmethod
    def _real_value(value: Optional[str]) -> Optional[str]:
        """
        Returns value if it looks like a real configured secret, else None.
        Treats blank/whitespace and template placeholders like
        '<refresh_token_from_portal>' or 'your-client-secret' as unset, so a
        forgotten placeholder in .env can't silently select the wrong OAuth
        grant type.
        """
        if not value:
            return None
        v = value.strip()
        if not v:
            return None
        if v.startswith("<") and v.endswith(">"):
            return None
        if v.lower().startswith("your-"):
            return None
        return value

    @property
    def _token_endpoint(self) -> str:
        return f"{settings.ARUBA_BASE_URL}/oauth2/token"

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
                    "Check ARUBA_REFRESH_TOKEN in .env."
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
        """
        Refresh via the refresh_token grant -- the only renewal grant
        Aruba Central's /oauth2/token endpoint supports.
        """
        if not self._refresh_token:
            raise RuntimeError(
                "No Aruba refresh token available. Set ARUBA_REFRESH_TOKEN "
                "in .env with a token generated via the Central UI "
                "(System Apps & Tokens)."
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
                self._persist_refresh_token(payload["refresh_token"])


            logger.info(
                f"Aruba: token refreshed successfully, "
                f"expires in {expires_in // 60} minutes"
            )
        except httpx.HTTPStatusError as exc:
            body = ""
            try:
                body = exc.response.text
            except Exception:
                pass
            logger.error(
                f"Aruba token refresh failed: HTTP {exc.response.status_code} "
                f"body={repr(body)}"
            )
            raise RuntimeError(
                f"Aruba token refresh failed: HTTP {exc.response.status_code}"
            ) from None
        except Exception as exc:
            import traceback
            logger.error(
                f"Aruba token refresh error:\n{traceback.format_exc()}"
            )
            raise RuntimeError(
                f"Aruba token refresh error: {type(exc).__name__}: {exc}"
            ) from None
    def _persist_refresh_token(self, new_token: str) -> None:
        try:
            from app.core.config import settings
            import re
            env_path = Path(settings.ENV_FILE_PATH) if settings.ENV_FILE_PATH else None
            if not env_path or not env_path.exists():
                # Fallback: search upward from this file
                candidate = Path(__file__).resolve().parent
                for _ in range(6):
                    if (candidate / ".env").exists():
                        env_path = candidate / ".env"
                        break
                    candidate = candidate.parent
            if not env_path or not env_path.exists():
                logger.warning("Aruba: .env not found, refresh token not persisted")
                return
            content = env_path.read_text(encoding="utf-8")
            content = re.sub(
                r"^ARUBA_REFRESH_TOKEN=.*$",
                f"ARUBA_REFRESH_TOKEN={new_token}",
                content,
                flags=re.MULTILINE,
            )
            env_path.write_text(content, encoding="utf-8")
            logger.info(f"Aruba: new refresh token persisted to {env_path}")
        except Exception as exc:
            logger.warning(f"Aruba: could not persist refresh token: {exc}")

# ------ Aruba API connector (live) ---------------------------------------------------------------------------------------------------------------------------------------------------
_TOKEN_MANAGER = None

class ArubaAPIConnector(BaseConnector):
    """
    Fetches wireless health data from HPE Aruba Central REST API.

    Endpoints used:
      GET /monitoring/v2/aps          -- AP inventory and status
      GET /monitoring/v2/clients      -- connected clients (grouped to
                                          per-site counts client-side --
                                          there is no site-count endpoint)
      GET /central/v1/notifications   -- active alerts ("List Notification
                                          API"; NOT /monitoring/v2/alerts,
                                          which does not exist)
      GET /aiops/v2/sites/health      -- best-effort composite site health
                                          score. This path does not exist on
                                          Aruba's real API (their AIOps API
                                          is per-AP/global insights, not a
                                          bulk per-site score) -- kept as a
                                          best-effort call that fails soft;
                                          normaliser falls back to AP ratio.
                                          Needs a redesign if real site-level
                                          health scoring is required later.

    Each Aruba site becomes one ArubaRawRecord -- same model as FileConnector.
    Field names match the CSV schema exactly so normaliser is unchanged.

    Pagination:
      Aruba API returns max 1000 records per call by default.
      offset/limit pagination used for large deployments.
    """

    _PAGE_LIMIT = 1000
    _MAX_PAGES  = 50  # safety cap -- 50k records at _PAGE_LIMIT=1000


    def __init__(self):
        global _TOKEN_MANAGER
        if _TOKEN_MANAGER is None:
            _TOKEN_MANAGER = _ArubaTokenManager()
        self._token_mgr = _TOKEN_MANAGER
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
        self, client: httpx.Client, path: str, key,
        extra_params: dict = None,
    ) -> List[dict]:
        """
        Fetch all pages from a paginated Aruba endpoint.

        `key` may be a single field name or a tuple of candidate field
        names tried in order -- used where the response envelope isn't
        confirmed from docs alone (e.g. notifications vs alerts). If none
        of the candidates are present on the first page, this logs the
        keys that ARE present instead of silently returning an empty list,
        so a wrong `key` guess is easy to spot from the logs.

        extra_params: static query params merged in on every page (e.g.
        {"state": "Open"}) -- offset/limit are always added by this method.

        Stops after _MAX_PAGES pages as a safety cap against a runaway
        `total`/offset from the API, logging a warning so a truncated
        result is visible rather than silent.
        """
        keys = (key,) if isinstance(key, str) else tuple(key)
        results = []
        offset = 0
        resolved_key = None
        first_page = True
        for page in range(self._MAX_PAGES):
            data = self._get(client, path, {
                "limit":  self._PAGE_LIMIT,
                "offset": offset,
                **(extra_params or {}),
            })
            if resolved_key is None:
                resolved_key = next((k for k in keys if k in data), None)
                if resolved_key is None:
                    if first_page:
                        logger.warning(
                            f"Aruba API: {path} response has none of {keys} "
                            f"-- top-level keys present: {list(data.keys())}"
                        )
                    break
            first_page = False
            items = data.get(resolved_key, [])
            results.extend(items)
            total = data.get("total", len(results))
            offset += len(items)
            if offset >= total or not items:
                break
        else:
            logger.warning(
                f"Aruba API: {path} hit the {self._MAX_PAGES}-page safety "
                f"cap ({len(results)} records fetched) -- result may be "
                f"truncated."
            )
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

    def _fetch_clients(self, client: httpx.Client) -> List[dict]:
        """
        Fetch connected clients. There is no per-site client-count
        endpoint on Aruba's real API (the previous /monitoring/v2/clients
        /count?group_by=site call 404s -- that combination doesn't exist).
        Instead fetch the raw client list from /monitoring/v2/clients, the
        same way APs are fetched, and let _merge_to_records() group them
        by site client-side.
        Best-effort like the other enrichment calls -- a failure here
        shouldn't abort the whole fetch cycle (AP data is still valid).
        """
        try:
            clients = self._fetch_all_pages(
                client, "/monitoring/v2/clients", "clients"
            )
            logger.info(f"Aruba API: fetched {len(clients)} clients")
            return clients
        except Exception as exc:
            logger.warning(f"Aruba API: client fetch failed: {exc}")
            return []

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
        """
        Fetch active alerts via the "List Notification API"
        (GET /central/v1/notifications) -- /monitoring/v2/alerts does not
        exist on Aruba's real API (that's what 404'd before).

        Paginated the same way as APs/clients via _fetch_all_pages -- a
        flat limit=100 call silently truncated alerts past the first page,
        which skews alert_severity/alert_count (and therefore composite
        score) on any site with more than 100 open alerts.
        """
        try:
            return self._fetch_all_pages(
                client, "/central/v1/notifications",
                ("notifications", "alerts"),
                extra_params={"state": "Open"},
            )
        except Exception as exc:
            logger.warning(f"Aruba API: alerts fetch failed: {exc}")
            return []

    def _merge_to_records(
        self,
        aps:     List[dict],
        clients: List[dict],
        health:  dict,
        alerts:  List[dict],
    ) -> List[ArubaRawRecord]:
        """
        Merge AP, client, health, and alert data into ArubaRawRecord objects.
        Groups APs and clients by site_id and aggregates to site-level
        totals. Field names match the CSV schema -- normaliser is unchanged.
        """
        # Group APs by site
        sites: dict = {}
        for ap in aps:
            sid = ap.get("site_id") or ap.get("swarm_id") or "unknown"
            sites.setdefault(sid, []).append(ap)

        # Group clients by site -- there's no per-site count endpoint, so
        # count them the same way APs are grouped. Field name for the site
        # identifier on a client record isn't confirmed from docs; falls
        # back the same way AP grouping does.
        client_counts: dict = {}
        for c in clients:
            sid = c.get("site_id") or c.get("swarm_id") or "unknown"
            client_counts[sid] = client_counts.get(sid, 0) + 1

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

            client_count   = client_counts.get(site_id, 0)
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
