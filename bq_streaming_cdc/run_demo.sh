#!/bin/bash
set -e

echo "========================================"
echo "Creating BigQuery Table (CDC Enabled)..."
echo "========================================"
uv run create_table.py

echo ""
echo "========================================"
echo "Streaming CDC Events via Storage API..."
echo "========================================"
uv run stream_cdc.py
