"""Background task runner for company data ingestion with real-time event streaming.

Orchestrates the 5-stage ingestion pipeline (validate, download_facts,
download_filings, parse_xbrl, embed_text) and emits progress events to
the Pub/Sub system for live dashboard updates.
"""

import asyncio
import json
import time
import traceback
from pathlib import Path
from typing import Any

import httpx

from auditchain.core.config import get_settings
from auditchain.core.logging import get_logger
from auditchain.data.database import get_session
from auditchain.data.models import (
    CompanyORM,
    FilingORM,
    FinancialLineItemORM,
    DisclosureORM,
    AuditRunORM,
    AgentStepORM,
    RedFlagORM,
)
from auditchain.data.ingestion_repository import IngestionRepository
from auditchain.data.ingestion import FilingIngestionService
from auditchain.data.text_ingestion import TextIngestionPipeline
from auditchain.data.known_fraud_cases import FraudCase
from auditchain.api.events.publisher import get_publisher
from auditchain.api.events.ingestion_schemas import (
    IngestionStartedEvent,
    StageStartedEvent,
    StageProgressEvent,
    StageCompletedEvent,
    IngestionCompletedEvent,
    IngestionFailedEvent,
)
from auditchain.utils.sec_client import SECClient, download_company

logger = get_logger(__name__)

SEC_DATA = "https://data.sec.gov"


