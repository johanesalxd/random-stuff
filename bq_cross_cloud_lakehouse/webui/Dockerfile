FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency handling
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy lockfiles and pyproject
COPY pyproject.toml uv.lock* ./

# Install python dependencies
RUN uv pip install --system -r pyproject.toml

# Copy application source
COPY . .

# Set environment
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

# Serve through gunicorn, not the Werkzeug development server. Sessions are held
# in process memory, so the worker count is pinned to 1; scale with Cloud Run
# --max-instances=1 until session state moves to a shared store.
CMD exec gunicorn --bind "0.0.0.0:${PORT}" --workers 1 --threads 8 \
    --timeout 300 --access-logfile - --error-logfile - app:app
