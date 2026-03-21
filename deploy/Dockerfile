# ==========================================
# Stage 1: Frontend builder
# ==========================================
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci --silent

COPY frontend/ ./
RUN npm run build

# ==========================================
# Stage 2: Python dependency builder
# ==========================================
FROM python:3.10-slim AS python-builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ==========================================
# Stage 3: Runtime (Production image)
# ==========================================
FROM python:3.10-slim AS runtime

RUN useradd -m -s /bin/bash appuser

WORKDIR /app

COPY --from=python-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Application code
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY data/ ./data/

# Compiled frontend
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Build vector index on first run if not present, then start API server
CMD ["sh", "-c", "python scripts/init_vector_db.py || true && uvicorn src.main:app --host 0.0.0.0 --port 8000"]
