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

## Setup

Set environment variables before running:

```bash
export GCP_PROJECT="your-project-id"
export GCP_REGION="asia-southeast1"
export GCP_TEMP_BUCKET="gs://your-bucket/dataflow/stress-test"
```

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
FROM `your-project-id.your_dataset.stress_test_transactions`
```

## Test Results

### Summary

| Metric | Value |
|--------|-------|
| Total Rows Ingested | 6,239,978 |
| Total Data Ingested | 102.47 GB |
| Test Duration | ~35 minutes |
| Avg Row Size | 17.22 KB |
| Peak Burst (Dataflow) | 243 MiB/s |
| Peak Sustained (BQ) | 83 MB/s |
| Avg Throughput | 50 MB/s |

### Quota Limit Reached

The pipeline successfully triggered BigQuery's AppendRows quota limit:

```
RESOURCE_EXHAUSTED: Exceeds 'AppendRows throughput' quota
user_id: project0000008d0226dd0f_asia-southeast1
status: INSUFFICIENT_TOKENS
```

A total of 441 quota errors occurred in 4 distinct bursts, confirming the pipeline generates data faster than the project quota allows.

### Throughput Analysis

```
                    Dataflow Metrics vs BQ Table Data
    
Throughput │
(MB/s)     │
           │                                           ▲ 243 (Dataflow burst
 250 ──────┼───────────────────────────────────────────│── includes retries)
           │                                          ╱│╲
           │         ▲ 160                           ╱ │ ╲
 150 ──────┼────────╱─╲──────────────────────────────────────
           │       ╱   ╲     ▲                      ╱     ╲
           │      ╱     ╲   ╱ ╲                    ╱       ╲
  83 ──────┼─────╱───────╲─╱───╲──────────────────╱─────────╲─ BQ peak
           │    ╱         ╳     ╲                ╱           ╲
  50 ══════╪═══════════════════════════════════════════════════ BQ average
           │
   0 ──────┴──────────────────────────────────────────────────►
              9:35    9:43    9:50    9:55   10:01   10:05
                       │              │        │
                   1st quota      3rd quota  4th quota
                   exhaustion     burst      burst (441 errors)
```

**Dataflow Job Metrics Screenshot:**

![Dataflow Throughput Metrics](images/Screenshot%202026-02-05%20220627.png)

**Why Dataflow shows higher peaks than BQ table:**
1. Dataflow metrics include failed writes being retried
2. During quota throttling, retry multiplier can reach 4x
3. BQ table only reflects successfully committed data

### Key Insights

1. Pipeline CAN generate 243+ MiB/s (proven by Dataflow metrics)
2. Default project quota limits sustained throughput to ~50 MB/s
3. Quota uses token bucket algorithm (allows bursts, then throttles)
4. To reach 300 MB/s regional limit, request higher AppendRows quota
