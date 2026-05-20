# Final Recommendation

## Current State Summary
- **Slot Metrics:** p50=450, p95=1,800, max=2,400
- **Variability:** CV=0.79 (Moderate)
- **Burstiness:** Ratio=4.0 (High Burst)
- **Current Spend (Est):** ~$8,500/month (On-Demand)

## Recommended Strategy
**Choice: Autoscaling Reservations (Standard Edition)**

**Reasoning:**
Your workload is highly bursty (4x peak-to-median ratio). A fixed baseline of 500 slots would hurt performance during your critical 9AM peaks (requiring 2,200 slots). However, paying for 2,200 slots 24/7 is wasteful.

**Autoscaling** can scale capacity for the morning peaks without committing to peak capacity 24/7. Validate the economics with current regional slot-hour pricing, scaled-slot billing behavior, and any committed-use discounts before treating this as a cost-saving change.

**Configuration:**
- **Edition:** Standard (autoscaling-only; billed for scaled slot capacity, not actual slot utilization)
- **Max Autoscale:** 2,500 slots (to cover the max peak)
- **Baseline:** Not applicable in Standard Edition; evaluate Enterprise/Enterprise Plus only if guaranteed baseline capacity or commitments are needed
- **Validation:** Cross-check BigQuery Slot Recommender / `INFORMATION_SCHEMA.RECOMMENDATIONS` before production changes.

## Alternative Analysis

### Why Other Options Were Not Recommended

**Option A: Stay On-Demand (PAYG)**
- **Why Considered:** Simplicity.
- **Why Rejected:** Current spend appears high enough to justify evaluating capacity pricing, but do not assume autoscaling is cheaper universally; compare against actual regional on-demand bytes processed, slot-hour pricing, and recommender output.

**Option C: Baseline Reservations (Enterprise/Enterprise Plus)**
- **Why Considered:** Discounts (1-year commit).
- **Why Rejected:** Valley usage is low. Committing to peak capacity (~2,000 slots) would likely waste substantial capacity, while committing near the average (~500 slots) may still leave morning peaks dependent on autoscaling or queues.

## Implementation Steps

### Step 1: Create Reservation
```bash
bq mk --reservation --project_id=my-project --location=US --edition=STANDARD --autoscale_max_slots=2500 prod_autoscale
```

### Step 2: Assign Project
```bash
bq mk --reservation_assignment --reservation_id=my-project:US.prod_autoscale --job_type=QUERY --assignee_type=PROJECT --assignee_id=ecommerce-prod
```
