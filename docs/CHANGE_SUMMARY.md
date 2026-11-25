# PhotonicOps Change Summary

## Snapshot

This summary covers the current worktree compared with `HEAD`.

- There are currently **no staged changes**. `git diff --cached` is empty.
- The changes are unstaged working-tree changes: modified tracked files plus new dashboard, observability, policy-scanner, and workflow files.
- The work is not one small fix. It is a Phase 4B implementation pass connected to the existing Phase 2A, Phase 3, and Phase 5 components.
- This document describes what is present in the worktree. It does not claim that the remaining roadmap phase gates have passed.

## Executive Summary

PhotonicOps now has a local operator-facing path from high-rate sensor telemetry through DSP and fail-safe triage into a live dashboard and local observability stack.

The main change is the addition of an operational surface around the existing offline pipeline:

- Python now exposes a local HTTP/WebSocket API for health, live signal data, and manual-review incidents.
- A new React dashboard displays raw versus filtered telemetry and gives operators an incident acknowledgment workflow.
- Triage work is moved off the telemetry-serving path into a bounded background queue.
- Every triage outcome is persisted locally, including manual-review outcomes.
- Prometheus and Grafana now cover ingestion, DSP, and triage signals.
- A pull-request policy workflow checks for cloud LLM, hosted telemetry, and disallowed TCP transport regressions.
- Docker Compose includes the new services and preserves the ARM64-only deployment constraint.

## What Changed

### 1. DSP-to-Dashboard API

`services/dsp-agent-python` now runs a local FastAPI/Uvicorn surface alongside the Unix-domain-socket gRPC DSP server.

- `GET /healthz` reports local API readiness.
- `GET /incidents` returns pending manual-review incidents.
- `POST /incidents/{incident_id}/ack` records an operator acknowledgment.
- `WS /ws/signal` streams the latest signal window at approximately 30 frames per second.
- The signal payload includes raw, filtered, and baseline-removed values, sensor ID, window timestamp, and anomaly state.
- Latest-window memory is bounded to a small number of sensors and points rather than growing without limit.

This connects the existing ingestion and DSP path to a usable local control-room view without sending telemetry to a hosted service.

### 2. Safer Triage Dispatch

LLM triage is no longer performed directly on the gRPC processing path.

- A bounded dispatcher queue and background worker isolate slower local Ollama calls from telemetry handling.
- Queue saturation becomes a `REQUIRES_MANUAL_REVIEW` incident instead of blocking ingestion indefinitely.
- Unreachable Ollama, timeout, schema failure, low confidence, and unexpected triage failures route to manual review.
- Confidence below `0.7` is rejected for automatic handling.
- Triage outcomes have stable IDs derived from the sensor and evaluation context.
- Outcome counters and triage latency are exported to Prometheus.

Important safety boundary: the code currently records an accepted high-confidence result as `AUTO_EXECUTED`, but there is no physical hardware executor wired into this worktree. That status means the safety gate accepted the decision; it does not prove that a real valve or optical mechanism was actuated.

### 3. Local Incident Feed

The incident feed has been expanded from a Phase 3 stub into a local persistence and API workflow.

- Every triage outcome is appended to a local JSONL incident log.
- Manual-review items are returned newest first.
- Acknowledgments are appended to a separate JSONL log, preserving an append-only history.
- The dashboard can acknowledge an incident without rewriting prior records.
- Incident storage is mounted into the Python container through the `dsp_incidents` Docker volume.

The active implementation uses JSONL. Existing requirements and ADR text that describe the audit-storage decision as open should be updated separately if JSONL is accepted as the project decision.

### 4. React Dashboard

A new ARM64-compatible React 19/Vite/TypeScript dashboard exists under `services/dashboard-ui`.

- HTML5 Canvas renders raw and filtered wavelength traces.
- `requestAnimationFrame` drives the 30 FPS rendering loop.
- A manual-review panel polls for incidents and supports acknowledgment.
- Metrics and local-runtime panels link the operator to the local stack.
- Responsive CSS supports desktop and mobile layouts.
- The dashboard is served by an Nginx container at `http://localhost:5173`.

The browser currently opens one signal WebSocket and renders the first window returned by the API. Multiple active sensors are retained in the bounded backend store but are not yet shown simultaneously in the UI.

### 5. Prometheus and Grafana

The local observability stack now includes Python DSP and triage metrics in addition to Go ingestion metrics.

- Prometheus scrapes Prometheus, Grafana, Go ingestion, and Python DSP/triage endpoints.
- Grafana is provisioned with a local Prometheus datasource and a PhotonicOps dashboard.
- Dashboard panels cover ingestion throughput, Go worker queue depth, ring occupancy, DSP processing latency, triage latency, and triage outcomes.
- Python metrics include DSP processing duration, detected spikes, triage evaluation duration, and triage outcome counts.

Known observability caveats:

- The Grafana panel named `DSP queue depth` currently queries the Go ingestion worker queue.
- Using unbounded `sensor_id` values as Prometheus labels could create high cardinality.
- The existing Go dropped-frame metric name contains the earlier `photocnics` spelling and was not corrected here.
- No live Grafana rendering or live Prometheus scrape test is included yet.

### 6. ARM64 Compose and Runtime Wiring

Docker Compose now wires the dashboard and the Python API into the local runtime.

- Python ports `8000` and `8001` are exposed for the API/WebSocket and metrics exporter.
- Dashboard port `5173` is exposed.
- Python has a `/healthz` container healthcheck.
- Grafana provisioning files are mounted into the Grafana container.
- Incident logs persist through a named volume.
- Python and dashboard images target `linux/arm64`.

