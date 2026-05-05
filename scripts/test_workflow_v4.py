"""Test script for the AuditChain workflow (v4) with 4 agents.

Executes the complete multi-agent LangGraph pipeline:
Collector -> Reconciler -> Quant Analyst -> Investigator

Usage:
    python -m scripts.test_workflow_v4
"""

import time
import uuid
import sys
import traceback
from typing import Any

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt

from auditchain.core.config import get_settings
from auditchain.core.logging import configure_logging, get_logger
from auditchain.graph.workflow import build_audit_graph
from auditchain.graph.state import (
    create_initial_state, 
    state_summary, 
)
from auditchain.schemas.enums import AuditPhase

logger = get_logger(__name__)
console = Console()
settings = get_settings()


def run_audit(graph: Any, test_name: str, cik: str, ticker: str | None) -> dict:
    """Executes the full audit workflow (4 nodes) for a company."""
    console.rule(f"[bold cyan]{test_name}[/bold cyan]", style="cyan")
    console.print(f"[yellow]CIK:[/yellow] {cik}, [yellow]Ticker:[/yellow] {ticker}")

    initial_state = create_initial_state(
        audit_run_id=str(uuid.uuid4()), 
        company_cik=cik, 
        company_ticker=ticker
    )
    
    start_time = time.time()
    try:
        console.print("[dim]Invoking AuditChain Graph (4 agents)...[/dim]")
        result = graph.invoke(initial_state)
        duration = time.time() - start_time
        
        cd = result.get("company_data")
        rec = result.get("reconciliation")
        quant = result.get("quant_analysis")
        inv = result.get("investigation")
        red_flags = result.get("red_flags", [])
        
        # 1. Company Info Panel
        company_info = []
        if cd:
            fraud_status = "[bold red]YES[/bold red]" if cd.is_known_fraud else "[green]NO[/green]"
            company_info.append(f"[bold]Company:[/bold] {cd.name} ({cd.ticker})")
            company_info.append(f"[bold]Known Fraud:[/bold] {fraud_status}")
            company_info.append(f"[dim]CIK: {cd.cik}[/dim]")
        
        # 2. Reconciliation Panel
        rec_info = []
        if rec:
            pass_color = "green" if rec.passed else "red"
            rec_info.append(f"[bold]Status:[/bold] [{pass_color}]{'PASSED' if rec.passed else 'FAILED'}[/{pass_color}]")
            rec_info.append(f"[bold]Red Flags:[/bold] {len(rec.red_flags)}")
            rec_info.append(f"[dim]Summary: {rec.summary}[/dim]")
        
        # 3. Quant Analysis Panel
        quant_info = []
        if quant:
            m_score = f"{quant.beneish_mscore:.4f}" if quant.beneish_mscore is not None else "N/A"
            z_score = f"{quant.altman_zscore:.4f}" if quant.altman_zscore is not None else "N/A"
            accruals = f"{quant.accruals_ratio:.4f}" if quant.accruals_ratio is not None else "N/A"
            
            quant_info.append(f"[bold]Beneish M-Score:[/bold] {m_score} [dim]({quant.beneish_interpretation})[/dim]")
            quant_info.append(f"[bold]Altman Z-Score:[/bold]  {z_score} [dim]({quant.altman_interpretation})[/dim]")
            quant_info.append(f"[bold]Accruals Ratio:[/bold]  {accruals}")
            quant_info.append(f"[bold]Red Flags:[/bold]      {len(quant.red_flags)}")

        # 4. Investigation Panel
        inv_info = []
        if inv:
            evasive = "[red]YES[/red]" if inv.evasive_language_detected else "[green]NO[/green]"
            inv_info.append(f"[bold]Evasive Language:[/bold] {evasive}")
            inv_info.append(f"[bold]Related Parties:[/bold] {', '.join(inv.related_parties_detected) if inv.related_parties_detected else 'None detected'}")
            inv_info.append(f"[bold]Red Flags:[/bold]       {len(inv.red_flags)}")
            inv_info.append(f"[bold]Key Quotes:[/bold]      {len(inv.key_quotes)}")
            inv_info.append(f"\n[bold underline]MD&A Findings:[/bold underline]\n[dim]{inv.mdna_findings[:300]}...[/dim]")
            inv_info.append(f"\n[bold underline]Risk Factors Summary:[/bold underline]\n[dim]{inv.risk_factors_summary[:300]}...[/dim]")

        # Display Panels
        console.print(Panel(Group(*company_info), title="Company Details", border_style="blue"))
        console.print(Panel(Group(*rec_info), title="Phase 1: Reconciliation", border_style="magenta"))
        console.print(Panel(Group(*quant_info), title="Phase 2: Quantitative Analysis", border_style="cyan"))
        console.print(Panel(Group(*inv_info), title="Phase 3: Qualitative Investigation", border_style="green"))

        # 5. Consolidated Red Flags
        if red_flags:
            flags_table = Table(title="Consolidated Red Flags (Categorized by Agent)")
            flags_table.add_column("Agent", style="bold")
            flags_table.add_column("Severity", justify="center")
            flags_table.add_column("Title", style="white")
            
            # Sort red flags by agent
            for flag in red_flags:
                sev_color = "red" if flag.severity.value in ["critical", "high"] else "yellow"
                flags_table.add_row(
                    flag.detected_by,
                    f"[{sev_color}]{flag.severity.value.upper()}[/{sev_color}]",
                    flag.title
                )
            console.print(flags_table)

        # Execution Summary
        console.print(f"\n[bold white]Execution Stats:[/bold white]")
        console.print(f"  Duration: {duration:.2f}s | Tokens: {result.get('total_tokens', 0)} | Cost: ${result.get('total_cost_usd', 0.0):.4f}")
        console.print(f"  Final Phase: [magenta]{result.get('current_phase', AuditPhase.FAILED).value}[/magenta]\n")
        
        return {
            "test_name": test_name,
            "phase": result.get("current_phase", AuditPhase.FAILED).value,
            "rec_passed": rec.passed if rec else False,
            "flags_rec": len(rec.red_flags) if rec else 0,
            "flags_quant": len(quant.red_flags) if quant else 0,
            "flags_inv": len(inv.red_flags) if inv else 0,
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
            "flags_rec": 0, "flags_quant": 0, "flags_inv": 0,
            "total_red_flags": 0,
            "tokens": 0, "cost": 0.0, "duration": 0, "success": False
        }


