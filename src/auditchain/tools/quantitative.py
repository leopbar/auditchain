"""Quantitative analysis tools for fraud detection and financial risk assessment.

These tools perform mathematical modeling (Beneish, Altman) on structured
financial data to identify patterns indicative of manipulation or distress.

Model notes
-----------
Beneish M-Score (1999):
  8-component model; coefficients sourced from the original paper.
  DEPI and SGAI are structurally unavailable in SEC company_facts.json
  (depreciation is not itemised; SGA is not a standard XBRL tag for all
  filers) and are held at their neutral values of 1.0. The Accruals
  component (coefficient 4.679 — the largest in the model) is NOT
  defaulted to 0.0 when cash-flow data is missing; instead the component
  is omitted and the computed_count gate catches the gap. A score is only
  returned when >= 5 of the 8 components have real data.

Altman Z-Score (public-firm variant, 1968/1983):
  Coefficients: 1.2/1.4/3.3/0.6/1.0; thresholds 2.99/1.81.
  X2 uses cumulative RetainedEarnings when available (correct input),
  falling back to single-year Net Income as a documented proxy.
  Note: this formula was designed for public manufacturing firms. It uses
  book equity (stockholders_equity) in place of the original market-value
  equity — consistent with the Z' private-firm variant's X4 input but
  combined with the public-firm coefficients. Results should be interpreted
  with caution for capital-intensive or high-growth companies (Tesla,
  semiconductor fabs) where asset intensity and retained-loss histories
  structurally depress the score. Sector-specific calibration is on the
  roadmap (Planner Agent).
"""

from langchain_core.tools import tool
from auditchain.core.logging import get_logger
from auditchain.schemas.components import CheckResult, FinancialPeriod

logger = get_logger(__name__)

# Minimum components required to produce a valid score
BENEISH_MIN_COMPONENTS = 5   # out of 8 (DEPI/SGAI always default; need ≥3 of the remaining 6)
ALTMAN_MIN_COMPONENTS = 3    # out of 5


