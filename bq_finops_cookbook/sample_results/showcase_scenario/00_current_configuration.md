# Current Configuration Analysis

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

- **Analysis Window:** [2025-12-18T00:00:00Z, 2026-01-17T00:00:00Z)

Unless labelled otherwise, fixture query rows are OBSERVED, calculations are
DERIVED, interpretations are HEURISTIC, and proposed actions are RECOMMENDATION.

## Existing Reservations

- **Reservation Name:** None found
- **Edition:** N/A
- **Baseline Slots:** N/A
- **Autoscale Max Slots:** N/A
- **Configured Max Slots:** N/A
- **Scaling Mode:** N/A
- **Configured Capacity Limit Slots:** N/A
- **Ignore Idle Slots:** N/A

## Reservation Assignments

- **Assignments:** None
- **Impact:** The analyzed workload used on-demand capacity.

## Commitments

- **Current Commitments:** None observed
- **Recent Change Ledger:** No retained change rows observed

## Analyzed-Project Reservation Contribution
- **Reservation:** None (On-Demand)
- **Baseline Slots:** 0
- **Autoscale Max:** N/A
- **Average Utilization:** N/A
- **Reservation-Wide Sizing Eligible:** No; only one workload project is in evidence

## Null-Reservation Compute Workloads
*Cached jobs are reported separately; 100% of positive-slot compute queries had no reservation.*

| Date | Completed Query Jobs | Cached | Positive Compute | Zero/Unknown Compute | Null Reservation | Reservation | % Null Reservation Positive Compute |
|------|----------------------|--------|------------------|----------------------|------------------|-------------|-------------------------------------|
| 2026-01-16 | 45,700 | 500 | 45,200 | 0 | 45,200 | 0 | 100% |
| 2026-01-15 | 42,550 | 400 | 42,150 | 0 | 42,150 | 0 | 100% |
| 2026-01-14 | 39,250 | 350 | 38,900 | 0 | 38,900 | 0 | 100% |
| ... | ... | ... | ... | ... | ... | ... | ... |

## Query Status

| Query | Status | Evidence / Fallback | Scope or Blocking Note |
|---|---|---|---|
| 0.1 | PASS | Synthetic primary result | Observed no reservations |
| 0.2 | PASS | Synthetic primary result | Observed no assignments |
| 0.2a | PASS | Synthetic primary result | No current commitments or retained change rows observed |
| 0.3 | NOT APPLICABLE | Not run | No reservation-backed positive compute |
| 0.4 | NOT APPLICABLE | Not run | No reservation baseline |
| 0.5 | PASS | Synthetic primary result | Project-scoped positive compute classification |

## Documentation Checks

| Claim | Source URL | Retrieved | Scope | PASS/GAP | Note |
|---|---|---|---|---|---|
| Cached query and reservation behavior | https://docs.cloud.google.com/bigquery/docs/reservations-workload-management | 2026-07-15 | Synthetic on-demand workload | PASS | Cached jobs are separated from compute jobs |
