package grpc

import (
	"io"
	"log"

	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/internal/buffer"
	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/internal/worker"
	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/pb"
)

type Server struct {
	pb.UnimplementedTelemetryServiceServer
	Ring   *buffer.RingBuffer
	Worker *worker.FramePool
}

func (s *Server) StreamTelemetry(stream pb.TelemetryService_StreamTelemetryServer) error {
	log.Println("New sensor connected and streaming...")
	for {
		frame, err := stream.Recv()
		if err == io.EOF {
			return stream.SendAndClose(&pb.StreamResponse{Success: true})
		}
		if err != nil {
			log.Printf("Stream error: %v", err)
			return err
		}
		// Push to RingBuffer (for the UI) and Worker Pool (for DSP)
		s.Ring.Push(frame)
		s.Worker.Enqueue(frame)
	}
}
