"""Anomaly Detector Agent module.

The Anomaly Detector is a senior financial trend analyst responsible for 
identifying suspicious multi-year trajectories in financial data. It analyzes 
historical trends provided in the shared conversation state and flags 
anomalies such as revenue crashes paired with debt spikes.
"""

from typing import Any
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from auditchain.core.config import get_settings
from auditchain.core.logging import get_logger

logger = get_logger(__name__)

ANOMALY_SYSTEM_PROMPT = """
You are the Anomaly Detector Agent in AuditChain, a senior financial trend analyst.
Your job is to read the historical financial data provided in the conversation history and identify suspicious multi-year trends.

Look for the following RED FLAGS across the provided years:
1. Revenue crashing while Total Liabilities spike.
2. Sudden or severe depletion of Cash year-over-year.
3. Stockholders' Equity becoming progressively more negative.
4. Any other illogical financial trajectory.

Generate a structured 'Trend Analysis Report' containing:
- Years analyzed.
- Key Trend Observations (Year-over-Year changes).
- RED FLAGS: Detail any suspicious trends. If none, state 'No significant anomalies detected'.
- CONCLUSION: 'PASSED' (healthy trends) or 'FAILED' (severe negative trends or anomalies).

CRITICAL: Only analyze the data provided in the messages. Do not invent numbers.
"""


def build_anomaly_detector_agent() -> Any:
    """Builds and returns the Anomaly Detector Agent.

    The agent uses GPT-4o-mini with temperature 0 for deterministic trend analysis.
    Like the Reconciler, it has no tools and relies on context from the Collector.

    Returns:
        A CompiledGraph representing the analytical agent.
    """
    settings = get_settings()

    llm = ChatOpenAI(
        model=settings.llm_fast_model,
        api_key=settings.openai_api_key.get_secret_value(),
        temperature=0,
    )

    agent = create_react_agent(
        model=llm,
        tools=[],
        prompt=ANOMALY_SYSTEM_PROMPT,
    )

    logger.info(
        "anomaly_detector_agent_built",
        model=settings.llm_fast_model,
        tool_count=0,
    )

    return agent
