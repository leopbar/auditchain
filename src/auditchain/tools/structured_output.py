"""Structured output submission tools for AuditChain agents.

This module defines "submit tools" — special tools that agents use to provide 
their final structured output. When an agent calls a submit tool, the 
arguments of the call constitute the structured result of that agent's work.
"""

from typing import Any, Dict, List, Optional
from langchain_core.tools import tool
from auditchain.core.logging import get_logger
from auditchain.schemas.reports import (
    CompanyData,
    InvestigationReport,
    QuantAnalysisReport,
    ReconciliationReport,
    RiskAssessment,
)

logger = get_logger(__name__)


@tool
def submit_risk_assessment(
    industry: str,
    materiality_threshold_usd: float,
    high_risk_areas: list[str],
    audit_focus_areas: list[str],
    required_audit_depth: str,
    notes: Optional[str] = None
) -> str:
    """Call this tool ONCE when you have completed your risk assessment and are ready to finalize your output. 
    
    Calling this tool means your work as Planner Agent is done.
    """
    logger.info("submit_risk_assessment_called", industry=industry)
    return "Risk assessment submitted."


@tool
def submit_company_data(
    cik: str,
    name: str,
    target_filing_id: Optional[int] = None,
    current_period: Optional[dict] = None,
    historical_periods: List[dict] = [],
    ticker: Optional[str] = None,
    is_known_fraud: bool = False
) -> str:
    """Call this tool ONCE when you have collected all required company information and are ready to finalize your output. 
    
    The CompanyData must include current_period (the filing under analysis) and at least 3 
    historical_periods for year-over-year analysis. Calling this tool means your work 
    as Collector Agent is done.
    """
    logger.info("submit_company_data_called", cik=cik)
    return "Company data submitted."


@tool
def submit_reconciliation(
    filing_id: Optional[int] = None,
    checks: List[dict] = [],
    passed: bool = True,
    discrepancies: List[str] = [],
    red_flags: List[dict] = []
) -> str:
    """Call this tool ONCE when you have completed all reconciliation checks and are ready to finalize your output. 
    
    The 'checks' list must contain objects with the following fields:
    - name (str): name of the check (e.g., 'accounting_equation')
    - passed (bool): whether it passed
    - expected (float/None): the value that should have been there
    - actual (float/None): the value found in the filing
    - tolerance (float/None): allowed margin of error
    - notes (str/None): context on why it failed or passed

    The 'red_flags' list must contain objects with this structure:
    {
      "detected_by": "reconciler",
      "category": "accounting_equation",
      "severity": "high",
      "title": "Unbalanced Balance Sheet",
      "description": "Total assets do not match liabilities plus equity by $X.",
      "confidence": 1.0
    }

    Calling this tool means your work as Reconciler Agent is done.
    """
    # Runtime validation: warn if passed=False but no red_flags provided
    failed_checks = [c for c in checks if isinstance(c, dict) and c.get("passed") is False]
    if not passed and len(red_flags) == 0:
        logger.warning(
            "submit_reconciliation_missing_red_flags",
            filing_id=filing_id,
            failed_checks_count=len(failed_checks),
            msg="ALERT: passed=False but red_flags is empty. Risk score will be incorrect."
        )
    elif len(failed_checks) > 0 and len(red_flags) < len(failed_checks):
        logger.warning(
            "submit_reconciliation_insufficient_red_flags",
            filing_id=filing_id,
            failed_checks_count=len(failed_checks),
            red_flags_count=len(red_flags),
            msg="red_flags count is less than failed checks count."
        )
    logger.info("submit_reconciliation_called", filing_id=filing_id, passed=passed, red_flags_count=len(red_flags))
    return "Reconciliation submitted."


@tool
def submit_quant_analysis(
    filing_id: Optional[int] = None,
    beneish_mscore: Optional[float] = None,
    beneish_interpretation: Optional[str] = None,
    altman_zscore: Optional[float] = None,
    altman_interpretation: Optional[str] = None,
    accruals_ratio: Optional[float] = None,
    peer_comparison_summary: str = "",
    red_flags: List[dict] = []
) -> str:
    """Call this tool ONCE when you have completed your quantitative analysis.
    
    Parameters:
    - beneish_interpretation: human-readable interpretation of the M-Score
    - altman_interpretation: human-readable interpretation of the Z-Score
    - red_flags: List of objects like:
      {
        "detected_by": "quant_analyst",
        "category": "altman_zscore",
        "severity": "high",
        "title": "High Bankruptcy Risk",
        "description": "Altman Z-Score of X is below the 1.81 distress threshold.",
        "confidence": 0.95
      }
    
    Calling this tool means your work as Quantitative Analyst is done.
    """
    # Runtime validation: warn if scores indicate risk but no red_flags provided
    has_risk = False
    if beneish_mscore is not None and beneish_mscore > -1.78:
        has_risk = True
    if altman_zscore is not None and altman_zscore < 2.99:
        has_risk = True
    if accruals_ratio is not None and abs(accruals_ratio) > 0.10:
        has_risk = True
    if has_risk and len(red_flags) == 0:
        logger.warning(
            "submit_quant_analysis_missing_red_flags",
            filing_id=filing_id,
            beneish=beneish_mscore,
            altman=altman_zscore,
            accruals=accruals_ratio,
            msg="ALERT: Scores indicate risk but red_flags is empty. Risk score will be incorrect."
        )
    logger.info("submit_quant_analysis_called", filing_id=filing_id, red_flags_count=len(red_flags))
    return "Quant analysis submitted."


@tool
def submit_investigation(
    filing_id: Optional[int] = None,
    category: str = "",
    summary: str = "",
    risks_identified: List[str] = [],
    recommendations: List[str] = [],
    evasive_language: bool = False,
    red_flags: List[dict] = []
) -> str:
    """Call this tool ONCE when you have completed your qualitative investigation. 
    
    The 'red_flags' list must contain objects with this structure:
    {
      "detected_by": "investigator",
      "category": "qualitative_disclosure",
      "severity": "medium",
      "title": "Evasive Language Detected",
      "description": "The MD&A section uses boilerplate language to avoid discussing revenue declines.",
      "confidence": 0.85
    }

    Calling this tool means your work as Investigator Agent is done.
    """
    logger.info("submit_investigation_called", filing_id=filing_id)
    return "Investigation submitted."
