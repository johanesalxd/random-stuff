"""
Airbyte Deferrable Stress Test DAG

Proves that AirbyteTriggerSyncOperator(deferrable=True) can handle 70+
concurrent Airbyte sync tasks on a single Small Cloud Composer worker
by offloading polling to the Triggerer.

This DAG is designed to run against a mock Airbyte API endpoint (see
mock_airbyte/ directory) but works with any real Airbyte deployment.

Prerequisites:
  1. Install the Airbyte provider:
     gcloud composer environments update <ENV> \
       --location=<REGION> \
       --update-pypi-packages-from-file=requirements.txt
     (or add apache-airflow-providers-airbyte>=5.4.1 via Console)

  2. Deploy the mock Airbyte service (see mock_airbyte/deploy.sh)

  3. Create the Airflow connection:
     gcloud composer environments run <ENV> \
       --location=<REGION> \
       connections add -- airbyte_default \
       --conn-type airbyte \
       --conn-host 'https://<MOCK_URL>/v1'

  4. Set Airflow config overrides:
     gcloud composer environments update <ENV> \
       --location=<REGION> \
       --update-airflow-configs=core-parallelism=150,core-max_active_tasks_per_dag=150

  5. Upload this DAG to the environment's GCS DAG bucket:
     gsutil cp airbyte_deferrable_stress_test.py gs://<DAG_BUCKET>/dags/
"""

import datetime
from datetime import timedelta

from airflow import DAG
from airflow.providers.airbyte.operators.airbyte import AirbyteTriggerSyncOperator

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TASK_COUNT = 70                          # Number of concurrent Airbyte tasks
AIRBYTE_CONN_ID = "airbyte_default"      # Airflow connection ID for Airbyte
SYNC_TIMEOUT = 300                       # Timeout per sync in seconds (5 min)
# Note: wait_seconds only applies in NON-deferrable mode. In deferrable mode,
# the trigger's poll_interval is hardcoded to 60s in the provider.
WAIT_SECONDS = 60                        # Poll interval (non-deferrable only)

# Use a single fake connection ID for all tasks (mock doesn't validate it).
# In production, each task would have a unique Airbyte connection UUID.
MOCK_CONNECTION_ID = "00000000-0000-0000-0000-000000000000"

# ---------------------------------------------------------------------------
# DAG Definition
# ---------------------------------------------------------------------------
with DAG(
    dag_id="airbyte_deferrable_stress_test",
    schedule=None,
    start_date=datetime.datetime(2023, 1, 1),
    catchup=False,
    max_active_tasks=TASK_COUNT,
    tags=["stress-test", "airbyte", "deferrable"],
    doc_md=__doc__,
) as dag:

    for i in range(1, TASK_COUNT + 1):
        AirbyteTriggerSyncOperator(
            task_id=f"airbyte_sync_{i}",
            connection_id=MOCK_CONNECTION_ID,
            airbyte_conn_id=AIRBYTE_CONN_ID,
            deferrable=True,                   # Offload to Triggerer
            timeout=SYNC_TIMEOUT,              # Per-task timeout
            wait_seconds=WAIT_SECONDS,         # Only used in non-deferrable mode
            retries=2,                         # Airflow-native retry
            retry_delay=timedelta(seconds=30), # Retry backoff
        )
