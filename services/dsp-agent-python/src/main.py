"""Entrypoint for the DSP agent process."""
from __future__ import annotations

import logging
import signal
from threading import Thread
from types import FrameType

import uvicorn
from prometheus_client import start_http_server

from src.dsp.pipeline import DSPPipeline
from src.httpapi.server import LatestWindowStore, create_app
from src.ipc.client import TriageDispatcher, serve

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
log = logging.getLogger(__name__)

def main() -> None:
    pipeline = DSPPipeline()
    start_http_server(8001)
    latest_windows = LatestWindowStore()
    triage = TriageDispatcher()
    api_server = uvicorn.Server(
        uvicorn.Config(
            create_app(latest_windows),
            host="0.0.0.0",
            port=8000,
            log_level="info",
        )
    )
    api_server.install_signal_handlers = lambda: None
    Thread(target=api_server.run, name="dashboard-api", daemon=True).start()
    server = serve(pipeline, latest_windows, triage)


    def _handle_shutdown(signum: int, _frame: FrameType | None) -> None:
        log.info("received signal %d, shutting down DSP IPC server", signum)
        server.stop(grace=5)
        triage.stop()
        api_server.should_exit = True

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)
    server.wait_for_termination()

if __name__ == "__main__":
    main()
