package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	FramesTotal = promauto.NewCounter(prometheus.CounterOpts{
		Name: "photonicops_ingestion_frames_total",
		Help: "Optical frames recived on StreamTelemetry",
	})
	FramesDroppedTotal = promauto.NewCounter(prometheus.CounterOpts{
		Name: "photocnics_ingestion_frames_dropped_total",
		Help: "Frames discarded by load-shedding Enqueue",
	})
)

func RegisterGuages(queueDepth, ringOccupancy func() float64) {
	prometheus.MustRegister(prometheus.NewGaugeFunc(prometheus.GaugeOpts{
		Name: "photonicops_ingestion_job_queue_depth",
		Help: "Current worker jobQueue occupancy",
	}, queueDepth))
	prometheus.MustRegister(prometheus.NewGaugeFunc(prometheus.GaugeOpts{
		Name: "photonicops_ingestion_ring_occupancy",
		Help: "Occupied ring-buffer slots (all sensors)",
	}, ringOccupancy))
}
