"""Test script for the refactored collector_node.

This script validates that the collector_node produces structured CompanyData
correctly, updates the audit state, and handles token/cost tracking.

Usage:
    python -m scripts.test_collector_node
"""

import time
import uuid
import sys
import traceback
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from auditchain.core.logging import configure_logging, get_logger
from auditchain.graph.nodes import collector_node
from auditchain.graph.state import create_initial_state
from auditchain.schemas.enums import AuditPhase
from auditchain.schemas.reports import CompanyData

logger = get_logger(__name__)
console = Console()


def run_test(test_name: str, cik: str, ticker: str | None) -> dict:
    """Executes a single collector_node test case and returns results."""
    console.rule(f"[bold cyan]{test_name}[/bold cyan]", style="cyan")
    console.print(f"[yellow]CIK:[/yellow] {cik}, [yellow]Ticker:[/yellow] {ticker}")

    # Initialize state
    audit_run_id = str(uuid.uuid4())
    initial_state = create_initial_state(
        audit_run_id=audit_run_id, 
        company_cik=cik, 
        company_ticker=ticker
    )
    
    console.print("[dim]Initial state created. Invoking collector_node...[/dim]\n")
    
    start_time = time.time()
    try:
        # Call the node
        update = collector_node(initial_state)
        duration = time.time() - start_time
        
        # Basic validations
        if not isinstance(update, dict):
            raise TypeError(f"Update must be a dict, got {type(update)}")
            
        company_data = update.get("company_data")
        success = company_data is not None and isinstance(company_data, CompanyData)
        
        if success:
            console.print(f"[bold green]Status: SUCCESS[/bold green]")
            console.print(f"Duration: {duration:.2f}s")
            console.print(f"Tokens used: {update.get('total_tokens', 0)}")
            console.print(f"Estimated cost: ${update.get('total_cost_usd', 0.0):.4f}")
            console.print(f"Phase advanced to: {update.get('current_phase', AuditPhase.FAILED).value}")
            console.print(f"Filing ID analyzed: {update.get('target_filing_id')}")
            console.print(f"Historical periods collected: {len(company_data.historical_periods)}")
            console.print(f"Messages count: {len(update.get('messages', []))}")
            
            # Detailed display
            cp = company_data.current_period
            panel_content = [
                f"[bold]Company:[/bold] {company_data.name} ({company_data.ticker} | CIK: {company_data.cik})",
                f"[bold]Known Fraud:[/bold] {'[red]YES[/red]' if company_data.is_known_fraud else '[green]NO[/green]'}",
                "\n[bold underline]Current Period Findings:[/bold underline]",
                f"  FY{cp.fiscal_year} (End: {cp.period_end})",
                f"  Revenue:      ${cp.revenue:,.0f} USD" if cp.revenue is not None else "  Revenue:      Not reported",
                f"  Net Income:   ${cp.net_income:,.0f} USD" if cp.net_income is not None else "  Net Income:   Not reported",
                f"  Total Assets: ${cp.total_assets:,.0f} USD" if cp.total_assets is not None else "  Total Assets: Not reported",
                f"  Total Liab:   ${cp.total_liabilities:,.0f} USD" if cp.total_liabilities is not None else "  Total Liab:   Not reported",
                f"  Equity:       ${cp.stockholders_equity:,.0f} USD" if cp.stockholders_equity is not None else "  Equity:       Not reported",
                f"  Cash:         ${cp.cash:,.0f} USD" if cp.cash is not None else "  Cash:         Not reported",
                "\n[bold underline]Historical Trend (YoY):[/bold underline]"
            ]
            
            for hp in company_data.historical_periods[:4]:
                rev_str = f"${hp.revenue:,.0f}" if hp.revenue is not None else "N/A"
                inc_str = f"${hp.net_income:,.0f}" if hp.net_income is not None else "N/A"
                panel_content.append(f"  FY{hp.fiscal_year}: Revenue {rev_str} | Net Income {inc_str}")
            
            console.print(Panel("\n".join(panel_content), title="[bold white]Extracted Company Data[/bold white]", border_style="green"))
            
        else:
            console.print(f"[bold red]Status: FAILED[/bold red]")
            console.print(f"Duration: {duration:.2f}s")
            console.print(f"Errors: {update.get('errors', [])}")
            console.print(f"Current phase: {update.get('current_phase', 'unknown')}")
            
        return {
            "test_name": test_name,
            "success": success,
            "duration": duration,
            "tokens": update.get("total_tokens", 0),
            "cost": update.get("total_cost_usd", 0.0),
            "filing_id": update.get("target_filing_id"),
            "historical_count": len(company_data.historical_periods) if success else 0,
            "error": None if success else update.get("errors", ["No data returned"])
        }
        
    except Exception as e:
        console.print(f"[bold red]Exception during test execution:[/bold red]\n{traceback.format_exc()}")
        return {
            "test_name": test_name,
            "success": False,
            "duration": 0,
            "tokens": 0,
            "cost": 0.0,
            "filing_id": None,
            "historical_count": 0,
            "error": str(e)
        }


def main():
    configure_logging()
    
    console.print("\n[bold cyan]AuditChain Collector Node Validation[/bold cyan]\n")
    
    tests = [
        ("Test 1: Apple (clean control)", "0000320193", "AAPL"),
        ("Test 2: BHC (known fraud case)", "0000885590", "BHC"),
    ]
    
    results = []
    for name, cik, ticker in tests:
        res = run_test(name, cik, ticker)
        results.append(res)
        console.print("\n")

    # Summary Table
    table = Table(title="Collector Node Summary Results")
    table.add_column("Test", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Duration (s)", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Cost (USD)", justify="right")
    table.add_column("Filing ID", justify="right")
    table.add_column("History", justify="right")

    passed_count = 0
    total_tokens = 0
    total_cost = 0.0
    
    for res in results:
        status = "[green]PASS[/green]" if res["success"] else "[red]FAIL[/red]"
        if res["success"]:
            passed_count += 1
        
        total_tokens += res["tokens"]
        total_cost += res["cost"]
        
        table.add_row(
            res["test_name"],
            status,
            f"{res['duration']:.2f}",
            str(res["tokens"]),
            f"{res['cost']:.4f}",
            str(res["filing_id"]) if res["filing_id"] else "-",
            str(res["historical_count"])
        )

    console.print(table)
    console.print(f"\n[bold]{passed_count} of {len(tests)} tests passed.[/bold]")
    console.print(f"Total tokens combined: [white]{total_tokens}[/white]")
    console.print(f"Total cost combined:   [green]${total_cost:.4f}[/green]\n")
    
    if passed_count == len(tests):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
