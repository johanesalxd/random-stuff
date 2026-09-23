#!/usr/bin/env bash
# ==============================================================================
# SGX Google Cloud Data Contracts - End-to-End Demonstration Runner
# 7-Stage Demonstration of Ingress Gates, Storage Write API & Dataplex Auto DQ
# ==============================================================================
set -euo pipefail

trap 'echo "[ERROR] run_demo.sh failed at line $LINENO" >&2' ERR

# Default Configuration
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || echo '')}"
REGION="asia-southeast1"
DATASET_ID="sgx_market_data"
TABLE_ID="equity_trades"
TOPIC_ID="sgx-equity-trades-topic"
DLQ_SUB_ID="sgx-equity-trades-dlq-sub"
DATASCAN_ID="sgx-equity-trades-dq"
MODE="simulated"
VERBOSE=false
WAIT_DLQ=false
PRESET="global"

show_help() {
  cat <<EOF
Usage: ./run_demo.sh [OPTIONS]

Executes the complete 7-stage Data Contracts demonstration.

Options:
  --project-id=ID         GCP Project ID (default: current gcloud project)
  --region=REGION         GCP Region (default: asia-southeast1)
  --dataset=DATASET       BigQuery dataset ID (default: sgx_market_data)
  --table=TABLE           BigQuery table ID (default: equity_trades)
  --topic=TOPIC           Pub/Sub topic ID (default: sgx-equity-trades-topic)
  --dlq-sub=DLQ_SUB       DLQ pull subscription ID (default: sgx-equity-trades-dlq-sub)
  --datascan=SCAN         Dataplex Data Quality Scan ID (default: sgx-equity-trades-dq)
  --preset={global|sgx}   Market data preset (default: global)
  --global                Shortcut for --preset=global (US tech equities)
  --sgx                   Shortcut for --preset=sgx (Singapore Exchange counters)
  --mode={live|simulated} Execution mode: 'live' (GCP) or 'simulated' (offline) [default: simulated]
  --live                  Shortcut for --mode=live
  --simulated             Shortcut for --mode=simulated
  --dry-run               Shortcut for --mode=simulated
  --verbose               Enable verbose payload output
  --wait-dlq              Poll DLQ subscription for message quarantine
  -h, --help              Show this help message and exit
EOF
}

# Parse CLI Arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-id=*) PROJECT_ID="${1#*=}" ;;
    --project-id) PROJECT_ID="$2"; shift ;;
    --region=*) REGION="${1#*=}" ;;
    --region) REGION="$2"; shift ;;
    --dataset=*) DATASET_ID="${1#*=}" ;;
    --dataset) DATASET_ID="$2"; shift ;;
    --table=*) TABLE_ID="${1#*=}" ;;
    --table) TABLE_ID="$2"; shift ;;
    --topic=*) TOPIC_ID="${1#*=}" ;;
    --topic) TOPIC_ID="$2"; shift ;;
    --dlq-sub=*) DLQ_SUB_ID="${1#*=}" ;;
    --dlq-sub) DLQ_SUB_ID="$2"; shift ;;
    --datascan=*) DATASCAN_ID="${1#*=}" ;;
    --datascan) DATASCAN_ID="$2"; shift ;;
    --preset=*) PRESET="${1#*=}" ;;
    --preset) PRESET="$2"; shift ;;
    --global) PRESET="global" ;;
    --sgx) PRESET="sgx" ;;
    --mode=*) MODE="${1#*=}" ;;
    --mode) MODE="$2"; shift ;;
    --live) MODE="live" ;;
    --simulated|--dry-run) MODE="simulated" ;;
    --verbose) VERBOSE=true ;;
    --wait-dlq) WAIT_DLQ=true ;;
    -h|--help) show_help; exit 0 ;;
    *) echo "[ERROR] Unknown flag: $1" >&2; show_help; exit 1 ;;
  esac
  shift
done

if [[ "${MODE}" != "live" && "${MODE}" != "simulated" ]]; then
  echo "[ERROR] Invalid --mode: '${MODE}'. Must be 'live' or 'simulated'." >&2
  exit 1
fi

if [[ -z "${PROJECT_ID}" ]]; then
  if [[ "${MODE}" == "simulated" ]]; then
    PROJECT_ID="sgx-demo-project"
  else
    echo "[ERROR] PROJECT_ID is required for live mode. Pass --project-id or set gcloud project." >&2
    exit 1
  fi
fi

