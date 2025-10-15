# BigQuery Data Science Agent: Example Prompts

This document provides a set of example prompts for the BigQuery Data Science Agent, designed to be used with the `your-project-id.thelook_ecommerce` dataset and BigFrames. The prompts are categorized by difficulty, from simple one-shot questions to complex, multi-step analytical tasks.

---

## Level 1: One-Shot Prompts (Simple)

These prompts are straightforward and can typically be answered in a single step. They are good for demonstrating the basic capabilities of the agent.

**1. Basic Data Exploration**
*   **Prompt:** "Show me the first 5 rows of the `users` table."
*   **Purpose:** Demonstrates the ability to read and display data from a table.

**2. Simple Calculation**
*   **Prompt:** "What is the total number of products in the `products` table?"
*   **Purpose:** Shows the agent can perform a simple aggregation (count) on a table.

**3. Basic Filtering**
*   **Prompt:** "How many users are from 'California'?"
*   **Purpose:** Demonstrates the ability to filter data based on a specific condition.

**4. Simple Join and Display**
*   **Prompt:** "Show me the names of the products in order `12345`."
*   **Purpose:** Requires a simple join between `order_items` and `products` and then filtering by `order_id`.

---

## Level 2: Multi-Step Prompts (Intermediate)

These prompts require a few steps to answer, such as joining multiple tables or performing more complex calculations.

**5. Sales Analysis by Category**
*   **Prompt:** "What are the top 5 best-selling product categories by total sales revenue?"
*   **Purpose:** This requires the agent to:
    1.  Join `order_items` and `products`.
    2.  Group by `category`.
    3.  Sum the `sale_price`.
    4.  Order the results and take the top 5.

**6. User Demographics Analysis**
*   **Prompt:** "Plot the distribution of user ages."
*   **Purpose:** This demonstrates the agent's ability to:
    1.  Read the `age` column from the `users` table.
    2.  Generate a histogram to visualize the age distribution.

**7. Shipping and Delivery Analysis**
*   **Prompt:** "What is the average shipping time for orders? Calculate the time difference between `created_at` and `shipped_at` in the `orders` table."
*   **Purpose:** This requires the agent to:
    1.  Calculate the time difference between two timestamp columns.
    2.  Compute the average of that difference.

**8. Inventory Management**
*   **Prompt:** "Which 5 products have been in inventory the longest without being sold? Use the `created_at` and `sold_at` columns in the `inventory_items` table."
*   **Purpose:** This requires the agent to:
    1.  Filter for items that are not yet sold (`sold_at` is NULL).
    2.  Calculate the time difference between now and `created_at`.
    3.  Find the top 5 longest durations.

---

## Level 3: Complex, Multi-Step Prompts (Advanced)

These prompts are more open-ended and require a more sophisticated plan to answer. They are excellent for showcasing the agent's ability to reason and break down a problem.

**9. Customer Lifetime Value (CLV) Analysis**
*   **Prompt:** "Calculate the Customer Lifetime Value (CLV) for our top 100 customers. For simplicity, define CLV as the total revenue generated from each customer. Then, plot the distribution of CLV for these top customers."
*   **Purpose:** This is a more advanced analysis that requires the agent to:
    1.  Join `users` and `order_items`.
    2.  Group by `user_id` and sum the `sale_price` to get total revenue per customer.
    3.  Order by total revenue and take the top 100.
    4.  Plot the distribution of this total revenue.

**10. User Behavior and Conversion Analysis**
*   **Prompt:** "Analyze the user journey on the website. What is the conversion rate from viewing a product (`event_type = 'product'`) to adding it to the cart (`event_type = 'cart'`)? Use the `events` table."
*   **Purpose:** This demonstrates funnel analysis and requires the agent to:
    1.  Count the number of unique sessions with a 'product' event.
    2.  Count the number of unique sessions with a 'cart' event.
    3.  Calculate the conversion rate between these two steps.

**11. Geospatial Analysis**
*   **Prompt:** "Visualize the geographic distribution of our customers and distribution centers on a map. Use the `users` and `distribution_centers` tables."
*   **Purpose:** This showcases the agent's ability to handle and visualize geospatial data. It needs to:
    1.  Read the latitude and longitude from both tables.
    2.  Create a map plot with two different markers for customers and distribution centers.

**12. Churn Prediction Feature Engineering**
*   **Prompt:** "I want to build a model to predict customer churn. Please create a BigFrames DataFrame with the following features for each user: `recency` (days since last purchase), `frequency` (total number of orders), and `monetary` (total spend). Also include the user's `traffic_source`."
*   **Purpose:** This is a feature engineering task that requires the agent to:
    1.  Join `users`, `orders`, and `order_items`.
    2.  For each user, calculate:
        *   The time since their last order.
        *   The total count of their orders.
        *   The total sum of their `sale_price`.
    3.  Combine these features into a single DataFrame.
