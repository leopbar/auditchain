"""Mathematical tools for the Reconciler Agent.

This module contains pure mathematical validation functions used by the 
Reconciler Agent to verify accounting consistency. Each tool receives structured 
financial data (FinancialPeriod) and returns a typed CheckResult.
These tools are idempotent and do not access external resources or databases.
"""

from langchain_core.tools import tool

from auditchain.core.logging import get_logger
from auditchain.schemas.components import CheckResult, FinancialPeriod

logger = get_logger(__name__)

# Constants for validation thresholds
ACCOUNTING_EQUATION_TOLERANCE_PCT = 0.001  # 0.1% of total assets
YOY_VARIATION_THRESHOLD_PCT = 0.50  # 50% year-over-year change is flagged
ACCRUALS_THRESHOLD_PCT = 0.10  # 10% of assets is flagged as high accruals


@tool
def check_accounting_equation(period: FinancialPeriod) -> CheckResult:
    """Verifies the fundamental accounting equation: Total Assets = Total Liabilities + Stockholders' Equity. 
    
    Returns a CheckResult indicating whether the equation balances within tolerance (0.1% of total assets). 
    Use this tool to validate any FinancialPeriod where total_assets, total_liabilities, 
    and stockholders_equity are all reported. 
    If any of those three are None, the check cannot run and you should not call this tool for that period.
    """
    logger.info("check_accounting_equation_called", filing_id=period.filing_id)

    # Check for required data
    if period.total_assets is None or period.total_liabilities is None or period.stockholders_equity is None:
        return CheckResult(
            name="accounting_equation",
            passed=False,
            expected=None,
            actual=None,
            tolerance=None,
            notes="Insufficient data: total_assets, total_liabilities, or stockholders_equity is None."
        )

    expected = period.total_liabilities + period.stockholders_equity
    actual = period.total_assets
    tolerance = abs(period.total_assets) * ACCOUNTING_EQUATION_TOLERANCE_PCT
    discrepancy = actual - expected
    passed = abs(discrepancy) <= tolerance

    if passed:
        notes = f"Equation balances within tolerance. Discrepancy: ${discrepancy:,.0f}, tolerance: ${tolerance:,.0f}"
    else:
        notes = f"Equation DOES NOT balance. Discrepancy: ${discrepancy:,.0f} exceeds tolerance: ${tolerance:,.0f}"

    return CheckResult(
        name="accounting_equation",
        passed=passed,
        expected=expected,
        actual=actual,
        tolerance=tolerance,
        notes=notes
    )


@tool
def check_yoy_consistency(current: FinancialPeriod, prior: FinancialPeriod) -> list[CheckResult]:
    """Compares two consecutive fiscal periods and flags excessive year-over-year variations in key metrics.
    
    Metrics checked: revenue, net_income, total_assets, total_liabilities. 
    Variations exceeding ±50% are flagged. 
    Returns a list of CheckResults, one per metric checked. 
    Use this tool to compare the current period against each historical period from CompanyData.
    """
    logger.info("check_yoy_consistency_called", current_filing_id=current.filing_id, prior_filing_id=prior.filing_id)

    metrics_to_check = [
        ("revenue", current.revenue, prior.revenue),
        ("net_income", current.net_income, prior.net_income),
        ("total_assets", current.total_assets, prior.total_assets),
        ("total_liabilities", current.total_liabilities, prior.total_liabilities),
    ]

    results = []

    for metric_name, current_value, prior_value in metrics_to_check:
        check_name = f"yoy_{metric_name}_FY{current.fiscal_year}_vs_FY{prior.fiscal_year}"
        
        if current_value is None or prior_value is None:
            results.append(CheckResult(
                name=check_name,
                passed=True,
                expected=None,
                actual=None,
                tolerance=None,
                notes="Insufficient data — skipped."
            ))
            continue

        if prior_value == 0:
            results.append(CheckResult(
                name=check_name,
                passed=True,
                expected=0.0,
                actual=current_value,
                tolerance=0.0,
                notes="Prior value is zero — variation undefined."
            ))
            continue

        variation_pct = (current_value - prior_value) / abs(prior_value)
        passed = abs(variation_pct) <= YOY_VARIATION_THRESHOLD_PCT
        tolerance = abs(prior_value) * YOY_VARIATION_THRESHOLD_PCT

        if passed:
            notes = f"YoY change: {variation_pct:+.1%}. Within normal range."
        else:
            notes = f"YoY change: {variation_pct:+.1%}. EXCEEDS ±50% threshold — warrants explanation."

        results.append(CheckResult(
            name=check_name,
            passed=passed,
            expected=prior_value,
            actual=current_value,
            tolerance=tolerance,
            notes=notes
        ))

    return results


@tool
def compare_income_vs_cashflow(period: FinancialPeriod) -> CheckResult:
    """Compares net income with cash flow from operations to compute the accruals ratio.
    
    Accruals ratio formula: (net_income - cash_from_operations) / total_assets. 
    High accruals (>10% of total assets) are a classic red flag for earnings management 
    or accounting manipulation. Use this tool when both net_income and 
    cash_from_operations are reported.
    """
    logger.info("compare_income_vs_cashflow_called", filing_id=period.filing_id)

    if period.net_income is None or period.cash_from_operations is None or period.total_assets is None or period.total_assets == 0:
        return CheckResult(
            name="accruals_check",
            passed=True,
            expected=None,
            actual=None,
            tolerance=None,
            notes="Insufficient data: requires net_income, cash_from_operations, and total_assets."
        )

    accruals = period.net_income - period.cash_from_operations
    accruals_ratio = accruals / period.total_assets
    passed = abs(accruals_ratio) <= ACCRUALS_THRESHOLD_PCT

    if passed:
        notes = f"Accruals ratio: {accruals_ratio:+.2%}. Within normal range (≤10% of assets)."
    else:
        notes = f"Accruals ratio: {accruals_ratio:+.2%}. EXCEEDS 10% threshold — possible earnings management."

    return CheckResult(
        name="accruals_check",
        passed=passed,
        expected=0.0,
        actual=accruals_ratio,
        tolerance=ACCRUALS_THRESHOLD_PCT,
        notes=notes
    )
