# Use a slim Python base image
FROM python:3.11-slim

# Set environment variables to prevent Python from writing .pyc files and to buffer output
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1


#RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
# Install uv, a fast Python package installer
RUN pip install uv

# Set the working directory inside the container
WORKDIR /app

# Copy only the files required for dependency installation to leverage Docker layer caching
COPY pyproject.toml alembic.ini uv.lock .

RUN uv sync --frozen --no-install-project --no-dev
RUN uv pip install --system .
#RUN alembic upgrade head


# Run database migrations and start the application
# The 'kickoff' script is defined in pyproject.toml
CMD ["/bin/bash", "-c", "alembic upgrade head"]
#CMD ["/bin/bash", "-c", "alembic upgrade head && sleep infinity"]