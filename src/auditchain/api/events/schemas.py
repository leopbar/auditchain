"""Schemas for Server-Sent Events (SSE).

Defines the structure of real-time events streamed from the audit pipeline 
to the frontend during an active investigation.
"""

from datetime import datetime
from typing import Any, Optional, Union, Literal
from pydantic import BaseModel, Field

class AuditEventBase(BaseModel):
    event_type: str
    run_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    elapsed_seconds: float  # time since audit start

class AuditStartedEvent(AuditEventBase):
    event_type: Literal["audit_started"] = "audit_started"
    company_cik: str
    company_name: str
    company_ticker: Optional[str] = None
    model: str

class PhaseStartedEvent(AuditEventBase):
    event_type: Literal["phase_started"] = "phase_started"
    phase: str  # collector, reconciler, quant_analyst, investigator, supervisor
    agent_name: str  # Friendly name: "Collector Agent"

class ToolCalledEvent(AuditEventBase):
    event_type: Literal["tool_called"] = "tool_called"
    phase: str
    tool_name: str
    tool_input: Optional[dict[str, Any]] = None  # Summarized tool arguments

class ToolCompletedEvent(AuditEventBase):
    event_type: Literal["tool_completed"] = "tool_completed"
    phase: str
    tool_name: str
    duration_ms: int
    success: bool

class PhaseCompletedEvent(AuditEventBase):
    event_type: Literal["phase_completed"] = "phase_completed"
    phase: str
    agent_name: str
    duration_seconds: float
    tokens_used: int
    cost_usd: float
    summary: dict[str, Any]  # Summary of results (varies by phase)
    red_flags_added: int

class PhaseFailedEvent(AuditEventBase):
    event_type: Literal["phase_failed"] = "phase_failed"
    phase: str
    error_message: str

class AuditCompletedEvent(AuditEventBase):
    event_type: Literal["audit_completed"] = "audit_completed"
    final_report: dict[str, Any]  # Full serialized AuditReport
    risk_score: float
    risk_level: str
    conclusion: str
    total_tokens: int
    total_cost_usd: float
    total_duration_seconds: float
    needs_human_review: bool

class AuditFailedEvent(AuditEventBase):
    event_type: Literal["audit_failed"] = "audit_failed"
    failed_phase: str
    error_message: str

# Type alias for any audit event
AuditEvent = Union[
    AuditStartedEvent,
    PhaseStartedEvent,
    ToolCalledEvent,
    ToolCompletedEvent,
    PhaseCompletedEvent,
    PhaseFailedEvent,
    AuditCompletedEvent,
    AuditFailedEvent
]

def event_to_sse(event: AuditEventBase) -> str:
    """Convert event to SSE format string ready for browser consumption."""
    return f"event: {event.event_type}\ndata: {event.model_dump_json()}\n\n"
