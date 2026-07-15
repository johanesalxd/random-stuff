# Current Configuration Analysis

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

- **Analysis Window:** [2026-05-05T00:00:00Z, 2026-06-04T00:00:00Z)

Unless labelled otherwise, fixture query rows are OBSERVED, calculations are
DERIVED, interpretations are HEURISTIC, and proposed actions are RECOMMENDATION.

## Existing Reservations

A single unused reservation was detected in the project:

- **Reservation Name:** `test-reservation`
- **Edition:** Standard
- **Baseline Slots:** 0 (Standard edition does not support baseline slot capacity)
- **Autoscale Max Slots:** 100
- **Autoscale Current Slots:** 0
- **Configured Max Slots:** N/A
- **Scaling Mode:** N/A
- **Configured Capacity Limit Slots:** 100 (shared idle capacity is excluded)
- **Ignore Idle Slots:** True
- **Target Job Concurrency:** 0 (Not supported in Standard edition)

## Reservation Assignments

No active reservation assignments were found:

- **Assignments:** None
- **Impact:** All workloads are currently using the default On-Demand (pay-as-you-go) billing model instead of using `test-reservation`.

## Commitments

No historical slot commitments are active or recorded:

- **Current Commitments:** None
- **Recent Change Ledger:** None

## Analyzed-Project Reservation Contribution

Since there are no active reservation assignments and all queries are billed via on-demand, no analyzed-project reservation contribution is recorded. Reservation-wide sizing is not eligible from this evidence.

## Null-Reservation Compute Workloads

100% of query workloads are processed on-demand:

- **Total Queries (declared analysis window):** 160 queries
- **Cached Queries:** 0 queries
- **Positive-Slot Compute Queries:** 160 queries
- **Zero/Unknown-Compute Queries:** 0 queries
- **Failed Positive-Slot Queries:** 3 queries (overlapping diagnostic subset)
- **Null-Reservation Positive-Slot Queries:** 160 queries (100%)
- **Reservation Positive-Slot Queries:** 0 queries (0%)

## Query Status

| Query | Status | Evidence / Fallback | Scope or Blocking Note |
|---|---|---|---|
| 0.1 | PASS | Synthetic primary result | One unused Standard reservation |
| 0.2 | PASS | Synthetic primary result | Observed no assignments |
| 0.2a | PASS | Synthetic primary result | Observed no current or recent commitments |
| 0.3 | NOT APPLICABLE | Not run | No reservation-backed positive compute |
| 0.4 | NOT APPLICABLE | Not run | No applicable baseline comparison |
| 0.5 | PASS | Synthetic primary result | Project-scoped positive compute classification |

## Documentation Checks

| Claim | Source URL | Retrieved | Scope | PASS/GAP | Note |
|---|---|---|---|---|---|
| Reservation configuration fields | https://docs.cloud.google.com/bigquery/docs/information-schema-reservations | 2026-07-15 | Synthetic Standard reservation | PASS | Includes legacy autoscale and predictability fields |
| Cached query classification | https://docs.cloud.google.com/bigquery/docs/reservations-workload-management | 2026-07-15 | Synthetic query jobs | PASS | Cached jobs are reported separately |
