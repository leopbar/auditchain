"""Validation tests for reconciliation tools.

This script validates the mathematical tools used by the Reconciler Agent,
including the accounting equation, year-over-year consistency, and 
accruals analysis. It includes both synthetic edge cases and real-world 
integration tests via the collector_node.

Usage:
    python -m scripts.test_reconciliation_tools
"""

import sys
import uuid
import traceback
from datetime import date
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from auditchain.core.logging import configure_logging
from auditchain.graph.nodes import collector_node
from auditchain.graph.state import create_initial_state
from auditchain.schemas.components import FinancialPeriod, CheckResult
from auditchain.tools.reconciliation import (
    check_accounting_equation,
    check_yoy_consistency,
    compare_income_vs_cashflow,
)

console = Console()


def make_period(
    filing_id: int = 1,
    fiscal_year: int = 2024,
    revenue: float | None = None,
    net_income: float | None = None,
    total_assets: float | None = None,
    total_liabilities: float | None = None,
    stockholders_equity: float | None = None,
    cash: float | None = None,
    cash_from_operations: float | None = None,
) -> FinancialPeriod:
    """Utility to create FinancialPeriod test cases quickly."""
    return FinancialPeriod(
        filing_id=filing_id,
        fiscal_year=fiscal_year,
        period_end=date(fiscal_year, 12, 31),
        revenue=revenue,
        cost_of_revenue=None,
        gross_profit=None,
        operating_expenses=None,
        operating_income=None,
        net_income=net_income,
        total_assets=total_assets,
        current_assets=None,
        accounts_receivable=None,
        inventory=None,
        total_liabilities=total_liabilities,
        current_liabilities=None,
        stockholders_equity=stockholders_equity,
        cash=cash,
        cash_from_operations=cash_from_operations,
        cash_from_investing=None,
        cash_from_financing=None,
    )


def print_check_result(result: CheckResult):
    """Rich formatting for a single CheckResult."""
    status_str = "[green]PASSED[/green]" if result.passed else "[red]FAILED[/red]"
    console.print(f"  [bold]{result.name:.<40}[/bold] {status_str}")
    console.print(f"  [dim]Notes: {result.notes}[/dim]")


