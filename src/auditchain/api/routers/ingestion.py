"""API router for company ingestion endpoints.

Handles adding new companies to the AuditChain database via a multi-stage
pipeline (validate CIK, download facts, download filings, parse XBRL,
embed text) with real-time progress streaming via SSE.
"""

import uuid
import asyncio
import time
from typing import Optional, Dict, Any, List

import httpx
from fastapi import APIRouter, HTTPException, BackgroundTasks, status, Path, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func

from auditchain.core.config import get_settings
from auditchain.core.logging import get_logger
from auditchain.data.database import get_session
from auditchain.data.models import CompanyORM, FilingORM, AuditRunORM
from auditchain.data.ingestion_repository import IngestionRepository
from auditchain.data.models import IngestionRunORM
from auditchain.schemas.ingestion import (
    CreateIngestionRequest,
    CreateIngestionResponse,
)
from auditchain.api.events.ingestion_subscriber import subscribe_to_ingestion
from auditchain.api.services.ingestion_runner import run_ingestion_with_streaming

logger = get_logger(__name__)
router = APIRouter(prefix="/api/companies", tags=["ingestion"])

# SEC Directory Cache
_sec_directory_cache: Optional[Dict[str, Any]] = None
_sec_directory_timestamp: float = 0
SEC_DIRECTORY_TTL = 24 * 3600  # 24 hours

# Concurrency control — only one ingestion at a time
_ingestion_in_progress: bool = False
_ingestion_lock = asyncio.Lock()


@router.get("/sec-directory")
async def get_sec_directory():
    """Proxy for SEC company_tickers.json to bypass CORS.
    
    Normalizes CIKs and caches the result for 24 hours.
    """
    global _sec_directory_cache, _sec_directory_timestamp
    
    now = time.time()
    if _sec_directory_cache and (now - _sec_directory_timestamp < SEC_DIRECTORY_TTL):
        logger.info("sec_directory_cached_hit")
        return _sec_directory_cache

    settings = get_settings()
    url = "https://www.sec.gov/files/company_tickers.json"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url, 
                headers={"User-Agent": settings.sec_user_agent}
            )
            resp.raise_for_status()
            data = resp.json()
            
        # Normalization and Deduplication by CIK
        companies_map = {}
        for item in data.values():
            cik = str(item["cik_str"]).zfill(10)
            if cik not in companies_map:
                companies_map[cik] = {
                    "cik": cik,
                    "ticker": item["ticker"],
                    "name": item["title"]
                }
            
        companies = list(companies_map.values())
        result = {
            "companies": companies,
            "total": len(companies)
        }
        
        _sec_directory_cache = result
        _sec_directory_timestamp = now
        logger.info("sec_directory_fetched_and_cached", total=len(companies))
        return result
        
    except Exception as e:
        logger.error("sec_directory_fetch_failed", error=str(e))
        if _sec_directory_cache:
            logger.warning("returning_stale_sec_directory_cache")
            return _sec_directory_cache
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SEC company directory is currently unavailable. Please try again later."
        )


