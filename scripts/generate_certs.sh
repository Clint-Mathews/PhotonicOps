#! /usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/certs"
mkdir -p "$OUT"

openssl genrsa -out "$OUT/ca.key" 4096
openssl req -x509 -new -nodes -key "$OUT/ca.key" -sha256 -days 365 \
    -subj "/CN=PhotonicOps Local CA" -out "$OUT/ca.crt"

openssl genrsa -out "$OUT/server.key" 2048
openssl req -new -key "$OUT/server.key" -subj "/CN=localhost" -out "$OUT/server.csr"
openssl x509 -req -in "$OUT/server.csr" -CA "$OUT/ca.crt" -CAkey "$OUT/ca.key" \
    -CAcreateserial -out "$OUT/server.crt" -days 365 -sha256 \
    -extfile <(printf "subjectAltName=DNS:localhost,DNS:ingestion-go,IP:127.0.0.1")

openssl genrsa -out "$OUT/client.key" 2048
openssl req -new -key "$OUT/client.key" -subj "/CN=mock-sensor" -out "$OUT/client.csr"
openssl x509 -req -in "$OUT/client.csr" -CA "$OUT/ca.crt" -CAkey "$OUT/ca.key" \
    -CAcreateserial -out "$OUT/client.crt" -days 365 -sha256

echo "wrote $OUT/{ca,server,client}.{crt,key}"