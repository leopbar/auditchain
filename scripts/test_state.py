"""Validation tests for AuditState and its helper functions.

Usage:
    python -m scripts.test_state
"""

import sys
import uuid
import traceback
from datetime import date, datetime
from rich.console import Console
from rich.table import Table

from auditchain.core.logging import configure_logging
from auditchain.graph.state import (
    AuditState,
    count_red_flags_by_agent,
    count_red_flags_by_severity,
    create_initial_state,
    get_completed_phases,
    state_summary,
)
from auditchain.schemas.components import CheckResult, FinancialPeriod, RedFlag
from auditchain.schemas.enums import AuditPhase, FlagCategory, FlagSeverity, RiskLevel
from auditchain.schemas.reports import (
    CompanyData,
    ReconciliationReport,
    RiskAssessment,
)

console = Console()


def make_red_flag(severity: FlagSeverity, detected_by: str = "reconciler") -> RedFlag:
    """Helper to create a RedFlag for testing."""
    return RedFlag(
        category=FlagCategory.DATA_QUALITY,
        severity=severity,
        title="test flag",
        description="for testing",
        evidence=[],
        confidence=0.5,
        detected_by=detected_by,
    )


def make_financial_period(filing_id: int = 25) -> FinancialPeriod:
    """Helper to create a FinancialPeriod for testing."""
    return FinancialPeriod(
        filing_id=filing_id,
        fiscal_year=2024,
        period_end=date(2024, 9, 28),
        revenue=391035000000.0,
        cost_of_revenue=None,
        gross_profit=None,
        operating_expenses=None,
        operating_income=None,
        net_income=93736000000.0,
        total_assets=364980000000.0,
        current_assets=None,
        accounts_receivable=None,
        inventory=None,
        total_liabilities=308030000000.0,
        current_liabilities=None,
        stockholders_equity=56950000000.0,
        cash=29943000000.0,
        cash_from_operations=None,
        cash_from_investing=None,
        cash_from_financing=None,
    )


def test_initial_state_creation():
    """Validates default initial state values."""
    run_id = "test-123"
    cik = "0000320193"
    ticker = "AAPL"
    
    state = create_initial_state(audit_run_id=run_id, company_cik=cik, company_ticker=ticker)
    
    assert isinstance(state, dict), "State must be a dict"
    assert state["audit_run_id"] == run_id
    assert state["company_cik"] == cik
    assert state["company_ticker"] == ticker
    
    # Defaults
    assert state["current_phase"] == AuditPhase.PLANNING
    assert state["target_filing_id"] is None
    assert state["messages"] == []
    assert state["red_flags"] == []
    assert state["errors"] == []
    assert state["needs_human_review"] is False
    assert state["total_tokens"] == 0
    assert state["total_cost_usd"] == 0.0
    
    # Reports should all be None
    report_fields = [
        "risk_assessment", "company_data", "reconciliation", 
        "quant_analysis", "investigation", "final_report"
    ]
    for field in report_fields:
        assert state[field] is None, f"Field {field} should be None initially"
        
    return "Initial State Creation", True, None


def test_initial_state_default_ticker():
    """Validates that ticker can be None."""
    state = create_initial_state(audit_run_id="test-456", company_cik="0000885590")
    assert state["company_ticker"] is None
    return "Initial State Default Ticker", True, None


def test_progressive_fill():
    """Simulates filling the state across agents."""
    state = create_initial_state("run-1", "0000320193")
    
    # Phase 1: Planning
    state["risk_assessment"] = RiskAssessment(
        industry="Tech", industry_specific_risks=[], materiality_threshold_usd=1.0, 
        focus_areas=[], prior_fraud_history=False, recommended_depth=RiskLevel.LOW
    )
    
    # Phase 2: Collection
    fp = make_financial_period()
    state["company_data"] = CompanyData(
        cik="0000320193", ticker="AAPL", name="Apple", is_known_fraud=False,
        target_filing_id=25, current_period=fp
    )
    
    # Phase 3: Reconciliation
    state["reconciliation"] = ReconciliationReport(
        filing_id=25,
        checks=[CheckResult(name="test", passed=True)],
        red_flags=[],
        passed=True,
        summary="ok"
    )
    
    assert state["risk_assessment"] is not None
    assert state["company_data"] is not None
    assert state["reconciliation"] is not None
    assert state["quant_analysis"] is None
    
    return "Progressive Fill", True, None


