"""Run the full ingestion pipeline for all benchmark companies.

Usage:
    python -m scripts.ingest_filings
    python -m scripts.ingest_filings --tickers AAPL TSLA
"""

from __future__ import annotations

import argparse

from rich.console import Console
from rich.table import Table

from auditchain.core.logging import configure_logging, get_logger
from auditchain.data.ingestion import FilingIngestionService
from auditchain.data.known_fraud_cases import get_benchmark_companies

logger = get_logger(__name__)
console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers", nargs="*", help="Limit to specific tickers")
    args = parser.parse_args()

    configure_logging()

    cases = get_benchmark_companies()
    if args.tickers:
        wanted = {t.upper() for t in args.tickers}
        cases = [c for c in cases if c.ticker.upper() in wanted]

    service = FilingIngestionService()

    table = Table(title="Ingestion summary")
    table.add_column("Company", style="cyan")
    table.add_column("Ticker", style="yellow")
    table.add_column("Filings", style="green", justify="right")
    table.add_column("Line items", style="green", justify="right")
    table.add_column("Status", style="magenta")

    grand_totals = {"filings": 0, "line_items": 0, "ok": 0, "skipped": 0}
    for case in cases:
        try:
            result = service.ingest_company(case)
            if result["company"] == 0:
                table.add_row(case.name, case.ticker, "—", "—", "skipped")
                grand_totals["skipped"] += 1
            else:
                table.add_row(
                    case.name,
                    case.ticker,
                    str(result["filings"]),
                    f"{result['line_items']:,}",
                    "ok",
                )
                grand_totals["filings"] += result["filings"]
                grand_totals["line_items"] += result["line_items"]
                grand_totals["ok"] += 1
        except Exception as exc:
            console.print(f"[red]Error ingesting {case.name}:[/red] {exc}")
            table.add_row(case.name, case.ticker, "—", "—", "error")

    console.print(table)
    console.print(
        f"\n[bold green]Done.[/bold green] "
        f"{grand_totals['ok']} companies ingested, "
        f"{grand_totals['filings']} filings, "
        f"{grand_totals['line_items']:,} line items. "
        f"{grand_totals['skipped']} skipped (no data on disk)."
    )


if __name__ == "__main__":
    main()