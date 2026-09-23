-- =============================================================================
-- SGX Data Contracts: Dataplex Auto Data Quality Export Table DDL
-- Table: ${PROJECT_ID}.sgx_market_data.dq_export_results
-- Compatible with Google Cloud Dataplex Auto DQ BigQuery Export Schema
-- Schema Version: 1_6_0 (captured from live Dataplex Auto DQ export)
-- Partitioning: Daily by job_start_time
-- Clustering: rule_dimension, rule_passed, rule_type
-- =============================================================================

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.sgx_market_data.dq_export_results`
(
  data_quality_scan STRUCT<
    resource_name STRING,
    project_id STRING,
    location STRING,
    data_scan_id STRING,
    display_name STRING
  > OPTIONS(description="Metadata about the Dataplex DataScan resource"),
  data_source STRUCT<
    resource_name STRING,
    dataplex_entity_project_id STRING,
    dataplex_entity_project_number INT64,
    dataplex_lake_id STRING,
    dataplex_zone_id STRING,
    dataplex_entity_id STRING,
    table_project_id STRING,
    table_project_number INT64,
    dataset_id STRING,
    table_id STRING,
    catalog_id STRING,
    namespace_id STRING
  > OPTIONS(description="Source table or asset metadata evaluated by DataScan"),
  data_quality_job_id STRING OPTIONS(description="Unique execution job UUID"),
  data_quality_job_configuration JSON OPTIONS(description="Scan job configuration metadata"),
  job_labels JSON OPTIONS(description="Job user labels"),
  job_start_time TIMESTAMP OPTIONS(description="Job execution start timestamp"),
  job_end_time TIMESTAMP OPTIONS(description="Job execution end timestamp"),
  job_quality_result STRUCT<
    passed BOOLEAN,
    score FLOAT64,
    incremental_start STRING,
    incremental_end STRING
  > OPTIONS(description="Job-level quality evaluation summary"),
  job_dimension_result JSON OPTIONS(description="Dimension score breakdown JSON"),
  job_rows_scanned INT64 OPTIONS(description="Total rows processed in source table"),
  rule_name STRING OPTIONS(description="Name or ID of evaluated rule"),
  rule_description STRING OPTIONS(description="Rule description"),
  rule_type STRING OPTIONS(description="Rule type: Non-null, Range Check, Row condition, SQL assertion"),
  rule_evaluation_type STRING OPTIONS(description="Per row or Per table"),
  rule_column STRING OPTIONS(description="Target column evaluated (if column-level)"),
  rule_dimension STRING OPTIONS(description="Quality dimension: COMPLETENESS, VALIDITY, FRESHNESS, INTEGRITY"),
  rule_threshold_percent FLOAT64 OPTIONS(description="Pass threshold percent (0-100)"),
  rule_parameters JSON OPTIONS(description="Rule execution parameters"),
  rule_passed BOOLEAN OPTIONS(description="Rule evaluation pass/fail status"),
  rule_suspended BOOLEAN OPTIONS(description="Indicator of whether rule is suspended"),
  rule_rows_evaluated INT64 OPTIONS(description="Number of rows evaluated against rule"),
  rule_rows_passed INT64 OPTIONS(description="Number of rows passing rule"),
  rule_rows_passed_percent FLOAT64 OPTIONS(description="Percentage of evaluated rows passing (0-100)"),
  rule_rows_null INT64 OPTIONS(description="Number of null values encountered"),
  rule_failed_records_query STRING OPTIONS(description="SQL query returning violating rows"),
  created_on TIMESTAMP OPTIONS(description="Export record creation timestamp"),
  last_updated TIMESTAMP OPTIONS(description="Export record last update timestamp"),
  rule_assertion_row_count INT64 OPTIONS(description="Violating rows count for SQL assertions"),
  debug_queries ARRAY<STRUCT<
    description STRING,
    sql_statement STRING,
    debug_query_results ARRAY<STRUCT<
      name STRING,
      type STRING,
      value STRING
    >>
  >> OPTIONS(description="Structured debug queries and sample failing records"),
  rule_attributes JSON OPTIONS(description="Custom rule attributes"),
  rule_source STRUCT<
    rule_path_elements ARRAY<STRUCT<
      entry_source STRUCT<
        entry_type STRING,
        entry STRING,
        display_name STRING
      >,
      entry_link_source STRUCT<
        entry_link_type STRING,
        entry_link STRING
      >
    >>
  > OPTIONS(description="Lineage and catalog provenance of rule source")
)
PARTITION BY DATE(job_start_time)
CLUSTER BY rule_dimension, rule_passed, rule_type
OPTIONS(
  description="Dataplex Auto Data Quality scan execution history for SGX Equity Trades",
  labels=[("goog-dataplex-datascan-export-table-schema-version", "1_6_0")]
);
