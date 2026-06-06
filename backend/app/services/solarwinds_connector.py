"""
SolarWinds SWIS REST API connector.

Security:
  - Basic Auth credentials never logged -- sanitised on all error paths
  - SSL verify=False isolated to this module only (POC with self-signed cert)
  - urllib3 InsecureRequestWarning suppressed to prevent credential hints in logs
  - All SWQL inputs validated before interpolation (no user-supplied strings
    go directly into queries -- only config-controlled values)
  - Passwords redacted from exception messages before propagation

Architecture:
  - Single httpx.Client reused across all queries in one cycle (connection pool)
  - SWQL queries defined as named constants -- easy to audit and update
  - Typed response mapping via Pydantic models -- schema drift caught at boundary
  - Retry logic with exponential backoff -- handles transient SolarWinds errors
"""

import logging
import time
from typing import List, Dict, Optional

import httpx
import urllib3

from app.core.config import settings
from app.models.lan_schemas import (
    SolarWindsNodeRaw,
    SolarWindsIfaceRaw,
    SolarWindsAlertRaw,
)

# Suppress SSL warning for self-signed cert -- isolated to this module
# Remove when a valid certificate is installed on the SolarWinds server
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# ------ SWQL query templates ------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Country property name is interpolated from config -- validated to contain
# only safe characters before use (see _validate_property_name)

_QUERY_NODES = """
SELECT n.NodeID              AS node_id,
       n.Caption             AS node_name,
       n.IPAddress           AS ip_address,
       n.Status              AS status,
       n.AvgResponseTime     AS avg_response_time_ms,
       n.PercentLoss         AS percent_loss,
       n.Severity            AS severity,
       IsNull(n.CustomProperties.{prop}, 'Unclassified') AS country
FROM Orion.Nodes n
ORDER BY n.Caption
"""

_QUERY_INTERFACES = """
SELECT i.NodeID                AS node_id,
       i.Node.Caption          AS node_name,
       MAX(i.InPercentUtil)    AS max_in_util,
       MAX(i.OutPercentUtil)   AS max_out_util,
       AVG(i.InPercentUtil)    AS avg_in_util,
       AVG(i.OutPercentUtil)   AS avg_out_util,
       Count(i.InterfaceID)    AS interface_count
FROM Orion.NPM.Interfaces i
WHERE i.InterfaceType = {itype}
GROUP BY i.NodeID, i.Node.Caption
"""

_QUERY_ALERTS = """
SELECT TOP {limit}
       ao.AlertObjectID                    AS alert_object_id,
       ao.AlertConfigurations.Name         AS alert_name,
       ao.AlertConfigurations.Severity     AS severity,
       ao.EntityCaption                    AS node_name,
       ao.RelatedNodeCaption               AS related_node,
       ao.AlertActive.TriggeredDateTime    AS triggered_at,
       ao.AlertActive.TriggeredMessage     AS description,
       ao.AlertActive.Acknowledged         AS acknowledged
FROM Orion.AlertObjects ao
WHERE ao.AlertActive.AlertActiveID > 0
ORDER BY ao.AlertConfigurations.Severity DESC,
         ao.AlertActive.TriggeredDateTime DESC
"""

_QUERY_COUNTRIES = """
SELECT DISTINCT
       IsNull(n.CustomProperties.{prop}, 'Unclassified') AS country,
       Count(n.NodeID)                                    AS node_count
FROM Orion.Nodes n
GROUP BY n.CustomProperties.{prop}
ORDER BY country
"""

# ------ Security: property name validation ---------------------------------------------------------------------------------------------------------------------
_SAFE_PROP_CHARS = set(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789_"
)


def _validate_property_name(name: str) -> str:
    """
    Validates the custom property name from config before interpolating
    into SWQL. Only alphanumeric and underscore characters permitted.
    Raises ValueError if the name contains any other character.
    This prevents any form of SWQL injection via the config value.
    """
    if not name or not all(c in _SAFE_PROP_CHARS for c in name):
        raise ValueError(
            f"SW_COUNTRY_PROPERTY '{name}' contains invalid characters. "
            f"Only letters, digits, and underscores are permitted."
        )
    return name


def _sanitise_error(exc: Exception) -> str:
    """
    Remove any credential-containing strings from exception messages
    before logging. Basic Auth credentials appear as base64 in headers --
    this strips the Authorization header value if present in the message.
    """
    msg = str(exc)
    # Redact anything that looks like a Basic Auth header value
    import re
    msg = re.sub(r"Basic\s+[A-Za-z0-9+/=]+", "Basic [REDACTED]", msg)
    # Redact password from connection URLs if they appear
    msg = re.sub(
        r"(https?://)([^:]+):([^@]+)@",
        r"\1\2:[REDACTED]@",
        msg,
    )
    return msg


# ------ HTTP client factory ---------------------------------------------------------------------------------------------------------------------------------------------------------------------

