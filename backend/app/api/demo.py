from fastapi import APIRouter
from typing import Optional

from app.services.demo_runner import start_demo, stop_demo, get_demo_state

router = APIRouter(prefix="/api/v1/demo", tags=["Demo"])


@router.post("/start")
async def demo_start(interval: Optional[int] = None):
    """
    Start demo mode — cycles through snapshots in DEMO_SAMPLES_PATH.
    interval: seconds between snapshots (overrides DEMO_INTERVAL_SECONDS).
    """
    return await start_demo(interval=interval)


@router.post("/stop")
def demo_stop():
    """Stop demo mode and return to normal polling."""
    return stop_demo()


@router.get("/status")
def demo_status():
    """Return current demo state."""
    return get_demo_state()
