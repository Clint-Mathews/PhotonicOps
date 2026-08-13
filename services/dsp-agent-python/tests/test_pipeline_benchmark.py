"""Benchmark test — checks the full pipeline processes one batch in under 10 ms."""
from __future__ import annotations

import numpy as np

from src.dsp.pipeline import DSPPipeline

# One batch = 100 ms of data at 10,000 samples/sec = 1000 samples.
SAMPLES_PER_BATCH = 1000


def test_process_batch_under_10ms(benchmark) -> None:
    # Runs the full pipeline (Kalman filter → baseline removal → spike detection)
    # on a realistic batch of 1000 samples and checks it finishes in under 10 ms on average.
    #
    # The signal is a flat 1500.0 pm reading with small random noise — typical of a
    # clean, idle biosensor. The benchmark runs the pipeline many times automatically
    # and records the average execution time.
    rng = np.random.default_rng(seed=2)
    wavelengths = 1500.0 + rng.normal(0, 1.0, size=SAMPLES_PER_BATCH)
    timestamps = np.arange(SAMPLES_PER_BATCH, dtype=np.int64) * 100_000  # 100 µs intervals

    pipeline = DSPPipeline()
    result = benchmark(pipeline.process, "ring-01", wavelengths, timestamps, 100.0)

    # The output must have the same number of samples as the input — nothing dropped.
    assert result.filtered.shape == wavelengths.shape

    # Mean processing time per batch must be under 10 ms.
    assert benchmark.stats["mean"] < 0.010, (
        f"Pipeline too slow: mean={benchmark.stats['mean']*1000:.2f} ms (limit: 10 ms)"
    )