-- =============================================================================
-- SGX Data Contracts: Executive Data Quality Scorecard & Incident Forensics
-- Queries for BigQuery export results table: ${PROJECT_ID}.sgx_market_data.dq_export_results
-- Governed by Open Data Contract Standard (ODCS) v3.0 & MAS TRM Section 8
-- =============================================================================

-- =============================================================================
-- Query 1: Executive KPI Dashboard (Latest Scan Summary)
-- Produces overall health score, per-dimension SLA scores, and regulatory RAG status
-- =============================================================================

WITH latest_scan AS (
  SELECT data_quality_job_id
  FROM `${PROJECT_ID}.sgx_market_data.dq_export_results`
  ORDER BY job_start_time DESC
  LIMIT 1
),
rule_evals AS (
  SELECT
    r.data_quality_job_id,
    r.job_start_time,
    COALESCE(r.data_source.table_id, 'equity_trades') AS table_name,
    r.rule_dimension,
    r.rule_name,
    r.rule_passed,
    COALESCE(r.rule_rows_evaluated, r.job_rows_scanned, 0) AS rows_evaluated,
    COALESCE(r.rule_rows_passed, IF(r.rule_passed, r.rule_rows_evaluated, 0)) AS rows_passed
  FROM `${PROJECT_ID}.sgx_market_data.dq_export_results` r
  JOIN latest_scan ls ON r.data_quality_job_id = ls.data_quality_job_id
)
SELECT
  MAX(data_quality_job_id) AS job_id,
  MAX(job_start_time) AS execution_timestamp,
  MAX(table_name) AS target_table,
  COUNT(*) AS total_rules_evaluated,
  COUNTIF(rule_passed) AS total_rules_passed,
  COUNTIF(NOT rule_passed) AS total_rules_failed,
  -- Overall Quality Score %
  ROUND(SAFE_DIVIDE(100.0 * COUNTIF(rule_passed), COUNT(*)), 2) AS overall_score_pct,
  -- Per-Dimension Scores %
  ROUND(100.0 * COUNTIF(rule_dimension = 'COMPLETENESS' AND rule_passed) / NULLIF(COUNTIF(rule_dimension = 'COMPLETENESS'), 0), 2) AS completeness_score_pct,
  ROUND(100.0 * COUNTIF(rule_dimension = 'VALIDITY' AND rule_passed) / NULLIF(COUNTIF(rule_dimension = 'VALIDITY'), 0), 2) AS validity_score_pct,
  ROUND(100.0 * COUNTIF(rule_dimension = 'FRESHNESS' AND rule_passed) / NULLIF(COUNTIF(rule_dimension = 'FRESHNESS'), 0), 2) AS freshness_score_pct,
  ROUND(100.0 * COUNTIF(rule_dimension = 'INTEGRITY' AND rule_passed) / NULLIF(COUNTIF(rule_dimension = 'INTEGRITY'), 0), 2) AS integrity_score_pct,
  -- Regulatory RAG Status Flag (MAS TRM Compliance)
  CASE
    WHEN COUNT(*) = 0 THEN 'NO DATA (No DataScan Executions Found)'
    WHEN COUNTIF(rule_dimension = 'INTEGRITY' AND NOT rule_passed) > 0 THEN 'RED (CRITICAL: Anti-Wash Trading Breach)'
    WHEN COUNTIF(rule_dimension = 'FRESHNESS' AND NOT rule_passed) > 0 THEN 'RED (CRITICAL: Market Data Freshness SLA Breach)'
    WHEN COUNTIF(NOT rule_passed) = 0 THEN 'GREEN (100% SLA Compliant)'
    ELSE 'AMBER (Quality Warning: Check Range/Validity)'
  END AS executive_rag_status
FROM rule_evals;

-- =============================================================================
-- Query 2: Dimension-Level Quality Breakdown Matrix
-- Evaluates SLA pass rate, rule counts, and volume compliance per dimension
-- =============================================================================

WITH latest_scan AS (
  SELECT data_quality_job_id
  FROM `${PROJECT_ID}.sgx_market_data.dq_export_results`
  ORDER BY job_start_time DESC
  LIMIT 1
)
SELECT
  r.rule_dimension AS dimension,
  COUNT(*) AS total_rules,
  COUNTIF(r.rule_passed) AS rules_passed,
  COUNTIF(NOT r.rule_passed) AS rules_failed,
  ROUND(100.0 * COUNTIF(r.rule_passed) / COUNT(*), 2) AS dimension_pass_pct,
  SUM(COALESCE(r.rule_rows_evaluated, 0)) AS total_rows_evaluated,
  SUM(COALESCE(r.rule_rows_passed, 0)) AS total_rows_passed,
  CASE
    WHEN COUNTIF(NOT r.rule_passed) = 0 THEN 'PASS'
    ELSE 'FAIL'
  END AS dimension_status
FROM `${PROJECT_ID}.sgx_market_data.dq_export_results` r
JOIN latest_scan ls ON r.data_quality_job_id = ls.data_quality_job_id
GROUP BY r.rule_dimension
ORDER BY dimension_pass_pct ASC, dimension ASC;

-- =============================================================================
-- Query 3: SLA Violation Incident Report & Forensics Drill-down
-- Details violating rules, failure record counts, and executable debug queries
-- =============================================================================

WITH latest_scan AS (
  SELECT data_quality_job_id
  FROM `${PROJECT_ID}.sgx_market_data.dq_export_results`
  ORDER BY job_start_time DESC
  LIMIT 1
)
SELECT
  r.rule_dimension AS dimension,
  r.rule_name,
  r.rule_type,
  r.rule_column,
  r.rule_rows_evaluated AS evaluated_records_count,
  (COALESCE(r.rule_rows_evaluated, 0) - COALESCE(r.rule_rows_passed, 0)) AS failed_records_count,
  ROUND(COALESCE(r.rule_rows_passed_percent, 0.0), 2) AS pass_percent,
  r.rule_failed_records_query AS debug_inspection_query
FROM `${PROJECT_ID}.sgx_market_data.dq_export_results` r
JOIN latest_scan ls ON r.data_quality_job_id = ls.data_quality_job_id
WHERE r.rule_passed = FALSE
ORDER BY r.rule_dimension ASC, r.rule_name ASC;
