# Final Recommendation

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

## Current State Summary

- `OBSERVED`: p50=450, p95=1,800, max=2,400 synthetic slots.
- `DERIVED`: the workload exceeds the current 1,600-slot Standard-edition ceiling.
- `HEURISTIC`: steady baseline use plus large peaks merits Enterprise capacity evaluation.
- `OFFICIAL`: an invalid 2,500-slot Standard reservation must never be proposed.

## Evidence Quality

- **Confidence:** MEDIUM
- **Query status:** synthetic fixture; no live MCP execution
- **IAM / visibility gaps:** current Slot Recommender output unavailable
- **Pricing verification:** NOT VERIFIED; no dollar savings claimed

## Recommended Strategy

**Choice:** Enterprise evaluation with baseline plus autoscaling

`HEURISTIC`: Start scenario testing around a 500-slot baseline plus 1,900 additional autoscaling slots, for a 2,400-slot total maximum. Final sizing requires Slot Estimator/Recommender evidence, current pricing, queue/runtime SLOs, and administrator review.

## Alternative Analysis

- **On-demand:** viable fallback while evidence is incomplete.
- **Standard autoscaling:** rejected because the synthetic peak exceeds the documented 1,600-slot maximum.
- **Enterprise baseline:** candidate, subject to economics and SLOs.
- **Hybrid:** candidate if production and development projects can be isolated cleanly.

## Optimization Actions

1. Optimize the highest-slot queries before purchasing capacity.
2. Move noncritical batch work away from peak windows.
3. Compare on-demand, Enterprise, and hybrid scenarios using verified prices.

## Implementation Proposals

**Classification:** `PROPOSAL_NONDESTRUCTIVE` — text only, not executed. Replace every placeholder and validate current CLI rules before administrator approval.

```bash
bq mk --reservation \
  --project_id=[ADMIN_PROJECT_ID] \
  --location=[REGION] \
  --edition=ENTERPRISE \
  --slots=500 \
  --autoscale_max_slots=1900 \
  [RESERVATION_NAME]
```

No assignment or commitment purchase is proposed until project ownership and pricing are verified.

## Validation Criteria

- [ ] Slot Estimator/Recommender evidence reconciled.
- [ ] Queue and p95 runtime SLOs improve or remain healthy.
- [ ] Current edition/location prices support the economics.
- [ ] Rollback and assignment ownership are approved.

## Documentation Checks

- Standard maximum verified from current BigQuery editions documentation.
- Reservation flags and increment behavior must be rechecked immediately before implementation.

## MCP / bq Execution Notes

This is a synthetic offline fixture. No MCP or `bq` command ran.

## Next Steps

1. Run the read-only analysis against an approved project.
2. Collect current Slot Estimator/Recommender and pricing evidence.
3. Have a BigQuery administrator review any final proposal.
