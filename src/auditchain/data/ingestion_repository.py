"""Repository layer for ingestion run records.

Encapsulates all database access for the ingestion_runs table.
Follows the same session-injection pattern as repositories.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import JSONB

from auditchain.core.logging import get_logger
from auditchain.data.models import IngestionRunORM

logger = get_logger(__name__)


class IngestionRepository:
    """All database operations for the ingestion_runs table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        ingestion_id: str,
        cik: str,
        is_update: bool = False,
    ) -> IngestionRunORM:
        """Create a new ingestion run record."""
        run = IngestionRunORM(
            id=uuid.UUID(ingestion_id),
            cik=cik,
            status="running",
            stages_completed=[],
            is_update=is_update,
        )
        self._session.add(run)
        self._session.flush()
        logger.info("ingestion_run_created", ingestion_id=ingestion_id, cik=cik)
        return run

    def get(self, ingestion_id: str) -> IngestionRunORM | None:
        """Retrieve an ingestion run by ID."""
        stmt = select(IngestionRunORM).where(
            IngestionRunORM.id == uuid.UUID(ingestion_id)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def update_stage(self, ingestion_id: str, stage_name: str) -> None:
        """Set current_stage and append to stages_completed."""
        run = self.get(ingestion_id)
        if run is None:
            logger.warning("ingestion_run_not_found", ingestion_id=ingestion_id)
            return

        run.current_stage = stage_name
        completed = list(run.stages_completed or [])
        if stage_name not in completed:
            completed.append(stage_name)
        run.stages_completed = completed
        self._session.flush()

    def complete(
        self,
        ingestion_id: str,
        filings_count: int,
        chunks_generated: int,
        financial_items_extracted: int,
    ) -> None:
        """Mark an ingestion run as completed with final statistics."""
        run = self.get(ingestion_id)
        if run is None:
            return

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.current_stage = None
        run.filings_count = filings_count
        run.chunks_generated = chunks_generated
        run.financial_items_extracted = financial_items_extracted
        self._session.flush()
        logger.info("ingestion_run_completed", ingestion_id=ingestion_id)

    def fail(self, ingestion_id: str, error_message: str) -> None:
        """Mark an ingestion run as failed."""
        run = self.get(ingestion_id)
        if run is None:
            return

        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        run.error_message = error_message
        self._session.flush()
        logger.info("ingestion_run_failed", ingestion_id=ingestion_id)
