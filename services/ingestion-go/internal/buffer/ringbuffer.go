package buffer

import (
	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/pb"
	"sync"
)

// RingBuffer implements a fixed-size circular buffer for storing OpticalFrame
// data with zero-allocation semantics, fixed size, thread-safe.
type RingBuffer struct {
	data  []*pb.OpticalFrame
	head  int
	tail  int
	count int
	size  int
	mu    sync.Mutex
}

// NewRingBuffer allocates the array exactly once at startup, then only recycles pointers, achieving zero-allocation throughput.
func NewRingBuffer(size int) *RingBuffer {
	return &RingBuffer{
		data: make([]*pb.OpticalFrame, size),
		size: size,
	}
}

// Push adds an item. If full, it overwrites the oldest item (zero-allocation).
func (r *RingBuffer) Push(frame *pb.OpticalFrame) {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.data[r.head] = frame
	r.head = (r.head + 1) % r.size

	if r.count < r.size {
		r.count++
	} else {
		// Buffer is full, tail moves forward as oldest data is overwritten
		r.tail = (r.tail + 1) % r.size
	}
}
