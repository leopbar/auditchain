"""Test script for quantitative tools with real database data.

Validates the Beneish M-Score, Altman Z-Score, and Accruals Ratio 
calculations using actual financial data extracted from the database.

Usage:
    python -m scripts.test_quant_tools
"""

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
from auditchain.tools.quantitative import (
    compute_beneish_mscore_simplified,
    compute_altman_zscore_simplified,
    compute_accruals_ratio
)

logger = get_logger(__name__)
console = Console()


def run_test(test_name: str, cik: str, ticker: str | None) -> dict:
    """Runs quantitative tests for a company and returns metrics."""
    console.rule(f"[bold cyan]{test_name}[/bold cyan]", style="cyan")
    
    # 1. Get real data via collector_node
    state = create_initial_state(str(uuid.uuid4()), cik, ticker)
    console.print(f"[dim]Invoking collector_node for {ticker or cik}...[/dim]")
    update = collector_node(state)
    
    cd = update.get("company_data")
    if not cd:
        console.print("[bold red]Failed to collect company data.[/bold red]")
        return {"ticker": ticker, "success": False}

    current = cd.current_period
    prior = cd.historical_periods[0] if cd.historical_periods else None
    
    console.print(f"[dim]Current Period: {current.fiscal_year} | Prior Period: {prior.fiscal_year if prior else 'None'}[/dim]")

    results = {}
    
    # 2. Test Tools
    # Beneish
    if prior:
        beneish = compute_beneish_mscore_simplified.invoke({"current": current, "prior": prior})
        results["beneish"] = beneish
    else:
        results["beneish"] = None
        console.print("[yellow]Skipping Beneish (requires historical period).[/yellow]")

    # Altman
    altman = compute_altman_zscore_simplified.invoke({"period": current})
    results["altman"] = altman

    # Accruals
    accruals = compute_accruals_ratio.invoke({"period": current})
    results["accruals"] = accruals

    # 3. Display Detail Table
    detail_table = Table(title=f"Quantitative Analysis Detail: {ticker}", box=None)
    detail_table.add_column("Check", style="white")
    detail_table.add_column("Result", justify="center")
    detail_table.add_column("Value", justify="right")
    detail_table.add_column("Interpretation", style="dim")

    for key, res in results.items():
        if not res: continue
        
        pass_str = "[green]PASS[/green]" if res.passed else "[red]FAIL[/red]"
        val_str = f"{res.actual:.4f}" if res.actual is not None else "N/A"
        detail_table.add_row(
            res.name,
            pass_str,
            val_str,
            res.notes
        )
    
    console.print(detail_table)
    
    return {
        "ticker": ticker,
        "name": cd.name,
        "beneish": results["beneish"],
        "altman": results["altman"],
        "accruals": results["accruals"],
        "success": True
    }


def main():
    configure_logging()
    console.print("\n[bold cyan]AuditChain: Quantitative Tools Validation (Real Data)[/bold cyan]\n")
    
    companies = [
        ("Apple Control", "0000320193", "AAPL"),
        ("Bausch Anomaly", "0000885590", "BHC"),
        ("Tesla Growth", "0001318605", "TSLA"),
    ]
    
    test_metrics = []
    for name, cik, ticker in companies:
        try:
            res = run_test(name, cik, ticker)
            test_metrics.append(res)
            console.print("\n")
        except Exception:
            console.print(f"[bold red]Exception testing {ticker}:[/bold red]\n{traceback.format_exc()}")

    # Final Summary Table
    summary_table = Table(title="Quantitative Tools Summary")
    summary_table.add_column("Company", style="cyan")
    summary_table.add_column("Beneish M-Score", justify="center")
    summary_table.add_column("Altman Z-Score", justify="center")
    summary_table.add_column("Accruals Ratio", justify="center")

    for m in test_metrics:
        if not m.get("success"): continue
        
        # Beneish cell
        b = m["beneish"]
        b_val = f"{b.actual:.2f}" if (b and b.actual is not None) else "N/A"
        b_cell = f"{b_val} ({'[green]PASS[/green]' if (b and b.passed) else '[red]FAIL[/red]'})" if b else "N/A"
        
        # Altman cell
        a = m["altman"]
        if a and a.actual is not None:
            color = "green" if a.actual > 2.99 else ("yellow" if a.actual >= 1.81 else "red")
            a_cell = f"[{color}]{a.actual:.2f}[/{color}]"
        else:
            a_cell = "N/A"
            
        # Accruals cell
        acc = m["accruals"]
        acc_val = f"{acc.actual:.2f}" if (acc and acc.actual is not None) else "N/A"
        acc_cell = f"{acc_val} ({'[green]PASS[/green]' if (acc and acc.passed) else '[red]FAIL[/red]'})" if acc else "N/A"
        
        summary_table.add_row(m["ticker"], b_cell, a_cell, acc_cell)

    console.print(summary_table)
    console.print("\n[dim]Altman Z-Score Legend: [green]>2.99 Safe[/green] | [yellow]1.81-2.99 Grey[/yellow] | [red]<1.81 Distress[/red][/dim]\n")


if __name__ == "__main__":
    main()
