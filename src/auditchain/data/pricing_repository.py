"""Repository for the ``model_prices`` table.

Holds the live, admin-updatable LLM prices. The cost meter loads a price map
from here (merged over the dated defaults in ``core.pricing``) so token usage
is priced by the model that actually produced it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from auditchain.core.logging import get_logger
from auditchain.core.pricing import DEFAULT_PRICE_MAP, ModelPrice, normalize_model_name
from auditchain.data.database import get_session
from auditchain.data.models import ModelPriceORM

logger = get_logger(__name__)


class PricingRepository:
    """Manage persisted per-model prices."""

    def __init__(self, session: Session):
        self.session = session

    def get_all(self) -> list[ModelPriceORM]:
        """Return all stored prices, ordered by model name."""
        stmt = select(ModelPriceORM).order_by(ModelPriceORM.model_name)
        return list(self.session.execute(stmt).scalars().all())

    def get_price_map(self) -> dict[str, ModelPrice]:
        """Return DB prices merged over the dated defaults (DB wins)."""
        price_map = dict(DEFAULT_PRICE_MAP)
        for row in self.get_all():
            key = normalize_model_name(row.model_name)
            if not key:
                continue
            price_map[key] = ModelPrice(
                input_per_1m=float(row.input_cost_per_1m),
                output_per_1m=float(row.output_cost_per_1m),
                source=row.source or "database",
            )
        return price_map

    def upsert(
        self,
        model_name: str,
        input_per_1m: float,
        output_per_1m: float,
        source: str | None = None,
    ) -> ModelPriceORM:
        """Insert or update the price for a single model (keyed by name)."""
        key = normalize_model_name(model_name)
        if not key:
            raise ValueError("model_name cannot be empty")

        row = self.session.get(ModelPriceORM, key)
        if row is None:
            row = ModelPriceORM(model_name=key)
            self.session.add(row)
        row.input_cost_per_1m = Decimal(str(input_per_1m))
        row.output_cost_per_1m = Decimal(str(output_per_1m))
        row.source = source
        row.updated_at = datetime.now(timezone.utc)
        self.session.flush()
        return row


def load_price_map() -> dict[str, ModelPrice]:
    """Load the price map, opening a short-lived session.

    Falls back to the dated defaults on any database error so the cost meter
    never crashes a running audit over a transient DB issue.
    """
    try:
        with get_session() as session:
            return PricingRepository(session).get_price_map()
    except Exception:
        logger.warning("pricing_load_fallback_defaults", exc_info=True)
        return dict(DEFAULT_PRICE_MAP)
