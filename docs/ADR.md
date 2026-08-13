# Architecture Decision Records (ADRs)

## System: PhotonicOps

This document records the key architectural decisions, context, and trade-offs made during the design and development of the **PhotonicOps** platform.

---

## ADR 001: Use Go for High-Throughput Telemetry Ingestion

### Context
The photonic biosensor streams optical wavelength shift data at rates up to 10,000 samples/second per channel. The ingestion layer requires predictable, low-latency processing without garbage collection stalls or heavy memory footprints.

### Decision
We will build the ingestion engine in **Go**, utilizing gRPC streaming, zero-allocation ring buffers, and bounded goroutine worker pools.

### Consequences
* **Positive:**
  * Sub-millisecond allocation latency (p99 < 2 ms).
  * High-concurrency throughput via native Go channels.
  * Simple deployment via standalone binary or minimal Docker container.
* **Negative:**
  * Requires maintaining a multi-language repository (Go for ingestion, Python for DSP/AI).
  * Duplication of data models via Protocol Buffers.

---

## ADR 002: Separate Python Pipeline for Digital Signal Processing (DSP) & ML

### Context
Raw optical telemetry contains hardware noise, thermal drift, and step spikes from microfluidic bubbles. Filtering this data requires complex matrix operations, Kalman filters, and baseline estimation algorithms.

### Decision
We will run the DSP pipeline in **Python**, using numerical libraries (`NumPy`, `SciPy`) decoupled from the Go ingestion engine via an inter-process communication stream.

### Consequences
* **Positive:**
  * Access to industry-standard mathematical and signal-processing ecosystems.
  * Direct integration path with Python-native LLMOps and ML frameworks.
* **Negative:**
  * Introduces inter-process serialization overhead between Go and Python.
  * Higher memory consumption per worker process compared to compiled binaries.

---

## ADR 003: Strict Schema Enforcement for LLM Diagnostic Outputs

### Context
The LLM agent provides automated triage and hardware remediation commands for corrupted optical streams. Free-form text output from an LLM cannot be safely consumed by automated hardware APIs or downstream microservices.

### Decision
We will enforce strict structural constraints using **Pydantic schemas** paired with structured output frameworks (`Instructor`). The system will automatically reject non-conforming responses and trigger an immediate fallback retry.

### Consequences
* **Positive:**
  * Guarantees zero-hallucination type safety for hardware remediation actions.
  * Deterministic integration into automated backend microservices.
* **Negative:**
  * Slight increase in LLM prompt token overhead due to schema injection.
  * Requires explicit schema migration management when adding new hardware failure categories.

---

## ADR 004: Repository-Enforced AI Development Harness (`.agents/AGENTS.md` & CI/CD)

### Context
To enable rapid engineering velocity while keeping code quality high across a multi-language stack (Go, Python, TypeScript), the development workflow requires standardized automated guardrails for AI coding assistants.

### Decision
We will commit an explicit `.agents/AGENTS.md` file, modular AI developer personas (e.g., `@go-architect`), and an automated GitHub Action reviewer to the repository to enforce system constraints across all AI-generated code.

### Consequences
* **Positive:**
  * Ensures AI coding assistants adhere strictly to typed interfaces, zero-allocation Go patterns, Apple Silicon targeting, and Pydantic schemas.
  * Automates code review enforcement during pull requests.
* **Negative:**
  * Requires maintaining and updating rule definitions as system architecture evolves.

---

## ADR 005: 100% Offline Local LLM Inference on Apple Silicon (M1)

### Context
PhotonicOps processes hardware telemetry that may be deployed in clinical trial environments subject to strict data privacy and HIPAA regulations. Furthermore, round-trip network latency to cloud-based LLM APIs (e.g., OpenAI, Anthropic) introduces unacceptable delays and jitter for real-time hardware remediation.

### Decision
We will run the LLM inference entirely offline utilizing **Ollama** deployed locally on Apple Silicon (M1/ARM64). The engine will leverage the M1 Unified Memory Architecture to run quantized models (e.g., `llama3.1:8b`) via Metal Performance Shaders (MPS).

### Consequences
* **Positive:**
  * Inherently HIPAA-compliant by eliminating external data transmission.
  * Eliminates API token costs and rate limits.
  * Ensures deterministic, sub-2.0 second triage latency by sharing memory between the CPU and GPU.
* **Negative:**
  * Increases the minimum hardware requirements for edge deployment (requires Apple Silicon or discrete GPUs).
  * Requires explicit `linux/arm64` container targeting to avoid x86 virtualization penalties.

