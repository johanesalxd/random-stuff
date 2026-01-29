# BigQuery Streaming CDC Demo

This project demonstrates how to perform **Change Data Capture (CDC)** updates into BigQuery using the **Storage Write API** with **Protobuf** serialization.

It validates that "normal" inserts containing the pseudo-columns `_CHANGE_TYPE` and `_CHANGE_SEQUENCE_NUMBER` correctly trigger BigQuery's native CDC process when applied to a table with a **Primary Key** and `max_staleness`.

## Prerequisites

1.  **Google Cloud Project**: Access to a project with BigQuery enabled.
2.  **`gcloud` CLI**: Authenticated with a user/service account that has BigQuery Admin permissions (to create tables and write data).
    *   `gcloud auth login`
    *   `gcloud auth application-default login`
3.  **`uv`**: A fast Python package manager. [Install uv](https://github.com/astral-sh/uv).

## Project Structure

*   `create_table.py`: Creates a BigQuery table with:
    *   **Primary Key**: `id`
    *   **Max Staleness**: `15 minutes` (required to enable CDC processing on streaming buffers)
*   `stream_cdc.py`: Streams data using the low-level **Storage Write API** (`AppendRowsRequest`).
    *   Dynamically defines a Protobuf schema in Python to include the CDC pseudo-columns (`_CHANGE_TYPE`, `_CHANGE_SEQUENCE_NUMBER`) without needing external `.proto` files.
    *   Simulates a sequence of operations: Insert, Update, Delete.
*   `run_demo.sh`: Orchestrates the creation and streaming steps.

## Usage

1.  **Initialize**:
    ```bash
    uv sync
    ```

2.  **Run the Demo**:
    ```bash
    ./run_demo.sh
    ```

## How it Works

1.  **Table Creation**: The table is created with `max_staleness` set. This tells BigQuery to expect high-throughput updates and allows it to perform background CDC merging.
2.  **Dynamic Protobuf**: Because `_CHANGE_TYPE` is a pseudo-column, it doesn't exist in the standard table schema. We use Python's `google.protobuf.descriptor_pb2` to create a message class on the fly that matches the table schema *plus* the hidden CDC fields.
3.  **Streaming**: The script sends a batch of rows. BigQuery receives them and, based on the `_CHANGE_SEQUENCE_NUMBER`, applies the latest state (or deletes the row) asynchronously.

## Verification

After running the demo, you can query the table in the BigQuery console:

```sql
SELECT * FROM `demo_dataset.cdc_demo`
```

*Note: You might need to wait up to `max_staleness` (15 mins) to see the final merged result, or you can force a fresh read by altering the table options to 0 staleness.*

## Scalability Considerations

The `stream_cdc.py` script is optimized for **readability** and **simplicity** to demonstrate the mechanics of CDC. However, for **high-throughput production workloads**, consider the following improvements:

1.  **Persistent Connections (Streaming)**
    *   **Current**: The demo opens a new gRPC connection (stream) for the batch.
    *   **Production**: Reuse the `BigQueryWriteClient` and keep the stream open (stateful). Use a Python **generator** to feed `append_rows` continuously without re-establishing connections, which incurs significant latency.

2.  **Schema Caching**
    *   **Current**: The demo attaches the `writer_schema` to the request.
    *   **Production**: In a persistent stream, you only need to send the `writer_schema` on the **first** request. Subsequent requests in the same stream should omit it to save bandwidth and processing overhead.

3.  **Serialization Performance**
    *   **Current**: We use dynamic Python object instantiation (`setattr` loop), which is CPU-intensive.
    *   **Production**: Use compiled `.proto` files (via `protoc`) or optimized serialization libraries (like `ujson` or C++-backed Protobuf) to handle thousands of messages per second.

4.  **Batching Strategy**
    *   **Current**: The demo buffers a small list in memory.
    *   **Production**: Implement a buffer that flushes based on **size** (e.g., 10MB) or **time** (e.g., every 1 second) to balance latency vs. throughput.
