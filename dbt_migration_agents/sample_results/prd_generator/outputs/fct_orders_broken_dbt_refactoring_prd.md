# PRD: Refactoring fct_orders_broken

**Status:** Draft
**Date:** 2026-01-16
**Author:** AI Agent
**Target:** `johanesa-playground-326616.sample_gold`

## 1. Executive Summary

**Objective:** Refactor the Gold layer model `fct_orders_broken` to eliminate reliance on a fragmented intermediate Silver chain (`int_orders_cleaned_broken` → `int_orders_enriched_broken` → `int_orders_final_broken`) and instead use the consolidated and correct `stg_orders` model.

**Business Impact:**
- Reduces lineage depth from 4 hops to 2 hops.
- Eliminates 3 unnecessary intermediate materializations.
- Aligns with standard architecture (Bronze → Silver (Consolidated) → Gold).
- Simplifies maintenance and debugging.

**Scope:**
- 1 Gold model to refactor: `fct_orders_broken`
- 3 Silver models to deprecate: `int_orders_cleaned_broken`, `int_orders_enriched_broken`, `int_orders_final_broken`

## 2. Background & Context

### Architecture
- **Bronze:** `johanesa-playground-326616.sample_bronze` (Raw)
- **Silver:** `johanesa-playground-326616.sample_silver` (Transformed/Cleaned)
- **Gold:** `johanesa-playground-326616.sample_gold` (Curated/Fact)

### Current State
`fct_orders_broken` currently consumes data from `int_orders_final_broken`, which is the end of a chain of 3 single-purpose transformations. This pattern is inefficient and identified as "broken" in the codebase.

### Target State
`fct_orders_broken` will consume data directly from `stg_orders`, which encapsulates all the logic of the broken chain in a single, efficient step.

## 3. Objectives & Success Metrics

### Objectives
1.  **Simplify Lineage:** Remove dependency on `int_*_broken` models.
2.  **Maintain Data Integrity:** Ensure `fct_orders_broken` output remains identical (or better due to correct deduplication in `stg_orders`).
3.  **Optimize Performance:** Reduce upstream storage and compute usage.

### Success Metrics
- **Row Count Match:** `stg_orders` row count matches `int_orders_final_broken` (allowance for duplicates removed).
- **Column Parity:** All columns used in `fct_orders_broken` are available in `stg_orders`.
- **Successful Build:** Refactored model builds successfully in Gold layer.

## 4. Proposed Solution

### Migration Strategy
- **Type:** Refactor (Change Source)
- **Source:** `johanesa-playground-326616.sample_silver.stg_orders`
- **Target:** `johanesa-playground-326616.sample_gold.fct_orders_broken`

### Models
| Model | Action | Source | Target |
|-------|--------|--------|--------|
| `fct_orders_broken` | **REFACTOR** | `int_orders_final_broken` | `stg_orders` |
| `int_orders_final_broken` | **DEPRECATE** | - | - |
| `int_orders_enriched_broken` | **DEPRECATE** | - | - |
| `int_orders_cleaned_broken` | **DEPRECATE** | - | - |

## 5. Technical Requirements

### Model: `fct_orders_broken`

**CURRENT (Broken Pattern):**
```sql
-- Source: {{ ref('int_orders_final_broken') }}
WITH orders AS (
    SELECT *
    FROM {{ ref('int_orders_final_broken') }}
),
...
```

