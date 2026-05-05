"""Node functions for the AuditChain LangGraph workflow.

Each node wraps a specific agent, manages its invocation, extracts structured 
outputs, and performs the corresponding state updates. Nodes bridge the gap 
between agent intelligence and graph mechanics.
"""

from typing import Any

from langchain_core.messages import HumanMessage, AIMessage

from auditchain.agents.collector import (
    build_collector_agent,
    extract_company_data_from_messages,
)
from auditchain.agents.reconciler import (
    build_reconciler_agent,
    extract_reconciliation_from_messages,
)
from auditchain.agents.quant_analyst import (
    build_quant_analyst_agent,
    extract_quant_analysis_from_messages,
)
from auditchain.agents.investigator import (
    build_investigator_agent,
    extract_investigation_from_messages,
)
from auditchain.agents.investigator import (
    build_investigator_agent,
    extract_investigation_from_messages,
)
from auditchain.agents.supervisor import (
    build_supervisor_agent,
    calculate_risk_score,
    determine_conclusion,
)
from auditchain.core.logging import get_logger
from auditchain.graph.state import AuditState
from auditchain.schemas.enums import AuditPhase, AuditConclusion
from auditchain.schemas.reports import AuditReport
from auditchain.schemas.components import AgentStepMetrics
from datetime import datetime
from auditchain.data.database import get_session
from auditchain.data.audit_repository import AuditRepository

logger = get_logger(__name__)

# Lazy initialization of agents
_collector_agent = None
_reconciler_agent = None
_quant_agent = None
_investigator_agent = None
_supervisor_agent = None


def _get_collector_agent():
    global _collector_agent
    if _collector_agent is None:
        _collector_agent = build_collector_agent()
    return _collector_agent


def _get_reconciler_agent():
    global _reconciler_agent
    if _reconciler_agent is None:
        _reconciler_agent = build_reconciler_agent()
    return _reconciler_agent


def _get_quant_agent():
    global _quant_agent
    if _quant_agent is None:
        _quant_agent = build_quant_analyst_agent()
    return _quant_agent


def _get_investigator_agent():
    global _investigator_agent
    if _investigator_agent is None:
        _investigator_agent = build_investigator_agent()
    return _investigator_agent


def _get_supervisor_agent():
    global _supervisor_agent
    if _supervisor_agent is None:
        _supervisor_agent = build_supervisor_agent()
    return _supervisor_agent


def collector_node(state: AuditState) -> dict[str, Any]:
    """Invokes the Collector Agent and updates the state with structured CompanyData output."""
    log = logger.bind(audit_run_id=state["audit_run_id"], company_cik=state["company_cik"])
    log.info("collector_node_started")
    started_at = datetime.utcnow()

    user_prompt = (
        f"Perform initial data collection for company with CIK={state['company_cik']}"
        + (f" (ticker: {state['company_ticker']})." if state["company_ticker"] else ".")
        + " Identify the company, list its 10-K filings, fetch the most recent filing"
        + " plus at least 3 prior fiscal years for trend analysis. Submit structured CompanyData."
    )

    agent = _get_collector_agent()
    # We invoke the agent with the user prompt
    response = agent.invoke({"messages": [HumanMessage(content=user_prompt)]})
    messages = response.get("messages", [])
    
    company_data = extract_company_data_from_messages(messages)
    
    if company_data is None:
        log.error("collector_node_no_submission")
        return {
            "messages": messages,
            "errors": ["Collector did not submit structured CompanyData"],
            "current_phase": AuditPhase.FAILED,
        }

    # Calculate token usage and cost
    tokens_in = 0
    tokens_out = 0
    
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.usage_metadata:
            input_tokens = msg.usage_metadata.get("input_tokens", 0)
            output_tokens = msg.usage_metadata.get("output_tokens", 0)
            tokens_in += input_tokens
            tokens_out += output_tokens

    total_tokens = tokens_in + tokens_out
    # Approximate cost for GPT-4o
    total_cost = (tokens_in * 0.0025 / 1000) + (tokens_out * 0.01 / 1000)
    
    completed_at = datetime.utcnow()
    latency_ms = int((completed_at - started_at).total_seconds() * 1000)

    metrics = AgentStepMetrics(
        agent_name="collector",
        step_index=0,
        latency_ms=latency_ms,
        tokens_input=tokens_in,
        tokens_output=tokens_out,
        cost_usd=total_cost,
        started_at=started_at,
        completed_at=completed_at
    )

    log.info(
        "collector_node_completed", 
        filing_id=company_data.target_filing_id, 
        historical_periods=len(company_data.historical_periods)
    )
    
    # Return updates to the state
    return {
        "messages": messages,
        "company_data": company_data,
        "target_filing_id": company_data.target_filing_id,
        "current_phase": AuditPhase.RECONCILIATION,
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost,
        "agent_steps_data": [metrics],
    }


