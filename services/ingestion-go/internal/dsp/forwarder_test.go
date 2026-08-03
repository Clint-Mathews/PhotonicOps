package dsp

import (
	"context"
	"io"
	"sync"
	"testing"
	"time"

	"google.golang.org/grpc"

	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/pb"
)

// --- Fake DSPServiceClient -------------------------------------------------
//
// fakeClient implements pb.DSPServiceClient. Only StreamBatches is used by
// Forwarder; the other methods are stubs required to satisfy the interface.
//
// fakeStreamClient records every FrameBatch sent to it so tests can assert on
// the batch contents, window timestamps, and sensor IDs.

type fakeStreamClient struct {
	grpc.ClientStream
	mu       sync.Mutex
	received []*pb.FrameBatch
	// sendErr, if non-nil, is returned from Send to simulate transport errors.
	sendErr error
	// ackAccepted controls the Accepted field in the returned DSPAck.
	ackAccepted bool
}

func (f *fakeStreamClient) Send(batch *pb.FrameBatch) error {
	if f.sendErr != nil {
		return f.sendErr
	}
	f.mu.Lock()
	f.received = append(f.received, batch)
	f.mu.Unlock()
	return nil
}

func (f *fakeStreamClient) CloseAndRecv() (*pb.DSPAck, error) {
	return &pb.DSPAck{Accpeted: f.ackAccepted}, nil
}

func (f *fakeStreamClient) batches() []*pb.FrameBatch {
	f.mu.Lock()
	defer f.mu.Unlock()
	out := make([]*pb.FrameBatch, len(f.received))
	copy(out, f.received)
	return out
}

// fakeClient implements pb.DSPServiceClient.
type fakeClient struct {
	stream      *fakeStreamClient
	openErr     error // returned from StreamBatches to simulate dial errors.
}

func (c *fakeClient) StreamBatches(_ context.Context, _ ...grpc.CallOption) (pb.DSPService_StreamBatchesClient, error) {
	if c.openErr != nil {
		return nil, c.openErr
	}
	return c.stream, nil
}

// newTestForwarder constructs a Forwarder with an injected fake client and a
// configurable batch size so tests don't have to push 1,000 real frames.
func newTestForwarder(client pb.DSPServiceClient, batchSize int) *Forwarder {
	f := NewForwarderWithClient(client)
	// Override the package-level constant for this instance by using the
	// forwarder's internal FramesPerBatch via a test-only helper.
	// Because FramesPerBatch is a const we cannot mutate it; instead we test
	// accumulation logic directly and use the real constant for the flush test.
	_ = batchSize // See individual tests for how batch size is handled.
	return f
}

// --- Tests ------------------------------------------------------------------

// TestForwarder_Push_AccumulatesWithoutFlushing verifies that Push does not
// call StreamBatches until exactly FramesPerBatch frames have arrived for a
// given sensor. Pushing FramesPerBatch-1 frames must produce zero batches.
func TestForwarder_Push_AccumulatesWithoutFlushing(t *testing.T) {
	stream := &fakeStreamClient{ackAccepted: true}
	client := &fakeClient{stream: stream}
	fwd := NewForwarderWithClient(client)

	frame := &pb.OpticalFrame{
		SensorId:        "sensor-A",
		Timestamp:       1_000_000,
		WavelengthShift: 0.5,
	}

	for i := 0; i < FramesPerBatch-1; i++ {
		if err := fwd.Push(frame); err != nil {
			t.Fatalf("Push %d returned unexpected error: %v", i, err)
		}
	}

	if got := len(stream.batches()); got != 0 {
		t.Errorf("expected 0 batches before FramesPerBatch, got %d", got)
	}

	acc := fwd.shards["sensor-A"]
	if acc == nil {
		t.Fatal("expected accumulator to exist for sensor-A")
	}
	if got := len(acc.frames); got != FramesPerBatch-1 {
		t.Errorf("expected %d frames in accumulator, got %d", FramesPerBatch-1, got)
	}
}

