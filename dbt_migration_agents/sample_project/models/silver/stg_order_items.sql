-- Silver Layer: Order Items
-- Complexity: MEDIUM
-- Order line items with calculations (simulated join between orders and products)

{{ config(
    materialized='table',
    tags=['silver', 'transformed', 'order_items']
) }}

-- Simulating order items (line items for each order)
-- In production, this would join bronze order_items with orders and products

WITH order_items_raw AS (
    -- Simulated order line items
    SELECT 1 AS line_id, 1001 AS order_id, 'PROD-001' AS product_id, 1 AS quantity, 79.99 AS unit_price UNION ALL
    SELECT 2, 1001, 'PROD-002', 2, 12.99 UNION ALL
    SELECT 3, 1002, 'PROD-003', 1, 45.00 UNION ALL
    SELECT 4, 1002, 'PROD-004', 2, 35.00 UNION ALL
    SELECT 5, 1002, 'PROD-005', 3, 15.00 UNION ALL
    SELECT 6, 1003, 'PROD-002', 3, 12.99 UNION ALL
    SELECT 7, 1003, 'PROD-007', 2, 22.00 UNION ALL
    SELECT 8, 1004, 'PROD-001', 2, 79.99 UNION ALL
    SELECT 9, 1004, 'PROD-003', 3, 45.00 UNION ALL
    SELECT 10, 1004, 'PROD-006', 1, 55.00 UNION ALL
    SELECT 11, 1005, 'PROD-004', 2, 35.00 UNION ALL
    SELECT 12, 1005, 'PROD-005', 5, 15.00 UNION ALL
    SELECT 13, 1006, 'PROD-001', 3, 79.99 UNION ALL
    SELECT 14, 1006, 'PROD-003', 2, 45.00 UNION ALL
    SELECT 15, 1006, 'PROD-004', 2, 35.00 UNION ALL
    SELECT 16, 1007, 'PROD-002', 5, 12.99 UNION ALL
    SELECT 17, 1007, 'PROD-007', 4, 22.00 UNION ALL
    SELECT 18, 1007, 'PROD-005', 6, 15.00
),

orders AS (
    SELECT *
    FROM {{ ref('stg_orders') }}
),

products AS (
    SELECT *
    FROM {{ ref('stg_products') }}
),

enriched AS (
    SELECT
        oi.line_id,
        oi.order_id,
        o.customer_id,
        o.order_date,
        o.order_status,

        oi.product_id,
        p.product_name,
        p.category_name,

        oi.quantity,
        oi.unit_price,

        -- Calculated fields
        oi.quantity * oi.unit_price AS line_total,

        -- Discount logic (10% off for 3+ items)
        CASE
            WHEN oi.quantity >= 3 THEN 0.10
            ELSE 0.00
        END AS discount_rate,

        CASE
            WHEN oi.quantity >= 3 THEN oi.quantity * oi.unit_price * 0.90
            ELSE oi.quantity * oi.unit_price
        END AS line_total_after_discount,

        -- Record metadata
        CURRENT_TIMESTAMP() AS _loaded_at

    FROM order_items_raw oi
    LEFT JOIN orders o ON oi.order_id = o.order_id
    LEFT JOIN products p ON oi.product_id = p.product_id
)

SELECT * FROM enriched
