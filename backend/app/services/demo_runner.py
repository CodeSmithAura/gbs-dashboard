"""
Demo runner service.

Cycles through CSV snapshots in DEMO_SAMPLES_PATH on a configurable interval.
Runs as an asyncio Task alongside the normal polling loop.
"""

import asyncio
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.workers.scheduler import run_ingestion_cycle

logger = logging.getLogger(__name__)

_demo = {
    "running":         False,
    "current_index":   0,
    "total_snapshots": 0,
    "current_file":    None,
    "interval":        30,
    "snapshots":       [],
    "started_at":      None,
    "error":           None,
}

_demo_task: Optional[asyncio.Task] = None


def get_demo_state() -> dict:
    return {
        "running":          _demo["running"],
        "current_index":    _demo["current_index"],
        "total_snapshots":  _demo["total_snapshots"],
        "current_file":     _demo["current_file"],
        "interval_seconds": _demo["interval"],
        "started_at":       _demo["started_at"],
        "error":            _demo["error"],
        "snapshots":        [p.name for p in _demo["snapshots"]],
    }


def _load_snapshots() -> list:
    samples_dir = Path(settings.DEMO_SAMPLES_PATH)
    if not samples_dir.exists():
        raise FileNotFoundError(
            f"Demo samples folder not found: {samples_dir}. "
            f"Create it and copy snapshot CSV files into it."
        )
    files = sorted(samples_dir.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {samples_dir}.")
    return files


def _apply_snapshot(path: Path):
    """Copy snapshot over the active data file and trigger an ingest."""
    active = Path(settings.DATA_SOURCE_PATH)
    active.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, active)
    logger.info(f"Demo: applied snapshot {path.name}")
    run_ingestion_cycle()


async def _demo_loop(interval: int):
    """Async loop — one snapshot per interval, runs until cancelled."""
    global _demo_task
    _demo["running"]    = True
    _demo["started_at"] = datetime.now(timezone.utc).isoformat()
    _demo["error"]      = None

    try:
        snapshots = _demo["snapshots"]
        total     = len(snapshots)

        while _demo["running"]:
            idx  = _demo["current_index"] % total
            path = snapshots[idx]

            _demo["current_index"] = idx
            _demo["current_file"]  = path.name

            logger.info(f"Demo step {idx + 1}/{total}: {path.name}")

            try:
                _apply_snapshot(path)
            except Exception as e:
                _demo["error"] = str(e)
                logger.error(f"Demo snapshot apply failed: {e}")

            _demo["current_index"] = (idx + 1) % total
            await asyncio.sleep(interval)

    except asyncio.CancelledError:
        logger.info("Demo loop cancelled.")
    finally:
        _demo["running"]      = False
        _demo["current_file"] = None
        _demo_task            = None


async def start_demo(interval: Optional[int] = None) -> dict:
    """
    Start the demo. Must be awaited (async) so asyncio.create_task()
    is called from within the running event loop — avoids the
    asyncio.get_event_loop() DeprecationWarning/RuntimeError in Python 3.10+.
    """
    global _demo_task

    if _demo["running"]:
        return {"ok": False, "error": "Demo is already running. Stop it first."}

    try:
        snapshots = _load_snapshots()
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}

    _demo["snapshots"]       = snapshots
    _demo["total_snapshots"] = len(snapshots)
    _demo["current_index"]   = 0
    _demo["interval"]        = interval or settings.DEMO_INTERVAL_SECONDS

    # create_task() works correctly here because start_demo is awaited
    # from inside a FastAPI async route — the event loop is already running.
    _demo_task = asyncio.create_task(_demo_loop(_demo["interval"]))

    logger.info(
        f"Demo started: {len(snapshots)} snapshots, "
        f"interval={_demo['interval']}s, "
        f"folder={settings.DEMO_SAMPLES_PATH}"
    )
    return {
        "ok": True,
        "total_snapshots": len(snapshots),
        "interval_seconds": _demo["interval"],
    }


def stop_demo() -> dict:
    """Stop the running demo."""
    global _demo_task

    if not _demo["running"] and _demo_task is None:
        return {"ok": False, "error": "Demo is not running."}

    if _demo_task:
        _demo_task.cancel()

    _demo["running"]      = False
    _demo["current_file"] = None
    logger.info("Demo stopped.")
    return {"ok": True}
