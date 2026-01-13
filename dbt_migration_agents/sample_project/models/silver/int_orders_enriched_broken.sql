-- Silver Intermediate: Status Mapping (BROKEN PATTERN)
-- Complexity: LOW
-- Part of BROKEN pattern - unnecessary intermediate step
-- ISSUE: This is step 2 of 3 unnecessary intermediate Silver models
-- CORRECT: Consolidate all steps into single stg_orders.sql

{{ config(
    materialized='table',
    tags=['silver', 'intermediate', 'broken', 'demo']
) }}

-- BROKEN PATTERN EXPLANATION:
-- This step only adds status mapping. It reads from int_orders_cleaned_broken
-- and passes data to int_orders_final_broken. This creates unnecessary
-- table materialization and lineage complexity.
-- MIGRATION GOAL: Combine into consolidated stg_orders.sql

WITH source AS (
    SELECT *
    FROM {{ ref('int_orders_cleaned_broken') }}
),

-- Step 2: Status mapping only
-- Note: This SHOULD be combined with deduplication and currency conversion
enriched AS (
    SELECT
        order_id,
        customer_id,
        order_date,
        status AS raw_status,

        -- Status mapping (same logic as stg_orders, but in separate step)
        CASE
            WHEN status = 'completed' THEN 'COMPLETED'
            WHEN status = 'shipped' THEN 'IN_TRANSIT'
            WHEN status = 'processing' THEN 'PROCESSING'
            WHEN status = 'pending' THEN 'PENDING'
            WHEN status = 'cancelled' THEN 'CANCELLED'
            WHEN status = 'refunded' THEN 'REFUNDED'
            ELSE 'UNKNOWN'
        END AS order_status,

        -- Status category grouping
        CASE
            WHEN status IN ('completed', 'shipped') THEN 'FULFILLED'
            WHEN status IN ('processing', 'pending') THEN 'IN_PROGRESS'
            WHEN status IN ('cancelled', 'refunded') THEN 'CANCELLED'
            ELSE 'OTHER'
        END AS status_category,

        total_amount,
        currency,
        created_at

    FROM source
)

SELECT * FROM enriched
