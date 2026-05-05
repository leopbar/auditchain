"""Repository for persisting audit results to the database.

This module handles AuditRun, AgentStep, and RedFlag persistence using
the SQLAlchemy ORM models.
"""

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from auditchain.core.logging import get_logger
from auditchain.data.models import AuditRunORM, AgentStepORM, RedFlagORM
from auditchain.schemas.components import RedFlag

logger = get_logger(__name__)


class AuditRepository:
    """Repository to manage audit-related data persistence."""

    def __init__(self, session: Session):
        self.session = session

    def create_run(
        self, 
        company_id: int, 
        audit_run_id: str, 
        filing_id: int | None = None,
        langgraph_thread_id: str | None = None
    ) -> AuditRunORM:
        """Creates a new audit run record in the database."""
        logger.info("audit_repo_create_run", audit_run_id=audit_run_id, company_id=company_id)
        run = AuditRunORM(
            id=audit_run_id,
            company_id=company_id,
            filing_id=filing_id,
            status="running",
            langgraph_thread_id=langgraph_thread_id,
            started_at=datetime.now()
        )
        self.session.add(run)
        self.session.flush()
        return run

    def complete_run(
        self, 
        run_id: str, 
        risk_score: float, 
        risk_level: str, 
        total_tokens: int, 
        total_cost_usd: float, 
        final_report_json: dict
    ) -> AuditRunORM:
        """Updates an existing run with completion status and final results."""
        logger.info("audit_repo_complete_run", run_id=run_id, risk_score=risk_score)
        run = self.get_run(run_id)
        if not run:
            raise ValueError(f"AuditRun {run_id} not found")
        
        run.status = "completed"
        run.risk_score = risk_score
        run.risk_level = risk_level
        run.total_tokens = total_tokens
        run.total_cost_usd = total_cost_usd
        run.final_report = final_report_json
        run.completed_at = datetime.now()
        
        self.session.flush()
        return run

    def fail_run(self, run_id: str, error_message: str) -> AuditRunORM:
        """Marks an audit run as failed and records the error."""
        logger.info("audit_repo_fail_run", run_id=run_id, error=error_message)
        run = self.get_run(run_id)
        if not run:
            raise ValueError(f"AuditRun {run_id} not found")
        
        run.status = "failed"
        run.completed_at = datetime.now()
        run.final_report = {"error": error_message}
        
        self.session.flush()
        return run

    def add_agent_step(
        self, 
        run_id: str, 
        agent_name: str, 
        step_index: int, 
        input_data: dict | None = None, 
        output_data: dict | None = None, 
        tool_calls_data: dict | None = None, 
        latency_ms: int | None = None, 
        tokens_input: int | None = None, 
        tokens_output: int | None = None, 
        cost_usd: float | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None
    ) -> AgentStepORM:
        """Records a single step performed by an agent during a run."""
        logger.info("audit_repo_add_step", run_id=run_id, agent=agent_name, step=step_index)
        step = AgentStepORM(
            run_id=run_id,
            agent_name=agent_name,
            step_index=step_index,
            input=input_data,
            output=output_data,
            tool_calls=tool_calls_data,
            latency_ms=latency_ms,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_usd=cost_usd,
            started_at=started_at,
            completed_at=completed_at
        )
        self.session.add(step)
        self.session.flush()
        return step

    def add_red_flag(
        self, 
        run_id: str, 
        detected_by: str, 
        category: str, 
        severity: str, 
        title: str, 
        description: str, 
        evidence_json: list | None = None, 
        rationale: str | None = None, 
        confidence: float | None = None
    ) -> RedFlagORM:
        """Persists a detected red flag in the database."""
        logger.info("audit_repo_add_red_flag", run_id=run_id, category=category, severity=severity)
        flag = RedFlagORM(
            run_id=run_id,
            detected_by=detected_by,
            category=category,
            severity=severity,
            title=title,
            description=description,
            evidence=evidence_json,
            rationale=rationale,
            confidence=confidence
        )
        self.session.add(flag)
        self.session.flush()
        return flag

    def add_red_flags_from_list(self, run_id: str, red_flags: list[RedFlag]):
        """Helper to batch insert red flags from a list of Pydantic models."""
        logger.info("audit_repo_add_red_flags_list", run_id=run_id, count=len(red_flags))
        for flag in red_flags:
            self.add_red_flag(
                run_id=run_id,
                detected_by=flag.detected_by,
                category=flag.category.value if hasattr(flag.category, 'value') else flag.category,
                severity=flag.severity.value if hasattr(flag.severity, 'value') else flag.severity,
                title=flag.title,
                description=flag.description,
                evidence_json=[e.model_dump() for e in flag.evidence],
                confidence=flag.confidence
            )

    def get_run(self, run_id: str) -> AuditRunORM | None:
        """Retrieves an audit run by its UUID."""
        return self.session.get(AuditRunORM, run_id)

    def list_runs(self, limit: int = 20) -> list[AuditRunORM]:
        """Lists the most recent audit runs."""
        stmt = select(AuditRunORM).order_by(AuditRunORM.started_at.desc()).limit(limit)
        return list(self.session.execute(stmt).scalars().all())
