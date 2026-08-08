# Use a slim Python base image
FROM python:3.11-slim

# Set environment variables to prevent Python from writing .pyc files and to buffer output
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PATH="/root/.local/bin:${PATH}"

# Install system dependencies including curl, git, ca-certificates, gnupg
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

# Set working directory
WORKDIR /app

# Copy dependency manifests
COPY pyproject.toml alembic.ini uv.lock .

# Install Python project dependencies and markitdown-mcp
RUN uv sync --frozen --no-install-project --no-dev
RUN uv pip install --system markitdown-mcp .

# Clone default agy plugins (obra/superpowers & ponytail)
RUN mkdir -p /root/.gemini/config/plugins /root/.gemini/antigravity-cli \
    && git clone https://github.com/obra/superpowers.git /root/.gemini/config/plugins/superpowers \
    && git clone https://github.com/DietrichGebert/ponytail.git /root/.gemini/config/plugins/ponytail

# Pre-configure MCP servers using ${CDP_URL} from .env
RUN echo '{\n\
  "mcpServers": {\n\
    "context7": {\n\
      "serverUrl": "https://mcp.context7.com/mcp"\n\
    },\n\
    "markitdown": {\n\
      "command": "markitdown-mcp"\n\
    },\n\
    "unbrowse": {\n\
      "command": "unbrowse",\n\
      "args": ["mcp"],\n\
      "env": {\n\
        "CDP_URL": "${CDP_URL}",\n\
        "UNBROWSE_MCP_SURFACE": "agent"\n\
      }\n\
    },\n\
    "playwright": {\n\
      "command": "npx",\n\
      "args": ["-y", "@playwright/mcp@latest"],\n\
      "env": {\n\
        "CDP_URL": "${CDP_URL}"\n\
      }\n\
    }\n\
  }\n\
}' > /root/.gemini/config/mcp_config.json \
  && cp /root/.gemini/config/mcp_config.json /root/.gemini/antigravity-cli/mcp_config.json

CMD ["/bin/bash", "-c", "alembic upgrade head"]