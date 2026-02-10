"""
Demo Responses for LLM ETL Optimizer

Pre-computed responses for demo mode to showcase functionality
without requiring API keys.
"""

SAMPLE_QUERIES = {
    "customer_sales": """SELECT
    c.customer_id,
    c.customer_name,
    c.email,
    SUM(o.amount) as total_revenue,
    COUNT(DISTINCT o.order_id) as order_count,
    AVG(o.amount) as avg_order_value,
    MAX(o.order_date) as last_order_date
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id
WHERE o.order_date >= '2024-01-01'
  AND o.status = 'completed'
GROUP BY c.customer_id, c.customer_name, c.email
HAVING SUM(o.amount) > 1000
ORDER BY total_revenue DESC""",

    "inventory": """SELECT
    p.product_id,
    p.product_name,
    p.category,
    i.warehouse_id,
    i.quantity_on_hand,
    i.reorder_point,
    CASE
        WHEN i.quantity_on_hand <= i.reorder_point THEN 'REORDER'
        WHEN i.quantity_on_hand <= i.reorder_point * 1.5 THEN 'LOW'
        ELSE 'OK'
    END as stock_status,
    (
        SELECT SUM(quantity)
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.order_id
        WHERE oi.product_id = p.product_id
          AND o.order_date >= DATEADD(day, -30, CURRENT_DATE)
    ) as units_sold_30d
FROM products p
JOIN inventory i ON p.product_id = i.product_id
WHERE p.is_active = 1""",

    "revenue_category": """SELECT
    DATE_TRUNC('month', o.order_date) as order_month,
    p.category,
    COUNT(DISTINCT o.order_id) as total_orders,
    COUNT(DISTINCT o.customer_id) as unique_customers,
    SUM(oi.quantity * oi.unit_price) as gross_revenue,
    SUM(oi.discount_amount) as total_discounts,
    SUM(oi.quantity * oi.unit_price) - SUM(oi.discount_amount) as net_revenue
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
JOIN products p ON oi.product_id = p.product_id
WHERE o.order_date >= '2023-01-01'
  AND o.status IN ('completed', 'shipped')
GROUP BY DATE_TRUNC('month', o.order_date), p.category
ORDER BY order_month DESC, net_revenue DESC""",

    "customer_segment": """SELECT
    c.customer_id,
    c.customer_name,
    c.signup_date,
    DATEDIFF(day, c.signup_date, CURRENT_DATE) as customer_age_days,
    COUNT(o.order_id) as lifetime_orders,
    SUM(o.amount) as lifetime_value,
    AVG(o.amount) as avg_order_value,
    DATEDIFF(day, MAX(o.order_date), CURRENT_DATE) as days_since_last_order,
    CASE
        WHEN SUM(o.amount) >= 10000 THEN 'VIP'
        WHEN SUM(o.amount) >= 5000 THEN 'Gold'
        WHEN SUM(o.amount) >= 1000 THEN 'Silver'
        ELSE 'Bronze'
    END as customer_tier,
    CASE
        WHEN DATEDIFF(day, MAX(o.order_date), CURRENT_DATE) > 180 THEN 'Churned'
        WHEN DATEDIFF(day, MAX(o.order_date), CURRENT_DATE) > 90 THEN 'At Risk'
        WHEN DATEDIFF(day, MAX(o.order_date), CURRENT_DATE) > 30 THEN 'Cooling'
        ELSE 'Active'
    END as engagement_status
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.customer_name, c.signup_date""",

    "monthly_trends": """SELECT
    DATE_TRUNC('month', order_date) as month,
    COUNT(*) as total_orders,
    COUNT(DISTINCT customer_id) as unique_customers,
    SUM(amount) as total_revenue,
    AVG(amount) as avg_order_value,
    SUM(amount) / COUNT(DISTINCT customer_id) as revenue_per_customer,
    LAG(SUM(amount)) OVER (ORDER BY DATE_TRUNC('month', order_date)) as prev_month_revenue,
    (SUM(amount) - LAG(SUM(amount)) OVER (ORDER BY DATE_TRUNC('month', order_date))) /
        NULLIF(LAG(SUM(amount)) OVER (ORDER BY DATE_TRUNC('month', order_date)), 0) * 100 as mom_growth_pct
FROM orders
WHERE order_date >= DATEADD(month, -12, CURRENT_DATE)
  AND status = 'completed'
GROUP BY DATE_TRUNC('month', order_date)
ORDER BY month DESC"""
}


