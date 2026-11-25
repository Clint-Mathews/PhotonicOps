"""Per-sensor stateful DSP pipeline: Kalman smoothing -> baseline
subtraction -> spike detection. Instantiated once and shared across all
sensors streaming over the UDS transport; internal state is keyed
by sensor_id so concurrent sensors don't corrupt each other's filter
histoyr (mirrors the per-sensor sharding direction, requires on the Go ring buffer)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock

import numpy as np

from src.dsp.exceptions import MismatchedFrameLengthError
from src.dsp.kalman import KalmanFilter1D, subtract_baseline
from src.dsp.spike_detector import SpikeReport, detect_spikes
from src.observability.metrics import DSP_PROCESS_SECONDS, DSP_SPIKES_TOTAL

log = logging.getLogger(__name__)

@dataclass(frozen=True)
class FrameResult:
    sensor_id: str
    raw: np.ndarray
    filtered: np.ndarray
    baseline_removed: np.ndarray
    spikes: SpikeReport
    window_start_ns: int

@dataclass
class _SensorMetrics:
    total_batches: int = 0
    total_spikes: int = 0

class DSPPipeline:
    def __init__(
        self,
        spike_threshold_pm_per_s: float = 500.0,
        baseline_window: int = 25,
    ) -> None:
        self._kalman = KalmanFilter1D()
        self._spike_threshold = spike_threshold_pm_per_s
        self._baseline_window = baseline_window
        self._metrics: dict[str, _SensorMetrics] = {}
        self._lock = RLock()

    def process(
        self,
        sensor_id: str,
        wavelengths: np.ndarray,
        timestamps: np.ndarray,
        window_duration_ms: float,
        window_start_ns: int = 0,
    ) -> FrameResult:
        with DSP_PROCESS_SECONDS.time(), self._lock:
            if wavelengths.shape != timestamps.shape:
                raise MismatchedFrameLengthError(
                    f"sensor {sensor_id!r}: {wavelengths.shape} wavelengths vs {timestamps.shape} timestamps"
                )
            raw = wavelengths.copy()
            filtered = self._kalman.filter_batch(sensor_id, wavelengths)
            baseline_removed = subtract_baseline(filtered, self._baseline_window)
            spikes = detect_spikes(sensor_id, filtered, timestamps, self._spike_threshold)

            DSP_SPIKES_TOTAL.labels(sensor_id=sensor_id).inc(spikes.spike_count)
            metrics = self._metrics.setdefault(sensor_id, _SensorMetrics())
            metrics.total_batches += 1
            metrics.total_spikes += spikes.spike_count
            if spikes.has_anomaly:
                log.warning(
                    "sensor=%s spike_count=%d window_ms=%.2f",
                    sensor_id, spikes.spike_count, window_duration_ms,
                )
            return FrameResult(
                sensor_id, raw, filtered, baseline_removed, spikes, window_start_ns
            )

    def false_positive_rate(self, sensor_id: str) -> float:
        """Spikes flagged per batch, for the Phase Gate 2A false-positibve
        record against the mock sensor's known-clean windows."""
        metrics = self._metrics.get(sensor_id)
        if metrics is None or metrics.total_batches == 0:
            return 0.0
        return metrics.total_spikes / metrics.total_batches
