# XQNEXT Framework Dockerfile
# Multi-stage build for optimal image size and faster builds

# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /build/webui

# Copy package files
COPY webui/package*.json ./

# Install dependencies
RUN npm ci --prefer-offline --no-audit

# Copy frontend source
COPY webui/ ./

# Build frontend for production
RUN npm run build

# Stage 2: Python dependencies
FROM python:3.11-slim AS python-builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - \
    && ln -s /root/.local/bin/poetry /usr/local/bin/poetry

# Copy poetry configuration
COPY pyproject.toml poetry.lock ./

# Configure Poetry and install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi --no-root

# Stage 3: Final runtime image
FROM python:3.11-slim

LABEL maintainer="XQNEXT Team"
LABEL description="XQNEXT OneBot Framework - AI-powered QQ bot framework"
LABEL version="0.0.2"

WORKDIR /app

# Install runtime dependencies (including fonts for image generation)
RUN apt-get update && apt-get install -y \
    curl \
    fonts-noto-cjk \
    fonts-liberation \
    libjpeg62-turbo \
    libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=python-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/
COPY config.toml ./config.toml

# Copy built frontend from frontend-builder
COPY --from=frontend-builder /build/webui/dist ./webui/dist

# Create necessary directories with proper permissions
RUN mkdir -p data logs plugins && \
    chmod 755 data logs plugins

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV TZ=Asia/Shanghai

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose ports
EXPOSE 8000 8080

# Run the application
CMD ["python", "-m", "src.main"]

