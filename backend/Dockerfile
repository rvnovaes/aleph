FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends yaz && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
ARG UV_SYNC_FLAGS=""
RUN uv sync --frozen ${UV_SYNC_FLAGS}
COPY . .
RUN useradd -u 1000 -m aleph
USER aleph
ENV PATH="/app/.venv/bin:$PATH"
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "90"]
