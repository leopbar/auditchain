"""Data quality validation for financial line items during ingestion.

Inspired by the XBRL US Data Quality Committee (DQC) rules.
Validates facts before they are bulk-upserted into financial_line_items.

Approach: mark, do not block.
  - Suspicious values receive a quality_flag describing the issue.
  - They are still stored in the database for auditability.
  - _get_value_for_concept in financial_data.py prefers NULL (clean) rows.

Four validation layers
----------------------
1. Sign checks     — values that should always be positive/non-negative.
2. Period duration — income/cash-flow items must cover ~12 months.
3. Cross-concept   — intra-period sanity (e.g. cost < revenue).
4. YoY plausibility — compare against prior filing to detect partial data.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from auditchain.core.logging import get_logger
from auditchain.data.sec_models import FactValue

logger = get_logger(__name__)

# ── constants ────────────────────────────────────────────────────────────────

# Concepts that should never have a negative value (DQC Rule 0015).
ALWAYS_POSITIVE = {
    # Revenue
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
    # Assets
    "Assets",
    "AssetsCurrent",
    "PropertyPlantAndEquipmentNet",
    "Goodwill",
    "IntangibleAssetsNetExcludingGoodwill",
    # Working capital components
    "InventoryNet",
    "InventoryFinishedGoodsNetOfReserves",
    "AccountsReceivableNetCurrent",
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    # Liabilities — always reported as positive numbers
    "LiabilitiesNoncurrent",
    # Share counts
    "CommonStockSharesOutstanding",
    "WeightedAverageNumberOfSharesOutstandingBasic",
    "WeightedAverageNumberOfSharesOutstandingDiluted",
}

# Income statement and cash flow items must have a duration.
FLOW_STATEMENTS = {"income_statement", "cash_flow"}

# Concepts to check for YoY plausibility (3x jump / 90% drop).
YOY_CHECK_CONCEPTS = {
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
    "NetIncomeLoss",
    "Assets",
    "NetCashProvidedByUsedInOperatingActivities",
}

MIN_ANNUAL_DAYS = 300   # ~10 months — allows short fiscal years
MAX_ANNUAL_DAYS = 400   # ~13 months — allows long first fiscal years
YOY_JUMP_FACTOR = 3.0   # 3× increase triggers flag
YOY_DROP_FACTOR = 0.10  # >90% drop triggers flag


# ── public API ────────────────────────────────────────────────────────────────

def validate_and_flag(
    fact_values: list[tuple[str, FactValue]],
    prior_values: dict[str, float],
    concept_to_statement: dict[str, str],
) -> dict[tuple, str | None]:
    """Validate facts and return a quality flag per (concept, end_date, frame).

    Args:
        fact_values:          All (concept_name, FactValue) pairs for one filing.
        prior_values:         Concept → value from the immediately prior filing
                              (empty dict if no prior filing exists).
        concept_to_statement: Mapping used during ingestion.

    Returns:
        Dict of (concept_name, period_end, frame) → quality_flag string or None.
        None means the value passed all checks (clean).
    """
    flags: dict[tuple, str | None] = {}

    # Index facts by (concept, end, frame) for cross-concept checks
    by_key: dict[tuple, FactValue] = {}
    by_concept_end: dict[tuple, list[FactValue]] = defaultdict(list)

    for concept_name, fact in fact_values:
        frame = fact.frame or ""
        key = (concept_name, fact.end, frame)
        by_key[key] = fact
        by_concept_end[(concept_name, fact.end)].append(fact)

    # Group by period end for cross-concept comparisons
    values_by_end: dict[date, dict[str, float]] = defaultdict(dict)
    for concept_name, fact in fact_values:
        values_by_end[fact.end][concept_name] = fact.val

    for concept_name, fact in fact_values:
        frame = fact.frame or ""
        key = (concept_name, fact.end, frame)
        statement = concept_to_statement.get(concept_name, "")
        flag = None

        # ── Layer 1: sign checks ──────────────────────────────────────────────
        if concept_name in ALWAYS_POSITIVE and fact.val < 0:
            flag = "negative_value"
            logger.warning(
                "quality_flag_negative_value",
                concept=concept_name,
                value=fact.val,
                period_end=str(fact.end),
            )

        # ── Layer 2: period duration ──────────────────────────────────────────
        if flag is None and statement in FLOW_STATEMENTS:
            if fact.start is None:
                flag = "missing_period_start"
                logger.warning(
                    "quality_flag_missing_period_start",
                    concept=concept_name,
                    period_end=str(fact.end),
                )
            else:
                duration_days = (fact.end - fact.start).days
                if not (MIN_ANNUAL_DAYS <= duration_days <= MAX_ANNUAL_DAYS):
                    flag = "duration_mismatch"
                    logger.warning(
                        "quality_flag_duration_mismatch",
                        concept=concept_name,
                        period_start=str(fact.start),
                        period_end=str(fact.end),
                        duration_days=duration_days,
                    )

        # ── Layer 4: YoY plausibility ────────────────────────────────────────
        # (Layer 3 cross-concept handled below, after the main loop)
        if flag is None and concept_name in YOY_CHECK_CONCEPTS and prior_values:
            prior_val = prior_values.get(concept_name)
            if prior_val and prior_val != 0 and fact.val != 0:
                ratio = abs(fact.val / prior_val)
                if ratio > YOY_JUMP_FACTOR:
                    flag = "yoy_3x_jump"
                    logger.warning(
                        "quality_flag_yoy_3x_jump",
                        concept=concept_name,
                        current=fact.val,
                        prior=prior_val,
                        ratio=round(ratio, 2),
                        period_end=str(fact.end),
                    )
                elif ratio < YOY_DROP_FACTOR:
                    flag = "yoy_90pct_drop"
                    logger.warning(
                        "quality_flag_yoy_90pct_drop",
                        concept=concept_name,
                        current=fact.val,
                        prior=prior_val,
                        ratio=round(ratio, 2),
                        period_end=str(fact.end),
                    )

        flags[key] = flag

    # ── Layer 3: cross-concept checks ────────────────────────────────────────
    # Run after the main loop so all values for a period are available.
    for end_date, period_vals in values_by_end.items():
        revenue = _revenue_value(period_vals)
        cost = _cost_value(period_vals)

        if revenue is not None and cost is not None and cost > revenue * 1.05:
            for cost_concept in ("CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"):
                if cost_concept in period_vals:
                    k = (cost_concept, end_date, "")
                    if k in flags and flags[k] is None:
                        flags[k] = "cost_exceeds_revenue"
                        logger.warning(
                            "quality_flag_cost_exceeds_revenue",
                            cost_concept=cost_concept,
                            cost=cost,
                            revenue=revenue,
                            period_end=str(end_date),
                        )

        # Gross profit negative (rare but possible — low-severity flag)
        gross = period_vals.get("GrossProfit")
        if gross is not None and gross < 0:
            k = ("GrossProfit", end_date, "")
            if k in flags and flags[k] is None:
                flags[k] = "negative_gross_profit"
                logger.warning(
                    "quality_flag_negative_gross_profit",
                    value=gross,
                    period_end=str(end_date),
                )

    # ── Layer 5: cross-statement checks ─────────────────────────────────────
    # These compare balance-sheet and cash-flow values within the same filing
    # and against the immediately prior period (prior_values).

    # Collect the single most recent period's values (latest end_date)
    if values_by_end:
        latest_end = max(values_by_end)
        latest = values_by_end[latest_end]

        # 5a ── Cash flow equation
        # prior_cash + CFO + CFI + CFF ≈ current_cash  (10 % tolerance)
        _check_cash_flow_equation(flags, latest, latest_end, prior_values)

        # 5b ── Cash balance-sheet vs cash-flow statement (DQC 0057)
        # The two cash concepts should agree within 20 % (restricted cash diff)
        _check_cash_bs_cf(flags, latest, latest_end)

        # 5c ── Retained earnings bridge
        # RE(t) ≈ RE(t-1) + NetIncome(t)  (30 % tolerance for dividends/buybacks)
        _check_retained_earnings_bridge(flags, latest, latest_end, prior_values)

    flagged = sum(1 for v in flags.values() if v is not None)
    if flagged:
        logger.info("ingestion_quality_flags_raised", flagged=flagged, total=len(flags))

    return flags


# ── helpers ───────────────────────────────────────────────────────────────────

def _revenue_value(vals: dict[str, float]) -> float | None:
    for concept in ("RevenueFromContractWithCustomerExcludingAssessedTax",
                    "Revenues", "SalesRevenueNet"):
        if concept in vals:
            return vals[concept]
    return None


def _cost_value(vals: dict[str, float]) -> float | None:
    for concept in ("CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"):
        if concept in vals:
            return vals[concept]
    return None


def _cash_value(vals: dict[str, float]) -> float | None:
    """Return cash balance from a period's values, preferring the narrower concept."""
    for concept in (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ):
        if concept in vals:
            return vals[concept]
    return None


