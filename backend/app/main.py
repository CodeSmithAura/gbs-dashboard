"""
GBS Service Health Dashboard -- FastAPI application entrypoint.

Starts two independent polling loops on startup:
  1. Wireless loop  -- reads CSV / Aruba API
  2. LAN loop       -- reads SolarWinds SWIS API

Security:
  - Security response headers applied via middleware (HSTS, CSP, X-Frame etc.)
  - CORS restricted to configured origins (permissive in POC -- tighten for prod)
  - No credentials in logs -- sanitise_log_message applied on exception paths
  - /health endpoint never exposes passwords or internal paths

Routers:
  /api/v1/wireless/*  -- Aruba wireless pillar
  /api/v1/lan/*       -- SolarWinds LAN pillar
  /api/v1/demo/*      -- demo simulation controls
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import check_db_connection, engine
from app.models.orm import Base
from app.api.wireless import router as wireless_router
from app.api.lan import router as lan_router
from app.api.demo import router as demo_router
from app.workers.scheduler import polling_loop as wireless_loop, get_state
from app.workers.lan_scheduler import lan_polling_loop, get_lan_state
from app.core.security import SECURITY_HEADERS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified.")

    wireless_task = asyncio.create_task(wireless_loop())
    lan_task      = asyncio.create_task(lan_polling_loop())
    logger.info("Wireless and LAN polling loops started.")

    yield

    for task, name in [(wireless_task, "wireless"), (lan_task, "LAN")]:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info(f"{name} polling loop stopped.")

    logger.info("Application shutdown complete.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "GBS Service Health Dashboard API -- "
        "Wireless (Aruba) and LAN (SolarWinds) pillars."
    ),
    lifespan=lifespan,
    # Disable docs in production -- enable for development only
    # docs_url=None, redoc_url=None,
)

# ------ Security headers middleware ------------------------------------------------------------------------------------------------------------------------------------------------
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    return response

# ------ CORS ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# POC: allow all origins.
# Production: restrict to the IIS frontend origin e.g. http://vm-hostname:3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],   # restrict to methods actually used
    allow_headers=["Content-Type", "Authorization"],
)

# ------ Routers ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
app.include_router(wireless_router)
app.include_router(lan_router)
app.include_router(demo_router)


@app.get("/health")
def health_check():
    """
    Application health -- covers both pillars and DB connectivity.
    Does NOT expose connection strings, passwords, or internal paths.
    """
    wireless = get_state()
    lan      = get_lan_state()
    return {
        "status":       "ok",
        "app":          settings.APP_NAME,
        "version":      settings.APP_VERSION,
        "db_connected": check_db_connection(),
        "wireless": {
            "data_source_type": settings.DATA_SOURCE_TYPE,
            "last_ingested_at": wireless.get("last_ingested_at"),
            "has_error":        wireless.get("error") is not None,
        },
        "lan": {
            "sw_host":          settings.SW_HOST,   # host only -- no credentials
            "sw_port":          settings.SW_PORT,
            "sw_connected":     lan.get("sw_connected"),
            "last_ingested_at": lan.get("last_ingested_at"),
            "has_error":        lan.get("error") is not None,
        },
        "is_poc": True,
    }


@app.get("/")
def root():
    return {
        "message": f"{settings.APP_NAME} API is running",
        "docs":    "/docs",
        "pillars": ["wireless", "lan"],
    }
