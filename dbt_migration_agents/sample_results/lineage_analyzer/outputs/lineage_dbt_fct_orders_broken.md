# Lineage Report: fct_orders_broken

Generated: 2026-01-16 21:41:34

## Summary

- **Total Levels:** 4
- **Total Nodes:** 11

### Nodes by Type

- **Model:** 11

## Lineage Tree View

Visual representation of the complete dependency hierarchy (no limits):

```
└── fct_orders_broken
    ├── int_orders_final_broken
    │   └── int_orders_enriched_broken
    │       └── int_orders_cleaned_broken
    │           └── raw_orders
    ├── stg_customers
    │   └── raw_customers
    └── stg_order_items
        ├── stg_orders
        └── stg_products
            └── raw_products
```

## Dependency Tree

### Level 0: Target Model

#### MODEL (1)

- **fct_orders_broken**
  - Path: `models/gold/fct_orders_broken.sql`
  - Location: `sample-project.sample_gold`
  - **Depends on:** int_orders_final_broken (Level 1), stg_customers (Level 1), stg_order_items (Level 1)

### Level 1: Upstream Dependencies

#### MODEL (3)

- **int_orders_final_broken**
  - Path: `models/silver/int_orders_final_broken.sql`
  - Location: `sample-project.sample_silver`
  - **Used by:** fct_orders_broken (Level 0)
  - **Depends on:** int_orders_enriched_broken (Level 2)

- **stg_customers**
  - Path: `models/silver/stg_customers.sql`
  - Location: `sample-project.sample_silver`
  - **Used by:** fct_orders_broken (Level 0)
  - **Depends on:** raw_customers (Level 2)

- **stg_order_items**
  - Path: `models/silver/stg_order_items.sql`
  - Location: `sample-project.sample_silver`
  - **Used by:** fct_orders_broken (Level 0)
  - **Depends on:** stg_orders (Level 2), stg_products (Level 2)

### Level 2: Upstream Dependencies

#### MODEL (4)

- **int_orders_enriched_broken**
  - Path: `models/silver/int_orders_enriched_broken.sql`
  - Location: `sample-project.sample_silver`
  - **Used by:** int_orders_final_broken (Level 1)
  - **Depends on:** int_orders_cleaned_broken (Level 3)

- **raw_customers**
  - Path: `models/bronze/raw_customers.sql`
  - Location: `sample-project.sample_bronze`
  - **Used by:** stg_customers (Level 1)

- **stg_orders**
  - Path: `models/silver/stg_orders.sql`
  - Location: `sample-project.sample_silver`
  - **Used by:** stg_order_items (Level 1)
  - **Depends on:** raw_orders (Level 3)

- **stg_products**
  - Path: `models/silver/stg_products.sql`
  - Location: `sample-project.sample_silver`
  - **Used by:** stg_order_items (Level 1)
  - **Depends on:** raw_products (Level 3)

### Level 3: Upstream Dependencies

#### MODEL (3)

- **int_orders_cleaned_broken**
  - Path: `models/silver/int_orders_cleaned_broken.sql`
  - Location: `sample-project.sample_silver`
  - **Used by:** int_orders_enriched_broken (Level 2)
  - **Depends on:** raw_orders (Level 3)

- **raw_orders**
  - Path: `models/bronze/raw_orders.sql`
  - Location: `sample-project.sample_bronze`
  - **Used by:** int_orders_cleaned_broken (Level 3), stg_orders (Level 2)

- **raw_products**
  - Path: `models/bronze/raw_products.sql`
  - Location: `sample-project.sample_bronze`
  - **Used by:** stg_products (Level 2)

## Most Upstream Sources

