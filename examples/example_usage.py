"""
Example Usage - LLM-Powered ETL Optimizer

This script demonstrates the core functionality of the ETL Optimizer.
"""

from src.etl_optimizer import ETLOptimizer
from src.sql_parser import analyze_sql
from src.quality_scorer import score_dbt_model

# Example 1: Simple query optimization
simple_sql = """
SELECT
    a.customer_id,
    a.name,
    a.email,
    SUM(b.amount) as total_sales,
    COUNT(DISTINCT b.order_id) as order_count,
    MAX(b.order_date) as last_order_date
FROM customers a
LEFT JOIN orders b ON a.customer_id = b.customer_id
WHERE b.order_date >= '2024-01-01'
  AND b.status = 'completed'
GROUP BY a.customer_id, a.name, a.email
HAVING SUM(b.amount) > 1000
ORDER BY total_sales DESC
"""

# Example 2: Complex legacy SQL with subqueries
complex_sql = """
SELECT
    c.customer_id,
    c.customer_name,
    c.segment,
    order_summary.total_orders,
    order_summary.total_revenue,
    order_summary.avg_order_value,
    (
        SELECT COUNT(*)
        FROM support_tickets st
        WHERE st.customer_id = c.customer_id
          AND st.created_at >= DATEADD(month, -6, CURRENT_DATE)
    ) as recent_tickets,
    CASE
        WHEN order_summary.total_revenue > 10000 THEN 'Platinum'
        WHEN order_summary.total_revenue > 5000 THEN 'Gold'
        WHEN order_summary.total_revenue > 1000 THEN 'Silver'
        ELSE 'Bronze'
    END as customer_tier
FROM customers c
LEFT JOIN (
    SELECT
        customer_id,
        COUNT(*) as total_orders,
        SUM(order_total) as total_revenue,
        AVG(order_total) as avg_order_value
    FROM orders
    WHERE order_status = 'completed'
      AND order_date >= DATEADD(year, -1, CURRENT_DATE)
    GROUP BY customer_id
) order_summary ON c.customer_id = order_summary.customer_id
WHERE c.is_active = 1
  AND c.created_at < DATEADD(month, -3, CURRENT_DATE)
"""


def demo_sql_analysis():
    """Demonstrate SQL parsing capabilities."""
    print("=" * 60)
    print("SQL ANALYSIS DEMO")
    print("=" * 60)

    analysis = analyze_sql(complex_sql)

    print(f"\nTables found: {analysis.tables}")
    print(f"Columns: {len(analysis.columns)} selected")
    print(f"Joins: {len(analysis.joins)}")
    print(f"Aggregations: {analysis.aggregations}")
    print(f"Subqueries: {len(analysis.subqueries)}")
    print(f"Complexity Score: {analysis.complexity_score}/100")


def demo_full_optimization():
    """Demonstrate complete optimization workflow."""
    print("\n" + "=" * 60)
    print("FULL OPTIMIZATION DEMO")
    print("=" * 60)

    # Initialize optimizer
    optimizer = ETLOptimizer(
        target_dialect="snowflake",
        auto_save=False  # Don't save files in demo
    )

    # Run optimization with business context
    result = optimizer.optimize(
        sql=simple_sql,
        context="""
        This query powers the executive dashboard showing top customers.
        It's used for quarterly business reviews and must refresh daily.
        Key stakeholders: Sales VP, Finance Director
        """
    )

    print("\n--- SQL Analysis ---")
    print(f"Tables: {result.sql_analysis.tables}")
    print(f"Complexity: {result.sql_analysis.complexity_score}/100")

    print("\n--- Optimization Hints ---")
    for hint in result.optimization_hints:
        print(f"  - {hint}")

    print("\n--- Generated DBT Model ---")
    print(result.dbt_sql[:500] + "..." if len(result.dbt_sql) > 500 else result.dbt_sql)

    print("\n--- Quality Score ---")
    print(f"Overall: {result.quality_report.overall_score}/100")
    print(f"Status: {'PASSED' if result.quality_report.passed else 'NEEDS IMPROVEMENT'}")

    print("\n--- LLM Stats ---")
    stats = optimizer.get_stats()
    print(f"Model used: {result.llm_response.model_used}")
    print(f"Tokens: {result.llm_response.tokens_used}")
    print(f"Latency: {result.llm_response.latency_ms:.0f}ms")


def demo_quality_scoring():
    """Demonstrate quality scoring on DBT code."""
    print("\n" + "=" * 60)
    print("QUALITY SCORING DEMO")
    print("=" * 60)

    sample_dbt = """
    {{
      config(
        materialized='table'
      )
    }}

    -- Model: fct_customer_orders
    -- Description: Customer order summary for reporting

    WITH customers AS (
        SELECT * FROM {{ ref('stg_customers') }}
    ),

    orders AS (
        SELECT * FROM {{ ref('stg_orders') }}
    )

    SELECT
        c.customer_id,
        c.customer_name,
        COUNT(o.order_id) as total_orders,
        SUM(o.amount) as total_revenue
    FROM customers c
    LEFT JOIN orders o ON c.customer_id = o.customer_id
    GROUP BY c.customer_id, c.customer_name
    """

    sample_yaml = """
    version: 2
    models:
      - name: fct_customer_orders
        description: Customer order summary
        columns:
          - name: customer_id
            description: Unique customer identifier
            tests:
              - unique
              - not_null
          - name: total_revenue
            description: Sum of all order amounts
    """

    report = score_dbt_model(sample_dbt, sample_yaml)

    print(f"\nOverall Score: {report.overall_score}/100")
    print(f"Status: {'PASS' if report.passed else 'FAIL'}")

    print("\nCategory Scores:")
    for cat, result in report.categories.items():
        print(f"  {cat}: {result['score']}/100")

    if report.suggestions:
        print("\nSuggestions:")
        for s in report.suggestions[:5]:
            print(f"  - {s}")


if __name__ == "__main__":
    # Run demos
    demo_sql_analysis()

    # Note: Full optimization requires API keys
    # Uncomment to run with valid keys:
    # demo_full_optimization()

    demo_quality_scoring()
