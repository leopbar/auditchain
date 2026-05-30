"""Best-effort scraper for OpenAI's published pricing page.

OpenAI does not offer an official pricing API, so the only public source of
truth is its human-facing pricing page. This module fetches that page and
tries to extract the per-1M-token input/output prices for the models we care
about.

This is inherently fragile: the page is built for humans, is largely rendered
client-side with JavaScript, and changes layout without notice. The design
goal here is *honesty over optimism*:

- If a price cannot be parsed and validated, it is dropped.
- If nothing usable is found, ``PricingScrapeError`` is raised so the caller
  keeps the existing stored prices untouched. We never write a guessed or
  fabricated number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests

from auditchain.core.logging import get_logger

logger = get_logger(__name__)

# Candidate URLs, tried in order. The first that returns parseable prices wins.
PRICING_URLS = (
    "https://platform.openai.com/docs/pricing",
    "https://openai.com/api/pricing/",
    "https://openai.com/pricing",
)

# Models we attempt to read. Keys are canonical (lowercase) names.
TARGET_MODELS = ("gpt-4o-mini", "gpt-4o", "text-embedding-3-small")

_REQUEST_TIMEOUT = 15
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# A price token. The dollar sign is mandatory: this is what keeps quantity
# markers like the "1" in "1M tokens" from being mistaken for a price.
_PRICE = r"\$\s*([0-9]+(?:\.[0-9]+)?)"
# Plausibility bounds for a USD-per-1M-tokens figure. Anything outside this is
# almost certainly a mis-parse (a context-window size, a date, etc).
_MIN_PRICE = 0.001
_MAX_PRICE = 10000.0


class PricingScrapeError(RuntimeError):
    """Raised when no usable prices could be scraped."""


@dataclass(frozen=True)
class ScrapedPrice:
    """A single model's prices as read from the pricing page."""

    model_name: str
    input_per_1m: float
    output_per_1m: float


def _find_price_near(window: str, keyword: str) -> float | None:
    """Find a price adjacent to ``keyword`` within ``window`` (either order)."""
    # The separator may contain digits (e.g. the "1M" between price and label)
    # but never another '$', so we don't skip past the next model's price.
    patterns = (
        _PRICE + r"[^$]{0,25}?" + keyword,  # "$2.50 / 1M input"
        keyword + r"[^$]{0,25}?" + _PRICE,  # "input  $2.50"
    )
    for pattern in patterns:
        match = re.search(pattern, window, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    return None


def _is_plausible(price: float | None) -> bool:
    return price is not None and _MIN_PRICE <= price <= _MAX_PRICE


def parse_prices_from_text(
    text: str, models: tuple[str, ...] = TARGET_MODELS
) -> list[ScrapedPrice]:
    """Extract per-model prices from raw page text. Pure and testable.

    For each model, locates the model name and scans a window after it for an
    ``input`` price and an ``output`` price. Embedding models legitimately have
    no output price, so a zero/absent output is accepted only for those.
    """
    results: list[ScrapedPrice] = []

    for model in models:
        # Match the model as a standalone token so "gpt-4o" does not match
        # inside "gpt-4o-mini". A trailing dated snapshot ("-2024-..") is still
        # allowed; a trailing letter (the "-mini" suffix) is not.
        match = re.search(re.escape(model) + r"(?!-?[a-z])", text, re.IGNORECASE)
        if not match:
            continue
        window = text[match.start() : match.start() + 600]

        input_price = _find_price_near(window, "input")
        output_price = _find_price_near(window, "output")
        is_embedding = "embedding" in model

        if not _is_plausible(input_price):
            logger.warning("pricing_scrape_input_implausible", model=model)
            continue
        if is_embedding:
            output_price = output_price if _is_plausible(output_price) else 0.0
        elif not _is_plausible(output_price):
            logger.warning("pricing_scrape_output_implausible", model=model)
            continue

        results.append(
            ScrapedPrice(
                model_name=model,
                input_per_1m=float(input_price),
                output_per_1m=float(output_price),
            )
        )

    return results


def scrape_openai_prices(
    models: tuple[str, ...] = TARGET_MODELS,
) -> tuple[list[ScrapedPrice], str]:
    """Fetch and parse OpenAI pricing. Returns ``(prices, source_url)``.

    Raises ``PricingScrapeError`` if no URL yields usable, validated prices, so
    the caller can keep existing prices rather than overwrite them with junk.
    """
    last_error: str | None = None

    for url in PRICING_URLS:
        try:
            response = requests.get(
                url,
                timeout=_REQUEST_TIMEOUT,
                headers={"User-Agent": _USER_AGENT},
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            last_error = f"{url}: {exc}"
            logger.warning("pricing_scrape_fetch_failed", url=url, error=str(exc))
            continue

        prices = parse_prices_from_text(response.text, models)
        if prices:
            logger.info("pricing_scrape_ok", url=url, count=len(prices))
            return prices, url

        last_error = f"{url}: page fetched but no prices could be parsed"
        logger.warning("pricing_scrape_no_match", url=url)

    raise PricingScrapeError(
        "Could not read prices from OpenAI's pricing page. "
        "The page is JavaScript-rendered and changes layout without notice. "
        f"Last attempt: {last_error}"
    )
