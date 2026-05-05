"""Test script for the reconciler_node in sequence with collector_node.

This script validates the multi-agent pipeline by first collecting data
and then performing mathematical reconciliation.

Usage:
    python -m scripts.test_reconciler_node
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
from auditchain.graph.nodes import collector_node, reconciler_node
from auditchain.graph.state import create_initial_state, AuditState
from auditchain.schemas.enums import AuditPhase
from auditchain.schemas.reports import ReconciliationReport

logger = get_logger(__name__)
console = Console()


def merge_update(state: AuditState, update: dict[str, Any]) -> None:
    """Helper to merge node updates into the state, simulating LangGraph logic."""
    for key, value in update.items():
        if key == "messages":
            state["messages"].extend(value)
        elif key == "red_flags":
            state["red_flags"].extend(value)
        elif key == "total_tokens":
            state["total_tokens"] += value
        elif key == "total_cost_usd":
            state["total_cost_usd"] += value
        elif key == "errors":
            state["errors"].extend(value)
        else:
            state[key] = value  # type: ignore


def run_test(test_name: str, cik: str, ticker: str | None) -> dict:
    """Executes collector and reconciler nodes in sequence and returns results."""
    console.rule(f"[bold cyan]{test_name}[/bold cyan]", style="cyan")
    console.print(f"[yellow]CIK:[/yellow] {cik}, [yellow]Ticker:[/yellow] {ticker}")

    # Initialize state
    state = create_initial_state(
        audit_run_id=str(uuid.uuid4()), 
        company_cik=cik, 
        company_ticker=ticker
    )
    
    start_time = time.time()
    try:
        # 1. Run Collector Node
        console.print("[dim]Step 1: Invoking collector_node...[/dim]")
        coll_update = collector_node(state)
        merge_update(state, coll_update)
        
        if coll_update.get("current_phase") == AuditPhase.FAILED:
            raise RuntimeError(f"Collector failed: {coll_update.get('errors')}")

        # 2. Run Reconciler Node
        console.print("[dim]Step 2: Invoking reconciler_node...[/dim]")
        rec_update = reconciler_node(state)
        merge_update(state, rec_update)
        
        duration = time.time() - start_time
        
        if rec_update.get("current_phase") == AuditPhase.FAILED:
             success = False
        else:
             success = True
             
        report = state.get("reconciliation")
        
        if success and report:
            console.print(f"[bold green]Status: SUCCESS[/bold green]")
            console.print(f"Total Duration: {duration:.2f}s")
            console.print(f"Total Tokens:   {state['total_tokens']}")
            console.print(f"Total Cost:     ${state['total_cost_usd']:.4f}")
            
            # Reconciliation Report Panel
            pass_color = "green" if report.passed else "red"
            panel_content = [
                f"[bold]Filing ID:[/bold] {report.filing_id}",
                f"[bold]Status:[/bold]   [{pass_color}]{'PASSED' if report.passed else 'FAILED'}[/{pass_color}]",
                f"[bold]Summary:[/bold]  {report.summary}",
                f"[bold]Checks executed:[/bold] {len(report.checks)}",
                f"[bold]Red Flags raised:[/bold] {len(report.red_flags)}"
            ]
            
            if report.red_flags:
                panel_content.append("\n[bold underline]RED FLAGS:[/bold underline]")
                for flag in report.red_flags:
                    panel_content.append(f"  • [[bold]{flag.severity.value.upper()}[/bold]] {flag.title} ({flag.category.value})")
            
            console.print(Panel("\n".join(panel_content), title="[bold white]Reconciliation Report[/bold white]", border_style=pass_color))
            
            # Checks detail table
            check_table = Table(title="Validation Checks Detail", box=None)
            check_table.add_column("Check Name", style="white")
            check_table.add_column("Result", justify="center")
            check_table.add_column("Notes", style="dim")
            
            for check in report.checks:
                res_str = "[green]✓[/green]" if check.passed else "[red]✗[/red]"
                note_short = (check.notes[:77] + "...") if check.notes and len(check.notes) > 80 else (check.notes or "")
                check_table.add_row(check.name, res_str, note_short)
            
            console.print(check_table)
            
        else:
            console.print(f"[bold red]Status: FAILED[/bold red]")
            console.print(f"Errors: {state.get('errors', [])}")
            
        return {
            "test_name": test_name,
            "success": success,
            "phase": state["current_phase"].value,
            "tokens": state["total_tokens"],
            "cost": state["total_cost_usd"],
            "red_flags": len(state["red_flags"]),
            "duration": duration
        }
        
    except Exception as e:
        console.print(f"[bold red]Exception during test execution:[/bold red]\n{traceback.format_exc()}")
        return {
            "test_name": test_name,
            "success": False,
            "phase": "EXCEPTION",
            "tokens": 0,
            "cost": 0.0,
            "red_flags": 0,
            "duration": 0
        }


def main():
    configure_logging()
    
    console.print("\n[bold cyan]AuditChain: Collector + Reconciler Integration Test[/bold cyan]\n")
    
    tests = [
        ("Test 1: Apple (clean control)", "0000320193", "AAPL"),
        ("Test 2: BHC (potential inconsistencies)", "0000885590", "BHC"),
    ]
    
    results = []
    for name, cik, ticker in tests:
        res = run_test(name, cik, ticker)
        results.append(res)
        console.print("\n")

    # Final Summary Table
    summary_table = Table(title="Pipeline Execution Summary")
    summary_table.add_column("Test", style="cyan")
    summary_table.add_column("Phase reached", style="magenta")
    summary_table.add_column("Status", justify="center")
    summary_table.add_column("Tokens", justify="right")
    summary_table.add_column("Cost (USD)", justify="right")
    summary_table.add_column("Red Flags", justify="right")

    passed_count = 0
    total_tokens = 0
    total_cost = 0.0
    
    for res in results:
        status = "[green]PASS[/green]" if res["success"] else "[red]FAIL[/red]"
        if res["success"]:
            passed_count += 1
        
        total_tokens += res["tokens"]
        total_cost += res["cost"]
        
        summary_table.add_row(
            res["test_name"],
            res["phase"],
            status,
            str(res["tokens"]),
            f"{res['cost']:.4f}",
            str(res["red_flags"])
        )

    console.print(summary_table)
    console.print(f"\n[bold]{passed_count} of {len(tests)} tests completed.[/bold]")
    console.print(f"Combined total tokens: [white]{total_tokens}[/white]")
    console.print(f"Combined total cost:   [green]${total_cost:.4f}[/green]\n")
    
    if passed_count == len(tests):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
