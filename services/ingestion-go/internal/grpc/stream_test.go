package grpc

import (
	"context"
	"io"
	"testing"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/metadata"

	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/internal/buffer"
	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/internal/dsp"
	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/internal/metrics"
	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/internal/worker"
	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/pb"
	dto "github.com/prometheus/client_model/go"
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

// noopDSPClient is a pb.DSPServiceClient that discards all batches. It prevents
// the stream test's worker goroutines from panicking on forwarder.Push when
// frames reach the worker before the test exits.
type noopDSPClient struct{}

type noopStream struct{ grpc.ClientStream }

func (s *noopStream) Send(_ *pb.FrameBatch) error { return nil }
func (s *noopStream) CloseAndRecv() (*pb.DSPAck, error) {
	return &pb.DSPAck{Accpeted: true}, nil
}

func (c *noopDSPClient) StreamBatches(_ context.Context, _ ...grpc.CallOption) (pb.DSPService_StreamBatchesClient, error) {
	return &noopStream{}, nil
}

func newTestServer(workers, queueSize int, loadShed bool) *Server {
	return &Server{
		Ring:   buffer.NewRingBuffer(10),
		Worker: worker.NewFramePool(workers, queueSize, dsp.NewForwarderWithClient(&noopDSPClient{}), loadShed),
	}
}

func twoFrames() []*pb.OpticalFrame {
	return []*pb.OpticalFrame{
		{SensorId: "sensor-1", WavelengthShift: 1.0},
		{SensorId: "sensor-2", WavelengthShift: 2.0},
	}
}

func counterValue(t *testing.T, c interface{ Write(*dto.Metric) error }) float64 {
	t.Helper()
	var m dto.Metric
	if err := c.Write(&m); err != nil {
		t.Fatalf("read counter: %v", err)
	}
	return m.GetCounter().GetValue()
}

func TestServer_StreamTelemetry(t *testing.T) {
	server := newTestServer(2, 10, false)

	stream := &mockStream{
		frames: []*pb.OpticalFrame{
			{SensorId: "sensor-1", WavelengthShift: 1.0},
			{SensorId: "sensor-2", WavelengthShift: 2.0},
			{SensorId: "sensor-3", WavelengthShift: 3.0},
		},
	}

	err := server.StreamTelemetry(stream)

	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}

	if !stream.closed {
		t.Errorf("expected SendAndClose to be called on the stream")
	}

	if stream.response == nil || !stream.response.Success {
		t.Errorf("expected StreamResponse{Success: true}, got %v", stream.response)
	}
}

func TestServer_StreamTelemetry_BlocksWhenQueueFull(t *testing.T) {
	// Zero workers: nothing drains jobQueue, so the second Enqueue blocks StreamTelemetry.
	server := newTestServer(0, 1, false)
	stream := &mockStream{frames: twoFrames()}

	done := make(chan struct{})
	go func() {
		_ = server.StreamTelemetry(stream)
		close(done)
	}()

	select {
	case <-done:
		t.Fatal("StreamTelemetry returned while jobQueue was full; expected blocking backpressure")
	case <-time.After(100 * time.Millisecond):
		// still blocked — expected
	}

	if stream.closed {
		t.Error("SendAndClose must not run while Enqueue is blocked on a full jobQueue")
	}
	if got := server.Worker.QueueDepth(); got != 1 {
		t.Errorf("QueueDepth = %d, want 1", got)
	}
}

func TestServer_StreamTelemetry_LoadShedCompletesWhenQueueFull(t *testing.T) {
	server := newTestServer(0, 1, true)
	stream := &mockStream{frames: twoFrames()}

	beforeDropped := counterValue(t, metrics.FramesDroppedTotal)
	beforeTotal := counterValue(t, metrics.FramesTotal)

	done := make(chan struct{})
	var streamErr error
	go func() {
		streamErr = server.StreamTelemetry(stream)
		close(done)
	}()

	select {
	case <-done:
	case <-time.After(100 * time.Millisecond):
		t.Fatal("load-shed StreamTelemetry blocked on a full jobQueue; expected an immediate drop")
	}

	if streamErr != nil {
		t.Fatalf("expected no error, got %v", streamErr)
	}
	if !stream.closed {
		t.Error("expected SendAndClose to be called on the stream")
	}
	if stream.response == nil || !stream.response.Success {
		t.Errorf("expected StreamResponse{Success: true}, got %v", stream.response)
	}

	if got := counterValue(t, metrics.FramesDroppedTotal); got != beforeDropped+1 {
		t.Errorf("FramesDroppedTotal: got %v, want %v", got, beforeDropped+1)
	}
	if got := counterValue(t, metrics.FramesTotal); got != beforeTotal+2 {
		t.Errorf("FramesTotal: got %v, want %v (both frames counted before Enqueue)", got, beforeTotal+2)
	}
	if got := server.Ring.Occupancy(); got != 2 {
		t.Errorf("ring occupancy = %d, want 2 (load-shed drops the worker handoff, not the UI buffer)", got)
	}
}
