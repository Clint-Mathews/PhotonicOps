package buffer

import (
	"testing"

	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/pb"
)

func TestRingBuffer_Push(t *testing.T) {
	size := 3
	rb := NewRingBuffer(size)

	if rb.size != size {
		t.Errorf("expected size %d, got %d", size, rb.size)
	}
	if rb.count != 0 {
		t.Errorf("expected initial count 0, got %d", rb.count)
	}

	frame1 := &pb.OpticalFrame{SensorId: "1"}
	frame2 := &pb.OpticalFrame{SensorId: "2"}
	frame3 := &pb.OpticalFrame{SensorId: "3"}
	frame4 := &pb.OpticalFrame{SensorId: "4"}

	// 1. Push first frame
	rb.Push(frame1)
	if rb.count != 1 {
		t.Errorf("expected count 1, got %d", rb.count)
	}
	if rb.data[0].SensorId != "1" {
		t.Errorf("expected SensorId 1 at index 0")
	}
	if rb.head != 1 {
		t.Errorf("expected head to be 1, got %d", rb.head)
	}
	if rb.tail != 0 {
		t.Errorf("expected tail to be 0, got %d", rb.tail)
	}

	// 2. Fill the buffer
	rb.Push(frame2)
	rb.Push(frame3)
	if rb.count != 3 {
		t.Errorf("expected count 3, got %d", rb.count)
	}
	if rb.head != 0 {
		t.Errorf("expected head to wrap to 0, got %d", rb.head)
	}
	if rb.tail != 0 {
		t.Errorf("expected tail to still be 0, got %d", rb.tail)
	}

	// 3. Overflow the buffer (Push 4th frame)
	rb.Push(frame4)
	if rb.count != 3 { // Count should not exceed size
		t.Errorf("expected count 3 after overflow, got %d", rb.count)
	}
	if rb.tail != 1 { // Tail should move forward
		t.Errorf("expected tail to move to 1, got %d", rb.tail)
	}
	if rb.data[0].SensorId != "4" { // Oldest frame (1) is overwritten by newest (4)
		t.Errorf("expected SensorId 4 at index 0, got %s", rb.data[0].SensorId)
	}
}

func TestRingBuffer_Snapshot(t *testing.T) {
	rb := NewRingBuffer(3)
	if got := rb.Snapshot(); len(got) != 0 {
		t.Fatalf("empty snapshot length = %d, want 0", len(got))
	}
	if got := rb.Occupancy(); got != 0 {
		t.Fatalf("empty occupancy = %d, want 0", got)
	}

	rb.Push(&pb.OpticalFrame{SensorId: "1"})
	rb.Push(&pb.OpticalFrame{SensorId: "2"})
	rb.Push(&pb.OpticalFrame{SensorId: "3"})
	rb.Push(&pb.OpticalFrame{SensorId: "4"}) // overwrites "1"

	if got := rb.Occupancy(); got != 3 {
		t.Fatalf("occupancy = %d, want 3", got)
	}
	got := rb.Snapshot()
	if len(got) != 3 {
		t.Fatalf("snapshot length = %d, want 3", len(got))
	}
	want := []string{"2", "3", "4"}
	for i, id := range want {
		if got[i].SensorId != id {
			t.Errorf("snapshot[%d].SensorId = %s, want %s", i, got[i].SensorId, id)
		}
	}
}
