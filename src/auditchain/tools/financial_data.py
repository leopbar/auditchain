"""LangChain tools for accessing financial data from the database.

Agents must always use these tools to interact with the database. This ensures
proper logging, consistent data formatting, and encapsulates query logic
away from the agent's core reasoning loops.
"""

from langchain_core.tools import tool
from sqlalchemy import desc, select

from auditchain.core.logging import get_logger
from auditchain.data.database import get_session
from auditchain.data.models import CompanyORM, FilingORM, FinancialLineItemORM
from auditchain.data.repositories import CompanyRepository
from auditchain.schemas.components import FinancialPeriod
from auditchain.tools.schemas import (
    CompanyInfo,
    FilingSummary,
    ToolError,
)

logger = get_logger(__name__)


@tool
def get_company(identifier: str) -> CompanyInfo | ToolError:
    """Retrieve structured data for a company using its ticker symbol or SEC CIK.

    Args:
        identifier: The company's ticker (e.g., 'AAPL', 'BHC') or 10-digit CIK
            (e.g., '0000320193'). The tool automatically detects the type.
            Tickers are case-insensitive.

    Returns:
        A CompanyInfo object if the company is found, or a ToolError if not.
    """
    logger.info("tool_get_company_called", identifier=identifier)

    # Simple detection: CIKs are 10-digit numbers (often with leading zeros)
    is_cik = identifier.isdigit() and len(identifier) == 10

    with get_session() as session:
        repo = CompanyRepository(session)
        company = None

        if is_cik:
            company = repo.get_by_cik(identifier)
        else:
            # Look up by ticker (case-insensitive)
            stmt = select(CompanyORM).where(CompanyORM.ticker == identifier.upper())
            company = session.execute(stmt).scalar_one_or_none()

        if not company:
            logger.warning("tool_get_company_not_found", identifier=identifier)
            return ToolError(
                error=f"No company found with identifier '{identifier}'",
                code="company_not_found",
            )

        logger.info("tool_get_company_success", cik=company.cik, name=company.name)
        return CompanyInfo(
            cik=company.cik,
            ticker=company.ticker,
            name=company.name,
            is_known_fraud=company.is_known_fraud,
            fraud_notes=company.fraud_notes,
        )


@tool
def list_filings(
    cik: str, filing_type: str | None = None, limit: int = 5
) -> list[FilingSummary] | ToolError:
    """List available SEC filings for a specific company, sorted by date.

    Use this when you need to identify which financial periods (e.g., FY 2023, Q3 2024)
    are available for audit after finding a company's CIK.

    Args:
        cik: The 10-digit SEC CIK (e.g., '0000320193'). Use the value exactly
            as returned by get_company.
        filing_type: Optional filter (e.g., '10-K' for annual, '10-Q' for quarterly).
            Omit to see all available documents.
        limit: Max number of documents to return. Default is 5 (most recent).

    Returns:
        A list of FilingSummary objects ordered by most recent first, or a
        ToolError if no filings are found.
    """
    logger.info("tool_list_filings_called", cik=cik, filing_type=filing_type, limit=limit)

    with get_session() as session:
        repo = CompanyRepository(session)
        company = repo.get_by_cik(cik)

        if not company:
            return ToolError(error=f"No company found with CIK '{cik}'", code="company_not_found")

        stmt = (
            select(FilingORM)
            .where(FilingORM.company_id == company.id)
            .order_by(desc(FilingORM.period_of_report))
            .limit(limit)
        )

        if filing_type:
            stmt = stmt.where(FilingORM.filing_type == filing_type)

        try:
            results = session.execute(stmt).scalars().all()
        except Exception as e:
            # Catch Postgres ENUM validation errors (DataError in SQLAlchemy)
            if "invalid input value for enum" in str(e):
                logger.warning("tool_list_filings_invalid_type", cik=cik, filing_type=filing_type)
                return ToolError(
                    error=f"Invalid filing_type '{filing_type}'. Must be one of the SEC standard forms (10-K, 10-Q, 8-K, etc.)",
                    code="invalid_filing_type",
                )
            raise

        if not results:
            type_msg = f" with type '{filing_type}'" if filing_type else ""
            return ToolError(
                error=f"No filings found for CIK '{cik}'{type_msg}",
                code="no_filings_found",
            )

        logger.info("tool_list_filings_success", cik=cik, count=len(results))
        return [
            FilingSummary(
                id=f.id,
                accession_number=f.accession_number,
                filing_type=f.filing_type,
                fiscal_year=f.fiscal_year,
                fiscal_period=f.fiscal_period,
                period_of_report=f.period_of_report,
                filing_date=f.filing_date,
            )
            for f in results
        ]


