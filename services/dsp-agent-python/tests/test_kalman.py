"""Tests for the Kalman filter and baseline subtraction functions."""
from __future__ import annotations

import numpy as np
import pytest

from src.dsp.exceptions import EmptyFrameBatchError, InvalidFilterParametersError
from src.dsp.kalman import KalmanFilter1D, subtract_baseline


def test_rejects_nonpositive_variance() -> None:
    # The filter must refuse to start if given a zero or negative variance value.
    # These values are mathematically invalid and would break the filter's internal math.
    with pytest.raises(InvalidFilterParametersError):
        KalmanFilter1D(process_variance=0.0, measurement_variance=1.0)


def test_filter_reduces_noise_variance() -> None:
    # Feed a noisy signal into the filter and check that the output is smoother.
    # We create a flat signal (constant 1500.0), add random jitter to it,
    # then filter it. The filtered output should have less variance than the noisy input.
    rng = np.random.default_rng(seed=0)
    true_signal = np.full(2000, 1500.0)
    noisy = true_signal + rng.normal(0, 5.0, size=2000)

    kf = KalmanFilter1D(process_variance=1e-3, measurement_variance=25.0)
    filtered = kf.filter_batch("ring-01", noisy)

    # Compare from sample 500 onward to skip the filter's brief startup period.
    assert np.var(filtered[500:]) < np.var(noisy[500:])


def test_state_persists_across_batches_without_discontinuity() -> None:
    # The filter must remember where it left off between calls.
    # If two batches are fed one after the other, the last value of the first batch
    # and the first value of the second batch should be essentially identical —
    # no jump or discontinuity at the boundary.
    kf = KalmanFilter1D()
    batch_a = np.full(100, 1500.0)
    batch_b = np.full(100, 1500.0)

    filtered_a = kf.filter_batch("ring-01", batch_a)
    filtered_b = kf.filter_batch("ring-01", batch_b)

    assert abs(filtered_b[0] - filtered_a[-1]) < 1e-6


def test_empty_batch_raises() -> None:
    # Passing an empty array must raise an error immediately.
    # An empty input would silently produce empty output and confuse downstream steps.
    kf = KalmanFilter1D()
    with pytest.raises(EmptyFrameBatchError):
        kf.filter_batch("ring-01", np.array([]))


def test_subtract_baseline_removes_linear_drift() -> None:
    # A signal that slowly drifts upward (like temperature changing over time)
    # should be corrected to near zero after baseline subtraction.
    # We use a perfectly linear drift from 1500 to 1510 pm over 500 samples.
    # After subtraction, the middle of the corrected signal should be within 1 pm of zero.
    drift = np.linspace(1500.0, 1510.0, 500)
    corrected = subtract_baseline(drift, window=25)

    # Check the interior only — the first and last 50 samples are near the edges
    # where the moving average has less context, so they're excluded.
    assert np.max(np.abs(corrected[50:-50])) < 1.0