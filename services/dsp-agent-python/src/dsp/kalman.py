"""1D steady-state Kalman filter + moving-average baseline subtraction.

Process the Go->Python telemetry IPC stream in vectorized
chunks. State (filter delay line, per sensor_id) perists across calls so
conservative FrameBatches from the same sensor produce a continous estimate 
rather than restarting from zero at every window boundry.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import lfilter, lfiltic

from src.dsp.exceptions import EmptyFrameBatchError, InvalidFilterParametersError

DEFAULT_PROCESS_VARIANCE = 1e-3  # 0.001
DEFAULT_MEASUREMENT_VARIANCE = 0.5
DEFAULT_BASELINE_WINDOW_SAMPLES = 25

class KalmanFilter1D:
    """Steady-state scalar Kalman filter for wavelength-shift smoothing.

    Assume a constant-signal process model (no control input) driven by
    Gaussian process noise `process_variance` and measurement noise
    `measurement_variance`. Maintains one delay-line state per sensor_id.
    """

    def __init__(
        self,
        process_variance: float = DEFAULT_PROCESS_VARIANCE,
        measurement_variance: float = DEFAULT_MEASUREMENT_VARIANCE,
        convergence_iters: int = 50,
    ) -> None:
        if process_variance <= 0 or measurement_variance <= 0:
            raise InvalidFilterParametersError(
                f"process_variance={process_variance}, measurement_variance={measurement_variance} "
                "must both be positive"
            )
        self._q = process_variance
        self._r = measurement_variance
        self._gain = self._solve_steady_state_gain(convergence_iters)
        self._b = np.array([self._gain])
        self._a = np.array([1.0, -(1.0 - self._gain)])
        self._zi: dict[str, np.ndarray] = {}

    def _solve_steady_state_gain(self, iters: int) -> float:
        """Iterate the scalar Riccati recursion to convergence. This loop is
        over `iters` (~50) scalar covariance updates at construction time,
        not over a data array, so it is outside the vectorization constraints.
        """
        p = self._q
        gain = 0.0
        for _ in range(iters):
            p_pred = p + self._q
            gain = p_pred / (p_pred + self._r)
            p = (1.0 - gain) * p_pred
        return float(gain)
    
    @property
    def gain(self) -> float:
        return self._gain
    
    def reset(self, sensor_id: str) -> None:
        """Drop carried state for a sensor (e.g. on reconnect after a gap)."""
        self._zi.pop(sensor_id, None)

    def filter_batch(self, sensor_id: str, wavelengths: np.ndarray) -> np.ndarray:
        if wavelengths.size == 0:
            raise EmptyFrameBatchError(f"empty wavelength array for sensor {sensor_id}")
        zi = self._zi.get(sensor_id)
        if zi is None:
            # No prior state: assume the filter was at rest on the first sample.
            zi = lfiltic(self._b, self._a, y=[wavelengths[0]])
        filtered, zf = lfilter(self._b, self._a, wavelengths, zi=zi)
        self._zi[sensor_id] = zf
        return filtered
    
def subtract_baseline(
    filtered: np.ndarray, window: int = DEFAULT_BASELINE_WINDOW_SAMPLES
) -> np.ndarray:
    """Remove slow thermal-drift baseline via a moving average.

    `uniform_filter1d` is a compiled vectorized call; `mode="nearest"`
    reflects edge samples rather than zero-padding, avoiding an artifical
    baseline dip at the start of each batch.
    """
    if window < 1:
        raise InvalidFilterParametersError(f"baseline window must be >= 1, got {window}")
    if filtered.size == 0:
        raise EmptyFrameBatchError("empty array passed to subtract_baseline")
    baseline = uniform_filter1d(filtered, size=window, mode="nearest")
    return filtered - baseline
    