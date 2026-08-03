#!/bin/bash

echo "=========================================="
echo "    Phase 0: Environment Gate Check       "
echo "=========================================="
echo ""
echo "Checks: Ollama | Langfuse | Prometheus | ARM64 containers"
echo ""

FAILED=0

# 1. Check Ollama API
echo -n "[1/4] Checking Ollama API (localhost:11434)... "
if curl -s http://localhost:11434 > /dev/null; then
    echo "OK"
else
    echo "FAILED"
    FAILED=1
fi

# 2. Check Langfuse UI
echo -n "[2/4] Checking Langfuse API/UI (localhost:3000)... "
# Langfuse has a health endpoint, we check that to ensure the backend is truly up
if curl -s http://localhost:3000/api/public/health > /dev/null; then
    echo "OK"
else
    echo "FAILED"
    FAILED=1
fi

# 3. Check Prometheus readiness and scrape config
echo -n "[3/4] Checking Prometheus (localhost:9090)... "
# Determine the repo root relative to this script's location.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
PROM_CONFIG="$REPO_ROOT/config/prometheus/prometheus.yml"

if [ ! -f "$PROM_CONFIG" ]; then
    echo "FAILED (config/prometheus/prometheus.yml not found — run 'git status')"
    FAILED=1
elif curl -sf http://localhost:9090/-/ready > /dev/null; then
    echo "OK"
else
    echo "FAILED (container may still be starting; retry in 10s)"
    FAILED=1
fi

# 4. Check for Native Apple Silicon Execution (arm64)
echo "[4/4] Checking Container Architectures (Zero Rosetta Emulation)..."
CONTAINERS=$(docker compose ps -q)

if [ -z "$CONTAINERS" ]; then
    echo "FAILED: No containers are currently running for this project."
    FAILED=1
else
    for container in $CONTAINERS; do
        # Extract container name
        NAME=$(docker inspect --format '{{.Name}}' $container | sed 's/\///')
        
        # Get the image hash the container is running
        IMAGE=$(docker inspect --format '{{.Image}}' $container)
        
        # Check the architecture of that specific image
        IMG_ARCH=$(docker image inspect --format '{{.Architecture}}' $IMAGE)
        
        if [ "$IMG_ARCH" != "arm64" ] && [ "$IMG_ARCH" != "aarch64" ]; then
            echo "  FAILED: $NAME is running on $IMG_ARCH"
            FAILED=1
        else
            echo "  OK: $NAME is native ($IMG_ARCH)"
        fi
    done
fi

echo "=========================================="
if [ $FAILED -eq 0 ]; then
    echo "Phase Gate Passed! Ready for Phase 1."
    exit 0
else
    echo "Phase Gate Failed. Please check the errors above."
    exit 1
fi
