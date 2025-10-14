# Changelog

All notable changes to the BigQuery FinOps Optimization Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2025-10-14

### Added
- Historical commitment analysis (Step 0.2a) to track capacity evolution over time
- Job error pattern analysis (Step 4.8) to identify capacity-related failures
- Granular usage breakdown by project, user, and job type (Step 1.3 replacement)
- Confidence checks at key decision points for better validation
- Assumption validation steps before strategy recommendations
- Attribution to Google Cloud's BigQuery Utils repository
- Integration documentation in `docs/integration_plan.md`

### Changed
- Replaced basic hourly usage query with detailed workload segmentation analysis
- Enhanced output templates to include error analysis section
- Simplified README "What This Framework Does" section for clarity
- Updated workflow to maintain focus on workload management strategy

### Improved
- Better support for Hybrid Strategy recommendations through granular usage data
- Enhanced capacity planning with historical commitment context
- More actionable recommendations based on error patterns
- Clearer validation checkpoints throughout the analysis process

## [1.0.0] - 2025-10-01

### Added
- Initial release of BigQuery FinOps Optimization Framework
- Comprehensive slot usage analysis using INFORMATION_SCHEMA
- Workload characterization with stability and burstiness metrics
- Four workload management strategies: On-Demand, Baseline, Autoscaling, Hybrid
- Automated report generation in markdown format
- Step-by-step implementation guides
- Monitoring and validation queries
- Troubleshooting documentation

### Features
- 30-day historical analysis of slot utilization
- Percentile-based capacity planning
- Top consumer identification
- Usage pattern analysis by time
- Optimization opportunity detection
- Reservation simulation
- Current configuration assessment

### Documentation
- Comprehensive README with quick reference guide
- Detailed analysis methodology
- Decision framework diagrams
- Best practices and common pitfalls
- Official Google Cloud documentation references
