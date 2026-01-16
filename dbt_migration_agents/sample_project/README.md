# Sample DBT Project

A minimal DBT project demonstrating the Bronze/Silver/Gold medallion architecture for testing the DBT Migration Agents framework.

## Naming Convention

This project uses **folder-based naming** instead of prefixes:

- Models are named after the entity they represent (e.g., `customers`, `orders`)
- The folder determines the layer (bronze/silver/gold)
- DBT's `ref()` resolves models based on the folder hierarchy
- Gold layer retains standard `dim_` and `fct_` prefixes (industry convention for dimensions and facts)

This approach keeps model names simple and lets the directory structure communicate the layer.

## Project Structure

```
sample_project/
├── dbt_project.yml           # DBT project configuration
├── profiles.yml.example      # BigQuery connection template
├── models/
│   ├── bronze/               # Raw source data (3 models)
│   │   ├── _bronze_schema.yml
│   │   ├── customers.sql
│   │   ├── orders.sql
│   │   └── products.sql
│   ├── silver/               # Transformed data (4 models + 3 broken)
│   │   ├── _silver_schema.yml
│   │   ├── customers.sql
│   │   ├── orders.sql
│   │   ├── products.sql
│   │   ├── order_items.sql
│   │   ├── int_orders_cleaned_broken.sql   # Demo: unnecessary intermediate
│   │   ├── int_orders_enriched_broken.sql  # Demo: unnecessary intermediate
│   │   └── int_orders_final_broken.sql     # Demo: unnecessary intermediate
│   └── gold/                 # Curated business data (3 models + 1 broken)
│       ├── _gold_schema.yml
│       ├── dim_customers.sql
│       ├── dim_products.sql
│       ├── fct_orders.sql
│       └── fct_orders_broken.sql           # Demo: reads from intermediate chain
└── seeds/
    └── country_codes.csv     # Reference data
```

## Layer Descriptions

### Bronze Layer (Raw)

Raw data ingestion with minimal transformation. Models are materialized as views.

| Model | Description | Complexity |
|-------|-------------|------------|
| `customers` | Customer records from source | LOW |
| `orders` | Order records (includes duplicates for testing) | LOW |
| `products` | Product catalog | LOW |

### Silver Layer (Transformed)

Cleaned, deduplicated, and enriched data. Models are materialized as tables.

| Model | Description | Complexity |
|-------|-------------|------------|
| `customers` | Cleaned customer data with full name | LOW |
| `orders` | Deduplicated orders with status mapping and currency normalization | MEDIUM |
| `products` | Products with category and stock enrichment | LOW-MEDIUM |
| `order_items` | Order line items with calculations | MEDIUM |

### Gold Layer (Curated)

Business-ready data for analytics and reporting. Models are materialized as tables.

| Model | Description | Complexity |
|-------|-------------|------------|
| `dim_customers` | Customer dimension with order metrics and segmentation | MEDIUM |
| `dim_products` | Product dimension with availability status | LOW |
| `fct_orders` | Order fact table with full metrics | HIGH |

## Business Logic Examples

### Status Mapping (silver/orders.sql)

Demonstrates CASE statement complexity:
- Raw status codes mapped to standardized statuses
- Status categories for grouping
- Currency conversion to USD

### Deduplication (silver/orders.sql)

Demonstrates ROW_NUMBER pattern:
```sql
ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY created_at ASC) AS row_num
```

### Aggregations (gold/dim_customers.sql)

Demonstrates customer metrics:
- Total orders and revenue
- Customer segmentation (PROSPECT, NEW, ACTIVE, LOYAL)
- Value tier classification

### Multi-Source Joins (gold/fct_orders.sql)

Demonstrates complex joins:
- Orders joined with customers for context
- Aggregated order items for line-level metrics
- Calculated fields for business insights

## Setup Instructions

**🚀 QUICK START**: To set up this project for testing the agents, follow the **[Quick Start Demo](../README.md#quick-start-demo)** in the root directory.

### Manual Setup (Reference Only)

If you cannot use the quick start script:

1. Copy profiles template:
   ```bash
   cp profiles.yml.example ~/.dbt/profiles.yml
   ```

2. Update the profiles.yml with your GCP project and credentials.

3. Verify the connection:
   ```bash
   dbt debug
   ```

4. Run the models:
   ```bash
   dbt run
   ```

5. Run tests:
   ```bash
   dbt test
   ```

## Using with Migration Agents

This sample project can be used to test the DBT Migration Agents framework:

1. Update `config/migration_config.yaml` with your GCP projects.

2. Run lineage analysis on a gold model:
   ```
   /migrate-cookbook-generator models/gold/dim_customers.sql my-project.my_dataset
   ```

3. Review the generated PRD and cookbook.

4. Execute the migration following the cookbook steps.

## Data Model

```
Bronze                  Silver                      Gold
------                  ------                      ----
customers ------------> customers ---------------> dim_customers
                                    \              /
orders ---------------> orders --------+-------> fct_orders
                              |        |
products -------------> products ------+
                              |
                        order_items
```

## Broken Scenarios (Migration Demo)

The project includes "broken" models that demonstrate the migration workflow. These models create unnecessary complexity that the migration framework helps consolidate.

### Broken Pattern (4 hops - TOO MANY INTERMEDIATES)

```
raw_orders
    |
    v
int_orders_cleaned_broken     (Step 1: Dedup only)
    |
    v
int_orders_enriched_broken    (Step 2: Status mapping only)
    |
    v
int_orders_final_broken       (Step 3: Currency conversion only)
    |
    v
fct_orders_broken             (Gold - reads from chain end)
```

**Problem**: Each transformation is materialized as a separate table, creating:
- 4 intermediate tables to maintain
- Complex lineage (4 hops from Bronze to Gold)
- Increased compute costs
- Harder debugging

### Correct Pattern (2 hops - CONSOLIDATED)

```
raw_orders
    |
    v
stg_orders                    (All transformations in one step)
    |
    v
fct_orders                    (Gold - reads from consolidated Silver)
```

**Solution**: Consolidate all intermediate steps into a single Silver model.

### Broken Model Files

| Model | Layer | Purpose |
|-------|-------|---------|
| `int_orders_cleaned_broken.sql` | Silver | Step 1: Deduplication only |
| `int_orders_enriched_broken.sql` | Silver | Step 2: Status mapping only |
| `int_orders_final_broken.sql` | Silver | Step 3: Currency conversion only |
| `fct_orders_broken.sql` | Gold | Reads from intermediate chain |

### How to Use for Testing

1. Run migration generator on the broken gold model:
   ```
   /migrate-cookbook-generator models/gold/fct_orders_broken.sql my-project.my_dataset
   ```

2. The framework will:
   - Analyze the intermediate chain dependency
   - Generate a PRD to consolidate into stg_orders pattern
   - Create a migration cookbook with step-by-step instructions

3. After migration, validate that both produce equivalent data:
   - `fct_orders_broken` (4 hops via int_orders_* chain)
   - `fct_orders` (2 hops via stg_orders)

4. The migration demonstrates layer consolidation without data loss.

---

## Notes

- Bronze models use simulated data via SELECT...UNION ALL statements
- Silver models demonstrate common transformation patterns
- Gold models include standard audit fields (gold_loaded_at, gold_source_system)
- The `order_items` model simulates line items not present in bronze layer
- Model names are simple; the folder structure indicates the layer
- Broken models (`*_broken.sql`) are for migration demo purposes only
