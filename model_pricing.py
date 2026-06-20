"""Configurable model pricing used for local operational cost estimates."""

from __future__ import annotations

from dataclasses import dataclass


PRICING_AS_OF = "2026-06-19"


@dataclass(frozen=True)
class ModelPricing:
    model: str
    input_per_million: float
    output_per_million: float
    source_url: str

    def estimate(self, *, input_tokens: int, output_tokens: int) -> float:
        return (
            (int(input_tokens or 0) / 1_000_000) * self.input_per_million
            + (int(output_tokens or 0) / 1_000_000) * self.output_per_million
        )


MODEL_PRICING = {
    "gpt-5.5": ModelPricing(
        model="gpt-5.5",
        input_per_million=5.00,
        output_per_million=30.00,
        source_url="https://openai.com/api/pricing/",
    ),
    "gpt-5.4": ModelPricing(
        model="gpt-5.4",
        input_per_million=2.50,
        output_per_million=15.00,
        source_url="https://openai.com/api/pricing/",
    ),
    "gpt-5.4-mini": ModelPricing(
        model="gpt-5.4-mini",
        input_per_million=0.75,
        output_per_million=4.50,
        source_url="https://openai.com/api/pricing/",
    ),
}


def pricing_for_model(model: str | None) -> ModelPricing | None:
    model = (model or "").strip()
    if not model:
        return None
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]
    for known_model, pricing in sorted(MODEL_PRICING.items(), key=lambda item: len(item[0]), reverse=True):
        if model.startswith(known_model):
            return pricing
    return None
