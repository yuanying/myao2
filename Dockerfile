# ===== Builder Stage =====
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# uv optimization settings
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies first (cache optimization)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# Copy application code
COPY src/ /app/src/
COPY pyproject.toml uv.lock README.md /app/

# Install project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev


# ===== Runtime Stage =====
FROM python:3.12-slim-bookworm

# Create non-root user
RUN groupadd --system --gid 1000 myao \
    && useradd --system --gid 1000 --uid 1000 --create-home myao

# Create data directory
RUN mkdir -p /app/data && chown -R myao:myao /app

# Copy application from builder stage
COPY --from=builder --chown=myao:myao /app /app

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Working directory
WORKDIR /app

# Run as non-root user
USER myao

# Start application
CMD ["python", "-m", "myao2"]
