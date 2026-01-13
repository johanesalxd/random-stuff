-- Bronze Layer: Customers
-- Complexity: LOW
-- Simple passthrough from source system

{{ config(
    materialized='view',
    tags=['bronze', 'customers']
) }}

-- Simulating raw data from source system
-- In production, this would be: SELECT * FROM source('crm', 'customers')

SELECT
    1 AS customer_id,
    'John' AS first_name,
    'Doe' AS last_name,
    'john.doe@example.com' AS email,
    'US' AS country_code,
    TIMESTAMP('2023-01-15 10:30:00') AS created_at,
    TIMESTAMP('2024-06-20 14:45:00') AS updated_at

UNION ALL

SELECT
    2 AS customer_id,
    'Jane' AS first_name,
    'Smith' AS last_name,
    'jane.smith@example.com' AS email,
    'UK' AS country_code,
    TIMESTAMP('2023-03-22 09:15:00') AS created_at,
    TIMESTAMP('2024-07-10 11:20:00') AS updated_at

UNION ALL

SELECT
    3 AS customer_id,
    'Bob' AS first_name,
    'Johnson' AS last_name,
    'bob.johnson@example.com' AS email,
    'CA' AS country_code,
    TIMESTAMP('2023-05-08 16:00:00') AS created_at,
    TIMESTAMP('2024-08-01 08:30:00') AS updated_at

UNION ALL

SELECT
    4 AS customer_id,
    'Alice' AS first_name,
    'Williams' AS last_name,
    'alice.w@example.com' AS email,
    'AU' AS country_code,
    TIMESTAMP('2023-07-12 12:45:00') AS created_at,
    TIMESTAMP('2024-08-15 17:00:00') AS updated_at

UNION ALL

SELECT
    5 AS customer_id,
    'Charlie' AS first_name,
    'Brown' AS last_name,
    'charlie.b@example.com' AS email,
    'DE' AS country_code,
    TIMESTAMP('2023-09-30 14:20:00') AS created_at,
    TIMESTAMP('2024-09-05 10:10:00') AS updated_at