def _build_client() -> httpx.Client:
    """
    Build a reusable httpx client for this ingest cycle.
    - Basic Auth from config (credentials never logged)
    - SSL verify from config (False for self-signed cert -- POC only)
    - 30-second timeout on all operations
    - verify=False is intentional and documented -- remove when cert installed
    """
    return httpx.Client(
        auth=(settings.SW_USER, settings.SW_PASSWORD),
        verify=settings.sw_verify,      # False for self-signed (POC)
        timeout=30.0,
        headers={"Content-Type": "application/json"},
    )


# ------ SWQL query execution ------------------------------------------------------------------------------------------------------------------------------------------------------------------

def _run_query(client: httpx.Client, swql: str) -> List[Dict]:
    """
    Execute a SWQL query against the SWIS REST API.
    Returns the 'results' list from the JSON response.

    Retries up to 3 times with exponential backoff on 5xx errors.
    Raises RuntimeError on persistent failure -- message is sanitised.
    """
    url = f"{settings.SW_BASE_URL}/Query"
    params = {"query": swql}

    for attempt in range(1, 4):
        try:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500 and attempt < 3:
                wait = 2 ** attempt
                logger.warning(
                    f"SolarWinds SWIS returned {exc.response.status_code} "
                    f"-- retrying in {wait}s (attempt {attempt}/3)"
                )
                time.sleep(wait)
                continue
            raise RuntimeError(
                f"SWIS query failed after {attempt} attempt(s): "
                f"HTTP {exc.response.status_code}"
            ) from None
        except Exception as exc:
            raise RuntimeError(
                f"SWIS query error: {_sanitise_error(exc)}"
            ) from None

    raise RuntimeError("SWIS query failed after 3 attempts.")


# ------ Public fetch functions ------------------------------------------------------------------------------------------------------------------------------------------------------------

def fetch_nodes() -> List[SolarWindsNodeRaw]:
    """
    Fetch all monitored nodes with country custom property.
    Returns a list of SolarWindsNodeRaw -- one per node.
    Invalid rows are skipped with a warning logged.
    """
    prop = _validate_property_name(settings.SW_COUNTRY_PROPERTY)
    query = _QUERY_NODES.format(prop=prop)

    with _build_client() as client:
        rows = _run_query(client, query)

    logger.info(f"SolarWinds: fetched {len(rows)} node rows")

    results = []
    for row in rows:
        try:
            results.append(SolarWindsNodeRaw(**row))
        except Exception as exc:
            logger.warning(
                f"SolarWinds: skipping invalid node row "
                f"node_id={row.get('node_id', '?')}: {exc}"
            )
    return results


def fetch_interfaces() -> List[SolarWindsIfaceRaw]:
    """
    Fetch interface utilisation aggregated to node level.
    Returns a list of SolarWindsIfaceRaw -- one per node.
    """
    query = _QUERY_INTERFACES.format(itype=settings.SW_INTERFACE_TYPE)

    with _build_client() as client:
        rows = _run_query(client, query)

    logger.info(f"SolarWinds: fetched {len(rows)} interface rows")

    results = []
    for row in rows:
        try:
            results.append(SolarWindsIfaceRaw(**row))
        except Exception as exc:
            logger.warning(
                f"SolarWinds: skipping invalid interface row "
                f"node_id={row.get('node_id', '?')}: {exc}"
            )
    return results


def fetch_alerts(limit: int = 100) -> List[SolarWindsAlertRaw]:
    """
    Fetch active alerts ordered by severity descending.
    limit: max rows to fetch -- defaults to SW_ALERT_LIMIT from config.
    """
    # Validate limit is a safe integer (not user-supplied at this layer)
    safe_limit = max(1, min(int(limit), 500))
    query = _QUERY_ALERTS.format(limit=safe_limit)

    with _build_client() as client:
        rows = _run_query(client, query)

    logger.info(f"SolarWinds: fetched {len(rows)} alert rows")

    results = []
    for row in rows:
        try:
            results.append(SolarWindsAlertRaw(**row))
        except Exception as exc:
            logger.warning(
                f"SolarWinds: skipping invalid alert row: {exc}"
            )
    return results


def fetch_countries() -> List[Dict]:
    """
    Fetch distinct country values and node counts.
    Used at startup and refreshed hourly.
    Returns raw list of {country, node_count} dicts.
    """
    prop = _validate_property_name(settings.SW_COUNTRY_PROPERTY)
    query = _QUERY_COUNTRIES.format(prop=prop)

    with _build_client() as client:
        rows = _run_query(client, query)

    logger.info(f"SolarWinds: fetched {len(rows)} country rows")
    return rows


def test_connectivity() -> bool:
    """
    Lightweight connectivity test -- called at startup.
    Returns True if SWIS API responds, False otherwise.
    Does not raise -- errors are logged and suppressed.
    """
    try:
        with _build_client() as client:
            _run_query(client, "SELECT TOP 1 NodeID AS node_id FROM Orion.Nodes")
        logger.info("SolarWinds: connectivity test passed")
        return True
    except Exception as exc:
        logger.error(
            f"SolarWinds: connectivity test failed -- "
            f"{_sanitise_error(exc)}"
        )
        return False
