"""API router for company-related endpoints.

Provides functionality to list companies and retrieve detailed profiles, 
including filing counts and indexing status.
"""

from typing import List
from fastapi import APIRouter, HTTPException, Path, Depends
from sqlalchemy import select, func, exists
from sqlalchemy.orm import Session

from auditchain.core.logging import get_logger
from auditchain.data.database import get_session
from auditchain.data.models import CompanyORM, FilingORM, DisclosureORM
from auditchain.api.schemas.responses import CompanyResponse, CompanyListResponse
from auditchain.auth.dependencies import get_current_user

logger = get_logger(__name__)
router = APIRouter(
    prefix="/api/companies", 
    tags=["companies"],
    dependencies=[Depends(get_current_user)]
)

@router.get("/", response_model=CompanyListResponse)
async def list_companies():
    """Returns a list of all tracked companies with summary statistics."""
    try:
        with get_session() as session:
            # Subquery to count filings per company
            filings_count_sub = (
                select(func.count(FilingORM.id))
                .where(FilingORM.company_id == CompanyORM.id)
                .scalar_subquery()
            )
            
            # Subquery to check if company has any indexed text
            indexed_exists_sub = exists().where(
                DisclosureORM.filing_id == FilingORM.id,
                FilingORM.company_id == CompanyORM.id,
                DisclosureORM.embedding != None
            )
            
            # Main query
            stmt = select(
                CompanyORM, 
                filings_count_sub.label("filings_count"),
                indexed_exists_sub.label("has_text_indexed")
            ).order_by(CompanyORM.name.asc())
            
            results = session.execute(stmt).all()
            
            companies = []
            for row in results:
                company_orm, filings_count, has_text_indexed = row
                companies.append(CompanyResponse(
                    cik=company_orm.cik,
                    ticker=company_orm.ticker,
                    name=company_orm.name,
                    is_known_fraud=company_orm.is_known_fraud,
                    fraud_notes=company_orm.fraud_notes,
                    filings_count=filings_count or 0,
                    has_text_indexed=has_text_indexed
                ))
                
            return CompanyListResponse(
                companies=companies,
                total=len(companies)
            )
    except Exception as e:
        logger.error("api_list_companies_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{cik}", response_model=CompanyResponse)
async def get_company(
    cik: str = Path(..., pattern=r"^\d{10}$", description="The 10-digit CIK of the company")
):
    """Retrieves detailed information for a specific company by its CIK."""
    try:
        with get_session() as session:
            # Reusable subqueries
            filings_count_sub = (
                select(func.count(FilingORM.id))
                .where(FilingORM.company_id == CompanyORM.id)
                .scalar_subquery()
            )
            indexed_exists_sub = exists().where(
                DisclosureORM.filing_id == FilingORM.id,
                FilingORM.company_id == CompanyORM.id,
                DisclosureORM.embedding != None
            )
            
            stmt = select(
                CompanyORM,
                filings_count_sub.label("filings_count"),
                indexed_exists_sub.label("has_text_indexed")
            ).where(CompanyORM.cik == cik)
            
            result = session.execute(stmt).first()
            
            if not result:
                raise HTTPException(status_code=404, detail="Company not found")
                
            company_orm, filings_count, has_text_indexed = result
            return CompanyResponse(
                cik=company_orm.cik,
                ticker=company_orm.ticker,
                name=company_orm.name,
                is_known_fraud=company_orm.is_known_fraud,
                fraud_notes=company_orm.fraud_notes,
                filings_count=filings_count or 0,
                has_text_indexed=has_text_indexed
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("api_get_company_failed", cik=cik, error=str(e))
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
