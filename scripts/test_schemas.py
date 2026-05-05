"""Smoke test for AuditChain Pydantic schemas.

Validates that all enums, components, and reports can be instantiated,
serialized, and strictly validated.

Usage:
    python -m scripts.test_schemas
"""

import sys
import uuid
import traceback
from datetime import date, datetime
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from auditchain.core.logging import configure_logging
from auditchain.schemas.enums import (
    RiskLevel, FlagSeverity, AuditPhase, AuditConclusion, FlagCategory
)
from auditchain.schemas.components import Evidence, RedFlag, FinancialPeriod, CheckResult
from auditchain.schemas.reports import (
    RiskAssessment, CompanyData, ReconciliationReport, QuantAnalysisReport, 
    InvestigationReport, AuditReport
)

console = Console()


def test_evidence():
    """Test Evidence model instantiation and round-trip."""
    obj = Evidence(
        source="10-K filing 2024",
        quote="net income increased substantially",
        metric="net_income",
        value=112010000000.0
    )
    dump = obj.model_dump()
    Evidence.model_validate(dump)
    return "Evidence", True, None


def test_red_flag():
    """Test RedFlag model instantiation and round-trip."""
    ev = Evidence(source="Audit trace", quote="High volume", value=100.0)
    obj = RedFlag(
        category=FlagCategory.REVENUE_RECOGNITION,
        severity=FlagSeverity.HIGH,
        title="Channel stuffing suspected",
        description="Q4 revenue jump unexplained",
        evidence=[ev],
        confidence=0.75,
        detected_by="quant_analyst"
    )
    dump = obj.model_dump()
    RedFlag.model_validate(dump)
    return "RedFlag", True, None


def test_financial_period():
    """Test FinancialPeriod model instantiation and round-trip."""
    obj = FinancialPeriod(
        filing_id=25,
        fiscal_year=2024,
        period_end=date(2024, 9, 28),
        revenue=391035000000.0,
        net_income=93736000000.0,
        total_assets=364980000000.0,
        total_liabilities=308030000000.0,
        stockholders_equity=56950000000.0,
        cash=29943000000.0
    )
    dump = obj.model_dump()
    FinancialPeriod.model_validate(dump)
    return "FinancialPeriod", True, None


def test_check_result():
    """Test CheckResult model instantiation and round-trip."""
    obj = CheckResult(
        name="accounting_equation",
        passed=True,
        expected=364980000000.0,
        actual=364980000000.0,
        tolerance=1000.0,
        notes="Within tolerance"
    )
    dump = obj.model_dump()
    CheckResult.model_validate(dump)
    return "CheckResult", True, None


def test_risk_assessment():
    """Test RiskAssessment model instantiation and round-trip."""
    obj = RiskAssessment(
        industry="Technology",
        industry_specific_risks=["revenue recognition complexity", "intangible assets valuation"],
        materiality_threshold_usd=2000000000.0,
        focus_areas=["revenue", "stock-based compensation"],
        prior_fraud_history=False,
        prior_fraud_notes=None,
        recommended_depth=RiskLevel.MEDIUM
    )
    dump = obj.model_dump()
    RiskAssessment.model_validate(dump)
    return "RiskAssessment", True, None


def test_company_data():
    """Test CompanyData model instantiation and round-trip."""
    fp = FinancialPeriod(
        filing_id=25, fiscal_year=2024, period_end=date(2024, 9, 28),
        revenue=391035000000.0, total_assets=364980000000.0
    )
    obj = CompanyData(
        cik="0000320193",
        ticker="AAPL",
        name="Apple Inc",
        is_known_fraud=False,
        target_filing_id=25,
        current_period=fp,
        historical_periods=[]
    )
    dump = obj.model_dump()
    CompanyData.model_validate(dump)
    return "CompanyData", True, None


def test_reconciliation_report():
    """Test ReconciliationReport model instantiation and round-trip."""
    cr = CheckResult(name="math", passed=True)
    obj = ReconciliationReport(
        filing_id=25,
        checks=[cr],
        red_flags=[],
        passed=True,
        summary="All checks passed within tolerance"
    )
    dump = obj.model_dump()
    ReconciliationReport.model_validate(dump)
    return "ReconciliationReport", True, None


