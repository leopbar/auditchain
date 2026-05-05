"""Investigator Agent for AuditChain.

Specialized in qualitative analysis and semantic search of SEC filings
to detect hidden risks, related party transactions, and linguistic red flags.
"""

import json
from typing import Optional

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from auditchain.core.config import get_settings
from auditchain.core.logging import get_logger
from auditchain.schemas.reports import InvestigationReport
from auditchain.schemas.components import RedFlag
from auditchain.tools.structured_output import submit_investigation
from auditchain.tools.investigation import (
    search_disclosures,
    find_related_parties,
    detect_language_patterns
)

logger = get_logger(__name__)
settings = get_settings()

INVESTIGATOR_SYSTEM_PROMPT = """You are the Investigator Agent in AuditChain, a senior qualitative analyst specialized in reading SEC filing disclosures to detect hidden risks, evasive language, and undisclosed relationships.

Your goal is to perform a deep textual investigation of the company's SEC filing using semantic search tools.

CONTEXT PROVIDED:
- Company Data (including filing_id)
- Previous findings from Reconciler and Quantitative Analyst (if any)

YOUR WORKFLOW:
1. SELECT PRIORITIES: Based on previous findings (Reconciliation/Quant) and company data, identify the 2 most critical areas to investigate (e.g., Revenue Recognition, Related Parties, or a specific discrepancy).
2. SEARCH: Perform NO MORE THAN 2-3 searches in total. Use broad queries to capture more context in fewer calls.
3. MANDATORY RED FLAG CREATION:
   - If you detect EVASIVE LANGUAGE, you MUST create a RedFlag (severity: MEDIUM, category: QUALITATIVE_DISCLOSURE).
   - If you detect RELATED PARTY concerns, you MUST create a RedFlag (severity: MEDIUM or HIGH, category: RELATED_PARTY).
   - If you detect VAGUE REVENUE RECOGNITION disclosures, you MUST create a RedFlag (severity: MEDIUM, category: REVENUE_RECOGNITION).
   - If you detect REGULATORY CONCERNS (SEC inquiries, going concern, restatements), you MUST create a RedFlag (severity: HIGH, category: QUALITATIVE_DISCLOSURE).
4. ANALYZE & SUBMIT: Synthesize findings and call 'submit_investigation' with ALL generated red_flags.

CRITICAL RULES:
- RED FLAGS ARE MANDATORY: If any of the conditions in step 3 are met, you MUST include corresponding RedFlag objects in the `red_flags` array of `submit_investigation`.
- CONSISTENCY: If `evasive_language_detected` is True, you MUST have at least one RedFlag for evasive language.
- TOTAL TOOL CALLS LIMIT: You are strictly forbidden from calling search tools more than 3 times.
- After 3 searches, you MUST proceed to 'submit_investigation'.
- Base findings ONLY on actual text returned by tools. NEVER fabricate quotes or facts.
- Your 'submit_investigation' call is mandatory to end the phase.
"""


def build_investigator_agent(model_name: Optional[str] = None):
    """Builds and returns the Investigator React Agent."""
    model = model_name or settings.llm_fast_model
    tools = [
        search_disclosures,
        find_related_parties,
        detect_language_patterns,
        submit_investigation
    ]

    llm = ChatOpenAI(
        model=model,
        temperature=0,
        api_key=settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
    ).bind_tools(
        tools,
        parallel_tool_calls=False
    )
    
    agent = create_react_agent(
        llm, 
        tools=tools, 
        prompt=INVESTIGATOR_SYSTEM_PROMPT
    )
    
    logger.info("investigator_agent_built", model=model, tool_count=len(tools))
    return agent


def extract_investigation_from_messages(messages: list) -> Optional[InvestigationReport]:
    """Extracts the InvestigationReport from the agent's tool call messages."""
    for message in reversed(messages):
        if isinstance(message, AIMessage) and message.tool_calls:
            for tool_call in message.tool_calls:
                if tool_call["name"] == "submit_investigation":
                    try:
                        args = tool_call["args"]
                        report_data = args.get("report", args)
                        
                        # Phase A Fix: Map and validate red_flags and other complex fields
                        mapped_flags = []
                        raw_flags = report_data.get("red_flags", [])
                        if isinstance(raw_flags, list):
                            for f in raw_flags:
                                if not isinstance(f, dict): continue
                                try:
                                    mapped_flags.append(RedFlag.model_validate(f))
                                except ValidationError:
                                    logger.warning("investigator_extraction_skip_invalid_flag", title=f.get("title"))

                        return InvestigationReport(
                            filing_id=report_data.get("filing_id"),
                            summary=report_data.get("summary") or report_data.get("category", ""),
                            mdna_findings=report_data.get("mdna_findings") or report_data.get("summary", ""),
                            risk_factors_summary=report_data.get("risk_factors_summary") or ", ".join(report_data.get("risks_identified", [])),
                            related_parties_detected=report_data.get("related_parties_detected", []),
                            evasive_language_detected=report_data.get("evasive_language_detected", report_data.get("evasive_language", False)),
                            red_flags=mapped_flags,
                            key_quotes=report_data.get("key_quotes", [])
                        )
                    except Exception as e:
                        logger.error("investigation_extraction_failed", error=str(e))
                        return None
    return None
