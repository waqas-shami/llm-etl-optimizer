"""
LLM Orchestrator Module

Manages multi-model inference with fallback, rate limiting,
caching, and cost optimization for ETL optimization tasks.
"""

import os
import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMResponse:
    """Structured response from LLM."""

    content: str
    model_used: str
    tokens_used: int
    latency_ms: float
    cached: bool = False


@dataclass
class OptimizationRequest:
    """Request structure for SQL optimization."""

    sql: str
    context: Optional[str] = None
    target_dialect: str = "snowflake"
    include_tests: bool = True
    include_docs: bool = True


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str) -> LLMResponse:
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider implementation."""

    def __init__(self, model: str = "gpt-4-turbo"):
        self.model = model
        self.client = ChatOpenAI(
            model=model,
            temperature=0.1,
            max_tokens=4096
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def generate(self, prompt: str, system_prompt: str) -> LLMResponse:
        start_time = datetime.now()

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]

        response = self.client.invoke(messages)

        latency = (datetime.now() - start_time).total_seconds() * 1000

        return LLMResponse(
            content=response.content,
            model_used=self.model,
            tokens_used=response.response_metadata.get('token_usage', {}).get('total_tokens', 0),
            latency_ms=latency
        )


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider implementation."""

    def __init__(self, model: str = "claude-3-sonnet-20240229"):
        self.model = model
        self.client = ChatAnthropic(
            model=model,
            temperature=0.1,
            max_tokens=4096
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def generate(self, prompt: str, system_prompt: str) -> LLMResponse:
        start_time = datetime.now()

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]

        response = self.client.invoke(messages)

        latency = (datetime.now() - start_time).total_seconds() * 1000

        return LLMResponse(
            content=response.content,
            model_used=self.model,
            tokens_used=response.response_metadata.get('usage', {}).get('total_tokens', 0),
            latency_ms=latency
        )


class ResponseCache:
    """Simple in-memory cache for LLM responses."""

    def __init__(self, ttl_hours: int = 24):
        self.cache: dict[str, tuple[LLMResponse, datetime]] = {}
        self.ttl = timedelta(hours=ttl_hours)

    def _hash_key(self, prompt: str, system_prompt: str) -> str:
        combined = f"{system_prompt}|||{prompt}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def get(self, prompt: str, system_prompt: str) -> Optional[LLMResponse]:
        key = self._hash_key(prompt, system_prompt)
        if key in self.cache:
            response, timestamp = self.cache[key]
            if datetime.now() - timestamp < self.ttl:
                response.cached = True
                return response
            del self.cache[key]
        return None

    def set(self, prompt: str, system_prompt: str, response: LLMResponse) -> None:
        key = self._hash_key(prompt, system_prompt)
        self.cache[key] = (response, datetime.now())

    def clear(self) -> None:
        self.cache.clear()


class LLMOrchestrator:
    """
    Orchestrates LLM calls with multi-provider support,
    fallback handling, and caching.
    """

    SYSTEM_PROMPT = """You are an expert data engineer specializing in SQL optimization and DBT development.
Your task is to analyze SQL queries and generate optimized, well-documented DBT models.

Follow these principles:
1. Use CTEs instead of subqueries for readability
2. Apply appropriate materializations (view, table, incremental)
3. Include column descriptions and model documentation
4. Add data quality tests (unique, not_null, accepted_values, relationships)
5. Follow naming conventions: stg_ for staging, int_ for intermediate, fct_ for facts, dim_ for dimensions
6. Optimize for the target data warehouse (Snowflake, BigQuery, Redshift)

Output Format:
- DBT model SQL code
- YAML documentation
- Explanation of optimizations made
- Suggested tests"""

    def __init__(
        self,
        primary_model: str = None,
        fallback_model: str = None,
        enable_cache: bool = True
    ):
        primary_model = primary_model or os.getenv("PRIMARY_MODEL", "gpt-4-turbo")
        fallback_model = fallback_model or os.getenv("FALLBACK_MODEL", "claude-3-sonnet-20240229")

        self.providers = {
            "primary": self._create_provider(primary_model),
            "fallback": self._create_provider(fallback_model)
        }

        self.cache = ResponseCache() if enable_cache else None
        self.stats = {"primary_calls": 0, "fallback_calls": 0, "cache_hits": 0}

    def _create_provider(self, model: str) -> LLMProvider:
        """Create appropriate provider based on model name."""
        if model.startswith("gpt"):
            return OpenAIProvider(model)
        elif model.startswith("claude"):
            return AnthropicProvider(model)
        else:
            raise ValueError(f"Unknown model: {model}")

    def optimize_sql(self, request: OptimizationRequest) -> LLMResponse:
        """
        Main entry point for SQL optimization.

        Args:
            request: OptimizationRequest with SQL and configuration

        Returns:
            LLMResponse with optimized DBT model
        """
        prompt = self._build_prompt(request)

        # Check cache first
        if self.cache:
            cached = self.cache.get(prompt, self.SYSTEM_PROMPT)
            if cached:
                self.stats["cache_hits"] += 1
                return cached

        # Try primary provider
        try:
            response = self.providers["primary"].generate(prompt, self.SYSTEM_PROMPT)
            self.stats["primary_calls"] += 1
        except Exception as e:
            print(f"Primary provider failed: {e}, falling back...")
            response = self.providers["fallback"].generate(prompt, self.SYSTEM_PROMPT)
            self.stats["fallback_calls"] += 1

        # Cache response
        if self.cache:
            self.cache.set(prompt, self.SYSTEM_PROMPT, response)

        return response

    def _build_prompt(self, request: OptimizationRequest) -> str:
        """Build optimization prompt from request."""
        prompt_parts = [
            f"## Input SQL\n```sql\n{request.sql}\n```",
            f"\n## Target Dialect: {request.target_dialect}",
        ]

        if request.context:
            prompt_parts.append(f"\n## Business Context\n{request.context}")

        prompt_parts.append("\n## Required Output:")
        prompt_parts.append("1. Optimized DBT model SQL")

        if request.include_docs:
            prompt_parts.append("2. YAML schema documentation")

        if request.include_tests:
            prompt_parts.append("3. Suggested data quality tests")

        prompt_parts.append("4. Explanation of optimizations made")

        return "\n".join(prompt_parts)

    def get_stats(self) -> dict:
        """Return usage statistics."""
        return self.stats.copy()


# Convenience function
def optimize(sql: str, **kwargs) -> LLMResponse:
    """Quick optimization of SQL query."""
    orchestrator = LLMOrchestrator()
    request = OptimizationRequest(sql=sql, **kwargs)
    return orchestrator.optimize_sql(request)
