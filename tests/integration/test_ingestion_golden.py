"""Integration tests: reconcile DB values against golden values after ingestion.

Requires:
  - auditchain-postgres container running
  - TSLA and AAPL already ingested (run: python -m scripts.ingest_filings --tickers TSLA AAPL)

Run with:
    make test-integration
    pytest -m integration tests/integration/test_ingestion_golden.py -v
"""

import pytest
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from auditchain.data.models import CompanyORM, FilingORM, FinancialLineItemORM
from tests.fixtures.golden_values import AAPL_GOLDEN, TSLA_GOLDEN

TOLERANCE = 0.001  # 0.1% — accounts for rounding in Numeric(20,2) storage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_value(
    session: Session,
    ticker: str,
    concept: str,
    period_end: date,
    frame: str = "",
) -> float | None:
    """Query the DB for a specific concept/period/frame combination."""
    stmt = (
        select(FinancialLineItemORM.value)
        .join(FilingORM, FinancialLineItemORM.filing_id == FilingORM.id)
        .join(CompanyORM, FilingORM.company_id == CompanyORM.id)
        .where(
            CompanyORM.ticker == ticker,
            FinancialLineItemORM.concept == concept,
            FinancialLineItemORM.period_end == period_end,
            FinancialLineItemORM.frame == frame,
        )
        .limit(1)
    )
    result = session.execute(stmt).scalar_one_or_none()
    return float(result) if result is not None else None


def _assert_close(actual: float | None, expected: float, label: str):
    assert actual is not None, f"{label}: value not found in DB"
    rel_error = abs(actual - expected) / expected
    assert rel_error <= TOLERANCE, (
        f"{label}: actual={actual:,.0f} expected={expected:,.0f} "
        f"relative error={rel_error:.4%} exceeds {TOLERANCE:.1%} tolerance"
    )


# ---------------------------------------------------------------------------
# Tesla — framed consolidated values
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestTeslaDB:

    def test_revenue_cy2024(self, db_session):
        val = _get_value(
            db_session, "TSLA",
            TSLA_GOLDEN["revenue_concept"],
            TSLA_GOLDEN["periods"]["CY2024"]["period_end"],
            frame="CY2024",
        )
        _assert_close(val, TSLA_GOLDEN["periods"]["CY2024"]["revenue"], "TSLA CY2024 revenue")

    def test_revenue_cy2023(self, db_session):
        val = _get_value(
            db_session, "TSLA",
            TSLA_GOLDEN["revenue_concept"],
            TSLA_GOLDEN["periods"]["CY2023"]["period_end"],
            frame="CY2023",
        )
        _assert_close(val, TSLA_GOLDEN["periods"]["CY2023"]["revenue"], "TSLA CY2023 revenue")

    def test_net_income_cy2024(self, db_session):
        val = _get_value(
            db_session, "TSLA",
            TSLA_GOLDEN["net_income_concept"],
            TSLA_GOLDEN["periods"]["CY2024"]["period_end"],
            frame="CY2024",
        )
        _assert_close(val, TSLA_GOLDEN["periods"]["CY2024"]["net_income"], "TSLA CY2024 net_income")

    def test_total_assets_cy2024(self, db_session):
        """Assets are balance-sheet instants — stored with a Q4 frame by the SEC.
        The ingestion stores the Q4 instant frame ('CY2024Q4I') as a separate row."""
        # Assets may be stored under Q4 instant frame or period frame
        val = (
            _get_value(db_session, "TSLA", TSLA_GOLDEN["assets_concept"],
                       TSLA_GOLDEN["periods"]["CY2024"]["period_end"], frame="CY2024Q4I")
            or _get_value(db_session, "TSLA", TSLA_GOLDEN["assets_concept"],
                          TSLA_GOLDEN["periods"]["CY2024"]["period_end"], frame="")
        )
        _assert_close(val, TSLA_GOLDEN["periods"]["CY2024"]["total_assets"], "TSLA CY2024 total_assets")

    def test_segment_revenue_not_chosen_over_consolidated(self, db_session):
        """The DB must contain BOTH framed (consolidated) and unframed (segment)
        rows for Tesla revenue. The framed row must equal the golden consolidated value."""
        framed = _get_value(
            db_session, "TSLA",
            TSLA_GOLDEN["revenue_concept"],
            TSLA_GOLDEN["periods"]["CY2024"]["period_end"],
            frame="CY2024",
        )
        assert framed is not None, "No framed (consolidated) CY2024 revenue in DB"

        # Segment rows exist with frame=''
        from sqlalchemy import func
        seg_count = db_session.execute(
            select(func.count())
            .select_from(FinancialLineItemORM)
            .join(FilingORM, FinancialLineItemORM.filing_id == FilingORM.id)
            .join(CompanyORM, FilingORM.company_id == CompanyORM.id)
            .where(
                CompanyORM.ticker == "TSLA",
                FinancialLineItemORM.concept == TSLA_GOLDEN["revenue_concept"],
                FinancialLineItemORM.frame == "",
            )
        ).scalar()
        assert seg_count > 0, "No segment revenue rows (frame='') in DB — A2 fix may have over-filtered"

        _assert_close(framed, TSLA_GOLDEN["periods"]["CY2024"]["revenue"],
                      "TSLA CY2024 consolidated revenue")


# ---------------------------------------------------------------------------
# Apple — unframed values (non-calendar FY fallback path)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestAppleDB:

    def test_revenue_fy2024(self, db_session):
        val = _get_value(
            db_session, "AAPL",
            AAPL_GOLDEN["revenue_concept"],
            AAPL_GOLDEN["periods"]["FY2024"]["period_end"],
            frame="",
        )
        _assert_close(val, AAPL_GOLDEN["periods"]["FY2024"]["revenue"], "AAPL FY2024 revenue")

    def test_revenue_fy2023(self, db_session):
        val = _get_value(
            db_session, "AAPL",
            AAPL_GOLDEN["revenue_concept"],
            AAPL_GOLDEN["periods"]["FY2023"]["period_end"],
            frame="",
        )
        _assert_close(val, AAPL_GOLDEN["periods"]["FY2023"]["revenue"], "AAPL FY2023 revenue")

    def test_net_income_fy2024(self, db_session):
        val = _get_value(
            db_session, "AAPL",
            AAPL_GOLDEN["net_income_concept"],
            AAPL_GOLDEN["periods"]["FY2024"]["period_end"],
            frame="",
        )
        _assert_close(val, AAPL_GOLDEN["periods"]["FY2024"]["net_income"], "AAPL FY2024 net_income")

    def test_total_assets_fy2024(self, db_session):
        val = _get_value(
            db_session, "AAPL",
            AAPL_GOLDEN["assets_concept"],
            AAPL_GOLDEN["periods"]["FY2024"]["period_end"],
            frame="",
        )
        _assert_close(val, AAPL_GOLDEN["periods"]["FY2024"]["total_assets"], "AAPL FY2024 total_assets")
