FROM python:3.12-slim

# rclone (Drive access) + ffmpeg/ffprobe (thumbnails & duration)
RUN apt-get update \
    && apt-get install -y --no-install-recommends rclone ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# uv for fast, reproducible dependency installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Install deps first for layer caching. uv.lock is optional; if absent it is resolved.
COPY pyproject.toml ./
COPY uv.lock* ./
RUN uv sync --no-dev --no-install-project

# App source
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh && uv sync --no-dev

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
