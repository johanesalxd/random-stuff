-- Silver Layer: Orders
-- Complexity: MEDIUM
-- Deduplicated orders with status mapping and business logic

{{ config(
    materialized='table',
    tags=['silver', 'transformed', 'orders']
) }}

WITH source AS (
    SELECT *
    FROM {{ ref('raw_orders') }}
),

-- Deduplication: Keep the earliest record per order_id
deduplicated AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY created_at ASC
        ) AS row_num
    FROM source
),

filtered AS (
    SELECT *
    FROM deduplicated
    WHERE row_num = 1
),

-- Apply business logic and status mapping
transformed AS (
    SELECT
        order_id,
        customer_id,
        order_date,
        DATE(order_date) AS order_date_key,

        -- Status mapping with CASE statements (MEDIUM complexity indicator)
        status AS raw_status,
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

        -- Financial fields
        total_amount,
        currency,

        -- Currency conversion to USD (simplified)
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

    FROM filtered
)

SELECT * FROM transformed
