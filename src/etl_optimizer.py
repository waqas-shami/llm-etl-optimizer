"""
ETL Optimizer - Main Entry Point

Orchestrates the complete pipeline for LLM-powered
SQL optimization and DBT model generation.
"""

from dataclasses import dataclass
from typing import Optional

from .sql_parser import SQLParser, SQLAnalysis
from .llm_orchestrator import LLMOrchestrator, OptimizationRequest, LLMResponse
from .dbt_generator import DBTGenerator, DBTModel
from .quality_scorer import QualityScorer, QualityReport


@dataclass
class OptimizationResult:
    """Complete result of ETL optimization."""

    # Input analysis
    sql_analysis: SQLAnalysis

    # LLM output
    llm_response: LLMResponse

    # Generated DBT model
    dbt_model: DBTModel
    dbt_sql: str
    dbt_yaml: str

    # Quality assessment
    quality_report: QualityReport

    # Metadata
    optimization_hints: list[str]
    files_created: Optional[dict] = None


class ETLOptimizer:
    """
    Main class for LLM-powered ETL optimization.

    Combines SQL parsing, LLM inference, DBT generation,
    and quality scoring into a single workflow.

    Example:
        >>> optimizer = ETLOptimizer()
        >>> result = optimizer.optimize('''
        ...     SELECT * FROM customers c
        ...     JOIN orders o ON c.id = o.customer_id
        ...     WHERE o.created_at > '2024-01-01'
        ... ''')
        >>> print(result.dbt_sql)
        >>> print(result.quality_report.overall_score)
    """

    def __init__(
        self,
        primary_model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        target_dialect: str = "snowflake",
        output_dir: str = "models",
        enable_cache: bool = True,
        auto_save: bool = False
    ):
        """
        Initialize the ETL Optimizer.

        Args:
            primary_model: Primary LLM model (default: gpt-4-turbo)
            fallback_model: Fallback LLM model (default: claude-3-sonnet)
            target_dialect: Target SQL dialect (snowflake, bigquery, redshift)
            output_dir: Directory for generated DBT models
            enable_cache: Enable LLM response caching
            auto_save: Automatically save generated models to disk
        """
        self.parser = SQLParser()
        self.orchestrator = LLMOrchestrator(
            primary_model=primary_model,
            fallback_model=fallback_model,
            enable_cache=enable_cache
        )
        self.generator = DBTGenerator(output_dir)
        self.scorer = QualityScorer()

        self.target_dialect = target_dialect
        self.auto_save = auto_save

    def optimize(
        self,
        sql: str,
        context: Optional[str] = None,
        include_tests: bool = True,
        include_docs: bool = True
    ) -> OptimizationResult:
        """
        Optimize SQL and generate DBT model.

        Args:
            sql: Legacy SQL query to optimize
            context: Optional business context for better optimization
            include_tests: Include test suggestions in output
            include_docs: Include documentation in output

        Returns:
            OptimizationResult with all artifacts
        """
        # Step 1: Parse and analyze input SQL
        sql_analysis = self.parser.parse(sql)
        optimization_hints = self.parser.get_optimization_hints()

        # Step 2: Build enhanced context for LLM
        enhanced_context = self._build_enhanced_context(
            sql_analysis,
            optimization_hints,
            context
        )

        # Step 3: Call LLM for optimization
        request = OptimizationRequest(
            sql=sql,
            context=enhanced_context,
            target_dialect=self.target_dialect,
            include_tests=include_tests,
            include_docs=include_docs
        )
        llm_response = self.orchestrator.optimize_sql(request)

        # Step 4: Parse LLM output into DBT model
        dbt_model = self.generator.parse_llm_output(llm_response.content)

        # Step 5: Generate DBT artifacts
        dbt_sql = self.generator.generate_model_file(dbt_model)
        dbt_yaml = self.generator.generate_schema_yaml(dbt_model)

        # Step 6: Score quality
        quality_report = self.scorer.evaluate(dbt_sql, dbt_yaml)

        # Step 7: Optionally save to disk
        files_created = None
        if self.auto_save:
            files_created = self.generator.save_model(dbt_model)

        return OptimizationResult(
            sql_analysis=sql_analysis,
            llm_response=llm_response,
            dbt_model=dbt_model,
            dbt_sql=dbt_sql,
            dbt_yaml=dbt_yaml,
            quality_report=quality_report,
            optimization_hints=optimization_hints,
            files_created=files_created
        )

    def _build_enhanced_context(
        self,
        analysis: SQLAnalysis,
        hints: list[str],
        user_context: Optional[str]
    ) -> str:
        """Build enhanced context from analysis."""
        context_parts = []

        # Add structural analysis
        context_parts.append("## SQL Analysis")
        context_parts.append(f"- Tables involved: {', '.join(analysis.tables)}")
        context_parts.append(f"- Join count: {len(analysis.joins)}")
        context_parts.append(f"- Aggregations: {', '.join(analysis.aggregations) or 'None'}")
        context_parts.append(f"- Complexity score: {analysis.complexity_score}/100")

        # Add optimization hints
        if hints:
            context_parts.append("\n## Optimization Hints")
            for hint in hints:
                context_parts.append(f"- {hint}")

        # Add user context
        if user_context:
            context_parts.append(f"\n## Business Context\n{user_context}")

        return "\n".join(context_parts)

    def batch_optimize(
        self,
        sql_queries: list[str],
        contexts: Optional[list[str]] = None
    ) -> list[OptimizationResult]:
        """
        Optimize multiple SQL queries.

        Args:
            sql_queries: List of SQL queries to optimize
            contexts: Optional list of contexts (parallel to queries)

        Returns:
            List of OptimizationResult objects
        """
        results = []
        contexts = contexts or [None] * len(sql_queries)

        for sql, context in zip(sql_queries, contexts):
            result = self.optimize(sql, context=context)
            results.append(result)

        return results

    def get_stats(self) -> dict:
        """Get optimization statistics."""
        return {
            "llm_stats": self.orchestrator.get_stats()
        }


# CLI Entry Point
def main():
    """Command-line interface for ETL Optimizer."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="LLM-Powered ETL Optimizer - Transform legacy SQL to DBT models"
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=str,
        help="SQL file path or '-' for stdin"
    )
    parser.add_argument(
        "--dialect",
        type=str,
        default="snowflake",
        choices=["snowflake", "bigquery", "redshift", "postgres"],
        help="Target SQL dialect"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="models",
        help="Output directory for DBT models"
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save generated models to disk"
    )
    parser.add_argument(
        "--context",
        type=str,
        help="Business context for optimization"
    )

    args = parser.parse_args()

    # Read input
    if args.input == "-" or args.input is None:
        sql = sys.stdin.read()
    else:
        with open(args.input) as f:
            sql = f.read()

    # Initialize optimizer
    optimizer = ETLOptimizer(
        target_dialect=args.dialect,
        output_dir=args.output,
        auto_save=args.save
    )

    # Run optimization
    print("Analyzing SQL and generating optimized DBT model...")
    result = optimizer.optimize(sql, context=args.context)

    # Output results
    print("\n" + "=" * 60)
    print("OPTIMIZED DBT MODEL")
    print("=" * 60)
    print(result.dbt_sql)

    print("\n" + "=" * 60)
    print("YAML SCHEMA")
    print("=" * 60)
    print(result.dbt_yaml)

    # Print quality report
    print(optimizer.scorer.format_report(result.quality_report))

    if result.files_created:
        print(f"\nFiles saved: {result.files_created}")


if __name__ == "__main__":
    main()
