# syntax=docker/dockerfile:1

# --- Stage 1: Builder ---
FROM --platform=linux/arm64 golang:1.24-bullseye AS builder

WORKDIR /build

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=arm64 \
    go build \
    -ldflags="-s -w" \
    -trimpath \
    -o /bin/ingestion-server \
    ./cmd/server

# --- Stage 2: Runtime ---
FROM --platform=linux/arm64 gcr.io/distroless/static-debian12:nonroot

COPY --from=builder /bin/ingestion-server /ingestion-server

EXPOSE 50051
EXPOSE 6060

USER nonroot

ENTRYPOINT ["/ingestion-server"]
