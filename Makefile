# Define phony targets to avoid conflicts with file names
.PHONY: build run stop

# Build the Docker image
build:
	docker build -t ningning-rag-api -f deploy/Dockerfile .

# Run the Docker container, mapping port 8000
run:
	docker run -d -p 8000:8000 --name ningning-api ningning-rag-api

# Stop and remove the running container
stop:
	docker stop ningning-api
	docker rm ningning-api