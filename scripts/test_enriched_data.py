"""Test script to verify enriched financial data extraction.

Validates that the updated get_financial_summary tool can retrieve all 
17 standardized financial indicators for a given company filing.

Usage:
    python -m scripts.test_enriched_data
"""

import sys
from typing import Any

from rich.console import Console
from rich.table import Table

from auditchain.core.logging import configure_logging, get_logger
from auditchain.tools.financial_data import get_financial_summary, list_filings

logger = get_logger(__name__)
console = Console()

INDICATORS = [
    "revenue", "cost_of_revenue", "gross_profit", "operating_expenses",
    "operating_income", "net_income", "total_assets", "current_assets",
    "accounts_receivable", "inventory", "total_liabilities",
    "current_liabilities", "stockholders_equity", "cash",
    "cash_from_operations", "cash_from_investing", "cash_from_financing"
]


def format_usd(value: float | None) -> str:
    """Format numeric value as USD currency string."""
    if value is None:
        return "[red]NOT AVAILABLE[/red]"
    
    abs_val = abs(value)
    if abs_val >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if abs_val >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    return f"${value:,.2f}"


def test_company_data(name: str, ticker: str, cik: str) -> dict:
    """Tests data enrichment for a specific company."""
    console.rule(f"[bold cyan]{name} ({ticker})[/bold cyan]", style="cyan")
    
    # 1. Get latest 10-K
    console.print(f"[dim]Searching for latest 10-K for CIK {cik}...[/dim]")
    filings = list_filings.invoke({"cik": cik, "filing_type": "10-K", "limit": 1})
    
    if isinstance(filings, list) and len(filings) > 0:
        filing = filings[0]
        console.print(f"[dim]Found filing ID {filing.id} (Period: {filing.period_of_report})[/dim]")
        
        # 2. Get financial summary (now returning FinancialPeriod)
        result = get_financial_summary.invoke({"filing_id": filing.id})
        
        if hasattr(result, "error"):
             console.print(f"[bold red]Error calling tool:[/bold red] {result.error}")
             return {"ticker": ticker, "available": 0, "status": "ERROR"}

        # 3. Build detail table
        detail_table = Table(title=f"Financial Indicators for {ticker}", box=None)
        detail_table.add_column("Indicator", style="white")
        detail_table.add_column("Value", justify="right")
        detail_table.add_column("Status", justify="center")
        
        found_count = 0
        for field in INDICATORS:
            val = getattr(result, field, None)
            status = "[green]✓[/green]" if val is not None else "[red]✗[/red]"
            if val is not None:
                found_count += 1
            detail_table.add_row(field, format_usd(val), status)
            
        console.print(detail_table)
        console.print(f"\n[bold]{found_count} of {len(INDICATORS)} financial indicators available.[/bold]")
        
        return {
            "name": name,
            "ticker": ticker,
            "available": f"{found_count}/{len(INDICATORS)}",
            "status": "[green]OK[/green]" if found_count >= 10 else "[yellow]PARTIAL[/yellow]"
        }
    else:
        error_msg = filings.error if hasattr(filings, "error") else "No filings found"
        console.print(f"[bold red]Failed to find filings:[/bold red] {error_msg}")
        return {"name": name, "ticker": ticker, "available": "0/17", "status": "[red]FAILED[/red]"}


def main():
    configure_logging()
    console.print("\n[bold cyan]AuditChain: Enriched Financial Data Validation[/bold cyan]\n")
    
    companies = [
        ("Apple Inc.", "AAPL", "0000320193"),
        ("Bausch Health", "BHC", "0000885590"),
        ("Tesla Inc.", "TSLA", "0001318605"),
    ]
    
    summary_results = []
    for name, ticker, cik in companies:
        res = test_company_data(name, ticker, cik)
        summary_results.append(res)
        console.print("\n")

    # Final Summary Table
    summary_table = Table(title="Data Enrichment Summary")
    summary_table.add_column("Company", style="cyan")
    summary_table.add_column("Ticker", style="magenta")
    summary_table.add_column("Indicators Available", justify="center")
    summary_table.add_column("Status", justify="center")

    for res in summary_results:
        summary_table.add_row(
            res.get("name", "Unknown"),
            res.get("ticker", "Unknown"),
            res.get("available", "0/17"),
            res.get("status", "[red]ERROR[/red]")
        )

    console.print(summary_table)
    console.print("\n[dim]Note: If indicators are 0/17, you may need to re-run the ingestion script.[/dim]\n")


if __name__ == "__main__":
    main()