DEMO_DBT_MODELS = {
    "default": """{{
  config(
    materialized='table',
    tags=['mart', 'customer', 'revenue']
  )
}}

/*
    Model: fct_customer_revenue
    Description: Customer revenue summary with order metrics
    Owner: Data Platform Team

    Business Context:
    This model aggregates customer order data to provide a comprehensive
    view of customer value, supporting executive dashboards and
    customer segmentation analysis.
*/

with customers as (
    select
        customer_id,
        customer_name,
        email
    from {{ ref('stg_customers') }}
),

orders as (
    select
        order_id,
        customer_id,
        amount,
        order_date,
        status
    from {{ ref('stg_orders') }}
    where status = 'completed'
      and order_date >= '2024-01-01'
),

customer_orders as (
    select
        customer_id,
        count(distinct order_id) as order_count,
        sum(amount) as total_revenue,
        avg(amount) as avg_order_value,
        max(order_date) as last_order_date,
        min(order_date) as first_order_date
    from orders
    group by customer_id
    having sum(amount) > 1000
)

select
    c.customer_id,
    c.customer_name,
    c.email,

    -- Order metrics
    coalesce(co.order_count, 0) as order_count,
    coalesce(co.total_revenue, 0) as total_revenue,
    coalesce(co.avg_order_value, 0) as avg_order_value,

    -- Dates
    co.first_order_date,
    co.last_order_date,

    -- Derived metrics
    datediff(day, co.first_order_date, co.last_order_date) as customer_tenure_days,

    -- Customer tier
    case
        when co.total_revenue >= 10000 then 'Platinum'
        when co.total_revenue >= 5000 then 'Gold'
        when co.total_revenue >= 2500 then 'Silver'
        else 'Bronze'
    end as customer_tier

from customers c
left join customer_orders co
    on c.customer_id = co.customer_id

where co.customer_id is not null  -- Only customers with qualifying orders

order by total_revenue desc""",

    "inventory": """{{
  config(
    materialized='table',
    tags=['mart', 'inventory', 'operations']
  )
}}

/*
    Model: fct_inventory_status
    Description: Real-time inventory status with reorder alerts
    Owner: Data Platform Team
*/

with products as (
    select * from {{ ref('stg_products') }}
    where is_active = true
),

inventory as (
    select * from {{ ref('stg_inventory') }}
),

recent_sales as (
    select
        product_id,
        sum(quantity) as units_sold_30d
    from {{ ref('stg_order_items') }} oi
    inner join {{ ref('stg_orders') }} o using (order_id)
    where o.order_date >= dateadd(day, -30, current_date)
    group by product_id
)

select
    p.product_id,
    p.product_name,
    p.category,
    i.warehouse_id,
    i.quantity_on_hand,
    i.reorder_point,

    -- Stock status
    case
        when i.quantity_on_hand <= i.reorder_point then 'REORDER_NOW'
        when i.quantity_on_hand <= i.reorder_point * 1.5 then 'LOW_STOCK'
        else 'HEALTHY'
    end as stock_status,

    -- Sales velocity
    coalesce(rs.units_sold_30d, 0) as units_sold_30d,

    -- Days of inventory
    case
        when coalesce(rs.units_sold_30d, 0) > 0
        then round(i.quantity_on_hand / (rs.units_sold_30d / 30.0), 1)
        else null
    end as days_of_inventory

from products p
inner join inventory i on p.product_id = i.product_id
left join recent_sales rs on p.product_id = rs.product_id"""
}


