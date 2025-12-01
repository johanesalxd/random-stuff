# BigQuery vs Databricks Scaling Visualization

An interactive visualization comparing the scaling mechanics of **Databricks Serverless SQL** and **Google BigQuery**.

## Live Demo

[View Live Demo](https://johanesalxd.github.io/random-stuff/bq_scaling_viz/)

## Overview

This visualization demonstrates the fundamental difference between "chunky" cluster-based scaling (Databricks) and "seamless" slot-based scaling (BigQuery).

### Key Concepts

**Databricks Serverless SQL:**
- Scales by adding entire clusters with fixed capacity
- Queries are "locked-in" to their assigned cluster
- Running queries cannot migrate to new clusters
- Results in the "stuffing effect" where early queries remain slow

**Google BigQuery:**
- Scales by adding granular slot units
- Uses fair scheduling to dynamically rebalance resources
- Running queries benefit from newly added capacity
- Provides consistent performance as capacity scales

## Features

- **Interactive Simulation**: Add jobs to see how each platform scales
- **Configurable Cluster Sizes**: Choose from Small (12 DBU), Medium (20 DBU), Large (40 DBU), or X-Large (80 DBU)
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

This visualization demonstrates a key scenario:

1. **Query 1**: Gets full cluster capacity
2. **Queries 2-10**: Share resources (stuffing effect)
3. **Query 11**: Triggers new cluster, gets full capacity
4. **Result**: Queries 1-10 remain slow, locked to first cluster

In BigQuery, all queries would benefit from the increased capacity through dynamic rebalancing.

## Important Caveats

The visualization includes a comprehensive "Caveats & Limitations" section that explains:

- **Fixed 10-Query Limit**: The visualization uses a fixed threshold for educational purposes. In reality, Databricks IWM (Intelligent Workload Management) may trigger scaling earlier or later based on query complexity and resource demands.
- **Cluster Startup Times**: Classic/Pro warehouses take 2-5 minutes to provision new VMs. Serverless warehouses use pre-warmed pools for near-instant startup (seconds to ~1 minute), but pool exhaustion can result in similar delays.
- **Cloud Provider Dependencies**: Scaling is subject to CSP capacity availability. During peak demand, VM provisioning can be delayed or fail.
- **Locked-In Queries**: Regardless of when scaling occurs, running queries remain locked to their original cluster and cannot benefit from newly provisioned resources.

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
5. Choose folder: `/bq_scaling_viz`
6. Save

Your site will be live at: `https://[username].github.io/[repo-name]/bq_scaling_viz/`

## License

MIT License - feel free to use and modify for your own purposes.

## Credits

Based on research of official Databricks and Google BigQuery documentation.
