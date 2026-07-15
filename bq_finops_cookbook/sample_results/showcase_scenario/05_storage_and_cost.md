# Storage & Cost Analysis

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

- **Analysis Window:** [2025-12-18T00:00:00Z, 2026-01-17T00:00:00Z)

Unless labelled otherwise, fixture query rows are OBSERVED, calculations are
DERIVED, interpretations are HEURISTIC, and proposed actions are RECOMMENDATION.

## Top Storage Consumers
*Top tables by total storage size.*

| Table | Total Size | Active | Long Term | % Long Term |
|-------|------------|--------|-----------|-------------|
| `logs.app_events_archive` | 250 TiB | 0 TiB | 250 TiB | 100% |
| `prod.orders` | 45 TiB | 45 TiB | 0 TiB | 0% |
| `staging.test_dump_2024` | 15 TiB | 0 TiB | 15 TiB | 100% |

**Recommendation:**
- **CRITICAL:** `logs.app_events_archive` is consuming **250 TiB** of long-term storage. Confirm retention requirements before moving or deleting it.
- **Economic Status:** NOT VERIFIED; storage volume alone does not establish a lower-cost action.
- **Action:** Consider partition expiration, lifecycle/retention policy changes,
  or alternate storage only after validating access patterns, compliance needs,
  current prices, and observed Billing evidence.

## Physical Storage Evidence

- **Total Physical:** 118 TiB (synthetic; excludes fail-safe)
- **Fail-Safe Physical:** 7 TiB (synthetic)
- **Physical Plus Fail-Safe:** 125 TiB (synthetic)

## Potential Cleanup Candidates

The archive and staging tables are review candidates only. Age and storage class do not prove disuse or authorize deletion.

## Storage Write API Activity

- **Status:** NOT APPLICABLE
- **Finding:** Storage Write API analysis was outside this synthetic scenario.

## Estimated Monthly Spend (Current)
- **Compute:** NOT VERIFIED
- **Storage:** NOT VERIFIED
- **Total:** NOT VERIFIED

**Optimization Target:**
- **Compute:** Evaluate Enterprise baseline-plus-autoscaling against on-demand
  against actual regional on-demand bytes processed, slot-hour pricing,
  scaled-slot billing, and supported Slot Recommender output. The synthetic peak
  exceeds the Standard limit used by this fixture.
- **Storage:** Reduce or tier archive logs where retention policy permits.
- **Expected Outcome:** No savings claim until current pricing inputs and production billing evidence are reconciled.
- **Economic Decision Status:** REVIEW_REQUIRED

## On-Demand Billing Evidence

- **Null-Reservation Bytes Billed:** synthetic evidence available in report 04
- **Estimated Cost:** NOT VERIFIED
- **Economic Decision Status:** REVIEW_REQUIRED

## Storage Billing Model Sensitivity

- **Status:** BLOCKED
- **Materiality Threshold:** not supplied
- **Lower-Forecast Candidate:** not produced
- **Billing and Storage-Semantics Reconciliation:** REVIEW_REQUIRED
- **Findings:** Current regional storage prices were unavailable, so no model comparison was produced.

## Query Status

| Query | Status | Evidence / Fallback | Scope or Blocking Note |
|---|---|---|---|
| 5.1 | NOT APPLICABLE | Not run | Ingestion analysis outside declared scope |
| 6.1 | PASS | Synthetic primary result | Logical, physical, and fail-safe values separate |
| 6.2 | PASS | Synthetic primary result | Review candidates only |
| 6.3 | BLOCKED | Required pricing and threshold absent | No dollar sensitivity output |

## Documentation Checks

| Claim | Source URL | Retrieved | Scope | PASS/GAP | Note |
|---|---|---|---|---|---|
| Storage billing models | https://docs.cloud.google.com/bigquery/docs/storage_overview | 2026-07-15 | Synthetic storage fixture | PASS | No DDL or numeric savings emitted |
| Numeric pricing | https://cloud.google.com/bigquery/pricing | 2026-07-15 | Synthetic location unspecified | GAP | Dollar estimates remain NOT VERIFIED |
