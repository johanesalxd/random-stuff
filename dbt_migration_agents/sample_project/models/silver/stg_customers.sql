-- Silver Layer: Customers
-- Complexity: LOW
-- Cleaned customer data with standardization

{{ config(
    materialized='table',
    tags=['silver', 'transformed', 'customers']
) }}

WITH source AS (
    SELECT *
    FROM {{ ref('raw_customers') }}
),

cleaned AS (
    SELECT
        customer_id,
        TRIM(UPPER(first_name)) AS first_name,
        TRIM(UPPER(last_name)) AS last_name,
        LOWER(TRIM(email)) AS email,
        country_code,
        created_at,
        updated_at,

        -- Derived fields
        CONCAT(TRIM(first_name), ' ', TRIM(last_name)) AS full_name,

        -- Record metadata
        CURRENT_TIMESTAMP() AS _loaded_at

    FROM source
)

SELECT * FROM cleaned
