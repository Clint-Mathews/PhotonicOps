# syntax=docker/dockerfile:1

# --- Stage 1: Builder ---
FROM --platform=$BUILDPLATFORM golang:1.26.4 AS builder

ARG TARGETOS=linux
ARG TARGETARCH=arm64

# Allow Go to auto-fetch the exact toolchain version declared in go.mod
# if the base image has a slightly different patch version.
ENV GOTOOLCHAIN=auto

WORKDIR /build

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} \
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
