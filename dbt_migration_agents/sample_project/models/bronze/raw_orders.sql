-- Bronze Layer: Orders
-- Complexity: LOW
-- Raw order data with intentional duplicates for testing deduplication

{{ config(
    materialized='view',
    tags=['bronze', 'orders']
) }}

-- Simulating raw data with duplicates (common in source systems)
-- In production, this would be: SELECT * FROM source('ecommerce', 'orders')

SELECT
    1001 AS order_id,
    1 AS customer_id,
    TIMESTAMP('2024-01-10 09:30:00') AS order_date,
    'completed' AS status,
    150.00 AS total_amount,
    'USD' AS currency,
    TIMESTAMP('2024-01-10 09:30:00') AS created_at

UNION ALL

-- Duplicate row (for testing deduplication in silver)
SELECT
    1001 AS order_id,
    1 AS customer_id,
    TIMESTAMP('2024-01-10 09:30:00') AS order_date,
    'completed' AS status,
    150.00 AS total_amount,
    'USD' AS currency,
    TIMESTAMP('2024-01-10 09:31:00') AS created_at

UNION ALL

SELECT
    1002 AS order_id,
    2 AS customer_id,
    TIMESTAMP('2024-02-15 14:45:00') AS order_date,
    'pending' AS status,
    275.50 AS total_amount,
    'GBP' AS currency,
    TIMESTAMP('2024-02-15 14:45:00') AS created_at

UNION ALL

SELECT
    1003 AS order_id,
    1 AS customer_id,
    TIMESTAMP('2024-03-20 11:00:00') AS order_date,
    'shipped' AS status,
    89.99 AS total_amount,
    'USD' AS currency,
    TIMESTAMP('2024-03-20 11:00:00') AS created_at

UNION ALL

SELECT
    1004 AS order_id,
    3 AS customer_id,
    TIMESTAMP('2024-04-05 16:30:00') AS order_date,
    'cancelled' AS status,
    420.00 AS total_amount,
    'CAD' AS currency,
    TIMESTAMP('2024-04-05 16:30:00') AS created_at

UNION ALL

SELECT
    1005 AS order_id,
    4 AS customer_id,
    TIMESTAMP('2024-05-12 08:15:00') AS order_date,
    'completed' AS status,
    199.00 AS total_amount,
    'AUD' AS currency,
    TIMESTAMP('2024-05-12 08:15:00') AS created_at

UNION ALL

-- Another duplicate for testing
SELECT
    1005 AS order_id,
    4 AS customer_id,
    TIMESTAMP('2024-05-12 08:15:00') AS order_date,
    'completed' AS status,
    199.00 AS total_amount,
    'AUD' AS currency,
    TIMESTAMP('2024-05-12 08:16:00') AS created_at

UNION ALL

SELECT
    1006 AS order_id,
    5 AS customer_id,
    TIMESTAMP('2024-06-18 10:00:00') AS order_date,
    'processing' AS status,
    550.75 AS total_amount,
    'EUR' AS currency,
    TIMESTAMP('2024-06-18 10:00:00') AS created_at

UNION ALL

SELECT
    1007 AS order_id,
    2 AS customer_id,
    TIMESTAMP('2024-07-22 13:30:00') AS order_date,
    'completed' AS status,
    325.00 AS total_amount,
    'GBP' AS currency,
    TIMESTAMP('2024-07-22 13:30:00') AS created_at
