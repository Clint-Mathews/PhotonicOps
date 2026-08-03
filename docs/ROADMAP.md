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

## [x] Phase 1: The Data Contract & Ingestion Engine (Go)
**Goal:** Build the high-throughput backbone capable of receiving 10,000 samples/sec with sub-millisecond allocation latency.

* [x] **Task 1.1: Protobuf Contract**
  * Define `proto/telemetry.proto` detailing the raw optical wavelength shift payload.
  * *AI Persona:* `@go-architect`
* [x] **Task 1.2: The Mock Sensor**
  * Build `scripts/simulate_sensor.go` to blast gRPC traffic at 10kHz, injecting synthetic thermal drift and bubble spikes.
* [x] **Task 1.3: The Go gRPC Server & Worker Pool**
  * Implement the gRPC listener and channel-based worker pool in `services/ingestion-go/`.
  * *Constraint:* Strict zero-allocation. Use `sync.Pool` for byte buffers and implement `ringbuffer.go`.
  * *AI Persona:* `@go-architect`
* [x] **Phase Gate:** The Go server successfully ingests 10,000 req/sec from the mock script. Go profiling (`pprof`) confirms zero significant Garbage Collection (GC) pauses.

---

## [ ] Phase 2: Digital Signal Processing Pipeline (Python)
**Goal:** Extract clean signals from the noisy gRPC stream using vector math.

* [x] **Task 2.0: Go → Python IPC Contract**
  * Implement the Unix-domain-socket local gRPC transport decided in ADR-007, including the frame-batching wrapper message added to `proto/telemetry.proto`. This blocks every other Phase 2 task — `src/dsp/kalman.py` cannot be written against an undefined input contract.
  * *AI Persona:* `@go-architect` (Go side), `@dsp-math` (Python client side)
* [ ] **Task 2.1: DSP Environment Setup**
  * Scaffold `services/dsp-agent-python/requirements.txt`.
  * *Constraint:* Ensure native ARM64 wheels for `NumPy` and `SciPy` (Accelerate framework compatibility).
* [ ] **Task 2.2: Kalman Filter & Baseline Subtraction**
  * Write `src/dsp/kalman.py`. Process the incoming Go telemetry IPC stream (Task 2.0) in vectorized chunks.
  * *AI Persona:* `@dsp-math`
* [ ] **Task 2.3: Anomaly Detection**
  * Write `src/dsp/spike_detector.py` to identify micro-bubbles via first-derivative thresholding ($|\frac{d\lambda}{dt}| > \text{threshold}$).
* [ ] **Task 2.4: Biomarker Extraction**
  * Extract steady-state optical saturation values and calculate estimated target protein concentration (ng/mL).
  * Satisfies FR-2.3, previously specified in the SRS but untracked in this roadmap.
  * *AI Persona:* `@dsp-math`
* [ ] **Phase Gate:** The Python pipeline successfully receives the data from Go, smooths the signal in $< 10\text{ ms}$ per frame, accurately flags the synthetic anomalies injected by the mock sensor, and produces a biomarker concentration estimate.

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
* [ ] **Task 3.4: Fail-Safe State Machine**
  * Implement the unreachable/timeout/low-confidence handling defined in ADR-008: no `remediation_action` is auto-executed unless the response is schema-valid *and* `confidence_score` clears the configured threshold; otherwise the anomaly is marked `REQUIRES_MANUAL_REVIEW`.
  * Satisfies FR-3.5. Depends on at minimum a stub of the Phase 4 Incident Management Feed (FR-4.2) to surface manual-review items — do not enable autonomous execution against real hardware endpoints until that exists.
  * *AI Persona:* `@mlops-agent`
* [ ] **Task 3.5: Diagnostic Audit Log**
  * Persist every triage decision (auto-executed, manual-review, and manual-override outcomes) with timestamp and triggering telemetry window. Storage medium (local Postgres vs. reusing the Langfuse database) is an open decision to resolve at the start of this task.
  * Satisfies FR-3.6.
