-- Silver Intermediate: Basic Cleaning (BROKEN PATTERN)
-- Complexity: LOW
-- Part of BROKEN pattern - unnecessary intermediate step
-- ISSUE: This is step 1 of 3 unnecessary intermediate Silver models
-- CORRECT: Consolidate all steps into single stg_orders.sql

{{ config(
    materialized='table',
    tags=['silver', 'intermediate', 'broken', 'demo']
) }}

-- BROKEN PATTERN EXPLANATION:
-- This model chain (int_orders_cleaned -> int_orders_enriched -> int_orders_final)
-- creates unnecessary complexity. The migration goal is to consolidate these
-- into a single stg_orders model that does all transformations in one step.

WITH source AS (
    SELECT *
    FROM {{ ref('raw_orders') }}
),

-- Step 1: Basic cleaning and deduplication only
-- Note: This SHOULD be combined with status mapping and currency conversion
cleaned AS (
    SELECT
        order_id,
        customer_id,
        order_date,
        status,
        total_amount,
        currency,
        created_at,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY created_at ASC
        ) AS row_num
    FROM source
)

SELECT
    order_id,
    customer_id,
    order_date,
    status,
    total_amount,
    currency,
    created_at
FROM cleaned
WHERE row_num = 1