def reconciler_node(state: AuditState) -> dict[str, Any]:
    """Invokes the Reconciler Agent and updates the state with mathematical consistency findings."""
    log = logger.bind(audit_run_id=state["audit_run_id"], company_cik=state["company_cik"])
    log.info("reconciler_node_started")
    started_at = datetime.utcnow()

    if state.get("company_data") is None:
        log.error("reconciler_node_missing_data")
        return {
            "errors": ["Reconciler invoked without company_data in state"],
            "current_phase": AuditPhase.FAILED,
        }

    # Prepare input for the agent
    company_data_json = state["company_data"].model_dump_json(indent=2)
    user_prompt = (
        "Perform reconciliation checks on the company data below. "
        "Use check_accounting_equation on the current period, "
        "check_yoy_consistency comparing current vs each historical period, "
        "and compare_income_vs_cashflow on the current period. "
        "Then submit a ReconciliationReport.\n\n"
        f"Data:\n{company_data_json}"
    )

    agent = _get_reconciler_agent()
    response = agent.invoke({"messages": [HumanMessage(content=user_prompt)]})
    messages = response.get("messages", [])

    report = extract_reconciliation_from_messages(messages)

    if report is None:
        log.error("reconciler_node_no_submission")
        return {
            "messages": messages,
            "errors": ["Reconciler did not submit ReconciliationReport"],
            "current_phase": AuditPhase.FAILED,
        }

    # Calculate token usage and cost
    tokens_in = 0
    tokens_out = 0
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.usage_metadata:
            input_tokens = msg.usage_metadata.get("input_tokens", 0)
            output_tokens = msg.usage_metadata.get("output_tokens", 0)
            tokens_in += input_tokens
            tokens_out += output_tokens

    total_tokens = tokens_in + tokens_out
    total_cost = (tokens_in * 0.0025 / 1000) + (tokens_out * 0.01 / 1000)
    
    completed_at = datetime.utcnow()
    latency_ms = int((completed_at - started_at).total_seconds() * 1000)

    metrics = AgentStepMetrics(
        agent_name="reconciler",
        step_index=1,
        latency_ms=latency_ms,
        tokens_input=tokens_in,
        tokens_output=tokens_out,
        cost_usd=total_cost,
        started_at=started_at,
        completed_at=completed_at
    )

    log.info(
        "reconciler_node_completed",
        filing_id=report.filing_id,
        checks_count=len(report.checks),
        red_flags_count=len(report.red_flags),
        passed=report.passed
    )

    return {
        "messages": messages,
        "reconciliation": report,
        "red_flags": report.red_flags,
        "current_phase": AuditPhase.QUANT_ANALYSIS,
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost,
        "agent_steps_data": [metrics]
    }


