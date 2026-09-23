-- SGX Equity Trades Table DDL
-- Generated deterministically by compile_contract.py from contract.odcs.yaml
-- Governed by Open Data Contract Standard (ODCS) v3.0.0

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.sgx_market_data.equity_trades`
(
  trade_id STRING NOT NULL OPTIONS(description="Unique trade execution identifier"),
  instrument_code STRING NOT NULL OPTIONS(description="SGX security ticker symbol (e.g. D05.SI, Z74.SI)"),
  price NUMERIC NOT NULL OPTIONS(description="Execution trade price in SGD"),
  volume INT64 NOT NULL OPTIONS(description="Number of shares executed"),
  buyer_id STRING NOT NULL OPTIONS(description="Clearing participant ID of purchasing broker"),
  seller_id STRING NOT NULL OPTIONS(description="Clearing participant ID of selling broker"),
  trade_timestamp TIMESTAMP NOT NULL OPTIONS(description="UTC execution timestamp (ISO-8601 format)"),
  trade_status STRING NOT NULL OPTIONS(description="Trade lifecycle state: EXECUTED, CANCELLED, AMENDED"),
  -- Pub/Sub Metadata Ingestion Columns (required for --write-metadata),
  subscription_name STRING OPTIONS(description="Pub/Sub subscription that delivered the message"),
  message_id STRING OPTIONS(description="Pub/Sub message identifier"),
  publish_time TIMESTAMP OPTIONS(description="Pub/Sub message publish timestamp"),
  attributes STRING OPTIONS(description="Pub/Sub message attributes formatted as JSON"),
  PRIMARY KEY (trade_id) NOT ENFORCED
)
PARTITION BY DATE(trade_timestamp)
CLUSTER BY instrument_code, trade_status
OPTIONS(
  description="Real-time and historical equity trade executions on the Singapore Exchange (governed by ODCS contract)"
);
