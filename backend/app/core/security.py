"""
Security utilities -- shared across all pillars.

Centralises:
  - Input sanitisation for any text displayed in the dashboard
  - Rate limiting state (simple in-memory counter for POC)
  - Security header middleware helper
  - Log sanitisation (credential scrubbing from log messages)

All functions are pure -- no side effects except logging.
Import from here rather than duplicating sanitisation logic in each module.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ------ Characters permitted in country/group name inputs ---------------------------------------------------------------------------
# Used server-side to validate scope-derived country names before DB queries.
# Allows unicode letters for international country names.
_SAFE_TEXT_RE = re.compile(r"^[\w\s\-',\.]{1,128}$", re.UNICODE)

# ------ Regex patterns for credential scrubbing from log messages ---------------------------------------------------
_SCRUB_PATTERNS = [
    # Basic Auth header value
    (re.compile(r"Basic\s+[A-Za-z0-9+/=]{8,}"), "Basic [REDACTED]"),
    # Passwords in URLs
    (re.compile(r"(https?://[^:]+):([^@]{3,})@"), r"\1:[REDACTED]@"),
    # pyodbc connection strings
    (re.compile(r"(PWD=)[^;]+"), r"\1[REDACTED]"),
    (re.compile(r"(Password=)[^;]+", re.IGNORECASE), r"\1[REDACTED]"),
    # SQLAlchemy URLs
    (re.compile(r"(mssql\+pyodbc://[^:]+:)[^@]+@"), r"\1[REDACTED]@"),
]


def sanitise_log_message(message: str) -> str:
    """
    Scrub credential patterns from a string before logging.
    Apply to exception messages before they reach the log handler.
    """
    for pattern, replacement in _SCRUB_PATTERNS:
        message = pattern.sub(replacement, message)
    return message


def is_safe_text(value: str) -> bool:
    """
    Validate that a text value contains only safe characters.
    Used to validate country names and group names from scope parameters
    before they are compared against DB values.

    Permits: unicode word characters, spaces, hyphens, apostrophes,
             commas, periods. Max 128 characters.
    """
    if not value or not isinstance(value, str):
        return False
    return bool(_SAFE_TEXT_RE.match(value.strip()))


def sanitise_scope_part(value: str) -> Optional[str]:
    """
    Sanitise the value part of a scope parameter
    (the part after 'group:' or 'country:').

    Returns sanitised string or None if input is unsafe.
    DB lookup is always parameterised -- this is a defence-in-depth check.
    """
    if not value:
        return None
    stripped = value.strip()
    if not stripped or len(stripped) > 128:
        return None
    if not is_safe_text(stripped):
        logger.warning(
            f"Security: rejected unsafe scope value: "
            f"{repr(stripped[:32])}"
        )
        return None
    return stripped


# ------ Security response headers ---------------------------------------------------------------------------------------------------------------------------------------------------
# Applied via FastAPI middleware in main.py
SECURITY_HEADERS = {
    "X-Content-Type-Options":  "nosniff",
    "X-Frame-Options":         "DENY",
    "X-XSS-Protection":        "1; mode=block",
    "Referrer-Policy":         "strict-origin-when-cross-origin",
    "Cache-Control":           "no-store",
    # Content-Security-Policy -- tighten in production
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "   # needed for React inline styles
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    ),
}
