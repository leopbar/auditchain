"""Quantitative analysis tools for fraud detection and financial risk assessment.

These tools perform mathematical modeling (Beneish, Altman) on structured 
financial data to identify patterns indicative of manipulation or distress.
"""

from langchain_core.tools import tool
from auditchain.core.logging import get_logger
from auditchain.schemas.components import CheckResult, FinancialPeriod

logger = get_logger(__name__)


@tool
def compute_beneish_mscore_simplified(current: FinancialPeriod, prior: FinancialPeriod) -> CheckResult:
    """Calculates a simplified version of the Beneish M-Score.
    
    Requires two consecutive periods. The M-Score is a probabilistic model 
    that uses financial ratios to identify potential earnings manipulation.
    Threshold: M-Score > -1.78 indicates a high probability of manipulation.
    """
    # Essential data for base indices
    if not all([current.revenue, prior.revenue, current.total_assets, prior.total_assets]):
        return CheckResult(
            name="beneish_mscore",
            passed=True,
            notes="Insufficient data for Beneish calculation (requires Revenue and Total Assets for both periods)."
        )

    computed_count = 0

    # 1. DSRI (Days Sales in Receivables Index)
    if current.accounts_receivable is not None and prior.accounts_receivable is not None:
        dsri = (current.accounts_receivable / current.revenue) / (prior.accounts_receivable / prior.revenue)
        computed_count += 1
    else:
        dsri = 1.0

    # 2. GMI (Gross Margin Index)
    if current.gross_profit is not None and prior.gross_profit is not None:
        # Gross Margin = Gross Profit / Revenue
        gmi = (prior.gross_profit / prior.revenue) / (current.gross_profit / current.revenue)
        computed_count += 1
    else:
        gmi = 1.0

    # 3. AQI (Asset Quality Index)
    if all(x is not None for x in [current.current_assets, current.total_assets, prior.current_assets, prior.total_assets]):
        # AQI = (1 - CurrentAssets/TotalAssets)_current / (1 - CurrentAssets/TotalAssets)_prior
        aqi_curr = 1 - (current.current_assets / current.total_assets)
        aqi_prior = 1 - (prior.current_assets / prior.total_assets)
        aqi = aqi_curr / aqi_prior if aqi_prior != 0 else 1.0
        computed_count += 1
    else:
        aqi = 1.0

    # 4. SGI (Sales Growth Index)
    sgi = current.revenue / prior.revenue
    computed_count += 1

    # 5. DEPI (Depreciation Index) - Data not available in current schema
    depi = 1.0

    # 6. SGAI (SGA Expenses Index) - Data not available in current schema
    sgai = 1.0

    # 7. Accruals
    if current.net_income is not None and current.cash_from_operations is not None:
        # Accruals = (Net Income - Cash from Operations) / Total Assets
        accruals = (current.net_income - current.cash_from_operations) / current.total_assets
        computed_count += 1
    else:
        accruals = 0.0

    # 8. LEVI (Leverage Index)
    if current.total_liabilities is not None and prior.total_liabilities is not None:
        levi = (current.total_liabilities / current.total_assets) / (prior.total_liabilities / prior.total_assets)
        computed_count += 1
    else:
        levi = 1.0

    # Beneish Formula
    m_score = (
        -4.84 +
        (0.920 * dsri) +
        (0.528 * gmi) +
        (0.404 * aqi) +
        (0.892 * sgi) +
        (0.115 * depi) -
        (0.172 * sgai) +
        (4.679 * accruals) -
        (0.327 * levi)
    )

    passed = (m_score <= -1.78)
    interpretation = "below threshold — no manipulation indicated" if passed else "ABOVE threshold — manipulation likely"
    
    return CheckResult(
        name="beneish_mscore",
        passed=passed,
        expected=-1.78,
        actual=m_score,
        notes=f"M-Score: {m_score:.4f} ({interpretation}). {computed_count} of 8 components computed with real data."
    )


@tool
def compute_altman_zscore_simplified(period: FinancialPeriod) -> CheckResult:
    """Calculates a simplified version of the Altman Z-Score.
    
    Used to predict the probability that a firm will go into bankruptcy.
    Safe zone: Z > 2.99 | Grey zone: 1.81-2.99 | Distress zone: Z < 1.81.
    """
    if not period.total_assets or period.total_assets == 0:
        return CheckResult(
            name="altman_zscore",
            passed=True,
            notes="Insufficient data for Altman calculation (Total Assets required)."
        )

    ta = period.total_assets
    computed_count = 0

    # X1: Working Capital / Total Assets
    if period.current_assets is not None and period.current_liabilities is not None:
        x1 = (period.current_assets - period.current_liabilities) / ta
        computed_count += 1
    else:
        x1 = 0.0

    # X2: Retained Earnings / Total Assets (Proxy: Net Income / TA)
    if period.net_income is not None:
        x2 = period.net_income / ta
        computed_count += 1
    else:
        x2 = 0.0

    # X3: EBIT / Total Assets (Proxy: Operating Income or Net Income)
    if period.operating_income is not None:
        x3 = period.operating_income / ta
        computed_count += 1
    elif period.net_income is not None:
        x3 = period.net_income / ta # Proxy
    else:
        x3 = 0.0

    # X4: Equity / Total Liabilities
    if period.stockholders_equity is not None and period.total_liabilities:
        x4 = period.stockholders_equity / period.total_liabilities
        computed_count += 1
    elif period.total_liabilities == 0:
        x4 = 999.0 # Effectively infinite
    else:
        x4 = 0.0

    # X5: Revenue / Total Assets
    if period.revenue is not None:
        x5 = period.revenue / ta
        computed_count += 1
    else:
        x5 = 0.0

    # Altman Z-Score Formula for Public Firms
    z_score = (1.2 * x1) + (1.4 * x2) + (3.3 * x3) + (0.6 * x4) + (1.0 * x5)

    if z_score > 2.99:
        interpretation = "Safe zone — low bankruptcy risk"
        passed = True
    elif z_score >= 1.81:
        interpretation = "Grey zone — moderate bankruptcy risk (caution advised)"
        passed = True
    else:
        interpretation = "Distress zone — HIGH bankruptcy risk"
        passed = False

    return CheckResult(
        name="altman_zscore",
        passed=passed,
        expected=2.99,
        actual=z_score,
        notes=f"Z-Score: {z_score:.4f} ({interpretation}). {computed_count} of 5 components used real data/proxies."
    )


@tool
def compute_accruals_ratio(period: FinancialPeriod) -> CheckResult:
    """Calculates the accruals ratio as a quantitative indicator of earnings quality.
    
    Formula: (Net Income - Cash Flow from Operations) / Total Assets.
    High accruals (> 10%) can indicate aggressive accounting or manipulation.
    """
    if not all([period.net_income, period.cash_from_operations, period.total_assets]):
        return CheckResult(
            name="quant_accruals_ratio",
            passed=True,
            notes="Insufficient data for accruals ratio calculation."
        )

    accruals_val = (period.net_income - period.cash_from_operations) / period.total_assets
    passed = abs(accruals_val) <= 0.10
    
    interpretation = "within normal range" if passed else "HIGH accruals — potential manipulation"
    
    return CheckResult(
        name="quant_accruals_ratio",
        passed=passed,
        expected=0.10,
        actual=accruals_val,
        notes=f"Accruals Ratio: {accruals_val:.4f} ({interpretation})."
    )
