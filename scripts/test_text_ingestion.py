"""Test script for the Text Ingestion Pipeline.

Ingests textual disclosures (MD&A, Risk Factors, etc.) for Apple Inc. (AAPL),
generates embeddings, and verifies the resulting database records.

Usage:
    python -m scripts.test_text_ingestion
"""

import sys
import traceback
from sqlalchemy import select, func

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from auditchain.core.logging import configure_logging, get_logger
from auditchain.data.database import get_session
from auditchain.data.models import FilingORM, DisclosureORM, CompanyORM
from auditchain.data.text_ingestion import TextIngestionPipeline

logger = get_logger(__name__)
console = Console()


def verify_ingestion(cik: str):
    """Queries the database to verify text ingestion results."""
    console.rule("[bold cyan]Verifying Database Records[/bold cyan]", style="cyan")
    
    with get_session() as session:
        # 1. Total chunks for this company
        query = (
            select(func.count(DisclosureORM.id))
            .join(FilingORM, DisclosureORM.filing_id == FilingORM.id)
            .join(CompanyORM, FilingORM.company_id == CompanyORM.id)
            .where(CompanyORM.cik == cik)
        )
        total_chunks = session.execute(query).scalar()
        
        if total_chunks == 0:
            console.print("[bold red]No disclosure records found in database for this company.[/bold red]")
            return

        console.print(f"[green]Total chunks ingested:[/green] {total_chunks}")

        # 2. Breakdown by section
        section_query = (
            select(DisclosureORM.section, func.count(DisclosureORM.id))
            .join(FilingORM, DisclosureORM.filing_id == FilingORM.id)
            .join(CompanyORM, FilingORM.company_id == CompanyORM.id)
            .where(CompanyORM.cik == cik)
            .group_by(DisclosureORM.section)
        )
        section_results = session.execute(section_query).all()
        
        table = Table(title="Disclosure Breakdown by Section")
        table.add_column("Section", style="magenta")
        table.add_column("Chunk Count", justify="right")
        
        for section, count in section_results:
            table.add_row(section, str(count))
        
        console.print(table)

        # 3. Sample check and embedding validation
        sample_query = (
            select(DisclosureORM)
            .join(FilingORM, DisclosureORM.filing_id == FilingORM.id)
            .join(CompanyORM, FilingORM.company_id == CompanyORM.id)
            .where(CompanyORM.cik == cik)
            .where(DisclosureORM.section == "mdna")
            .limit(1)
        )
        sample = session.execute(sample_query).scalar_one_or_none()
        
        if sample:
            content_preview = sample.content[:200].replace("\n", " ") + "..."
            has_embedding = sample.embedding is not None
            emb_status = "[green]YES[/green]" if has_embedding else "[red]NO[/red]"
            
            sample_panel = Panel(
                f"[bold]Section:[/bold] {sample.section}\n"
                f"[bold]Tokens:[/bold] {sample.token_count}\n"
                f"[bold]Embedding Generated:[/bold] {emb_status}\n"
                f"[bold]Content Preview:[/bold] {content_preview}",
                title="Disclosure Sample (MD&A)",
                border_style="green"
            )
            console.print(sample_panel)
        else:
            console.print("[yellow]No MD&A sample found to display.[/yellow]")


def main():
    configure_logging()
    console.print("\n[bold cyan]AuditChain: Text Ingestion Pipeline Validation[/bold cyan]\n")
    
    cik = "0000320193" # Apple
    pipeline = TextIngestionPipeline()
    
    # 1. Run Ingestion
    console.rule(f"[bold cyan]Ingesting Text for CIK {cik}[/bold cyan]", style="cyan")
    console.print(f"[dim]Note: This will call OpenAI Embeddings API (text-embedding-3-small).[/dim]")
    
    try:
        pipeline.ingest_all_for_company(cik)
        console.print("[bold green]Ingestion process completed successfully![/bold green]\n")
    except Exception:
        console.print("[bold red]Ingestion process failed with exception:[/bold red]")
        console.print(traceback.format_exc())
    
    # 2. Verify Results
    try:
        verify_ingestion(cik)
    except Exception:
        console.print("[bold red]Verification failed with exception:[/bold red]")
        console.print(traceback.format_exc())

    console.print("\n[bold cyan]End of Validation[/bold cyan]\n")


if __name__ == "__main__":
    main()
