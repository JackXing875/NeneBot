# Define phony targets to avoid conflicts with file names
.PHONY: build run stop

# Build the Docker image
build:
	docker build -t persona-studio -f deploy/Dockerfile .

# Run the Docker container, mapping port 8000
run:
	docker run -d -p 8000:8000 --name persona-studio persona-studio

# Stop and remove the running container
stop:
	docker stop persona-studio
	docker rm persona-studio
