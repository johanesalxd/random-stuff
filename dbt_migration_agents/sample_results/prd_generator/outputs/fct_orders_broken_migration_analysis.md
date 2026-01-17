# Migration Analysis: fct_orders_broken

**Generated:** 2026-01-16
**Target Model:** `fct_orders_broken`
**Target Layer:** Gold

## 1. Executive Summary

The analysis of `fct_orders_broken` reveals a significant refactoring opportunity. The current model relies on a fragmented chain of intermediate Silver models (`int_orders_cleaned_broken` → `int_orders_enriched_broken` → `int_orders_final_broken`) which introduces unnecessary complexity and lineage depth.

A consolidated Silver model, `stg_orders`, already exists and implements the superset of logic found in the broken chain. The primary migration objective is to repoint the Gold model to use `stg_orders` and deprecate the intermediate chain.

- **Total Dependencies:** 11 nodes (including broken chain)
- **Direct Dependencies:** 3 (`int_orders_final_broken`, `stg_customers`, `stg_order_items`)
- **Key Recommendation:** Refactor to use `stg_orders` directly.

## 2. Dependency Inventory

### Silver Layer (To Be Used)
| Model | Type | Source | Status |
|-------|------|--------|--------|
| `stg_orders` | Table | `raw_orders` | **EXISTING & CORRECT** |
| `stg_customers` | Table | `raw_customers` | **EXISTING & CORRECT** |
| `stg_order_items` | Table | `stg_orders`, `stg_products` | **EXISTING & CORRECT** |
| `stg_products` | Table | `raw_products` | **EXISTING & CORRECT** |

### Silver Layer (To Be Deprecated)
| Model | Type | Source | Status |
|-------|------|--------|--------|
| `int_orders_final_broken` | Table | `int_orders_enriched_broken` | **DEPRECATE** |
| `int_orders_enriched_broken` | Table | `int_orders_cleaned_broken` | **DEPRECATE** |
| `int_orders_cleaned_broken` | Table | `raw_orders` | **DEPRECATE** |

### Bronze Layer (Sources)
- `raw_orders`
- `raw_customers`
- `raw_products`

## 3. Transformation Analysis

### Target Model: `fct_orders_broken`
- **Current Logic:** Joins `int_orders_final_broken` with `stg_customers` and `stg_order_items` (via aggregate `order_item_summary`).
- **Refactoring:** Replace `int_orders_final_broken` with `stg_orders`.

### Comparison: Broken Chain vs. `stg_orders`

| Feature | Broken Chain (`int_*_broken`) | Consolidated `stg_orders` | Match? |
|---------|-------------------------------|---------------------------|--------|
| **Deduplication** | `int_orders_cleaned_broken` (Row Num) | Included | ✅ Yes |
| **Status Mapping** | `int_orders_enriched_broken` (CASE) | Included (Identical) | ✅ Yes |
| **Status Grouping** | `int_orders_enriched_broken` (CASE) | Included (Identical) | ✅ Yes |
| **Currency Conv** | `int_orders_final_broken` (CASE) | Included (Identical) | ✅ Yes |
| **Size Category** | `int_orders_final_broken` (CASE) | Included (Identical) | ✅ Yes |

**Conclusion:** `stg_orders` is a functional superset of the broken chain and is the correct source for the Gold layer.

### Other Dependencies
- **`stg_customers`**: Standard cleaning (Trim/Upper/Lower). Complexity: LOW.
- **`stg_order_items`**: Joins orders and products, calculates line totals and discounts. Complexity: MEDIUM.
- **`stg_products`**: Category mapping, price tiering, stock status. Complexity: MEDIUM.

## 4. Migration Recommendations

### Priority 1: Foundation (Silver Layer Verification)
Ensure `stg_orders`, `stg_customers`, and `stg_products` are deployed and validated in the Silver layer (Project: `johanesa-playground-326616`).
- **Action:** Verify `stg_orders` row counts match `int_orders_final_broken` (should be identical or better due to deduplication).

### Priority 2: Refactor Gold Model
Refactor `fct_orders_broken.sql`:
1.  **Change Source:** Replace `{{ ref('int_orders_final_broken') }}` with `{{ ref('stg_orders') }}`.
2.  **Verify Columns:** Ensure all columns used from `int_orders_final_broken` exist in `stg_orders` (Analysis confirms they do).
3.  **Rename:** Ideally rename `fct_orders_broken` to `fct_orders` (or similar) as part of the fix, but strictly speaking we are migrating the *logic* first.

### Priority 3: Cleanup
Deprecate and remove the `int_*_broken` models to clean up the lineage.

## 5. Implementation Plan

1.  **Validation Phase:** Validate data parity between `int_orders_final_broken` and `stg_orders`.
2.  **Code Refactor:** Update `fct_orders_broken` SQL to point to `stg_orders`.
3.  **Testing:** Run `dbt test` on the new model.
4.  **Deployment:** Deploy to Gold layer.
5.  **Post-Migration:** Archive `int_*_broken` models.

## 6. Risk Assessment
- **Risk:** `stg_orders` might have slight logic differences I missed.
- **Mitigation:** The comparison shows identical logic structure. Data validation (row count/checksum) will confirm.
- **Severity:** Low.

