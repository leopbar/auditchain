"""Reusable Pydantic components for AuditChain schemas.

This module defines compound elements like RedFlags, Evidence, and FinancialPeriods
 that are shared across different agent reports.
"""

from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from auditchain.schemas.enums import FlagSeverity, FlagCategory


class Evidence(BaseModel):
    """A piece of evidence supporting a finding. Used to make red flags traceable to source data."""

    model_config = ConfigDict(extra="ignore")

    source: str = Field(description="The source of the evidence, e.g., '10-K filing 2024-09-30, MD&A section'")
    quote: str | None = Field(None, description="Verbatim quote or relevant text snippet from the source")
    metric: str | None = Field(None, description="The name of the metric if the evidence is numeric")
    value: float | None = Field(None, description="The numeric value if applicable")


class RedFlag(BaseModel):
    """A specific finding that warrants attention during audit. 
    
    Multiple red flags can be raised by different agents and aggregated into a final report.
    """

    model_config = ConfigDict(extra="ignore")

    category: FlagCategory = Field(description="The category of the audit finding")
    severity: FlagSeverity = Field(description="The severity level of the flag")
    title: str = Field(description="Short, descriptive title of the finding")
    description: str = Field(description="Detailed explanation of the anomaly or risk detected")
    evidence: list[Evidence] = Field(default_factory=list, description="Supporting evidence for this finding")
    confidence: float = Field(ge=0.0, le=1.0, description="The agent's confidence in this finding (0.0 to 1.0)")
    detected_by: str = Field(description="The name of the agent that detected this flag (e.g., 'reconciler')")


class FinancialPeriod(BaseModel):
    """Financial data for a single reporting period. 
    
    More comprehensive than a simple summary, it includes balance sheet and 
    cash flow details needed for advanced analysis (Beneish, Altman, accruals).
    """

    model_config = ConfigDict(extra="ignore")

    filing_id: int | None = Field(None, description="Internal database ID for the filing")
    fiscal_year: int | None = Field(None, description="The fiscal year of the report")
    period_end: date | None = Field(None, description="The end date of the reporting period")
    
    # Income Statement
    revenue: float | None = Field(None, description="Total Revenue")
    cost_of_revenue: float | None = Field(None, description="Cost of Goods Sold / Revenue")
    gross_profit: float | None = Field(None, description="Gross Profit")
    operating_expenses: float | None = Field(None, description="Total Operating Expenses")
    operating_income: float | None = Field(None, description="Operating Income (Loss)")
    net_income: float | None = Field(None, description="Net Income (Loss)")
    
    # Balance Sheet
    total_assets: float | None = Field(None, description="Total Assets")
    current_assets: float | None = Field(None, description="Total Current Assets")
    accounts_receivable: float | None = Field(None, description="Accounts Receivable, Net")
    inventory: float | None = Field(None, description="Total Inventory")
    total_liabilities: float | None = Field(None, description="Total Liabilities")
    current_liabilities: float | None = Field(None, description="Total Current Liabilities")
    stockholders_equity: float | None = Field(None, description="Total Stockholders' Equity")
    cash: float | None = Field(None, description="Cash and Cash Equivalents")
    
    # Cash Flow
    cash_from_operations: float | None = Field(None, description="Net Cash Provided by (Used in) Operating Activities")
    cash_from_investing: float | None = Field(None, description="Net Cash Provided by (Used in) Investing Activities")
    cash_from_financing: float | None = Field(None, description="Net Cash Provided by (Used in) Financing Activities")


class CheckResult(BaseModel):
    """Result of a single validation check. Used inside reports to enumerate what was tested."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(description="The name of the check, e.g., 'accounting_equation'")
    passed: bool = Field(description="Whether the check passed successfully")
    expected: float | None = Field(None, description="The expected value for the check")
    actual: float | None = Field(None, description="The actual value found")
    tolerance: float | None = Field(None, description="The allowed margin of error")
    notes: str | None = Field(None, description="Additional context or failure reasons")


class AgentStepMetrics(BaseModel):
    """Granular performance metrics for a single agent execution step."""

    model_config = ConfigDict(extra="ignore")

    agent_name: str = Field(description="The name of the agent (e.g., 'reconciler')")
    step_index: int = Field(description="Sequential index of the step (0-based)")
    latency_ms: int | None = Field(None, description="Execution time in milliseconds")
    tokens_input: int | None = Field(None, description="Prompt tokens consumed")
    tokens_output: int | None = Field(None, description="Completion tokens generated")
    cost_usd: float | None = Field(None, description="Estimated cost in USD")
    started_at: datetime | None = Field(None, description="Timestamp when the node started")
    completed_at: datetime | None = Field(None, description="Timestamp when the node finished")
