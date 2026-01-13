-- Silver Intermediate: Currency Conversion (BROKEN PATTERN)
-- Complexity: LOW
-- Part of BROKEN pattern - unnecessary intermediate step
-- ISSUE: This is step 3 of 3 unnecessary intermediate Silver models
-- CORRECT: Consolidate all steps into single stg_orders.sql

{{ config(
    materialized='table',
    tags=['silver', 'intermediate', 'broken', 'demo']
) }}

-- BROKEN PATTERN EXPLANATION:
-- This is the final step in the unnecessary intermediate chain.
-- It reads from int_orders_enriched_broken and adds currency conversion.
-- The Gold layer (fct_orders_broken) reads from this model.
-- MIGRATION GOAL: Bypass this chain and read from consolidated stg_orders.sql

WITH source AS (
    SELECT *
    FROM {{ ref('int_orders_enriched_broken') }}
),

-- Step 3: Currency conversion and final fields
-- Note: This SHOULD be combined with deduplication and status mapping
final AS (
    SELECT
        order_id,
        customer_id,
        order_date,
        DATE(order_date) AS order_date_key,
        raw_status,
        order_status,
        status_category,
        total_amount,
        currency,

        -- Currency conversion to USD (same logic as stg_orders)
        CASE currency
            WHEN 'USD' THEN total_amount
            WHEN 'GBP' THEN total_amount * 1.27
            WHEN 'EUR' THEN total_amount * 1.08
            WHEN 'CAD' THEN total_amount * 0.74
            WHEN 'AUD' THEN total_amount * 0.65
            ELSE total_amount
        END AS total_amount_usd,

        -- Order size classification
        CASE
            WHEN total_amount < 50 THEN 'SMALL'
            WHEN total_amount BETWEEN 50 AND 200 THEN 'MEDIUM'
            WHEN total_amount BETWEEN 200 AND 500 THEN 'LARGE'
            ELSE 'ENTERPRISE'
        END AS order_size_category,

        created_at,

        -- Record metadata
        CURRENT_TIMESTAMP() AS _loaded_at

    FROM source
)

SELECT * FROM final
