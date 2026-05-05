"""Manual test script for the get_company tool.

Usage:
    python -m scripts.test_get_company_tool
"""

from rich.console import Console
from rich.table import Table

from auditchain.core.logging import configure_logging
from auditchain.tools.financial_data import get_company
from auditchain.tools.schemas import CompanyInfo, ToolError

console = Console()


def main() -> None:
    configure_logging()

    test_cases = [
        {"input": "AAPL", "expected": CompanyInfo},
        {"input": "bhc", "expected": CompanyInfo},
        {"input": "TSLA", "expected": CompanyInfo},
        {"input": "0000320193", "expected": CompanyInfo},
        {"input": "XYZ123", "expected": ToolError},
        {"input": "9999999999", "expected": ToolError},
    ]

    summary_rows = []
    passed_count = 0

    console.print("\n[bold cyan]Running tool tests...[/bold cyan]\n")

    for case in test_cases:
        identifier = case["input"]
        expected_type = case["expected"]

        console.print(f"Testing input: [cyan]'{identifier}'[/cyan]")

        # Call the tool via .invoke() as required for LangChain tools
        try:
            result = get_company.invoke({"identifier": identifier})
        except Exception as e:
            console.print(f"[bold red]Unexpected exception during invoke:[/bold red] {e}")
            summary_rows.append((identifier, "Exception", "FAIL"))
            continue

        result_type = type(result).__name__
        is_passed = isinstance(result, expected_type)

        if is_passed:
            color = "green"
            status = "PASS"
            passed_count += 1
        else:
            color = "red"
            status = "FAIL"

        console.print(f"  Result: [{color}]{result}[/{color}]")
        console.print(f"  Type:   [white]{result_type}[/white]\n")

        summary_rows.append((identifier, result_type, status))

    # Show summary table
    table = Table(title="get_company Tool Test Results")
    table.add_column("Input", style="cyan")
    table.add_column("Result Type", style="white")
    table.add_column("Status", justify="center")

    for inp, res_type, status in summary_rows:
        status_color = "green" if status == "PASS" else "red"
        table.add_row(inp, res_type, f"[{status_color}]{status}[/{status_color}]")

    console.print(table)
    console.print(
        f"\n[bold]{passed_count} of {len(test_cases)} tests passed.[/bold]"
    )


if __name__ == "__main__":
    main()
