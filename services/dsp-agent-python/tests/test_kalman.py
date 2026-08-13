from __future__ import annotations

import numpy as np
import pytest

from src.dsp.exceptions import EmptyFrameBatchError, InvalidFilterParametersError
from src.dsp.kalman import KalmanFilter1D, subtract_baseline


def test_rejects_nonpositive_variance() -> None:
    with pytest.raises(InvalidFilterParametersError):
        KalmanFilter1D(process_variance=0.0, measurement_variance=1.0)


def test_filter_reduces_noise_variance() -> None:
    rng = np.random.default_rng(seed=0)
    true_signal = np.full(2000, 1500.0)
    noisy = true_signal + rng.normal(0, 5.0, size=2000)

    kf = KalmanFilter1D(process_variance=1e-3, measurement_variance=25.0)
    filtered = kf.filter_batch("ring-01", noisy)

    assert np.var(filtered[500:]) < np.var(noisy[500:])


def test_state_persists_across_batches_without_discontinuity() -> None:
    kf = KalmanFilter1D()
    batch_a = np.full(100, 1500.0)
    batch_b = np.full(100, 1500.0)

    filtered_a = kf.filter_batch("ring-01", batch_a)
    filtered_b = kf.filter_batch("ring-01", batch_b)

    assert abs(filtered_b[0] - filtered_a[-1]) < 1e-6


def test_empty_batch_raises() -> None:
    kf = KalmanFilter1D()
    with pytest.raises(EmptyFrameBatchError):
        kf.filter_batch("ring-01", np.array([]))


def test_subtract_baseline_removes_linear_drift() -> None:
    drift = np.linspace(1500.0, 1510.0, 500)
    corrected = subtract_baseline(drift, window=25)
    assert np.max(np.abs(corrected[50:-50])) < 1.0