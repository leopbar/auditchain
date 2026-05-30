"""Model-aware cost summarisation for graph nodes.

Replaces the previous "one hardcoded price for everything" approach. Each AI
message is priced by the model that the OpenAI API reported as having produced
it (``response_metadata['model_name']``), using the live price map from the
database. Token counts are measured; only the per-token price is looked up.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import AIMessage

from auditchain.core.config import get_settings
from auditchain.core.logging import get_logger
from auditchain.core.pricing import estimate_cost
from auditchain.data.pricing_repository import load_price_map

logger = get_logger(__name__)


@dataclass
class UsageSummary:
    """Aggregated token usage and USD cost for a single node's messages."""

    tokens_input: int
    tokens_output: int
    total_tokens: int
    cost_usd: float


def summarize_usage(messages: list) -> UsageSummary:
    """Sum tokens and cost across the AI messages produced in a node.

    Each AI message is priced by the model the API reported (per-message),
    falling back to the configured smart model when a message carries no model
    name — a conservative default, since the smart model is the pricier one.
    """
    price_map = load_price_map()
    fallback_model = get_settings().llm_smart_model

    tokens_in = 0
    tokens_out = 0
    cost = 0.0

    for msg in messages:
        if not isinstance(msg, AIMessage) or not msg.usage_metadata:
            continue
        in_tok = msg.usage_metadata.get("input_tokens", 0) or 0
        out_tok = msg.usage_metadata.get("output_tokens", 0) or 0
        model = (msg.response_metadata or {}).get("model_name")
        tokens_in += in_tok
        tokens_out += out_tok
        cost += estimate_cost(
            model, in_tok, out_tok, price_map, fallback_model=fallback_model
        )

    return UsageSummary(
        tokens_input=tokens_in,
        tokens_output=tokens_out,
        total_tokens=tokens_in + tokens_out,
        cost_usd=cost,
    )
