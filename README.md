# PhotonicOps 🔬⚡

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![HIPAA Compliant](https://img.shields.io/badge/Compliance-HIPAA_Ready-success.svg)
![Go Version](https://img.shields.io/badge/Go-1.26+-00ADD8.svg)
![Python Version](https://img.shields.io/badge/Python-3.11+-3776AB.svg)

**PhotonicOps** is a 100% open-source, edge-deployed, and completely air-gapped telemetry ingestion and agentic hardware triage engine for silicon photonic biosensors. 

Designed for clinical environments where data privacy is paramount, PhotonicOps runs a local pipeline that ingests microfluidic telemetry at 10,000 samples per second, processes the signals to detect anomalies (thermal drift, micro-bubbles, clogs), and uses a local Large Language Model (LLM) to orchestrate hardware remediation—with **zero cloud API dependencies**.

---

## 🏗️ System Architecture

The system is built on a high-throughput, low-latency microservices architecture:

1. **Ingestion (Go):** A high-performance gRPC server utilizing goroutine worker pools and zero-allocation ring buffers. It captures raw optical wavelength shifts (Δλ) at $\ge 10,000\text{ Hz}$ with a $p_{99}$ latency of $< 2\text{ ms}$.
2. **DSP Pipeline (Python):** Applies 1D Kalman Filtering, baseline subtraction, and derivative thresholding to filter noise and detect physical anomalies in real-time (frame processing $< 10\text{ ms}$).
3. **Agentic Triage (Python + Local LLM):** When the signal-to-noise ratio drops below 12 dB, the system triggers a local Llama 3.1 (8B) model via Ollama. Using `Instructor` and `Pydantic`, the LLM generates strict, deterministic JSON commands to trigger automated hardware remediation.
4. **Observability:** Langfuse (self-hosted) traces LLM reasoning steps, while Prometheus and Grafana track ingestion metrics.
5. **Dashboard UI:** A React + TypeScript frontend providing a 30 FPS WebSocket-driven canvas plotting raw vs. filtered signals.

---

## 🛠️ Tech Stack

* **Ingestion Engine:** Go, `google.golang.org/grpc`
* **Signal Processing (DSP):** Python, `NumPy`, `SciPy`, `FilterPy`
* **Local AI Agent:** Ollama / vLLM (`llama3.1:8b` or `qwen2.5:7b`)
* **Schema Enforcement:** `Instructor-Python`, `Pydantic`
* **MLOps & Tracing:** Langfuse (Docker), Promptfoo (CLI)
* **Metrics & UI:** Prometheus, Grafana, React, TypeScript, Tailwind CSS, Chart.js
* **Orchestration:** Docker, Docker Compose

---

## 🚀 Getting Started

### Prerequisites
* Docker and Docker Compose
* Minimum 16GB RAM
* GPU (NVIDIA/Apple Silicon) is highly recommended for Ollama inference latency

### Quick Start
The entire stack is containerized for a one-click deployment.

```bash
# 1. Clone the repository
git clone [https://github.com/Clint-Mathews/PhotonicOps.git](https://github.com/Clint-Mathews/PhotonicOps.git)
cd PhotonicOps

# 2. Spin up the stack (Go Engine, Python DSP, Ollama, Langfuse, UI, Prometheus)
docker-compose up -d

# 3. Start the mock sensor stream (generates 10kHz gRPC telemetry)
go run scripts/simulate_sensor.go