-- Gold Layer: Orders Fact Table
-- Complexity: HIGH
-- Complete order facts with multi-source joins and aggregations

{{ config(
    materialized='table',
    tags=['gold', 'curated', 'fact', 'orders']
) }}

WITH orders AS (
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
