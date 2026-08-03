package worker

import (
	"context"
	"testing"
	"time"

	"google.golang.org/grpc"

	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/internal/dsp"
	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/pb"
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

func TestFramePool_Enqueue(t *testing.T) {
	workers := 2
	queueSize := 5
	// Inject a no-op forwarder so worker goroutines can safely call Push
	// on the enqueued frames without requiring a live Unix socket.
	forwarder := dsp.NewForwarderWithClient(&noopDSPClient{})
	pool := NewFramePool(workers, queueSize, forwarder)

	frame := &pb.OpticalFrame{
		SensorId:        "test-sensor",
		WavelengthShift: 1.23,
	}

	// Enqueue should not block, as the queue has capacity.
	pool.Enqueue(frame)
	pool.Enqueue(frame)
	pool.Enqueue(frame)

	// Give the workers time to drain the queue. We verify the pool doesn't
	// crash or deadlock under normal enqueue load.
	time.Sleep(50 * time.Millisecond)
}
