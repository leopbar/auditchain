"""Quick exploration script to load and inspect a company_facts.json.

Run after downloading filings to verify our Pydantic models match
the actual SEC data structure.

Usage:
    python -m scripts.explore_company_facts AAPL
    python -m scripts.explore_company_facts TSLA
"""

from __future__ import annotations

import argparse
import json
import sys

from rich.console import Console
from rich.table import Table

from auditchain.core.config import get_settings
from auditchain.core.logging import configure_logging, get_logger
from auditchain.data.known_fraud_cases import get_benchmark_companies
from auditchain.data.sec_models import CompanyFacts

logger = get_logger(__name__)
console = Console()

KEY_CONCEPTS = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "NetIncomeLoss",
    "Assets",
    "Liabilities",
    "StockholdersEquity",
    "CashAndCashEquivalentsAtCarryingValue",
    "OperatingIncomeLoss",
]


def find_company_by_ticker(ticker: str) -> tuple[str, str] | None:
    """Find CIK and name for a given ticker in our benchmark catalog."""
    for case in get_benchmark_companies():
        if case.ticker.upper() == ticker.upper():
            return case.cik, case.name
    return None


def load_company_facts(cik: str) -> CompanyFacts:
    """Load and parse a company_facts.json file using our Pydantic model."""
    settings = get_settings()
    path = settings.raw_data_dir / "sec_edgar" / cik / "company_facts.json"

    if not path.exists():
        raise FileNotFoundError(
            f"company_facts.json not found at {path}. "
            f"Run: python -m scripts.download_filings --tickers <ticker>"
        )

    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    return CompanyFacts.model_validate(raw)


def show_overview(facts: CompanyFacts) -> None:
    """Print a high-level overview of what concepts are reported."""
    us_gaap_count = len(facts.facts.us_gaap)
    dei_count = len(facts.facts.dei)

    console.print(f"\n[bold cyan]Company:[/bold cyan] {facts.entityName}")
    console.print(f"[bold cyan]CIK:[/bold cyan] {facts.cik}")
    console.print(f"[bold cyan]US GAAP concepts reported:[/bold cyan] {us_gaap_count}")
    console.print(f"[bold cyan]DEI concepts reported:[/bold cyan] {dei_count}\n")


def show_key_concepts(facts: CompanyFacts) -> None:
    """Print a table with the most recent annual value for each key concept."""
    table = Table(title="Key US GAAP concepts (most recent annual values)")
    table.add_column("Concept", style="cyan")
    table.add_column("Most recent FY", style="yellow")
    table.add_column("Value (USD)", style="green", justify="right")
    table.add_column("Periods reported", justify="right")

    for concept_name in KEY_CONCEPTS:
        annual = facts.get_annual_values(concept_name)
        if not annual:
            table.add_row(concept_name, "—", "[dim]not reported[/dim]", "0")
            continue

        latest = annual[-1]
        formatted_value = f"{latest.val:,.0f}"
        table.add_row(
            concept_name,
            latest.end.isoformat(),
            formatted_value,
            str(len(annual)),
        )

    console.print(table)


def show_revenue_history(facts: CompanyFacts) -> None:
    """Print the full annual revenue history."""
    for concept in ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"]:
        annual = facts.get_annual_values(concept)
        if not annual:
            continue

        table = Table(title=f"Annual revenue history ({concept})")
        table.add_column("Fiscal year", style="cyan")
        table.add_column("Period end", style="yellow")
        table.add_column("Value (USD)", style="green", justify="right")
        table.add_column("Form", style="dim")

        for value in annual:
            table.add_row(
                str(value.fy) if value.fy else "—",
                value.end.isoformat(),
                f"{value.val:,.0f}",
                value.form or "—",
            )

        console.print(table)
        return


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker", help="Stock ticker (e.g. AAPL, TSLA, HPQ)")
    args = parser.parse_args()

    configure_logging()

    found = find_company_by_ticker(args.ticker)
    if not found:
        console.print(f"[red]Ticker {args.ticker} not found in benchmark catalog[/red]")
        sys.exit(1)

    cik, _name = found

    try:
        facts = load_company_facts(cik)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)

    show_overview(facts)
    show_key_concepts(facts)
    show_revenue_history(facts)


if __name__ == "__main__":
    main()