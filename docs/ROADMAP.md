# Implementation & Progression Guide

## System: PhotonicOps
**Execution Strategy:** AI-First Constraint-Driven Development ("Antigravity" Workflow)
**Host Architecture:** Apple Silicon (M1/ARM64)

This document outlines the step-by-step progression plan for building PhotonicOps. It defines the sequence of execution, which AI developer personas to invoke at each step, and the strict technical phase-gates required to move forward.

## Execution Order

```
Phase 0  [x]
Phase 1  [x]
Phase 2A [x]
Phase 3  [ ]
Phase 4A [ ]
Phase 5  [ ]
Phase 4B [ ]
Phase 2B [ ]
```

| Sequence | Phase | Contents |
|---|---|---|
| 1 | **2A** | Tasks 2.1, 2.2, 2.3 |
| 2 | **3** | Agentic triage |
| 3 | **4A** | Task 4.1 — eval suite |
| 4 | **5** | Ingestion hardening |
| 5 | **4B** | Tasks 4.2, 4.3, 4.4 — dashboard, remaining metrics, CI gate |
| 6 | **2B** | Task 2.4 — biomarker extraction |

Tasks 2.4 and 4.2 are deferred; each deferral is recorded as an ADR with rationale. ADR-006 (mTLS relaxation) is the reference pattern for this.

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

## [x] Phase 2A: Minimum Viable DSP
**Goal:** Produce a clean, flagged anomaly stream that Phase 3 can triage. Nothing more — Task 2.4 is explicitly not in this phase.

* [x] **Task 2.0: Go → Python IPC Contract**
  * Implement the Unix-domain-socket local gRPC transport decided in ADR-007, including the frame-batching wrapper message added to `proto/telemetry.proto`. This blocks every other task in this phase.
  * *AI Persona:* `@go-architect` (Go side), `@dsp-math` (Python client side)
* [x] **Task 2.1: DSP Environment Setup**
  * Scaffold `services/dsp-agent-python/requirements.txt`.
  * *Constraint:* Ensure native ARM64 wheels for `NumPy` and `SciPy` (Accelerate framework compatibility).
  * *Verify:* `python -c "import numpy; numpy.show_config()"` shows Accelerate linkage, not a generic BLAS fallback.
* [x] **Task 2.2: Kalman Filter & Baseline Subtraction**
  * Write `src/dsp/kalman.py`. Process the incoming Go telemetry IPC stream (Task 2.0) in vectorized chunks.
  * *Constraint:* vectorized NumPy only. **No Python `for` loops over data arrays** (`@dsp-math` rule).
  * *Target:* <10 ms per frame.
  * *AI Persona:* `@dsp-math`
* [x] **Task 2.3: Anomaly Detection**
  * Write `src/dsp/spike_detector.py` to identify micro-bubbles via first-derivative thresholding ($|\frac{d\lambda}{dt}| > \text{threshold}$).
  * Tune against the mock sensor's injected spikes; record the false-positive rate.
  * *AI Persona:* `@dsp-math`
* [x] **Task 2.A.1: Deferral ADR**
  * Record the decision to defer Task 2.4 (biomarker extraction) and Task 4.2 (dashboard), with rationale and re-entry criteria.
* [x] **Phase Gate (2A):** Python pipeline receives Go telemetry over UDS, smooths signal in <10 ms/frame, and reliably flags synthetic anomalies with a documented false-positive rate. **No biomarker output required to pass.**

---

## [ ] Phase 3: LLMOps & Agentic Hardware Triage
**Goal:** Deterministic, zero-hallucination hardware remediation on the local M1 GPU.

* [ ] **Task 3.1: Hardware Skills & Schema**
  * Define strict hardware action schemas in `src/agent/schema.py` using Pydantic.
  * Include `RemediationDecision`, `confidence_score`, enumerated action types (`FLUSH_VALVE` etc.), and explicit refusal states.
* [ ] **Task 3.2: Instructor Integration & Triage Engine**
  * Build `src/agent/triage.py` to prompt local Ollama via `Instructor`. Input: flagged DSP frame. Output: structured `RemediationDecision`.
  * *AI Persona:* `@mlops-agent`
* [ ] **Task 3.3: Langfuse Tracing**
  * Wrap the LLM calls with `@observe()` decorators to log token usage and latency to the local Langfuse instance.
* [ ] **Task 3.4: Fail-Safe State Machine** — the safety-critical task
  * Implement the unreachable/timeout/low-confidence handling defined in ADR-008: **no `remediation_action` is auto-executed** unless the response is schema-valid *and* `confidence_score` clears the configured threshold. Otherwise → `REQUIRES_MANUAL_REVIEW`.
  * Handle: schema-invalid · below-threshold confidence · timeout · unreachable.
  * *Dependency:* requires at minimum a stub of the Phase 4B incident feed (FR-4.2) to surface manual-review items. **Do not enable autonomous execution against real hardware endpoints until that exists.**
  * **Write the test that proves no action auto-executes on low confidence.** This test is the deliverable.
  * Satisfies FR-3.5.
  * *AI Persona:* `@mlops-agent`
* [ ] **Task 3.4b: Incident Feed Stub**
  * Minimal surface for `REQUIRES_MANUAL_REVIEW` items so Task 3.4 is unblocked without building the full Phase 4B dashboard.
* [ ] **Task 3.5: Diagnostic Audit Log**
  * Persist every triage decision — auto-executed, manual-review, manual-override — with timestamp and triggering telemetry window.
  * **Open decision to resolve at task start:** local Postgres vs. reusing the Langfuse database. Record as an ADR.
  * Satisfies FR-3.6.
