"""Prometheus metrics for DSP processing and local triage."""
from prometheus_client import Counter, Histogram

DSP_PROCESS_SECONDS = Histogram(
    "photonicops_dsp_process_seconds",
    "DSPPipeline.process wall time",
    buckets=(0.001, 0.002, 0.005, 0.010, 0.025, 0.050),
)

DSP_SPIKES_TOTAL = Counter(
    "photonicops_dsp_spikes_total",
    "Spikes flagged by the detector",
    ["sensor_id"]
)
TRIAGE_SECONDS = Histogram(
    "photonicops_triage_evaluate_seconds",
    "safety.evaluate wall time",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)

TRIAGE_OUTCOMES = Counter(
    "photonicops_triage_outcomes_total",
    "Triage outcomes by status",
    ["status"]
)
