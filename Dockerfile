# Build stage
FROM python:3.13-slim AS builder

# Install curl and uv (recommended install method for uv)
RUN apt-get update && apt-get install -y curl git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv
ARG DEPLOY_VERSION
# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VERSION=$DEPLOY_VERSION

WORKDIR /app

# Copy full source including .git for dynamic versioning
COPY . /app

RUN \
  if [ -n "$VERSION" ]; then \
    SETUPTOOLS_SCM_PRETEND_VERSION=$VERSION; \
  fi && \
  uv sync --frozen && \
  uv build --wheel

# Final stage - only the installed application
FROM python:3.13-slim

RUN apt-get update && apt-get install -y git

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install uv
RUN pip install uv

# Copy the wheel file from builder stage
COPY --from=builder /app/dist/*.whl /tmp/

# Install the wheel file (use the first/only wheel if multiple exist)
RUN uv pip install --system $(ls -1 /tmp/*.whl | head -1) && rm -rf /tmp/*.whl

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
USER app

# Run the application as a CLI
ENTRYPOINT ["secretzero"]
CMD []