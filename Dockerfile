# ==============================================================================
# Stage 1: Build Frontend SPA
# ==============================================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /build

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Production Python Runtime (API & Worker)
# ==============================================================================
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (curl for healthcheck, ca-certificates)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/pyproject.toml backend/README.md ./
RUN pip install --no-cache-dir .

# Copy backend source code & migrations
COPY backend/app/ ./app/
COPY backend/migrations/ ./migrations/
COPY backend/alembic.ini ./

# Copy built frontend SPA from Stage 1
COPY --from=frontend-builder /build/dist /app/frontend/dist

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FRONTEND_DIST_DIR=/app/frontend/dist

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
