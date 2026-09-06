package main

import (
	"flag"
	"log"
	"net"
	"net/http"
	_ "net/http/pprof" // Blank import to automatically register /debug/pprof/ endpoints

	"google.golang.org/grpc"

	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/internal/buffer"
	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/internal/dsp"
	mygrpc "github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/internal/grpc"
	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/internal/metrics"
	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/internal/worker"
	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/pb"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

func main() {
	// 1. Start pprof in the background for memory profiling and prometheus for metrics
	go func() {
		log.Println("Starting pprof debug server on :6060")
		log.Println(http.ListenAndServe("localhost:6060", nil))
	}()

	go func() {
		mux := http.NewServeMux()
		mux.Handle("/metrics", promhttp.Handler())
		log.Println("Prometheus metrics on : 2112")
		log.Println(http.ListenAndServe(":2112", mux))
	}()

	// 2. Initialize our Zero-Alloc components
	loadShed := flag.Bool("load-shead", false, "drop frames when jobQueue is full instead of blocking")
	flag.Parse()
	ring := buffer.NewRingBuffer(10000) // Hold last 1 second of data
	forwarder, err := dsp.NewForwarder()
	if err != nil {
		log.Fatalf("failed to connect to DSP process: %v", err)
	}
	pool := worker.NewFramePool(10, 50000, forwarder, *loadShed) // 10 workers, channel buffer of 50k

	metrics.RegisterGuages(
		func() float64 { return float64(pool.QueueDepth()) },
		func() float64 { return float64(ring.Occupancy()) },
	)

	// 3. Setup gRPC ``Server
	lis, err := net.Listen("tcp", ":50051")
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	grpcServer := grpc.NewServer()
	telemetryServer := &mygrpc.Server{
		Ring:   ring,
		Worker: pool,
	}

	pb.RegisterTelemetryServiceServer(grpcServer, telemetryServer)

	log.Println("gRPC Ingestion Server listening on :50051")
	if err := grpcServer.Serve(lis); err != nil {
		log.Fatalf("failed to serve: %v", err)
	}
}
