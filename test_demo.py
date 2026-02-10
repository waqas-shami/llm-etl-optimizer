#!/usr/bin/env python
"""
Quick test script to verify the demo components work correctly.
Run this before launching the Streamlit app.

Usage:
    python test_demo.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def test_sql_parser():
    """Test SQL parser functionality."""
    print("Testing SQL Parser...", end=" ")

    from src.sql_parser import SQLParser

    parser = SQLParser()

    test_sql = """
    SELECT
        c.customer_id,
        c.name,
        SUM(o.amount) as total
    FROM customers c
    LEFT JOIN orders o ON c.customer_id = o.customer_id
    WHERE o.order_date >= '2024-01-01'
    GROUP BY c.customer_id, c.name
    HAVING SUM(o.amount) > 1000
    """

    result = parser.parse(test_sql)

    assert len(result.tables) >= 1, "Should find at least 1 table"
    assert len(result.aggregations) >= 1, "Should find aggregations"
    assert result.complexity_score > 0, "Should calculate complexity"

    print("OK")
    print(f"   - Found {len(result.tables)} tables: {result.tables}")
    print(f"   - Found {len(result.aggregations)} aggregations")
    print(f"   - Complexity score: {result.complexity_score}")

    return True


def test_quality_scorer():
    """Test quality scorer functionality."""
    print("\nTesting Quality Scorer...", end=" ")

    from src.quality_scorer import QualityScorer

    scorer = QualityScorer()

    test_dbt = """
    {{
      config(
        materialized='table'
      )
    }}

    -- Model: fct_customer_orders
    -- Description: Customer order summary

    SELECT
        customer_id,
        SUM(amount) as total_revenue
    FROM {{ ref('stg_orders') }}
    GROUP BY customer_id
    """

    test_yaml = """
    version: 2
    models:
      - name: fct_customer_orders
        description: Customer orders
        columns:
          - name: customer_id
            tests:
              - unique
              - not_null
    """

    report = scorer.evaluate(test_dbt, test_yaml)

    assert report.overall_score > 0, "Should calculate overall score"
    assert len(report.categories) > 0, "Should have category scores"

    print("OK")
    print(f"   - Overall score: {report.overall_score}/100")
    print(f"   - Status: {'PASSED' if report.passed else 'NEEDS IMPROVEMENT'}")

    return True


def test_demo_responses():
    """Test demo response module."""
    print("\nTesting Demo Responses...", end=" ")

    from app.demo_responses import get_demo_response, SAMPLE_QUERIES

    assert len(SAMPLE_QUERIES) > 0, "Should have sample queries"

    response = get_demo_response("SELECT * FROM customers", {})

    assert "dbt_model" in response, "Should return dbt_model"
    assert "yaml_schema" in response, "Should return yaml_schema"
    assert "explanation" in response, "Should return explanation"

    print("OK")
    print(f"   - {len(SAMPLE_QUERIES)} sample queries available")
    print(f"   - Demo response contains all required fields")

    return True


def main():
    """Run all tests."""
    print("=" * 50)
    print("LLM ETL Optimizer - Demo Test Suite")
    print("=" * 50)
    print()

    all_passed = True

    try:
        all_passed &= test_sql_parser()
    except Exception as e:
        print(f"FAILED: {e}")
        all_passed = False

    try:
        all_passed &= test_quality_scorer()
    except Exception as e:
        print(f"FAILED: {e}")
        all_passed = False

    try:
        all_passed &= test_demo_responses()
    except Exception as e:
        print(f"FAILED: {e}")
        all_passed = False

    print()
    print("=" * 50)

    if all_passed:
        print("[PASSED] All tests passed! Ready to run the demo.")
        print()
        print("Launch with:")
        print("  python run_demo.py")
        print("  # or")
        print("  streamlit run app/streamlit_app.py")
        return 0
    else:
        print("[FAILED] Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
