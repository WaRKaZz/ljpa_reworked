# Application image for linkedin-bot. Runtime volumes provide database and state.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_CACHE_DIR="/tmp/.uv-cache" PATH="/root/.local/bin:${PATH}"
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev
COPY src/ ./src/
RUN uv sync --frozen --no-dev && mkdir -p /app/data /app/resources /tmp/.uv-cache && chmod -R 777 /app /tmp
CMD ["uv", "run", "--no-dev", "python", "-m", "ljpa_reworked.main"]
