FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.10.4 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PORT=8000 DATA_DIR=/app/data
RUN install -d -o appuser -g appuser /app/data /app/data/cache /app/data/cache/models
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "uvicorn investigation.web:create_app --factory --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --no-proxy-headers"]
