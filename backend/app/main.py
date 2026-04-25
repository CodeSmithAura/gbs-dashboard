import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import check_db_connection, engine
from app.models.orm import Base
from app.api.wireless import router as wireless_router
from app.workers.scheduler import polling_loop, get_state

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ready.")

    # Start asyncio polling loop as a background task
    task = asyncio.create_task(polling_loop())

    yield

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("Application shutdown complete.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="GBS Service Health Dashboard — Wireless Pillar POC",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(wireless_router)


@app.get("/health")
def health_check():
    state = get_state()
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "db_connected": check_db_connection(),
        "data_source_type": settings.DATA_SOURCE_TYPE,
        "last_ingested_at": state["last_ingested_at"],
        "ingestion_error": state["error"],
        "is_poc": True,
    }


@app.get("/")
def root():
    return {"message": f"{settings.APP_NAME} API is running", "docs": "/docs"}
