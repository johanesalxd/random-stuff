# BigQuery Storage Write API Stress Test

## Goal

Test the maximum throughput of BigQuery's Storage Write API (reported limit: 300 MB/s per region) by generating synthetic data faster than BQ can ingest it.

## Why Synthetic Data?

Using streaming sources (Kafka, Pub/Sub) typically bottlenecks on:
- Source read throughput
- Small bundle sizes (streaming latency optimization)
- Network contention (read + write competing)

By generating data in-memory, we eliminate read I/O and test pure write bandwidth.

## Method

```
GenerateSequence (unbounded, max speed)
    ↓
Reshuffle (distribute across workers)
    ↓
Map: Generate ~5KB e-commerce transaction
    ↓
WriteToBigQuery (Storage Write API)
```

Each transaction row is ~5KB, with a large `shipping_address` JSON field acting as the bandwidth driver. At 300 MB/s, this means ~60,000 rows/second.

## Configuration

| Setting | Value |
|---------|-------|
| Region | asia-southeast1 |
| Workers | 5x n2-standard-4 |
| Duration | Manual (use cancel.sh) |
| Target | 300 MB/s |

## Usage

```bash
uv sync        # Install dependencies (first time only)
./run.sh       # Drop/create table, submit job
./cancel.sh    # Cancel running jobs (with prompt)
./cancel.sh -f # Cancel without prompt
```

## What `run.sh` Does

1. Drops the target table if it exists
2. Creates a fresh empty table with schema
3. Submits the streaming Dataflow job

## Cost Estimate

~$12 USD per 10-minute test (BQ ingestion + Dataflow workers)

## Verify Results

```sql
SELECT 
  COUNT(*) AS total_rows, 
  ROUND(SUM(LENGTH(shipping_address))/1024/1024/1024, 2) AS total_gb
FROM `johanesa-playground-326616.demo_dataset_asia.stress_test_transactions`
```
