# Software Requirements Specification (SRS)

## System: PhotonicOps (Real-Time Sensor Telemetry & AI Diagnostic Engine)
- **Version:** 0.2.0 (Phase 1 of 4 complete — see `docs/ROADMAP.md`; requirements below describe the target system, not all are yet implemented)
- **System Objective:** Ingest high-frequency photonic biosensor telemetry, perform real-time signal cleansing to eliminate biological/hardware noise, and execute agentic root-cause analysis on hardware anomalies natively at the edge.

---

## 1. System Context & Overview

PhotonicOps is a hybrid distributed system designed to bridge physical hardware sensors with modern software operations in highly secure clinical environments. It handles high-throughput telemetry streams from optical ring resonator chips, applies digital signal processing (DSP) to isolate protein-binding events from microfluidic anomalies, and routes hardware failures to a locally hosted, offline LLM diagnostic agent for real-time triage.

+-------------------+      gRPC       +------------------------+
| Photonic Sensors  | --------------> | Go Ingestion Engine    |
| (Simulated Nodes) |                 | (Worker Pool/Channels) |
+-------------------+                 +------------------------+
|
v IPC / Stream
+-------------------+                 +------------------------+
| React Dashboard   | <-------------- | Python DSP Engine      |
| (WebSockets / UI) |   WebSockets    | (Kalman Filter + SNR)  |
+-------------------+                 +------------------------+
| Anomaly Flag
v
+------------------------+
| LLMOps Triage Agent    |
| (Ollama / Local LLM)   |
+------------------------+

---

## 2. Functional Requirements (FR)

### Module 1: Telemetry Ingestion Engine (Go)
* **FR-1.1 (High-Frequency Streaming):** Ingest raw optical wavelength shift telemetry (Δλ in picometers) over gRPC streams at a target rate of 10,000 samples/second per channel.
* **FR-1.2 (Concurrent Processing):** Implement a bounded goroutine worker pool with zero-allocation ring buffers and `sync.Pool` to prevent memory allocation overhead and garbage collection pauses during peak throughput.
* **FR-1.3 (Backpressure & Buffering):** Apply channel-based backpressure to the worker pool queue. The default mode blocks the producer (natural TCP backpressure to the sensor, per `docs/FAQ/PHASE1.md` Q5); a `--load-shed` mode using a non-blocking `select`/`default` send must be available for deployments that prefer dropping frames over stalling upstream sensors. *(Status: blocking mode implemented in `internal/worker/pool.go`; load-shed mode not yet implemented.)*
* **FR-1.4 (Health Heartbeat):** Export ingestion health and throughput counters (frames/sec, queue depth, ring buffer occupancy) on a Prometheus `/metrics` endpoint, scraped at the operator's configured interval. *(Status: not yet implemented — tracked as Roadmap Phase 1.5, not Phase 1, since it depends on the Prometheus wiring described in NFR-6.1/Task 4.3.)*
* **FR-1.5 (Transport Security):** The ingestion gRPC endpoint must require mTLS in any non-development build; see ADR-006. *(Status: not yet implemented — server and mock sensor currently use `insecure.NewCredentials()`.)*

### Module 2: Signal Cleansing & Anomaly Classifier (Python)
* **FR-2.1 (Noise Cleansing):** Implement real-time 1D Kalman Filtering and moving-average baseline subtraction to eliminate thermal drift and ambient optical interference.
* **FR-2.2 (Spike & Bubble Detection):** Detect step-function signal anomalies characteristic of microfluidic bubbles or cell clogs using first-derivative thresholding (|dλ/dt| > threshold).
* **FR-2.3 (Biomarker Extraction):** Extract steady-state optical saturation values to calculate estimated target protein concentrations in ng/mL. *(Not yet scheduled in `docs/ROADMAP.md` Phase 2 — needs a task before Phase 2 can be considered complete against this SRS.)*

### Module 3: LLMOps Diagnostic & Triage Agent (Python)
* **FR-3.1 (Automated Triggering):** Instantly trigger an AI diagnostic agent when Signal-to-Noise Ratio (SNR) drops below 12 dB or when a hard hardware anomaly is flagged.
* **FR-3.2 (Offline Execution):** Connect to a locally hosted Ollama instance (llama3.1:8b or qwen2.5:7b) running natively on Apple Silicon (Metal/MPS) with zero cloud API dependencies.
* **FR-3.3 (Zero-Hallucination Schema Enforcement):** Enforce strict JSON output schemas via Pydantic/Instructor containing:
  * `failure_category`: Enum (MICROFLUIDIC_BUBBLE, THERMAL_DRIFT, PHOTONIC_ALIGNMENT_LOSS, NORMAL_NOISE, UNKNOWN)
  * `confidence_score`: Float between 0.0 and 1.0
  * `remediation_action`: Executable API action command (e.g., FLUSH_VALVE)
  * `reasoning`: Concise physical explanation of the root cause
