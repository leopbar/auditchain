"""Repository layer — encapsulates all database access patterns.

The rest of the application talks to the database only through repositories.
This keeps SQLAlchemy as an implementation detail and makes the codebase
easier to test, swap, and reason about.

Each repository receives an active Session in its constructor. Session
lifecycle (open, commit, rollback, close) belongs to the caller via
get_session() — repositories never commit on their own.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from auditchain.core.logging import get_logger
from auditchain.data.models import CompanyORM, FilingORM, FinancialLineItemORM

logger = get_logger(__name__)


class CompanyRepository:
    """All database operations for the companies table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_cik(self, cik: str) -> CompanyORM | None:
        """Return the company with the given CIK, or None if not found."""
        stmt = select(CompanyORM).where(CompanyORM.cik == cik)
        return self._session.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        cik: str,
        name: str,
        ticker: str | None = None,
        is_known_fraud: bool = False,
        fraud_notes: str | None = None,
    ) -> CompanyORM:
        """Insert or update a company by CIK.

        If a row with this CIK already exists, the mutable fields are updated.
        Returns the persisted ORM instance.
        """
        stmt = pg_insert(CompanyORM).values(
            cik=cik,
            name=name,
            ticker=ticker,
            is_known_fraud=is_known_fraud,
            fraud_notes=fraud_notes,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["cik"],
            set_={
                "name": stmt.excluded.name,
                "ticker": stmt.excluded.ticker,
                "is_known_fraud": stmt.excluded.is_known_fraud,
                "fraud_notes": stmt.excluded.fraud_notes,
            },
        ).returning(CompanyORM)

        result = self._session.execute(stmt).scalar_one()
        self._session.flush()
        return result

    def list_all(self) -> list[CompanyORM]:
        """Return every company in the database."""
        return list(self._session.execute(select(CompanyORM)).scalars())

    def list_known_fraud(self) -> list[CompanyORM]:
        """Return only companies flagged as known fraud cases."""
        stmt = select(CompanyORM).where(CompanyORM.is_known_fraud.is_(True))
        return list(self._session.execute(stmt).scalars())


class FilingRepository:
    """All database operations for the filings table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_accession(self, accession_number: str) -> FilingORM | None:
        """Return the filing with the given SEC accession number."""
        stmt = select(FilingORM).where(FilingORM.accession_number == accession_number)
        return self._session.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        company_id: int,
        accession_number: str,
        filing_type: str,
        filing_date: object,
        period_of_report: object,
        fiscal_year: int,
        fiscal_period: str,
        is_synthetic: bool = False,
        fraud_injected: dict | None = None,
    ) -> FilingORM:
        """Insert or update a filing keyed by accession number."""
        stmt = pg_insert(FilingORM).values(
            company_id=company_id,
            accession_number=accession_number,
            filing_type=filing_type,
            filing_date=filing_date,
            period_of_report=period_of_report,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            is_synthetic=is_synthetic,
            fraud_injected=fraud_injected,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["accession_number"],
            set_={
                "company_id": stmt.excluded.company_id,
                "filing_type": stmt.excluded.filing_type,
                "filing_date": stmt.excluded.filing_date,
                "period_of_report": stmt.excluded.period_of_report,
                "fiscal_year": stmt.excluded.fiscal_year,
                "fiscal_period": stmt.excluded.fiscal_period,
            },
        ).returning(FilingORM)

        result = self._session.execute(stmt).scalar_one()
        self._session.flush()
        return result

    def list_for_company(self, company_id: int) -> list[FilingORM]:
        """Return all filings for a given company, newest first."""
        stmt = (
            select(FilingORM)
            .where(FilingORM.company_id == company_id)
            .order_by(FilingORM.period_of_report.desc())
        )
        return list(self._session.execute(stmt).scalars())


class FinancialLineItemRepository:
    """All database operations for the financial_line_items table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_upsert(self, rows: Iterable[dict]) -> int:
        """Insert or update many line items at once.

        Each row dict must contain: filing_id, statement, concept, period_end, value.
        Optional: label, currency, unit, decimals, period_start.

        Returns the number of rows processed.
        """
        rows_list = list(rows)
        if not rows_list:
            return 0

        stmt = pg_insert(FinancialLineItemORM).values(rows_list)
        stmt = stmt.on_conflict_do_update(
            index_elements=["filing_id", "statement", "concept", "period_end"],
            set_={
                "value": stmt.excluded.value,
                "label": stmt.excluded.label,
                "currency": stmt.excluded.currency,
                "unit": stmt.excluded.unit,
                "decimals": stmt.excluded.decimals,
                "period_start": stmt.excluded.period_start,
            },
        )
        self._session.execute(stmt)
        self._session.flush()
        logger.info("line_items_bulk_upserted", count=len(rows_list))
        return len(rows_list)

    def count_for_filing(self, filing_id: int) -> int:
        """Return how many line items belong to a filing."""
        stmt = select(FinancialLineItemORM).where(FinancialLineItemORM.filing_id == filing_id)
        return len(list(self._session.execute(stmt).scalars()))