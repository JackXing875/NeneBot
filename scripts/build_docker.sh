#!/bin/bash
# Helper script to build the Docker image locally.

IMAGE_NAME="persona-studio"
TAG="latest"

echo "Building Docker image: ${IMAGE_NAME}:${TAG}..."
docker build -t ${IMAGE_NAME}:${TAG} -f deploy/Dockerfile .

echo "Build complete. Run 'make run' to start the container."
