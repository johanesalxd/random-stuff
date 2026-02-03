# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ app/

# Run the application
CMD exec uvicorn app.bridge:app --host 0.0.0.0 --port $PORT
