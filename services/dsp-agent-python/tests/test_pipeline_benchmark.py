from __future__ import annotations

import numpy as np

from src.dsp.pipeline import DSPPipeline

# 10,000 samples/sec * 100ms nominal window (matches FrameBatch batching).
SAMPLES_PER_BATCH = 1000


def test_process_batch_under_10ms(benchmark) -> None:
    rng = np.random.default_rng(seed=2)
    wavelengths = 1500.0 + rng.normal(0, 1.0, size=SAMPLES_PER_BATCH)
    timestamps = np.arange(SAMPLES_PER_BATCH, dtype=np.int64) * 100_000

    pipeline = DSPPipeline()
    result = benchmark(pipeline.process, "ring-01", wavelengths, timestamps, 100.0)

    assert result.filtered.shape == wavelengths.shape
    assert benchmark.stats["mean"] < 0.010  # NFR-1.2: <10ms per frame