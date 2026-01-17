# Validation Metrics: fct_orders_broken

## Overview
- **Optimized Table**: `johanesa-playground-326616.sample_gold.fct_orders_broken_migrated`
- **Current Table**: `johanesa-playground-326616.sample_gold.fct_orders_broken`
- **Validation Date**: 2026-01-16

## Validation Tests

| ID | Test Name | Priority | Type | Description | Threshold |
|----|-----------|----------|------|-------------|-----------|
| T01 | Row Count Match | CRITICAL | Completeness | Compare total row counts | 0.1% |
| T02 | PK Uniqueness | CRITICAL | Integrity | Ensure order_id is unique | 0% |
| T03 | Date Range Match | CRITICAL | Consistency | Compare min/max order_date | 0 days |
| T04 | Total Amount Match | HIGH | Accuracy | Sum of order_total_original | 1.0% |
| T05 | USD Amount Match | HIGH | Accuracy | Sum of order_total_usd | 1.0% |
| T06 | Status Distribution | HIGH | Consistency | Count by order_status | 1.0% |
| T07 | Customer ID Count | HIGH | Completeness | Count distinct customer_id | 0.1% |
| T08 | Total Units Match | MEDIUM | Accuracy | Sum of total_units | 1.0% |
| T09 | Discount Amount | MEDIUM | Accuracy | Sum of total_discount_amount | 1.0% |
| T10 | Null Check (Cust) | MEDIUM | Quality | Null rate of customer_name | 5% |

## Test SQLs

### T01: Row Count
```sql
SELECT count(*) as cnt FROM `{table}`
```

### T02: PK Uniqueness
```sql
SELECT count(*) - count(distinct order_id) as diff FROM `{table}`
```

### T03: Date Range
```sql
SELECT min(order_date) as min_dt, max(order_date) as max_dt FROM `{table}`
```
