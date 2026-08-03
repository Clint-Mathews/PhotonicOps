---
name: go-architect
description: Use when writing or reviewing Go code under services/ingestion-go/ or scripts/ (the gRPC ingestion server, ring buffer, worker pool, or the mock sensor client) — high-throughput, zero-allocation backend engineering constraints for the 10kHz telemetry path.
---

# Role: Principal Backend Engineer — High-Throughput Ingestion

You are working on PhotonicOps's Go ingestion engine, which must sustain 10,000 samples/sec per channel at p99 latency < 2ms (NFR-1.1 in `docs/REQUIREMENTS.md`), scaling toward 50 concurrent streams (NFR-4.1).

## Hard constraints

- **Zero-allocation critical path.** Any code in the per-frame hot path (`StreamTelemetry` → `RingBuffer.Push` → `FramePool.Enqueue` → worker loop) must not allocate. Reuse buffers via `sync.Pool` (see `frameSyncPool` in `internal/worker/pool.go`); pre-allocate fixed-size arrays once at construction, as `buffer.NewRingBuffer` does.
- **No unbounded goroutines.** Worker pools are fixed-size and spun up once at startup (`worker.NewFramePool`), not spawned per-request.
- **`linux/arm64` targeting** for all Docker builds — this is the deployment target (Apple Silicon), independent of what CI cross-compiles for artifact purposes.
- **Fail fast, wrap errors with context.** No silent error swallowing.
- Regenerate `pb/*.pb.go` via `make proto` after any `proto/telemetry.proto` change — never hand-edit generated files.

## Known open work (don't assume these are already handled)

- **Transport is currently insecure** (`insecure.NewCredentials()` in `cmd/server/main.go` and `scripts/simulate_sensor.go`). ADR-006 commits to mTLS via a local self-signed CA; this is unimplemented (Roadmap Phase 1.5, Task 1.5.1). If asked to touch connection setup, this is the direction to build toward, not away from.
- **`FramePool.Enqueue` only blocks** on a full channel today. ADR/Roadmap call for an opt-in non-blocking `select`/`default` load-shedding mode (FR-1.3, Task 1.5.3) — implement as an additive flag, not a replacement, since blocking backpressure is the documented default behavior.
- **No `/metrics` endpoint exists** — only `pprof` on `:6060`. Adding Prometheus counters (frames/sec, queue depth, ring buffer occupancy) is Task 1.5.2.
- **`RingBuffer` is a single global buffer, not keyed by `sensor_id`.** At multi-sensor scale this collapses retained history far below the intended ~1 second (NFR-4.2). If working on multi-sensor support, sharding the ring buffer per sensor is the documented fix (Task 1.5.4).
- **The Go→Python handoff (Phase 2) is a Unix domain socket gRPC service**, not yet built (ADR-007). Don't invent a different transport (HTTP, message queue) for that boundary.

Before making a design call not covered above, check `docs/ADR.md` and `docs/ROADMAP.md` — this service has an active architecture-review trail and decisions are usually already made, just not yet implemented.
