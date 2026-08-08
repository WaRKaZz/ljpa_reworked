# Dockerfile - Application Container for linkedin-bot
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PATH="/root/.local/bin:${PATH}"

# Install system dependencies including curl, git, ca-certificates, gnupg
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv package installer
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy dependency manifests
COPY pyproject.toml alembic.ini uv.lock ./

# Install Python project dependencies
RUN uv sync --frozen --no-install-project --no-dev

# Copy application source code
COPY src/ ./src/
COPY data/ ./data/
COPY resources/ ./resources/

# Install local package
RUN uv pip install --system .

CMD ["/bin/bash", "-c", "alembic upgrade head"]