def main():
    configure_logging()
    console.print("\n[bold cyan]AuditChain Reconciliation Tools Validation[/bold cyan]\n")

    results_data = []

    def log_test_result(group, name, success, notes):
        results_data.append({
            "group": group,
            "name": name,
            "success": success,
            "notes": notes
        })

    # --- GROUP 1: check_accounting_equation ---
    console.rule("[bold cian]Group 1: Accounting Equation[/bold cian]", style="cyan")

    # Test 1.1: Apple-like clean balance
    name = "Apple-like clean balance"
    p = make_period(total_assets=359241000000.0, total_liabilities=285508000000.0, stockholders_equity=73733000000.0)
    console.print(f"[bold cyan]{name}[/bold cyan]")
    res = check_accounting_equation.invoke({"period": p})
    print_check_result(res)
    log_test_result("Accounting Eq", name, res.passed is True, res.notes)

    # Test 1.2: BHC-like balanced (custom numbers to balance exactly)
    name = "Negative equity balance"
    p = make_period(total_assets=26366000000.0, total_liabilities=25989000000.0, stockholders_equity=377000000.0)
    console.print(f"[bold cyan]{name}[/bold cyan]")
    res = check_accounting_equation.invoke({"period": p})
    print_check_result(res)
    log_test_result("Accounting Eq", name, res.passed is True, res.notes)

    # Test 1.3: Broken equation (synthetic fraud)
    name = "Broken equation (fraud)"
    p = make_period(total_assets=1000000000.0, total_liabilities=400000000.0, stockholders_equity=300000000.0)
    console.print(f"[bold cyan]{name}[/bold cyan]")
    res = check_accounting_equation.invoke({"period": p})
    print_check_result(res)
    log_test_result("Accounting Eq", name, res.passed is False, res.notes)

    # Test 1.4: Insufficient data
    name = "Insufficient data (None)"
    p = make_period(total_assets=1000000000.0, total_liabilities=None, stockholders_equity=None)
    console.print(f"[bold cyan]{name}[/bold cyan]")
    res = check_accounting_equation.invoke({"period": p})
    print_check_result(res)
    log_test_result("Accounting Eq", name, res.passed is False, res.notes)

    # --- GROUP 2: check_yoy_consistency ---
    console.rule("[bold cian]Group 2: YoY Consistency[/bold cian]", style="cyan")

    # Test 2.1: Normal growth
    name = "Normal growth (Apple-like)"
    curr = make_period(fiscal_year=2024, revenue=391000000000.0, net_income=93700000000.0, total_assets=364000000000.0, total_liabilities=308000000000.0)
    prior = make_period(fiscal_year=2023, revenue=383000000000.0, net_income=97000000000.0, total_assets=352000000000.0, total_liabilities=290000000000.0)
    console.print(f"[bold cyan]{name}[/bold cyan]")
    res_list = check_yoy_consistency.invoke({"current": curr, "prior": prior})
    all_passed = all(r.passed for r in res_list)
    for r in res_list: print_check_result(r)
    log_test_result("YoY Consistency", name, all_passed is True, "All metrics passed within range")

    # Test 2.2: Suspicious revenue spike
    name = "Suspicious revenue spike"
    curr = make_period(fiscal_year=2024, revenue=200000000000.0, net_income=10000000000.0, total_assets=100000000000.0, total_liabilities=50000000000.0)
    prior = make_period(fiscal_year=2023, revenue=100000000000.0, net_income=10000000000.0, total_assets=100000000000.0, total_liabilities=50000000000.0)
    console.print(f"[bold cyan]{name}[/bold cyan]")
    res_list = check_yoy_consistency.invoke({"current": curr, "prior": prior})
    rev_check = next(r for r in res_list if "revenue" in r.name)
    for r in res_list: print_check_result(r)
    log_test_result("YoY Consistency", name, rev_check.passed is False, f"Revenue check failed as expected: {rev_check.notes}")

    # Test 2.3: Mixed signals
    name = "Mixed signals (liabilities spike)"
    curr = make_period(fiscal_year=2024, revenue=100000000000.0, net_income=-5000000000.0, total_assets=80000000000.0, total_liabilities=120000000000.0)
    prior = make_period(fiscal_year=2023, revenue=110000000000.0, net_income=8000000000.0, total_assets=120000000000.0, total_liabilities=70000000000.0)
    console.print(f"[bold cyan]{name}[/bold cyan]")
    res_list = check_yoy_consistency.invoke({"current": curr, "prior": prior})
    liab_check = next(r for r in res_list if "total_liabilities" in r.name)
    for r in res_list: print_check_result(r)
    log_test_result("YoY Consistency", name, liab_check.passed is False, f"Liabilities check failed as expected: {liab_check.notes}")

    # --- GROUP 3: compare_income_vs_cashflow ---
    console.rule("[bold cian]Group 3: Income vs Cashflow[/bold cian]", style="cyan")

    # Test 3.1: Healthy
    name = "Healthy: income matches cash"
    p = make_period(net_income=10000000000.0, cash_from_operations=11000000000.0, total_assets=100000000000.0)
    console.print(f"[bold cyan]{name}[/bold cyan]")
    res = compare_income_vs_cashflow.invoke({"period": p})
    print_check_result(res)
    log_test_result("Income vs Cash", name, res.passed is True, res.notes)

    # Test 3.2: Suspicious (high accruals)
    name = "Suspicious: high accruals"
    p = make_period(net_income=10000000000.0, cash_from_operations=2000000000.0, total_assets=50000000000.0)
    console.print(f"[bold cyan]{name}[/bold cyan]")
    res = compare_income_vs_cashflow.invoke({"period": p})
    print_check_result(res)
    log_test_result("Income vs Cash", name, res.passed is False, res.notes)

    # Test 3.3: Insufficient data
    name = "Insufficient data (Income/Cash)"
    p = make_period(net_income=10000000000.0, cash_from_operations=None, total_assets=100000000000.0)
    console.print(f"[bold cyan]{name}[/bold cyan]")
    res = compare_income_vs_cashflow.invoke({"period": p})
    print_check_result(res)
    log_test_result("Income vs Cash", name, res.passed is True, res.notes)

    # --- GROUP 4: Integration with REAL data ---
    console.rule("[bold cian]Group 4: Real-world Integration[/bold cian]", style="cyan")
    
    try:
        name = "Real-world: Apple via collector"
        console.print(f"[bold cyan]{name}[/bold cyan]")
        initial_state = create_initial_state(audit_run_id=str(uuid.uuid4()), company_cik="0000320193", company_ticker="AAPL")
        update = collector_node(initial_state)
        cd = update.get("company_data")
        
        if cd:
            # Check equation
            res_eq = check_accounting_equation.invoke({"period": cd.current_period})
            print_check_result(res_eq)
            
            # Check YoY if history exists
            if cd.historical_periods:
                res_yoy = check_yoy_consistency.invoke({"current": cd.current_period, "prior": cd.historical_periods[0]})
                for r in res_yoy: print_check_result(r)
                
            log_test_result("Integration", name, res_eq.passed is True, "Apple data balances and passed integration")
        else:
            log_test_result("Integration", name, False, "Collector failed to return data")
    except Exception:
        log_test_result("Integration", "Real-world: Apple via collector", False, traceback.format_exc())

    # --- FINAL SUMMARY ---
    console.print("\n")
    table = Table(title="Reconciliation Tools Validation Summary")
    table.add_column("Group", style="magenta")
    table.add_column("Test Name", style="cyan")
    table.add_column("Result", justify="center")
    table.add_column("Notes", style="dim")

    passed_count = 0
    for r in results_data:
        status = "[green]PASS[/green]" if r["success"] else "[red]FAIL[/red]"
        if r["success"]: passed_count += 1
        note_short = (r["notes"][:77] + "...") if len(r["notes"]) > 80 else r["notes"]
        table.add_row(r["group"], r["name"], status, note_short)

    console.print(table)
    console.print(f"\n[bold]{passed_count} of {len(results_data)} tests matched expected behavior.[/bold]\n")

    if passed_count == len(results_data):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
