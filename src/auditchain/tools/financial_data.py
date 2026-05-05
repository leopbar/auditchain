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
) -> float | None:
    """Internal helper to fetch the latest value for a set of possible XBRL concepts."""
    for concept in concept_names:
        stmt = (
            select(FinancialLineItemORM.value)
            .where(
                FinancialLineItemORM.filing_id == filing_id,
                FinancialLineItemORM.concept == concept,
            )
            .order_by(FinancialLineItemORM.period_end.desc())
            .limit(1)
        )
        val = session.execute(stmt).scalar_one_or_none()
        if val is not None:
            return float(val)
    return None


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

            # Mapping of indicators to their possible XBRL concept names
            indicators = {
                "revenue": [
                    "RevenueFromContractWithCustomerExcludingAssessedTax",
                    "Revenues",
                ],
                "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
                "gross_profit": ["GrossProfit"],
                "operating_expenses": ["OperatingExpenses"],
                "operating_income": ["OperatingIncomeLoss"],
                "net_income": ["NetIncomeLoss"],
                "total_assets": ["Assets"],
                "current_assets": ["AssetsCurrent"],
                "accounts_receivable": ["AccountsReceivableNetCurrent"],
                "inventory": ["InventoryNet"],
                "total_liabilities": ["Liabilities"],
                "current_liabilities": ["LiabilitiesCurrent"],
                "stockholders_equity": ["StockholdersEquity"],
                "cash": ["CashAndCashEquivalentsAtCarryingValue"],
                "cash_from_operations": ["NetCashProvidedByUsedInOperatingActivities"],
                "cash_from_investing": ["NetCashProvidedByUsedInInvestingActivities"],
                "cash_from_financing": ["NetCashProvidedByUsedInFinancingActivities"],
            }

            values = {}
            found_count = 0
            for key, concepts in indicators.items():
                val = _get_value_for_concept(session, filing_id, concepts)
                values[key] = val
                if val is not None:
                    found_count += 1

            logger.info(
                "tool_get_financial_summary_success",
                filing_id=filing_id,
                indicators_found=found_count,
            )

            return FinancialPeriod(
                filing_id=filing.id,
                fiscal_year=filing.fiscal_year,
                period_end=filing.period_of_report,
                **values,
            )
    except Exception as e:
        logger.exception("tool_get_financial_summary_failed", filing_id=filing_id)
        return ToolError(error=str(e), code="internal_error")
