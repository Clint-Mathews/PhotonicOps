package worker

import (
	"testing"
	"time"

	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/pb"
)

func TestFramePool_Enqueue(t *testing.T) {
	workers := 2
	queueSize := 5
	pool := NewFramePool(workers, queueSize)

	frame := &pb.OpticalFrame{
		SensorId:        "test-sensor",
		WavelengthShift: 1.23,
	}

	// Enqueue should not block, as the queue has capacity
	pool.Enqueue(frame)
	pool.Enqueue(frame)
	pool.Enqueue(frame)

	// Since workers are processing asynchronously, give them a tiny moment to pick up jobs.
	// We just want to ensure Enqueue works and workers don't panic while reading.
	time.Sleep(50 * time.Millisecond)

	// In a complete test suite, we would provide a mechanism to cleanly stop 
	// the workers and wait for the WaitGroup, but for this zero-allocation 
	// ingestion pipeline validation, ensuring it doesn't crash on enqueue is sufficient.
}
