from __future__ import annotations

import numpy as np
import pytest

from src.dsp.exceptions import MismatchedFrameLengthError
from src.dsp.spike_detector import detect_spikes


def _make_timestamps(n: int, dt_ns: int = 100_000) -> np.ndarray:
    return (np.arange(n, dtype=np.int64) * dt_ns)


def test_detects_injected_bubble_spike() -> None:
    n = 1000
    wavelengths = np.full(n, 1500.0)
    wavelengths[500:] += 50.0  # step function: 50pm jump
    timestamps = _make_timestamps(n)

    report = detect_spikes("ring-01", wavelengths, timestamps, threshold_pm_per_s=1000.0)

    assert report.has_anomaly
    assert report.spike_count == 1


def test_smooth_signal_has_no_false_positive() -> None:
    n = 1000
    # A slow, smooth thermal drift (10pm over 0.1s = 100 pm/s)
    wavelengths = np.linspace(1500.0, 1500.0 + 10.0, n)
    timestamps = _make_timestamps(n)

    report = detect_spikes("ring-01", wavelengths, timestamps, threshold_pm_per_s=500.0)

    assert not report.has_anomaly


def test_mismatched_lengths_raise() -> None:
    with pytest.raises(MismatchedFrameLengthError):
        detect_spikes("ring-01", np.zeros(10), np.zeros(9))