async def _run_ingestion_wrapper(ingestion_id: str, cik: str, force_update: bool):
    """Safely runs the ingestion background task and resets the progress flag."""
    global _ingestion_in_progress
    try:
        await run_ingestion_with_streaming(
            ingestion_id=ingestion_id,
            cik=cik,
            force_update=force_update,
        )
    finally:
        async with _ingestion_lock:
            _ingestion_in_progress = False
            logger.info("ingestion_lock_released", ingestion_id=ingestion_id)


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT 1 — Start ingestion
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/add", response_model=CreateIngestionResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_ingestion(request: CreateIngestionRequest, background_tasks: BackgroundTasks):
    """Initiates a new company data ingestion pipeline.

    Downloads SEC filings, parses XBRL data, and generates text embeddings
    for a given CIK. Only one ingestion can run at a time.
    """
    global _ingestion_in_progress

    async with _ingestion_lock:
        if _ingestion_in_progress:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An ingestion is already running. Please wait for it to complete.",
            )

        # Check if company already exists
        with get_session() as session:
            existing = session.scalar(
                select(CompanyORM).where(CompanyORM.cik == request.cik)
            )
            if existing and not request.force_update:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Company '{existing.name}' (CIK {request.cik}) already exists "
                        "in the database. Set force_update=true to re-ingest."
                    ),
                )

        ingestion_id = str(uuid.uuid4())
        is_update = existing is not None
        _ingestion_in_progress = True
        logger.info("ingestion_lock_acquired", ingestion_id=ingestion_id, cik=request.cik)

    background_tasks.add_task(
        _run_ingestion_wrapper, ingestion_id, request.cik, request.force_update
    )

    return CreateIngestionResponse(
        ingestion_id=ingestion_id,
        status="running",
        message="Ingestion started in background",
        stream_url=f"/api/companies/add/{ingestion_id}/stream",
    )


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT 2 — Check if company exists
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/check/{cik}")
async def check_company(cik: str = Path(..., pattern=r"^\d{10}$", description="SEC CIK (10 digits)")):
    """Checks whether a company with the given CIK already exists in the database.

    Returns basic info if the company exists, or {"exists": false} otherwise.
    """
    try:
        with get_session() as session:
            company = session.scalar(
                select(CompanyORM).where(CompanyORM.cik == cik)
            )

            if not company:
                return {"exists": False}

            # Count filings
            filings_count = session.scalar(
                select(func.count(FilingORM.id)).where(
                    FilingORM.company_id == company.id
                )
            ) or 0

            # Count audit runs (through filings)
            audit_runs_count = session.scalar(
                select(func.count(AuditRunORM.id)).where(
                    AuditRunORM.filing_id.in_(
                        select(FilingORM.id).where(FilingORM.company_id == company.id)
                    )
                )
            ) or 0

            return {
                "exists": True,
                "company_name": company.name,
                "ticker": company.ticker,
                "filings_count": filings_count,
                "audit_runs_count": audit_runs_count,
            }

    except Exception as e:
        logger.error("api_check_company_failed", cik=cik, error=str(e))
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT 3 — SSE stream for ingestion progress
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/add/{ingestion_id}/stream")
async def stream_ingestion_progress(
    ingestion_id: str = Path(..., description="The unique UUID of the ingestion run"),
):
    """SSE endpoint for real-time ingestion progress updates."""
    return StreamingResponse(
        subscribe_to_ingestion(ingestion_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT 4 — List past ingestion runs
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/ingestions")
async def list_ingestion_runs(
    limit: int = Query(20, ge=1, le=100),
    ingestion_status: Optional[str] = Query(
        None, alias="status", description="Filter by status (running, completed, failed)"
    ),
):
    """Returns a list of recent ingestion runs with summary statistics."""
    try:
        with get_session() as session:
            stmt = select(IngestionRunORM)

            if ingestion_status:
                stmt = stmt.where(IngestionRunORM.status == ingestion_status)

            stmt = stmt.order_by(IngestionRunORM.started_at.desc()).limit(limit)
            runs = session.scalars(stmt).all()

            results = []
            for run in runs:
                duration = None
                if run.started_at and run.completed_at:
                    duration = (run.completed_at - run.started_at).total_seconds()

                results.append({
                    "ingestion_id": str(run.id),
                    "cik": run.cik,
                    "status": run.status,
                    "current_stage": run.current_stage,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                    "duration_seconds": duration,
                    "is_update": run.is_update,
                    "error_message": run.error_message,
                    "filings_count": run.filings_count,
                    "chunks_generated": run.chunks_generated,
                    "financial_items_extracted": run.financial_items_extracted,
                })

            return {"ingestion_runs": results, "total": len(results)}

    except Exception as e:
        logger.error("api_list_ingestions_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
