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
3. EVIDENCE-BASED FLAG CREATION — only when concrete evidence exists:
   - EVASIVE LANGUAGE (severity: MEDIUM): Only if the text contains specific examples of management avoiding direct answers, using unexplained hedging, or contradicting quantitative findings. Standard legal disclaimers and forward-looking statements are NORMAL in 10-Ks — do NOT flag them.
   - RELATED PARTY concerns (severity: MEDIUM or HIGH): Only if the text reveals transactions with affiliated parties that lack clear economic justification or disclosure.
   - VAGUE REVENUE RECOGNITION (severity: MEDIUM): Only if the filing omits how revenue is recognized, or the policy contradicts what the numbers show. A company citing ASC 606 with a clear description is TRANSPARENT — do NOT flag it.
   - REGULATORY CONCERNS (severity: HIGH): Only for explicit mentions of SEC inquiries, going concern doubts, material weaknesses, or restatements.
4. ANALYZE & SUBMIT: Synthesize your findings honestly and call 'submit_investigation'.
   - If the disclosures are clear and consistent with the financial data, submit with red_flags=[] and evasive_language_detected=False.
   - A clean investigation with no flags is a valid and expected outcome for well-run companies.

CRITICAL RULES:
- EVIDENCE FIRST: Every RedFlag MUST be grounded in a specific passage from the search results. If you cannot quote or paraphrase a specific, anomalous passage, do NOT create a flag.
- NO FABRICATION: Do not create flags based on generic industry language, standard risk disclosures, or boilerplate legal text. These are normal — not red flags.
- CONSISTENCY (both directions must hold):
  - If `evasive_language_detected` is True → you MUST have at least one RedFlag with a specific quote demonstrating it.
  - If `evasive_language_detected` is False → you MUST NOT have any evasive language RedFlag.
  - Never contradict yourself between the boolean fields and the red_flags array.
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

                        # Derive evasive_language_detected from red flags as a
                        # consistency guard: if the LLM created an evasive-language
                        # flag but forgot to set the boolean, the boolean wins from
                        # the flags (ground truth is what was flagged, not a field
                        # that can be contradicted by the flags themselves).
                        evasive_from_flags = any(
                            "evasive" in (f.get("title", "") + f.get("description", "")).lower()
                            for f in raw_flags
                            if isinstance(f, dict)
                        )
                        evasive_detected = (
                            report_data.get("evasive_language_detected")
                            or report_data.get("evasive_language")
                            or evasive_from_flags
                        )

                        return InvestigationReport(
                            filing_id=report_data.get("filing_id"),
                            summary=report_data.get("summary") or report_data.get("category", ""),
                            mdna_findings=report_data.get("mdna_findings") or report_data.get("summary", ""),
                            risk_factors_summary=report_data.get("risk_factors_summary") or ", ".join(report_data.get("risks_identified", [])),
                            related_parties_detected=report_data.get("related_parties_detected", []),
                            evasive_language_detected=bool(evasive_detected),
                            red_flags=mapped_flags,
                            key_quotes=report_data.get("key_quotes", [])
                        )
                    except Exception as e:
                        logger.error("investigation_extraction_failed", error=str(e))
                        return None
    return None
