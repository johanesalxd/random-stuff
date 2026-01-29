from google.cloud import bigquery

# Construct a BigQuery client object.
client = bigquery.Client()

project_id = client.project
dataset_id = "demo_dataset"
table_id = "cdc_demo"
table_ref = f"{project_id}.{dataset_id}.{table_id}"

# DDL to create table with Primary Key and Max Staleness
ddl = f"""
CREATE OR REPLACE TABLE `{table_ref}`
(
  id INT64,
  name STRING,
  PRIMARY KEY(id) NOT ENFORCED
)
OPTIONS(
  max_staleness = INTERVAL 0 MINUTE
);
"""

# Execute the DDL
query_job = client.query(ddl)
query_job.result()  # Wait for the job to complete.

print(f"Created table {table_ref} using DDL.")