* [ ] **Phase Gate:** When the DSP pipeline detects a bubble, the local Llama 3.1 model successfully outputs a perfectly formatted `FLUSH_VALVE` JSON command in $< 2.0\text{ seconds}$, low-confidence/unreachable cases correctly fall back to `REQUIRES_MANUAL_REVIEW` instead of executing, and both outcomes are recorded in the audit log.

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
  * Wire remaining DSP/agent processing-time metrics to Prometheus/Grafana. (Go ingestion `/metrics` ships in Phase 5 Task 5.2.)
* [ ] **Task 4.4: AI-Reviewed CI/CD Gate**
  * Add the `.github/workflows/ai-review.yml` GitHub Action referenced in `structure.txt` but not yet present in `.github/workflows/`, scanning PRs for data-privacy regressions (e.g., reintroduced cloud API calls, disabled mTLS) and `.agents/AGENTS.md` constraint violations.
  * Satisfies FR-5.2, currently unimplemented.
* [ ] **Phase Gate:** The React dashboard renders smoothly without crashing the browser tab. Promptfoo evaluations pass with $> 95\%$ remediation accuracy, including the Phase 3 fail-safe paths (Task 3.4). The AI-review CI gate is active on pull requests. The system is functionally complete.

---

## [ ] Phase 5: Ingestion Hardening
**Goal:** Close the remaining SRS gaps in the ingestion engine that do not block functional delivery of Phases 2–4 but are required before a production deployment. This phase was originally scoped as Phase 1.5 and intentionally deferred.

> **ADR-006 Note:** Task 5.1 (mTLS) was originally marked as a hard prerequisite for Phase 2 in ADR-006. That constraint has been consciously relaxed for development velocity — the plaintext transport is acceptable in a local, single-host dev environment. mTLS **must** be completed before any deployment against real clinical hardware or a shared network segment.

* [ ] **Task 5.1: Transport Security**
  * Implement mTLS on the ingestion gRPC server and mock sensor client, replacing `insecure.NewCredentials()`. Local self-signed CA, no external ACME dependency. Cert generation script already exists at `scripts/generate_certs.sh`.
  * Satisfies FR-1.5 / ADR-006.
  * *AI Persona:* `@go-architect`
* [ ] **Task 5.2: Prometheus Metrics Endpoint**
  * Export `/metrics` (frames/sec, `jobQueue` depth, ring buffer occupancy) from the ingestion server. Required for Phase 4 Task 4.3 Grafana wiring to be complete.
  * Satisfies FR-1.4 / NFR-6.1 for the ingestion service.
* [ ] **Task 5.3: Load-Shedding Mode**
  * Add an opt-in non-blocking `select`/`default` send path in `internal/worker/pool.go::Enqueue` per `docs/FAQ/PHASE1.md` Q5, toggled by a `--load-shed` startup flag.
  * Satisfies FR-1.3.
* [ ] **Task 5.4: Per-Sensor Ring Buffer Sharding**
  * Key `internal/buffer.RingBuffer` by `sensor_id` (or otherwise size it for concurrent multi-sensor retention) so historical depth doesn't collapse under NFR-4.1 load.
  * Satisfies NFR-4.2.
* [ ] **Task 5.5: CI ARM64 Build Target**
  * Fix `build-binary` job in `.github/workflows/ci-ingestion-go.yml` to produce a `linux/arm64` artifact in addition to `linux/amd64`.
  * Satisfies NFR-2.1.
* [ ] **Phase Gate:** `docker-compose`-launched ingestion server rejects non-mTLS connections, `/metrics` is scrapeable and wired into Grafana, load-shedding can be toggled and verified under an artificial backlog, per-sensor history is retrievable independent of other concurrently streaming sensors, and CI produces a native ARM64 binary.