* [ ] **Phase Gate (3):** Bubble detected → local Llama 3.1 emits well-formed `FLUSH_VALVE` JSON in <2.0 s · low-confidence and unreachable cases correctly fall back to `REQUIRES_MANUAL_REVIEW` without executing · both outcomes appear in the audit log.

---

## [ ] Phase 4A: Evaluation Suite
**Goal:** Prove the agent's reliability mathematically rather than anecdotally.

* [ ] **Task 4.1: Prompt Evaluation Suite**
  * Build `evals/test_cases.json`. Design the labelled scenario set across four classes: **clean · noisy · ambiguous · adversarial**.
  * Configure Promptfoo for regression testing against synthetic noise profiles.
  * Score: remediation accuracy, false-positive rate, p50/p95 latency.
  * **Include the Phase 3 fail-safe paths (Task 3.4) as explicit eval cases** — an agent that correctly refuses is passing, not failing.
  * Keep a record of prompts that didn't work; the failure log is as valuable as the pass rate.
  * Satisfies FR-5.3.
  * *AI Persona:* `@mlops-agent`
* [ ] **Phase Gate (4A):** Promptfoo evaluations pass at >95% remediation accuracy **including** fail-safe paths. Eval suite runs reproducibly from a single command.

After this gate the agentic triage system may be described as built, not architected. Update the project README accordingly — and not before.

---

## [ ] Phase 5: Ingestion Hardening
**Goal:** Close the remaining SRS gaps required before any production deployment.

Task 5.1 (mTLS) must be completed before any deployment against real clinical hardware or a shared network segment; plaintext transport is acceptable on a local single host until then (ADR-006).

* [ ] **Task 5.1: Transport Security**
  * mTLS on the ingestion gRPC server and mock sensor client, replacing `insecure.NewCredentials()`.
  * Local self-signed CA, no external ACME dependency. `scripts/generate_certs.sh` already exists.
  * Satisfies FR-1.5 / ADR-006. *AI Persona:* `@go-architect`
* [ ] **Task 5.2: Prometheus Metrics Endpoint**
  * Export `/metrics`: frames/sec, `jobQueue` depth, ring buffer occupancy.
  * Required before Phase 4B Task 4.3 Grafana wiring can be completed.
  * Satisfies FR-1.4 / NFR-6.1.
* [ ] **Task 5.3: Load-Shedding Mode**
  * Opt-in non-blocking `select`/`default` send path in `internal/worker/pool.go::Enqueue` per `docs/FAQ/PHASE1.md` Q5, behind a `--load-shed` startup flag.
  * Verify under artificial backlog; measure and document what gets dropped and when.
  * Satisfies FR-1.3.
* [ ] **Task 5.4: Per-Sensor Ring Buffer Sharding**
  * Key `internal/buffer.RingBuffer` by `sensor_id` (or size it for concurrent multi-sensor retention) so historical depth doesn't collapse under NFR-4.1 load.
  * Satisfies NFR-4.2.
* [ ] **Task 5.5: CI ARM64 Build Target**
  * Fix the `build-binary` job in `.github/workflows/ci-ingestion-go.yml` to produce a `linux/arm64` artifact alongside `linux/amd64`.
  * Satisfies NFR-2.1.
* [ ] **Phase Gate (5):** Ingestion server rejects non-mTLS connections · `/metrics` scrapeable and wired into Grafana · load-shedding togglable and verified under backlog · per-sensor history retrievable independently of other streaming sensors · CI produces a native ARM64 binary.

---

## [ ] Phase 4B: Observability & Dashboard
**Goal:** Expose internal system state visually.

* [ ] **Task 4.2: Real-Time UI**
  * React/TypeScript dashboard in `services/dashboard-ui/`.
  * HTML5 Canvas or WebGL chart (Chart.js or similar) over WebSockets, plotting Raw vs. Filtered signal at 30 FPS.
  * Promote the Task 3.4b incident-feed stub into the full manual-review queue.
  * Satisfies FR-4.1 / FR-4.2.
* [ ] **Task 4.3: Prometheus Integration**
  * Wire remaining DSP/agent processing-time metrics to Prometheus/Grafana. (Go ingestion `/metrics` shipped in Task 5.2.)
  * Satisfies FR-4.3.
* [ ] **Task 4.4: AI-Reviewed CI/CD Gate**
  * Add `.github/workflows/ai-review.yml` (referenced in `structure.txt`, not yet present) — scan PRs for data-privacy regressions (reintroduced cloud API calls, disabled mTLS) and `.agents/AGENTS.md` constraint violations.
  * Satisfies FR-5.2.
* [ ] **Phase Gate (4B):** Dashboard renders at 30 FPS without crashing the tab · manual-review queue functional · AI-review CI gate active on PRs.

---

## [ ] Phase 2B: Biomarker Extraction
**Goal:** Complete the original scientific scope.

* [ ] **Task 2.4: Biomarker Extraction**
  * Extract steady-state optical saturation values; calculate estimated target protein concentration (ng/mL).
  * Satisfies FR-2.3.
  * *AI Persona:* `@dsp-math`
* [ ] **Phase Gate (2B):** Pipeline produces a biomarker concentration estimate consistent with the mock sensor's ground truth.

---

## Definition of Done — full system

- [ ] All phase gates passed
- [ ] Every deferral documented as an ADR with re-entry criteria
- [ ] README accurately states build status per phase — no "architected" language for anything shipped, no "built" language for anything designed
- [ ] Zero cloud API calls anywhere in the codebase (enforced by Task 4.4)
- [ ] `docker-compose up -d` → working end-to-end system on a clean ARM64 machine
