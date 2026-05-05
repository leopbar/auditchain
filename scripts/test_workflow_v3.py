"""Test script for the AuditChain workflow (v3) with 3 agents.

Executes the complete multi-agent LangGraph pipeline:
Collector -> Reconciler -> Quant Analyst

Usage:
    python -m scripts.test_workflow_v3
"""

import time
import uuid
import sys
import traceback
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from rich.prompt import Prompt

from auditchain.core.config import get_settings
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
settings = get_settings()


def run_audit(graph: Any, test_name: str, cik: str, ticker: str | None) -> dict:
    """Executes the full audit workflow (3 nodes) for a company."""
    console.rule(f"[bold cyan]{test_name}[/bold cyan]", style="cyan")
    console.print(f"[yellow]CIK:[/yellow] {cik}, [yellow]Ticker:[/yellow] {ticker}")

    initial_state = create_initial_state(
        audit_run_id=str(uuid.uuid4()), 
        company_cik=cik, 
        company_ticker=ticker
    )
    
    start_time = time.time()
    try:
        console.print("[dim]Invoking AuditChain Graph (3 agents)...[/dim]")
        result = graph.invoke(initial_state)
        duration = time.time() - start_time
        
        cd = result.get("company_data")
        rec = result.get("reconciliation")
        quant = result.get("quant_analysis")
        red_flags = result.get("red_flags", [])
        
        panel_content = []
        
        # 1. Company Info
        if cd:
            panel_content.append(f"[bold white]Company:[/bold white] {cd.name} ({cd.ticker})")
            panel_content.append(f"[dim]Known Fraud: {cd.is_known_fraud}[/dim]\n")
        else:
            panel_content.append("[red]No company data collected.[/red]\n")
            
        # 2. Reconciliation Result
        if rec:
            pass_color = "green" if rec.passed else "red"
            panel_content.append(f"[bold white]Phase 1: Reconciliation:[/bold white] [{pass_color}]{'PASSED' if rec.passed else 'FAILED'}[/{pass_color}]")
            panel_content.append(f"[dim]Summary: {rec.summary}[/dim]\n")
        else:
            panel_content.append("[yellow]Phase 1: No reconciliation data.[/yellow]\n")

        # 3. Quant Analysis Result
        if quant:
            panel_content.append("[bold white]Phase 2: Quantitative Analysis:[/bold white]")
            panel_content.append(f"  • Beneish M-Score: {quant.beneish_mscore if quant.beneish_mscore is not None else 'N/A'}")
            panel_content.append(f"    [dim]{quant.beneish_interpretation}[/dim]")
            panel_content.append(f"  • Altman Z-Score:  {quant.altman_zscore if quant.altman_zscore is not None else 'N/A'}")
            panel_content.append(f"    [dim]{quant.altman_interpretation}[/dim]")
            panel_content.append(f"  • Accruals Ratio:  {quant.accruals_ratio if quant.accruals_ratio is not None else 'N/A'}\n")
        else:
            panel_content.append("[yellow]Phase 2: No quantitative analysis data.[/yellow]\n")
            
        # 4. All Red Flags Consolidated
        if red_flags:
            panel_content.append("[bold underline]Consolidated Findings (Red Flags):[/bold underline]")
            # Group by severity for better display
            by_severity = {"critical": [], "high": [], "medium": [], "low": []}
            for flag in red_flags:
                by_severity[flag.severity.value].append(flag)
            
            for sev in ["critical", "high", "medium", "low"]:
                for flag in by_severity[sev]:
                    color = "red" if sev in ["critical", "high"] else "yellow"
                    panel_content.append(f"  • [[{color}]{sev.upper()}[/{color}]] {flag.title} [dim]({flag.category.value})[/dim]")
            panel_content.append("")
            
        # 5. Resources & Phase
        panel_content.append(f"[bold white]Execution Summary:[/bold white]")
        panel_content.append(f"  {state_summary(result)}")
        panel_content.append(f"  Duration: {duration:.2f}s | Tokens: {result.get('total_tokens', 0)} | Cost: ${result.get('total_cost_usd', 0.0):.4f}")
        panel_content.append(f"  Final Phase: [magenta]{result.get('current_phase', AuditPhase.FAILED).value}[/magenta]")
        
        console.print(Panel("\n".join(panel_content), title=f"[bold]Workflow V3 Audit: {ticker or cik}[/bold]", border_style="cyan"))
        
        return {
            "test_name": test_name,
            "phase": result.get("current_phase", AuditPhase.FAILED).value,
            "rec_passed": rec.passed if rec else False,
            "quant_flags": len(quant.red_flags) if quant else 0,
            "total_red_flags": len(red_flags),
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
            "rec_passed": False,
            "quant_flags": 0,
            "total_red_flags": 0,
            "tokens": 0,
            "cost": 0.0,
            "duration": 0,
            "success": False
        }


def main():
    configure_logging()
    
    console.print("\n[bold cyan]AuditChain: End-to-End Workflow Validation[/bold cyan]\n")
    
    # 1. Interactive Model Selection
    console.print("[bold yellow]Select LLM Model for Audit:[/bold yellow]")
    console.print("1) gpt-4o (Smartest, strict rate limits)")
    console.print("2) gpt-4o-mini (Faster, higher rate limits, recommended)")
    
    choice = Prompt.ask("Enter choice", choices=["1", "2"], default="2")
    model_choice = "gpt-4o" if choice == "1" else "gpt-4o-mini"
    
    # Override settings for this run
    settings.llm_smart_model = model_choice
    console.print(f"[bold green]Using model:[/bold green] {model_choice}\n")
    
    console.print("[bold reverse cyan] Building AuditChain Workflow Graph [/bold reverse cyan]\n")
    graph = build_audit_graph()
    
    tests = [
        ("Full Audit: Apple (AAPL)", "0000320193", "AAPL"),
        ("Full Audit: BHC", "0000885590", "BHC"),
    ]
    
    results = []
    for i, (name, cik, ticker) in enumerate(tests):
        if i > 0:
            console.print(f"[yellow]Waiting 30 seconds to reset OpenAI Rate Limits (TPM)...[/yellow]")
            time.sleep(30)
            
        res = run_audit(graph, name, cik, ticker)
        results.append(res)
        console.print("\n")

    # Final Summary Table
    summary_table = Table(title="End-to-End Workflow Summary (V3)")
    summary_table.add_column("Test", style="cyan")
    summary_table.add_column("Final Phase", style="magenta")
    summary_table.add_column("Rec. Pass", justify="center")
    summary_table.add_column("Quant Flags", justify="right")
    summary_table.add_column("Total Red Flags", justify="right")
    summary_table.add_column("Tokens", justify="right")
    summary_table.add_column("Cost (USD)", justify="right")
    summary_table.add_column("Duration (s)", justify="right")
    summary_table.add_column("Status", justify="center")

    passed_count = 0
    for res in results:
        status = "[green]PASS[/green]" if res["success"] else "[red]FAIL[/red]"
        rec_mark = "[green]✓[/green]" if res["rec_passed"] else "[red]✗[/red]"
        if res["success"]:
            passed_count += 1
            
        summary_table.add_row(
            res["test_name"],
            res["phase"],
            rec_mark,
            str(res["quant_flags"]),
            str(res["total_red_flags"]),
            str(res["tokens"]),
            f"{res['cost']:.4f}",
            f"{res['duration']:.2f}",
            status
        )

    console.print(summary_table)
    console.print(f"\n[bold]{passed_count} of {len(tests)} 3-agent audits completed successfully.[/bold]\n")


if __name__ == "__main__":
    main()
