"""Model-aware pricing for LLM token usage.

Single source of truth for turning token counts into a USD cost.

Important distinction:
- Token counts are *measured* — they come straight from the OpenAI API
  (``usage_metadata`` on each message). They are not estimates.
- The per-token *price* is *published* by OpenAI on its pricing page and is
  not returned by the API. We therefore keep a price table. The live,
  admin-updatable values live in the ``model_prices`` database table; the
  ``DEFAULT_PRICE_MAP`` below is the dated baseline used as a fallback when
  that table is empty or unreachable.

Pricing reference (USD per 1M tokens), OpenAI — captured 2026-05-29
(https://openai.com/api/pricing):
    gpt-4o                  input 2.50   output 10.00
    gpt-4o-mini             input 0.15   output  0.60
    text-embedding-3-small  input 0.02   output  0.00

The key insight behind the design: instead of hardcoding "this node uses
model X", callers should pass the model name that the API actually reported
for each response. That keeps the cost correct by construction even if a
node's model is reassigned later.
"""

from __future__ import annotations

from dataclasses import dataclass

from auditchain.core.logging import get_logger

logger = get_logger(__name__)

ONE_MILLION = 1_000_000


@dataclass(frozen=True)
class ModelPrice:
    """USD price per 1 million tokens for a single model."""

    input_per_1m: float
    output_per_1m: float
    source: str = "default"


# Dated baseline. Used only when the database table has no entry for a model.
# Keys must be lowercase canonical model names (no dated snapshot suffix).
DEFAULT_PRICE_MAP: dict[str, ModelPrice] = {
    "gpt-4o": ModelPrice(2.50, 10.00, "default (OpenAI 2026-05-29)"),
    "gpt-4o-mini": ModelPrice(0.15, 0.60, "default (OpenAI 2026-05-29)"),
    "text-embedding-3-small": ModelPrice(0.02, 0.0, "default (OpenAI 2026-05-29)"),
}


def normalize_model_name(model: str | None) -> str | None:
    """Lowercase and trim a model name. Returns None for empty input."""
    if not model:
        return None
    return model.strip().lower()


def price_for_model(
    model: str | None, price_map: dict[str, ModelPrice]
) -> tuple[ModelPrice | None, str | None]:
    """Resolve the price for a model name.

    The OpenAI API returns dated snapshots (e.g. ``gpt-4o-2024-08-06`` or
    ``gpt-4o-mini-2024-07-18``), so an exact lookup is not enough. We fall
    back to the longest matching key prefix, which makes ``gpt-4o-mini-...``
    resolve to ``gpt-4o-mini`` rather than ``gpt-4o``.

    Returns a ``(ModelPrice | None, matched_key | None)`` tuple.
    """
    norm = normalize_model_name(model)
    if norm is None:
        return None, None
    if norm in price_map:
        return price_map[norm], norm
    candidates = [key for key in price_map if norm.startswith(key)]
    if candidates:
        best = max(candidates, key=len)
        return price_map[best], best
    return None, None


def estimate_cost(
    model: str | None,
    tokens_in: int,
    tokens_out: int,
    price_map: dict[str, ModelPrice],
    *,
    fallback_model: str | None = None,
) -> float:
    """Return the USD cost for the given token counts under ``model``'s price.

    Resolution order:
    1. The model's own price (exact or prefix match).
    2. ``fallback_model``'s price, if the model is unknown (used when a
       response carries no model name — we fall back to the node's configured
       model rather than guessing).
    3. As a last resort, the most expensive known price, logged as a warning.
       We never silently price an unknown model at zero.
    """
    price, matched = price_for_model(model, price_map)

    if price is None and fallback_model:
        price, matched = price_for_model(fallback_model, price_map)
        if price is not None:
            logger.warning(
                "pricing_unknown_model_fallback", requested=model, fallback=matched
            )

    if price is None:
        if price_map:
            matched = max(price_map, key=lambda key: price_map[key].output_per_1m)
            price = price_map[matched]
        else:
            matched, price = "gpt-4o", DEFAULT_PRICE_MAP["gpt-4o"]
        logger.warning(
            "pricing_unknown_model_conservative", requested=model, priced_as=matched
        )

    return (tokens_in / ONE_MILLION) * price.input_per_1m + (
        tokens_out / ONE_MILLION
    ) * price.output_per_1m
