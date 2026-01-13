-- Gold Layer: Customer Dimension
-- Complexity: MEDIUM
-- Curated customer dimension with aggregated metrics

{{ config(
    materialized='table',
    tags=['gold', 'curated', 'dimension', 'customers']
) }}

WITH customers AS (
    SELECT *
    FROM {{ ref('stg_customers') }}
),

orders AS (
    SELECT *
    FROM {{ ref('stg_orders') }}
),

order_items AS (
    SELECT *
    FROM {{ ref('stg_order_items') }}
),

-- Customer order metrics
customer_orders AS (
    SELECT
        customer_id,
        COUNT(DISTINCT order_id) AS total_orders,
        SUM(total_amount_usd) AS total_revenue_usd,
        AVG(total_amount_usd) AS avg_order_value_usd,
        MIN(order_date) AS first_order_date,
        MAX(order_date) AS last_order_date,
        COUNT(DISTINCT CASE WHEN order_status = 'COMPLETED' THEN order_id END) AS completed_orders
    FROM orders
    GROUP BY customer_id
),

-- Customer segmentation
final AS (
    SELECT
        c.customer_id,
        c.first_name,
        c.last_name,
        c.full_name,
        c.email,
        c.country_code,

        -- Country name from seed (simplified inline for demo)
        CASE c.country_code
            WHEN 'US' THEN 'United States'
            WHEN 'UK' THEN 'United Kingdom'
            WHEN 'CA' THEN 'Canada'
            WHEN 'AU' THEN 'Australia'
            WHEN 'DE' THEN 'Germany'
            ELSE 'Other'
        END AS country_name,

        -- Order metrics
        COALESCE(co.total_orders, 0) AS total_orders,
        COALESCE(co.total_revenue_usd, 0) AS lifetime_value_usd,
        COALESCE(co.avg_order_value_usd, 0) AS avg_order_value_usd,
        COALESCE(co.completed_orders, 0) AS completed_orders,
        co.first_order_date,
        co.last_order_date,

        -- Customer segment
        CASE
            WHEN co.total_orders IS NULL THEN 'PROSPECT'
            WHEN co.total_orders = 1 THEN 'NEW'
            WHEN co.total_orders BETWEEN 2 AND 5 THEN 'ACTIVE'
            WHEN co.total_orders > 5 THEN 'LOYAL'
            ELSE 'UNKNOWN'
        END AS customer_segment,

        -- Value tier
        CASE
            WHEN COALESCE(co.total_revenue_usd, 0) = 0 THEN 'NO_PURCHASE'
            WHEN co.total_revenue_usd < 100 THEN 'LOW_VALUE'
            WHEN co.total_revenue_usd BETWEEN 100 AND 500 THEN 'MEDIUM_VALUE'
            WHEN co.total_revenue_usd > 500 THEN 'HIGH_VALUE'
            ELSE 'UNKNOWN'
        END AS value_tier,

        -- Timestamps
        c.created_at AS customer_created_at,
        c.updated_at AS customer_updated_at,

        -- Audit fields (gold layer standard)
        CURRENT_TIMESTAMP() AS gold_loaded_at,
        'sample_project' AS gold_source_system

    FROM customers c
    LEFT JOIN customer_orders co ON c.customer_id = co.customer_id
)

SELECT * FROM final
