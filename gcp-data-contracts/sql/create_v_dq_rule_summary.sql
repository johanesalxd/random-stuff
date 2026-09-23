-- =============================================================================
-- SGX Data Contracts: Canonical 10-Column Quality Rule Summary View
-- View: ${PROJECT_ID}.sgx_market_data.v_dq_rule_summary
-- Implements canonical reporting abstraction on top of dq_export_results
-- Columns: job_id, execution_date, data_source, rule_name, dimension,
--          rule_type, passed, evaluated_records_count, null_count, pass_ratio
-- =============================================================================

CREATE OR REPLACE VIEW `${PROJECT_ID}.sgx_market_data.v_dq_rule_summary` AS
SELECT
  data_quality_job_id AS job_id,
  DATE(job_start_time) AS execution_date,
  COALESCE(data_source.table_id, data_source.resource_name, 'equity_trades') AS data_source,
  COALESCE(rule_name, rule_description) AS rule_name,
  rule_dimension AS dimension,
  rule_type,
  rule_passed AS passed,
  COALESCE(rule_rows_evaluated, job_rows_scanned, 0) AS evaluated_records_count,
  COALESCE(rule_rows_null, 0) AS null_count,
  ROUND(
    COALESCE(
      rule_rows_passed_percent / 100.0,
      IF(rule_rows_evaluated > 0, rule_rows_passed / rule_rows_evaluated, NULL),
      IF(rule_passed, 1.0, 0.0)
    ),
    4
  ) AS pass_ratio
FROM `${PROJECT_ID}.sgx_market_data.dq_export_results`;
