"""Pydantic models for LangChain tool outputs.

These models ensure consistent, structured data is returned to the agents,
making it easier for them to reason about financial data and handle errors.
"""

from datetime import date
from pydantic import BaseModel, ConfigDict


class CompanyInfo(BaseModel):
    """Standard response model for tools that look up company data.

    Provides core identification and ground truth fraud status.
    """

    model_config = ConfigDict(extra="forbid")

    cik: str
    ticker: str | None
    name: str
    is_known_fraud: bool
    fraud_notes: str | None


class FilingSummary(BaseModel):
    """Summary metadata for an SEC filing.

    Used by listing tools to provide agents with a high-level overview
    of available financial statements before they commit to deeper analysis.
    """

    model_config = ConfigDict(extra="forbid")

    id: int
    accession_number: str
    filing_type: str
    fiscal_year: int
    fiscal_period: str
    period_of_report: date
    filing_date: date


class FinancialSummary(BaseModel):
    """Key financial indicators ('vital signs') for a specific SEC filing.

    This model aggregates the most important financial metrics found in a filing
    to provide a quick quantitative overview. Note that any numeric field can be
    None if the specific XBRL concept was not reported by the company in this
    particular filing.
    """

    model_config = ConfigDict(extra="forbid")

    filing_id: int
    period_of_report: date
    fiscal_year: int
    revenue: float | None
    net_income: float | None
    total_assets: float | None
    total_liabilities: float | None
    stockholders_equity: float | None
    cash: float | None
    operating_income: float | None


class ToolError(BaseModel):
    """Standard model used when a tool encounters an expected failure.

    Used for graceful error handling within the agent's flow (e.g., company not found),
    allowing the agent to decide how to proceed rather than crashing.
    """

    model_config = ConfigDict(extra="forbid")

    error: str
    code: str
