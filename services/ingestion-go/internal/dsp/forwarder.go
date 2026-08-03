// Accumulates OpticalFrames from the worker pool into 100ms FrameBatches
// and forwards them to the Python DSP process over a Unix domain socket.

package dsp

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/pb"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

const (
	// SocketPath is the Unix domain socket path shared between Go and Python.
	SocketPath = "/tmp/photonicops-dsp.sock"
	// FramesPerBatch is the number of frames that constitute one 100ms window
	FramesPerBatch = 1000
)

// Forwarder accumulates framers per sensor and flushes complete batches to the
// Python DSP process over the Unix domain socket gRPC service.
type Forwarder struct {
	mu     sync.Mutex
	shards map[string]*sensorAccumulator
	client pb.DSPServiceClient
}

type sensorAccumulator struct {
	frames      []*pb.OpticalFrame
	windowstart int64 // Unix ns of first frame in the current window
}

// NewForwarder dials the Unix socket and returns a ready Forwarder.
// The DPS python process must already be listening before this is called;
// cmd/server/maing.go should retry with backoff a connection failure.
func NewForwarder() (*Forwarder, error) {
	conn, err := grpc.NewClient(
		"unix://"+SocketPath,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		return nil, fmt.Errorf("dps: dial unix socket %q: %w", SocketPath, err)
	}
	return NewForwarderWithClient(pb.NewDSPServiceClient(conn)), nil
}

// NewForwarderWithClient constructs a Forwarder with a pre-built DSPServiceClient.
// Intended for testing: callers can inject a fake client without requiring a
// live Unix socket or Python process.
func NewForwarderWithClient(client pb.DSPServiceClient) *Forwarder {
	return &Forwarder{
		shards: make(map[string]*sensorAccumulator),
		client: client,
	}
}


// Push adds a frame to its sensor's accumulator. When the accumulator reaches
// FramesPerBatch, it flushes synchronously on the calling goroutines.
// This is safe to call from multiple worker goroutines concurrently.
func (f *Forwarder) Push(frame *pb.OpticalFrame) error {
	f.mu.Lock()

	acc, ok := f.shards[frame.SensorId]
	if !ok {
		acc = &sensorAccumulator{
			frames:      make([]*pb.OpticalFrame, 0, FramesPerBatch),
			windowstart: frame.Timestamp,
		}
		f.shards[frame.SensorId] = acc
	}

	acc.frames = append(acc.frames, frame)

	if len(acc.frames) < FramesPerBatch {
		f.mu.Unlock()
		return nil
	}

	// Batch is full - flush it. Move ownership out of the map entry
	batch := &pb.FrameBatch{
		Frames:           acc.frames,
		SensorId:         frame.SensorId,
		WindowStartNs:    acc.windowstart,
		WindowDurationMs: float64(time.Duration(frame.Timestamp - acc.windowstart).Milliseconds()),
	}

	// Reset accumulator for the next window.
	acc.frames = make([]*pb.OpticalFrame, 0, FramesPerBatch)
	acc.windowstart = frame.Timestamp
	f.mu.Unlock()

	return f.flush(batch)
}

func (f *Forwarder) flush(batch *pb.FrameBatch) error {
	ack, err := f.client.StreamBatches(context.Background())
	if err != nil {
		return fmt.Errorf("dsp: open StreamBatches: %w", err)
	}
	if err := ack.Send(batch); err != nil {
		return fmt.Errorf("dsp: send batch sensor=%s: %w", batch.SensorId, err)
	}
	reply, err := ack.CloseAndRecv()
	if err != nil {
		return fmt.Errorf("dsp: recv DSPAck: %w", err)
	}
	if !reply.Accpeted {
		log.Printf("dsp: batch rejected by Python: %s", reply.RejectionReason)
	}
	return nil
}
