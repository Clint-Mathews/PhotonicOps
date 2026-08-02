# Implementation & Progression Guide

## System: PhotonicOps
**Execution Strategy:** AI-First Constraint-Driven Development ("Antigravity" Workflow)
**Host Architecture:** Apple Silicon (M1/ARM64)

This document outlines the step-by-step progression plan for building PhotonicOps. It defines the sequence of execution, which AI developer personas to invoke at each step, and the strict technical phase-gates required to move forward.

---

## [x] Phase 0: The Harness & Environment
**Goal:** Establish the strict AI coding guardrails and local infrastructure required for an Apple Silicon/ARM64 environment before writing any application code.

* [x] **Task 0.1:** Commit `.agents/AGENTS.md` and the `.agents/skills/*/SKILL.md` developer personas (`@go-architect`, `@dsp-math`, `@mlops-agent`).
* [x] **Task 0.2:** Scaffold the foundational `docker-compose.yml`.
  * *Constraint:* Must explicitly define `platform: linux/arm64` for all services.
  * *Components:* Prometheus, Grafana, Langfuse (Postgres dependency), and Ollama.
* [x] **Task 0.3:** Pull the local LLM weights into the Ollama volume (`docker exec -it ollama ollama run llama3.1:8b`).
* [x] **Phase Gate:** You can run `docker-compose up -d` and successfully hit the Ollama local API and Langfuse UI at `localhost` with zero x86 Rosetta emulation.

---

## [ ] Phase 1: The Data Contract & Ingestion Engine (Go)
**Goal:** Build the high-throughput backbone capable of receiving 10,000 samples/sec with sub-millisecond allocation latency.

* [ ] **Task 1.1: Protobuf Contract**
  * Define `proto/telemetry.proto` detailing the raw optical wavelength shift payload.
  * *AI Persona:* `@go-architect`
* [ ] **Task 1.2: The Mock Sensor**
  * Build `scripts/simulate_sensor.go` to blast gRPC traffic at 10kHz, injecting synthetic thermal drift and bubble spikes.
* [ ] **Task 1.3: The Go gRPC Server & Worker Pool**
  * Implement the gRPC listener and channel-based worker pool in `services/ingestion-go/`.
  * *Constraint:* Strict zero-allocation. Use `sync.Pool` for byte buffers and implement `ringbuffer.go`.
  * *AI Persona:* `@go-architect`
* [ ] **Phase Gate:** The Go server successfully ingests 10,000 req/sec from the mock script. Go profiling (`pprof`) confirms zero significant Garbage Collection (GC) pauses.

---

## [ ] Phase 2: Digital Signal Processing Pipeline (Python)
**Goal:** Extract clean signals from the noisy gRPC stream using vector math.

* [ ] **Task 2.1: DSP Environment Setup**
  * Scaffold `services/dsp-agent-python/requirements.txt`.
  * *Constraint:* Ensure native ARM64 wheels for `NumPy` and `SciPy` (Accelerate framework compatibility).
* [ ] **Task 2.2: Kalman Filter & Baseline Subtraction**
  * Write `src/dsp/kalman.py`. Process the incoming Go telemetry IPC stream in vectorized chunks.
  * *AI Persona:* `@dsp-math`
* [ ] **Task 2.3: Anomaly Detection**
  * Write `src/dsp/spike_detector.py` to identify micro-bubbles via first-derivative thresholding ($|\frac{d\lambda}{dt}| > \text{threshold}$).
* [ ] **Phase Gate:** The Python pipeline successfully receives the data from Go, smooths the signal in $< 10\text{ ms}$ per frame, and accurately flags the synthetic anomalies injected by the mock sensor.

---

## [ ] Phase 3: LLMOps & Agentic Hardware Triage (Python)
**Goal:** Enforce deterministic, zero-hallucination hardware remediation using the local M1 GPU.

* [ ] **Task 3.1: Hardware Skills & Schema**
  * Define the strict hardware action schemas in `src/agent/schema.py` using Pydantic.
* [ ] **Task 3.2: Instructor Integration & Triage Engine**
  * Build `src/agent/triage.py` to prompt the local Ollama instance using `Instructor`. Pass the flagged DSP frame and require the LLM to output a `RemediationDecision`.
  * *AI Persona:* `@mlops-agent`
* [ ] **Task 3.3: Langfuse Tracing**
  * Wrap the LLM calls with `@observe()` decorators to log token usage and latency to the local Langfuse instance.
* [ ] **Phase Gate:** When the DSP pipeline detects a bubble, the local Llama 3.1 model successfully outputs a perfectly formatted `FLUSH_VALVE` JSON command in $< 2.0\text{ seconds}$.

---

## [ ] Phase 4: Observability, Evals, & Dashboard
**Goal:** Expose the internal state of the system and prove the AI's reliability mathematically.

* [ ] **Task 4.1: Prompt Evaluation Suite**
  * Build `evals/test_cases.json` and configure Promptfoo to run regression tests on the agent's diagnostic accuracy against various synthetic noise profiles.
  * *AI Persona:* `@mlops-agent`
* [ ] **Task 4.2: Real-Time UI**
  * Build the React/TypeScript dashboard in `services/dashboard-ui/`.
  * Implement an HTML5 Canvas or WebGL chart (via Chart.js or similar) driven by WebSockets to plot the Raw vs. Filtered signal at $30\text{ FPS}$.
* [ ] **Task 4.3: Prometheus Integration**
  * Wire Go ingestion latency and Python DSP processing times to Prometheus/Grafana.
* [ ] **Phase Gate:** The React dashboard renders smoothly without crashing the browser tab. Promptfoo evaluations pass with $> 95\%$ remediation accuracy. The system is functionally complete.