"""Micro-bubble / cell-clog detection via first-derivative thresholding.

|dλ/dt| > threshold_pm_per_s flags a step-function anomaly. Operates on the
already Kalman-filtered siginal (post src/dsp/kalman.py) so thermal drift
doesn't inflate the derivative.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from src.dsp.exceptions import MismatchedFrameLengthError

DEFAULT_SPIKE_THRESHOLD_PM_PER_S = 500.0

@dataclass(frozen=True)
class SpikeReport:
    sensor_id: str
    spike_mask: np.ndarray # bool, len == len(wavelengths) - 1
    spike_timestamp_ns: np.ndarray # int64, timestamp of the later sample in each flagged pair
    derivative_pm_per_s: np.ndarray # float64, dλ/dt for every consecutive sample pair
    
    @property
    def has_anomaly(self) -> bool:
        return bool(self.spike_mask.any())

    @property
    def spike_count(self) -> int:
        return int(self.spike_mask.sum())

def detect_spikes(
    sensor_id: str,
    wavelengths: np.ndarray,
    timestamps_ns: np.ndarray,
    threshold_pm_per_s: float = DEFAULT_SPIKE_THRESHOLD_PM_PER_S,
) -> SpikeReport:
    if wavelengths.shape != timestamps_ns.shape:
        raise MismatchedFrameLengthError(
            f"sensor {sensor_id!r}.: wavelength shape {wavelengths.shape} != "
            f"timestamps shape {timestamps_ns.shape}"
        )
    if wavelengths.size <2:
        empty = np.zero(0)
        return SpikeReport(sensor_id, empty.astype(bool), empty.astype(np.int64), empty)
    
    d_lambda = np.diff(wavelengths)
    d_t_s = np.diff(timestamps_ns) /1e9
    # Duplicate timestamsp from a misbehaving sensor would otherwise divide by 
    # zero; treat that as an infinite-rate spike instead of raising/NaN-ing.
    derivative = np.divide(
        d_lambda, d_t_s, out=np.full_like(d_lambda, np.inf), where=d_t_s != 0
    )
    mask = np.abs(derivative) > threshold_pm_per_s
    return SpikeReport(
        sensor_id=sensor_id,
        spike_mask=mask,
        spike_timestamp_ns=timestamps_ns[1:][mask],
        derivative_pm_per_s=derivative,
    )

