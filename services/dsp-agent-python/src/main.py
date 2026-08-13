"""Entrypoint for the DSP agent process."""
from __future__ import annotations

import logging
import signal
import sys
from types import FrameType

from src.dsp.pipeline import DSPPipeline
from src.ipc.client import serve

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
log = logging.getLogger(__name__)

def main() -> None:
    pipeline = DSPPipeline()
    server = serve(pipeline)

    def _handle_shutdown(signum:int, _frame: FrameType | None) -> None:
        log.info("received signal %d, shutting down DSP IPC server", signum)
        server.stop(grace=5)

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)
    server.wait_for_termination()

if __name__=="__main__":
    sys.exit(main())