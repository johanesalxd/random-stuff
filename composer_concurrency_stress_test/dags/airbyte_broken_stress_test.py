"""
Airbyte BROKEN Stress Test DAG -- Anti-Pattern Demonstration

Demonstrates the critical anti-pattern: calling time.sleep() inside
execute_complete() (the deferrable callback). This blocks a worker slot
during what should be a ~1-second callback, defeating the entire purpose
of the deferrable pattern.

The deferrable lifecycle has 3 phases:
  Phase 1 (INIT):     Worker slot held ~2-5s -- submits job, defers. CORRECT.
  Phase 2 (DEFER):    No worker slot -- triggerer polls async. CORRECT.
  Phase 3 (CALLBACK): Worker slot held ~1s -- checks result. CORRECT.
                       BUT: this operator adds time.sleep(30) here. BROKEN.

With 70 tasks and ~6 worker slots, the callback phase becomes:
  BROKEN:  70 tasks / 6 slots * 30s = ~350s (~6 min) of wasted worker time
  CORRECT: 70 tasks / 6 slots * ~1s = ~12s

Run this DAG alongside airbyte_deferrable_stress_test.py (the fixed version)
to see the difference. See ARCHITECTURE.md for the full comparison.

Prerequisites: same as airbyte_deferrable_stress_test.py (mock Airbyte
server deployed, apache-airflow-providers-airbyte installed, airbyte_default
connection configured).
"""

import datetime
import time
from datetime import timedelta

from airflow import DAG
from airflow.models import BaseOperator
from airflow.providers.airbyte.hooks.airbyte import AirbyteHook
from airflow.providers.airbyte.triggers.airbyte import AirbyteSyncTrigger

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TASK_COUNT = 70
AIRBYTE_CONN_ID = "airbyte_default"
SYNC_TIMEOUT = 300
MOCK_CONNECTION_ID = "00000000-0000-0000-0000-000000000000"

# The critical bug: how long the callback blocks the worker slot.
# In the real customer code this was 180 seconds (3 minutes).
# We use 30 seconds for a faster demo that still clearly shows the impact.
CALLBACK_SLEEP_SECONDS = 30


# ---------------------------------------------------------------------------
# Broken Operator -- DO NOT USE IN PRODUCTION
# ---------------------------------------------------------------------------
class BrokenDeferrableAirbyteSyncOperator(BaseOperator):
    """Demonstrates the anti-pattern: time.sleep() in execute_complete.

    This operator correctly defers to the triggerer in Phase 1-2.
    The bug is in Phase 3 (callback): it calls time.sleep() which
    blocks a worker slot, re-introducing the concurrency bottleneck
    that deferrable operators are designed to solve.

    In real-world code, this pattern appears when developers add
    retry backoff (time.sleep(180) before re-triggering) or
    post-processing (byte validation, API calls) inside the callback
    without realizing it holds a worker slot the entire time.

    The correct approach: use AirbyteTriggerSyncOperator(deferrable=True)
    with Airflow's native retries/retry_delay. See
    airbyte_deferrable_stress_test.py for the correct implementation.
    """

    template_fields = ("connection_id",)

    def __init__(
        self,
        connection_id: str,
        airbyte_conn_id: str = AIRBYTE_CONN_ID,
        callback_sleep: int = CALLBACK_SLEEP_SECONDS,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.connection_id = connection_id
        self.airbyte_conn_id = airbyte_conn_id
        self.callback_sleep = callback_sleep

    def execute(self, context):
        """Phase 1: Submit sync and defer to triggerer. This part is correct."""
        hook = AirbyteHook(airbyte_conn_id=self.airbyte_conn_id)
        result = hook.submit_sync_connection(connection_id=self.connection_id)
        self.job_id = result.job_id

        self.log.info("Job %s submitted. Deferring to triggerer...", self.job_id)

        # Correctly defers -- worker slot is released here
        self.defer(
            trigger=AirbyteSyncTrigger(
                job_id=self.job_id,
                conn_id=self.airbyte_conn_id,
                poll_interval=60,
                end_time=time.monotonic() + SYNC_TIMEOUT,
            ),
            method_name="execute_complete",
        )

    def execute_complete(self, context, event=None):
        """Phase 3: Callback. THIS IS WHERE THE BUG IS.

        The time.sleep() below blocks the worker slot for CALLBACK_SLEEP
        seconds. With 70 tasks competing for ~6 worker slots, this creates
        a serialized bottleneck in the callback phase:

            70 tasks / 6 slots * 30s sleep = ~350s (~6 minutes)

        Without the sleep, callbacks take ~1s each:

            70 tasks / 6 slots * 1s = ~12s

        In the real customer code, this was time.sleep(180) for retry
        backoff, making the callback phase take ~35 minutes.
        """
        if not event or event.get("status") == "error":
            raise RuntimeError(
                f"Job failed: {event.get('message', 'unknown') if event else 'no event'}"
            )

        # ===================================================================
        # BUG: time.sleep() in the callback blocks the worker slot!
        #
        # This simulates the real-world anti-pattern where developers add:
        #   - Retry backoff:   time.sleep(180) before re-triggering
        #   - Byte validation: time.sleep() while polling job details
        #   - Rate limiting:   time.sleep() between API calls
        #
        # The worker slot is HELD during this entire sleep. No other task
        # can use this slot for its init or callback.
        # ===================================================================
        self.log.warning(
            "ANTI-PATTERN: Sleeping %ds in callback -- worker slot blocked!",
            self.callback_sleep,
        )
        time.sleep(self.callback_sleep)

        self.log.info("Job %s completed.", event.get("job_id", "unknown"))


# ---------------------------------------------------------------------------
# DAG Definition
# ---------------------------------------------------------------------------
with DAG(
    dag_id="airbyte_broken_stress_test",
    schedule=None,
    start_date=datetime.datetime(2023, 1, 1),
    catchup=False,
    max_active_tasks=TASK_COUNT,
    tags=["stress-test", "airbyte", "broken", "anti-pattern"],
    doc_md=__doc__,
) as dag:

    for i in range(1, TASK_COUNT + 1):
        BrokenDeferrableAirbyteSyncOperator(
            task_id=f"airbyte_sync_{i}",
            connection_id=MOCK_CONNECTION_ID,
            airbyte_conn_id=AIRBYTE_CONN_ID,
            callback_sleep=CALLBACK_SLEEP_SECONDS,
            retries=0,                             # No retries -- focus on callback bug
            execution_timeout=timedelta(minutes=15),
        )
