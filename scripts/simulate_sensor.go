package main

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"flag"
	"fmt"
	"log"
	"math/rand/v2"
	"os"
	"time"

	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/pb"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
)

func clientTLS(caFile, certFile, keyFile string) (credentials.TransportCredentials, error) {
	ca, err := os.ReadFile(caFile)
	if err != nil {
		return nil, fmt.Errorf("read CA: %w", err)
	}
	pool := x509.NewCertPool()
	if !pool.AppendCertsFromPEM(ca) {
		return nil, fmt.Errorf("parse CA")
	}
	cert, err := tls.LoadX509KeyPair(certFile, keyFile)
	if err != nil {
		return nil, fmt.Errorf("load client cert: %w", err)
	}
	cfg := &tls.Config{
		RootCAs:      pool,
		Certificates: []tls.Certificate{cert},
		MinVersion:   tls.VersionTLS13,
		ServerName:   "localhost",
	}
	return credentials.NewTLS(cfg), nil
}

func main() {
	caPath := flag.String("ca-path", "certs/ca.crt", "path to CA certificate")
	certPath := flag.String("cert-path", "certs/client.crt", "path to client certificate")
	keyPath := flag.String("key-path", "certs/client.key", "path to client private key")
	flag.Parse()

	log.Println("Connecting to ingeston server at localhost:50051...")
	creds, err := clientTLS(*caPath, *certPath, *keyPath)
	if err != nil {
		log.Fatalf("mtls: %v", err)
	}
	conn, err := grpc.NewClient("localhost:50051", grpc.WithTransportCredentials(creds))
	if err != nil {
		log.Fatalf("did not connect: %v", err)
	}
	defer conn.Close()

	client := pb.NewTelemetryServiceClient(conn)

	// 2. Open the gRPC Stream (Notice we use context.Background() becuase it runs forever)
	stream, err := client.StreamTelemetry(context.Background())
	if err != nil {
		log.Fatalf("failed to open stream: %v", err)
	}

	// 3. Ticket to send 10,000 frames per second (every 100 microsecond)
	ticker := time.NewTicker(100 * time.Microsecond)
	defer ticker.Stop()

	log.Println("Streaming synthetic physics data at 10KHz...")

	var baseline float64 = 0.0

	for {
		<-ticker.C // Wait for the 100-microsecond tick
		// Simulate Physics:
		// White Noise: Random jitter between -0.5 and +0.5 pm
		noise := (rand.Float64() - 0.5)

		// Thermal Dritf: The baseline slowly wanders up or down over time
		baseline += (rand.Float64() - 0.5) * 0.01

		// Build the Frame
		frame := &pb.OpticalFrame{
			Timestamp:       time.Now().UnixNano(),
			SensorId:        "sensor-01",
			WavelengthShift: baseline + noise,
		}
		// Send it over the open TCP connection
		if err := stream.Send(frame); err != nil {
			log.Fatalf("Failed to send frame: %v", err)
		}
	}

}
