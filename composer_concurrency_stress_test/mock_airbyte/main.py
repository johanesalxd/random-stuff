"""
Mock Airbyte API Server for Deferrable Operator Stress Testing

Simulates the Airbyte REST API endpoints used by the apache-airflow-providers-airbyte
SDK (v5.x). Deployed as a Cloud Run service, it allows testing
AirbyteTriggerSyncOperator(deferrable=True) without a real Airbyte instance.

Endpoints:
  POST /v1/jobs       -- Create a sync job (returns jobId + "running" status)
  GET  /v1/jobs/<id>  -- Get job status (transitions to "succeeded" after SYNC_DURATION)
  GET  /v1/health     -- Health check

Environment variables:
  SYNC_DURATION_SECONDS  -- Simulated sync duration (default: 30)
  PORT                   -- Server port (default: 8080, set by Cloud Run)
"""

import os
import time
import random
import threading

from flask import Flask, request, jsonify

app = Flask(__name__)

# Configuration
SYNC_DURATION = int(os.environ.get("SYNC_DURATION_SECONDS", "30"))

# In-memory job store (thread-safe via GIL for simple dict ops)
# Format: {job_id: {"created_at": float, "connection_id": str}}
jobs = {}
_lock = threading.Lock()


@app.route("/v1/jobs", methods=["POST"])
def create_job():
    """Simulate POST /v1/jobs -- trigger a sync job."""
    data = request.get_json(silent=True) or {}
    connection_id = data.get("connectionId", "unknown")
    job_type = data.get("jobType", "sync")

    job_id = random.randint(10000, 99999)
    with _lock:
        jobs[job_id] = {
            "created_at": time.time(),
            "connection_id": connection_id,
        }

    app.logger.info(f"Created job {job_id} for connection {connection_id}")

    return jsonify({
        "jobId": job_id,
        "status": "running",
        "jobType": job_type,
        "connectionId": connection_id,
        "startTime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }), 200


@app.route("/v1/jobs/<int:job_id>", methods=["GET"])
def get_job(job_id):
    """Simulate GET /v1/jobs/{jobId} -- get job status and details."""
    with _lock:
        job = jobs.get(job_id)

    if not job:
        # Unknown job -- return succeeded to avoid blocking the test.
        # In production Airbyte, this would be a 404, but the SDK may not
        # handle 404 gracefully in all versions.
        return jsonify({
            "jobId": job_id,
            "status": "succeeded",
            "jobType": "sync",
            "bytesSynced": 1024,
            "rowsSynced": 10,
        }), 200

    elapsed = time.time() - job["created_at"]
    if elapsed >= SYNC_DURATION:
        status = "succeeded"
        bytes_synced = random.randint(1024, 1048576)  # 1KB - 1MB
        rows_synced = random.randint(10, 10000)
    else:
        status = "running"
        bytes_synced = 0
        rows_synced = 0

    return jsonify({
        "jobId": job_id,
        "status": status,
        "jobType": "sync",
        "connectionId": job["connection_id"],
        "startTime": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(job["created_at"])
        ),
        "bytesSynced": bytes_synced,
        "rowsSynced": rows_synced,
    }), 200


@app.route("/v1/health", methods=["GET"])
def health_check():
    """Simulate GET /v1/health -- Airbyte health check."""
    return jsonify({"available": True}), 200


@app.route("/", methods=["GET"])
def root():
    """Root endpoint -- service info."""
    return jsonify({
        "service": "mock-airbyte",
        "description": "Mock Airbyte API for deferrable operator stress testing",
        "sync_duration_seconds": SYNC_DURATION,
        "active_jobs": len(jobs),
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False)