def quant_analyst_node(state: AuditState) -> dict[str, Any]:
    """Invokes the Quant Analyst Agent and updates the state with fraud model scores."""
    log = logger.bind(audit_run_id=state["audit_run_id"], company_cik=state["company_cik"])
    log.info("quant_analyst_node_started")
    started_at = datetime.utcnow()

    if state.get("company_data") is None:
        log.error("quant_analyst_node_missing_data")
        return {
            "errors": ["Quant Analyst invoked without company_data in state"],
            "current_phase": AuditPhase.FAILED,
        }

    # Prepare input for the agent
    company_data_json = state["company_data"].model_dump_json(indent=2)
    user_prompt = (
        "Perform quantitative fraud detection analysis on the company data below. "
        "Compute Beneish M-Score (using current and first historical period), "
        "Altman Z-Score, and Accruals Ratio. Then submit a QuantAnalysisReport.\n\n"
        f"Data:\n{company_data_json}"
    )

    agent = _get_quant_agent()
    response = agent.invoke({"messages": [HumanMessage(content=user_prompt)]})
    messages = response.get("messages", [])

    report = extract_quant_analysis_from_messages(messages)

    if report is None:
        log.error("quant_analyst_node_no_submission")
        return {
            "messages": messages,
            "errors": ["Quant Analyst did not submit QuantAnalysisReport"],
            "current_phase": AuditPhase.FAILED,
        }

    # Calculate usage
    tokens_in = 0
    tokens_out = 0
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.usage_metadata:
            input_tokens = msg.usage_metadata.get("input_tokens", 0)
            output_tokens = msg.usage_metadata.get("output_tokens", 0)
            tokens_in += input_tokens
            tokens_out += output_tokens

    total_tokens = tokens_in + tokens_out
    total_cost = (tokens_in * 0.0025 / 1000) + (tokens_out * 0.01 / 1000)
    
    completed_at = datetime.utcnow()
    latency_ms = int((completed_at - started_at).total_seconds() * 1000)

    metrics = AgentStepMetrics(
        agent_name="quant_analyst",
        step_index=2,
        latency_ms=latency_ms,
        tokens_input=tokens_in,
        tokens_output=tokens_out,
        cost_usd=total_cost,
        started_at=started_at,
        completed_at=completed_at
    )

    log.info(
        "quant_analyst_node_completed",
        filing_id=report.filing_id,
        beneish=report.beneish_mscore,
        altman=report.altman_zscore,
        red_flags_count=len(report.red_flags)
    )

    return {
        "messages": messages,
        "quant_analysis": report,
        "red_flags": report.red_flags,
        "current_phase": AuditPhase.INVESTIGATION,
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost,
        "agent_steps_data": [metrics]
    }


def investigator_node(state: AuditState) -> dict[str, Any]:
    """Invokes the Investigator Agent and updates state with qualitative search findings."""
    log = logger.bind(audit_run_id=state["audit_run_id"], company_cik=state["company_cik"])
    log.info("investigator_node_started")
    started_at = datetime.utcnow()

    if state.get("company_data") is None:
        log.error("investigator_node_missing_data")
        return {
            "errors": ["Investigator invoked without company_data in state"],
            "current_phase": AuditPhase.FAILED,
        }

    # Prepare rich context for the agent
    company_data_json = state["company_data"].model_dump_json(indent=2)
    context_parts = [f"Company Data:\n{company_data_json}"]
    
    if state.get("reconciliation"):
        r = state["reconciliation"]
        context_parts.append(
            f"Reconciliation result: passed={r.passed}, red_flags_count={len(r.red_flags)}, summary={r.summary}"
        )
        
    if state.get("quant_analysis"):
        q = state["quant_analysis"]
        context_parts.append(
            f"Quant Analysis: beneish={q.beneish_mscore}, altman={q.altman_zscore}, red_flags_count={len(q.red_flags)}"
        )
    
    full_context = "\n\n".join(context_parts)
    
    user_prompt = (
        f"Investigate the qualitative disclosures for filing_id={state['target_filing_id']}. "
        "Search for revenue recognition policies, related parties, and language patterns. "
        "Previous findings from other agents are included below for context.\n\n"
        f"Company data and prior findings:\n{full_context}"
    )

    agent = _get_investigator_agent()
    response = agent.invoke({"messages": [HumanMessage(content=user_prompt)]})
    messages = response.get("messages", [])

    report = extract_investigation_from_messages(messages)

    if report is None:
        log.error("investigator_node_no_submission")
        return {
            "messages": messages,
            "errors": ["Investigator did not submit InvestigationReport"],
            "current_phase": AuditPhase.FAILED,
        }

    # Calculate usage
    tokens_in = 0
    tokens_out = 0
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.usage_metadata:
            input_tokens = msg.usage_metadata.get("input_tokens", 0)
            output_tokens = msg.usage_metadata.get("output_tokens", 0)
            tokens_in += input_tokens
            tokens_out += output_tokens

    total_tokens = tokens_in + tokens_out
    total_cost = (tokens_in * 0.0025 / 1000) + (tokens_out * 0.01 / 1000)
    
    completed_at = datetime.utcnow()
    latency_ms = int((completed_at - started_at).total_seconds() * 1000)

    metrics = AgentStepMetrics(
        agent_name="investigator",
        step_index=3,
        latency_ms=latency_ms,
        tokens_input=tokens_in,
        tokens_output=tokens_out,
        cost_usd=total_cost,
        started_at=started_at,
        completed_at=completed_at
    )

    log.info(
        "investigator_node_completed",
        filing_id=report.filing_id,
        red_flags_count=len(report.red_flags),
        evasive=report.evasive_language_detected
    )

    return {
        "messages": messages,
        "investigation": report,
        "red_flags": report.red_flags,
        "current_phase": AuditPhase.SUPERVISION,
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost,
        "agent_steps_data": [metrics]
    }

