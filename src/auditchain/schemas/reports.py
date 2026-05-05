"""Structured report schemas for AuditChain agents.

This module defines the final output format for each specialist agent in the
pipeline, as well as the final consolidated report produced by the Supervisor.
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from auditchain.schemas.enums import RiskLevel, AuditConclusion
from auditchain.schemas.components import RedFlag, FinancialPeriod, CheckResult, Evidence


class RiskAssessment(BaseModel):
    """Output of the Planner Agent. Sets the context, scope, and risk priorities for the rest of the audit."""

    model_config = ConfigDict(extra="ignore")

    industry: str = Field(description="The primary industry of the company")
    industry_specific_risks: list[str] = Field(description="List of risks typically associated with this industry")
    materiality_threshold_usd: float = Field(description="Materiality threshold in USD for audit findings")
    focus_areas: list[str] = Field(description="Specific areas or accounts where the audit should focus")
    prior_fraud_history: bool = Field(False, description="Whether the company has a known history of fraud or regulatory issues")
    prior_fraud_notes: str | None = Field(None, description="Detailed notes on prior fraud cases if applicable")
    recommended_depth: RiskLevel = Field(RiskLevel.LOW, description="The recommended depth level for the audit based on initial risk")


class CompanyData(BaseModel):
    """Output of the Collector Agent. Structured financial data ready for analysis."""

    model_config = ConfigDict(extra="ignore")

    cik: str = Field(description="SEC Central Index Key (10 digits)")
    ticker: str | None = Field(None, description="Stock ticker symbol")
    name: str = Field(description="Official company name")
    is_known_fraud: bool = Field(False, description="Whether this company is in our known fraud catalog")
    target_filing_id: int | None = Field(None, description="Internal ID of the primary filing under analysis")
    current_period: FinancialPeriod | None = Field(None, description="Financial data for the primary period under analysis")
    historical_periods: list[FinancialPeriod] = Field(default_factory=list, description="Historical financial data for trend comparison")


class ReconciliationReport(BaseModel):
    """Output of the Reconciler Agent. Documents accounting consistency checks and any discrepancies found."""

    model_config = ConfigDict(extra="ignore")

    filing_id: int | None = Field(None, description="Internal ID of the filing reconciled")
    checks: list[CheckResult] = Field(default_factory=list, description="List of all validation checks executed")
    red_flags: list[RedFlag] = Field(default_factory=list, description="Specific flags raised during reconciliation")
    passed: bool = Field(True, description="Whether the filing passed all critical consistency checks")
    summary: str = Field("", description="A 1-2 sentence overview of the reconciliation results")


class QuantAnalysisReport(BaseModel):
    """Output of the Quantitative Analyst Agent.
    
    Includes classic fraud detection scores (Beneish M-Score, Altman Z-Score) 
    and accruals analysis.
    """

    model_config = ConfigDict(extra="ignore")

    filing_id: int | None = Field(None, description="Internal ID of the filing analyzed")
    beneish_mscore: float | None = Field(None, description="Beneish M-Score value")
    beneish_interpretation: str | None = Field(None, description="Interpretation of the M-Score (e.g., 'Possible manipulator')")
    altman_zscore: float | None = Field(None, description="Altman Z-Score value")
    altman_interpretation: str | None = Field(None, description="Interpretation of the Z-Score (e.g., 'Distress zone')")
    accruals_ratio: float | None = Field(None, description="Sloan's Accruals Ratio or similar metric")
    revenue_growth_yoy: float | None = Field(None, description="Year-over-Year revenue growth percentage")
    peer_comparison_notes: str | None = Field(None, description="Qualitative notes on how this company compares to industry peers")
    red_flags: list[RedFlag] = Field(default_factory=list, description="Specific flags raised during quantitative analysis")
    summary: str = Field("", description="Overview of quantitative findings")


class InvestigationReport(BaseModel):
    """Output of the Investigator Agent. 
    
    Qualitative analysis based on RAG over filing disclosures (MD&A, Risk Factors, Notes).
    """

    model_config = ConfigDict(extra="ignore")

    filing_id: int | None = Field(None, description="Internal ID of the filing investigated")
    mdna_findings: str | None = Field(None, description="Key insights found in Management's Discussion and Analysis")
    risk_factors_summary: str | None = Field(None, description="Summary of the most critical risk factors disclosed")
    related_parties_detected: list[str] = Field(default_factory=list, description="List of related parties mentioned in disclosures")
    evasive_language_detected: bool = Field(False, description="Whether the LLM detected signs of evasive or boilerplate language")
    red_flags: list[RedFlag] = Field(default_factory=list, description="Specific flags raised during qualitative investigation")
    key_quotes: list[Evidence] = Field(default_factory=list, description="Important literal quotes from the filing")
    summary: str = Field("", description="Overview of investigative findings")


class AuditReport(BaseModel):
    """The final audit report consolidating findings from all specialist agents. 
    
    Produced by the Supervisor Agent. This is what would be delivered to a partner 
    at a Big Four firm.
    """

    model_config = ConfigDict(extra="ignore")

    audit_run_id: str = Field(description="Unique UUID for this specific audit execution")
    company_cik: str = Field(description="SEC CIK of the audited company")
    company_name: str = Field(description="Name of the audited company")
    target_filing_id: int = Field(description="Primary filing analyzed")
    executed_at: datetime = Field(description="Timestamp of the audit completion")
    
    risk_assessment: RiskAssessment | None = Field(None, description="Context and scope from the Planner")
    company_data: CompanyData | None = Field(None, description="Extracted financial data from the Collector")
    reconciliation: ReconciliationReport | None = Field(None, description="Consistency findings from the Reconciler")
    quant_analysis: QuantAnalysisReport | None = Field(None, description="Quantitative metrics from the Quant Analyst")
    investigation: InvestigationReport | None = Field(None, description="Qualitative findings from the Investigator")
    
    consolidated_red_flags: list[RedFlag] = Field(default_factory=list, description="All flags from all agents, consolidated and prioritized")
    risk_score: float = Field(ge=0.0, le=100.0, description="Final calculated risk score (0 to 100)")
    risk_level: RiskLevel = Field(description="Final risk categorization")
    audit_conclusion: AuditConclusion = Field(description="The final audit opinion (Clean, Qualified, etc.)")
    executive_summary: str = Field(description="Executive summary in prose for final review")
    recommendations: list[str] = Field(default_factory=list, description="List of recommended actions for human auditors")
