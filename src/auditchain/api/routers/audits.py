"""API router for audit-related endpoints.

Handles audit execution requests, real-time status streaming via SSE, 
and retrieval of historical audit results and traces.
"""

import uuid
import asyncio
from typing import Optional, List
from fastapi import APIRouter, HTTPException, BackgroundTasks, status, Path, Query, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from auditchain.core.logging import get_logger
from auditchain.data.database import get_session
from auditchain.data.models import CompanyORM, FilingORM, AuditRunORM, AgentStepORM, RedFlagORM
from auditchain.api.schemas.responses import (
    CreateAuditRequest, 
    CreateAuditResponse, 
    AuditRunSummary, 
    AuditRunListResponse, 
    AuditRunDetailResponse
)
from auditchain.api.events.subscriber import subscribe_to_audit
from auditchain.api.services.audit_runner import run_audit_with_streaming
from auditchain.auth.dependencies import get_current_user

logger = get_logger(__name__)
router = APIRouter(
    prefix="/api/audits", 
    tags=["audits"],
    dependencies=[Depends(get_current_user)]
)

# Concurrency control
_audit_in_progress = False
_lock = asyncio.Lock()

async def _run_audit_wrapper(run_id: str, cik: str, model: str):
    """Safely runs the audit background task and resets the progress flag."""
    global _audit_in_progress
    try:
        await run_audit_with_streaming(run_id=run_id, cik=cik, model=model)
    finally:
        async with _lock:
            _audit_in_progress = False
            logger.info("audit_lock_released", run_id=run_id)

@router.post("/", response_model=CreateAuditResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_audit(request: CreateAuditRequest, background_tasks: BackgroundTasks):
    """Initiates a new multi-agent audit for a specific company."""
    global _audit_in_progress
    
    async with _lock:
        if _audit_in_progress:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, 
                detail="An audit is already running. Please wait for it to complete."
            )
        
        # Verify company exists
        with get_session() as session:
            company = session.scalar(select(CompanyORM).where(CompanyORM.cik == request.cik))
            if not company:
                raise HTTPException(status_code=404, detail="Company not found in database.")
                
        run_id = str(uuid.uuid4())
        _audit_in_progress = True
        logger.info("audit_lock_acquired", run_id=run_id, cik=request.cik)
        
    background_tasks.add_task(_run_audit_wrapper, run_id, request.cik, request.model)
    
    return CreateAuditResponse(
        run_id=run_id,
        status="running",
        message="Audit started in background",
        stream_url=f"/api/audits/{run_id}/stream"
    )

@router.get("/{run_id}/stream")
async def stream_audit_progress(
    run_id: str = Path(..., description="The unique UUID of the audit run")
):
    """Endpoint for Server-Sent Events (SSE) to track audit progress in real-time."""
    return StreamingResponse(
        subscribe_to_audit(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )

@router.get("/", response_model=AuditRunListResponse)
async def list_audits(
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status (pending, completed, failed)")
):
    """Returns a list of recent audit executions."""
    try:
        with get_session() as session:
            # Subquery to count red flags
            flags_count_sub = (
                select(func.count(RedFlagORM.id))
                .where(RedFlagORM.run_id == AuditRunORM.id)
                .scalar_subquery()
            )
            
            stmt = select(
                AuditRunORM,
                CompanyORM.name.label("company_name"),
                CompanyORM.ticker.label("company_ticker"),
                CompanyORM.cik.label("company_cik"),
                flags_count_sub.label("red_flags_count")
            ).join(
                CompanyORM, AuditRunORM.company_id == CompanyORM.id
            )
            
            if status:
                stmt = stmt.where(AuditRunORM.status == status)
                
            stmt = stmt.order_by(desc(AuditRunORM.started_at)).limit(limit)
            results = session.execute(stmt).all()
            
            audits = []
            for row in results:
                run, name, ticker, cik, flags_count = row
                
                duration = None
                if run.started_at and run.completed_at:
                    duration = (run.completed_at - run.started_at).total_seconds()
                    
                audits.append(AuditRunSummary(
                    run_id=str(run.id),
                    company_cik=cik,
                    company_name=name,
                    company_ticker=ticker,
                    status=run.status,
                    conclusion=run.final_report.get("audit_conclusion") if run.final_report else None,
                    risk_score=float(run.risk_score) if run.risk_score is not None else None,
                    risk_level=run.risk_level,
                    red_flags_count=flags_count or 0,
                    started_at=run.started_at,
                    completed_at=run.completed_at,
                    duration_seconds=duration
                ))
                
            return AuditRunListResponse(
                audits=audits,
                total=len(audits)
            )
    except Exception as e:
        logger.error("api_list_audits_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{run_id}", response_model=AuditRunDetailResponse)
async def get_audit_detail(
    run_id: str = Path(..., description="The unique UUID of the audit run")
):
    """Returns full details, findings, and traces for a specific audit run."""
    try:
        run_uuid = uuid.UUID(run_id)
        with get_session() as session:
            # Query run with company info (now linked directly via company_id)
            stmt = select(
                AuditRunORM,
                CompanyORM.name.label("company_name"),
                CompanyORM.ticker.label("company_ticker"),
                CompanyORM.cik.label("company_cik")
            ).join(
                CompanyORM, AuditRunORM.company_id == CompanyORM.id
            ).where(AuditRunORM.id == run_uuid)
            
            result = session.execute(stmt).first()
            if not result:
                raise HTTPException(status_code=404, detail="Audit run not found")
                
            run, name, ticker, cik = result
            
            # Fetch steps and flags
            steps = session.scalars(
                select(AgentStepORM).where(AgentStepORM.run_id == run_uuid).order_by(AgentStepORM.step_index)
            ).all()
            
            flags = session.scalars(
                select(RedFlagORM).where(RedFlagORM.run_id == run_uuid)
            ).all()
            
            return AuditRunDetailResponse(
                run_id=str(run.id),
                company_cik=cik,
                company_name=name,
                company_ticker=ticker,
                status=run.status,
                conclusion=run.final_report.get("audit_conclusion") if run.final_report else None,
                risk_score=float(run.risk_score) if run.risk_score is not None else None,
                risk_level=run.risk_level,
                needs_human_review=run.final_report.get("needs_human_review", False) if run.final_report else False,
                started_at=run.started_at,
                completed_at=run.completed_at,
                total_tokens=run.total_tokens,
                total_cost_usd=float(run.total_cost_usd) if run.total_cost_usd is not None else None,
                final_report=run.final_report,
                red_flags=[{
                    "detected_by": f.detected_by,
                    "category": f.category,
                    "severity": f.severity,
                    "title": f.title,
                    "description": f.description,
                    "confidence": float(f.confidence) if f.confidence is not None else None
                } for f in flags],
                agent_steps=[{
                    "agent_name": s.agent_name,
                    "step_index": s.step_index,
                    "latency_ms": s.latency_ms,
                    "tokens_input": s.tokens_input,
                    "tokens_output": s.tokens_output,
                    "cost_usd": float(s.cost_usd) if s.cost_usd is not None else None
                } for s in steps]
            )
            
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id format. Must be a UUID.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("api_get_audit_failed", run_id=run_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