def _check_cash_flow_equation(
    flags: dict[tuple, str | None],
    latest: dict[str, float],
    latest_end,
    prior_values: dict[str, float],
) -> None:
    """Layer 5a: prior_cash + CFO + CFI + CFF ≈ current_cash (10 % tolerance)."""
    current_cash = _cash_value(latest)
    cfo = latest.get("NetCashProvidedByUsedInOperatingActivities")
    cfi = latest.get("NetCashProvidedByUsedInInvestingActivities")
    cff = latest.get("NetCashProvidedByUsedInFinancingActivities")
    prior_cash = _cash_value(prior_values) if prior_values else None

    if None in (current_cash, cfo, cfi, cff, prior_cash):
        return

    expected = prior_cash + cfo + cfi + cff  # type: ignore[operator]
    denom = max(abs(current_cash), abs(expected), 1.0)  # type: ignore[arg-type]
    if abs(expected - current_cash) / denom > 0.10:  # type: ignore[operator]
        k = ("NetCashProvidedByUsedInOperatingActivities", latest_end, "")
        if flags.get(k) is None:
            flags[k] = "cash_flow_equation_error"
            logger.warning(
                "quality_flag_cash_flow_equation_error",
                expected=round(expected),
                actual=round(current_cash),  # type: ignore[arg-type]
                period_end=str(latest_end),
            )


