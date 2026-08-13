.PHONY: init-proto proto proto-python proto-all

DSP_PYTHON := services/dsp-agent-python/.venv/bin/python

init-proto:
	go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
	go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

proto:
	mkdir -p services/ingestion-go/pb
	protoc --go_out=services/ingestion-go/pb --go_opt=paths=source_relative \
	       --go-grpc_out=services/ingestion-go/pb --go-grpc_opt=paths=source_relative \
	       --proto_path=proto proto/telemetry.proto

proto-python:
	mkdir -p services/dsp-agent-python/pb
	PATH="$$PWD/services/dsp-agent-python/.venv/bin:$$PATH" $(DSP_PYTHON) -m grpc_tools.protoc \
	    --proto_path=proto \
	    --python_out=services/dsp-agent-python/pb \
	    --grpc_python_out=services/dsp-agent-python/pb \
	    proto/telemetry.proto
	sed -i '' 's/^import telemetry_pb2/from . import telemetry_pb2/' \
	    services/dsp-agent-python/pb/telemetry_pb2_grpc.py


proto-all: proto proto-python
