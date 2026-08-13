import numpy as np
from src.dsp.kalman import KalmanFilter1D
from src.dsp.spike_detector import detect_spikes

def _make_timestamps(n: int, dt_ns: int = 100_000) -> np.ndarray:
    return (np.arange(n, dtype=np.int64) * dt_ns)

rng = np.random.default_rng(seed=1)
n = 1000
noisy_wavelengths = 1500.0 + rng.normal(0, 0.5, size=n)
timestamps = _make_timestamps(n)

kf = KalmanFilter1D()
smoothed = kf.filter_batch("ring-01", noisy_wavelengths)
report = detect_spikes("ring-01", smoothed, timestamps, threshold_pm_per_s=500.0)
print("Max deriv:", np.max(np.abs(report.derivative_pm_per_s)))
print("Has anomaly:", report.has_anomaly)