def main():
    configure_logging()
    
    console.print("\n[bold reverse cyan] AuditChain: Full 4-Agent Workflow Validation (V4) [/bold reverse cyan]\n")
    
    # 1. Interactive Model Selection
    console.print("[bold yellow]Select LLM Model for Audit:[/bold yellow]")
    console.print("1) gpt-4o (Smartest, strict rate limits)")
    console.print("2) gpt-4o-mini (Faster, higher rate limits, recommended)")
    
    choice = Prompt.ask("Enter choice", choices=["1", "2"], default="2")
    model_choice = "gpt-4o" if choice == "1" else "gpt-4o-mini"
    
    settings.llm_smart_model = model_choice
    console.print(f"[bold green]Using model:[/bold green] {model_choice}\n")
    
    console.print("[dim]Compiling AuditChain Graph (Collector + Reconciler + Quant + Investigator)...[/dim]")
    graph = build_audit_graph()
    
    # Test only with BHC for now as requested
    tests = [
        ("Full Audit: Bausch Health (BHC)", "0000885590", "BHC"),
    ]
    
    results = []
    for i, (name, cik, ticker) in enumerate(tests):
        if i > 0:
            console.print(f"[yellow]Waiting 60 seconds to reset OpenAI Rate Limits (TPM)...[/yellow]")
            time.sleep(60)
            
        res = run_audit(graph, name, cik, ticker)
        results.append(res)
        console.print("\n")

    # Final Summary Table
    summary_table = Table(title="AuditChain Workflow Summary (V4)")
    summary_table.add_column("Test", style="cyan")
    summary_table.add_column("Final Phase", style="magenta")
    summary_table.add_column("Rec. Pass", justify="center")
    summary_table.add_column("Flags (R/Q/I)", justify="center")
    summary_table.add_column("Total Red Flags", justify="right")
    summary_table.add_column("Tokens", justify="right")
    summary_table.add_column("Cost (USD)", justify="right")
    summary_table.add_column("Duration (s)", justify="right")

    for res in results:
        rec_mark = "[green]✓[/green]" if res["rec_passed"] else "[red]✗[/red]"
        breakdown = f"{res['flags_rec']}/{res['flags_quant']}/{res['flags_inv']}"
            
        summary_table.add_row(
            res["test_name"],
            res["phase"],
            rec_mark,
            breakdown,
            str(res["total_red_flags"]),
            str(res["tokens"]),
            f"{res['cost']:.4f}",
            f"{res['duration']:.2f}"
        )

    console.print(summary_table)
    console.print(f"\n[bold cyan]End of Workflow V4 Validation[/bold cyan]\n")


if __name__ == "__main__":
    main()
