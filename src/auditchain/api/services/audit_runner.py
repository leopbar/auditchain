"""Background task runner for audit execution with real-time event streaming.

Orchestrates the LangGraph audit workflow and emits progress events to the 
Pub/Sub system for live dashboard updates.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select

from auditchain.core.logging import get_logger
from auditchain.graph.workflow import build_audit_graph
from auditchain.graph.state import create_initial_state
from auditchain.schemas.enums import AuditPhase
from auditchain.data.database import get_session
from auditchain.data.models import CompanyORM
from auditchain.data.audit_repository import AuditRepository

# Event schemas and publisher
from auditchain.api.events.publisher import get_publisher
from auditchain.api.events.callbacks import AuditChainCallbackHandler
from auditchain.api.events.schemas import (
    AuditStartedEvent, 
    PhaseStartedEvent, 
    PhaseCompletedEvent, 
    PhaseFailedEvent, 
    AuditCompletedEvent, 
    AuditFailedEvent
)

PHASE_ORDER = ["collector", "reconciler", "quant_analyst", "investigator", "supervisor"]

AGENT_DISPLAY_NAMES = {
    "collector": "Collector Agent",
    "reconciler": "Reconciler Agent",
    "quant_analyst": "Quantitative Analyst",
    "investigator": "Investigator Agent",
    "supervisor": "Supervisor Agent",
}

def extract_phase_summary(phase: str, state_update: Dict[str, Any]) -> Dict[str, Any]:
    """Extracts a concise summary of the results from a completed phase."""
    try:
        if phase == "collector":
            cd = state_update.get("company_data")
            if cd:
                return {
                    "company_name": cd.name,
                    "ticker": cd.ticker,
                    "filings_count": 1 + len(cd.historical_periods),
                    "current_period_year": cd.current_period.fiscal_year
                }
        
        elif phase == "reconciler":
            rec = state_update.get("reconciliation")
            if rec:
                return {
                    "passed": rec.passed,
                    "checks_count": len(rec.checks),
                    "summary": rec.summary[:150]
                }
        
        elif phase == "quant_analyst":
            qa = state_update.get("quant_analysis")
            if qa:
                return {
                    "beneish_mscore": qa.beneish_mscore,
                    "altman_zscore": qa.altman_zscore,
                    "accruals_ratio": qa.accruals_ratio,
                    "summary": qa.summary[:150]
                }
        
        elif phase == "investigator":
            inv = state_update.get("investigation")
            if inv:
                return {
                    "evasive_language": inv.evasive_language_detected,
                    "related_parties_count": len(inv.related_parties_detected),
                    "summary": inv.summary[:150]
                }
        
        elif phase == "supervisor":
            fr = state_update.get("final_report")
            if fr:
                return {
                    "risk_score": fr.risk_score,
                    "conclusion": fr.audit_conclusion.value if hasattr(fr.audit_conclusion, 'value') else str(fr.audit_conclusion),
                    "risk_level": fr.risk_level.value if hasattr(fr.risk_level, 'value') else str(fr.risk_level),
                    "executive_summary": fr.executive_summary[:300]
                }
        
        return {"info": f"Phase {phase} completed"}
    except Exception as e:
        return {"error": f"Failed to extract summary: {str(e)}"}

async def run_audit_with_streaming(run_id: str, cik: str, model: str = "gpt-4o-mini") -> None:
    """Orchestrates an audit run while emitting real-time events via Pub/Sub.
    
    This is intended to be run as a background task. It uses the LangGraph 
    .astream() method to gain visibility into individual node completions.
    """
    publisher = get_publisher()
    logger = get_logger(__name__)
    audit_start_time = time.time()
    
    log = logger.bind(run_id=run_id, cik=cik)
    log.info("audit_runner_started")
    
    # 1. Fetch company info for the starting event
    company_name = "Unknown"
    company_ticker = None
    with get_session() as session:
        company = session.scalar(select(CompanyORM).where(CompanyORM.cik == cik))
        if company:
            company_name = company.name
            company_ticker = company.ticker
            
    # 2. Initialize audit run in database
    try:
        with get_session() as session:
            repo = AuditRepository(session)
            # Find the company ID
            company = session.scalar(select(CompanyORM).where(CompanyORM.cik == cik))
            if company:
                # Create the record. filing_id is None for now, will be updated in supervisor.
                repo.create_run(company_id=company.id, audit_run_id=run_id)
                session.commit()
                log.info("audit_run_record_initialized", company_id=company.id)
            else:
                log.error("audit_run_initialization_failed_company_not_found", cik=cik)
    except Exception as e:
        log.error("audit_run_initialization_failed", error=str(e))
        # We continue anyway as the stream can still work

    # 3. Emit audit_started event
    await publisher.publish(AuditStartedEvent(
        run_id=run_id,
        elapsed_seconds=0.0,
        company_cik=cik,
        company_name=company_name,
        company_ticker=company_ticker,
        model=model,
    ))
    
    # 3. Setup LangGraph components
    callback = AuditChainCallbackHandler(run_id=run_id, audit_started_at=audit_start_time)
    graph = build_audit_graph()
    initial_state = create_initial_state(
        audit_run_id=run_id,
        company_cik=cik,
        company_ticker=company_ticker,
    )
    
    accumulated_state = dict(initial_state)
    red_flags_count_before = 0
    phase_start_time = time.time()
    current_phase_idx = 0
    
    try:
        # Emit phase_started for the first phase
        first_phase = PHASE_ORDER[0]
        callback.set_current_phase(first_phase)
        await publisher.publish(PhaseStartedEvent(
            run_id=run_id,
            elapsed_seconds=time.time() - audit_start_time,
            phase=first_phase,
            agent_name=AGENT_DISPLAY_NAMES[first_phase],
        ))
        phase_start_time = time.time()
        
        # 4. Stream graph execution
        async for chunk in graph.astream(
            initial_state,
            config={"callbacks": [callback]},
            stream_mode="updates"
        ):
            for node_name, state_update in chunk.items():
                if node_name not in PHASE_ORDER:
                    continue  # Skip internal routing nodes or non-agent nodes
                
                # Merge update into our local tracking state
                for key, value in state_update.items():
                    if key == "red_flags":
                        accumulated_state.setdefault("red_flags", []).extend(value)
                    elif key == "messages":
                        accumulated_state.setdefault("messages", []).extend(value)
                    elif key in ("total_tokens", "total_cost_usd"):
                        accumulated_state[key] = accumulated_state.get(key, 0) + value
                    else:
                        accumulated_state[key] = value
                
                # Calculate metrics for the event
                total_flags_now = len(accumulated_state.get("red_flags", []))
                flags_added = total_flags_now - red_flags_count_before
                red_flags_count_before = total_flags_now
                
                tokens_used = accumulated_state.get("total_tokens", 0)
                cost_usd = accumulated_state.get("total_cost_usd", 0.0)
                phase_duration = time.time() - phase_start_time
                
                # Handle Phase Failure
                current_state_phase = state_update.get("current_phase")
                if current_state_phase == AuditPhase.FAILED:
                    errors = state_update.get("errors", [])
                    error_msg = errors[-1] if errors else "Unknown error during graph execution"
                    
                    await publisher.publish(PhaseFailedEvent(
                        run_id=run_id,
                        elapsed_seconds=time.time() - audit_start_time,
                        phase=node_name,
                        error_message=error_msg,
                    ))
                    await publisher.publish(AuditFailedEvent(
                        run_id=run_id,
                        elapsed_seconds=time.time() - audit_start_time,
                        failed_phase=node_name,
                        error_message=error_msg,
                    ))
                    log.error("audit_runner_phase_failed", phase=node_name, error=error_msg)
                    
                    # Persist failure
                    try:
                        with get_session() as session:
                            repo = AuditRepository(session)
                            repo.fail_run(run_id, error_msg)
                            session.commit()
                    except Exception as db_err:
                        log.error("audit_runner_fail_persistence_failed", error=str(db_err))
                        
                    return 
                
                # Emit Phase Completion
                summary = extract_phase_summary(node_name, accumulated_state)
                await publisher.publish(PhaseCompletedEvent(
                    run_id=run_id,
                    elapsed_seconds=time.time() - audit_start_time,
                    phase=node_name,
                    agent_name=AGENT_DISPLAY_NAMES[node_name],
                    duration_seconds=phase_duration,
                    tokens_used=state_update.get("total_tokens", 0),
                    cost_usd=state_update.get("total_cost_usd", 0.0),
                    summary=summary,
                    red_flags_added=flags_added,
                ))
                
                # Start Next Phase (if applicable)
                current_phase_idx = PHASE_ORDER.index(node_name) + 1
                if current_phase_idx < len(PHASE_ORDER):
                    next_phase = PHASE_ORDER[current_phase_idx]
                    callback.set_current_phase(next_phase)
                    await publisher.publish(PhaseStartedEvent(
                        run_id=run_id,
                        elapsed_seconds=time.time() - audit_start_time,
                        phase=next_phase,
                        agent_name=AGENT_DISPLAY_NAMES[next_phase],
                    ))
                    phase_start_time = time.time()
                    
        # 5. Finalize Audit
        final_report = accumulated_state.get("final_report")
        if final_report is None:
            await publisher.publish(AuditFailedEvent(
                run_id=run_id,
                elapsed_seconds=time.time() - audit_start_time,
                failed_phase="supervisor",
                error_message="Supervisor phase completed but no final_report was produced",
            ))
            log.error("audit_runner_no_final_report")
            return
            
        # Serialize report and emit completion
        final_report_dict = final_report.model_dump(mode="json")
        
        await publisher.publish(AuditCompletedEvent(
            run_id=run_id,
            elapsed_seconds=time.time() - audit_start_time,
            final_report=final_report_dict,
            risk_score=final_report.risk_score,
            risk_level=final_report.risk_level.value if hasattr(final_report.risk_level, 'value') else str(final_report.risk_level),
            conclusion=final_report.audit_conclusion.value if hasattr(final_report.audit_conclusion, 'value') else str(final_report.audit_conclusion),
            total_tokens=accumulated_state.get("total_tokens", 0),
            total_cost_usd=accumulated_state.get("total_cost_usd", 0.0),
            total_duration_seconds=time.time() - audit_start_time,
            needs_human_review=accumulated_state.get("needs_human_review", False),
        ))
        log.info("audit_runner_completed", risk_score=final_report.risk_score)
        
    except Exception as e:
        log.exception("audit_runner_unexpected_failure")
        failed_phase = PHASE_ORDER[current_phase_idx] if current_phase_idx < len(PHASE_ORDER) else "unknown"
        await publisher.publish(AuditFailedEvent(
            run_id=run_id,
            elapsed_seconds=time.time() - audit_start_time,
            failed_phase=failed_phase,
            error_message=str(e),
        ))

        # Persist failure
        try:
            with get_session() as session:
                repo = AuditRepository(session)
                repo.fail_run(run_id, str(e))
                session.commit()
        except Exception as db_err:
            log.error("audit_runner_unexpected_fail_persistence_failed", error=str(db_err))
    finally:
        # Always close the stream to signal the frontend
        await publisher.close(run_id)
        log.info("audit_runner_finalized")