def test_quant_analysis_report():
    """Test QuantAnalysisReport model instantiation and round-trip."""
    obj = QuantAnalysisReport(
        filing_id=25,
        beneish_mscore=-2.5,
        beneish_interpretation="Below threshold; no manipulation indicated",
        altman_zscore=4.2,
        altman_interpretation="Safe zone",
        accruals_ratio=0.05,
        revenue_growth_yoy=0.08,
        peer_comparison_notes="In line with industry peers",
        red_flags=[],
        summary="Quantitative metrics indicate financial health"
    )
    dump = obj.model_dump()
    QuantAnalysisReport.model_validate(dump)
    return "QuantAnalysisReport", True, None


def test_investigation_report():
    """Test InvestigationReport model instantiation and round-trip."""
    obj = InvestigationReport(
        filing_id=25,
        mdna_findings="Standard discussion of segments",
        risk_factors_summary="Typical tech sector risks",
        related_parties_detected=[],
        evasive_language_detected=False,
        red_flags=[],
        key_quotes=[],
        summary="No qualitative concerns identified"
    )
    dump = obj.model_dump()
    InvestigationReport.model_validate(dump)
    return "InvestigationReport", True, None


def test_audit_report():
    """Test complete AuditReport model instantiation and round-trip."""
    ra = RiskAssessment(industry="Tech", industry_specific_risks=[], materiality_threshold_usd=1.0, focus_areas=[], prior_fraud_history=False, recommended_depth=RiskLevel.LOW)
    fp = FinancialPeriod(filing_id=1, fiscal_year=2024, period_end=date(2024,1,1))
    cd = CompanyData(cik="123", name="Test", is_known_fraud=False, target_filing_id=1, current_period=fp)
    rr = ReconciliationReport(filing_id=1, checks=[], red_flags=[], passed=True, summary="OK")
    qr = QuantAnalysisReport(filing_id=1, red_flags=[], summary="OK")
    ir = InvestigationReport(filing_id=1, evasive_language_detected=False, red_flags=[], summary="OK")

    obj = AuditReport(
        audit_run_id=str(uuid.uuid4()),
        company_cik="0000320193",
        company_name="Apple Inc",
        target_filing_id=25,
        executed_at=datetime.now(),
        risk_assessment=ra,
        company_data=cd,
        reconciliation=rr,
        quant_analysis=qr,
        investigation=ir,
        consolidated_red_flags=[],
        risk_score=15.5,
        risk_level=RiskLevel.LOW,
        audit_conclusion=AuditConclusion.CLEAN,
        executive_summary="Audit completed without significant findings",
        recommendations=["Continue normal monitoring"]
    )
    dump = obj.model_dump()
    AuditReport.model_validate(dump)
    return "AuditReport", True, None


def test_red_flag_validation():
    """Negative test: Validate confidence range constraint."""
    try:
        RedFlag(
            category=FlagCategory.DATA_QUALITY,
            severity=FlagSeverity.LOW,
            title="Invalid Confidence",
            description="Should fail",
            confidence=1.5,  # Out of range (ge=0.0, le=1.0)
            detected_by="test"
        )
        return "RedFlag Validation", False, "Confidence 1.5 did not raise ValidationError"
    except ValidationError:
        return "RedFlag Validation", True, None


def test_extra_field_forbidden():
    """Negative test: Validate extra=forbid constraint."""
    try:
        Evidence(
            source="Test",
            foo="bar"  # Extra field
        )
        return "Extra Field Forbidden", False, "Extra field 'foo' did not raise ValidationError"
    except ValidationError:
        return "Extra Field Forbidden", True, None


def main():
    configure_logging()
    
    test_functions = [
        test_evidence, test_red_flag, test_financial_period, test_check_result,
        test_risk_assessment, test_company_data, test_reconciliation_report,
        test_quant_analysis_report, test_investigation_report, test_audit_report,
        test_red_flag_validation, test_extra_field_forbidden
    ]
    
    results = []
    passed_count = 0
    
    for func in test_functions:
        try:
            name, success, error = func()
            if success:
                passed_count += 1
            results.append((name, success, error))
        except Exception:
            results.append((func.__name__, False, traceback.format_exc()))

    table = Table(title="AuditChain Schema Validation Results")
    table.add_column("Test", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Error", style="red")

    for name, success, error in results:
        status = "[green]PASS[/green]" if success else "[red]FAIL[/red]"
        err_msg = (error[:80] + "...") if error and len(error) > 80 else (error or "")
        table.add_row(name, status, err_msg)

    console.print(table)
    console.print(f"\n[bold]{passed_count} of {len(test_functions)} tests passed.[/bold]")
    
    if passed_count == len(test_functions):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
