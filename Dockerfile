# Use a slim Python base image
FROM python:3.11-slim

# Set environment variables to prevent Python from writing .pyc files and to buffer output
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PATH="/root/.local/bin:${PATH}"

# Install system dependencies including curl, git, ca-certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 22.x LTS and npm
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Unbrowse CLI globally
RUN npm install -g unbrowse@latest

# Install uv package installer
RUN pip install --no-cache-dir uv

# Set the working directory inside the container
WORKDIR /app

# Copy dependency manifests
COPY pyproject.toml alembic.ini uv.lock .

# Install Python project dependencies and markitdown-mcp
RUN uv sync --frozen --no-install-project --no-dev
RUN uv pip install --system markitdown-mcp .

CMD ["/bin/bash", "-c", "alembic upgrade head"]