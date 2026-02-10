"""
Quality Scorer Module

Evaluates generated DBT code against enterprise standards
and provides improvement suggestions.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class QualityReport:
    """Quality assessment report for generated code."""

    overall_score: int  # 0-100
    categories: dict = field(default_factory=dict)
    issues: list[dict] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    passed: bool = False


class QualityScorer:
    """
    Evaluates DBT model quality against enterprise standards.
    """

    # Scoring weights for different categories
    WEIGHTS = {
        "naming": 15,
        "documentation": 20,
        "testing": 20,
        "performance": 25,
        "maintainability": 20
    }

    # Passing threshold
    PASS_THRESHOLD = 70

    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode

    def evaluate(self, sql: str, yaml_schema: Optional[str] = None) -> QualityReport:
        """
        Evaluate DBT model quality.

        Args:
            sql: DBT model SQL content
            yaml_schema: Optional YAML schema content

        Returns:
            QualityReport with scores and suggestions
        """
        report = QualityReport(overall_score=0)

        # Evaluate each category
        report.categories["naming"] = self._score_naming(sql)
        report.categories["documentation"] = self._score_documentation(sql, yaml_schema)
        report.categories["testing"] = self._score_testing(yaml_schema)
        report.categories["performance"] = self._score_performance(sql)
        report.categories["maintainability"] = self._score_maintainability(sql)

        # Calculate overall score
        total_score = sum(
            report.categories[cat]["score"] * (self.WEIGHTS[cat] / 100)
            for cat in self.WEIGHTS
        )
        report.overall_score = int(total_score)
        report.passed = report.overall_score >= self.PASS_THRESHOLD

        # Collect all issues and suggestions
        for cat, result in report.categories.items():
            report.issues.extend(result.get("issues", []))
            report.suggestions.extend(result.get("suggestions", []))

        return report

    def _score_naming(self, sql: str) -> dict:
        """Score naming conventions."""
        score = 100
        issues = []
        suggestions = []

        # Check for model name prefix
        valid_prefixes = ['stg_', 'int_', 'fct_', 'dim_', 'mart_']
        model_pattern = r'--\s*Model:\s*(\w+)'
        match = re.search(model_pattern, sql, re.IGNORECASE)

        if match:
            model_name = match.group(1)
            if not any(model_name.startswith(p) for p in valid_prefixes):
                score -= 20
                issues.append({
                    "severity": "warning",
                    "message": f"Model name '{model_name}' doesn't follow naming convention"
                })
                suggestions.append("Use prefixes: stg_, int_, fct_, dim_, or mart_")

        # Check for snake_case in SQL
        camel_pattern = r'[a-z][A-Z]'
        if re.search(camel_pattern, sql):
            score -= 10
            issues.append({
                "severity": "info",
                "message": "CamelCase detected - prefer snake_case"
            })

        # Check for meaningful aliases
        single_letter_alias = r'\bAS\s+[a-zA-Z]\b'
        if re.search(single_letter_alias, sql, re.IGNORECASE):
            score -= 15
            issues.append({
                "severity": "warning",
                "message": "Single-letter aliases detected"
            })
            suggestions.append("Use meaningful table aliases (e.g., 'orders' instead of 'o')")

        return {"score": max(0, score), "issues": issues, "suggestions": suggestions}

    def _score_documentation(self, sql: str, yaml_schema: Optional[str]) -> dict:
        """Score documentation quality."""
        score = 0
        issues = []
        suggestions = []

        # Check for model description in SQL
        if re.search(r'--\s*Description:', sql, re.IGNORECASE):
            score += 30

        # Check for inline comments
        comment_lines = len(re.findall(r'--.*$', sql, re.MULTILINE))
        if comment_lines >= 3:
            score += 20
        elif comment_lines >= 1:
            score += 10

        # Check YAML schema
        if yaml_schema:
            score += 30

            # Check for column descriptions
            if 'description:' in yaml_schema.lower():
                score += 20
            else:
                issues.append({
                    "severity": "warning",
                    "message": "Column descriptions missing in schema"
                })
                suggestions.append("Add descriptions for all columns in YAML schema")
        else:
            issues.append({
                "severity": "error",
                "message": "No YAML schema documentation"
            })
            suggestions.append("Create a _schema.yml file with model and column documentation")

        return {"score": min(100, score), "issues": issues, "suggestions": suggestions}

    def _score_testing(self, yaml_schema: Optional[str]) -> dict:
        """Score test coverage."""
        score = 0
        issues = []
        suggestions = []

        if not yaml_schema:
            issues.append({
                "severity": "error",
                "message": "No tests defined"
            })
            suggestions.append("Add data quality tests in YAML schema")
            return {"score": 0, "issues": issues, "suggestions": suggestions}

        # Check for test types
        test_types = {
            'unique': 25,
            'not_null': 25,
            'accepted_values': 25,
            'relationships': 25
        }

        for test, points in test_types.items():
            if test in yaml_schema.lower():
                score += points
            else:
                suggestions.append(f"Consider adding '{test}' tests")

        if score < 50:
            issues.append({
                "severity": "warning",
                "message": "Limited test coverage"
            })

        return {"score": score, "issues": issues, "suggestions": suggestions}

    def _score_performance(self, sql: str) -> dict:
        """Score performance best practices."""
        score = 100
        issues = []
        suggestions = []

        # Check for SELECT *
        if re.search(r'SELECT\s+\*', sql, re.IGNORECASE):
            score -= 30
            issues.append({
                "severity": "error",
                "message": "SELECT * detected - performance anti-pattern"
            })
            suggestions.append("Explicitly list required columns instead of SELECT *")

        # Check for CTEs vs subqueries
        subquery_count = len(re.findall(r'\(\s*SELECT', sql, re.IGNORECASE))
        cte_count = len(re.findall(r'WITH\s+\w+\s+AS', sql, re.IGNORECASE))

        if subquery_count > 2 and cte_count == 0:
            score -= 20
            issues.append({
                "severity": "warning",
                "message": "Multiple subqueries without CTEs"
            })
            suggestions.append("Consider refactoring subqueries into CTEs for readability")

        # Check for DISTINCT without need
        if re.search(r'SELECT\s+DISTINCT', sql, re.IGNORECASE):
            score -= 10
            issues.append({
                "severity": "info",
                "message": "DISTINCT usage - verify it's necessary"
            })

        # Check for materialization config
        if '{{ config(' in sql:
            score += 10
        else:
            suggestions.append("Add explicit materialization config")

        return {"score": max(0, min(100, score)), "issues": issues, "suggestions": suggestions}

    def _score_maintainability(self, sql: str) -> dict:
        """Score code maintainability."""
        score = 100
        issues = []
        suggestions = []

        lines = sql.split('\n')

        # Check line length
        long_lines = [i for i, line in enumerate(lines, 1) if len(line) > 120]
        if long_lines:
            score -= min(20, len(long_lines) * 5)
            issues.append({
                "severity": "info",
                "message": f"Lines exceeding 120 characters: {long_lines[:5]}"
            })

        # Check for ref() usage (DBT best practice)
        if '{{ ref(' in sql:
            score += 10
        elif re.search(r'FROM\s+\w+\.\w+', sql):
            score -= 15
            suggestions.append("Use {{ ref('model_name') }} instead of hardcoded table references")

        # Check for source() usage
        if '{{ source(' in sql:
            score += 10

        # Check total line count (complexity indicator)
        if len(lines) > 200:
            score -= 15
            suggestions.append("Consider breaking into smaller, modular models")
        elif len(lines) > 100:
            score -= 5
            issues.append({
                "severity": "info",
                "message": "Model is getting complex - consider modularization"
            })

        # Check for consistent formatting
        if re.search(r'\t', sql):
            issues.append({
                "severity": "info",
                "message": "Mixed tabs detected - use spaces for consistency"
            })
            score -= 5

        return {"score": max(0, min(100, score)), "issues": issues, "suggestions": suggestions}

    def format_report(self, report: QualityReport) -> str:
        """Format quality report as readable string."""
        output = []
        output.append("=" * 60)
        output.append("DBT MODEL QUALITY REPORT")
        output.append("=" * 60)
        output.append(f"\nOverall Score: {report.overall_score}/100 {'PASS' if report.passed else 'FAIL'}")
        output.append("-" * 40)

        output.append("\nCategory Scores:")
        for category, result in report.categories.items():
            output.append(f"  {category.capitalize():20} {result['score']:3}/100")

        if report.issues:
            output.append("\nIssues Found:")
            for issue in report.issues:
                severity = issue['severity'].upper()
                output.append(f"  [{severity}] {issue['message']}")

        if report.suggestions:
            output.append("\nSuggestions:")
            for i, suggestion in enumerate(report.suggestions, 1):
                output.append(f"  {i}. {suggestion}")

        output.append("\n" + "=" * 60)
        return "\n".join(output)


# Convenience function
def score_dbt_model(sql: str, yaml_schema: Optional[str] = None) -> QualityReport:
    """Quick quality assessment of DBT model."""
    scorer = QualityScorer()
    return scorer.evaluate(sql, yaml_schema)
