"""Manual test script for the get_financial_summary tool.

Usage:
    python -m scripts.test_get_financial_summary_tool
"""

from rich.console import Console
from rich.table import Table

from auditchain.core.logging import configure_logging
from auditchain.tools.financial_data import get_financial_summary, list_filings
from auditchain.tools.schemas import FinancialSummary, FilingSummary, ToolError

console = Console()


def format_value(v: float | None) -> str:
    """Format float as USD or return 'not reported'."""
    if v is None:
        return "[italic dim]not reported[/italic dim]"
    return f"${v:,.2f} USD"


def main() -> None:
    configure_logging()

    test_scenarios = [
        {
            "id": 1,
            "desc": "Apple - 10-K mais recente",
            "cik": "0000320193",
            "filing_type": "10-K",
            "index": 0,
            "limit": 1,
        },
        {
            "id": 2,
            "desc": "BHC - 10-K mais recente",
            "cik": "0000885590",
            "filing_type": "10-K",
            "index": 0,
            "limit": 1,
        },
        {
            "id": 3,
            "desc": "Tesla - 10-K mais recente",
            "cik": "0001318605",
            "filing_type": "10-K",
            "index": 0,
            "limit": 1,
        },
        {
            "id": 4,
            "desc": "Apple - filing antigo (5º mais recente)",
            "cik": "0000320193",
            "filing_type": "10-K",
            "index": -1,  # Last of the 5
            "limit": 5,
        },
        {
            "id": 5,
            "desc": "Filing ID inexistente",
            "filing_id": 999999,
        },
    ]

    summary_rows = []
    passed_count = 0

    console.print("\n[bold cyan]Running get_financial_summary tool tests...[/bold cyan]\n")

    for scenario in test_scenarios:
        t_id = scenario["id"]
        desc = scenario["desc"]
        
        console.print(f"[bold cyan]Test #{t_id}: {desc}[/bold cyan]")

        # Step 1: Resolve filing_id if needed
        filing_id = scenario.get("filing_id")
        if filing_id is None:
            cik = scenario["cik"]
            f_type = scenario["filing_type"]
            limit = scenario["limit"]
            index = scenario["index"]
            
            console.print(f"  Resolving filing_id for {cik} ({f_type})...")
            list_res = list_filings.invoke({"cik": cik, "filing_type": f_type, "limit": limit})
            
            if isinstance(list_res, list) and len(list_res) > 0:
                # Handle positive or negative index
                try:
                    target_filing = list_res[index]
                    filing_id = target_filing.id
                except IndexError:
                    filing_id = None
            else:
                filing_id = None

        if filing_id is None:
            console.print("  [bold red]Error: Could not retrieve filing for testing.[/bold red]")
            summary_rows.append((t_id, desc, "FAIL", "—", "could not retrieve filing"))
            continue

        console.print(f"  Testing Filing ID: [bold yellow]{filing_id}[/bold yellow]")

        # Step 2: Call get_financial_summary
        try:
            result = get_financial_summary.invoke({"filing_id": filing_id})
        except Exception as e:
            console.print(f"  [bold red]Exception:[/bold red] {e}")
            summary_rows.append((t_id, desc, "Exception", "—", "FAIL"))
            continue

        result_type = type(result).__name__
        is_passed = False
        indicators_found = "—"

        if isinstance(result, FinancialSummary):
            is_passed = (t_id <= 4)
            
            # Count indicators
            numeric_fields = [
                result.revenue, result.net_income, result.total_assets,
                result.total_liabilities, result.stockholders_equity,
                result.cash, result.operating_income
            ]
            count = sum(1 for v in numeric_fields if v is not None)
            indicators_found = str(count)

            # Show details
            console.print(f"  Result: [green]FinancialSummary found[/green]")
            console.print(f"    - Filing ID: {result.filing_id}")
            console.print(f"    - Period End: {result.period_of_report}")
            console.print(f"    - Fiscal Year: {result.fiscal_year}")
            console.print(f"    - Revenue: {format_value(result.revenue)}")
            console.print(f"    - Net Income: {format_value(result.net_income)}")
            console.print(f"    - Operating Income: {format_value(result.operating_income)}")
            console.print(f"    - Cash: {format_value(result.cash)}")
            console.print(f"    - Total Assets: {format_value(result.total_assets)}")
            console.print(f"    - Total Liabilities: {format_value(result.total_liabilities)}")
            console.print(f"    - Equity: {format_value(result.stockholders_equity)}")

        elif isinstance(result, ToolError):
            console.print(f"  Result: [red]ToolError(code='{result.code}', error='{result.error}')[/red]")
            if t_id == 5 and result.code == "filing_not_found":
                is_passed = True

        status = "PASS" if is_passed else "FAIL"
        if is_passed:
            passed_count += 1

        console.print(f"  Type:   [white]{result_type}[/white]\n")
        summary_rows.append((t_id, desc, result_type, indicators_found, status))

    # Summary Table
    table = Table(title="get_financial_summary Tool Test Results")
    table.add_column("Test #", justify="right")
    table.add_column("Description", style="cyan")
    table.add_column("Result Type", style="white")
    table.add_column("Indicators Found", justify="center")
    table.add_column("Status", justify="center")

    for t_id, desc, res_type, ind_count, status in summary_rows:
        status_color = "green" if status == "PASS" else "red"
        table.add_row(str(t_id), desc, res_type, ind_count, f"[{status_color}]{status}[/{status_color}]")

    console.print(table)
    console.print(f"\n[bold]{passed_count} of {len(test_scenarios)} tests passed.[/bold]")


if __name__ == "__main__":
    main()
