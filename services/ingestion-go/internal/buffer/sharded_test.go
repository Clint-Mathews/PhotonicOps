package buffer

import (
	"testing"

	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/pb"
)

func TestShardedRingBuffer_IndependentHistory(t *testing.T) {
	const size = 10000
	s := NewShardedRingBuffer(size)

	seedB := &pb.OpticalFrame{SensorId: "B", WavelengthShift: 99}
	s.Push(seedB)

	for i := 0; i < size+1; i++ {
		s.Push(&pb.OpticalFrame{SensorId: "A", WavelengthShift: float64(i)})
	}

	gotB := s.Snapshot("B")
	if len(gotB) != 1 {
		t.Fatalf("sensor B snapshot length = %d, want 1", len(gotB))
	}
	if gotB[0] != seedB {
		t.Fatalf("sensor B snapshot was mutated by sensor A overflow")
	}

	if got := s.shards["A"].Occupancy(); got != size {
		t.Errorf("sensor A occupancy = %d, want %d", got, size)
	}

	gotA := s.Snapshot("A")
	if len(gotA) != size {
		t.Fatalf("sensor A snapshot length = %d, want %d", len(gotA), size)
	}
	if gotA[0].WavelengthShift != 1 {
		t.Errorf("sensor A oldest retained shift = %v, want 1 (frame 0 overwritten)", gotA[0].WavelengthShift)
	}
	if gotA[size-1].WavelengthShift != float64(size) {
		t.Errorf("sensor A newest shift = %v, want %d", gotA[size-1].WavelengthShift, size)
	}
	if s.Occupancy() != size+1 {
		t.Errorf("total occupancy = %d, want %d (A full + B seed)", s.Occupancy(), size+1)
	}
}

func TestShardedRingBuffer_SnapshotUnknownSensor(t *testing.T) {
	s := NewShardedRingBuffer(8)
	s.Push(&pb.OpticalFrame{SensorId: "A"})
	if got := s.Snapshot("missing"); got != nil {
		t.Fatalf("unknown sensor snapshot = %v, want nil", got)
	}
}