"""AuditChain State Definition for LangGraph.

This module defines the AuditState, the central data structure that circulates 
through the LangGraph workflow during an audit. Each agent reads from this state
and writes its specific structured output into dedicated fields.

Unlike the previous MVP which relied solely on messages, this version uses 
structured Pydantic schemas for inter-agent communication and state management.
"""

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from auditchain.schemas.components import RedFlag, AgentStepMetrics
from auditchain.schemas.enums import AuditPhase, FlagSeverity
from auditchain.schemas.reports import (
    AuditReport,
    CompanyData,
    InvestigationReport,
    QuantAnalysisReport,
    ReconciliationReport,
    RiskAssessment,
)


class AuditState(TypedDict):
    """The complete state of an ongoing audit process.
    
    Fields marked with Annotated[..., operator.add] or add_messages are cumulative,
    meaning multiple agents can contribute to them (e.g., adding red flags or messages).
    All other fields are replaced when updated by an agent.
    """

    # Identification
    audit_run_id: str
    company_cik: str
    company_ticker: str | None

    # Flow control
    current_phase: AuditPhase

    # Filing info
    target_filing_id: int | None

    # Conversation history (cumulative)
    messages: Annotated[list[AnyMessage], add_messages]

    # Structured outputs (replaced by specific agents)
    risk_assessment: RiskAssessment | None
    company_data: CompanyData | None
    reconciliation: ReconciliationReport | None
    quant_analysis: QuantAnalysisReport | None
    investigation: InvestigationReport | None
    final_report: AuditReport | None

    # Cumulative fields (multiple agents contribute)
    red_flags: Annotated[list[RedFlag], operator.add]
    errors: Annotated[list[str], operator.add]
    agent_steps_data: Annotated[list[AgentStepMetrics], operator.add]

    # Control and metrics
    needs_human_review: bool
    total_tokens: Annotated[int, operator.add]
    total_cost_usd: Annotated[float, operator.add]


def create_initial_state(
    audit_run_id: str, 
    company_cik: str, 
    company_ticker: str | None = None
) -> dict:
    """Produces a clean initial state for invoking the audit graph.
    
    Args:
        audit_run_id: Unique UUID for the audit run.
        company_cik: SEC Central Index Key for the target company.
        company_ticker: Stock ticker symbol if known.
        
    Returns:
        A dictionary initialized with all AuditState fields.
    """
    return {
        "audit_run_id": audit_run_id,
        "company_cik": company_cik,
        "company_ticker": company_ticker,
        "current_phase": AuditPhase.PLANNING,
        "target_filing_id": None,
        "messages": [],
        "risk_assessment": None,
        "company_data": None,
        "reconciliation": None,
        "quant_analysis": None,
        "investigation": None,
        "final_report": None,
        "red_flags": [],
        "errors": [],
        "agent_steps_data": [],
        "needs_human_review": False,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
    }


def get_completed_phases(state: AuditState) -> list[str]:
    """Returns a list of phase names that have already produced structured output.
    
    Args:
        state: The current audit state.
        
    Returns:
        A list of completed phase names (e.g., ["planning", "collection"]).
    """
    completed = []
    if state.get("risk_assessment") is not None:
        completed.append("planning")
    if state.get("company_data") is not None:
        completed.append("collection")
    if state.get("reconciliation") is not None:
        completed.append("reconciliation")
    if state.get("quant_analysis") is not None:
        completed.append("quant_analysis")
    if state.get("investigation") is not None:
        completed.append("investigation")
    if state.get("final_report") is not None:
        completed.append("supervision")
    return completed


def count_red_flags_by_severity(state: AuditState) -> dict[str, int]:
    """Returns a count of red flags grouped by their severity level.
    
    Args:
        state: The current audit state.
        
    Returns:
        A dictionary mapping severity names to counts.
    """
    counts = {s.value: 0 for s in FlagSeverity}
    for flag in state.get("red_flags", []):
        counts[flag.severity.value] += 1
    return counts


def count_red_flags_by_agent(state: AuditState) -> dict[str, int]:
    """Returns a count of red flags grouped by the agent that detected them.
    
    Args:
        state: The current audit state.
        
    Returns:
        A dictionary mapping agent names to counts.
    """
    counts = {}
    for flag in state.get("red_flags", []):
        agent = flag.detected_by
        counts[agent] = counts.get(agent, 0) + 1
    return counts


def state_summary(state: AuditState) -> str:
    """Returns a multi-line string summarizing the current state of the audit.
    
    Useful for logging and debugging.
    """
    completed = get_completed_phases(state)
    severity_counts = count_red_flags_by_severity(state)
    total_flags = sum(severity_counts.values())
    
    summary = [
        f"Audit Run ID: {state['audit_run_id']}",
        f"Company:      {state['company_cik']} ({state['company_ticker'] or 'N/A'})",
        f"Current Phase: {state['current_phase'].value}",
        f"Completed:     {', '.join(completed) if completed else 'None'}",
        f"Red Flags:     {total_flags} {severity_counts}",
        f"Cost/Usage:    ${state['total_cost_usd']:.4f} ({state['total_tokens']} tokens)",
        f"Errors:        {len(state['errors'])}"
    ]
    return "\n".join(summary)