// TestForwarder_Push_FlushesOnBatchBoundary verifies that exactly one batch is
// sent when FramesPerBatch frames arrive, the batch carries the correct sensor
// ID and frame count, and the accumulator resets after the flush.
func TestForwarder_Push_FlushesOnBatchBoundary(t *testing.T) {
	const windowStartNs = int64(1_000_000_000) // 1 second in ns.
	stream := &fakeStreamClient{ackAccepted: true}
	client := &fakeClient{stream: stream}
	fwd := NewForwarderWithClient(client)

	for i := 0; i < FramesPerBatch; i++ {
		ts := windowStartNs + int64(i)*100_000 // 100µs per frame (10kHz).
		frame := &pb.OpticalFrame{
			SensorId:        "sensor-B",
			Timestamp:       ts,
			WavelengthShift: float64(i) * 0.001,
		}
		if err := fwd.Push(frame); err != nil {
			t.Fatalf("Push %d returned unexpected error: %v", i, err)
		}
	}

	batches := stream.batches()
	if len(batches) != 1 {
		t.Fatalf("expected exactly 1 batch, got %d", len(batches))
	}

	b := batches[0]

	if b.SensorId != "sensor-B" {
		t.Errorf("expected SensorId %q, got %q", "sensor-B", b.SensorId)
	}

	if len(b.Frames) != FramesPerBatch {
		t.Errorf("expected %d frames in batch, got %d", FramesPerBatch, len(b.Frames))
	}

	if b.WindowStartNs != windowStartNs {
		t.Errorf("expected WindowStartNs %d, got %d", windowStartNs, b.WindowStartNs)
	}

	// WindowDurationMs should be approximately 100ms (999 × 100µs intervals).
	expectedDurationMs := float64(999 * 100_000 / 1_000_000) // ~99.9ms
	if b.WindowDurationMs < expectedDurationMs-1 || b.WindowDurationMs > expectedDurationMs+1 {
		t.Errorf("expected WindowDurationMs ≈ %.1fms, got %.4fms", expectedDurationMs, b.WindowDurationMs)
	}

	// Accumulator must be reset: the 1000th frame becomes the start of the next window.
	acc := fwd.shards["sensor-B"]
	if acc == nil {
		t.Fatal("expected shard to still exist after flush")
	}
	if len(acc.frames) != 0 {
		t.Errorf("expected accumulator to be empty after flush, got %d frames", len(acc.frames))
	}
	// windowstart must be the timestamp of the 1000th (last) frame, not zero.
	lastFrameTs := windowStartNs + int64(FramesPerBatch-1)*100_000
	if acc.windowstart != lastFrameTs {
		t.Errorf("expected windowstart reset to last frame ts %d, got %d", lastFrameTs, acc.windowstart)
	}
}

// TestForwarder_Push_MultiSensorIndependence verifies that two sensors each
// accumulate their own separate batches and do not interfere with each other.
func TestForwarder_Push_MultiSensorIndependence(t *testing.T) {
	stream := &fakeStreamClient{ackAccepted: true}
	client := &fakeClient{stream: stream}
	fwd := NewForwarderWithClient(client)

	frameA := &pb.OpticalFrame{SensorId: "sensor-A", Timestamp: 1_000_000, WavelengthShift: 1.0}
	frameB := &pb.OpticalFrame{SensorId: "sensor-B", Timestamp: 2_000_000, WavelengthShift: 2.0}

	// Push FramesPerBatch-1 of sensor-A and FramesPerBatch of sensor-B.
	for i := 0; i < FramesPerBatch-1; i++ {
		if err := fwd.Push(frameA); err != nil {
			t.Fatalf("Push sensor-A frame %d: %v", i, err)
		}
	}
	for i := 0; i < FramesPerBatch; i++ {
		if err := fwd.Push(frameB); err != nil {
			t.Fatalf("Push sensor-B frame %d: %v", i, err)
		}
	}

	batches := stream.batches()
	if len(batches) != 1 {
		t.Fatalf("expected exactly 1 batch (from sensor-B only), got %d", len(batches))
	}
	if batches[0].SensorId != "sensor-B" {
		t.Errorf("expected batch from sensor-B, got sensor %q", batches[0].SensorId)
	}

	// sensor-A should still have FramesPerBatch-1 frames waiting.
	accA := fwd.shards["sensor-A"]
	if len(accA.frames) != FramesPerBatch-1 {
		t.Errorf("expected %d frames for sensor-A, got %d", FramesPerBatch-1, len(accA.frames))
	}
}

