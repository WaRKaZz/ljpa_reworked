# Use a slim Python base image
FROM python:3.11-slim

# Set environment variables to prevent Python from writing .pyc files and to buffer output
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PATH="/root/.local/bin:${PATH}"

# Install system dependencies including curl and git
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install official Antigravity CLI (agy)
RUN curl -fsSL https://antigravity.google/install.sh | bash || true

# Install uv package installer
RUN pip install --no-cache-dir uv

# Set the working directory inside the container
WORKDIR /app

# Copy only the files required for dependency installation to leverage Docker layer caching
COPY pyproject.toml alembic.ini uv.lock .

RUN uv sync --frozen --no-install-project --no-dev
RUN uv pip install --system .

CMD ["/bin/bash", "-c", "alembic upgrade head"]