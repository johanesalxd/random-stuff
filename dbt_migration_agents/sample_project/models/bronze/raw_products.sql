-- Bronze Layer: Products
-- Complexity: LOW
-- Product catalog from source system

{{ config(
    materialized='view',
    tags=['bronze', 'products']
) }}

-- Simulating raw data from source system
-- In production, this would be: SELECT * FROM source('inventory', 'products')

SELECT
    'PROD-001' AS product_id,
    'Wireless Headphones' AS product_name,
    'ELECTRONICS' AS category_code,
    79.99 AS price,
    150 AS stock_quantity,
    TRUE AS is_active,
    TIMESTAMP('2023-01-01 00:00:00') AS created_at

UNION ALL

SELECT
    'PROD-002' AS product_id,
    'USB-C Cable' AS product_name,
    'ELECTRONICS' AS category_code,
    12.99 AS price,
    500 AS stock_quantity,
    TRUE AS is_active,
    TIMESTAMP('2023-02-15 00:00:00') AS created_at

UNION ALL

SELECT
    'PROD-003' AS product_id,
    'Laptop Stand' AS product_name,
    'OFFICE' AS category_code,
    45.00 AS price,
    75 AS stock_quantity,
    TRUE AS is_active,
    TIMESTAMP('2023-03-10 00:00:00') AS created_at

UNION ALL

SELECT
    'PROD-004' AS product_id,
    'Ergonomic Mouse' AS product_name,
    'OFFICE' AS category_code,
    35.00 AS price,
    200 AS stock_quantity,
    TRUE AS is_active,
    TIMESTAMP('2023-04-20 00:00:00') AS created_at

UNION ALL

SELECT
    'PROD-005' AS product_id,
    'Coffee Mug' AS product_name,
    'HOME' AS category_code,
    15.00 AS price,
    1000 AS stock_quantity,
    TRUE AS is_active,
    TIMESTAMP('2023-05-05 00:00:00') AS created_at

UNION ALL

SELECT
    'PROD-006' AS product_id,
    'Desk Lamp' AS product_name,
    'HOME' AS category_code,
    55.00 AS price,
    80 AS stock_quantity,
    FALSE AS is_active,
    TIMESTAMP('2023-06-01 00:00:00') AS created_at

UNION ALL

SELECT
    'PROD-007' AS product_id,
    'Notebook Set' AS product_name,
    'OFFICE' AS category_code,
    22.00 AS price,
    300 AS stock_quantity,
    TRUE AS is_active,
    TIMESTAMP('2023-07-15 00:00:00') AS created_at
