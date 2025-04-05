# Stage 1: Build environment with build dependencies
FROM python:3.11-slim as builder

WORKDIR /app

# Install build tools and dependencies needed for Playwright install
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    # Dependencies needed by Playwright browsers - check Playwright docs for current list
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libatspi2.0-0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libxkbcommon0 libpango-1.0-0 libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Install poetry or PDM if you use them, otherwise just pip
# RUN pip install poetry
# COPY poetry.lock pyproject.toml ./
# RUN poetry install --no-dev --no-root

# Using pip with pyproject.toml
COPY pyproject.toml setup.py ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
# Install project dependencies (excluding 'dev' extras)
RUN pip install --no-cache-dir ".[all]" # Install base dependencies, adjust if using optional deps for prod

# Install Playwright browsers - this happens in the builder stage
# so the final image doesn't need the full Playwright install script overhead
RUN python -m playwright install --with-deps chromium # Only install needed browsers

# Stage 2: Final production image
FROM python:3.11-slim as final

WORKDIR /app

# Create a non-root user for security
RUN groupadd --gid 1001 raiden && \
    useradd --uid 1001 --gid 1001 --shell /bin/bash --create-home raiden
RUN chown -R raiden:raiden /app

# Copy installed dependencies and playwright browsers from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /root/.cache/ms-playwright /home/raiden/.cache/ms-playwright # Copy browser binaries
RUN chown -R raiden:raiden /home/raiden/.cache/ms-playwright

# Copy application code
COPY --chown=raiden:raiden raiden/ ./raiden

# Create directories for recordings if needed, owned by the app user
RUN mkdir -p /app/recordings/videos /app/recordings/traces && \
    chown -R raiden:raiden /app/recordings

USER raiden

# Expose the API port
EXPOSE 8000

# Set environment variables needed by Playwright within the container
ENV PLAYWRIGHT_BROWSERS_PATH=/home/raiden/.cache/ms-playwright

# Default command to run the API
# Using Gunicorn for production WSGI server
CMD ["uvicorn", "raiden.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
# Consider using Gunicorn workers in production:
# CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "raiden.api.main:app", "--bind", "0.0.0.0:8000"]