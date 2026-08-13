# syntax=docker/dockerfile:1

# --- Stage 1: Runtime ---
FROM --platform=$BUILDPLATFORM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir -e .

# --- Stage 2: Runtime ---
FROM --platform=linux/arm64 python:3.11-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app /app

CMD ["python", "-m", "src.main"]
