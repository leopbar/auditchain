"""Remove a company and all its related data from the database.

Usage:
    python -m scripts.cleanup_company --cik 0001067983
"""

import argparse
import sys

from rich.console import Console
from sqlalchemy import select

from auditchain.core.logging import configure_logging
from auditchain.data.database import get_session
from auditchain.data.models import CompanyORM

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cik", required=True, help="SEC CIK of the company to remove")
    args = parser.parse_args()

    configure_logging()

    with get_session() as session:
        # Find the company
        # We use select() and scalar_one_or_none() as per SQLAlchemy 2.0 standards
        stmt = select(CompanyORM).where(CompanyORM.cik == args.cik)
        company = session.execute(stmt).scalar_one_or_none()

        if not company:
            console.print(
                f"[bold red]Error:[/bold red] Company with CIK [yellow]{args.cik}[/yellow] not found in database."
            )
            sys.exit(1)

        # Gather counts before deletion for the summary
        num_filings = len(company.filings)

        console.print("\n[bold cyan]Found Company:[/bold cyan]")
        console.print(f"  Name:   [white]{company.name}[/white]")
        console.print(f"  Ticker: [yellow]{company.ticker or 'N/A'}[/yellow]")
        console.print(f"  CIK:    [blue]{company.cik}[/blue]")
        console.print(
            f"  Filings to be removed: [red]{num_filings}[/red] (along with all their financial line items)"
        )

        # Confirmation step
        console.print(
            "\n[bold red]WARNING:[/bold red] This action is destructive and cannot be undone."
        )
        confirm = input("Type 'yes' to confirm deletion: ").strip().lower()

        if confirm != "yes":
            console.print("[yellow]Deletion cancelled.[/yellow]")
            return

        # Since relationships are configured with cascade="all, delete-orphan",
        # deleting the parent CompanyORM instance removes all related Filings
        # and FinancialLineItems automatically.
        session.delete(company)

        # The get_session() context manager handles session.commit() upon successful exit.
        console.print(
            f"\n[bold green]Success![/bold green] Company [white]'{company.name}'[/white] "
            f"and its {num_filings} filings have been removed from the database."
        )


if __name__ == "__main__":
    main()
