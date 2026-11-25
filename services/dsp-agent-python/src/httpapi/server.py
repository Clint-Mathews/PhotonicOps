"""Local-only dashboard API and bounded latest-window state."""
from __future__ import annotations

import asyncio
import logging
from threading import RLock
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from src.agent.incident_feed import acknowledge_incident, list_pending_reviews
from src.dsp.pipeline import FrameResult

log = logging.getLogger(__name__)


class LatestWindowStore:
    """Thread-safe latest result store bounded to a small number of sensors."""

    def __init__(self, max_sensors: int = 3, max_points: int = 200) -> None:
        self._max_sensors = max_sensors
        self._max_points = max_points
        self._lock = RLock()
        self._windows: dict[str, dict[str, Any]] = {}

    def update(self, result: FrameResult) -> None:
        with self._lock:
            if result.sensor_id not in self._windows and len(self._windows) >= self._max_sensors:
                oldest = next(iter(self._windows))
                del self._windows[oldest]
            self._windows[result.sensor_id] = self._serialize(result)

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._windows.values())

    def _serialize(self, result: FrameResult) -> dict[str, Any]:
        stride = max(1, result.raw.size // self._max_points)
        return {
            "sensor_id": result.sensor_id,
            "window_start_ns": result.window_start_ns,
            "raw": result.raw[::stride].tolist(),
            "filtered": result.filtered[::stride].tolist(),
            "baseline_removed": result.baseline_removed[::stride].tolist(),
            "has_anomaly": result.spikes.has_anomaly,
        }


def create_app(store: LatestWindowStore) -> FastAPI:
    app = FastAPI(title="PhotonicOps DSP API", docs_url=None, redoc_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["content-type"],
    )

    @app.get("/healthz")
    def healthz() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/incidents")
    def incidents() -> list[dict[str, Any]]:
        return [outcome.model_dump(mode="json") for outcome in list_pending_reviews()]

    @app.post("/incidents/{incident_id}/ack")
    def ack_incident(incident_id: str) -> dict[str, Any]:
        if not acknowledge_incident(incident_id):
            raise HTTPException(status_code=404, detail="incident not found")
        return {"ok": True, "id": incident_id}

    @app.websocket("/ws/signal")
    async def signal_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                windows = store.snapshot()
                if windows:
                    await websocket.send_json(windows[0])
                else:
                    await websocket.send_json({
                        "sensor_id": "",
                        "raw": [],
                        "filtered": [],
                        "baseline_removed": [],
                        "has_anomaly": False,
                    })
                await asyncio.sleep(1 / 30)
        except WebSocketDisconnect:
            return
        except RuntimeError:
            return

    return app
