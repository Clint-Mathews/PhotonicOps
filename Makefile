.PHONY: init-proto proto

# Install the required Go plugins for protobuf
init-proto:
	go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
	go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

# Generate the Go code from the proto file
proto:
	mkdir -p services/ingestion-go/pb
	protoc --go_out=services/ingestion-go/pb --go_opt=paths=source_relative \
	       --go-grpc_out=services/ingestion-go/pb --go-grpc_opt=paths=source_relative \
	       --proto_path=proto proto/telemetry.proto
