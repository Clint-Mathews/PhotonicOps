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
from typing import TYPE_CHECKING, Iterator

import grpc
import numpy as np

from pb import telemetry_pb2, telemetry_pb2_grpc

if TYPE_CHECKING:
    from src.dsp.pipeline import DSPPipeline

SOCKET_PATH = "/tmp/photonicops-dsp.sock"
log = logging.getLogger(__name__)

class _DSPServicer(telemetry_pb2_grpc.DSPServiceServicer):
    """Receives FrameBatches from Go and dispatches them to the DSP pipeline."""
    def __init__(self, pipeline: DSPPipeline) -> None:
        self._pipeline = pipeline

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
            self._pipeline.process(
                sensor_id=batch.sensor_id,
                wavelengths=wavelengths,
                timestamps=timestamps,
                window_duration_ms=batch.window_duration_ms,
            )
        return telemetry_pb2.DSPAck(accepted=True)

def serve(pipeline: DSPPipeline) -> grpc.Server:
    """Bind the Unix socket and start the gRPC server in a thread pool.
    Returns the Server instance so the caller can block on server.wait_for_termination()
    or call server.stop() on SIGTERM.
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    telemetry_pb2_grpc.add_DSPServiceServicer_to_server(_DSPServicer(pipeline=pipeline),server)
    server.add_insecure_port(f"unix:{SOCKET_PATH}")
    server.start()
    log.info("DSP IPC server listening on unix: %s", SOCKET_PATH)
    return server
