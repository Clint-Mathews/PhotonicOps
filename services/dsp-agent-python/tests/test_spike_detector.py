"""Tests for the spike detector — checks it correctly finds anomalies and ignores normal signals."""
from __future__ import annotations

import numpy as np
import pytest

from src.dsp.exceptions import MismatchedFrameLengthError
from src.dsp.spike_detector import detect_spikes


def _make_timestamps(n: int, dt_ns: int = 100_000) -> np.ndarray:
    # Generate evenly spaced timestamps. Default interval is 100 µs,
    # which matches the 10,000 Hz sensor sampling rate.
    return (np.arange(n, dtype=np.int64) * dt_ns)


def test_detects_injected_bubble_spike() -> None:
    # Create a flat signal and inject one sudden jump at the midpoint.
    # This simulates a micro-bubble passing over the sensor and abruptly
    # shifting the wavelength reading by 50 pm.
    # The detector should flag exactly one spike at that jump point.
    n = 1000
    wavelengths = np.full(n, 1500.0)
    wavelengths[500:] += 50.0  # sudden +50 pm step at index 500
    timestamps = _make_timestamps(n)

    report = detect_spikes("ring-01", wavelengths, timestamps, threshold_pm_per_s=1000.0)

    assert report.has_anomaly
    assert report.spike_count == 1


def test_smooth_signal_has_no_false_positive() -> None:
    # A signal that slowly drifts upward (thermal drift) should NOT be flagged.
    # The drift here is 10 pm over 0.1 seconds — a gradual change, not a sudden event.
    # The threshold is 500 pm/s, which is 5x higher than the drift rate, so no alarms.
    n = 1000
    wavelengths = np.linspace(1500.0, 1510.0, n)  # slow linear drift, 100 pm/s rate
    timestamps = _make_timestamps(n)

    report = detect_spikes("ring-01", wavelengths, timestamps, threshold_pm_per_s=500.0)

    assert not report.has_anomaly


def test_mismatched_lengths_raise() -> None:
    # Wavelength and timestamp arrays must always be the same length.
    # If they differ, the data is corrupt — the detector must raise an error
    # rather than silently computing incorrect results.
    with pytest.raises(MismatchedFrameLengthError):
        detect_spikes("ring-01", np.zeros(10), np.zeros(9))


def test_precision_against_synthetic_spikes() -> None:
    # Inject 3 known spikes into a clean signal and verify all 3 are found,
    # at exactly the right timestamps, with no false alarms in between.
    #
    # Signal: 5000 flat samples with +50 pm steps at indices 1000, 2500, and 4000.
    # The sections between spikes are perfectly flat → zero rate of change → no false alarms.
    n = 5000
    dt_ns = 100_000
    spike_indices = [1000, 2500, 4000]
    threshold_pm_per_s = 300.0

    wavelengths = np.full(n, 1500.0)
    for idx in spike_indices:
        wavelengths[idx:] += 50.0  # step at each spike index

    timestamps = _make_timestamps(n, dt_ns=dt_ns)
    report = detect_spikes("ring-01", wavelengths, timestamps, threshold_pm_per_s=threshold_pm_per_s)

    # All 3 injected spikes must be detected — no misses.
    assert report.spike_count == len(spike_indices), (
        f"Expected {len(spike_indices)} spikes, detected {report.spike_count}. "
        f"derivative range: [{report.derivative_pm_per_s.min():.1f}, "
        f"{report.derivative_pm_per_s.max():.1f}] pm/s"
    )

    # The timestamps of the detected spikes must match exactly where we injected them.
    expected_ts = np.array([timestamps[i] for i in spike_indices], dtype=np.int64)
    assert np.array_equal(np.sort(report.spike_timestamp_ns), np.sort(expected_ts)), (
        f"Spike timestamps mismatch. Expected {expected_ts}, got {report.spike_timestamp_ns}"
    )