The normal local prerequisites remain: copy `.env.example` to `.env`, generate certificates, and pull the Ollama model. Compose startup order does not itself guarantee that the Python UDS server is ready before Go connects.

### 7. Privacy and Transport Regression Gate

A new pull-request workflow, `.github/workflows/ai-review.yml`, runs a local policy scanner and its tests.

The scanner checks selected Python, Go, YAML, and workflow files for:

- Cloud LLM endpoints.
- Hosted telemetry endpoints.
- Anthropic references and unsupported OpenAI clients.
- Disallowed insecure TCP gRPC credentials.
- Required repository constraint files.

The existing Go workflow also removes the external Codecov upload while retaining local coverage artifacts.

This is a lightweight policy gate, not a complete compliance or security review. The scanner does not currently cover every file type or enforce every repository rule, and dashboard-only changes are not included in the existing Go/Python path filters.

### 8. Roadmap and README Updates

The roadmap now marks the Phase 4B implementation tasks as complete:

- Task 4.2: Real-time UI.
- Task 4.3: Prometheus integration.
- Task 4.4: AI-reviewed CI/CD gate.

The Phase 4B gate remains open until browser, incident-feed, and PR-enforcement checks are verified. README runtime links now include the dashboard, DSP health endpoint, Python metrics, and expanded Grafana/Prometheus coverage.

## Verification

The following checks were recorded as passing for this worktree:

- Python tests: 17 passed.
- Python DSP benchmark: approximately `0.069 ms` mean for a 1,000-sample batch on the development machine.
- Dashboard production build: passed with `npm run build`.
- Privacy policy scanner: passed.
- Privacy policy scanner tests: 3 passed.
- `docker compose config --quiet`: passed.
- Go test suite: passed.
- `git diff --check`: passed.

## Verification Still Needed

These checks are not covered by the current change set:

- Go race-detector verification locally.
- End-to-end sensor to Go to UDS to Python to dashboard validation.
- Dashboard Docker build and runtime test.
- Browser-level 30 FPS, reconnect, and multi-sensor tests.
- Live Ollama and Langfuse integration tests.
- mTLS handshake integration tests.
- Queue-saturation, shutdown, generic-exception, persistence-failure, and non-empty WebSocket tests.
- Live Prometheus scrape and Grafana panel verification.
- PR branch-protection verification that requires the AI review workflow.

## Remaining Roadmap Work

The next formal work is:

1. **Phase 4A / Task 4.1:** Build the Promptfoo evaluation suite, including fail-safe cases, and pass the greater-than-95-percent accuracy gate.
2. **Phase 5 / Task 5.5:** Add a native `linux/arm64` CI binary artifact, then close the Phase 5 gate.
3. **Phase 4B gate:** Complete environment-level verification for the dashboard, incident queue, metrics, and PR policy enforcement.
4. **Phase 2B / Task 2.4:** Add biomarker extraction and validate concentration estimates against mock-sensor ground truth.

The full definition of done also requires all phase gates, current documentation, zero cloud API calls, and a working end-to-end stack on a clean ARM64 machine.

## Social Content Source Material

### Core narrative

PhotonicOps moved from a backend pipeline toward a local operational control room: telemetry is filtered at the edge, anomalies are triaged by a local model, uncertain outcomes are routed to humans, and operators can inspect live signals and incidents without a cloud dependency.

### Proof points

- 10,000 samples per second remains the ingestion target.
- Raw versus filtered signal is visible in a 30 FPS Canvas view.
- Manual-review incidents are persisted locally and can be acknowledged.
- Local Prometheus and Grafana dashboards cover ingestion, DSP, and triage behavior.
- Ollama, Langfuse, Prometheus, Grafana, Go, Python, and the dashboard are wired for an ARM64 local deployment.
- A pull-request scanner checks for cloud LLM and insecure transport regressions.

### Claims to avoid

- Do not say physical hardware remediation is already executing; no hardware executor is wired yet.
- Do not say the Phase 4B gate is complete; implementation tasks are marked complete but environment-level checks remain.
- Do not describe the system as HIPAA-certified or clinically production-ready.
- Do not claim the dashboard currently displays multiple sensors simultaneously.
- Do not claim full compliance enforcement from the policy scanner.

### Draft short post

PhotonicOps now has a local edge control room for silicon photonic telemetry. The pipeline takes high-rate sensor data through DSP, routes anomalies to a local Ollama model, sends uncertain decisions to a manual-review queue, and exposes live raw-versus-filtered signals through a React dashboard. Prometheus, Grafana, and CI policy checks keep the system observable and cloud-free on ARM64.

### Draft technical post

This iteration connected the full local path around PhotonicOps: bounded DSP state, background triage dispatch, fail-safe incident persistence, a 30 FPS Canvas dashboard, Prometheus/Grafana provisioning, and a pull-request scanner for cloud-LLM and insecure-transport regressions. The important boundary remains explicit: low-confidence, timeout, unreachable, and invalid responses become `REQUIRES_MANUAL_REVIEW` rather than triggering unsafe automation.

### Suggested next-post themes

- Why fail-safe triage matters more than raw model fluency in hardware systems.
- How a 10 kHz telemetry path can remain responsive while local LLM work runs asynchronously.
- Building observability for an air-gapped system with Prometheus and Grafana.
- Why the next milestone is evaluation evidence, not another feature: Phase 4A Promptfoo testing.
