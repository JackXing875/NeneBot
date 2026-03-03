# ==========================================
# Stage 1: Builder (Install dependencies)
# ==========================================
FROM python:3.10-slim as builder

# Set environment variables to optimize Python execution
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install build dependencies (e.g., for compiling C extensions if needed)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only the dependency file first to leverage Docker cache
COPY requirements.txt .

# Install dependencies into a virtual environment to isolate them
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ==========================================
# Stage 2: Runtime (Production image)
# ==========================================
FROM python:3.10-slim as runtime

# Create a non-root user for security purposes
RUN useradd -m -s /bin/bash appuser

WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Ensure the virtual environment is used
ENV PATH="/opt/venv/bin:$PATH"

# Copy the actual application code
COPY src/ ./src/

# Change ownership of the application files to the non-root user
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Expose the port the FastAPI application will run on
EXPOSE 8000

# Command to run the application using a production ASGI server
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]