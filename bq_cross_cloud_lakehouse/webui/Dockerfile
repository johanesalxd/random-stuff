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

CMD ["python", "app.py"]