echo "========================================================================"
echo "   FINANCIAL TRADING DATA CONTRACTS - END-TO-END DEMONSTRATION          "
echo "   Two-Tier Ingress Gate & Dataplex Auto Data Quality SLA Enforcement   "
echo "========================================================================"
echo "Execution Mode   : ${MODE}"
echo "Market Preset    : ${PRESET^^}"
echo "Project ID       : ${PROJECT_ID}"
echo "Region           : ${REGION}"
echo "BigQuery Dataset : ${DATASET_ID}"
echo "BigQuery Table   : ${TABLE_ID}"
echo "Pub/Sub Topic    : ${TOPIC_ID}"
echo "DLQ Sub          : ${DLQ_SUB_ID}"
echo "Dataplex Scan    : ${DATASCAN_ID}"
echo "========================================================================"

# Stage 1: Compile Data Contract
echo -e "\n>> [Stage 1/7] Compiling Open Data Contract Standard (ODCS v3.0)..."
python3 compile_contract.py \
  --contract="contract.odcs.yaml" \
  --project-id="${PROJECT_ID}" \
  --dataset="${DATASET_ID}" \
  --table="${TABLE_ID}"
echo "   ✓ Contract compiled into Avro schema, BigQuery DDL, and Dataplex YAML spec."

# Stage 2: Stream Valid Trades (Happy Path)
echo -e "\n>> [Stage 2/7] Streaming 20 conforming equity trade executions (${PRESET})..."
if [[ "${MODE}" == "live" ]]; then
  PUB_FLAGS=(--project-id="${PROJECT_ID}" --topic="${TOPIC_ID}" --mode=valid --count=20 --preset="${PRESET}")
  if [[ "${VERBOSE}" == "true" ]]; then PUB_FLAGS+=(--verbose); fi
  python3 scripts/publish_events.py "${PUB_FLAGS[@]}"

  echo "   Waiting 5 seconds for Storage Write API insertion into BigQuery..."
  sleep 5
  bq query --project_id="${PROJECT_ID}" --use_legacy_sql=false \
    "SELECT COUNT(*) AS total_ingested FROM \`${PROJECT_ID}.${DATASET_ID}.${TABLE_ID}\`"
else
  if [[ "${PRESET}" == "global" ]]; then
    echo "   [SIMULATION] Publishing 20 valid trade executions (AAPL, GOOGL, MSFT, NVDA, AMZN)..."
  else
    echo "   [SIMULATION] Publishing 20 valid trade executions (DBS, Singtel, UOB, OCBC, SIA)..."
  fi
  echo "   ✓ Conforming trades accepted by Pub/Sub wire gate and committed via Storage Write API."
fi

# Stage 3: Test Perimeter Schema Rejection (Invalid Ingress)
echo -e "\n>> [Stage 3/7] Testing Wire-Level Perimeter Defense (Pub/Sub Schema Registry)..."
if [[ "${MODE}" == "live" ]]; then
  PUB_FLAGS=(--project-id="${PROJECT_ID}" --topic="${TOPIC_ID}" --mode=invalid-schema)
  if [[ "${VERBOSE}" == "true" ]]; then PUB_FLAGS+=(--verbose); fi
  python3 scripts/publish_events.py "${PUB_FLAGS[@]}"
else
  echo "   [SIMULATION] Sending 4 invalid payloads to topic boundary:"
  echo "     1. Missing required 'trade_id' -> Blocked with HTTP 400 INVALID_ARGUMENT"
  echo "     2. String price ('MARKET_CLOSE') -> Blocked with HTTP 400 INVALID_ARGUMENT"
  echo "     3. Float volume (100.5) -> Blocked with HTTP 400 INVALID_ARGUMENT"
  echo "     4. Invalid trade status ('PENDING') -> Blocked with HTTP 400 INVALID_ARGUMENT"
  echo "   ✓ Verified: 4/4 malformed records rejected synchronously at wire boundary."
fi

# Stage 4: Test Downstream Storage Failure & DLQ Routing
echo -e "\n>> [Stage 4/7] Testing Storage Write API Rejection & Dead-Letter Queue (DLQ)..."
if [[ "${MODE}" == "live" ]]; then
  DLQ_FLAGS=(--project-id="${PROJECT_ID}" --topic="${TOPIC_ID}" --mode=trigger-dlq --dlq-sub="${DLQ_SUB_ID}")
  if [[ "${WAIT_DLQ}" == "true" ]]; then DLQ_FLAGS+=(--wait-for-dlq); fi
  if [[ "${VERBOSE}" == "true" ]]; then DLQ_FLAGS+=(--verbose); fi
  python3 scripts/publish_events.py "${DLQ_FLAGS[@]}"
else
  echo "   [SIMULATION] Sending payload with unparseable timestamp format..."
  echo "     -> Accepted at wire boundary (Avro string type match)"
  echo "     -> Rejected by BigQuery Storage Write API (TIMESTAMP NOT NULL constraint)"
  echo "     -> Retried 5 times with exponential backoff"
  echo "     -> Automatically quarantined in DLQ topic: ${TOPIC_ID}-dlq"
  echo "   ✓ Verified: Main stream remains unblocked; corrupted payload isolated in DLQ."
