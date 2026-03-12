# --- Builder Stage ---
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
	UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# README is required for the project install declared in pyproject.toml.
COPY README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

# --- Final Stage ---
FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY README.md ./README.md
COPY src ./src
COPY examples ./examples

EXPOSE 8000

ENV PATH="/app/.venv/bin:$PATH" \
	PYTHONPATH="/app/src" \
	PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

CMD ["phids", "--host", "0.0.0.0", "--port", "8000"]
