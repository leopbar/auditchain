"""Main AuditChain workflow definition using LangGraph.

This module connects the specialized agent nodes into a deterministic 
multi-agent pipeline with conditional routing and shared state.
"""

from typing import Literal

from langgraph.graph import END, START, StateGraph

from auditchain.core.logging import get_logger
from auditchain.graph.nodes import (
    collector_node,
    reconciler_node,
    quant_analyst_node,
    investigator_node,
    supervisor_node,
)
from auditchain.graph.state import AuditState
from auditchain.schemas.enums import AuditPhase

logger = get_logger(__name__)


def route_after_collector(state: AuditState) -> Literal["reconciler", "end"]:
    """Decides where to go after data collection phase."""
    if state.get("current_phase") == AuditPhase.FAILED:
        logger.warning("route_after_collector_decision", decision="end", reason="phase_failed")
        return "end"
    
    if state.get("company_data") is None:
        logger.warning("route_after_collector_decision", decision="end", reason="missing_company_data")
        return "end"
    
    logger.info("route_after_collector_decision", decision="reconciler")
    return "reconciler"


def route_after_reconciler(state: AuditState) -> Literal["quant_analyst", "end"]:
    """Decides where to go after mathematical reconciliation phase."""
    if state.get("current_phase") == AuditPhase.FAILED:
        logger.warning("route_after_reconciler_decision", decision="end", reason="phase_failed")
        return "end"

    # Analysis of reconciliation results for observability
    report = state.get("reconciliation")
    if report and not report.passed:
        # Check for critical flags
        critical_flags = [f for f in state.get("red_flags", []) if f.severity in ["high", "critical"]]
        if critical_flags:
            logger.warning(
                "reconciler_detected_critical_risks", 
                flag_count=len(critical_flags),
                summary=report.summary
            )
            # Note: Supervisor Agent will handle state['needs_human_review'] later

    logger.info("route_after_reconciler_decision", decision="quant_analyst")
    return "quant_analyst"


def route_after_quant(state: AuditState) -> Literal["investigator", "end"]:
    """Decides where to go after quantitative analysis phase."""
    if state.get("current_phase") == AuditPhase.FAILED:
        logger.warning("route_after_quant_decision", decision="end", reason="phase_failed")
        return "end"

    logger.info("route_after_quant_decision", decision="investigator")
    return "investigator"


def route_after_investigator(state: AuditState) -> Literal["supervisor", "end"]:
    """Decides where to go after qualitative investigation phase."""
    if state.get("current_phase") == AuditPhase.FAILED:
        logger.warning("route_after_investigator_decision", decision="end", reason="phase_failed")
        return "end"

    logger.info("route_after_investigator_decision", decision="supervisor")
    return "supervisor"


def build_audit_graph():
    """Constructs and compiles the AuditChain StateGraph."""
    workflow = StateGraph(AuditState)

    # Add agent nodes
    workflow.add_node("collector", collector_node)
    workflow.add_node("reconciler", reconciler_node)
    workflow.add_node("quant_analyst", quant_analyst_node)
    workflow.add_node("investigator", investigator_node)
    workflow.add_node("supervisor", supervisor_node)

    # Define edges and routing
    workflow.add_edge(START, "collector")

    workflow.add_conditional_edges(
        "collector",
        route_after_collector,
        {
            "reconciler": "reconciler",
            "end": END
        }
    )

    workflow.add_conditional_edges(
        "reconciler",
        route_after_reconciler,
        {
            "quant_analyst": "quant_analyst",
            "end": END
        }
    )

    workflow.add_conditional_edges(
        "quant_analyst",
        route_after_quant,
        {
            "investigator": "investigator",
            "end": END
        }
    )

    workflow.add_conditional_edges(
        "investigator",
        route_after_investigator,
        {
            "supervisor": "supervisor",
            "end": END
        }
    )

    workflow.add_edge("supervisor", END)

    # Compile
    app = workflow.compile()
    
    logger.info("audit_graph_compiled", node_count=5)
    return app