async def run_ingestion_with_streaming(
    ingestion_id: str,
    cik: str,
    force_update: bool = False,
) -> None:
    """Orchestrates a full company ingestion while emitting real-time SSE events.

    This is intended to be run as a background task (via BackgroundTasks or
    asyncio.create_task). It progresses through 5 stages and publishes
    progress events at each step.
    """
    publisher = get_publisher()
    settings = get_settings()
    start_time = time.time()
    current_stage = "validate"

    log = logger.bind(ingestion_id=ingestion_id, cik=cik)
    log.info("ingestion_runner_started")

    # Helpers ---------------------------------------------------------------

    def elapsed() -> float:
        return round(time.time() - start_time, 2)

    async def emit(event: Any) -> None:
        await publisher.publish_raw(ingestion_id, event)

    # Tracking variables ----------------------------------------------------
    company_name: str = "Unknown"
    company_ticker: str | None = None
    filings_count: int = 0
    chunks_generated: int = 0
    financial_items_extracted: int = 0

    # Create DB record ------------------------------------------------------
    with get_session() as session:
        repo = IngestionRepository(session)
        repo.create(ingestion_id, cik, is_update=force_update)

    # Emit started event
    await emit(IngestionStartedEvent(
        ingestion_id=ingestion_id,
        elapsed_seconds=elapsed(),
        cik=cik,
        is_update=force_update,
    ))

    try:
        # ═══════════════════════════════════════════════════════════════════
        # STAGE 1 — VALIDATE
        # ═══════════════════════════════════════════════════════════════════
        current_stage = "validate"
        stage_start = time.time()

        with get_session() as session:
            IngestionRepository(session).update_stage(ingestion_id, current_stage)

        await emit(StageStartedEvent(
            ingestion_id=ingestion_id,
            elapsed_seconds=elapsed(),
            stage="validate",
            description="Validating CIK on SEC EDGAR...",
        ))

        cik_padded = cik.zfill(10)
        submissions_url = f"{SEC_DATA}/submissions/CIK{cik_padded}.json"

        async with httpx.AsyncClient(
            headers={"User-Agent": settings.sec_user_agent},
            timeout=30.0,
            follow_redirects=True,
        ) as http:
            resp = await http.get(submissions_url)
            if resp.status_code == 404:
                raise ValueError(
                    f"CIK {cik} not found on SEC EDGAR. "
                    "Verify the CIK is correct (10-digit, zero-padded)."
                )
            resp.raise_for_status()
            submissions = resp.json()

        company_name = submissions.get("name", "Unknown")
        tickers_list = submissions.get("tickers", [])
        company_ticker = tickers_list[0] if tickers_list else None

        # Verify at least one 10-K exists
        recent_forms = submissions.get("filings", {}).get("recent", {}).get("form", [])
        has_10k = "10-K" in recent_forms
        if not has_10k:
            raise ValueError(
                f"Company '{company_name}' (CIK {cik}) has no 10-K filings on EDGAR."
            )

        total_filings_found = recent_forms.count("10-K")

        await emit(StageCompletedEvent(
            ingestion_id=ingestion_id,
            elapsed_seconds=elapsed(),
            stage="validate",
            duration_seconds=round(time.time() - stage_start, 2),
            summary={
                "company_name": company_name,
                "ticker": company_ticker,
                "total_10k_filings_found": total_filings_found,
            },
        ))
        log.info("stage_validate_completed", company_name=company_name, ticker=company_ticker)

        # ═══════════════════════════════════════════════════════════════════
        # DECISION: DELETE EXISTING DATA IF FORCE UPDATE
        # ═══════════════════════════════════════════════════════════════════
        if force_update:
            deleted_counts = _delete_existing_company_data(cik)
            log.info("existing_data_deleted", **deleted_counts)

        # ═══════════════════════════════════════════════════════════════════
        # STAGE 2 — DOWNLOAD FACTS
        # ═══════════════════════════════════════════════════════════════════
        current_stage = "download_facts"
        stage_start = time.time()

        with get_session() as session:
            IngestionRepository(session).update_stage(ingestion_id, current_stage)

        await emit(StageStartedEvent(
            ingestion_id=ingestion_id,
            elapsed_seconds=elapsed(),
            stage="download_facts",
            description="Downloading company facts from SEC EDGAR...",
        ))

        output_dir = settings.raw_data_dir / "sec_edgar"
        company_dir = output_dir / cik
        company_dir.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(
            headers={"User-Agent": settings.sec_user_agent},
            timeout=30.0,
            follow_redirects=True,
        ) as http:
            facts_url = f"{SEC_DATA}/api/xbrl/companyfacts/CIK{cik_padded}.json"
            await asyncio.sleep(0.15)  # SEC rate limiting
            facts_resp = await http.get(facts_url)
            facts_resp.raise_for_status()
            facts_data = facts_resp.json()

        facts_path = company_dir / "company_facts.json"
        facts_path.write_text(json.dumps(facts_data, indent=2))
        file_size_kb = facts_path.stat().st_size // 1024

        await emit(StageCompletedEvent(
            ingestion_id=ingestion_id,
            elapsed_seconds=elapsed(),
            stage="download_facts",
            duration_seconds=round(time.time() - stage_start, 2),
            summary={"file_size_kb": file_size_kb},
        ))
        log.info("stage_download_facts_completed", file_size_kb=file_size_kb)

        # ═══════════════════════════════════════════════════════════════════
        # STAGE 3 — DOWNLOAD FILINGS
        # ═══════════════════════════════════════════════════════════════════
        current_stage = "download_filings"
        stage_start = time.time()

        with get_session() as session:
            IngestionRepository(session).update_stage(ingestion_id, current_stage)

        await emit(StageStartedEvent(
            ingestion_id=ingestion_id,
            elapsed_seconds=elapsed(),
            stage="download_filings",
            description="Downloading 5 most recent 10-K filings...",
        ))

        # Reuse SECClient from scripts/download_filings.py
        pseudo_case = FraudCase(
            cik=cik,
            ticker=company_ticker or "N/A",
            name=company_name,
            fraud_period=("", ""),
            fraud_type="new_ingestion",
            description="Dynamically ingested company",
            is_known_fraud=False,
        )

        max_filings = 5
        filings_downloaded = 0

        async with SECClient(settings.sec_user_agent) as sec_client:
            # Get submissions to iterate filings with progress events
            recent = submissions.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            accessions = recent.get("accessionNumber", [])
            primary_docs = recent.get("primaryDocument", [])
            filing_dates = recent.get("filingDate", [])

            for form, acc, doc, fdate in zip(forms, accessions, primary_docs, filing_dates):
                if filings_downloaded >= max_filings:
                    break
                if form != "10-K":
                    continue

                filing_dir = company_dir / form / fdate
                filing_dir.mkdir(parents=True, exist_ok=True)
                target = filing_dir / doc

                if not target.exists():
                    try:
                        content = await sec_client.download_filing(acc, cik, doc)
                        target.write_bytes(content)
                    except Exception as e:
                        log.warning("filing_download_failed", form=form, date=fdate, error=str(e))
                        continue

                filings_downloaded += 1
                await emit(StageProgressEvent(
                    ingestion_id=ingestion_id,
                    elapsed_seconds=elapsed(),
                    stage="download_filings",
                    current=filings_downloaded,
                    total=max_filings,
                    message=f"Downloaded filing {filings_downloaded} of {max_filings}: {form}-{fdate}",
                ))

        if filings_downloaded == 0:
            raise ValueError("Failed to download any 10-K filings from EDGAR.")

        filings_count = filings_downloaded
        total_size_bytes = sum(
            f.stat().st_size
            for f in company_dir.rglob("*.htm")
        )

        await emit(StageCompletedEvent(
            ingestion_id=ingestion_id,
            elapsed_seconds=elapsed(),
            stage="download_filings",
            duration_seconds=round(time.time() - stage_start, 2),
            summary={
                "filings_downloaded": filings_downloaded,
                "total_size_mb": round(total_size_bytes / (1024 * 1024), 2),
            },
        ))
        log.info("stage_download_filings_completed", count=filings_downloaded)

        # ═══════════════════════════════════════════════════════════════════
        # STAGE 4 — PARSE XBRL
        # ═══════════════════════════════════════════════════════════════════
        current_stage = "parse_xbrl"
        stage_start = time.time()

        with get_session() as session:
            IngestionRepository(session).update_stage(ingestion_id, current_stage)

        await emit(StageStartedEvent(
            ingestion_id=ingestion_id,
            elapsed_seconds=elapsed(),
            stage="parse_xbrl",
            description="Parsing XBRL data and extracting financial figures...",
        ))

        # Reuse FilingIngestionService from src/auditchain/data/ingestion.py
        ingestion_service = FilingIngestionService()
        result = ingestion_service.ingest_company(pseudo_case)
        financial_items_extracted = result.get("line_items", 0)
        parsed_filings_count = result.get("filings", 0)

        await emit(StageProgressEvent(
            ingestion_id=ingestion_id,
            elapsed_seconds=elapsed(),
            stage="parse_xbrl",
            current=parsed_filings_count,
            total=parsed_filings_count,
            message=f"Parsed {parsed_filings_count} filings, extracted {financial_items_extracted} financial line items",
        ))

        await emit(StageCompletedEvent(
            ingestion_id=ingestion_id,
            elapsed_seconds=elapsed(),
            stage="parse_xbrl",
            duration_seconds=round(time.time() - stage_start, 2),
            summary={
                "filings_parsed": parsed_filings_count,
                "financial_items_extracted": financial_items_extracted,
            },
        ))
        log.info("stage_parse_xbrl_completed", items=financial_items_extracted)

        # ═══════════════════════════════════════════════════════════════════
        # STAGE 5 — EMBED TEXT
        # ═══════════════════════════════════════════════════════════════════
        current_stage = "embed_text"
        stage_start = time.time()

        with get_session() as session:
            IngestionRepository(session).update_stage(ingestion_id, current_stage)

        await emit(StageStartedEvent(
            ingestion_id=ingestion_id,
            elapsed_seconds=elapsed(),
            stage="embed_text",
            description="Generating embeddings from filing text...",
        ))

        # Reuse TextIngestionPipeline from src/auditchain/data/text_ingestion.py
        text_pipeline = TextIngestionPipeline()
        text_pipeline.ingest_all_for_company(cik)

        # Count chunks generated
        from sqlalchemy import select, func
        with get_session() as session:
            company_orm = session.execute(
                select(CompanyORM).where(CompanyORM.cik == cik)
            ).scalar_one_or_none()

            if company_orm:
                chunks_generated = session.execute(
                    select(func.count(DisclosureORM.id))
                    .join(FilingORM, DisclosureORM.filing_id == FilingORM.id)
                    .where(FilingORM.company_id == company_orm.id)
                ).scalar() or 0
            else:
                chunks_generated = 0

        # Count sections found
        sections_found: list[str] = []
        with get_session() as session:
            company_orm = session.execute(
                select(CompanyORM).where(CompanyORM.cik == cik)
            ).scalar_one_or_none()
            if company_orm:
                rows = session.execute(
                    select(DisclosureORM.section)
                    .join(FilingORM, DisclosureORM.filing_id == FilingORM.id)
                    .where(FilingORM.company_id == company_orm.id)
                    .distinct()
                ).scalars().all()
                sections_found = list(rows)

        await emit(StageCompletedEvent(
            ingestion_id=ingestion_id,
            elapsed_seconds=elapsed(),
            stage="embed_text",
            duration_seconds=round(time.time() - stage_start, 2),
            summary={
                "total_chunks": chunks_generated,
                "sections_found": sections_found,
            },
        ))
        log.info("stage_embed_text_completed", chunks=chunks_generated)

        # ═══════════════════════════════════════════════════════════════════
        # FINALIZATION
        # ═══════════════════════════════════════════════════════════════════
        total_duration = round(time.time() - start_time, 2)

        with get_session() as session:
            repo = IngestionRepository(session)
            repo.complete(
                ingestion_id,
                filings_count=filings_count,
                chunks_generated=chunks_generated,
                financial_items_extracted=financial_items_extracted,
            )

        await emit(IngestionCompletedEvent(
            ingestion_id=ingestion_id,
            elapsed_seconds=elapsed(),
            cik=cik,
            company_name=company_name,
            ticker=company_ticker,
            filings_count=filings_count,
            chunks_generated=chunks_generated,
            financial_items_extracted=financial_items_extracted,
            total_duration_seconds=total_duration,
        ))
        log.info("ingestion_completed", duration_s=total_duration)

    except Exception as e:
        log.exception("ingestion_runner_failed", stage=current_stage)

        with get_session() as session:
            IngestionRepository(session).fail(ingestion_id, str(e))

        await emit(IngestionFailedEvent(
            ingestion_id=ingestion_id,
            elapsed_seconds=elapsed(),
            failed_stage=current_stage,
            error_message=str(e),
        ))

    finally:
        await publisher.close(ingestion_id)
        log.info("ingestion_runner_finalized")


