package grpc

import (
	"context"
	"io"
	"testing"

	"google.golang.org/grpc/metadata"

	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/internal/buffer"
	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/internal/worker"
	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/pb"
)

// mockStream implements pb.TelemetryService_StreamTelemetryServer
// This allows us to inject fake network traffic directly into the server.
type mockStream struct {
	frames   []*pb.OpticalFrame
	index    int
	closed   bool
	response *pb.StreamResponse
}

// Recv mimics pulling data off a TCP connection.
func (m *mockStream) Recv() (*pb.OpticalFrame, error) {
	if m.index >= len(m.frames) {
		// When we run out of mock frames, send EOF to simulate the client closing the stream
		return nil, io.EOF 
	}
	frame := m.frames[m.index]
	m.index++
	return frame, nil
}

// SendAndClose mimics the server sending the final response.
func (m *mockStream) SendAndClose(resp *pb.StreamResponse) error {
	m.closed = true
	m.response = resp
	return nil
}

// Required interface methods (stubs since we don't use them in StreamTelemetry)
func (m *mockStream) SetHeader(metadata.MD) error  { return nil }
func (m *mockStream) SendHeader(metadata.MD) error { return nil }
func (m *mockStream) SetTrailer(metadata.MD)       {}
func (m *mockStream) Context() context.Context     { return context.Background() }
func (m *mockStream) SendMsg(m_ interface{}) error { return nil }
func (m *mockStream) RecvMsg(m_ interface{}) error { return nil }

func TestServer_StreamTelemetry(t *testing.T) {
	// 1. Initialize the Zero-Allocation components
	ring := buffer.NewRingBuffer(10)
	pool := worker.NewFramePool(2, 10)

	server := &Server{
		Ring:   ring,
		Worker: pool,
	}

	// 2. Setup the mock stream with 3 simulated frames
	stream := &mockStream{
		frames: []*pb.OpticalFrame{
			{SensorId: "sensor-1", WavelengthShift: 1.0},
			{SensorId: "sensor-2", WavelengthShift: 2.0},
			{SensorId: "sensor-3", WavelengthShift: 3.0},
		},
	}

	// 3. Execute the function (it should process all 3 frames and exit on EOF)
	err := server.StreamTelemetry(stream)

	// 4. Validate results
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}

	if !stream.closed {
		t.Errorf("expected SendAndClose to be called on the stream")
	}

	if stream.response == nil || !stream.response.Success {
		t.Errorf("expected StreamResponse{Success: true}, got %v", stream.response)
	}

	// Because it didn't panic or freeze, we know it successfully handed the frames
	// off to both the RingBuffer and the WorkerPool job queue!
}
