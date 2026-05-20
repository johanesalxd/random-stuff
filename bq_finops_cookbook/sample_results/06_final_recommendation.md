# Final Recommendation

## Strategy: Option A: Stay On-Demand (PAYG)

### Reasoning
Based on the 30-day analysis of project `demo-project`, the workload is **negligible**.
*   **Average Slot Usage**: 0.0 slots
*   **Peak Usage (Max)**: 0.2 slots
*   **Total Slot Hours**: 0.4 hours (negligible relative to any practical reservation footprint)

Creating a reservation for this workload would leave almost all provisioned capacity idle. Standard Edition autoscaling is also unnecessary here: the observed activity is sporadic and tiny, so staying on-demand is the safer recommendation unless project-specific pricing, discounts, or recommender output says otherwise.

### Action Plan
1.  **Maintain On-Demand Pricing**: Do not create reservations for this workload based on the observed slot profile.
2.  **Resolve Access Errors**: Investigate the high volume of `accessDenied` errors on `demo_dataset.employees`. Ensure users have the correct Data Catalog Policy Tags or IAM permissions to access protected columns (`salary`, `ssn`, etc.).
3.  **Storage Cleanup**: Review the ~400 GB of "Long Term" storage in `mdm_demo` and `demo_dataset`. If these are obsolete demo artifacts, deleting them will provide the most immediate cost savings.
4.  **Cross-check Recommendations**: Review BigQuery recommender output (`INFORMATION_SCHEMA.RECOMMENDATIONS` or Recommender API) before making production pricing or reservation changes.

### Monitoring
*   Re-evaluate if workload volume or predictability materially increases; use current regional pricing and edition-specific slot-hour rates rather than a fixed universal break-even threshold.
*   Monitor `accessDenied` error rates to ensure legitimate business processes aren't being blocked.