* **FR-3.4 (Agent Tracing & Observability):** Log all agent executions, prompt versions, token consumption, and model latency metrics using a locally hosted Langfuse instance.
* **FR-3.5 (Fail-Safe Default State):** If the LLM is unreachable, times out, or returns a `confidence_score` below the configured threshold (default 0.7), no `remediation_action` is auto-executed. The anomaly is logged and surfaced as `REQUIRES_MANUAL_REVIEW` on the Incident Management Feed (FR-4.2) instead. See ADR-008.
* **FR-3.6 (Diagnostic Audit Trail):** Every triage decision (including `REQUIRES_MANUAL_REVIEW` outcomes and manual overrides) is persisted with a timestamp and the triggering telemetry window, retained beyond the ingestion engine's in-memory ring buffer, to support the audit-control expectations of clinical/HIPAA environments referenced in ADR-005. Retention duration and storage medium (e.g., local Postgres, the existing Langfuse database) are an open decision for Phase 3 design.

### Module 4: Web Dashboard & Monitoring (TypeScript / React)
* **FR-4.1 (Real-Time Visualization):** Render a dual-line live canvas updating at >= 30 FPS displaying Raw Signal vs. Filtered Signal.
* **FR-4.2 (Incident Management Feed):** Display an active log of AI-diagnosed anomalies with one-click manual hardware override triggers.
* **FR-4.3 (System Observability Metrics):** Display running system health metrics, including ingestion latency (p99), pipeline throughput, and local LLM execution times.

### Module 5: AI-SDLC Harness & Developer Tooling
* **FR-5.1 (Agent Constraints):** Enforce repository-level `.agents/AGENTS.md` defining code style, typing strictness, M1 architecture targets, and zero-allocation memory constraints.
* **FR-5.2 (Automated CI/CD Review):** Execute an automated GitHub Action on Pull Requests to scan code changes for data privacy compliance and architectural regressions.
* **FR-5.3 (Prompt Evaluation Suite):** Maintain an evaluation suite (`/evals`) utilizing Promptfoo to run synthetic noisy signal scenarios against the LLM agent, ensuring diagnostic consistency across model updates. This suite must also cover the FR-3.5 fail-safe paths (unreachable LLM, low-confidence response), not only well-formed high-confidence cases.

---

## 3. Non-Functional Requirements (NFR)

### NFR-1: Performance & Latency
* **NFR-1.1:** The Go ingestion engine must maintain a p99 ingestion latency under 2 ms for incoming gRPC frames.
* **NFR-1.2:** The Python DSP pipeline must process each 100ms signal frame in under 10 ms.
* **NFR-1.3:** The LLM triage agent must return a validated JSON remediation action in under 2.0 seconds utilizing native hardware acceleration (Apple Silicon Unified Memory).

### NFR-2: Target Architecture & Environment
* **NFR-2.1:** All containerized services must be built natively for `linux/arm64` to utilize Apple Silicon efficiently and avoid x86 emulation overhead.
* **NFR-2.2:** Python dependencies (NumPy, SciPy) must utilize native ARM64/Accelerate wheels for vectorized performance.

### NFR-3: Privacy, Security & Compliance
* **NFR-3.1:** The system must operate 100% offline. Zero telemetry data or prompt context may be sent to external cloud APIs, strictly satisfying HIPAA data isolation requirements for clinical edge deployments.

### NFR-4: Throughput & Scalability
* **NFR-4.1:** The ingestion layer must scale horizontally to handle up to 50 concurrent simulated chip streams (500,000 samples/sec aggregate).
* **NFR-4.2:** The ring buffer (`internal/buffer.RingBuffer`) must retain approximately 1 second of history *per sensor*, not per instance. The current implementation is a single global buffer keyed by insertion order, not `sensor_id`; at NFR-4.1 scale this would retain roughly 20ms of aggregate history and interleave sensors. Sharding the buffer by `sensor_id` (or sizing it to `10,000 * expected_concurrent_streams`) is required before NFR-4.1 can be considered met.

### NFR-5: Reliability & Determinism
* **NFR-5.1:** The system must achieve 0% schema validation failures on LLM diagnostic responses through automated retries and strict Pydantic parsing.
* **NFR-5.2:** The DSP classifier must accurately flag micro-bubble anomalies with >= 95% precision against baseline test datasets.

### NFR-6: Observability & Governance
* **NFR-6.1:** All components must export Prometheus metrics at `/metrics`.
* **NFR-6.2:** The entire application stack must launch locally using a single command: `docker-compose up`.

### NFR-7: Transport Security
* **NFR-7.1:** All process-to-process traffic carrying telemetry or diagnostic data (sensor → ingestion, ingestion → DSP, DSP → triage agent) must be encrypted or otherwise confined to a mechanism not reachable from outside the host (e.g., mTLS for network sockets, or a Unix domain socket for same-host IPC). See ADR-006 and ADR-007.