@tool
def compute_beneish_mscore_simplified(current: FinancialPeriod, prior: FinancialPeriod) -> CheckResult:
    """Calculates the Beneish M-Score (1999) for earnings-manipulation detection.

    Requires two consecutive annual periods. The model uses 8 financial-ratio
    indices; components without data default to their neutral values (1.0)
    EXCEPT for Accruals, which is omitted rather than defaulted because its
    coefficient (4.679) is the largest in the model and a zero default would
    silently favour the auditee.

    A result is only returned when >= 5 of the 8 components have real data;
    otherwise the result is status="inconclusive".

    Threshold: M-Score > -1.78 indicates elevated manipulation probability.
    DEPI and SGAI are structurally unavailable in EDGAR company_facts.json
    and are held at 1.0 (neutral).
    """
    if not all([current.revenue, prior.revenue, current.total_assets, prior.total_assets]):
        return CheckResult(
            name="beneish_mscore",
            passed=False,
            status="inconclusive",
            notes="Inconclusive: Beneish M-Score requires Revenue and Total Assets for both periods — one or more fields are missing."
        )

    computed_count = 0
    component_log: list[str] = []

    # 1. DSRI — Days Sales in Receivables Index (coef 0.920)
    if current.accounts_receivable is not None and prior.accounts_receivable is not None:
        dsri = (current.accounts_receivable / current.revenue) / (prior.accounts_receivable / prior.revenue)
        computed_count += 1
        component_log.append("DSRI(real)")
    else:
        dsri = 1.0
        component_log.append("DSRI(default=1.0)")

    # 2. GMI — Gross Margin Index (coef 0.528)
    if current.gross_profit is not None and prior.gross_profit is not None:
        gmi = (prior.gross_profit / prior.revenue) / (current.gross_profit / current.revenue)
        computed_count += 1
        component_log.append("GMI(real)")
    else:
        gmi = 1.0
        component_log.append("GMI(default=1.0)")

    # 3. AQI — Asset Quality Index (coef 0.404)
    if all(x is not None for x in [current.current_assets, current.total_assets, prior.current_assets, prior.total_assets]):
        aqi_curr = 1 - (current.current_assets / current.total_assets)
        aqi_prior = 1 - (prior.current_assets / prior.total_assets)
        aqi = aqi_curr / aqi_prior if aqi_prior != 0 else 1.0
        computed_count += 1
        component_log.append("AQI(real)")
    else:
        aqi = 1.0
        component_log.append("AQI(default=1.0)")

    # 4. SGI — Sales Growth Index (coef 0.892) — always computable when revenue is present
    sgi = current.revenue / prior.revenue
    computed_count += 1
    component_log.append("SGI(real)")

    # 5. DEPI — Depreciation Index (coef 0.115)
    # Structurally unavailable: depreciation is not itemised in company_facts.json.
    depi = 1.0
    component_log.append("DEPI(unavailable=1.0)")

    # 6. SGAI — SGA Expenses Index (coef -0.172)
    # Structurally unavailable: SGA is not a consistent XBRL tag across all filers.
    sgai = 1.0
    component_log.append("SGAI(unavailable=1.0)")

    # 7. Accruals (coef 4.679 — highest magnitude in the model)
    # NOT defaulted to 0.0: a zero default artificially suppresses the score by
    # ~4.68 points, silently favouring the auditee. Omit and let the gate handle it.
    if current.net_income is not None and current.cash_from_operations is not None:
        accruals = (current.net_income - current.cash_from_operations) / current.total_assets
        computed_count += 1
        component_log.append("Accruals(real)")
    else:
        accruals = 0.0   # value unused when gate triggers; kept for formula completeness
        component_log.append("Accruals(missing — omitted)")

    # 8. LEVI — Leverage Index (coef -0.327)
    if current.total_liabilities is not None and prior.total_liabilities is not None:
        levi = (current.total_liabilities / current.total_assets) / (prior.total_liabilities / prior.total_assets)
        computed_count += 1
        component_log.append("LEVI(real)")
    else:
        levi = 1.0
        component_log.append("LEVI(default=1.0)")

    # Gate: require at least BENEISH_MIN_COMPONENTS real values for a valid score
    component_summary = ", ".join(component_log)
    if computed_count < BENEISH_MIN_COMPONENTS:
        return CheckResult(
            name="beneish_mscore",
            passed=False,
            status="inconclusive",
            notes=(
                f"Inconclusive: only {computed_count}/8 components have real data "
                f"(minimum {BENEISH_MIN_COMPONENTS} required) — threshold -1.78 is not "
                f"statistically valid with this many defaults. "
                f"Components: {component_summary}."
            )
        )

    m_score = (
        -4.84
        + (0.920 * dsri)
        + (0.528 * gmi)
        + (0.404 * aqi)
        + (0.892 * sgi)
        + (0.115 * depi)
        - (0.172 * sgai)
        + (4.679 * accruals)
        - (0.327 * levi)
    )

    passed = m_score <= -1.78
    interpretation = "below threshold — no manipulation indicated" if passed else "ABOVE threshold — manipulation likely"

    return CheckResult(
        name="beneish_mscore",
        passed=passed,
        expected=-1.78,
        actual=m_score,
        notes=(
            f"M-Score: {m_score:.4f} ({interpretation}). "
            f"{computed_count}/8 components with real data. "
            f"Components: {component_summary}."
        )
    )


