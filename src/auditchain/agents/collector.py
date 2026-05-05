"""Collector Agent module.

The Collector Agent is the first analytical agent in the pipeline. It is 
responsible for identifying a company and gathering its primary filing and 
historical financial data. It outputs structured CompanyData.
"""

from typing import Any

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from pydantic import ValidationError

from auditchain.core.config import get_settings
from auditchain.core.logging import get_logger
from auditchain.schemas.reports import CompanyData
from auditchain.tools.financial_data import (
    get_company,
    get_financial_summary,
    list_filings,
)
from auditchain.tools.structured_output import submit_company_data

logger = get_logger(__name__)

COLLECTOR_SYSTEM_PROMPT = """
You are the Collector Agent in AuditChain, a multi-agent SEC fraud detection system.

Your role is to gather comprehensive structured financial data for a target company, including the most recent annual filing (target) and at least 3 prior fiscal years for year-over-year trend analysis. Other agents (Reconciler, Quant Analyst, Investigator) will analyze your output.

You have these tools available:
- get_company: identify a company by ticker or CIK
- list_filings: list available SEC filings, ordered by date desc
- get_financial_summary: extract key financial metrics from a specific filing
- submit_company_data: finalize and submit your structured CompanyData output (call ONCE at the end)

Required workflow:
1. Call get_company to identify the company and obtain CIK + name + fraud flags
2. Call list_filings with filing_type="10-K" and limit=5 to get the 5 most recent annual filings
3. Choose the MOST RECENT filing as the target. Call get_financial_summary on it.
4. Call get_financial_summary on the next 3-4 most recent 10-Ks for historical comparison
5. Call submit_company_data with a CompanyData object containing:
   - cik, ticker, name, is_known_fraud (from get_company)
   - target_filing_id (the id of the most recent 10-K)
   - current_period: FinancialPeriod from the target filing
   - historical_periods: list of FinancialPeriod from prior years (at least 3 entries)

Critical rules:
- NEVER invent any number. Only use values returned by tools.
- If a tool returns ToolError, log the issue but continue with available data.
- For FinancialPeriod, fields not returned by get_financial_summary should be set to null.
- The fields cost_of_revenue, gross_profit, operating_expenses, current_assets, accounts_receivable, inventory, current_liabilities, cash_from_operations, cash_from_investing, cash_from_financing are NOT available from get_financial_summary — set them to null.
- Submit ONLY ONCE via submit_company_data when you have collected all required data.
- After calling submit_company_data, your job is done. Do not call any more tools.
"""


def build_collector_agent() -> Any:
    """Builds the Collector Agent with data retrieval and submission tools.
    
    Uses a smarter LLM model to handle complex structured output generation.
    """
    settings = get_settings()

    llm = ChatOpenAI(
        model=settings.llm_smart_model,
        api_key=settings.openai_api_key.get_secret_value(),
        temperature=0,
    )

    tools = [get_company, list_filings, get_financial_summary, submit_company_data]

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=COLLECTOR_SYSTEM_PROMPT,
    )

    logger.info(
        "collector_agent_built", 
        model=settings.llm_smart_model, 
        tool_count=len(tools)
    )

    return agent


def extract_company_data_from_messages(messages: list) -> CompanyData | None:
    """Examines an agent's message history and extracts the CompanyData submitted 
    via the submit_company_data tool. Returns None if the tool was never called.
    """
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc["name"] == "submit_company_data":
                    try:
                        # args is expected to have 'company_data' key
                        args = tc["args"]
                        if "company_data" in args:
                            return CompanyData.model_validate(args["company_data"])
                        else:
                            # Fallback if the LLM sent the model directly as root args
                            return CompanyData.model_validate(args)
                    except ValidationError as e:
                        logger.error("extract_company_data_validation_error", error=str(e), args=args)
                        return None
    
    logger.warning("extract_company_data_no_submission_found")
    return None
