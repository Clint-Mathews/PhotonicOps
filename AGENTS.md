# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project

PhotonicOps is a fully offline, air-gapped telemetry ingestion and agentic hardware triage engine for silicon photonic biosensors, targeting HIPAA-sensitive clinical environments. It ingests microfluidic optical telemetry (resonance wavelength shift, Δλ, in picometers) at 10,000 samples/sec, filters/analyzes it with DSP, and (in later phases) uses a local LLM to decide on hardware remediation actions — with zero cloud API calls of any kind.

The repo is mid-build. **Phase 0**, **Phase 1**, **Phase 2A**, and **Phase 3** are implemented; Phase 5 ingestion hardening (mTLS, `/metrics`, load-shedding, per-sensor ring buffers) is in progress — Task 5.5 (ARM64 CI artifact) is still open. `services/dashboard-ui` described in `structure.txt` **does not exist yet**. See `docs/ROADMAP.md` for phase gates and `docs/ADR.md` for the reasoning behind major decisions:

- **ADR-006:** the sensor TCP listener (`:50051`) now requires mTLS (local CA via `scripts/generate_certs.sh`). The Unix-domain DSP hop stays `insecure.NewCredentials()` on purpose (ADR-007).
- **ADR-007:** the Go→Python DSP handoff is a local gRPC service over a Unix domain socket reusing `proto/telemetry.proto`.
- **ADR-008:** the LLM triage agent must never auto-execute a hardware remediation command on an unreachable/timed-out/low-confidence response; it falls back to a `REQUIRES_MANUAL_REVIEW` state instead.

## Global constraints (from `.agents/AGENTS.md`)

These apply repo-wide and are non-negotiable:

- **Apple Silicon / ARM64 only.** Every `docker-compose.yml` service and Dockerfile must set `platform: linux/arm64`. Never introduce x86-only configs.
- **Zero cloud APIs.** No OpenAI/Anthropic/AWS/GCP calls anywhere in code. All LLM inference goes through a local Ollama instance at `localhost:11434`. All observability (Langfuse, Prometheus, Grafana) is self-hosted/local. Telemetry data must never leave the local network.
- **Go (1.22+, currently pinned to 1.26.4 via `go.work`):** lock-free/zero-allocation data structures on the critical path, `sync.Pool` for reusable buffers.
- **Python DSP (when it lands):** strictly vectorized `NumPy`/`SciPy`, no `for` loops over data arrays.
- **LLM orchestration (when it lands):** `Instructor` + `Pydantic` only — deterministic JSON output, never raw free-text generation.
- **Tone:** no emojis or conversational filler in code/comments; write complete, production-ready code (no `// ... implementation here ...` placeholders); wrap Go errors with context; raise specific custom exceptions in Python.

Per-directory AI personas under `.agents/skills/` (`go-architect`, `dsp-math`, `mlops-agent`) restate these constraints for their respective service directories — adopt the matching persona's constraints when working in that area.

## Commands

All Go commands below run from `services/ingestion-go/` unless noted. The repo uses a Go workspace (`go.work`) spanning `./scripts` and `./services/ingestion-go`.

```bash
# Issue local CA + server/client certs (gitignored under certs/)
./scripts/generate_certs.sh

# Build & run the ingestion server (from repo root; mTLS required)
go run services/ingestion-go/cmd/server/main.go \
  --ca-path certs/ca.crt \
  --cert-path certs/server.crt \
  --key-path certs/server.key

# Run the mock 10kHz sensor client against it (from repo root, separate terminal)
go run scripts/simulate_sensor.go \
  --ca-path certs/ca.crt \
  --cert-path certs/client.crt \
  --key-path certs/client.key

# Test, vet, and verify — mirrors .github/workflows/ci-ingestion-go.yml
cd services/ingestion-go
go mod verify
go vet ./...
go test -race -covermode=atomic -coverprofile=coverage.out ./...
go tool cover -func=coverage.out          # per-package coverage summary

# Run a single test
go test ./internal/buffer/ -run TestRingBuffer_Push -v

# Regenerate protobuf/gRPC Go bindings after editing proto/telemetry.proto
make init-proto   # one-time: installs protoc-gen-go and protoc-gen-go-grpc
make proto        # regenerates services/ingestion-go/pb/*.pb.go

# Bring up local infra (Prometheus, Grafana, Postgres, Langfuse, Ollama)
docker-compose up -d

# Verify Phase 0 environment gate (Ollama/Langfuse reachable, containers are native arm64)
./scripts/check_phase0.sh

# Pull the local LLM weights into the Ollama container
docker exec -it ollama-photonicops ollama run llama3.2:3b
```

CI (`.github/workflows/ci-ingestion-go.yml`) only triggers on changes under `services/ingestion-go/**`, `proto/**`, `go.work*`, or the workflow file itself. It runs `go mod verify`, `go vet`, `go test -race` with coverage, then a separate job cross-compiles a static Linux/amd64 binary (`CGO_ENABLED=0`) purely as a CI artifact — that target architecture is unrelated to the arm64 runtime requirement above, which governs Docker images actually deployed.

## Architecture: `services/ingestion-go`

Data flow for one sensor frame, from `cmd/server/main.go`:

1. `internal/grpc.Server.StreamTelemetry` receives an `OpticalFrame` over a client-streaming gRPC call (schema in `proto/telemetry.proto`; generated code lives in `pb/` — regenerate via `make proto`, don't hand-edit).
2. Each frame is pushed to **two** independent consumers, both owned by `main.go` and injected into the gRPC `Server` struct:
   - `internal/buffer.ShardedRingBuffer` — one 10,000-slot `RingBuffer` per `sensor_id` (~1 second at 10 kHz). `Push` is per-shard; map growth happens once per new sensor, not per frame.
   - `internal/worker.FramePool` — a fixed pool of goroutines (currently 10) draining a buffered channel (currently 50,000 slots) via `Enqueue`. Workers borrow/return `[]byte` scratch buffers from a package-level `sync.Pool` (`frameSyncPool`). Default `Enqueue` blocks on a full channel (TCP backpressure). `--load-shed` switches to non-blocking drop of the newest frame after `Push`.
3. `net/http/pprof` is on `localhost:6060`. Prometheus `/metrics` is on `:2112` (all interfaces). The sensor gRPC listener on `:50051` uses mTLS (`internal/grpc.ServerTLS`); plaintext clients are rejected.

`scripts/simulate_sensor.go` is a standalone gRPC client (own `go.mod`, part of the same `go.work`) that presents the issued client certificate, then streams synthetic frames at 10kHz via a `time.Ticker`, injecting Gaussian white noise and a slowly-wandering thermal-drift baseline into `WavelengthShift`.

## Environment

Copy `.env.example` to `.env` before running `docker-compose up`. It supplies Postgres credentials for Langfuse and Langfuse's own secrets (`NEXTAUTH_SECRET`, `SALT`, `ENCRYPTION_KEY`) — the example values are placeholders only, not safe defaults for anything beyond local dev.
