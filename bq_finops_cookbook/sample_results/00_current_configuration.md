# Current Configuration Analysis

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

## Existing Reservations

A single unused reservation was detected in the project:

- **Reservation Name:** `test-reservation`
- **Edition:** Standard
- **Baseline Slots:** 0 (Standard edition does not support baseline slot capacity)
- **Autoscale Max Slots:** 100
- **Autoscale Current Slots:** 0
- **Ignore Idle Slots:** True
- **Target Job Concurrency:** 0 (Not supported in Standard edition)

## Reservation Assignments

No active reservation assignments were found:

- **Assignments:** None
- **Impact:** All workloads are currently using the default On-Demand (pay-as-you-go) billing model instead of using `test-reservation`.

## Historical commitments

No historical slot commitments are active or recorded:

- **Commitments:** None

## Current Utilization and Idle Slots

Since there are no active reservation assignments and all queries are billed via on-demand, no slot utilization or idle slots are recorded under `test-reservation` or other capacity reservations.

## On-Demand / Unassigned Workloads

100% of query workloads are processed on-demand:

- **Total Queries (30 days):** 160 queries
- **On-Demand Queries:** 160 queries (100%)
- **Reservation Queries:** 0 queries (0%)
