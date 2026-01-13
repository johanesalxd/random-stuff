-- Gold Layer: Product Dimension
-- Complexity: LOW
-- Curated product dimension

{{ config(
    materialized='table',
    tags=['gold', 'curated', 'dimension', 'products']
) }}

WITH products AS (
    SELECT *
    FROM {{ ref('stg_products') }}
),

final AS (
    SELECT
        product_id,
        product_name,
        category_code,
        category_name,
        price,
        price_tier,
        stock_quantity,
        stock_status,
        is_active,

        -- Product status description
        CASE
            WHEN NOT is_active THEN 'DISCONTINUED'
            WHEN stock_quantity = 0 THEN 'OUT_OF_STOCK'
            ELSE 'AVAILABLE'
        END AS availability_status,

        created_at AS product_created_at,

        -- Audit fields (gold layer standard)
        CURRENT_TIMESTAMP() AS gold_loaded_at,
        'sample_project' AS gold_source_system

    FROM products
)

SELECT * FROM final