fi

# Stage 5: Inject Semantic SLA Violations into BigQuery
echo -e "\n>> [Stage 5/7] Injecting Semantic Quality & SLA Violations into BigQuery..."
if [[ "${MODE}" == "live" ]]; then
  bq query --project_id="${PROJECT_ID}" --use_legacy_sql=false "
  INSERT INTO \`${PROJECT_ID}.${DATASET_ID}.${TABLE_ID}\`
  (trade_id, instrument_code, price, volume, buyer_id, seller_id, trade_timestamp, trade_status, subscription_name, message_id, publish_time, attributes)
  VALUES
  -- 1. Freshness SLA Breach (>2 hours old)
  ('TR-VIOL-FRESHNESS-001', 'D05.SI', 35.80, 2500, 'BROKER_DBS_01', 'BROKER_OCBC_02', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 4 HOUR), 'EXECUTED', 'manual_inj', 'msg-inj-01', CURRENT_TIMESTAMP(), '{}'),
  -- 2. Negative Price Breach (Validity range)
  ('TR-VIOL-PRICE-002', 'Z74.SI', -12.50, 500, 'BROKER_UOB_01', 'BROKER_DBS_02', CURRENT_TIMESTAMP(), 'EXECUTED', 'manual_inj', 'msg-inj-02', CURRENT_TIMESTAMP(), '{}'),
  -- 3. Zero Volume Breach (Validity range)
  ('TR-VIOL-VOL-003', 'O39.SI', 15.40, 0, 'BROKER_CITI_01', 'BROKER_SCB_01', CURRENT_TIMESTAMP(), 'EXECUTED', 'manual_inj', 'msg-inj-03', CURRENT_TIMESTAMP(), '{}'),
  -- 4. Anti-Wash Trading Breach (buyer_id == seller_id)
  ('TR-VIOL-WASH-004', 'U11.SI', 32.10, 10000, 'WASH_BROKER_999', 'WASH_BROKER_999', CURRENT_TIMESTAMP(), 'EXECUTED', 'manual_inj', 'msg-inj-04', CURRENT_TIMESTAMP(), '{}');
  "
  echo "   ✓ Injected 4 controlled SLA breaches into ${DATASET_ID}.${TABLE_ID}."
else
  echo "   [SIMULATION] Injecting 4 controlled financial SLA violations into test fixture:"
  echo "     - TR-VIOL-FRESHNESS-001: trade_timestamp = NOW - 4 HOURS (Freshness SLA breach)"
  echo "     - TR-VIOL-PRICE-002: price = -12.50 SGD (Validity range breach)"
  echo "     - TR-VIOL-VOL-003: volume = 0 shares (Validity range breach)"
  echo "     - TR-VIOL-WASH-004: buyer_id = seller_id = 'WASH_BROKER_999' (Financial Integrity breach)"
fi

# Stage 6: Run Dataplex Auto Data Quality Scan
echo -e "\n>> [Stage 6/7] Executing Dataplex Auto Data Quality DataScan..."
if [[ "${MODE}" == "live" ]]; then
  python3 scripts/run_dataplex_scan.py \
    --mode=run \
    --project-id="${PROJECT_ID}" \
    --location="${REGION}" \
    --datascan-id="${DATASCAN_ID}" \
    --dataset="${DATASET_ID}" \
    --table="${TABLE_ID}"
else
  python3 scripts/run_dataplex_scan.py \
    --mode=dry-run \
    --project-id="${PROJECT_ID}" \
    --dataset="${DATASET_ID}" \
    --table="${TABLE_ID}"
fi

# Stage 7: Display Executive Scorecard & Forensics Drilldown
echo -e "\n>> [Stage 7/7] Generating Executive Scorecard & Forensics Drilldown..."
if [[ "${MODE}" == "live" ]]; then
  python3 scripts/run_dataplex_scan.py \
    --mode=scorecard \
    --project-id="${PROJECT_ID}" \
    --dataset="${DATASET_ID}" \
    --table="${TABLE_ID}"
else
  echo "   [SIMULATION] Scorecard successfully evaluated by Dataplex Auto DQ engine above."
  echo "   Executive Scorecard SQL definitions available in: sql/query_executive_scorecard.sql"
  echo "     - Query 1: Executive KPI Dashboard (RAG Status Banner)"
  echo "     - Query 2: Dimension-Level Quality Breakdown Matrix"
  echo "     - Query 3: SLA Violation Incident Report & Forensics Drilldown"
fi

echo -e "\n========================================================================"
echo "   [SUCCESS] End-to-end demonstration completed successfully."
echo "========================================================================"
