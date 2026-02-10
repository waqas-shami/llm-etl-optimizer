"""
DBT Generator Module

Converts LLM output into valid DBT models with proper
refs, tests, documentation, and project structure.
"""

import re
import yaml
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class DBTModel:
    """Represents a complete DBT model."""

    name: str
    sql: str
    description: str
    columns: list[dict] = field(default_factory=list)
    tests: list[dict] = field(default_factory=list)
    materialization: str = "view"
    tags: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


@dataclass
class DBTProject:
    """Collection of DBT models."""

    models: list[DBTModel] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)


class DBTGenerator:
    """
    Generates DBT models from parsed LLM output.
    """

    MODEL_PREFIXES = {
        "staging": "stg_",
        "intermediate": "int_",
        "fact": "fct_",
        "dimension": "dim_",
        "mart": "mart_"
    }

    def __init__(self, target_dir: str = "models"):
        self.target_dir = Path(target_dir)

    def parse_llm_output(self, llm_response: str) -> DBTModel:
        """
        Parse LLM response and extract DBT model components.

        Args:
            llm_response: Raw LLM output containing SQL and documentation

        Returns:
            DBTModel with extracted components
        """
        # Extract SQL block
        sql = self._extract_sql(llm_response)

        # Extract model name from SQL or generate
        name = self._extract_model_name(sql, llm_response)

        # Extract description
        description = self._extract_description(llm_response)

        # Extract columns documentation
        columns = self._extract_columns(llm_response)

        # Extract tests
        tests = self._extract_tests(llm_response)

        # Determine materialization
        materialization = self._determine_materialization(sql, llm_response)

        return DBTModel(
            name=name,
            sql=sql,
            description=description,
            columns=columns,
            tests=tests,
            materialization=materialization
        )

    def _extract_sql(self, response: str) -> str:
        """Extract SQL code block from response."""
        # Try to find SQL in code blocks
        sql_pattern = r'```sql\n(.*?)```'
        match = re.search(sql_pattern, response, re.DOTALL | re.IGNORECASE)

        if match:
            return match.group(1).strip()

        # Try generic code block
        code_pattern = r'```\n(.*?)```'
        match = re.search(code_pattern, response, re.DOTALL)

        if match:
            return match.group(1).strip()

        # Return response as-is if no code blocks
        return response.strip()

    def _extract_model_name(self, sql: str, response: str) -> str:
        """Extract or generate model name."""
        # Look for explicit model name in response
        name_pattern = r'model[:\s]+(\w+)'
        match = re.search(name_pattern, response, re.IGNORECASE)
        if match:
            return match.group(1).lower()

        # Try to infer from main table in SQL
        from_pattern = r'FROM\s+(\w+)'
        match = re.search(from_pattern, sql, re.IGNORECASE)
        if match:
            table_name = match.group(1).lower()
            return f"stg_{table_name}"

        return "model_unnamed"

    def _extract_description(self, response: str) -> str:
        """Extract model description from response."""
        # Look for description section
        desc_pattern = r'(?:description|summary)[:\s]+(.*?)(?:\n\n|\n#|$)'
        match = re.search(desc_pattern, response, re.IGNORECASE | re.DOTALL)

        if match:
            return match.group(1).strip()[:500]

        return "Auto-generated DBT model from legacy SQL optimization"

    def _extract_columns(self, response: str) -> list[dict]:
        """Extract column definitions from response."""
        columns = []

        # Look for YAML schema block
        yaml_pattern = r'```ya?ml\n(.*?)```'
        match = re.search(yaml_pattern, response, re.DOTALL | re.IGNORECASE)

        if match:
            try:
                schema = yaml.safe_load(match.group(1))
                if isinstance(schema, dict) and 'columns' in schema:
                    return schema['columns']
            except yaml.YAMLError:
                pass

        # Try to parse column list
        col_pattern = r'-\s*(\w+):\s*(.*?)(?:\n|$)'
        matches = re.findall(col_pattern, response)

        for name, desc in matches:
            columns.append({
                "name": name,
                "description": desc.strip()
            })

        return columns

    def _extract_tests(self, response: str) -> list[dict]:
        """Extract suggested tests from response."""
        tests = []

        # Common test patterns to look for
        test_keywords = ['unique', 'not_null', 'accepted_values', 'relationships']

        for keyword in test_keywords:
            if keyword.lower() in response.lower():
                # Find associated column
                pattern = rf'(\w+).*{keyword}'
                matches = re.findall(pattern, response, re.IGNORECASE)
                for col in matches[:5]:  # Limit to 5 per test type
                    tests.append({
                        "column": col,
                        "test": keyword
                    })

        return tests

    def _determine_materialization(self, sql: str, response: str) -> str:
        """Determine appropriate materialization strategy."""
        sql_lower = sql.lower()
        response_lower = response.lower()

        # Check for incremental patterns
        if any(kw in sql_lower for kw in ['updated_at', 'created_at', 'modified_date']):
            if 'incremental' in response_lower:
                return "incremental"

        # Check for aggregations suggesting table
        if any(kw in sql_lower for kw in ['sum(', 'count(', 'avg(', 'group by']):
            return "table"

        # Check for explicit mentions
        if 'materialization' in response_lower:
            for mat in ['table', 'incremental', 'ephemeral']:
                if mat in response_lower:
                    return mat

        return "view"

    def generate_model_file(self, model: DBTModel) -> str:
        """Generate DBT model SQL file content."""
        config_parts = [f"materialized='{model.materialization}'"]

        if model.tags:
            config_parts.append(f"tags={model.tags}")

        config = ", ".join(config_parts)

        sql_content = f"""{{{{
  config(
    {config}
  )
}}}}

-- Model: {model.name}
-- Description: {model.description}
-- Generated by LLM ETL Optimizer

{model.sql}
"""
        return sql_content

    def generate_schema_yaml(self, model: DBTModel) -> str:
        """Generate DBT schema YAML content."""
        schema = {
            "version": 2,
            "models": [{
                "name": model.name,
                "description": model.description,
                "columns": []
            }]
        }

        for col in model.columns:
            col_def = {
                "name": col.get("name"),
                "description": col.get("description", "")
            }

            # Add tests for this column
            col_tests = [t["test"] for t in model.tests if t.get("column") == col.get("name")]
            if col_tests:
                col_def["tests"] = col_tests

            schema["models"][0]["columns"].append(col_def)

        return yaml.dump(schema, default_flow_style=False, sort_keys=False)

    def save_model(self, model: DBTModel, output_dir: Optional[Path] = None) -> dict:
        """
        Save DBT model files to disk.

        Args:
            model: DBTModel to save
            output_dir: Optional output directory override

        Returns:
            Dict with paths to created files
        """
        output_dir = output_dir or self.target_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        # Determine subdirectory based on model prefix
        subdir = "staging"
        for layer, prefix in self.MODEL_PREFIXES.items():
            if model.name.startswith(prefix):
                subdir = layer
                break

        model_dir = output_dir / subdir
        model_dir.mkdir(exist_ok=True)

        # Save SQL file
        sql_path = model_dir / f"{model.name}.sql"
        sql_path.write_text(self.generate_model_file(model))

        # Save schema YAML
        schema_path = model_dir / f"_schema_{model.name}.yml"
        schema_path.write_text(self.generate_schema_yaml(model))

        return {
            "sql_file": str(sql_path),
            "schema_file": str(schema_path)
        }


# Convenience function
def generate_dbt_model(llm_response: str, output_dir: str = "models") -> dict:
    """Quick generation of DBT model from LLM response."""
    generator = DBTGenerator(output_dir)
    model = generator.parse_llm_output(llm_response)
    return generator.save_model(model)