def supervisor_node(state: AuditState) -> dict[str, Any]:
    """Invokes the Supervisor Agent to produce final AuditReport and persist results."""
    log = logger.bind(audit_run_id=state["audit_run_id"], company_cik=state["company_cik"])
    log.info("supervisor_node_started")
    started_at = datetime.utcnow()

    # 1. Calculate Risk Score and Level
    risk_score, risk_level = calculate_risk_score(state["red_flags"])
    
    # 2. Determine Conclusion
    rec_passed = state["reconciliation"].passed if state.get("reconciliation") else True
    conclusion = determine_conclusion(risk_score, rec_passed)

    # 3. Build context for Supervisor LLM
    cd = state["company_data"]
    context_parts = [
        f"Company: {cd.name if cd else 'Unknown'} (CIK: {state['company_cik']}, Ticker: {state.get('company_ticker') or 'N/A'})",
        f"Known Fraud: {cd.is_known_fraud if cd else False}"
    ]
    
    if state.get("reconciliation"):
        r = state["reconciliation"]
        context_parts.append(f"Reconciliation: passed={r.passed}, checks={len(r.checks)}, flags={len(r.red_flags)}, summary={r.summary}")
        
    if state.get("quant_analysis"):
        q = state["quant_analysis"]
        context_parts.append(f"Quant Analysis: beneish={q.beneish_mscore}, altman={q.altman_zscore}, accruals={q.accruals_ratio}")
        
    if state.get("investigation"):
        i = state["investigation"]
        mdna = i.mdna_findings[:500] + "..." if i.mdna_findings else "N/A"
        risks = i.risk_factors_summary[:500] + "..." if i.risk_factors_summary else "N/A"
        context_parts.append(f"Investigation: evasive={i.evasive_language_detected}, related_parties={i.related_parties_detected}")
        context_parts.append(f"MD&A Summary: {mdna}")
        context_parts.append(f"Risks Summary: {risks}")
        
    # List consolidated flags
    flag_list = "\n".join([f"- [{f.severity.value.upper()}] {f.title}" for f in state["red_flags"]])
    context_parts.append(f"Consolidated Red Flags:\n{flag_list}")
    context_parts.append(f"Calculated Risk Score: {risk_score} ({risk_level.value})")
    context_parts.append(f"Suggested Conclusion: {conclusion.value}")

    full_context = "\n\n".join(context_parts)
    
    user_prompt = (
        "Write an executive_summary (3-5 paragraphs) and a list of recommendations (3-5 items). "
        "Format your response as:\n\n"
        "EXECUTIVE SUMMARY:\n[Text here]\n\n"
        "RECOMMENDATIONS:\n1. [Item]\n2. [Item]..."
        "\n\nContext:\n" + full_context
    )

    agent = _get_supervisor_agent()
    response = agent.invoke({"messages": [HumanMessage(content=user_prompt)]})
    messages = response.get("messages", [])
    
    # Extract text from the last AIMessage
    final_text = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            final_text = msg.content
            break
            
    # Simple parser
    executive_summary = "N/A"
    recommendations = []
    
    if "EXECUTIVE SUMMARY:" in final_text and "RECOMMENDATIONS:" in final_text:
        parts = final_text.split("RECOMMENDATIONS:")
        summary_part = parts[0].replace("EXECUTIVE SUMMARY:", "").strip()
        rec_part = parts[1].strip()
        
        executive_summary = summary_part
        # Split by lines and clean bullets
        for line in rec_part.split("\n"):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-") or line.startswith("*")):
                # Strip leading number/bullet
                clean_line = line.lstrip("0123456789.-* ").strip()
                if clean_line:
                    recommendations.append(clean_line)
    
    # 4. Construct AuditReport
    report = AuditReport(
        audit_run_id=state["audit_run_id"],
        company_cik=state["company_cik"],
        company_name=cd.name if cd else "Unknown",
        target_filing_id=state["target_filing_id"],
        executed_at=datetime.now(),
        risk_assessment=state.get("risk_assessment"),
        company_data=cd,
        reconciliation=state.get("reconciliation"),
        quant_analysis=state.get("quant_analysis"),
        investigation=state.get("investigation"),
        consolidated_red_flags=state["red_flags"],
        risk_score=risk_score,
        risk_level=risk_level,
        audit_conclusion=conclusion,
        executive_summary=executive_summary,
        recommendations=recommendations
    )

    # 5. Calculate usage
    tokens_in = 0
    tokens_out = 0
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.usage_metadata:
            tokens_in += msg.usage_metadata.get("input_tokens", 0)
            tokens_out += msg.usage_metadata.get("output_tokens", 0)
            
    total_tokens = tokens_in + tokens_out
    total_cost = (tokens_in * 0.0025 / 1000) + (tokens_out * 0.01 / 1000)
    
    completed_at = datetime.utcnow()
    latency_ms = int((completed_at - started_at).total_seconds() * 1000)

    supervisor_metrics = AgentStepMetrics(
        agent_name="supervisor",
        step_index=4,
        latency_ms=latency_ms,
        tokens_input=tokens_in,
        tokens_output=tokens_out,
        cost_usd=total_cost,
        started_at=started_at,
        completed_at=completed_at
    )

    # 6. Database Persistence
    try:
        with get_session() as session:
            repo = AuditRepository(session)
            # Update the existing run record with the target filing_id identified by the collector
            run = repo.get_run(state["audit_run_id"])
            if run:
                run.filing_id = state["target_filing_id"]
            else:
                # Fallback if creation at start failed
                company = session.scalar(select(CompanyORM).where(CompanyORM.cik == state["company_cik"]))
                if company:
                    repo.create_run(
                        company_id=company.id, 
                        filing_id=state["target_filing_id"], 
                        audit_run_id=state["audit_run_id"]
                    )
            
            # Batch add red flags
            repo.add_red_flags_from_list(state["audit_run_id"], state["red_flags"])
            
            # Add steps (from state["agent_steps_data"] plus current supervisor step)
            all_steps = state.get("agent_steps_data", []) + [supervisor_metrics]
            
            for step in all_steps:
                # Find output_data from state if applicable
                out_data = None
                if step.agent_name == "collector":
                    out_data = state["company_data"].model_dump(mode="json") if state.get("company_data") else None
                elif step.agent_name == "reconciler":
                    out_data = state["reconciliation"].model_dump(mode="json") if state.get("reconciliation") else None
                elif step.agent_name == "quant_analyst":
                    out_data = state["quant_analysis"].model_dump(mode="json") if state.get("quant_analysis") else None
                elif step.agent_name == "investigator":
                    out_data = state["investigation"].model_dump(mode="json") if state.get("investigation") else None
                elif step.agent_name == "supervisor":
                    out_data = {"executive_summary": executive_summary, "recommendations": recommendations}

                repo.add_agent_step(
                    run_id=state["audit_run_id"],
                    agent_name=step.agent_name,
                    step_index=step.step_index,
                    output_data=out_data,
                    latency_ms=step.latency_ms,
                    tokens_input=step.tokens_input,
                    tokens_output=step.tokens_output,
                    cost_usd=step.cost_usd,
                    started_at=step.started_at,
                    completed_at=step.completed_at
                )
            
            # Complete the run
            repo.complete_run(
                run_id=state["audit_run_id"],
                risk_score=risk_score,
                risk_level=risk_level.value,
                total_tokens=state["total_tokens"] + total_tokens,
                total_cost_usd=state["total_cost_usd"] + total_cost,
                final_report_json=report.model_dump(mode="json")
            )
    except Exception as e:
        log.error("supervisor_persistence_failed", error=str(e))

    return {
        "messages": messages,
        "final_report": report,
        "current_phase": AuditPhase.COMPLETED,
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost,
        "agent_steps_data": [supervisor_metrics]
    }
