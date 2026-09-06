package buffer

import (
	"sync"

	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/pb"
)

type ShardedRingBuffer struct {
	size   int
	mu     sync.Mutex
	shards map[string]*RingBuffer
}

func NewShardedRingBuffer(perSensorSize int) *ShardedRingBuffer {
	return &ShardedRingBuffer{
		size:   perSensorSize,
		shards: make(map[string]*RingBuffer),
	}
}

func (s *ShardedRingBuffer) Push(frame *pb.OpticalFrame) {
	s.mu.Lock()
	rb, ok := s.shards[frame.SensorId]
	if !ok {
		rb = NewRingBuffer(s.size)
		s.shards[frame.SensorId] = rb
	}
	s.mu.Unlock()
	rb.Push(frame)
}

func (s *ShardedRingBuffer) Occupancy() int {
	s.mu.Lock()
	defer s.mu.Unlock()

	n := 0
	for _, rb := range s.shards {
		n += rb.Occupancy()
	}
	return n
}

func (s *ShardedRingBuffer) Snapshot(sensorId string) []*pb.OpticalFrame {
	s.mu.Lock()
	rb := s.shards[sensorId]
	s.mu.Unlock()
	if rb == nil {
		return nil
	}
	return rb.Snapshot()
}