DEMO_YAML_SCHEMAS = {
    "default": """version: 2

models:
  - name: fct_customer_revenue
    description: >
      Customer revenue summary aggregating order data to provide
      comprehensive customer value metrics. Supports executive
      dashboards and customer segmentation analysis.

    config:
      tags: ['mart', 'customer', 'revenue']

    columns:
      - name: customer_id
        description: Unique identifier for the customer
        tests:
          - unique
          - not_null

      - name: customer_name
        description: Full name of the customer
        tests:
          - not_null

      - name: email
        description: Customer email address
        tests:
          - not_null

      - name: order_count
        description: Total number of completed orders
        tests:
          - not_null

      - name: total_revenue
        description: Sum of all order amounts in local currency
        tests:
          - not_null

      - name: avg_order_value
        description: Average order value (total_revenue / order_count)

      - name: first_order_date
        description: Date of customer's first order

      - name: last_order_date
        description: Date of customer's most recent order

      - name: customer_tenure_days
        description: Days between first and last order

      - name: customer_tier
        description: Customer value tier based on total revenue
        tests:
          - accepted_values:
              values: ['Platinum', 'Gold', 'Silver', 'Bronze']""",

    "inventory": """version: 2

models:
  - name: fct_inventory_status
    description: >
      Real-time inventory status with stock levels, reorder alerts,
      and sales velocity metrics for operational decision-making.

    columns:
      - name: product_id
        description: Unique product identifier
        tests:
          - not_null

      - name: stock_status
        description: Current inventory status classification
        tests:
          - accepted_values:
              values: ['REORDER_NOW', 'LOW_STOCK', 'HEALTHY']

      - name: days_of_inventory
        description: Estimated days until stockout based on 30-day sales velocity"""
}


DEMO_EXPLANATIONS = {
    "default": """## Optimization Summary

### What Changed

1. **Refactored to CTEs**: Converted subqueries into Common Table Expressions for better readability and maintainability.

2. **Added Proper Refs**: Replaced hardcoded table names with `{{ ref() }}` macros for DBT lineage tracking.

3. **Improved Column Selection**: Explicitly listed all columns instead of using implicit column references.

4. **Added Documentation**: Included model description, column descriptions, and business context.

5. **Added Data Tests**: Implemented `unique`, `not_null`, and `accepted_values` tests for data quality.

### Performance Considerations

- **Materialization**: Set to `table` for optimal query performance on downstream dashboards.
- **Filtering Early**: Applied date and status filters early in the CTE chain to reduce data volume.
- **Aggregation Optimization**: Grouped aggregations together to minimize table scans.

### Best Practices Applied

- ✅ Snake_case naming convention
- ✅ Descriptive column aliases
- ✅ Proper indentation and formatting
- ✅ Business logic documented in comments
- ✅ Null handling with COALESCE
- ✅ Customer tier logic extracted for clarity

### Suggested Follow-ups

1. Consider adding an incremental materialization if data volume grows
2. Add freshness tests to source tables
3. Consider partitioning by date for large datasets
4. Add row-level security if needed for customer data""",

    "inventory": """## Optimization Summary

### What Changed

1. **Eliminated Correlated Subquery**: Converted the per-row subquery into a CTE with pre-aggregation.

2. **Added Sales Velocity Metrics**: Calculated days of inventory to support operational decisions.

3. **Improved Stock Status Logic**: Made CASE statement more readable and maintainable.

### Performance Impact

- Estimated **10x performance improvement** by eliminating N+1 query pattern
- Pre-aggregating 30-day sales reduces repeated date calculations"""
}


def get_demo_response(sql_input: str, options: dict) -> dict:
    """
    Get a demo response based on input SQL.

    In demo mode, we return pre-computed responses.
    In live mode, this would call the actual LLM.
    """
    # Determine which demo response to use based on SQL content
    sql_lower = sql_input.lower()

    if 'inventory' in sql_lower or 'warehouse' in sql_lower or 'reorder' in sql_lower:
        template_key = "inventory"
    else:
        template_key = "default"

    return {
        "dbt_model": DEMO_DBT_MODELS.get(template_key, DEMO_DBT_MODELS["default"]),
        "yaml_schema": DEMO_YAML_SCHEMAS.get(template_key, DEMO_YAML_SCHEMAS["default"]),
        "explanation": DEMO_EXPLANATIONS.get(template_key, DEMO_EXPLANATIONS["default"])
    }


def get_live_response(sql_input: str, options: dict, api_key: str) -> dict:
    """
    Get a live response from LLM API.

    This function would call the actual LLM orchestrator.
    For now, falls back to demo mode if not implemented.
    """
    # TODO: Implement actual LLM call
    # from src.llm_orchestrator import LLMOrchestrator
    # orchestrator = LLMOrchestrator(api_key=api_key)
    # return orchestrator.optimize(sql_input, options)

    return get_demo_response(sql_input, options)