**NEW (Refactored):**
```sql
-- Target: johanesa-playground-326616.sample_gold.fct_orders_broken
-- Source: {{ ref('stg_orders') }}

{{ config(
    materialized='table',
    tags=['gold', 'curated', 'fact', 'orders', 'broken', 'demo'],
    project='johanesa-playground-326616',
    schema='sample_gold'
) }}

WITH orders AS (
    -- REFACTORED: Read from consolidated stg_orders
    SELECT *
    FROM {{ ref('stg_orders') }}
),

customers AS (
    SELECT
        customer_id,
        full_name AS customer_name,
        country_code AS customer_country
    FROM {{ ref('stg_customers') }}
),

order_items AS (
    SELECT *
    FROM {{ ref('stg_order_items') }}
),

-- Aggregate order items per order
order_item_summary AS (
    SELECT
        order_id,
        COUNT(DISTINCT line_id) AS total_line_items,
        SUM(quantity) AS total_units,
        COUNT(DISTINCT product_id) AS unique_products,
        SUM(line_total) AS subtotal,
        SUM(line_total_after_discount) AS subtotal_after_discount,
        SUM(line_total - line_total_after_discount) AS total_discount_amount
    FROM order_items
    GROUP BY order_id
),

-- Final fact table
final AS (
    SELECT
        -- Keys
        o.order_id,
        o.customer_id,
        o.order_date_key,

        -- Customer context
        c.customer_name,
        c.customer_country,

        -- Order details
        o.order_date,
        o.raw_status,
        o.order_status,
        o.status_category,

        -- Financial metrics
        o.total_amount AS order_total_original,
        o.currency AS original_currency,
        o.total_amount_usd AS order_total_usd,
        o.order_size_category,

        -- Line item metrics
        COALESCE(ois.total_line_items, 0) AS total_line_items,
        COALESCE(ois.total_units, 0) AS total_units,
        COALESCE(ois.unique_products, 0) AS unique_products,
        COALESCE(ois.subtotal, 0) AS line_items_subtotal,
        COALESCE(ois.subtotal_after_discount, 0) AS line_items_after_discount,
        COALESCE(ois.total_discount_amount, 0) AS total_discount_amount,

        -- Calculated metrics
        CASE
            WHEN ois.total_units > 0 THEN o.total_amount_usd / ois.total_units
            ELSE 0
        END AS avg_unit_price_usd,

        CASE
            WHEN ois.subtotal > 0 THEN ois.total_discount_amount / ois.subtotal
            ELSE 0
        END AS discount_rate,

        -- Order flags
        CASE WHEN o.order_status = 'COMPLETED' THEN TRUE ELSE FALSE END AS is_completed,
        CASE WHEN o.order_status = 'CANCELLED' THEN TRUE ELSE FALSE END AS is_cancelled,
        CASE WHEN ois.total_discount_amount > 0 THEN TRUE ELSE FALSE END AS has_discount,

        -- Time metrics
        o.created_at AS order_created_at,

        -- Audit fields (gold layer standard)
        CURRENT_TIMESTAMP() AS gold_loaded_at,
        'sample_project' AS gold_source_system

    FROM orders o
    LEFT JOIN customers c ON o.customer_id = c.customer_id
    LEFT JOIN order_item_summary ois ON o.order_id = ois.order_id
)

SELECT * FROM final
```

## 6. Implementation Steps

1.  **Validation Phase:**
    - Verify `stg_orders` exists in Silver.
    - Compare `stg_orders` vs `int_orders_final_broken`.

2.  **Refactoring Phase:**
    - Modify `models/gold/fct_orders_broken.sql`.
    - Update `ref` to `stg_orders`.

3.  **Execution Phase:**
    - `dbt run --select fct_orders_broken`

4.  **Cleanup Phase:**
    - `dbt run --select int_orders_final_broken --full-refresh` (to drop or just delete files).
    - Remove `models/silver/int_*_broken.sql` files.

## 7. Validation Tests

### Row Count Check
```sql
SELECT
    (SELECT COUNT(*) FROM `johanesa-playground-326616.sample_silver.stg_orders`) as stg_count,
    (SELECT COUNT(*) FROM `johanesa-playground-326616.sample_silver.int_orders_final_broken`) as broken_count
```

### Data Integrity
Ensure `total_amount_usd` is calculated correctly in `stg_orders` (it uses the same logic as `int_orders_final_broken`).

## 8. Risk Assessment & Mitigation

- **Risk:** `stg_orders` might have subtly different logic for edge cases.
- **Mitigation:** The SQL analysis confirms logic parity. Validation queries will confirm data parity.
- **Rollback:** Revert changes to `fct_orders_broken.sql` using Git.

## 9. Success Criteria

- [ ] `fct_orders_broken` builds successfully using `stg_orders`.
- [ ] Data validation passes.
- [ ] Lineage graph shows direct connection from `stg_orders` to `fct_orders_broken`.

## 10. Next Steps

1.  **Approve PRD.**
2.  **Generate Migration Cookbook.**
3.  **Execute Migration.**