def _check_cash_bs_cf(
    flags: dict[tuple, str | None],
    latest: dict[str, float],
    latest_end,
) -> None:
    """Layer 5b: CashAndCash... ≈ CashCashEquiv... (20 % tolerance, DQC 0057)."""
    cash_narrow = latest.get("CashAndCashEquivalentsAtCarryingValue")
    cash_broad = latest.get("CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents")

    if cash_narrow is None or cash_broad is None:
        return
    if cash_narrow == 0 and cash_broad == 0:
        return

    denom = max(abs(cash_narrow), abs(cash_broad), 1.0)
    if abs(cash_narrow - cash_broad) / denom > 0.20:
        k = ("CashAndCashEquivalentsAtCarryingValue", latest_end, "")
        if flags.get(k) is None:
            flags[k] = "cash_bs_cf_mismatch"
            logger.warning(
                "quality_flag_cash_bs_cf_mismatch",
                cash_narrow=cash_narrow,
                cash_broad=cash_broad,
                period_end=str(latest_end),
            )


def _check_retained_earnings_bridge(
    flags: dict[tuple, str | None],
    latest: dict[str, float],
    latest_end,
    prior_values: dict[str, float],
) -> None:
    """Layer 5c: RE(t) ≈ RE(t-1) + NetIncome(t) (30 % tolerance for dividends)."""
    current_re = latest.get("RetainedEarningsAccumulatedDeficit")
    net_income = latest.get("NetIncomeLoss")
    prior_re = prior_values.get("RetainedEarningsAccumulatedDeficit") if prior_values else None

    if None in (current_re, net_income, prior_re):
        return

    expected_re = prior_re + net_income  # type: ignore[operator]
    denom = max(abs(current_re), abs(expected_re), 1.0)  # type: ignore[arg-type]
    if abs(expected_re - current_re) / denom > 0.30:  # type: ignore[operator]
        k = ("RetainedEarningsAccumulatedDeficit", latest_end, "")
        if flags.get(k) is None:
            flags[k] = "retained_earnings_discontinuity"
            logger.warning(
                "quality_flag_retained_earnings_discontinuity",
                expected=round(expected_re),
                actual=round(current_re),  # type: ignore[arg-type]
                period_end=str(latest_end),
            )