---

## ADR 006: Defer mTLS on the Ingestion gRPC Transport

### Context
NFR-3.1 and the offline/HIPAA posture require locking down any network-exposed listener before real hardware or clinical data touches it. mTLS was originally scoped as a hard prerequisite before Phase 2 could start. Enforcing certificate issuance, rotation, and client verification before Phase 2A's DSP handoff even existed would have blocked every downstream phase on a task orthogonal to proving the ingestion → DSP → triage pipeline end-to-end.

### Decision
Phase 1 and Phase 2A ship the ingestion gRPC server and `scripts/simulate_sensor.go` using `insecure.NewCredentials()`. mTLS — local self-signed CA via `scripts/generate_certs.sh`, no external ACME dependency — is deferred to Phase 5, Task 5.1, and is a hard gate before any deployment against real clinical hardware or a shared network segment.

### Consequences
* **Positive:**
  * Unblocks Phase 2A/3/4A on the critical path without waiting on certificate lifecycle tooling.
* **Negative:**
  * The current transport is not representative of the target security posture; every phase between now and Phase 5 must be treated as dev-only and never exposed off a single trusted host.
  * Satisfies FR-1.5 only once Task 5.1 is complete — until then FR-1.5 is a known open gap, not a met requirement.

---

## ADR 007: Go → Python Transport for the DSP Handoff

### Context
ADR-002 commits to "an inter-process communication stream" between the Go ingestion engine and the Python DSP pipeline without naming a mechanism. Phase 2A (`docs/ROADMAP.md`) cannot start until this is fixed, since it determines the shape of `src/dsp/kalman.py`'s input and the serialization/batching contract.

### Decision
The Go ingestion engine exposes a second, local-only gRPC service (over a Unix domain socket rather than a TCP port) that streams `OpticalFrame` batches to the Python DSP process, reusing the existing `proto/telemetry.proto` contract with an added batching wrapper message. A Unix domain socket is chosen over TCP loopback, shared memory, or a message broker (NATS/ZeroMQ/Redis) because it avoids introducing a new dependency into the offline stack, keeps a single schema source of truth (the existing `.proto` file), and has negligible latency overhead relative to the 10ms-per-frame DSP budget (NFR-1.2).

### Consequences
* **Positive:**
  * No new infrastructure dependency; reuses existing protobuf tooling and `make proto`.
  * Unix domain sockets avoid TCP/IP stack overhead and are automatically scoped to the local host, closing off network-exposure concerns for this internal hop.
* **Negative:**
  * Ties the Go and Python processes to co-location on the same host/filesystem namespace; this is acceptable for the current single-node edge deployment target but would need revisiting if the DSP pipeline is ever split onto a separate host.
  * Requires defining and versioning a frame-batching message (frame count, window duration) that does not exist in the current `.proto` file.

---

## ADR 008: Fail-Safe Default State for Autonomous Hardware Remediation

### Context
The triage agent (Phase 3) issues executable hardware commands (e.g., `FLUSH_VALVE`) derived from LLM output. FR-3.3 and NFR-5.1 define schema-validation guarantees for well-formed responses, but no requirement or ADR defines system behavior when the LLM is unreachable, times out, exceeds the 2-second latency budget (NFR-1.3), or returns a low-confidence classification. For a system that actuates physical hardware, silently doing nothing and silently doing something are both unacceptable defaults if left undefined per failure mode.

### Decision
The triage agent enforces an explicit fail-safe state machine:
1. If Ollama is unreachable or a call times out, no remediation command is issued; the anomaly is logged and surfaced via the CLI/stub interface as `REQUIRES_MANUAL_REVIEW`.
2. If `confidence_score` is returned but falls below a configured threshold (default 0.7), the system logs the LLM's suggested action but does not execute it automatically — it is queued for manual override.
3. Only responses that pass schema validation *and* meet the confidence threshold are auto-executed.
This threshold and the manual-review fallback path are themselves subject to the Promptfoo regression suite (FR-5.3).

### Consequences
* **Positive:**
  * Guarantees the system never autonomously actuates hardware on missing or low-confidence information — closes a safety-critical gap.
  * Gives clinical operators a bounded, auditable manual-override path rather than an implicit "nothing happens" failure mode.
* **Negative:**
  * Requires the CLI/stub incident feed (Task 3.4b) to exist and be monitored before Phase 3 remediation can be considered safe to enable outside of test environments.
  * Introduces a tunable (confidence threshold) that needs to be validated empirically against real anomaly data rather than chosen arbitrarily.