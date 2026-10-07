"""Token accounting and cost calculation engine for multi-provider agent workloads."""

from typing import Dict, List, Optional
from pydantic import BaseModel


class ModelPricing(BaseModel):
    """Pricing rates in USD per 1 Million tokens."""
    prompt_rate_per_m: float
    completion_rate_per_m: float


# Industry baseline pricing table per 1M tokens
MODEL_PRICING_TABLE: Dict[str, ModelPricing] = {
    # OpenAI Models
    "gpt-4o": ModelPricing(prompt_rate_per_m=2.50, completion_rate_per_m=10.00),
    "gpt-4o-mini": ModelPricing(prompt_rate_per_m=0.15, completion_rate_per_m=0.60),
    "gpt-4-turbo": ModelPricing(prompt_rate_per_m=10.00, completion_rate_per_m=30.00),
    "gpt-3.5-turbo": ModelPricing(prompt_rate_per_m=0.50, completion_rate_per_m=1.50),

    # Anthropic Models
    "claude-3-5-sonnet-20241022": ModelPricing(prompt_rate_per_m=3.00, completion_rate_per_m=15.00),
    "claude-3-5-sonnet": ModelPricing(prompt_rate_per_m=3.00, completion_rate_per_m=15.00),
    "claude-3-opus": ModelPricing(prompt_rate_per_m=15.00, completion_rate_per_m=75.00),
    "claude-3-haiku": ModelPricing(prompt_rate_per_m=0.25, completion_rate_per_m=1.25),

    # Google Gemini Models
    "gemini-1.5-pro": ModelPricing(prompt_rate_per_m=1.25, completion_rate_per_m=5.00),
    "gemini-1.5-flash": ModelPricing(prompt_rate_per_m=0.075, completion_rate_per_m=0.30),
    "gemini-2.0-flash": ModelPricing(prompt_rate_per_m=0.10, completion_rate_per_m=0.40),

    # Open Source & Self-Hosted Models
    "qwen3.8-27b": ModelPricing(prompt_rate_per_m=0.35, completion_rate_per_m=0.70),
    "qwen2.5-72b": ModelPricing(prompt_rate_per_m=0.40, completion_rate_per_m=0.80),
    "llama-3.1-70b": ModelPricing(prompt_rate_per_m=0.50, completion_rate_per_m=0.90),
    "llama-3.1-8b": ModelPricing(prompt_rate_per_m=0.08, completion_rate_per_m=0.15),
    "ollama": ModelPricing(prompt_rate_per_m=0.00, completion_rate_per_m=0.00),
    "local": ModelPricing(prompt_rate_per_m=0.00, completion_rate_per_m=0.00)
}

DEFAULT_PRICING = ModelPricing(prompt_rate_per_m=0.50, completion_rate_per_m=1.50)


class CostEngine:
    """Calculates USD cost and token efficiency metrics for agent runs."""

    @staticmethod
    def get_pricing(model_name: Optional[str]) -> ModelPricing:
        """Resolve pricing rates by matching model name or family."""
        if not model_name:
            return DEFAULT_PRICING

        normalized = model_name.lower().strip()
        for key, pricing in MODEL_PRICING_TABLE.items():
            if key in normalized:
                return pricing

        return DEFAULT_PRICING

    @classmethod
    def calculate_span_cost(
        cls,
        prompt_tokens: int,
        completion_tokens: int,
        model_name: Optional[str]
    ) -> float:
        """Calculate USD cost for an individual span."""
        pricing = cls.get_pricing(model_name)
        prompt_cost = (prompt_tokens / 1_000_000.0) * pricing.prompt_rate_per_m
        completion_cost = (completion_tokens / 1_000_000.0) * pricing.completion_rate_per_m
        return round(prompt_cost + completion_cost, 6)

    @classmethod
    def calculate_token_waste_ratio(
        cls,
        spans: List[Dict[str, any]]
    ) -> float:
        """Calculate the proportion of tokens consumed by failed or retried spans."""
        total_tokens = 0
        wasted_tokens = 0

        for s in spans:
            tokens = int(s.get("prompt_tokens", 0)) + int(s.get("completion_tokens", 0))
            total_tokens += tokens
            if s.get("status") in ("error", "retrying") or bool(s.get("error_message")):
                wasted_tokens += tokens

        if total_tokens == 0:
            return 0.0

        return round(wasted_tokens / total_tokens, 4)


cost_engine = CostEngine()
