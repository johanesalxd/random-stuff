# Final Recommendation

## Strategy: Option A: Stay On-Demand (PAYG)

### Reasoning
Based on the 30-day analysis of project `demo-project`, the workload is **negligible**.
*   **Average Slot Usage**: 0.0 slots
*   **Peak Usage (Max)**: 0.2 slots
*   **Total Slot Hours**: 0.4 hours (approx. < $0.05 value)

Purchasing even the smallest slot commitment (100 slots) would result in **>99.9% waste**. Standard Edition autoscaling is also unnecessary as the On-Demand tier handles this volume effortlessly and is the most cost-effective model.

### Action Plan
1.  **Maintain On-Demand Pricing**: Do not create any reservations.
2.  **Resolve Access Errors**: Investigate the high volume of `accessDenied` errors on `demo_dataset.employees`. Ensure users have the correct Data Catalog Policy Tags or IAM permissions to access protected columns (`salary`, `ssn`, etc.).
3.  **Storage Cleanup**: Review the ~400 GB of "Long Term" storage in `mdm_demo` and `demo_dataset`. If these are obsolete demo artifacts, deleting them will provide the most immediate cost savings.

### Monitoring
*   Re-evaluate if monthly on-demand costs exceed **$2,000** (approx. break-even point for considering baseline slots, though autoscaling might be viable earlier).
*   Monitor `accessDenied` error rates to ensure legitimate business processes aren't being blocked.