def _get_value_for_concept(
    session, filing_id: int, concept_names: list[str]
) -> tuple[float | None, str | None]:
    """Fetch the latest value for the first matching XBRL concept.

    Returns a ``(value, matched_concept)`` tuple so callers can record which
    alias actually resolved (provenance). Returns ``(None, None)`` when no
    concept in ``concept_names`` matches.
    """
    for concept in concept_names:
        base = (
            select(FinancialLineItemORM.value)
            .where(
                FinancialLineItemORM.filing_id == filing_id,
                FinancialLineItemORM.concept == concept,
            )
            .order_by(FinancialLineItemORM.period_end.desc())
            .limit(1)
        )
        # Prefer the consolidated figure (frame != '' means SEC assigned a standard
        # calendar-period identifier, which only happens for company-level totals).
        val = session.execute(base.where(FinancialLineItemORM.frame != "")).scalar_one_or_none()
        # Fallback: companies with non-December fiscal year-ends (e.g. Apple) have
        # frame='' even on consolidated facts because the period doesn't align with
        # a standard calendar year.
        if val is None:
            val = session.execute(base).scalar_one_or_none()
        if val is not None:
            return float(val), concept
    return None, None


def _derive_balance_sheet_aggregates(
    session,
    filing_id: int,
    values: dict[str, float | None],
    provenance: dict[str, str],
) -> None:
    """Fill in ``total_liabilities`` / ``stockholders_equity`` when not tagged directly.

    Mutates ``values`` and ``provenance`` in place. Direct lookups must already
    have run, so reported values are never overwritten. Derivation by composition:
      - ``Liabilities = LiabilitiesCurrent + LiabilitiesNoncurrent``
      - ``Equity(total) = StockholdersEquity (parent) + MinorityInterest (NCI)``
      - Last resort, via the identity ``LiabilitiesAndStockholdersEquity = Assets``:
          ``Liabilities = LiabilitiesAndStockholdersEquity - Equity`` and
          ``Equity = LiabilitiesAndStockholdersEquity - Liabilities``.

    For the accounting equation to balance against total assets, equity must be
    the TOTAL including noncontrolling interest (NCI) — hence parent + NCI.
    """
    # total_liabilities from the current + noncurrent pieces
    if values.get("total_liabilities") is None:
        current = values.get("current_liabilities")
        noncurrent, _ = _get_value_for_concept(
            session, filing_id, ["LiabilitiesNoncurrent"]
        )
        if current is not None and noncurrent is not None:
            values["total_liabilities"] = current + noncurrent
            provenance["total_liabilities"] = (
                "derived: LiabilitiesCurrent + LiabilitiesNoncurrent"
            )

    # stockholders_equity (total, including NCI) from parent + minority interest
    if values.get("stockholders_equity") is None:
        parent, _ = _get_value_for_concept(session, filing_id, ["StockholdersEquity"])
        nci, _ = _get_value_for_concept(session, filing_id, ["MinorityInterest"])
        if parent is not None:
            values["stockholders_equity"] = parent + (nci or 0.0)
            provenance["stockholders_equity"] = (
                "derived: StockholdersEquity + MinorityInterest"
                if nci is not None
                else "alias: StockholdersEquity (no NCI reported)"
            )

    # Add redeemable NCI (mezzanine item between liabilities and permanent equity).
    # Some filers (e.g. Tesla) report a "redeemable noncontrolling interest" that
    # sits outside both Liabilities and the NCI-inclusive equity tag.  It must be
    # included in the equity side for the accounting equation to balance.
    redeemable_nci, _ = _get_value_for_concept(
        session, filing_id, ["RedeemableNoncontrollingInterestEquityCarryingAmount"]
    )
    if redeemable_nci is not None and values.get("stockholders_equity") is not None:
        values["stockholders_equity"] += redeemable_nci
        provenance["stockholders_equity"] = (
            provenance.get("stockholders_equity", "direct")
            + " + RedeemableNoncontrollingInterest"
        )

    # Last resort: balance-sheet identity (right-hand side total == total assets)
    total_rhs, _ = _get_value_for_concept(
        session, filing_id, ["LiabilitiesAndStockholdersEquity"]
    )
    if total_rhs is not None:
        if (
            values.get("total_liabilities") is None
            and values.get("stockholders_equity") is not None
        ):
            values["total_liabilities"] = total_rhs - values["stockholders_equity"]
            provenance["total_liabilities"] = (
                "derived: LiabilitiesAndStockholdersEquity - StockholdersEquity"
            )
        if (
            values.get("stockholders_equity") is None
            and values.get("total_liabilities") is not None
        ):
            values["stockholders_equity"] = total_rhs - values["total_liabilities"]
            provenance["stockholders_equity"] = (
                "derived: LiabilitiesAndStockholdersEquity - Liabilities"
            )


