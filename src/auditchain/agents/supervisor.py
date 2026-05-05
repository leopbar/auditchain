"""Supervisor Agent for AuditChain.

The final authority in the pipeline, responsible for consolidating findings
from all agents, calculating the final risk score, and writing the 
Executive Summary and Recommendations.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Tuple

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import AIMessage

from auditchain.core.config import get_settings
from auditchain.core.logging import get_logger
from auditchain.schemas.reports import AuditReport
from auditchain.schemas.components import RedFlag
from auditchain.schemas.enums import RiskLevel, AuditConclusion

logger = get_logger(__name__)
settings = get_settings()

def calculate_risk_score(red_flags: List[RedFlag]) -> Tuple[float, RiskLevel]:
    """Calculates a numerical risk score (0-100) based on red flags.
    
    Weights:
    - CRITICAL: 25 points
    - HIGH: 15 points
    - MEDIUM: 8 points
    - LOW: 3 points
    - INFO: 1 point
    """
    weights = {
        "critical": 25,
        "high": 15,
        "medium": 8,
        "low": 3,
        "info": 1
    }
    
    total_score = 0.0
    for flag in red_flags:
        severity_val = flag.severity.value if hasattr(flag.severity, "value") else str(flag.severity)
        total_score += weights.get(severity_val.lower(), 0)
        
    # Cap at 100
    final_score = min(total_score, 100.0)
    
    # Determine Level
    if final_score <= 20:
        level = RiskLevel.LOW
    elif final_score <= 50:
        level = RiskLevel.MEDIUM
    elif final_score <= 75:
        level = RiskLevel.HIGH
    else:
        level = RiskLevel.CRITICAL
        
    return final_score, level

def determine_conclusion(risk_score: float, reconciliation_passed: bool) -> AuditConclusion:
    """Determines the final audit conclusion based on risk and data integrity."""
    if risk_score > 75 or not reconciliation_passed:
        return AuditConclusion.ADVERSE
    
    if risk_score > 20:
        return AuditConclusion.QUALIFIED
        
    return AuditConclusion.CLEAN

SUPERVISOR_SYSTEM_PROMPT = """You are the Supervisor Agent in AuditChain, a senior audit partner responsible for reviewing all findings and producing the final audit report for a corporate entity.

You will be provided with:
- Company data
- Reconciliation report (mathematical integrity)
- Quantitative analysis (statistical fraud models)
- Qualitative investigation (textual red flags and semantic search)
- A consolidated list of all Red Flags detected
- Pre-calculated risk score, risk level, and suggested audit conclusion

YOUR TASK:
Write a high-quality, professional Executive Summary and a set of Recommendations based on ALL the findings provided.

1. EXECUTIVE SUMMARY:
Write 3-5 paragraphs directed to the company's Board of Directors.
- Identify the company and period analyzed.
- Summarize the quantitative findings (e.g., accounting equation status, Beneish M-Score, Altman Z-Score).
- Summarize the qualitative findings (e.g., evasive language patterns, related party concerns).
- State the final risk score and the audit conclusion.
- Maintain a strictly professional, factual, and authoritative tone.

2. RECOMMENDATIONS:
Provide 3-5 concrete, actionable recommendations for management or human auditors.
- Focus on addressing the specific red flags found (e.g., "Investigate the $X discrepancy in the accounting equation", "Perform a site visit to verify existence of related party assets").

CRITICAL RULES:
- NEVER fabricate data.
- Refer to specific findings from the previous reports.
- Format your response exactly as follows:

EXECUTIVE SUMMARY:
[Your summary text here]

RECOMMENDATIONS:
1. [Recommendation 1]
2. [Recommendation 2]
...
"""

def build_supervisor_agent(model_name: str = "gpt-4o"):
    """Builds and returns the Supervisor Agent (GPT-4o)."""
    llm = ChatOpenAI(
        model=model_name,
        temperature=0,
        api_key=settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
    )
    
    # The supervisor is a reviewer, it doesn't need external tools
    agent = create_react_agent(
        llm, 
        tools=[], 
        prompt=SUPERVISOR_SYSTEM_PROMPT
    )
    
    logger.info("supervisor_agent_built", model=model_name)
    return agent
