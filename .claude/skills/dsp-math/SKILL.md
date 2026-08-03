---
name: dsp-math
description: Use when writing or reviewing Python digital signal processing code under services/dsp-agent-python/src/dsp/ (Kalman filtering, baseline subtraction, spike/bubble anomaly detection, biomarker extraction) — vectorized NumPy/SciPy constraints for the real-time optical telemetry pipeline.
---

# Role: DSP Mathematician

You are building PhotonicOps's Python signal-processing pipeline, which consumes optical wavelength-shift telemetry (Δλ, picometers) handed off from the Go ingestion engine and must process each ~100ms frame in under 10ms (NFR-1.2).

Note: as of this writing, `services/dsp-agent-python/` does not exist yet — this is Phase 2 (`docs/ROADMAP.md`), currently blocked on Task 2.0 (defining the Go→Python IPC contract per ADR-007, a Unix-domain-socket local gRPC service reusing `proto/telemetry.proto` plus a batching wrapper message). Confirm that contract exists before writing consumer code against it; do not assume a transport.

## Hard constraints

- **Strictly vectorized.** Use `NumPy`/`SciPy` array operations. **No `for` loops over sample data** — if you find yourself iterating frame-by-frame in Python, restructure as a batched/vectorized operation instead.
- **Operate on buffers in place where possible** — memory efficiency matters on a real-time stream; avoid needless copies of large arrays.
- **Design for streaming, not batch.** The pipeline runs continuously against a live feed; algorithms (Kalman filter state, baseline estimates) must carry state across calls rather than assume a fixed offline dataset.
- **Native ARM64 wheels only** (Accelerate-framework-backed NumPy/SciPy) — this runs on Apple Silicon, and `requirements.txt` should not pull generic manylinux wheels that fall back to slower BLAS.
- **Strict type hints**, and raise specific custom exceptions rather than generic ones on malformed input.

## What this pipeline is responsible for (FR-2.x in `docs/REQUIREMENTS.md`)

- `kalman.py`: 1D Kalman filtering + moving-average baseline subtraction to remove thermal drift and ambient noise (Roadmap Task 2.2).
- `spike_detector.py`: first-derivative thresholding (`|dλ/dt| > threshold`) to flag microfluidic bubbles/clogs (Task 2.3).
- Biomarker extraction: steady-state optical saturation → estimated protein concentration in ng/mL (Task 2.4, FR-2.3) — this exists in the requirements spec but had no roadmap task until the recent architecture review added one; don't assume it's already scaffolded elsewhere.

Flagged anomalies (SNR < 12 dB or a hard spike) are the trigger condition for the Phase 3 LLM triage agent — see the `mlops-agent` skill for that boundary.
