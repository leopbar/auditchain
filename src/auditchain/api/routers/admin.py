"""Admin-only router for user management and system control."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from auditchain.api.schemas.pricing import (
    ModelPriceOut,
    PriceChange,
    PricingListResponse,
    PricingRefreshResponse,
)
from auditchain.auth import repository, schemas, service
from auditchain.auth.dependencies import require_admin
from auditchain.core.logging import get_logger
from auditchain.core.openai_pricing import PricingScrapeError, scrape_openai_prices
from auditchain.core.pricing import DEFAULT_PRICE_MAP
from auditchain.data.database import get_async_session, get_session
from auditchain.data.pricing_repository import PricingRepository

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)]
)


@router.get("/users", response_model=list[schemas.UserOut])
async def list_users(session: AsyncSession = Depends(get_async_session)):
    """List all registered users in the system."""
    return await repository.get_all_users(session)


@router.post("/users", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
async def create_new_user(
    user_data: schemas.UserCreate,
    session: AsyncSession = Depends(get_async_session),
):
    """Create a new user with hashed password."""
    hashed = service.hash_password(user_data.password)
    return await repository.create_user(session, user_data, hashed)


@router.delete("/users/{user_id}/deactivate")
async def deactivate(user_id: UUID, session: AsyncSession = Depends(get_async_session)):
    """Deactivate a user account without deleting it."""
    success = await repository.deactivate_user(session, user_id)
    if not success:
        return {"message": "User not found or already inactive"}
    return {"message": "user deactivated"}


@router.delete("/users/{user_id}")
async def delete(user_id: UUID, session: AsyncSession = Depends(get_async_session)):
    """Permanently delete a user from the system."""
    success = await repository.delete_user(session, user_id)
    if not success:
        return {"message": "User not found"}
    return {"message": "user deleted"}


# ── Model pricing ────────────────────────────────────────────────────────────
# OpenAI has no official pricing API, so prices live in the `model_prices` table
# (seeded with a dated baseline) and can be refreshed by scraping OpenAI's
# public pricing page. These endpoints are synchronous on purpose: they use the
# sync session + the `requests`-based scraper, and FastAPI runs them in a
# threadpool. The router-level `require_admin` dependency still applies.


def _effective_prices(session: Session) -> list[ModelPriceOut]:
    """Current price table: DB rows, plus any in-code defaults not yet stored."""
    repo = PricingRepository(session)
    stored = {row.model_name: row for row in repo.get_all()}

    prices = [ModelPriceOut.model_validate(row) for row in stored.values()]
    for name, price in DEFAULT_PRICE_MAP.items():
        if name not in stored:
            prices.append(
                ModelPriceOut(
                    model_name=name,
                    input_cost_per_1m=price.input_per_1m,
                    output_cost_per_1m=price.output_per_1m,
                    source=price.source,
                    updated_at=None,
                )
            )
    prices.sort(key=lambda p: p.model_name)
    return prices


@router.get("/pricing", response_model=PricingListResponse)
def get_model_pricing():
    """Return the current per-model token prices used by the cost meter."""
    with get_session() as session:
        return PricingListResponse(prices=_effective_prices(session))


_PRICE_EPSILON = 1e-9


@router.post("/pricing/refresh", response_model=PricingRefreshResponse)
def refresh_model_pricing():
    """Scrape OpenAI's pricing page and update stored prices.

    Returns one of three outcomes (see ``PricingRefreshResponse.status``):
    "updated" with the list of changes, "no_changes", or "error". On any
    failure the stored prices are left untouched — never a fabricated number.
    """
    try:
        try:
            scraped, source_url = scrape_openai_prices()
        except PricingScrapeError as exc:
            logger.warning("pricing_refresh_failed", error=str(exc))
            with get_session() as session:
                current = _effective_prices(session)
            return PricingRefreshResponse(
                status="error",
                message=(
                    "Update failed: could not access OpenAI's pricing page. "
                    "Existing prices were kept. Please contact the administrator."
                ),
                changes=[],
                source_url=None,
                prices=current,
            )

        stamp = datetime.now(timezone.utc).date().isoformat()
        changes: list[PriceChange] = []
        with get_session() as session:
            repo = PricingRepository(session)
            existing = {row.model_name: row for row in repo.get_all()}

            for item in scraped:
                prev = existing.get(item.model_name)
                prev_in = float(prev.input_cost_per_1m) if prev else None
                prev_out = float(prev.output_cost_per_1m) if prev else None
                differs = (
                    prev is None
                    or abs(prev_in - item.input_per_1m) > _PRICE_EPSILON
                    or abs(prev_out - item.output_per_1m) > _PRICE_EPSILON
                )
                if differs:
                    repo.upsert(
                        item.model_name,
                        item.input_per_1m,
                        item.output_per_1m,
                        source=f"OpenAI scrape {stamp} ({source_url})",
                    )
                    changes.append(
                        PriceChange(
                            model_name=item.model_name,
                            old_input_per_1m=prev_in,
                            old_output_per_1m=prev_out,
                            new_input_per_1m=item.input_per_1m,
                            new_output_per_1m=item.output_per_1m,
                        )
                    )
            current = _effective_prices(session)

        if changes:
            logger.info("pricing_refresh_ok", changed=len(changes), source=source_url)
            return PricingRefreshResponse(
                status="updated",
                message=f"Update completed. {len(changes)} price(s) changed.",
                changes=changes,
                source_url=source_url,
                prices=current,
            )

        logger.info("pricing_refresh_no_changes", source=source_url)
        return PricingRefreshResponse(
            status="no_changes",
            message="Update completed, but there were no price changes.",
            changes=[],
            source_url=source_url,
            prices=current,
        )

    except Exception as exc:  # noqa: BLE001 — surface any failure as a clean popup
        logger.error("pricing_refresh_unexpected_error", error=str(exc))
        current: list[ModelPriceOut] = []
        try:
            with get_session() as session:
                current = _effective_prices(session)
        except Exception:
            logger.error("pricing_refresh_load_after_error_failed")
        return PricingRefreshResponse(
            status="error",
            message=(
                "Update failed due to an unexpected error while accessing the "
                "price data. Please contact the administrator."
            ),
            changes=[],
            source_url=None,
            prices=current,
        )
