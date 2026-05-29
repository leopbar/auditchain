"""Pydantic schemas for the admin pricing endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ModelPriceOut(BaseModel):
    """A single model's price, in USD per 1 million tokens."""

    # `model_` is a Pydantic-protected prefix; opt out so `model_name` is allowed.
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    model_name: str
    input_cost_per_1m: float
    output_cost_per_1m: float
    source: str | None = None
    updated_at: datetime | None = None


class PricingListResponse(BaseModel):
    """Current effective price table used by the cost meter."""

    prices: list[ModelPriceOut]


class PriceChange(BaseModel):
    """A single model whose price changed during a refresh."""

    model_config = ConfigDict(protected_namespaces=())

    model_name: str
    old_input_per_1m: float | None = None
    old_output_per_1m: float | None = None
    new_input_per_1m: float
    new_output_per_1m: float


class PricingRefreshResponse(BaseModel):
    """Result of an attempt to refresh prices from OpenAI.

    ``status`` is one of:
    - "updated"    — scrape succeeded and at least one price changed.
    - "no_changes" — scrape succeeded but every price matched what we had.
    - "error"      — OpenAI's pricing could not be accessed/parsed.
    """

    model_config = ConfigDict(protected_namespaces=())

    status: str  # "updated" | "no_changes" | "error"
    message: str
    changes: list[PriceChange] = []
    source_url: str | None = None
    prices: list[ModelPriceOut]
