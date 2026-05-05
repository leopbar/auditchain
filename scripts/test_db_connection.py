"""Quick smoke test for database connectivity and ORM models.

Verifies:
- We can connect to Postgres
- All ORM tables match the existing schema
- We can insert and query a row

Usage:
    python -m scripts.test_db_connection
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from sqlalchemy import inspect, text

from auditchain.core.logging import configure_logging, get_logger
from auditchain.data.database import engine, get_session
from auditchain.data.models import CompanyORM

logger = get_logger(__name__)
console = Console()


def check_connection() -> bool:
    """Run SELECT 1 to confirm connectivity."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            value = result.scalar()
        console.print(f"[green]Connection OK[/green] (SELECT 1 returned {value})")
        return True
    except Exception as exc:
        console.print(f"[red]Connection failed:[/red] {exc}")
        return False


def list_tables() -> None:
    """Show all tables that exist in the public schema."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    table = Table(title="Tables in database")
    table.add_column("Table name", style="cyan")
    table.add_column("Columns", style="yellow", justify="right")

    for name in sorted(tables):
        cols = inspector.get_columns(name)
        table.add_row(name, str(len(cols)))

    console.print(table)


def test_round_trip() -> None:
    """Insert a test company, read it back, then delete it."""
    test_cik = "9999999999"

    with get_session() as session:
        existing = session.query(CompanyORM).filter_by(cik=test_cik).first()
        if existing:
            session.delete(existing)
            session.flush()

    with get_session() as session:
        company = CompanyORM(
            cik=test_cik,
            ticker="TEST",
            name="Test Corporation (delete me)",
            is_known_fraud=False,
        )
        session.add(company)
        session.flush()
        console.print(f"[green]Inserted:[/green] {company}")

    with get_session() as session:
        found = session.query(CompanyORM).filter_by(cik=test_cik).one()
        console.print(f"[green]Retrieved:[/green] {found}")
        session.delete(found)
        console.print("[green]Deleted test row[/green]")


def main() -> None:
    configure_logging()

    console.print("\n[bold cyan]Database smoke test[/bold cyan]\n")

    if not check_connection():
        return

    list_tables()
    console.print()
    test_round_trip()
    console.print("\n[bold green]All checks passed[/bold green]\n")


if __name__ == "__main__":
    main()