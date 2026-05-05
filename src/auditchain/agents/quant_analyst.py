"""Quantitative Analyst Agent for the AuditChain multi-agent system.

This agent specializes in fraud detection models (Beneish M-Score) and 
financial health indicators (Altman Z-Score) using structured financial data.
"""

import json
from typing import Any

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from auditchain.core.config import get_settings
from auditchain.core.logging import get_logger
from auditchain.schemas.reports import QuantAnalysisReport
from auditchain.schemas.components import RedFlag
from auditchain.tools.structured_output import submit_quant_analysis
from auditchain.tools.quantitative import (
    compute_beneish_mscore_simplified,
    compute_altman_zscore_simplified,
    compute_accruals_ratio
)

logger = get_logger(__name__)
settings = get_settings()

QUANT_SYSTEM_PROMPT = """You are the Quantitative Analyst Agent in AuditChain, a senior financial data scientist specialized in fraud detection models and bankruptcy prediction.

═══════════════════════════════════════════════════════════════
CRITICAL OUTPUT REQUIREMENTS — READ BEFORE ANYTHING ELSE
═══════════════════════════════════════════════════════════════

Your submission to submit_quant_analysis MUST include the `red_flags` array populated with formal RedFlag objects whenever scores indicate risk.

The red_flags array is NOT redundant with the score fields. They serve different purposes:
- Score fields (beneish_mscore, altman_zscore, etc.) = raw numbers
- red_flags = FORMAL CONCERNS that trigger downstream risk scoring

WITHOUT red_flags, the entire audit's risk score will be ZERO regardless of how alarming the scores are. The Supervisor agent calculates risk ONLY from red_flags.

ABSOLUTE RULE: If Altman Z-Score < 2.99 OR Beneish M-Score > -1.78 OR Accruals > 10%, your red_flags array MUST NOT be empty. Submitting alarming scores with empty red_flags is INVALID.

═══════════════════════════════════════════════════════════════

WORKFLOW:
1. Extract `current_period` and the first `historical_period` from the provided company data.
2. Call `compute_beneish_mscore_simplified` using the current and prior periods.
3. Call `compute_altman_zscore_simplified` using the current period.
4. Call `compute_accruals_ratio` using the current period.
5. Create red_flags based on results:
   - BENEISH M-SCORE > -1.78 → RedFlag (severity: "high", category: "beneish_mscore")
   - ALTMAN Z-SCORE < 1.81 → RedFlag (severity: "high", category: "altman_zscore")
   - ALTMAN Z-SCORE between 1.81-2.99 → RedFlag (severity: "medium", category: "altman_zscore")
   - ACCRUALS RATIO > 10% → RedFlag (severity: "medium", category: "cash_flow_inconsistency")
6. Fill `beneish_interpretation` and `altman_interpretation` with descriptive text.
7. Call `submit_quant_analysis` with ALL scores AND ALL generated red_flags.

Every RedFlag MUST have: detected_by="quant_analyst", confidence=0.9 or higher.

═══════════════════════════════════════════════════════════════
EXAMPLE — submit_quant_analysis when Altman Z-Score = 0.61 (distress):
═══════════════════════════════════════════════════════════════

submit_quant_analysis(
  filing_id=12345,
  beneish_mscore=-2.5,
  beneish_interpretation="No earnings manipulation indicated (M-Score below -1.78 threshold)",
  altman_zscore=0.61,
  altman_interpretation="Distress zone - high bankruptcy risk (Z-Score below 1.81)",
  accruals_ratio=0.05,
  red_flags=[
    {"detected_by": "quant_analyst", "category": "altman_zscore", "severity": "high", "title": "High Bankruptcy Risk - Distress Zone", "description": "Altman Z-Score of 0.61 is far below the 1.81 distress threshold, indicating severe financial distress and high bankruptcy risk.", "confidence": 0.95}
  ]
)

Notice: Altman < 1.81 → 1 red_flag created. This is mandatory.

═══════════════════════════════════════════════════════════════

CRITICAL RULES:
- RED FLAGS ARE MANDATORY when scores indicate risk. Empty red_flags with risky scores = INVALID submission.
- NEVER invent or hallucinate financial numbers. Use only what is provided or returned by tools.
- If a tool returns "Insufficient data", report it in interpretation fields but do not flag it.
- Call `submit_quant_analysis` exactly once at the end.
"""


def build_quant_analyst_agent():
    """Factory function to instantiate the Quant Analyst agent."""
    llm = ChatOpenAI(
        model=settings.llm_smart_model,
        temperature=0,
        api_key=settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
    )
    
    tools = [
        compute_beneish_mscore_simplified,
        compute_altman_zscore_simplified,
        compute_accruals_ratio,
        submit_quant_analysis
    ]
    
    agent = create_react_agent(
        model=llm, 
        tools=tools,
        prompt=QUANT_SYSTEM_PROMPT
    )
    
    logger.info("quant_analyst_agent_built", model=settings.llm_smart_model)
    return agent


def extract_quant_analysis_from_messages(messages: list[Any]) -> QuantAnalysisReport | None:
    """Extracts the structured QuantAnalysisReport from the agent's tool calls with robust validation."""
    for message in reversed(messages):
        if isinstance(message, AIMessage) and message.tool_calls:
            for tool_call in message.tool_calls:
                if tool_call["name"] == "submit_quant_analysis":
                    try:
                        args = tool_call["args"]
                        report_data = args.get("report", args)
                        
                        # Defensively extract and validate red_flags
                        mapped_flags = []
                        raw_flags = report_data.get("red_flags", [])
                        if isinstance(raw_flags, list):
                            for f in raw_flags:
                                if not isinstance(f, dict): continue
                                try:
                                    mapped_flags.append(RedFlag.model_validate(f))
                                except ValidationError:
                                    logger.warning("quant_extraction_skip_invalid_flag", title=f.get("title"))

                        return QuantAnalysisReport(
                            filing_id=report_data.get("filing_id"),
                            beneish_mscore=report_data.get("beneish_mscore"),
                            beneish_interpretation=report_data.get("beneish_interpretation"),
                            altman_zscore=report_data.get("altman_zscore"),
                            altman_interpretation=report_data.get("altman_interpretation"),
                            accruals_ratio=report_data.get("accruals_ratio"),
                            revenue_growth_yoy=report_data.get("revenue_growth_yoy"),
                            peer_comparison_notes=report_data.get("peer_comparison_notes") or report_data.get("peer_comparison_summary", ""),
                            summary=report_data.get("summary", ""),
                            red_flags=mapped_flags
                        )
                    except Exception as e:
                        logger.error("extract_quant_analysis_failed", error=str(e))
                        return None
    return None
