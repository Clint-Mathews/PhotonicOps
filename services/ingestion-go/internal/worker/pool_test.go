package worker

import (
	"context"
	"testing"
	"time"

	"google.golang.org/grpc"

	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/internal/dsp"
	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/internal/metrics"
	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/pb"
	dto "github.com/prometheus/client_model/go"
)

// noopStream and noopDSPClient satisfy the DSPServiceClient interface with
// zero-overhead no-ops, so pool tests can exercise Enqueue without requiring
// a live Unix socket or risking nil pointer dereferences in worker goroutines.
type noopStream struct{ grpc.ClientStream }

func (s *noopStream) Send(_ *pb.FrameBatch) error       { return nil }
func (s *noopStream) CloseAndRecv() (*pb.DSPAck, error) { return &pb.DSPAck{Accpeted: true}, nil }

type noopDSPClient struct{}

func (c *noopDSPClient) StreamBatches(_ context.Context, _ ...grpc.CallOption) (pb.DSPService_StreamBatchesClient, error) {
	return &noopStream{}, nil
}

func testFrame() *pb.OpticalFrame {
	return &pb.OpticalFrame{
		SensorId:        "test-sensor",
		WavelengthShift: 1.23,
	}
}

func counterValue(t *testing.T) float64 {
	t.Helper()
	var m dto.Metric
	if err := metrics.FramesDroppedTotal.Write(&m); err != nil {
		t.Fatalf("read FramesDroppedTotal: %v", err)
	}
	return m.GetCounter().GetValue()
}

func TestFramePool_Enqueue(t *testing.T) {
	workers := 2
	queueSize := 5
	// Inject a no-op forwarder so worker goroutines can safely call Push
	// on the enqueued frames without requiring a live Unix socket.
	forwarder := dsp.NewForwarderWithClient(&noopDSPClient{})
	pool := NewFramePool(workers, queueSize, forwarder, false)

	frame := testFrame()

	// Enqueue should not block, as the queue has capacity.
	pool.Enqueue(frame)
	pool.Enqueue(frame)
	pool.Enqueue(frame)
}

func TestFramePool_Enqueue_BlocksWhenFull(t *testing.T) {
	// Zero workers: nothing drains jobQueue, so a size-1 buffer fills and stays full.
	pool := NewFramePool(0, 1, dsp.NewForwarderWithClient(&noopDSPClient{}), false)
	pool.Enqueue(testFrame())

	done := make(chan struct{})
	go func() {
		pool.Enqueue(testFrame())
		close(done)
	}()

	select {
	case <-done:
		t.Fatal("Enqueue returned while jobQueue was full; expected blocking backpressure")
	case <-time.After(100 * time.Millisecond):
		// still blocked — expected
	}

	// Free a slot so the blocked send can complete and the goroutine does not leak.
	<-pool.jobQueue
	select {
	case <-done:
	case <-time.After(100 * time.Millisecond):
		t.Fatal("Enqueue remained blocked after a jobQueue slot was freed")
	}
}

func TestFramePool_Enqueue_LoadShedDropsWhenFull(t *testing.T) {
	pool := NewFramePool(0, 1, dsp.NewForwarderWithClient(&noopDSPClient{}), true)
	pool.Enqueue(testFrame())

	before := counterValue(t)

	done := make(chan struct{})
	go func() {
		pool.Enqueue(testFrame())
		close(done)
	}()

	select {
	case <-done:
	case <-time.After(100 * time.Millisecond):
		t.Fatal("load-shed Enqueue blocked on a full jobQueue; expected an immediate drop")
	}

	after := counterValue(t)
	if after != before+1 {
		t.Fatalf("FramesDroppedTotal: got %v, want %v", after, before+1)
	}
}
