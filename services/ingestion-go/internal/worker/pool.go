package worker

import (
	"log"
	"sync"

	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/internal/dsp"
	"github.com/Clint-Mathews/PhotonicOps/services/ingestion-go/pb"
)

type FramePool struct {
	jobQueue  chan *pb.OpticalFrame
	wg        sync.WaitGroup
	forwarder *dsp.Forwarder
}

// frameSyncPool is our sync.Pool. It reuses byte buffers
// so we don't trigger the Garbage Collector every time we process a frame.
var frameSyncPool = sync.Pool{
	New: func() any {
		// If the pool is empty, allocate ONE new byte slice.
		return make([]byte, 0, 1024)
	},
}

func NewFramePool(workers, queueSize int, forwarder *dsp.Forwarder) *FramePool {
	p := &FramePool{
		jobQueue:  make(chan *pb.OpticalFrame, queueSize),
		forwarder: forwarder,
	}
	// Spin up fixed workers on startup
	for i := 0; i < workers; i++ {
		p.wg.Add(1)
		go p.worker(i)
	}
	return p
}

func (p *FramePool) worker(id int) {
	defer p.wg.Done()
	for frame := range p.jobQueue {
		// 1. Borrow a pre-allocated buffer from the pool
		buf := frameSyncPool.Get().([]byte)
		// 2. Do "work" (eg: DSP [Digital Signal Processing] preparation)
		if err := p.forwarder.Push(frame); err != nil {
			log.Printf("worker %d: dsp forwarder push error: %v", id, err)
		}
		// 3. Clear the buffer (keep its capacity, set length to 0)
		buf = buf[:0]
		// 4. Return it to the pool for the next worker! (ZERO ALLOCATION)
		frameSyncPool.Put(buf)
	}
}

func (p *FramePool) Enqueue(frame *pb.OpticalFrame) {
	p.jobQueue <- frame
}