def test_get_completed_phases_empty():
    """Empty state should return empty completed phases."""
    state = create_initial_state("run-1", "cik")
    completed = get_completed_phases(state)
    assert completed == []
    return "Get Completed Phases (Empty)", True, None


def test_get_completed_phases_partial():
    """Partial state should return correct phases in order."""
    state = create_initial_state("run-1", "cik")
    state["risk_assessment"] = "dummy"
    state["company_data"] = "dummy"
    
    completed = get_completed_phases(state)
    assert "planning" in completed
    assert "collection" in completed
    assert len(completed) == 2
    return "Get Completed Phases (Partial)", True, None


def test_count_red_flags_by_severity_empty():
    """Empty red_flags should return all severities with 0 count."""
    state = create_initial_state("run-1", "cik")
    counts = count_red_flags_by_severity(state)
    for sev in FlagSeverity:
        assert counts[sev.value] == 0
    return "Count Flags By Severity (Empty)", True, None


def test_count_red_flags_by_severity_populated():
    """Populated red_flags should return correct counts."""
    state = create_initial_state("run-1", "cik")
    state["red_flags"] = [
        make_red_flag(FlagSeverity.INFO),
        make_red_flag(FlagSeverity.MEDIUM),
        make_red_flag(FlagSeverity.MEDIUM),
        make_red_flag(FlagSeverity.HIGH),
        make_red_flag(FlagSeverity.CRITICAL),
    ]
    counts = count_red_flags_by_severity(state)
    assert counts["info"] == 1
    assert counts["low"] == 0
    assert counts["medium"] == 2
    assert counts["high"] == 1
    assert counts["critical"] == 1
    return "Count Flags By Severity (Populated)", True, None


def test_count_red_flags_by_agent():
    """Should aggregate flags by their detected_by field."""
    state = create_initial_state("run-1", "cik")
    state["red_flags"] = [
        make_red_flag(FlagSeverity.LOW, "reconciler"),
        make_red_flag(FlagSeverity.LOW, "reconciler"),
        make_red_flag(FlagSeverity.LOW, "quant_analyst"),
        make_red_flag(FlagSeverity.LOW, "quant_analyst"),
        make_red_flag(FlagSeverity.LOW, "quant_analyst"),
        make_red_flag(FlagSeverity.LOW, "investigator"),
    ]
    counts = count_red_flags_by_agent(state)
    assert counts["reconciler"] == 2
    assert counts["quant_analyst"] == 3
    assert counts["investigator"] == 1
    return "Count Flags By Agent", True, None


def test_state_summary_returns_string():
    """State summary should produce a descriptive string."""
    state = create_initial_state("test-run", "0000320193", "AAPL")
    summary = state_summary(state)
    assert isinstance(summary, str)
    assert "test-run" in summary
    assert "0000320193" in summary
    assert AuditPhase.PLANNING.value in summary
    return "State Summary returns string", True, None


def test_phase_transitions():
    """Validates that phase transitions work correctly."""
    state = create_initial_state("run-1", "cik")
    assert state["current_phase"] == AuditPhase.PLANNING
    
    state["current_phase"] = AuditPhase.COLLECTION
    assert state["current_phase"] == AuditPhase.COLLECTION
    
    state["current_phase"] = AuditPhase.RECONCILIATION
    assert state["current_phase"] == AuditPhase.RECONCILIATION
    
    state["current_phase"] = AuditPhase.COMPLETED
    assert state["current_phase"] == AuditPhase.COMPLETED
    
    return "Phase Transitions", True, None


def main():
    configure_logging()
    console.print("\n[bold cyan]AuditState Validation Tests[/bold cyan]")
    
    test_functions = [
        test_initial_state_creation,
        test_initial_state_default_ticker,
        test_progressive_fill,
        test_get_completed_phases_empty,
        test_get_completed_phases_partial,
        test_count_red_flags_by_severity_empty,
        test_count_red_flags_by_severity_populated,
        test_count_red_flags_by_agent,
        test_state_summary_returns_string,
        test_phase_transitions,
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

    table = Table(title="AuditState Helper Results")
    table.add_column("Test", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Error", style="red")

    for name, success, error in results:
        status = "[green]PASS[/green]" if success else "[red]FAIL[/red]"
        err_msg = (error[:100] + "...") if error and len(error) > 100 else (error or "")
        table.add_row(name, status, err_msg)

    console.print(table)
    console.print(f"\n[bold]{passed_count} of {len(test_functions)} tests passed.[/bold]")
    
    if passed_count == len(test_functions):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