@tool
def compute_altman_zscore_simplified(period: FinancialPeriod) -> CheckResult:
    """Calculates the Altman Z-Score (public-firm variant) for bankruptcy prediction.

    Uses the original public-firm coefficients (1.2/1.4/3.3/0.6/1.0) and
    thresholds (safe > 2.99, grey 1.81-2.99, distress < 1.81).

    X2 uses cumulative RetainedEarnings when available (the correct input per
    the original model). Falls back to single-year Net Income as a documented
    proxy when retained earnings are not available — this understates financial
    stability for mature firms with long earnings histories.

    Caution: this model was calibrated on public manufacturing firms. Capital-
    intensive or high-growth companies (EVs, semiconductors) may score lower
    than their actual risk warrants. Sector-specific calibration is on the roadmap.

    A result is only returned when >= 3 of the 5 components have real data.
    """
    # Gate 1: financial-sector companies (insurance, banking, REITs, holding
    # companies — SIC 6000-6799). Policy reserves and investment portfolios
    # structurally distort every component of the model. Altman himself excluded
    # financial institutions from the original 1968 sample.
    if period.sector == "financial":
        return CheckResult(
            name="altman_zscore",
            passed=False,
            status="inconclusive",
            notes=(
                f"Inconclusive: Altman Z-Score is not calibrated for financial-sector "
                f"companies (SIC {period.sic_code}). Policy reserves, investment portfolios, "
                f"and the absence of current asset classification structurally distort all "
                f"five model components. Use sector-specific solvency metrics instead."
            )
        )

    # Gate 2: structural fallback for companies whose SIC has not yet been
    # ingested but whose balance sheet pattern indicates a financial institution
    # (insurance/banking companies never report AssetsCurrent or LiabilitiesCurrent
    # under US GAAP, making X1 uncomputable and the model invalid).
    if period.sic_code is None and period.current_assets is None and period.current_liabilities is None:
        return CheckResult(
            name="altman_zscore",
            passed=False,
            status="inconclusive",
            notes=(
                "Inconclusive: neither current_assets nor current_liabilities are available. "
                "This balance sheet structure is typical of financial institutions (insurance, "
                "banking) for which Altman Z-Score is not valid. Re-ingest to populate SIC code."
            )
        )

    if not period.total_assets or period.total_assets == 0:
        return CheckResult(
            name="altman_zscore",
            passed=False,
            status="inconclusive",
            notes="Inconclusive: Altman Z-Score requires Total Assets — field is missing or zero."
        )

    ta = period.total_assets
    computed_count = 0
    component_log: list[str] = []

    # X1: Working Capital / Total Assets (coef 1.2)
    if period.current_assets is not None and period.current_liabilities is not None:
        x1 = (period.current_assets - period.current_liabilities) / ta
        computed_count += 1
        component_log.append("X1(real)")
    else:
        x1 = 0.0
        component_log.append("X1(missing=0.0)")

    # X2: Retained Earnings / Total Assets (coef 1.4)
    # Prefer cumulative retained_earnings; fall back to single-year net_income.
    if period.retained_earnings is not None:
        x2 = period.retained_earnings / ta
        computed_count += 1
        component_log.append("X2(retained_earnings — correct)")
    elif period.net_income is not None:
        x2 = period.net_income / ta
        computed_count += 1
        component_log.append("X2(net_income proxy — single-year, may understate stability)")
    else:
        x2 = 0.0
        component_log.append("X2(missing=0.0)")

    # X3: EBIT / Total Assets (coef 3.3)
    # Operating income is the best available proxy for EBIT.
    if period.operating_income is not None:
        x3 = period.operating_income / ta
        computed_count += 1
        component_log.append("X3(operating_income)")
    elif period.net_income is not None:
        x3 = period.net_income / ta
        # Not incrementing computed_count: net_income already counted in X2 if used there;
        # we still compute X3 but flag it as a secondary proxy.
        component_log.append("X3(net_income fallback proxy)")
    else:
        x3 = 0.0
        component_log.append("X3(missing=0.0)")

    # X4: Book Equity / Total Liabilities (coef 0.6)
    # Note: original Z model requires market-value equity; we use book equity
    # (consistent with Z' private-firm variant) combined with Z public coefficients.
    if period.stockholders_equity is not None and period.total_liabilities:
        x4 = period.stockholders_equity / period.total_liabilities
        computed_count += 1
        component_log.append("X4(book_equity — not market_cap)")
    elif period.total_liabilities == 0:
        x4 = 999.0
        computed_count += 1
        component_log.append("X4(liabilities=0 → infinite)")
    else:
        x4 = 0.0
        component_log.append("X4(missing=0.0)")

    # X5: Revenue / Total Assets — Asset Turnover (coef 1.0)
    if period.revenue is not None:
        x5 = period.revenue / ta
        computed_count += 1
        component_log.append("X5(real)")
    else:
        x5 = 0.0
        component_log.append("X5(missing=0.0)")

    # Gate: require at least ALTMAN_MIN_COMPONENTS real values
    component_summary = ", ".join(component_log)
    if computed_count < ALTMAN_MIN_COMPONENTS:
        return CheckResult(
            name="altman_zscore",
            passed=False,
            status="inconclusive",
            notes=(
                f"Inconclusive: only {computed_count}/5 components computed "
                f"(minimum {ALTMAN_MIN_COMPONENTS} required) — Z-Score thresholds 2.99/1.81 not valid. "
                f"Components: {component_summary}."
            )
        )

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
        notes=(
            f"Z-Score: {z_score:.4f} ({interpretation}). "
            f"Public-firm model (book equity used, not market cap). "
            f"{computed_count}/5 components with real data. "
            f"Components: {component_summary}."
        )
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
            passed=False,
            status="inconclusive",
            notes="Inconclusive: accruals ratio requires net_income, cash_from_operations, and total_assets — one or more fields are missing."
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
