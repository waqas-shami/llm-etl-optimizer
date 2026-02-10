"""
LLM Service for Live Mode

Handles actual LLM API calls when users provide API keys.
Falls back to demo mode if no key is provided or on errors.
"""

import os
from typing import Optional
from dataclasses import dataclass

# Optional imports - only needed for live mode
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


@dataclass
class LLMResponse:
    """Response from LLM service."""
    dbt_model: str
    yaml_schema: str
    explanation: str
    model_used: str
    tokens_used: int = 0
    from_cache: bool = False


SYSTEM_PROMPT = """You are an expert data engineer specializing in SQL optimization and DBT development.
Transform the provided SQL query into an optimized DBT model following these guidelines:

1. Use CTEs instead of subqueries for readability
2. Follow naming conventions: stg_ for staging, int_ for intermediate, fct_ for facts, dim_ for dimensions
3. Add proper Jinja config block with materialization
4. Include detailed comments explaining business logic
5. Use {{ ref() }} for table references
6. Apply COALESCE for null handling where appropriate

Output format:
1. First, output the complete DBT SQL model wrapped in ```sql blocks
2. Then output a YAML schema file wrapped in ```yaml blocks with:
   - Model description
   - Column descriptions
   - Appropriate tests (unique, not_null, accepted_values)
3. Finally, provide an explanation section with:
   - Summary of changes made
   - Performance considerations
   - Best practices applied
"""


class LLMService:
    """Service for LLM-powered SQL optimization."""

    def __init__(self, openai_key: Optional[str] = None, anthropic_key: Optional[str] = None):
        self.openai_key = openai_key
        self.anthropic_key = anthropic_key
        self.openai_client = None
        self.anthropic_client = None

        if openai_key and OPENAI_AVAILABLE:
            self.openai_client = OpenAI(api_key=openai_key)

        if anthropic_key and ANTHROPIC_AVAILABLE:
            self.anthropic_client = Anthropic(api_key=anthropic_key)

    def optimize_sql(self, sql: str, dialect: str = "snowflake", context: str = "") -> Optional[LLMResponse]:
        """
        Optimize SQL using LLM.

        Args:
            sql: Input SQL query
            dialect: Target SQL dialect
            context: Additional business context

        Returns:
            LLMResponse with optimized DBT model, or None on failure
        """
        prompt = f"""Optimize this SQL query for {dialect} and convert to a DBT model:

```sql
{sql}
```

{f"Business Context: {context}" if context else ""}

Generate the optimized DBT model with schema and explanation."""

        # Try OpenAI first
        if self.openai_client:
            try:
                return self._call_openai(prompt)
            except Exception as e:
                print(f"OpenAI error: {e}")

        # Fall back to Anthropic
        if self.anthropic_client:
            try:
                return self._call_anthropic(prompt)
            except Exception as e:
                print(f"Anthropic error: {e}")

        return None

    def _call_openai(self, prompt: str) -> LLMResponse:
        """Call OpenAI API."""
        response = self.openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=4096
        )

        content = response.choices[0].message.content
        tokens = response.usage.total_tokens if response.usage else 0

        return self._parse_response(content, "gpt-4-turbo", tokens)

    def _call_anthropic(self, prompt: str) -> LLMResponse:
        """Call Anthropic API."""
        response = self.anthropic_client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text
        tokens = response.usage.input_tokens + response.usage.output_tokens

        return self._parse_response(content, "claude-3-sonnet", tokens)

    def _parse_response(self, content: str, model: str, tokens: int) -> LLMResponse:
        """Parse LLM response into structured components."""
        import re

        # Extract SQL block
        sql_match = re.search(r'```sql\n(.*?)```', content, re.DOTALL)
        dbt_model = sql_match.group(1).strip() if sql_match else content

        # Extract YAML block
        yaml_match = re.search(r'```ya?ml\n(.*?)```', content, re.DOTALL)
        yaml_schema = yaml_match.group(1).strip() if yaml_match else self._generate_basic_yaml()

        # Extract explanation (everything after the code blocks)
        explanation = re.sub(r'```.*?```', '', content, flags=re.DOTALL).strip()
        if not explanation:
            explanation = "Model optimized successfully."

        return LLMResponse(
            dbt_model=dbt_model,
            yaml_schema=yaml_schema,
            explanation=explanation,
            model_used=model,
            tokens_used=tokens
        )

    def _generate_basic_yaml(self) -> str:
        """Generate basic YAML if not provided by LLM."""
        return """version: 2

models:
  - name: optimized_model
    description: Auto-generated DBT model
    columns: []
"""


def get_live_response(sql: str, options: dict, api_key: str) -> Optional[dict]:
    """
    Get live LLM response.

    Args:
        sql: Input SQL
        options: Configuration options
        api_key: OpenAI API key

    Returns:
        Dict with dbt_model, yaml_schema, explanation or None
    """
    service = LLMService(openai_key=api_key)
    response = service.optimize_sql(
        sql,
        dialect=options.get("dialect", "snowflake"),
        context=options.get("context", "")
    )

    if response:
        return {
            "dbt_model": response.dbt_model,
            "yaml_schema": response.yaml_schema,
            "explanation": response.explanation
        }

    return None
