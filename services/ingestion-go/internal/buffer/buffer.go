package buffer

import "github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/pb"

type FrameSink interface {
	Push(frame *pb.OpticalFrame)
	Occupancy() int
}