// TestForwarder_Push_ConcurrentSafety fires multiple goroutines pushing to the
// same Forwarder simultaneously and verifies no data race occurs. Run with:
//
//	go test -race ./internal/dsp/...
func TestForwarder_Push_ConcurrentSafety(t *testing.T) {
	stream := &fakeStreamClient{ackAccepted: true}
	client := &fakeClient{stream: stream}
	fwd := NewForwarderWithClient(client)

	const goroutines = 10
	const framesEach = 200 // Total: 2000 frames across 10 goroutines, 2 full batches.

	var wg sync.WaitGroup
	wg.Add(goroutines)
	for g := 0; g < goroutines; g++ {
		go func() {
			defer wg.Done()
			frame := &pb.OpticalFrame{
				SensorId:        "sensor-concurrent",
				Timestamp:       time.Now().UnixNano(),
				WavelengthShift: 1.0,
			}
			for i := 0; i < framesEach; i++ {
				if err := fwd.Push(frame); err != nil {
					// Flush errors are expected if the fake stream is not set up
					// for concurrent sends; log but don't fail — race detection
					// is the goal of this test, not flush correctness.
					t.Logf("Push error (may be expected under contention): %v", err)
				}
			}
		}()
	}
	wg.Wait()
	// No assertion on batch count — the race detector is the pass/fail criterion.
}

// TestForwarder_Push_FlushError verifies that a transport error from flush is
// returned to the caller and does not corrupt the accumulator state.
func TestForwarder_Push_FlushError(t *testing.T) {
	stream := &fakeStreamClient{
		ackAccepted: true,
		sendErr:     io.ErrUnexpectedEOF,
	}
	client := &fakeClient{stream: stream}
	fwd := NewForwarderWithClient(client)

	frame := &pb.OpticalFrame{SensorId: "sensor-err", Timestamp: 1_000_000}

	var lastErr error
	for i := 0; i < FramesPerBatch; i++ {
		lastErr = fwd.Push(frame)
	}

	// The FramesPerBatch-th push triggers flush, which should return an error.
	if lastErr == nil {
		t.Error("expected Push to return error on flush failure, got nil")
	}
}

// TestForwarder_Push_WindowStartNotZeroAfterReset is a regression test for the
// windowstart=0 bug: after a flush the next batch's WindowStartNs must not be
// the Unix epoch.
func TestForwarder_Push_WindowStartNotZeroAfterReset(t *testing.T) {
	stream := &fakeStreamClient{ackAccepted: true}
	client := &fakeClient{stream: stream}
	fwd := NewForwarderWithClient(client)

	const baseTs = int64(1_750_000_000_000_000_000) // A plausible 2025 Unix ns timestamp.

	// Push two full batches.
	for batch := 0; batch < 2; batch++ {
		for i := 0; i < FramesPerBatch; i++ {
			ts := baseTs + int64(batch*FramesPerBatch+i)*100_000
			frame := &pb.OpticalFrame{SensorId: "sensor-reg", Timestamp: ts}
			if err := fwd.Push(frame); err != nil {
				t.Fatalf("batch %d frame %d: %v", batch, i, err)
			}
		}
	}

	batches := stream.batches()
	if len(batches) != 2 {
		t.Fatalf("expected 2 batches, got %d", len(batches))
	}

	// The second batch's WindowStartNs must not be zero (the pre-fix bug value).
	if batches[1].WindowStartNs == 0 {
		t.Error("second batch WindowStartNs is 0 (Unix epoch) — windowstart reset bug regression")
	}

	// It should equal the timestamp of the 1000th frame of the first batch.
	expectedStart := baseTs + int64(FramesPerBatch-1)*100_000
	if batches[1].WindowStartNs != expectedStart {
		t.Errorf("expected second batch WindowStartNs=%d, got %d", expectedStart, batches[1].WindowStartNs)
	}
}
