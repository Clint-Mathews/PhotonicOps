"""
ipc.client
----------
Unix domain socket gRPC server that receives FrameBatches from the Go ingestion
engine and forwards them to the DSP pipeline as NumPy arrays.
The server runs in a background ThreadPoolExecutor so the main process thread
can remain free for other work (health checks, signal handling, etc.).
"""
from __future__ import annotations

import logging
from concurrent import futures
from datetime import datetime, timezone
from queue import Empty, Full, Queue
from threading import Event, Thread
from typing import TYPE_CHECKING, Iterator

import grpc
import numpy as np

from pb import telemetry_pb2, telemetry_pb2_grpc
from src.agent.incident_feed import record_outcome
from src.agent.safety import evaluate
from src.agent.schema import TriageOutcome, TriageStatus
from src.httpapi.server import LatestWindowStore

if TYPE_CHECKING:
    from src.dsp.pipeline import DSPPipeline

SOCKET_PATH = "/tmp/photonicops-dsp.sock"
log = logging.getLogger(__name__)


class TriageDispatcher:
    """Run slow local-LLM calls off the gRPC worker threads."""

    def __init__(self, maxsize: int = 32) -> None:
        self._queue: Queue[tuple[str, int, list[float]]] = Queue(maxsize=maxsize)
        self._stop = Event()
        self._thread = Thread(target=self._run, name="triage-dispatcher", daemon=True)
        self._thread.start()

    def enqueue(self, sensor_id: str, window_start_ns: int, values: list[float]) -> None:
        try:
            self._queue.put_nowait((sensor_id, window_start_ns, values))
        except Full:
            log.error("triage queue full; anomaly requires manual review outside the live queue")
            try:
                record_outcome(
                    TriageOutcome(
                        status=TriageStatus.REQUIRES_MANUAL_REVIEW,
                        decision=None,
                        reason="triage queue saturated",
                        sensor_id=sensor_id,
                        window_start_ns=window_start_ns,
                        evaluated_at=datetime.now(timezone.utc),
                    )
                )
            except OSError:
                log.exception("could not persist triage queue saturation incident")

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                sensor_id, window_start_ns, values = self._queue.get(timeout=0.2)
            except Empty:
                continue
            try:
                evaluate(sensor_id, window_start_ns, values)
            finally:
                self._queue.task_done()

class _DSPServicer(telemetry_pb2_grpc.DSPServiceServicer):
    """Receives FrameBatches from Go and dispatches them to the DSP pipeline."""
    def __init__(
        self,
        pipeline: DSPPipeline,
        latest_windows: LatestWindowStore,
        triage: TriageDispatcher,
    ) -> None:
        self._pipeline = pipeline
        self._latest_windows = latest_windows
        self._triage = triage

    def StreamBatches(
        self, 
        request_iterator: Iterator[telemetry_pb2.FrameBatch],
        context: grpc.ServicerContext,
        ) -> telemetry_pb2.DSPAck:
        for batch in request_iterator:
            # Convert the repeated protobuf field to NumPy in a single vectorised
            wavelengths = np.array(
                [f.wavelength_shift for f in batch.frames], dtype=np.float64
            )
            timestamps = np.array(
                [f.timestamp for f in batch.frames], dtype=np.int64
            )
            result = self._pipeline.process(
                sensor_id=batch.sensor_id,
                wavelengths=wavelengths,
                timestamps=timestamps,
                window_duration_ms=batch.window_duration_ms,
                window_start_ns=batch.window_start_ns,
            )
            self._latest_windows.update(result)
            if result.spikes.has_anomaly:
                self._triage.enqueue(
                    batch.sensor_id,
                    batch.window_start_ns,
                    wavelengths.tolist(),
                )
        return telemetry_pb2.DSPAck(accepted=True)

def serve(
    pipeline: DSPPipeline,
    latest_windows: LatestWindowStore | None = None,
    triage: TriageDispatcher | None = None,
) -> grpc.Server:
    """Bind the Unix socket and start the gRPC server in a thread pool.
    Returns the Server instance so the caller can block on server.wait_for_termination()
    or call server.stop() on SIGTERM.
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    latest_windows = latest_windows or LatestWindowStore()
    triage = triage or TriageDispatcher()
    telemetry_pb2_grpc.add_DSPServiceServicer_to_server(
        _DSPServicer(pipeline, latest_windows, triage), server
    )
    server.add_insecure_port(f"unix:{SOCKET_PATH}")
    server.start()
    log.info("DSP IPC server listening on unix: %s", SOCKET_PATH)
    return server
