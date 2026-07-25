# BigQuery vs Databricks Scaling Visualization

An interactive visualization comparing the scaling mechanics of **Databricks Serverless SQL** and **Google BigQuery**.

## Live Demo

[View Live Demo](https://johanesalxd.github.io/random-stuff/bq_dbx_scaling_viz/)

## Overview

This visualization demonstrates the fundamental difference between "chunky" cluster-based scaling (Databricks) and "seamless" slot-based scaling (BigQuery).

### Key Concepts

**Databricks SQL Warehouses:**
- Scales by adding entire clusters of a fixed size ("chunky")
- Queries are "locked-in" to their assigned cluster; running queries cannot migrate to new clusters
- Results in the "stuffing effect" where early queries stay slow
- Classic/pro warehouses use a fixed "one cluster per 10 concurrent queries" rule; serverless uses Intelligent Workload Management (IWM), which scales on ML-predicted demand and queue wait time (no hard query-#11 trigger)

**Google BigQuery:**
- Scales slot capacity in increments (rounded up to the nearest 50 slots)
- Uses fair scheduling to reassign slots to running queries on the fly
- Running queries benefit from newly added capacity
- More consistent — but the autoscaler is reactive, has a 60-second minimum billing window, and is bounded by reservation limits (or ~2,000 slots/project on-demand)

## Features

- **Interactive Simulation**: Add jobs to see how each platform scales
- **Configurable Cluster Sizes**: Choose from Small (~12 DBU/hr), Medium (~24 DBU/hr), Large (~40 DBU/hr), or X-Large (~80 DBU/hr) — approximate serverless billing rates, not per-query compute budgets
- **DBU-to-Slots Ratio**: Adjust the conversion ratio (default 1:15)
- **Visual Indicators**: Orange highlighting shows "locked-in" slow queries in Databricks mode
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Detailed Explanations**: Includes scenario walkthrough, comparison table, and caveats section
- **Technical Accuracy**: Documents IWM behavior, cluster startup times, and cloud provider dependencies

## How to Use

1. **Select Mode**: Toggle between Databricks and BigQuery modes
2. **Configure Settings**:
   - Choose cluster size (Databricks only)
   - Adjust DBU-to-Slots ratio
3. **Add Jobs**: Click "+ Add Job" to simulate concurrent queries
4. **Observe Behavior**:
   - Databricks: Watch the "stuffing effect" and cluster scaling
   - BigQuery: See linear, seamless scaling

## The "1 to 11" Query Problem

This visualization demonstrates a key scenario (modeled on the classic/pro one-cluster-per-10-queries rule; serverless/IWM timing is queue-driven and only illustrative here):

1. **Query 1**: Gets full cluster capacity
2. **Queries 2-10**: Share resources (stuffing effect)
3. **Query 11**: Triggers new cluster, gets full capacity
4. **Result**: Queries 1-10 remain slow, locked to first cluster

In BigQuery, running queries benefit from added capacity through fair-scheduling rebalancing (within reservation / on-demand limits).

## Important Caveats

The visualization includes a comprehensive "Caveats & Limitations" section that explains:

- **Fixed 10-Query Limit**: The threshold is exact for classic/pro warehouses but illustrative for serverless. Databricks IWM may trigger scaling earlier or later based on query complexity, resource demands, and queue wait time.
- **Cluster Startup Times**: Classic/Pro warehouses take 2-5 minutes to provision new VMs. Serverless warehouses use pre-warmed pools for near-instant startup (seconds to ~1 minute), but pool exhaustion can result in similar delays.
- **Cloud Provider Dependencies**: Scaling is subject to CSP capacity availability. During peak demand, VM provisioning can be delayed or fail.
- **Locked-In Queries**: Regardless of when scaling occurs, running queries remain locked to their original cluster and cannot benefit from newly provisioned resources.
- **BigQuery isn't unbounded or instant**: Autoscaling moves in 50-slot increments, is reactive/conservative, carries a 60-second minimum billing window, and is capped by reservation limits (or ~2,000 slots/project on-demand). Fair scheduling rebalances only within available capacity.

These caveats ensure users understand the real-world behavior beyond the simplified demonstration.

## Technical Details

- **Pure HTML/CSS/JavaScript**: No dependencies, runs entirely in the browser
- **Responsive**: Uses CSS Grid and Flexbox with clamp() for fluid typography
- **Accessible**: Semantic HTML with proper ARIA labels

## Local Development

Simply open `index.html` in a web browser. No build process required.

## Deployment

This visualization is deployed using GitHub Pages. To deploy your own version:

1. Fork this repository
2. Go to Settings → Pages
3. Select source: Deploy from branch
4. Choose branch: `main`
5. Choose folder: `/bq_dbx_scaling_viz`
6. Save

Your site will be live at: `https://[username].github.io/[repo-name]/bq_dbx_scaling_viz/`

## Companion

This page is a companion to the **Open Data Platform** interactive reference (`bq_dbx_viz`), which maps platform ownership across Databricks and Google Cloud. The two share a common design system:

- `bq_dbx_viz` — *what runs where* (platform / ownership map)
- `bq_dbx_scaling_viz` — *how each platform scales* (scaling mechanics)

## References

Grounded to Google Cloud & Databricks documentation as of 25 Jul 2026. Each claim on the page links to the matching source below via inline `[n]` markers.

1. Databricks — [SQL warehouse sizing, scaling, and queuing behavior](https://docs.databricks.com/aws/en/compute/sql-warehouse/warehouse-behavior) — IWM & autoscaling; one cluster per 10 concurrent queries (classic/pro); queue-based autoscaling; 1,000 max queued queries; cluster size → driver/worker counts.
2. Databricks — [Databricks SQL pricing](https://www.databricks.com/product/pricing/databricks-sql) — per-size serverless DBU/hr rates (Small 12, Medium 24, Large 40, X-Large 80).
3. Databricks — [Serverless compute](https://docs.databricks.com/aws/en/compute/serverless/) — managed compute plane, pre-warmed capacity, rapid startup.
4. BigQuery — [Understand slots](https://cloud.google.com/bigquery/docs/slots) — fair scheduling (project → job, eventual fairness); 50-slot autoscale increments; on-demand ~2,000 slots/project, 20,000/org.
5. BigQuery — [Introduction to slots autoscaling](https://cloud.google.com/bigquery/docs/slots-autoscaling-intro) — 60-second scale-down window; Fluid Scaling.
6. BigQuery — [Understand reservations (workload management)](https://cloud.google.com/bigquery/docs/reservations-workload-management) — baseline + `autoscale_max_slots`; per-second, one-minute-minimum billing.
7. BigQuery — [Quotas & limits](https://cloud.google.com/bigquery/quotas) — on-demand concurrent slot quotas.

## License

MIT License - feel free to use and modify for your own purposes.

## Credits

Based on official Databricks and Google BigQuery documentation (see References).
