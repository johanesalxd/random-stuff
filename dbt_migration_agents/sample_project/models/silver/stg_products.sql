-- Silver Layer: Products
-- Complexity: LOW-MEDIUM
-- Products with category enrichment

{{ config(
    materialized='table',
    tags=['silver', 'transformed', 'products']
) }}

WITH source AS (
    SELECT *
    FROM {{ ref('raw_products') }}
),

transformed AS (
    SELECT
        product_id,
        product_name,
        category_code,

        -- Category name mapping
        CASE category_code
            WHEN 'ELECTRONICS' THEN 'Electronics & Gadgets'
            WHEN 'OFFICE' THEN 'Office Supplies'
            WHEN 'HOME' THEN 'Home & Living'
            ELSE 'Other'
        END AS category_name,

        price,
        stock_quantity,
        is_active,

        -- Stock status
        CASE
            WHEN stock_quantity = 0 THEN 'OUT_OF_STOCK'
            WHEN stock_quantity < 50 THEN 'LOW_STOCK'
            WHEN stock_quantity < 200 THEN 'IN_STOCK'
            ELSE 'WELL_STOCKED'
        END AS stock_status,

        -- Price tier
        CASE
            WHEN price < 20 THEN 'BUDGET'
            WHEN price BETWEEN 20 AND 50 THEN 'MID_RANGE'
            WHEN price BETWEEN 50 AND 100 THEN 'PREMIUM'
            ELSE 'LUXURY'
        END AS price_tier,

        created_at,

        -- Record metadata
        CURRENT_TIMESTAMP() AS _loaded_at

    FROM source
)

SELECT * FROM transformed