@tool
def get_financial_summary(filing_id: int) -> FinancialPeriod | ToolError:
    """Retrieve comprehensive financial data (revenue, income, assets, liabilities, etc.) for a filing.

    Use this tool when you need structured financial numbers for a specific period
    to perform analysis, mathematical reconciliation, or quantitative risk scoring (Beneish, Altman).

    Args:
        filing_id: The internal database ID of the filing (integer).
            Obtain this from a previous list_filings call.

    Returns:
        A FinancialPeriod object containing the detailed financial data,
        or a ToolError if the filing is not found.
    """
    logger.info("tool_get_financial_summary_called", filing_id=filing_id)

    try:
        with get_session() as session:
            filing = session.get(FilingORM, filing_id)
            if not filing:
                return ToolError(
                    error=f"No filing found with id {filing_id}", code="filing_not_found"
                )

            # Mapping of indicators to their possible XBRL concept names, in
            # priority order (first match wins). Multiple aliases guard against
            # the fact that US-GAAP offers many valid tags for the same concept.
            # For stockholders_equity the NCI-inclusive variant comes FIRST so the
            # accounting equation balances against total assets (see reconciler).
            indicators = {
                "revenue": [
                    "RevenueFromContractWithCustomerExcludingAssessedTax",
                    "RevenueFromContractWithCustomerIncludingAssessedTax",
                    "Revenues",
                    "SalesRevenueNet",
                ],
                "cost_of_revenue": [
                    "CostOfRevenue",
                    "CostOfGoodsAndServicesSold",
                    "CostOfGoodsSold",
                ],
                "gross_profit": ["GrossProfit"],
                "operating_expenses": ["OperatingExpenses", "CostsAndExpenses"],
                "operating_income": ["OperatingIncomeLoss"],
                "net_income": ["NetIncomeLoss", "ProfitLoss"],
                "total_assets": ["Assets"],
                "current_assets": ["AssetsCurrent"],
                "accounts_receivable": [
                    "AccountsReceivableNetCurrent",
                    "ReceivablesNetCurrent",
                ],
                "inventory": ["InventoryNet", "InventoryFinishedGoodsNetOfReserves"],
                "total_liabilities": ["Liabilities"],
                "current_liabilities": ["LiabilitiesCurrent"],
                "stockholders_equity": [
                    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
                    "StockholdersEquity",
                ],
                "cash": [
                    "CashAndCashEquivalentsAtCarryingValue",
                    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
                ],
                "cash_from_operations": ["NetCashProvidedByUsedInOperatingActivities"],
                "cash_from_investing": ["NetCashProvidedByUsedInInvestingActivities"],
                "cash_from_financing": ["NetCashProvidedByUsedInFinancingActivities"],
            }

            values: dict[str, float | None] = {}
            provenance: dict[str, str] = {}
            for key, concepts in indicators.items():
                val, matched = _get_value_for_concept(session, filing_id, concepts)
                values[key] = val
                provenance[key] = matched if matched is not None else "not_found"

            # Fill in balance-sheet aggregates that filers often omit (e.g. the
            # aggregate Liabilities, or NCI-adjusted equity) by composition.
            _derive_balance_sheet_aggregates(session, filing_id, values, provenance)

            critical_missing = [k for k, v in values.items() if v is None]
            found_count = len(values) - len(critical_missing)

            logger.info(
                "tool_get_financial_summary_success",
                filing_id=filing_id,
                indicators_found=found_count,
                indicators_total=len(values),
                critical_missing=critical_missing,
            )
            logger.info(
                "financial_summary_provenance",
                filing_id=filing_id,
                provenance=provenance,
            )

            return FinancialPeriod(
                filing_id=filing.id,
                fiscal_year=filing.fiscal_year,
                period_end=filing.period_of_report,
                indicators_found=found_count,
                critical_missing=critical_missing,
                **values,
            )
    except Exception as e:
        logger.exception("tool_get_financial_summary_failed", filing_id=filing_id)
        return ToolError(error=str(e), code="internal_error")
