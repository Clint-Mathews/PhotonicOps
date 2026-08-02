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