def _delete_existing_company_data(cik: str) -> dict[str, int]:
    """Delete all existing data for a company in the correct dependency order.
    
    Returns a dict with counts of deleted rows per table.

    NOTE: This does not attempt to roll back partial data from a failed 
    previous ingestion. That is documented as future work.
    """
    log = logger.bind(cik=cik)
    counts: dict[str, int] = {}

    with get_session() as session:
        # Find company
        company = session.execute(
            select(CompanyORM).where(CompanyORM.cik == cik)
        ).scalar_one_or_none()

        if company is None:
            log.info("no_existing_data_to_delete")
            return counts

        company_id = company.id

        # Find filings
        filing_ids = [
            f.id for f in
            session.execute(
                select(FilingORM).where(FilingORM.company_id == company_id)
            ).scalars().all()
        ]

        # Find audit runs referencing those filings
        if filing_ids:
            from sqlalchemy import delete

            audit_run_ids = [
                r.id for r in
                session.execute(
                    select(AuditRunORM).where(AuditRunORM.filing_id.in_(filing_ids))
                ).scalars().all()
            ]

            if audit_run_ids:
                # Delete red_flags
                result = session.execute(
                    delete(RedFlagORM).where(RedFlagORM.run_id.in_(audit_run_ids))
                )
                counts["red_flags"] = result.rowcount

                # Delete agent_steps
                result = session.execute(
                    delete(AgentStepORM).where(AgentStepORM.run_id.in_(audit_run_ids))
                )
                counts["agent_steps"] = result.rowcount

                # Delete audit_runs
                result = session.execute(
                    delete(AuditRunORM).where(AuditRunORM.id.in_(audit_run_ids))
                )
                counts["audit_runs"] = result.rowcount

            # Delete disclosures
            result = session.execute(
                delete(DisclosureORM).where(DisclosureORM.filing_id.in_(filing_ids))
            )
            counts["disclosures"] = result.rowcount

            # Delete financial_line_items
            result = session.execute(
                delete(FinancialLineItemORM).where(FinancialLineItemORM.filing_id.in_(filing_ids))
            )
            counts["financial_line_items"] = result.rowcount

            # Delete filings
            result = session.execute(
                delete(FilingORM).where(FilingORM.company_id == company_id)
            )
            counts["filings"] = result.rowcount

        # Delete company
        from sqlalchemy import delete
        result = session.execute(
            delete(CompanyORM).where(CompanyORM.id == company_id)
        )
        counts["companies"] = result.rowcount

    log.info("company_data_deleted", **counts)
    return counts
