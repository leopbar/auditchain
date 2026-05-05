"""Manual test script for the list_filings tool.

Usage:
    python -m scripts.test_list_filings_tool
"""

from rich.console import Console
from rich.table import Table

from auditchain.core.logging import configure_logging
from auditchain.tools.financial_data import list_filings
from auditchain.tools.schemas import FilingSummary, ToolError

console = Console()


def main() -> None:
    configure_logging()

    test_cases = [
        {
            "id": 1,
            "desc": "CIK válido sem filtro (Apple)",
            "args": {"cik": "0000320193"},
            "expected_code": None,
        },
        {
            "id": 2,
            "desc": "CIK válido com filtro 10-K (BHC)",
            "args": {"cik": "0000885590", "filing_type": "10-K"},
            "expected_code": None,
        },
        {
            "id": 3,
            "desc": "CIK válido com limit alto (Apple, 10 filings)",
            "args": {"cik": "0000320193", "limit": 10},
            "expected_code": None,
        },
        {
            "id": 4,
            "desc": "CIK válido com filtro 10-Q (Apple)",
            "args": {"cik": "0000320193", "filing_type": "10-Q"},
            "expected_code": "no_filings_found",  # Accepted if no data in DB
        },
        {
            "id": 5,
            "desc": "CIK que não existe",
            "args": {"cik": "9999999999"},
            "expected_code": "company_not_found",
        },
        {
            "id": 6,
            "desc": "Filing type inválido (Tesla)",
            "args": {"cik": "0001318605", "filing_type": "99-Z"},
            "expected_code": "invalid_filing_type",
        },
    ]

    summary_rows = []
    passed_count = 0

    console.print("\n[bold cyan]Running list_filings tool tests...[/bold cyan]\n")

    for case in test_cases:
        t_id = case["id"]
        desc = case["desc"]
        args = case["args"]

        console.print(f"[bold cyan]Test #{t_id}: {desc}[/bold cyan]")
        console.print(f"  Input: [yellow]{args}[/yellow]")

        try:
            result = list_filings.invoke(args)
        except Exception as e:
            console.print(f"  [bold red]Exception:[/bold red] {e}")
            summary_rows.append((t_id, desc, "Exception", str(e), "FAIL"))
            continue

        result_type = type(result).__name__
        if isinstance(result, list):
            result_type = f"list[{type(result[0]).__name__}]" if result else "list[empty]"

        # Determine pass/fail
        is_passed = False
        count_or_code = ""

        if isinstance(result, list):
            count_or_code = str(len(result))
            if t_id <= 4 and len(result) > 0:
                is_passed = True
            elif t_id <= 4 and len(result) == 0:
                # list_filings shouldn't return empty list, it returns ToolError
                # so this case is theoretically unreachable based on tool logic
                is_passed = False
            
            # Show entries
            console.print(f"  Result: [green]Found {len(result)} filings[/green]")
            for f in result:
                console.print(
                    f"    - {f.accession_number} | {f.filing_type} | {f.fiscal_year} | {f.period_of_report}"
                )
        elif isinstance(result, ToolError):
            count_or_code = result.code
            console.print(f"  Result: [red]ToolError(code='{result.code}', error='{result.error}')[/red]")
            
            if t_id == 4 and result.code == "no_filings_found":
                is_passed = True
            elif t_id == 5 and result.code == "company_not_found":
                is_passed = True
            elif t_id == 6 and result.code in ("no_filings_found", "invalid_filing_type"):
                is_passed = True

        status = "PASS" if is_passed else "FAIL"
        if is_passed:
            passed_count += 1

        console.print(f"  Type:   [white]{result_type}[/white]\n")
        summary_rows.append((t_id, desc, result_type, count_or_code, status))

    # Show summary table
    table = Table(title="list_filings Tool Test Results")
    table.add_column("Test #", justify="right")
    table.add_column("Description", style="cyan")
    table.add_column("Result Type", style="white")
    table.add_column("Count/Code")
    table.add_column("Status", justify="center")

    for t_id, desc, res_type, count_code, status in summary_rows:
        status_color = "green" if status == "PASS" else "red"
        table.add_row(str(t_id), desc, res_type, count_code, f"[{status_color}]{status}[/{status_color}]")

    console.print(table)
    console.print(
        f"\n[bold]{passed_count} of {len(test_cases)} tests passed.[/bold]"
    )


if __name__ == "__main__":
    main()
