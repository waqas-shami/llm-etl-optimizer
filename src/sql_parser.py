"""
SQL Parser Module

Extracts Abstract Syntax Tree (AST) from legacy SQL and identifies
patterns, tables, joins, aggregations, and business logic.
"""

import sqlparse
from sqlparse.sql import IdentifierList, Identifier, Where, Parenthesis
from sqlparse.tokens import Keyword, DML
from dataclasses import dataclass, field
from typing import Optional
import re


@dataclass
class SQLAnalysis:
    """Structured analysis of a SQL query."""

    tables: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    joins: list[dict] = field(default_factory=list)
    where_conditions: list[str] = field(default_factory=list)
    aggregations: list[str] = field(default_factory=list)
    group_by: list[str] = field(default_factory=list)
    having: Optional[str] = None
    subqueries: list[str] = field(default_factory=list)
    ctes: list[dict] = field(default_factory=list)
    complexity_score: int = 0
    query_type: str = "SELECT"


class SQLParser:
    """
    Parses SQL queries and extracts structural information
    for LLM optimization.
    """

    AGGREGATION_FUNCTIONS = {'SUM', 'COUNT', 'AVG', 'MIN', 'MAX', 'STDDEV', 'VARIANCE'}

    def __init__(self):
        self.analysis = SQLAnalysis()

    def parse(self, sql: str) -> SQLAnalysis:
        """
        Parse SQL and return structured analysis.

        Args:
            sql: Raw SQL query string

        Returns:
            SQLAnalysis object with extracted information
        """
        self.analysis = SQLAnalysis()

        # Normalize SQL
        sql = self._normalize_sql(sql)

        # Parse with sqlparse
        parsed = sqlparse.parse(sql)[0]

        # Extract components
        self._extract_query_type(parsed)
        self._extract_tables(parsed)
        self._extract_columns(parsed)
        self._extract_joins(sql)
        self._extract_where(parsed)
        self._extract_aggregations(sql)
        self._extract_group_by(sql)
        self._extract_having(sql)
        self._extract_ctes(sql)
        self._calculate_complexity()

        return self.analysis

    def _normalize_sql(self, sql: str) -> str:
        """Normalize SQL whitespace and formatting."""
        sql = ' '.join(sql.split())
        return sql.strip()

    def _extract_query_type(self, parsed) -> None:
        """Identify query type (SELECT, INSERT, UPDATE, etc.)."""
        for token in parsed.tokens:
            if token.ttype is DML:
                self.analysis.query_type = token.value.upper()
                break

    def _extract_tables(self, parsed) -> None:
        """Extract table names from FROM and JOIN clauses."""
        from_seen = False
        for token in parsed.tokens:
            if from_seen:
                if self._is_subselect(token):
                    self.analysis.subqueries.append(str(token))
                elif token.ttype is Keyword:
                    from_seen = False
                else:
                    self._extract_table_identifiers(token)
            if token.ttype is Keyword and token.value.upper() == 'FROM':
                from_seen = True

    def _extract_table_identifiers(self, token) -> None:
        """Extract table identifiers from token."""
        if isinstance(token, IdentifierList):
            for identifier in token.get_identifiers():
                self._add_table(identifier)
        elif isinstance(token, Identifier):
            self._add_table(token)
        elif token.ttype is not Keyword:
            self._add_table(token)

    def _add_table(self, token) -> None:
        """Add table name to analysis."""
        name = token.get_real_name() if hasattr(token, 'get_real_name') else str(token).strip()
        if name and name.upper() not in ('', 'JOIN', 'ON', 'AND', 'OR', 'LEFT', 'RIGHT', 'INNER', 'OUTER'):
            # Clean up table name
            name = name.split()[0] if ' ' in name else name
            if name not in self.analysis.tables:
                self.analysis.tables.append(name)

    def _extract_columns(self, parsed) -> None:
        """Extract column names from SELECT clause."""
        select_seen = False
        for token in parsed.tokens:
            if select_seen:
                if token.ttype is Keyword and token.value.upper() == 'FROM':
                    break
                self._extract_column_identifiers(token)
            if token.ttype is DML and token.value.upper() == 'SELECT':
                select_seen = True

    def _extract_column_identifiers(self, token) -> None:
        """Extract column identifiers from token."""
        if isinstance(token, IdentifierList):
            for identifier in token.get_identifiers():
                col_name = str(identifier).strip()
                if col_name:
                    self.analysis.columns.append(col_name)
        elif isinstance(token, Identifier):
            col_name = str(token).strip()
            if col_name:
                self.analysis.columns.append(col_name)

    def _extract_joins(self, sql: str) -> None:
        """Extract JOIN information."""
        join_pattern = r'(LEFT|RIGHT|INNER|OUTER|FULL|CROSS)?\s*JOIN\s+(\w+)\s+(?:AS\s+)?(\w+)?\s+ON\s+([^WHERE|GROUP|ORDER|HAVING|LIMIT]+)'
        matches = re.findall(join_pattern, sql, re.IGNORECASE)

        for match in matches:
            join_type, table, alias, condition = match
            self.analysis.joins.append({
                'type': (join_type or 'INNER').upper(),
                'table': table,
                'alias': alias or table,
                'condition': condition.strip()
            })

    def _extract_where(self, parsed) -> None:
        """Extract WHERE conditions."""
        for token in parsed.tokens:
            if isinstance(token, Where):
                condition = str(token).replace('WHERE', '').strip()
                self.analysis.where_conditions = [condition]

    def _extract_aggregations(self, sql: str) -> None:
        """Extract aggregation functions used."""
        for func in self.AGGREGATION_FUNCTIONS:
            pattern = rf'{func}\s*\([^)]+\)'
            matches = re.findall(pattern, sql, re.IGNORECASE)
            self.analysis.aggregations.extend(matches)

    def _extract_group_by(self, sql: str) -> None:
        """Extract GROUP BY columns."""
        pattern = r'GROUP\s+BY\s+([^HAVING|ORDER|LIMIT]+)'
        match = re.search(pattern, sql, re.IGNORECASE)
        if match:
            columns = match.group(1).strip()
            self.analysis.group_by = [col.strip() for col in columns.split(',')]

    def _extract_having(self, sql: str) -> None:
        """Extract HAVING clause."""
        pattern = r'HAVING\s+([^ORDER|LIMIT]+)'
        match = re.search(pattern, sql, re.IGNORECASE)
        if match:
            self.analysis.having = match.group(1).strip()

    def _extract_ctes(self, sql: str) -> None:
        """Extract Common Table Expressions (WITH clauses)."""
        pattern = r'WITH\s+(\w+)\s+AS\s*\(([^)]+)\)'
        matches = re.findall(pattern, sql, re.IGNORECASE)
        for name, query in matches:
            self.analysis.ctes.append({
                'name': name,
                'query': query.strip()
            })

    def _is_subselect(self, token) -> bool:
        """Check if token is a subselect."""
        if isinstance(token, Parenthesis):
            return any(t.ttype is DML for t in token.tokens)
        return False

    def _calculate_complexity(self) -> None:
        """Calculate query complexity score (0-100)."""
        score = 0

        # Base complexity from tables
        score += len(self.analysis.tables) * 5

        # Join complexity
        score += len(self.analysis.joins) * 10

        # Aggregation complexity
        score += len(self.analysis.aggregations) * 5

        # Subquery complexity
        score += len(self.analysis.subqueries) * 15

        # CTE complexity
        score += len(self.analysis.ctes) * 10

        # HAVING adds complexity
        if self.analysis.having:
            score += 5

        self.analysis.complexity_score = min(score, 100)

    def get_optimization_hints(self) -> list[str]:
        """Generate optimization hints based on analysis."""
        hints = []

        if len(self.analysis.joins) > 3:
            hints.append("Consider breaking into multiple CTEs for readability")

        if self.analysis.subqueries:
            hints.append("Subqueries detected - consider converting to CTEs for DBT")

        if 'SELECT *' in ' '.join(self.analysis.columns).upper():
            hints.append("Avoid SELECT * - explicitly list required columns")

        if self.analysis.complexity_score > 70:
            hints.append("High complexity query - consider modular DBT models")

        return hints


# Convenience function
def analyze_sql(sql: str) -> SQLAnalysis:
    """Quick analysis of SQL query."""
    parser = SQLParser()
    return parser.parse(sql)
