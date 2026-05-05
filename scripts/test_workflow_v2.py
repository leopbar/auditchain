"""Test script for the refactored AuditChain workflow (v2).

This script executes the complete multi-agent LangGraph pipeline,
validating the end-to-end flow from data collection to mathematical 
reconciliation with structured outputs.

Usage:
    python -m scripts.test_workflow_v2
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
from auditchain.graph.workflow import build_audit_graph
from auditchain.graph.state import (
    create_initial_state, 
    state_summary, 
    count_red_flags_by_severity
)
from auditchain.schemas.enums import AuditPhase

logger = get_logger(__name__)
console = Console()


def run_audit(graph: Any, test_name: str, cik: str, ticker: str | None) -> dict:
    """Executes the full audit workflow for a company and returns results."""
    console.rule(f"[bold cyan]{test_name}[/bold cyan]", style="cyan")
    console.print(f"[yellow]CIK:[/yellow] {cik}, [yellow]Ticker:[/yellow] {ticker}")

    initial_state = create_initial_state(
        audit_run_id=str(uuid.uuid4()), 
        company_cik=cik, 
        company_ticker=ticker
    )
    
    start_time = time.time()
    try:
        # Invoke the complete graph
        console.print("[dim]Invoking AuditChain Graph...[/dim]")
        result = graph.invoke(initial_state)
        duration = time.time() - start_time
        
        cd = result.get("company_data")
        rec = result.get("reconciliation")
        red_flags = result.get("red_flags", [])
        
        # Display Results
        panel_content = []
        
        # 1. Company Info
        if cd:
            panel_content.append(f"[bold white]Company:[/bold white] {cd.name} ({cd.ticker})")
            panel_content.append(f"[dim]Known Fraud: {cd.is_known_fraud}[/dim]\n")
        else:
            panel_content.append("[red]No company data collected.[/red]\n")
            
        # 2. Reconciliation Summary
        if rec:
            pass_color = "green" if rec.passed else "red"
            panel_content.append(f"[bold white]Reconciliation Status:[/bold white] [{pass_color}]{'PASSED' if rec.passed else 'FAILED'}[/{pass_color}]")
            panel_content.append(f"[dim]{rec.summary}[/dim]")
            panel_content.append(f"[dim]Checks executed: {len(rec.checks)} | Red Flags: {len(rec.red_flags)}[/dim]\n")
        else:
            panel_content.append("[yellow]No reconciliation report produced.[/yellow]\n")
            
        # 3. All Red Flags
        if red_flags:
            panel_content.append("[bold underline]Detected Risks (Red Flags):[/bold underline]")
            for flag in red_flags:
                panel_content.append(f"  • [[bold]{flag.severity.value.upper()}[/bold]] {flag.title} ({flag.category.value})")
            panel_content.append("")
            
        # 4. State Summary & Resources
        panel_content.append(f"[bold white]Execution Summary:[/bold white]")
        panel_content.append(f"  {state_summary(result)}")
        panel_content.append(f"  Total Duration: {duration:.2f}s")
        panel_content.append(f"  Total Tokens:   {result.get('total_tokens', 0)}")
        panel_content.append(f"  Total Cost:     ${result.get('total_cost_usd', 0.0):.4f}")
        panel_content.append(f"  Final Phase:    [magenta]{result.get('current_phase', AuditPhase.FAILED).value}[/magenta]")
        
        console.print(Panel("\n".join(panel_content), title=f"[bold]Audit Result: {ticker or cik}[/bold]", border_style="cyan"))
        
        return {
            "test_name": test_name,
            "phase": result.get("current_phase", AuditPhase.FAILED).value,
            "passed": rec.passed if rec else False,
            "red_flags": len(red_flags),
            "tokens": result.get("total_tokens", 0),
            "cost": result.get("total_cost_usd", 0.0),
            "duration": duration,
            "success": result.get("current_phase") != AuditPhase.FAILED
        }
        
    except Exception as e:
        console.print(f"[bold red]Exception during workflow execution:[/bold red]\n{traceback.format_exc()}")
        return {
            "test_name": test_name,
            "phase": "EXCEPTION",
            "passed": False,
            "red_flags": 0,
            "tokens": 0,
            "cost": 0.0,
            "duration": 0,
            "success": False
        }


def main():
    configure_logging()
    
    console.print("\n[bold reverse cyan] Building AuditChain Workflow Graph... [/bold reverse cyan]\n")
    graph = build_audit_graph()
    
    tests = [
        ("Full Audit: Apple (AAPL)", "0000320193", "AAPL"),
        ("Full Audit: BHC", "0000885590", "BHC"),
    ]
    
    results = []
    for name, cik, ticker in tests:
        res = run_audit(graph, name, cik, ticker)
        results.append(res)
        console.print("\n")

    # Final Summary Table
    summary_table = Table(title="End-to-End Workflow Summary (V2)")
    summary_table.add_column("Test", style="cyan")
    summary_table.add_column("Final Phase", style="magenta")
    summary_table.add_column("Passed", justify="center")
    summary_table.add_column("Flags", justify="right")
    summary_table.add_column("Tokens", justify="right")
    summary_table.add_column("Cost (USD)", justify="right")
    summary_table.add_column("Duration (s)", justify="right")
    summary_table.add_column("Status", justify="center")

    passed_count = 0
    for res in results:
        status = "[green]PASS[/green]" if res["success"] else "[red]FAIL[/red]"
        passed_mark = "[green]✓[/green]" if res["passed"] else "[red]✗[/red]"
        if res["success"]:
            passed_count += 1
            
        summary_table.add_row(
            res["test_name"],
            res["phase"],
            passed_mark,
            str(res["red_flags"]),
            str(res["tokens"]),
            f"{res['cost']:.4f}",
            f"{res['duration']:.2f}",
            status
        )

    console.print(summary_table)
    console.print(f"\n[bold]{passed_count} of {len(tests)} audits completed successfully.[/bold]\n")
    
    if passed_count == len(tests):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
